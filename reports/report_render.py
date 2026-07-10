"""Render the Tier 1 audit report per Report Structure Specification v1.3.

Five sections + Appendix A:
  1 Audit Findings, 2 AI Readiness Scorecard, 3 AI Risk & Governance
  Review(tm), 4 AI Efficiency & Process Optimization, 5 Summary of
  Findings (opinion), Appendix A (all questions + responses).

Data sources: scoring contexts (reports.context.build_snapshot_context),
raw responses (SQL), question bank metadata. Public entry point stays
`render_tier1_snapshot_html` so reports.services is unchanged.
"""

from __future__ import annotations

import logging

from django.db import connection
from django.template.loader import render_to_string

from questionnaire.question_bank import QUESTIONS
from reports.context import build_snapshot_context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Artifact -> question-id curation (Spec v1.3 Phase 1)
# ---------------------------------------------------------------------------

SECTION_1_ARTIFACTS = [
    ("AI Tool Inventory",
     "What the company knows about the AI tools in active use.",
     ["T1-B-001", "T1-B-002", "T1-B-003", "T1-B-004", "T1-B-005",
      "T1-B-007", "T1-B-009", "T1-B-010", "T1-B-011", "T1-B-021",
      "T1-B-022", "T1-B-023", "T1-B-024"]),
    ("Fully Loaded Cost Map",
     "Subscription spend plus the hidden costs of review, rework, and "
     "vendor lock-in.",
     ["T1-C-002", "T1-C-003", "T1-C-004", "T1-C-006", "T1-C-007",
      "T1-C-010", "T1-C-011", "T1-C-012", "T1-C-013", "T1-C-014",
      "T1-C-015", "T1-C-016"]),
    ("Shadow AI Surface Report",
     "AI in use outside sanctioned channels: personal accounts, "
     "department-level adoption, vendor-embedded features, and "
     "unrecognized charges.",
     ["T1-B-011", "T1-B-013", "T1-B-014", "T1-B-015", "T1-B-016",
      "T1-B-019", "T1-C-005"]),
]

SECTION_1E_OPERATIONAL_QIDS = ["T1-G-002", "T1-G-005", "T1-D-016", "T1-C-015"]
SECTION_1E_PERFORMATIVE_QIDS = ["T1-A-009", "T1-F-001", "T1-F-006", "T1-D-007"]

POLICY_FIELDS = [
    ("Named owner", "T1-B-004"),
    ("Published AI usage policy", "T1-F-001"),
    ("Defined budget (AI as distinct budget line)", "T1-C-006"),
    ("Documented controls (approval before adoption)", "T1-B-024"),
    ("Recurring review cadence", "T1-F-021"),
    ("Exit criteria (tools retired on missed targets)", "T1-B-023"),
]

CONDITION_NARRATIVES = [
    ("Condition 01 — Workflows ready",
     "What workflows is AI supporting, and are they ready?",
     ["T1-G-005", "T1-G-007", "T1-G-008"]),
    ("Condition 02 — Data reliable",
     "What data is AI relying on, and is it reliable?",
     ["T1-E-004", "T1-E-006", "T1-E-007", "T1-E-008"]),
    ("Condition 03 — Output owned",
     "Who owns the output and what review standard does it meet?",
     ["T1-D-005", "T1-D-010", "T1-D-011"]),
    ("Condition 04 — Measurable result",
     "What is AI producing in measurable business terms?",
     ["T1-G-002", "T1-C-015", "T1-D-016", "T1-D-008"]),
]

SECTION_3_ARTIFACTS = [
    ("AI Data Exposure Model",
     "Where sensitive information meets external AI systems.",
     ["T1-E-001", "T1-E-002", "T1-E-004", "T1-E-006", "T1-E-007",
      "T1-E-008"]),
    ("Decision Influence Matrix",
     "Where AI influences or makes consequential decisions.",
     ["T1-E-009", "T1-F-031", "T1-E-025", "T1-D-019"]),
    ("AI Vendor Risk Inventory",
     "Vendor terms, incidents, compliance evidence, and switching "
     "exposure.",
     ["T1-E-003", "T1-E-017", "T1-E-018", "T1-E-019", "T1-E-020",
      "T1-E-021", "T1-E-029", "T1-E-031", "T1-E-032", "T1-C-012",
      "T1-C-013", "T1-C-014"]),
    ("AI Governance Framework Crosswalk",
     "Obligations and voluntary standards mapped against assessed "
     "posture.",
     ["T1-A-006", "T1-A-011", "T1-A-012", "T1-F-013", "T1-F-014",
      "T1-F-015", "T1-F-016", "T1-E-024"]),
    ("Per-Use-Case Governance Dossier",
     "Whether governance exists at the level of individual AI use "
     "cases.",
     ["T1-F-019", "T1-F-020", "T1-F-022"]),
]

