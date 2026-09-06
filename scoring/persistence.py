"""Persist a scored snapshot to the `scores` table.

Design (locked with Stephen 2026-09-05):

  * APPEND, never overwrite. One row per framework+dimension per report,
    tagged with the report_id it was computed for. A regeneration adds a
    new set of rows; the old set stays. That is what makes the table a
    trend source for Tier 4 rather than a cache of "current" scores.

  * Written from reports.services.generate_and_lock, inside the same
    transaction as the report row -- not from build_snapshot_context,
    which runs on every render including previews. A stored score
    therefore always means "this is what a report of record said".

  * The four frameworks use different taxonomies (V1 dimensions, V2
    modules, V3 steps, Efficiency components). reports.context already
    normalizes all of them to one {overall, items, priority_gaps} shape,
    so this module consumes that rather than re-deriving four result
    types. The framework key is stored alongside `dimension`, so the
    flattened namespace stays unambiguous when queried.

A failure here must never lose a report: the caller is expected to treat
persist_snapshot_scores as best-effort.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# reports.context normalizes every framework to this one key.
_ITEM_KEYS = ("items",)

_OVERALL_DIMENSION = "__overall__"


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _ITEM_KEYS:
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def _row(company_id, engagement_id, report_id, framework, dimension,
         score, maturity_level, components, confidence, gaps, now):
    return (
        company_id, engagement_id, report_id, framework, dimension,
        score, maturity_level,
        json.dumps(components) if components is not None else None,
        confidence,
        json.dumps(gaps) if gaps is not None else None,
        now,
    )


def persist_snapshot_scores(
    cursor,
    *,
    company_id: str,
    engagement_id: str,
    report_id: str,
    payloads: dict[str, dict[str, Any]],
    now,
) -> int:
    """Insert one row per framework overall + per framework item.

    `payloads` maps framework key -> the snapshot payload produced by
    reports.context (must contain "overall"; item list and "gaps" are
    optional). Returns the number of rows written.
    """
    rows = []
    for framework, payload in payloads.items():
        overall = payload.get("overall") or {}
        rows.append(_row(
            company_id, engagement_id, report_id, framework, _OVERALL_DIMENSION,
            overall.get("score_0_100"), overall.get("maturity_level"),
            {k: v for k, v in overall.items() if k != "score_0_100"},
            overall.get("confidence_level"), payload.get("gaps"), now,
        ))
        for item in _items(payload):
            rows.append(_row(
                company_id, engagement_id, report_id, framework,
                item.get("name") or item.get("key") or "unnamed",
                item.get("score_0_100"), item.get("maturity_level"),
                item, item.get("confidence_level"), None, now,
            ))

    if not rows:
        return 0

    cursor.executemany(
        """
        INSERT INTO scores
            (id, company_id, engagement_id, report_id, framework, dimension,
             score, maturity_level, score_components, confidence_level,
             gaps_identified, calculated_at)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s, %s::jsonb, %s)
        """,
        rows,
    )
    logger.info("scores: persisted %d rows for report %s", len(rows), report_id)
    return len(rows)
