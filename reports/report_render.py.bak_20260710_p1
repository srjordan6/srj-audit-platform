"""Render Tier 1 snapshot report HTML from scoring contexts.

Builds one combined HTML document covering all four frameworks
(V1 audit, V2 readiness, V3 governance, Efficiency). Each framework
context is built independently; a scoring failure in one framework
renders an error card instead of killing the whole report.
"""

from __future__ import annotations

import logging

from django.template.loader import render_to_string

from reports.context import build_snapshot_context, FRAMEWORK_DISPLAY_NAMES

logger = logging.getLogger(__name__)

FRAMEWORK_ORDER = ["v1_audit", "v2_readiness", "v3_governance", "efficiency"]


def render_tier1_snapshot_html(engagement_id: str) -> str:
    """Return the report content HTML fragment for the given engagement."""
    frameworks = []
    company = None
    engagement = None
    methodology = ""
    trademark_notice = ""
    disclaimer = ""
    generated_at = ""

    for key in FRAMEWORK_ORDER:
        try:
            ctx = build_snapshot_context(engagement_id, key)
            ctx["error"] = None
            frameworks.append(ctx)
            company = company or ctx["company"]
            engagement = engagement or ctx["engagement"]
            methodology = methodology or ctx["methodology"]
            trademark_notice = trademark_notice or ctx["trademark_notice"]
            disclaimer = disclaimer or ctx["disclaimer"]
            generated_at = generated_at or ctx["generated_at"]
        except Exception as exc:  # noqa: BLE001 — render error card, keep going
            logger.exception("scoring failed for framework %s", key)
            frameworks.append({
                "error": str(exc),
                "framework": {
                    "key": key,
                    "display_name": FRAMEWORK_DISPLAY_NAMES.get(key, key),
                    "subtitle": "Snapshot Report",
                },
            })

    return render_to_string("reports/tier1_snapshot.html", {
        "company": company,
        "engagement": engagement,
        "frameworks": frameworks,
        "methodology": methodology,
        "trademark_notice": trademark_notice,
        "disclaimer": disclaimer,
        "generated_at": generated_at,
    })