SECTION_4_ARTIFACTS = [
    ("Workflow Reality Map",
     "How AI actually behaves inside day-to-day work.",
     ["T1-G-005", "T1-G-006", "T1-G-007", "T1-G-008"]),
    ("The AI Efficiency Tax(tm)",
     "Time and money consumed correcting, verifying, and reformatting "
     "AI output.",
     ["T1-C-007", "T1-C-010", "T1-C-011", "T1-D-009"]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _question_index() -> dict:
    return {q["id"]: q for q in QUESTIONS}


def _load_responses(cursor, engagement_id: str) -> dict:
    cursor.execute(
        """
        SELECT r.question_id, r.answer_value, r.is_dont_know
        FROM responses r
        JOIN respondents rs ON r.respondent_id = rs.id
        WHERE rs.engagement_id = %s
        """,
        [engagement_id],
    )
    return {row[0]: {"value": row[1], "dont_know": bool(row[2])}
            for row in cursor.fetchall()}


def _format_answer(resp) -> str:
    if resp is None:
        return "Not answered"
    value = resp["value"]
    if isinstance(value, dict):
        if value.get("_placeholder"):
            return "Not captured (response pending re-answer)"
        if "selected" in value:
            sel = value["selected"]
            if isinstance(sel, list):
                return "; ".join(str(s) for s in sel)
            return str(sel)
        if "ranked" in value:
            ranked = value.get("ranked") or []
            if not ranked:
                return "Not captured (response pending re-answer)"
            return " > ".join(str(r) for r in ranked)
        if "rows" in value:
            parts = []
            for key, row in sorted(value["rows"].items()):
                if isinstance(row, dict):
                    name = row.get("name") or f"Row {key}"
                    cells = row.get("cells") or {}
                    yes = sum(1 for v in cells.values()
                              if str(v).lower() in ("selected", "yes"))
                    parts.append(f"{name}: {yes}/{len(cells)} attributes")
                else:
                    parts.append(f"Row {key}: {row}")
            return "; ".join(parts) if parts else "Matrix response recorded"
    suffix = " (answered: Don't know)" if resp["dont_know"] else ""
    return f"{value}{suffix}" if not isinstance(value, dict) else "Recorded"


def _qa_block(qindex, responses, qids):
    out = []
    for qid in qids:
        q = qindex.get(qid)
        if q is None:
            continue
        resp = responses.get(qid)
        answer = _format_answer(resp)
        if resp and resp["dont_know"]:
            answer = f"{answer} — respondent answered Don't know"
        out.append({
            "qid": qid,
            "question": q["question_text"],
            "answer": answer,
            "answered": resp is not None,
        })
    return out


def _artifact(qindex, responses, title, intro, qids, note=None):
    return {
        "title": title,
        "intro": intro,
        "qa": _qa_block(qindex, responses, qids),
        "note": note,
    }


def _fuzzy_module_score(items, *keywords):
    for item in items:
        name = item.get("name", "").lower()
        if any(k in name for k in keywords):
            return item
    return None


# ---------------------------------------------------------------------------
# Opinion rule (Phase 1 placeholder — operator-tunable)
# ---------------------------------------------------------------------------

OPINION_SCORE_FLOOR = 60.0
OPINION_DK_CEILING = 0.25


def _build_opinion(frameworks):
    drivers = []
    scored = [f for f in frameworks if not f.get("error")]
    if not scored:
        return {
            "kind": "qualified",
            "drivers": ["No framework could be scored for this engagement."],
        }
    for f in scored:
        o = f["overall"]
        name = f["framework"]["display_name"]
        if (o.get("score_0_100") or 0) < OPINION_SCORE_FLOOR:
            drivers.append(
                f"{name} scored {o['score_0_100']} — below the "
                f"{OPINION_SCORE_FLOOR:.0f} threshold."
            )
        if (o.get("dk_ratio") or 0) > OPINION_DK_CEILING:
            drivers.append(
                f"{name} \"don't know\" ratio {o['dk_ratio']} exceeds "
                f"{OPINION_DK_CEILING} — material uncertainty."
            )
        if str(o.get("confidence_level", "")).lower() == "low":
            drivers.append(f"{name} confidence level is low.")
    kind = "unqualified" if not drivers else "qualified"
    return {"kind": kind, "drivers": drivers}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_tier1_snapshot_html(engagement_id: str) -> str:
    qindex = _question_index()

    with connection.cursor() as cursor:
        responses = _load_responses(cursor, engagement_id)

    frameworks = []
    for key in ("v1_audit", "v2_readiness", "v3_governance", "efficiency"):
        try:
            ctx = build_snapshot_context(engagement_id, key)
            ctx["error"] = None
            frameworks.append(ctx)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scoring failed for framework %s", key)
            frameworks.append({"error": str(exc), "framework": {"key": key}})

    by_key = {f["framework"]["key"]: f for f in frameworks
              if not f.get("error")}
    v2 = by_key.get("v2_readiness")
    v3 = by_key.get("v3_governance")
    eff = by_key.get("efficiency")
    first = next(iter(by_key.values()), None)

    # --- Section 1 ---
    section1 = [
        _artifact(qindex, responses, title, intro, qids)
        for title, intro, qids in SECTION_1_ARTIFACTS
    ]
    gap_analysis = {
        "title": "Governance Gap Analysis",
        "intro": "Highest-priority governance gaps identified by the "
                 "AI Risk & Governance Review(tm) scoring.",
        "gaps": (v3["priority_gaps"] if v3 else []),
        "note": None if v3 else "Governance scoring unavailable for this "
                                "engagement.",
    }
    perf_vs_op = {
        "operational_score": (eff["overall"]["score_0_100"] if eff else None),
        "performative_score": (v3["overall"]["score_0_100"] if v3 else None),
        "operational_qa": _qa_block(qindex, responses,
                                    SECTION_1E_OPERATIONAL_QIDS),
        "performative_qa": _qa_block(qindex, responses,
                                     SECTION_1E_PERFORMATIVE_QIDS),
    }
    policy_fields = []
    for label, qid in POLICY_FIELDS:
        resp = responses.get(qid)
        policy_fields.append({
            "label": label,
            "value": _format_answer(resp),
        })

    # --- Section 2 ---
    v2_items = v2["items"] if v2 else []
    conditions = [
        {"n": 1, "name": "Workflow Readiness Review",
         "item": _fuzzy_module_score(v2_items, "workflow")},
        {"n": 2, "name": "Data Reliability Checklist",
         "item": _fuzzy_module_score(v2_items, "data")},
        {"n": 3, "name": "AI Adoption Pattern Map",
         "item": _fuzzy_module_score(v2_items, "adoption", "pattern")},
        {"n": 4, "name": "AI Governance Matrix",
         "item": _fuzzy_module_score(v2_items, "governance")},
        {"n": 5, "name": "Net Efficiency Yield Ratio",
         "item": None,
         "metric_note": "NEYR = Net Completed Output Value / Total Labor "
                        "Hours Across Generation. Tier 1 does not collect "
                        "output value and labor hours directly - "
                        "directional signals below; measured in Tier 2."},
        {"n": 6, "name": "Operational Leakage Factor(tm)",
         "item": None,
         "metric_note": "OLF(tm) = Total Weekly Untracked Manual "
                        "Correction, Verification, Reformatting, and "
                        "Bypass Hours / Total Weekly AI-Supported Workflow "
                        "Volume. Tier 1 directional estimate from the "
                        "weekly review-and-fix time reported below; "
                        "measured in Tier 2."},
    ]
    neyr_olf_signals = _qa_block(qindex, responses,
                                 ["T1-C-010", "T1-C-011", "T1-G-009"])
    condition_narratives = [
        {"title": t, "question": qtext,
         "qa": _qa_block(qindex, responses, qids)}
        for t, qtext, qids in CONDITION_NARRATIVES
    ]

    # --- Section 3 ---
    section3 = [
        _artifact(qindex, responses, title, intro, qids)
        for title, intro, qids in SECTION_3_ARTIFACTS
    ]
    maturity = {
        "overall": (v3["overall"] if v3 else None),
        "items": (v3["items"] if v3 else []),
        "cross_cutting": (v3.get("cross_cutting_signals", []) if v3 else []),
    }

    # --- Section 4 ---
    section4 = [