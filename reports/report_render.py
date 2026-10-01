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

from core.dbjson import loads_maybe
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
    ("Condition 01 - Workflows ready",
     "What workflows is AI supporting, and are they ready?",
     ["T1-G-005", "T1-G-007", "T1-G-008"]),
    ("Condition 02 - Data reliable",
     "What data is AI relying on, and is it reliable?",
     ["T1-E-004", "T1-E-006", "T1-E-007", "T1-E-008"]),
    ("Condition 03 - Output owned",
     "Who owns the output and what review standard does it meet?",
     ["T1-D-005", "T1-D-010", "T1-D-011"]),
    ("Condition 04 - Measurable result",
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


# Which respondent's answer stands for "the company's answer" on the
# factual Section 1 fields (policy exists, inventory exists...) when several
# respondents answered. Leadership first: those are statements about what the
# organisation has, and the people accountable for it are the source of
# record. Divergence is surfaced separately (Part B-3 S.2.2), not hidden here.
_ROLE_PRECEDENCE = ["CEO", "BOARD", "CFO", "CIO", "CISO", "COO", "VP", "DIR", "HR", "MGR", "IC"]
_ROLE_LABELS = {"BOARD": "Board", "CEO": "CEO", "CFO": "CFO", "CIO": "CIO", "CISO": "CISO",
                "COO": "COO", "VP": "VP", "DIR": "Director", "MGR": "Manager",
                "IC": "Individual contributor", "HR": "HR"}


def _load_responses(cursor, engagement_id: str) -> tuple[dict, dict, int]:
    """Returns (primary, by_question, respondent_count).

    primary      {qid: resp}            one answer per question, leadership-first
    by_question  {qid: [(role, resp)]}  every completed respondent's answer,
                                        for the Appendix A rendering
    Answers are keyed by role, never by name: Part B-1 S.1.2 and B-3 S.4.3
    -- individual answers are confidential to the platform and the report
    aggregates and anonymises.
    """
    cursor.execute(
        """
        SELECT r.question_id, r.answer_value, r.is_dont_know,
               coalesce(rs.role, ''), rs.id::text
        FROM responses r
        JOIN respondents rs ON r.respondent_id = rs.id
        WHERE rs.engagement_id = %s
          AND rs.status <> 'removed'
        ORDER BY r.question_id, rs.completed_at NULLS LAST
        """,
        [engagement_id],
    )
    by_question: dict[str, list] = {}
    respondents: set[str] = set()
    for qid, av, dk, role, rid in cursor.fetchall():
        respondents.add(rid)
        by_question.setdefault(qid, []).append(
            (role, {"value": loads_maybe(av), "dont_know": bool(dk)}))

    def _rank(role: str) -> int:
        return _ROLE_PRECEDENCE.index(role) if role in _ROLE_PRECEDENCE else len(_ROLE_PRECEDENCE)

    primary = {}
    for qid, entries in by_question.items():
        entries.sort(key=lambda e: _rank(e[0]))
        primary[qid] = entries[0][1]
    return primary, by_question, len(respondents)


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
            answer = f"{answer} - respondent answered Don't know"
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
# Opinion rule (Phase 1 placeholder - operator-tunable)
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
                f"{name} scored {o['score_0_100']} - below the "
                f"{OPINION_SCORE_FLOOR:.0f} threshold."
            )
        if (o.get("dk_ratio") or 0) > OPINION_DK_CEILING:
            drivers.append(
                f"{name} \"don't know\" ratio {o['dk_ratio']} exceeds "
                f"{OPINION_DK_CEILING} - material uncertainty."
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
        responses, responses_by_question, respondent_count = _load_responses(cursor, engagement_id)
        cursor.execute("SELECT coalesce(instrument, 'tier_1') FROM engagements WHERE id = %s", [engagement_id])
        _irow = cursor.fetchone()
        instrument = _irow[0] if _irow and _irow[0] else "tier_1"
        # OD-19 (2026-10-01): a combined engagement produces two completely
        # separate reports. This document is the governance report only;
        # the AI IT Security Audit has its own pack, its own appendix and
        # its own opinion. Nothing from the security questionnaire renders
        # here.
        aiitsa_by_question = {}
    aiitsa_body = ""

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
         "item": _fuzzy_module_score(v2_items, "workflow"),
         "metric_note": None},
        {"n": 2, "name": "Data Reliability Checklist",
         "item": _fuzzy_module_score(v2_items, "data"),
         "metric_note": None},
        {"n": 3, "name": "AI Adoption Pattern Map",
         "item": _fuzzy_module_score(v2_items, "adoption", "pattern"),
         "metric_note": None},
        {"n": 4, "name": "AI Governance Matrix",
         "item": _fuzzy_module_score(v2_items, "governance"),
         "metric_note": None},
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
        _artifact(qindex, responses, title, intro, qids)
        for title, intro, qids in SECTION_4_ARTIFACTS
    ]
    eff_scorecard = {
        "overall": (eff["overall"] if eff else None),
        "items": (eff["items"] if eff else []),
        "gaps": (eff["priority_gaps"] if eff else []),
    }
    ninety_day = []
    for f in (eff, v3, v2):
        if f:
            for gap in f["priority_gaps"]:
                ninety_day.append(gap)
    ninety_day = ninety_day[:3]

    # --- Section 5 ---
    opinion = _build_opinion(frameworks)

    # --- Divergence panel (Part B-3 S.2.2, S.2.4): multi-respondent only ---
    # Where leadership and the workforce disagree by 20+ points, and the
    # single questions they answered most differently. Aggregation data is
    # attached to each framework context by scoring.engine; absent for a
    # single respondent, so the panel does not exist for Tier 1.
    divergence = None
    _agg_frameworks = [f for f in frameworks if not f.get("error") and f.get("aggregation")]
    if respondent_count > 1 and _agg_frameworks:
        _agg = _agg_frameworks[0]["aggregation"]
        _dim_label = {}
        for f in _agg_frameworks:
            for item in (f.get("items") or []):
                if isinstance(item, dict) and item.get("name"):
                    _dim_label[(f["framework"]["key"], item["name"])] = item.get("label") or item.get("display_name") or item["name"].replace("_", " ").title()
        _fw_name = {f["framework"]["key"]: f["framework"].get("display_name", f["framework"]["key"]) for f in _agg_frameworks}
        rows = []
        for d in _agg.get("dimensions", []):
            if d.get("leadership_mean") is None or d.get("workforce_mean") is None:
                continue
            rows.append({
                "framework": _fw_name.get(d["framework"], d["framework"]),
                "dimension": _dim_label.get((d["framework"], d["dimension"]), d["dimension"].replace("_", " ").title()),
                "leadership": round(d["leadership_mean"]),
                "workforce": round(d["workforce_mean"]),
                "gap": round(d["divergence"]),
                "flagged": bool(d.get("flagged")),
            })
        rows.sort(key=lambda r: -abs(r["gap"]))
        contested = []
        for c in _agg.get("contested", [])[:5]:
            if c.get("stdev_0_1", 0) <= 0:
                continue
            q = qindex.get(c["question_id"], {})
            entries = responses_by_question.get(c["question_id"], [])
            contested.append({
                "qid": c["question_id"], "question": q.get("question_text", c["question_id"]),
                "answers": "; ".join(f"{_ROLE_LABELS.get(role, role or 'Respondent')}: {_format_answer(resp)}"
                                     for role, resp in entries),
                "spread": round(c["stdev_0_1"] * 100),
            })
        divergence = {
            "respondent_count": _agg.get("respondent_count", respondent_count),
            "roles": [_ROLE_LABELS.get(r, r) for r in _agg.get("roles", [])],
            "threshold": int(_agg.get("divergence_threshold", 20)),
            "rows": rows, "flagged": [r for r in rows if r["flagged"]], "contested": contested,
        }

    # --- Appendix A ---
    appendix = []
    for q in QUESTIONS:
        entries = responses_by_question.get(q["id"], [])
        if respondent_count > 1 and len(entries) > 1:
            # Every respondent's answer, by role. The report gains rows, not
            # a new shape (operator decision 2026-09-27).
            answer = "; ".join(
                f"{_ROLE_LABELS.get(role, role or 'Respondent')}: {_format_answer(resp)}"
                for role, resp in entries)
        else:
            answer = _format_answer(responses.get(q["id"]))
        appendix.append({
            "qid": q["id"],
            "section": q.get("section", ""),
            "question": q["question_text"],
            "answer": answer,
        })
    if aiitsa_by_question:
        from questionnaire.aiitsa_question_bank import AIITSA_QUESTIONS
        for q in AIITSA_QUESTIONS:
            entries = aiitsa_by_question.get(q["id"], [])
            if respondent_count > 1 and len(entries) > 1:
                answer = "; ".join(f"{_ROLE_LABELS.get(role, role or 'Respondent')}: {_format_answer(resp)}"
                                   for role, resp in entries)
            else:
                answer = _format_answer(entries[0][1]) if entries else _format_answer(None)
            appendix.append({
                "qid": q["id"],
                "section": f"AI IT Security Audit: {q['domain_label']}",
                "question": q["question_text"],
                "answer": answer,
            })

    context = {
        "company": (first["company"] if first else None),
        "engagement": (first["engagement"] if first else None),
        "generated_at": (first["generated_at"] if first else ""),
        "instrument": instrument,
        "respondent_count": respondent_count,
        "respondent_basis": ("Single-respondent snapshot" if respondent_count <= 1
                             else f"{respondent_count}-respondent engagement"),
        "frameworks": frameworks,
        "section1": section1,
        "gap_analysis": gap_analysis,
        "perf_vs_op": perf_vs_op,
        "policy_fields": policy_fields,
        "conditions": conditions,
        "neyr_olf_signals": neyr_olf_signals,
        "condition_narratives": condition_narratives,
        "v2_overall": (v2["overall"] if v2 else None),
        "section3": section3,
        "maturity": maturity,
        "section4": section4,
        "eff_scorecard": eff_scorecard,
        "ninety_day": ninety_day,
        "opinion": opinion,
        "divergence": divergence,
        "aiitsa_body": aiitsa_body,
        "appendix": appendix,
        "methodology": (first["methodology"] if first else ""),
        "trademark_notice": (first["trademark_notice"] if first else ""),
        "disclaimer": (first["disclaimer"] if first else ""),
    }

    # --- Tool-inventory discrepancy signal ---
    # Compare T1-A-000 tool count against T1-B-009 / T1-B-011 self-reports.
    # Attached to context so AI analysis can quote it and the template
    # renders a Basis-for-Opinion exception when material.
    try:
        from reports.tool_inventory_signals import compute_signals
        from django.db import connection as _conn
        with _conn.cursor() as _c:
            # engagement_id -> respondent_id lookup
            _c.execute(
                "SELECT id FROM respondents WHERE engagement_id = %s LIMIT 1",
                (engagement_id,),
            )
            _row = _c.fetchone()
            if _row:
                context["tool_inventory_signal"] = compute_signals(_c, _row[0])
    except Exception:  # noqa: BLE001
        logger.exception("tool_inventory_signal compute failed; continuing")
        context["tool_inventory_signal"] = None

    # --- Phase 2a: AI narrative analysis (never fatal) ---
    try:
        from reports.ai_analysis import analyze_report
        context["ai"] = analyze_report(engagement_id, context)
    except Exception:  # noqa: BLE001
        logger.exception("AI analysis failed; rendering without narratives")
        context["ai"] = {}

    # --- Phase 2b: fold checklist exceptions into the opinion ---
    # Material exceptions from the 100-point qualified-opinion checklist
    # qualify the opinion even when framework scores alone would not.
    basis = (context["ai"] or {}).get("opinion_basis") or {}
    exceptions = basis.get("exceptions") or []
    material = [e for e in exceptions if e.get("materiality") == "material"]
    if material and opinion["kind"] == "unqualified":
        opinion["kind"] = "qualified"
    opinion["exceptions"] = exceptions
    opinion["scope_limitations"] = basis.get("scope_limitations") or []
    opinion["statement"] = basis.get("opinion_statement") or ""

    return render_to_string("reports/tier1_snapshot.html", context)
