"""Tool-inventory discrepancy signals for the Tier 1 audit report.

Compares the respondent's explicit tool inventory (T1-A-000, now
rendered as first question of Section B) against downstream
"how-many" self-reports:

    T1-B-009 — How many AI tools does leadership believe are in use?
    T1-B-011 — How many AI tools do you personally use for work tasks?

If the numbers disagree materially, the auditor's opinion notes it as
a Basis exception ("Leadership head-count of N conflicts with an
inventoried M tools"). Feeds the AI narrative context so the report
surfaces the gap rather than silently accepting either figure.

Public entry point: compute_signals(cursor, respondent_id) -> dict.

Shape of the returned dict:

    {
        "inventory_count":   <int>,   # from T1-A-000 selected + parsed "other"
        "leadership_count":  <int|None>,
        "personal_count":    <int|None>,
        "delta_vs_leadership": <int|None>,  # inventory - leadership
        "delta_vs_personal":   <int|None>,
        "flags": [
            "leadership_underestimate",         # leadership < inventory
            "leadership_overestimate",          # leadership > inventory
            "personal_use_exceeds_inventory",   # personal > inventory
            "material_discrepancy",             # any |delta| >= 3
        ],
        "narrative": "One-line summary suitable for the report.",
    }

Callers (report_render, ai_analysis) can consume flags to influence
opinion basis and narrative context.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


MATERIAL_DELTA_THRESHOLD = 3  # tools


def _parse_int(value: Any) -> Optional[int]:
    """Try to pull an int out of an answer_value dict / range string."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            # Bare string — maybe a numeric range like "10-20" or "50+".
            m = re.search(r"\d+", value)
            return int(m.group(0)) if m else None
    if isinstance(value, dict):
        selected = value.get("selected")
        if isinstance(selected, list):
            return len(selected)
        if isinstance(selected, str):
            m = re.search(r"\d+", selected)
            return int(m.group(0)) if m else None
    return None


def _inventory_count(av: Any) -> int:
    """Count selected tools + comma-split "other" free-text entries."""
    if not isinstance(av, dict):
        try:
            av = json.loads(av) if isinstance(av, str) else {}
        except (ValueError, TypeError):
            av = {}
    selected = av.get("selected") or []
    if isinstance(selected, str):
        selected = [selected]
    n = len(selected)
    other = (av.get("other") or "").strip()
    if other:
        n += sum(1 for chunk in other.split(",") if chunk.strip())
    return n


def compute_signals(cursor, respondent_id: str) -> dict:
    """Return the tool-count discrepancy signal for a respondent.

    Reads directly from public.responses so it's safe to call from
    report generation, from a management command, or from a diagnostic
    tool. Uses same key ('T1-A-000') the flow uses for the inventory
    question even though it's now rendered in Section B.
    """
    cursor.execute(
        "SELECT question_id, answer_value FROM responses "
        "WHERE respondent_id = %s AND question_id IN "
        "('T1-A-000', 'T1-B-009', 'T1-B-011')",
        (respondent_id,),
    )
    by_qid: dict[str, Any] = {}
    for qid, val in cursor.fetchall():
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (ValueError, TypeError):
                pass
        by_qid[qid] = val

    inv_count = _inventory_count(by_qid.get("T1-A-000")) if "T1-A-000" in by_qid else 0
    leader_count = _parse_int(by_qid.get("T1-B-009"))
    personal_count = _parse_int(by_qid.get("T1-B-011"))

    delta_leader = (inv_count - leader_count) if leader_count is not None else None
    delta_personal = (inv_count - personal_count) if personal_count is not None else None

    flags: list[str] = []
    if leader_count is not None:
        if leader_count < inv_count:
            flags.append("leadership_underestimate")
        elif leader_count > inv_count:
            flags.append("leadership_overestimate")
    if personal_count is not None and personal_count > inv_count:
        flags.append("personal_use_exceeds_inventory")
    if any(abs(d) >= MATERIAL_DELTA_THRESHOLD for d in (delta_leader, delta_personal) if d is not None):
        flags.append("material_discrepancy")

    narrative_bits: list[str] = []
    narrative_bits.append(
        f"Inventory captured {inv_count} tool"
        + ("" if inv_count == 1 else "s")
        + "."
    )
    if leader_count is not None:
        narrative_bits.append(
            f"Leadership head-count self-report: {leader_count}"
            + (f" ({'undercount' if delta_leader > 0 else 'overcount'} of {abs(delta_leader)})" if delta_leader else " (matches)")
        )
    if personal_count is not None and personal_count != inv_count:
        narrative_bits.append(
            f"Personal-use self-report: {personal_count}"
        )
    narrative = " ".join(narrative_bits)

    return {
        "inventory_count": inv_count,
        "leadership_count": leader_count,
        "personal_count": personal_count,
        "delta_vs_leadership": delta_leader,
        "delta_vs_personal": delta_personal,
        "flags": flags,
        "narrative": narrative,
    }
