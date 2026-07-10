"""
scoring.engine — Orchestrator for the four framework aggregators.

Loads engagement data from the database, builds normalized response
records, and dispatches scoring to v1_audit, v2_readiness, v3_governance,
and efficiency. Returns a CombinedScoringResult containing all four
framework outputs plus engagement metadata.

This module is the only scoring component that talks to the Django ORM.
The four framework aggregators are pure-logic (Question + ResponseRecord
in, Result dataclass out); the engine is the place where DB rows become
ResponseRecord objects.

LIFECYCLE
---------
A typical scoring run for one engagement:

    1. Caller invokes score_engagement(engagement_id)
    2. Engine loads engagement + tier + respondent list
    3. For each completed respondent, engine loads their responses
       and converts the responses table rows into ResponseRecord
    4. Engine invokes v1_audit + v2_readiness + v3_governance + efficiency
    5. Engine assembles CombinedScoringResult and returns

Triggered by:
  - A background RQ job after the respondent completes the questionnaire
    (Tier 1) — `scoring.jobs.score_engagement_job(engagement_id)`
  - Buyer-initiated "Generate report" action (Tier 2/3) once coverage
    is met — same entry point

TIER 1 vs TIER 2/3
------------------
Tier 1 has exactly one respondent. The engine loads that respondent's
responses and dispatches directly to the framework scorers, which expect
single-respondent input.

Tier 2/3 have multiple respondents. The current implementation handles
Tier 1 fully; Tier 2/3 aggregation strategy is hooked but not finalized.
The intended approach (v0.2): score each respondent independently against
each framework, then average the framework Result.dimensions /
.modules / .steps / .components across respondents. This preserves
per-respondent integrity (which honest answers required by Decision 7-8)
while producing engagement-level scores. Other strategies that were
considered:

  - Per-question mean across respondents, then score the mean. Loses
    per-respondent dispersion signal. Rejected.
  - Multi-response retention (per-question dispersion + consensus in the
    report). Defer to a future enhancement; not a v0.2 requirement.

CANONICAL RESPONSE RECORD
-------------------------
All four framework modules define their own ResponseRecord dataclass with
an identical shape (question_id, answer_value, is_dont_know, has_note,
has_attachments). The engine builds a single dict of v1_audit.ResponseRecord
instances and passes the same dict to all four scorers — Python's
runtime duck-typing handles the cross-module type. A future refactor
could move ResponseRecord into a shared types module; for v0.1 the
duplication is harmless and keeps each framework standalone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from django.db import connection

from questionnaire.question_bank import QUESTIONS
from scoring.frameworks import efficiency, v1_audit, v2_readiness, v3_governance


# Keys the framework aggregators may access on any question. Question
# dicts in question_bank omit keys that don't apply to them; merging
# these defaults guarantees the attribute exists on the namespace.
_AGGREGATOR_DEFAULTS: dict = {
    "subsection": None,
    "matrix_rows": None,
    "matrix_columns": None,
    "skip_logic": None,
    "scoring_overrides": None,
    "extended_metadata": None,
    "notes": None,
    "role_visibility": None,
    "required": False,
    "scoring_weight": None,
    "framework_mappings": None,
}


def _wrap_for_aggregator(q: dict) -> SimpleNamespace:
    """Adapt a dict-shaped question row to the attribute-access shape the
    framework aggregators expect (e.g. `question.framework_mappings`,
    `question.id`, `question.subsection`).

    The four framework modules were written against a Question dataclass
    that was never materialized; production `QUESTIONS` is a list of
    plain dicts. SimpleNamespace gives attribute access; merged defaults
    guarantee every aggregator-accessed attribute exists even when the
    source dict omits the key.
    """
    return SimpleNamespace(**{**_AGGREGATOR_DEFAULTS, **q})

# Cached once at module import. The aggregators are pure (no mutation),
# so a single shared sequence per process is correct.
_QUESTIONS_AS_NS: tuple[SimpleNamespace, ...] = tuple(
    _wrap_for_aggregator(q) for q in QUESTIONS
)

# Use v1_audit's ResponseRecord as the canonical engine type. All four
# framework modules accept this shape at runtime.
ResponseRecord = v1_audit.ResponseRecord

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Result type
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class CombinedScoringResult:
    """All four framework scores plus engagement metadata."""
    engagement_id: str
    tier: str                     # 'tier_1', 'tier_2', 'tier_3'
    respondent_count: int         # how many completed respondents contributed
    response_count: int           # total response rows across all respondents
    coverage_complete: bool       # for Tier 2+, did we meet sample-size minimums
    v1: v1_audit.V1FrameworkResult
    v2: v2_readiness.V2FrameworkResult
    v3: v3_governance.V3FrameworkResult
    eff: efficiency.EfficiencyFrameworkResult


# ----------------------------------------------------------------------------
# Response loading
# ----------------------------------------------------------------------------

def _load_completed_respondent_ids(engagement_id: str) -> list[UUID]:
    """Return UUIDs of respondents who marked themselves complete for this engagement.

    Filters to status='completed' to exclude in-progress/abandoned/removed
    respondents. Tier 1 should return exactly 1; Tier 2/3 returns the
    full completed set.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM respondents
            WHERE engagement_id = %s
              AND status = 'completed'
            ORDER BY completed_at NULLS LAST
            """,
            [engagement_id],
        )
        return [row[0] for row in cursor.fetchall()]


def _load_responses_for_respondent(respondent_id: UUID) -> dict[str, ResponseRecord]:
    """Load all responses for one respondent.

    Returns {question_id: ResponseRecord}. The has_note and has_attachments
    flags are derived from the database columns added by OD-16 / OD-17.
    """
    with connection.cursor() as cursor:
        # LEFT JOIN against response_attachments to avoid N+1
        cursor.execute(
            """
            SELECT
                r.question_id,
                r.answer_value,
                r.is_dont_know,
                (r.respondent_note IS NOT NULL AND length(trim(r.respondent_note)) > 0) AS has_note,
                EXISTS (
                    SELECT 1 FROM response_attachments ra
                    WHERE ra.response_id = r.id
                ) AS has_attachments
            FROM responses r
            WHERE r.respondent_id = %s
            """,
            [str(respondent_id)],
        )
        rows = cursor.fetchall()

    out: dict[str, ResponseRecord] = {}
    for question_id, answer_value, is_dont_know, has_note, has_attachments in rows:
        out[question_id] = ResponseRecord(
            question_id=question_id,
            answer_value=answer_value,
            is_dont_know=bool(is_dont_know),
            has_note=bool(has_note),
            has_attachments=bool(has_attachments),
        )
    return out


# ----------------------------------------------------------------------------
# Single-respondent scoring (Tier 1, and the per-respondent slice for Tier 2/3)
# ----------------------------------------------------------------------------

def _score_for_responses(
    responses_by_qid: dict[str, ResponseRecord],
    option_weight_override_map: dict[str, dict[str, float]] | None = None,
) -> tuple[
    v1_audit.V1FrameworkResult,
    v2_readiness.V2FrameworkResult,
    v3_governance.V3FrameworkResult,
    efficiency.EfficiencyFrameworkResult,
]:
    """Run all four framework scorers against one response set."""
    v1_result = v1_audit.score_v1_audit(
        _QUESTIONS_AS_NS, responses_by_qid,
        option_weight_override_map=option_weight_override_map,
    )
    v2_result = v2_readiness.score_v2_readiness(
        _QUESTIONS_AS_NS, responses_by_qid,
        option_weight_override_map=option_weight_override_map,
    )
    v3_result = v3_governance.score_v3_governance(
        _QUESTIONS_AS_NS, responses_by_qid,
        option_weight_override_map=option_weight_override_map,
    )
    eff_result = efficiency.score_efficiency(
        _QUESTIONS_AS_NS, responses_by_qid,
        option_weight_override_map=option_weight_override_map,
    )
    return v1_result, v2_result, v3_result, eff_result


# ----------------------------------------------------------------------------
# Engagement metadata
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class _EngagementMeta:
    engagement_id: str
    tier: str
    coverage_met_at: Any | None


def _load_engagement_meta(engagement_id: str) -> _EngagementMeta:
    """Pull tier + coverage flag from the engagements table."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, tier, coverage_met_at
            FROM engagements
            WHERE id = %s
            """,
            [engagement_id],
        )
        row = cursor.fetchone()

    if row is None:
        raise ValueError(f"Engagement not found: {engagement_id}")

    eng_id, tier, coverage_met_at = row
    if tier not in ("tier_1", "tier_2", "tier_3"):
        logger.warning("Engagement %s has unknown tier %r", eng_id, tier)
    return _EngagementMeta(
        engagement_id=str(eng_id),
        tier=tier,
        coverage_met_at=coverage_met_at,
    )


# ----------------------------------------------------------------------------
# Tier 2/3 multi-respondent aggregation (HOOK — not yet finalized)
# ----------------------------------------------------------------------------

def _aggregate_multi_respondent(
    per_respondent_results: list[tuple[
        v1_audit.V1FrameworkResult,
        v2_readiness.V2FrameworkResult,
        v3_governance.V3FrameworkResult,
        efficiency.EfficiencyFrameworkResult,
    ]],
) -> tuple[
    v1_audit.V1FrameworkResult,
    v2_readiness.V2FrameworkResult,
    v3_governance.V3FrameworkResult,
    efficiency.EfficiencyFrameworkResult,
]:
    """TODO: aggregate per-respondent results into engagement-level results.

    v0.2 plan: score each respondent independently (above), then average
    framework results across respondents at the dimension/module/step/
    component level. This requires synthesizing new V*FrameworkResult
    instances from the per-respondent ones — combining contributions,
    re-computing weighted means and confidence levels, and producing a
    single "engagement view" Result.

    Not blocking for Tier 1 — score_engagement falls through to single-
    respondent path when respondent_count == 1.
    """
    if len(per_respondent_results) == 1:
        return per_respondent_results[0]

    raise NotImplementedError(
        "Multi-respondent aggregation not yet implemented (Tier 2/3 path). "
        "See scoring.engine._aggregate_multi_respondent docstring for v0.2 plan."
    )


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------

def score_engagement(
    engagement_id: str,
    *,
    option_weight_override_map: dict[str, dict[str, float]] | None = None,
) -> CombinedScoringResult:
    """Score one engagement against all four frameworks.

    Parameters
    ----------
    engagement_id
        UUID of the engagement (as string). Engagement must exist and
        have at least one completed respondent.
    option_weight_override_map
        Optional per-question option-weight maps, forwarded to all four
        framework scorers (which forward to response_scoring). Typically
        loaded from scoring.option_weights.

    Returns
    -------
    CombinedScoringResult with all four framework outputs plus
    engagement metadata.

    Raises
    ------
    ValueError
        If the engagement doesn't exist or has no completed respondents.
    NotImplementedError
        For Tier 2/3 with multiple completed respondents (until v0.2 of
        multi-respondent aggregation lands).
    """
    meta = _load_engagement_meta(engagement_id)
    respondent_ids = _load_completed_respondent_ids(engagement_id)

    if not respondent_ids:
        raise ValueError(
            f"Engagement {engagement_id} has no completed respondents; "
            f"cannot score."
        )

    # Tier 1 expects exactly 1 respondent. Log a warning if anything else.
    if meta.tier == "tier_1" and len(respondent_ids) > 1:
        logger.warning(
            "Tier 1 engagement %s has %d completed respondents; expected 1. "
            "Using first respondent only.",
            engagement_id, len(respondent_ids),
        )
        respondent_ids = respondent_ids[:1]

    # Load responses per respondent
    per_respondent_responses: list[dict[str, ResponseRecord]] = [
        _load_responses_for_respondent(rid)
        for rid in respondent_ids
    ]
    total_responses = sum(len(r) for r in per_respondent_responses)

    # Score each respondent
    per_respondent_results = [
        _score_for_responses(responses, option_weight_override_map)
        for responses in per_respondent_responses
    ]

    # Aggregate (Tier 1: identity; Tier 2/3: TODO)
    v1, v2, v3, eff = _aggregate_multi_respondent(per_respondent_results)

    coverage_complete = (
        meta.coverage_met_at is not None
        if meta.tier in ("tier_2", "tier_3")
        else True  # Tier 1 has no formal coverage requirement
    )

    return CombinedScoringResult(
        engagement_id=meta.engagement_id,
        tier=meta.tier,
        respondent_count=len(respondent_ids),
        response_count=total_responses,
        coverage_complete=coverage_complete,
        v1=v1,
        v2=v2,
        v3=v3,
        eff=eff,
    )


# ----------------------------------------------------------------------------
# Convenience: score and return a flat summary dict (for testing / debug)
# ----------------------------------------------------------------------------

def score_engagement_summary(engagement_id: str) -> dict[str, Any]:
    """Score an engagement and return a flat dict of headline numbers.

    Useful for quick CLI / Django admin / test inspection. Not used by
    report generation, which consumes the full CombinedScoringResult.
    """
    result = score_engagement(engagement_id)
    return {
        "engagement_id": result.engagement_id,
        "tier": result.tier,
        "respondent_count": result.respondent_count,
        "response_count": result.response_count,
        "coverage_complete": result.coverage_complete,
        "v1_composite": round(result.v1.composite_score_0_100, 2),
        "v1_bracket": result.v1.composite_bracket,
        "v1_confidence": result.v1.overall_confidence_level,
        "v2_cri": round(result.v2.cri_score_0_100, 2),
        "v2_maturity": f"L{result.v2.cri_maturity_level} {result.v2.cri_maturity_label}",
        "v2_confidence": result.v2.overall_confidence_level,
        "v3_composite": round(result.v3.composite_score_0_100, 2),
        "v3_maturity": f"L{result.v3.composite_maturity_level} {result.v3.composite_maturity_label}",
        "v3_confidence": result.v3.overall_confidence_level,
        "eff_composite": round(result.eff.composite_score_0_100, 2),
        "eff_bracket": result.eff.composite_bracket,
        "eff_confidence": result.eff.overall_confidence_level,
        "top_gap_v1": (
            result.v1.top_gaps[0].sub_component
            if result.v1.top_gaps else None
        ),
        "top_gap_v2": (
            result.v2.top_gaps[0].name
            if result.v2.top_gaps else None
        ),
        "top_gap_v3": (
            result.v3.top_gaps[0].name
            if result.v3.top_gaps else None
        ),
        "top_gap_eff": (
            result.eff.top_gaps[0].name
            if result.eff.top_gaps else None
        ),
    }
