"""
reports.context — Build template context dicts for snapshot reports.

Bridges the scoring engine (scoring/engine.py) and the gap-action layer
(scoring/gap_actions.py) into a unified per-framework dictionary that
report templates render against. The function `build_snapshot_context`
is the single public entry point: pass an engagement_id and a framework
key, get back a dict ready for Jinja2/WeasyPrint.

DESIGN
------
Each framework's result type has a slightly different shape:

    V1: dimensions[].final_score_0_100, bracket-only, gap is (dimension, sub_component)
    V2: modules[].score_0_100 + maturity_level/label, gap is single name
    V3: steps[].score_0_100 + maturity_level/label, cross_cutting_signals[]
    Eff: components[].score_0_100 + bracket-only, top_gaps may be 1 or 2

This module normalizes those differences into one output shape:

    {
        "company":              {name, size_bracket, industry, geographic_scope},
        "engagement":           {tier, respondent_count, ...},
        "framework":            {key, display_name, subtitle},
        "overall":              {score_0_100, bracket, maturity_level, ...},
        "items":                [{name, display_name, score_0_100, ...}, ...],
        "cross_cutting_signals": [...]  (V3 only, empty list for others)
        "priority_gaps":        [{statement, impact, action, addresses_via, ...}],
        "methodology":          str,
        "trademark_notice":     str,
        "disclaimer":           str,
        "generated_at":         ISO timestamp,
    }

DEPENDENCIES
------------
- scoring.engine.score_engagement(engagement_id)
- scoring.gap_actions.resolve_gap_action(framework, identifier, ...)
- Django database connection for company/engagement metadata

NO WEASYPRINT, NO HTML, NO JINJA HERE. This is pure data assembly. PDF
generation and template rendering live downstream in reports.generators.

TRADEMARK CONSTRAINTS
---------------------
The methodology and trademark_notice strings reference only trademarks
in the operator's permitted set (per userPreferences). The framework
display names are similarly restricted to:
    The AI Business Enablement Audit™
    The AI Readiness & Performance Assessment™
    AI Risk & Governance Review™
    The AI Efficiency & Process Optimization™
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from django.db import connection

from scoring.engine import score_engagement
from scoring.gap_actions import GapAction, resolve_gap_action


# ---------------------------------------------------------------------------
# Framework display configuration
# ---------------------------------------------------------------------------

FRAMEWORK_DISPLAY_NAMES: dict[str, str] = {
    "v1_audit":     "The AI Business Enablement Audit™",
    "v2_readiness": "The AI Readiness & Performance Assessment™",
    "v3_governance": "AI Risk & Governance Review™",
    "efficiency":   "The AI Efficiency & Process Optimization™",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_snapshot_context(engagement_id: str, framework: str) -> dict[str, Any]:
    """Build a complete template context dict for one engagement, one framework.

    Raises
    ------
    ValueError
        If `framework` is not one of the four canonical framework keys, or
        if the engagement does not exist.

    Other exceptions
        Propagated from score_engagement (e.g. engagement with zero
        completed respondents). The caller decides how to surface those.
    """
    if framework not in FRAMEWORK_DISPLAY_NAMES:
        raise ValueError(
            f"Unknown framework {framework!r}; expected one of "
            f"{sorted(FRAMEWORK_DISPLAY_NAMES)}"
        )

    # Score the engagement (returns CombinedScoringResult with v1/v2/v3/eff)
    result = score_engagement(engagement_id)

    company_data = _fetch_company_data(engagement_id)
    engagement_meta = _fetch_engagement_metadata(engagement_id)

    if framework == "v1_audit":
        payload = _build_v1_payload(result.v1)
    elif framework == "v2_readiness":
        payload = _build_v2_payload(result.v2)
    elif framework == "v3_governance":
        payload = _build_v3_payload(result.v3)
    else:  # efficiency
        payload = _build_efficiency_payload(result.eff)

    return {
        "company": company_data,
        "engagement": {
            "tier": result.tier,
            "respondent_count": result.respondent_count,
            "response_count": result.response_count,
            "coverage_complete": result.coverage_complete,
            "completed_at": engagement_meta.get("completed_at"),
            "created_at": engagement_meta.get("created_at"),
        },
        "framework": {
            "key": framework,
            "display_name": FRAMEWORK_DISPLAY_NAMES[framework],
            "subtitle": "Snapshot Report",
        },
        "overall": payload["overall"],
        "items": payload["items"],
        "cross_cutting_signals": payload.get("cross_cutting_signals", []),
        "priority_gaps": payload["priority_gaps"],
        "methodology": _build_methodology(result.tier),
        "trademark_notice": _build_trademark_notice(),
        "disclaimer": _build_disclaimer(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# DB lookups
# ---------------------------------------------------------------------------

def _fetch_company_data(engagement_id: str) -> dict[str, Any]:
    """Pull company info via raw SQL (matches the engine.py pattern)."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.name, c.size_bracket, c.industry, c.geographic_scope
            FROM engagements e
            JOIN companies c ON c.id = e.company_id
            WHERE e.id = %s
            """,
            [engagement_id],
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Engagement {engagement_id} not found")
        return {
            "name": row[0],
            "size_bracket": row[1],
            "industry": row[2],
            "geographic_scope": row[3],
        }


def _fetch_engagement_metadata(engagement_id: str) -> dict[str, Any]:
    """Pull engagement timestamps. The respondent_count comes from the
    CombinedScoringResult; this just supplies created_at/completed_at."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT created_at, completed_at
            FROM engagements
            WHERE id = %s
            """,
            [engagement_id],
        )
        row = cursor.fetchone()
        if row is None:
            return {}
        return {"created_at": row[0], "completed_at": row[1]}


# ---------------------------------------------------------------------------
# Per-framework payload builders
# ---------------------------------------------------------------------------

def _humanize(name: str) -> str:
    """Convert snake_case to Title Case for display."""
    return name.replace("_", " ").title()


def _build_v1_payload(v1_result: Any) -> dict[str, Any]:
    """V1FrameworkResult -> snapshot payload.

    V1 uses dimensions[] with `final_score_0_100` (post-inversion).
    Gap items reference dimension + sub_component.
    No maturity scale -- bracket only.
    """
    overall = {
        "score_0_100": round(v1_result.composite_score_0_100, 1),
        "bracket": v1_result.composite_bracket,
        "confidence_level": v1_result.overall_confidence_level,
        "dk_ratio": round(v1_result.overall_dk_ratio, 3),
        "maturity_level": None,
        "maturity_label": None,
    }
    items = [
        {
            "name": d.name,
            "display_name": _humanize(d.name),
            "score_0_100": round(d.final_score_0_100, 1),
            "bracket": d.bracket,
            "confidence_level": d.confidence_level,
            "inverted": d.inverted,
            "answered": d.answered_count,
            "expected": d.expected_count,
        }
        for d in v1_result.dimensions
    ]
    priority_gaps = []
    for gap in v1_result.top_gaps[:3]:
        action = resolve_gap_action(
            "v1_audit", gap.dimension, sub_component=gap.sub_component
        )
        fallback = f"{_humanize(gap.dimension)} — {_humanize(gap.sub_component)}"
        priority_gaps.append(
            _gap_dict(
                action,
                gap_score_0_100=gap.weighted_mean_0_1 * 100.0,
                fallback_label=fallback,
            )
        )
    return {"overall": overall, "items": items, "priority_gaps": priority_gaps}


def _build_v2_payload(v2_result: Any) -> dict[str, Any]:
    """V2FrameworkResult -> snapshot payload.

    V2 uses modules[] with score_0_100 + maturity_level + maturity_label.
    Gap items reference just `name`.
    """
    overall = {
        "score_0_100": round(v2_result.cri_score_0_100, 1),
        "bracket": v2_result.cri_bracket,
        "confidence_level": v2_result.overall_confidence_level,
        "dk_ratio": round(v2_result.overall_dk_ratio, 3),
        "maturity_level": v2_result.cri_maturity_level,
        "maturity_label": v2_result.cri_maturity_label,
    }
    items = [
        {
            "name": m.name,
            "display_name": _humanize(m.name),
            "score_0_100": round(m.score_0_100, 1),
            "bracket": m.bracket,
            "maturity_level": m.maturity_level,
            "maturity_label": m.maturity_label,
            "confidence_level": m.confidence_level,
            "answered": m.answered_count,
            "expected": m.expected_count,
        }
        for m in v2_result.modules
    ]
    priority_gaps = []
    for gap in v2_result.top_gaps[:3]:
        action = resolve_gap_action("v2_readiness", gap.name)
        priority_gaps.append(
            _gap_dict(
                action,
                gap_score_0_100=gap.score_0_100,
                fallback_label=_humanize(gap.name),
            )
        )
    return {"overall": overall, "items": items, "priority_gaps": priority_gaps}


def _build_v3_payload(v3_result: Any) -> dict[str, Any]:
    """V3FrameworkResult -> snapshot payload.

    V3 uses steps[] with score_0_100 + maturity. Also exposes
    cross_cutting_signals[] as a parallel list.
    """
    overall = {
        "score_0_100": round(v3_result.composite_score_0_100, 1),
        "bracket": None,  # V3 uses maturity labels rather than brackets
        "confidence_level": v3_result.overall_confidence_level,
        "dk_ratio": round(v3_result.overall_dk_ratio, 3),
        "maturity_level": v3_result.composite_maturity_level,
        "maturity_label": v3_result.composite_maturity_label,
    }
    items = [
        {
            "name": s.name,
            "display_name": _humanize(s.name),
            "score_0_100": round(s.score_0_100, 1),
            "maturity_level": s.maturity_level,
            "maturity_label": s.maturity_label,
            "confidence_level": s.confidence_level,
            "answered": s.answered_count,
            "expected": s.expected_count,
        }
        for s in v3_result.steps
    ]
    cross_cutting = [
        {
            "name": c.name,
            "display_name": _humanize(c.name),
            "score_0_100": round(c.score_0_100, 1),
            "confidence_level": c.confidence_level,
            "answered": c.answered_count,
            "expected": c.expected_count,
        }
        for c in v3_result.cross_cutting_signals
    ]
    priority_gaps = []
    for gap in v3_result.top_gaps[:3]:
        action = resolve_gap_action("v3_governance", gap.name)
        priority_gaps.append(
            _gap_dict(
                action,
                gap_score_0_100=gap.score_0_100,
                fallback_label=_humanize(gap.name),
            )
        )
    return {
        "overall": overall,
        "items": items,
        "cross_cutting_signals": cross_cutting,
        "priority_gaps": priority_gaps,
    }


def _build_efficiency_payload(eff_result: Any) -> dict[str, Any]:
    """EfficiencyFrameworkResult -> snapshot payload.

    Efficiency uses components[] (outcome_alignment, process_optimization)
    with score_0_100 + bracket. top_gaps may contain 1 or 2 items.
    """
    overall = {
        "score_0_100": round(eff_result.composite_score_0_100, 1),
        "bracket": eff_result.composite_bracket,
        "confidence_level": eff_result.overall_confidence_level,
        "dk_ratio": round(eff_result.overall_dk_ratio, 3),
        "maturity_level": None,
        "maturity_label": None,
    }
    items = [
        {
            "name": c.name,
            "display_name": _humanize(c.name),
            "score_0_100": round(c.score_0_100, 1),
            "bracket": c.bracket,
            "confidence_level": c.confidence_level,
            "answered": c.answered_count,
            "expected": c.expected_count,
        }
        for c in eff_result.components
    ]
    priority_gaps = []
    # top_gaps may have only 1 or 2 entries for efficiency
    for gap in eff_result.top_gaps[:3]:
        action = resolve_gap_action("efficiency", gap.name)
        priority_gaps.append(
            _gap_dict(
                action,
                gap_score_0_100=gap.score_0_100,
                fallback_label=_humanize(gap.name),
            )
        )
    return {"overall": overall, "items": items, "priority_gaps": priority_gaps}


# ---------------------------------------------------------------------------
# Gap dict normalization
# ---------------------------------------------------------------------------

def _gap_dict(
    action: GapAction | None,
    *,
    gap_score_0_100: float,
    fallback_label: str,
) -> dict[str, Any]:
    """Produce a uniformly-shaped gap dict for the template.

    When gap_actions.resolve_gap_action() returns None (no canonical
    mapping for this gap key yet), emit a graceful fallback that the
    template can still render. The `mapped: False` flag lets the
    template render unmapped gaps with a distinct style if desired.
    """
    if action is None:
        return {
            "statement": f"Low score in {fallback_label}",
            "impact": (
                "Further investigation recommended; no canonical gap "
                "mapping exists for this area yet."
            ),
            "action": (
                "Review the underlying questions and consider this area "
                "for the next governance cycle."
            ),
            "addresses_via": "Operational Health Check™",
            "score_0_100": round(gap_score_0_100, 1),
            "mapped": False,
        }
    return {
        "statement": action.statement,
        "impact": action.impact,
        "action": action.action,
        "addresses_via": action.addresses_via,
        "score_0_100": round(gap_score_0_100, 1),
        "mapped": True,
    }


# ---------------------------------------------------------------------------
# Copy blocks
# ---------------------------------------------------------------------------

def _build_methodology(tier: str) -> str:
    if tier == "tier_1":
        return (
            "Indicative findings based on self-reported survey data from a "
            "single respondent. Full board-grade audit requires a multi-"
            "respondent Tier 2 or Tier 3 engagement, per the methodology "
            "documented in The Operating Discipline for AI Library™."
        )
    return (
        "Findings based on multi-respondent self-reported survey data with "
        "supporting documentation, per The Operating Discipline for AI "
        "Library™ methodology."
    )


def _build_trademark_notice() -> str:
    """All marks here are in the operator's permitted set."""
    return (
        "The AI Business Enablement Audit™, The AI Readiness & Performance "
        "Assessment™, AI Risk & Governance Review™, The AI Efficiency & "
        "Process Optimization™, The Operating Discipline for AI Library™, "
        "The AI Operating System™, AI Business Services™, AI Risk Governance "
        "& Security™, AI Decision Accountability Framework™, AI Operational "
        "Risk Assessment™, AI Operational Risk Categories™, AI ROI Evaluation "
        "Framework™, AI Performance Scorecard™, AI Performance Governance™, "
        "AI Integration Checklist™, AI Adoption Decision Framework™, "
        "Operational Health Check™, Operational Integration & Workflow "
        "Adoption™, Outcome Alignment Map™, and Standing AI Adoption Policy™ "
        "are trademarks of SRJ Consulting & Services LLC."
    )


def _build_disclaimer() -> str:
    return (
        "This report is provided for informational purposes only. It is not "
        "legal advice, financial advice, or a substitute for engagement with "
        "qualified counsel or auditors. SRJ Consulting & Services LLC makes "
        "no representations regarding the suitability of these findings for "
        "any specific business decision or regulatory filing."
    )
