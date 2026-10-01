"""Combined Board Analysis (OD-19, 2026-10-01).

The third document a Tier 2 buyer of both audits receives: the two audits
read together for the board, one roadmap, the decisions only the board can
take, and the engagement's one opinion. The two separate reports keep
their findings and appendices; this document never repeats them.
"""

from __future__ import annotations

import logging
from datetime import date

from django.db import connection
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def is_board_engagement(cursor, engagement_id: str) -> bool:
    cursor.execute("SELECT coalesce(tier, 'tier_1'), coalesce(instrument, 'tier_1') FROM engagements WHERE id = %s",
                   [str(engagement_id)])
    row = cursor.fetchone()
    return bool(row) and row[0] == "tier_2" and row[1] == "combined"


def build_board_context(engagement_id: str) -> dict:
    from reports.report_render import build_tier1_context
    from reports.aiitsa_render import build_aiitsa_context, _with_analysis
    from reports.board_analysis import analyze_board, build_opinion

    gov = build_tier1_context(engagement_id)
    sec = _with_analysis(engagement_id, build_aiitsa_context(engagement_id))

    frameworks = [f for f in gov["frameworks"] if not f.get("error")]
    gaps = []
    for f in frameworks:
        for g in (f.get("priority_gaps") or f.get("gaps") or [])[:3]:
            gaps.append({"framework": f["framework"]["display_name"], **(g if isinstance(g, dict) else {"text": str(g)})})
    ctx = {
        "company": gov.get("company") or sec["company"],
        "generated_at": gov.get("generated_at") or "",
        "assessed_on": sec["assessed_on"],
        "gov": {
            "frameworks": frameworks,
            "priority_gaps": gaps,
            "ninety_day": gov.get("ninety_day") or [],
            "divergence": gov.get("divergence"),
            "respondent_count": gov.get("respondent_count") or 0,
            "opinion": gov.get("opinion") or {},
        },
        "sec": {
            "baseline": sec["baseline"], "areas": sec["areas"], "weakest": sec["weakest"],
            "visibility": sec["visibility"], "roadmap": sec["roadmap"],
            "divergence": sec.get("divergence"), "respondent_count": sec["respondent_count"],
            "opinion": sec.get("opinion") or {},
        },
    }
    try:
        ctx["ai"] = analyze_board(engagement_id, ctx)
    except Exception:  # noqa: BLE001
        logger.exception("board analysis failed; rendering without narratives")
        ctx["ai"] = {}
    ctx["opinion"] = build_opinion(ctx, (ctx["ai"] or {}).get("opinion_basis"))
    return ctx


def render_board_html(engagement_id: str) -> str:
    return render_to_string("reports/board_analysis.html", build_board_context(engagement_id))
