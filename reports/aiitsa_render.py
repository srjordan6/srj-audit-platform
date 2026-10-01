"""AI IT Security Audit(TM) report: the Four-Page Pack (spec v1.6 S.10).

  Page 1  Executive summary: exposure statement, Visibility Triangle
          zones, headline findings.
  Page 2  Remediation Roadmap: gap-to-standard for each of the seven
          Baseline areas, then the 90-day roadmap in the book's fixed
          sequence (S.11, do not reorder).
  Page 3  Framework Crosswalk: one-page external reference (S.9), static
          rows keyed to the seven areas.
  Page 4  Baseline Score: dated, scored, trendable (prior dated scores
          from the scores table give the "compared to what?" line).
  Appendix  every question and the answer(s), by role when several
          respondents answered.

Design rule from the mine: every score line pairs with the artefact it
needs or the gap statement; the pack must be defensible to whoever asks
first. Trademark rule (S.12 / OD-B): the instrument names carry no (TM);
the product is "AI IT Security Audit" with (TM).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from django.db import connection
from django.template.loader import render_to_string

from core.dbjson import loads_maybe
from questionnaire.aiitsa_question_bank import AIITSA_QUESTIONS
from scoring.aiitsa import AIITSAResult, score_aiitsa

logger = logging.getLogger(__name__)

_ROLE_LABELS = {"BOARD": "Board", "CEO": "CEO", "CFO": "CFO", "CIO": "CIO", "CISO": "CISO",
                "COO": "COO", "VP": "VP", "DIR": "Director", "MGR": "Manager",
                "IC": "Individual contributor", "HR": "HR"}
_ROLE_PRECEDENCE = ["CISO", "CIO", "CEO", "BOARD", "CFO", "COO", "VP", "DIR", "HR", "MGR", "IC"]

DOMAIN_LABELS = {
    "governance": "Governance", "security_operations": "Security Operations",
    "architecture": "Architecture", "application_security": "Application Security",
    "third_party_risk": "Third-Party Risk", "data_protection": "Data Protection",
}
ZONE_LABELS = {
    "known": "Known (named)", "suspected": "Suspected", "clear": "None named",
    "unknown": "Unknown zone", "unanswered": "Not answered",
}

# S.9 crosswalk, static content keyed to the seven Baseline areas. Rows are
# the frameworks the mine weights most; a real engagement can extend them.
CROSSWALK = [
    ("Inventory", "NIST AI RMF MAP 1 / GOVERN 1.6", "ISO/IEC 42001 A.6 (AI system inventory)", "NIST CSF 2.0 ID.AM", "EU AI Act Art. 49 registration; SEC cyber disclosure (material systems)"),
    ("Access", "NIST SP 800-207 Zero Trust; OWASP Agentic (agent identity)", "ISO/IEC 27001 A.5.15-5.18 access control", "MITRE ATLAS AML.T0040 (ML supply chain), credential techniques", "HIPAA 164.312(a); state AI laws on automated decision access"),
    ("Data", "NIST AI RMF MAP 2.3 / MEASURE 2.6", "ISO/IEC 42001 A.7 data for AI systems", "OWASP LLM06 sensitive information disclosure; LLM03 training data poisoning", "GDPR Art. 5, 6, 17, 30, 35; CCPA; HIPAA 164.312(b)"),
    ("Vendors", "NIST AI RMF GOVERN 6 (third-party)", "ISO/IEC 42001 A.10 third-party and customer relationships", "OWASP LLM05 supply chain vulnerabilities", "GDPR Art. 28 processors; SEC third-party cyber risk; HITRUST AI"),
    ("Incidents", "NIST AI RMF MANAGE 4.3 incident response", "NIST CSF 2.0 DE, RS, RC; ISO/IEC 27001 A.5.24-5.28", "MITRE ATLAS tactics: Initial Access through Impact; OWASP LLM01 prompt injection", "SEC Form 8-K Item 1.05 (4-day material incident); GDPR Art. 33 (72 hours); HIPAA breach rule"),
    ("Governance", "NIST AI RMF GOVERN 1-5; Google SAIF", "ISO/IEC 42001 clauses 5, 6, 9; COBIT / COSO ERM", "OWASP AIVSS risk rating; SR 11-7 model risk", "EU AI Act Art. 9 risk management; state AI laws (CO, TX, CA)"),
    ("Evidence", "NIST AI RMF MEASURE 1 / MANAGE 1 documentation", "ISO/IEC 42001 clause 7.5 documented information; ISO 27001 A.5.36", "NIST CSF 2.0 GV.OV (oversight and evaluation)", "SEC 10-K Item 1C cyber governance disclosure; FedRAMP / CMMC 2.0 evidence packages"),
]

ROADMAP_90_DAY = [
    ("Week 1", "Mandate week (political, not technical): signed written audit mandate, executive coalition named (CISO, CIO, CRO, GC), audit team roster, wall calendar."),
    ("Week 2", "Sanctioned AI discovery."),
    ("Week 3", "Shadow and embedded AI discovery."),
    ("Week 4", "Agentic AI discovery; apply the Visibility Triangle; four-layer AI inventory complete."),
    ("Week 5", "Non-human identity discovery against the full inventory."),
    ("Week 6", "Agent boundary matrix."),
    ("Weeks 7-9", "Application security testing with test evidence; top-tier vendor contract review; cross-border inference review; IR integration; AI Red Button rehearsal in week 9."),
    ("Weeks 10-13", "Assembly: Four-Page Pack, Baseline Score, remediation roadmap, board presentation."),
]


def _rank(role: str) -> int:
    return _ROLE_PRECEDENCE.index(role) if role in _ROLE_PRECEDENCE else len(_ROLE_PRECEDENCE)


def _t1_sources(cursor, engagement_id: str) -> dict[str, tuple[str, dict]]:
    """{respondent_id: (role, {t1_id: response})} for the governance answers
    that stand in for overlapping security questions (OD-19)."""
    from questionnaire.overlap import SOURCE_IDS
    cursor.execute(
        """
        SELECT rs.id::text, coalesce(rs.role, ''), r.question_id, r.answer_value, r.is_dont_know
        FROM responses r JOIN respondents rs ON rs.id = r.respondent_id
        WHERE rs.engagement_id = %s AND rs.status <> 'removed' AND r.question_id = ANY(%s)
        """,
        [engagement_id, list(SOURCE_IDS)],
    )
    out: dict[str, tuple[str, dict]] = {}
    for rid, role, qid, av, dk in cursor.fetchall():
        out.setdefault(rid, (role, {}))[1][qid] = {"value": loads_maybe(av), "dont_know": bool(dk)}
    return out


def load_aiitsa_responses(cursor, engagement_id: str) -> tuple[dict, dict, int]:
    """(primary, by_question, respondent_count) over the AIITSA questions of
    this engagement. Primary answer is the most senior security role's.
    For scoring N respondents use load_aiitsa_per_respondent()."""
    cursor.execute(
        """
        SELECT r.question_id, r.answer_value, r.is_dont_know, coalesce(rs.role, ''), rs.id::text
        FROM responses r
        JOIN respondents rs ON rs.id = r.respondent_id
        WHERE rs.engagement_id = %s AND rs.status <> 'removed'
          AND r.question_id LIKE 'AIITSA-%%'
        ORDER BY r.question_id, rs.completed_at NULLS LAST
        """,
        [engagement_id],
    )
    by_q: dict[str, list] = {}
    who: set[str] = set()
    have: dict[str, set] = {}
    for qid, av, dk, role, rid in cursor.fetchall():
        who.add(rid)
        have.setdefault(rid, set()).add(qid)
        by_q.setdefault(qid, []).append((role, {"value": loads_maybe(av), "dont_know": bool(dk)}))
    from questionnaire.overlap import derive_for_respondent
    for rid, (role, t1) in _t1_sources(cursor, engagement_id).items():
        if rid not in who:
            continue  # governance-only respondent: not part of this audit
        for qid, resp in derive_for_respondent(t1, have.get(rid, set())).items():
            by_q.setdefault(qid, []).append((role, resp))
    primary = {}
    for qid, entries in by_q.items():
        entries.sort(key=lambda e: _rank(e[0]))
        primary[qid] = entries[0][1]
    return primary, by_q, len(who)


def load_aiitsa_per_respondent(cursor, engagement_id: str) -> list[tuple[str, dict]]:
    """[(role, {qid: resp}), ...] for every non-removed respondent with
    AIITSA answers, most senior role first."""
    cursor.execute(
        """
        SELECT rs.id::text, coalesce(rs.role, ''), r.question_id, r.answer_value, r.is_dont_know
        FROM responses r JOIN respondents rs ON rs.id = r.respondent_id
        WHERE rs.engagement_id = %s AND rs.status <> 'removed' AND r.question_id LIKE 'AIITSA-%%'
        """,
        [engagement_id],
    )
    per: dict[str, tuple[str, dict]] = {}
    for rid, role, qid, av, dk in cursor.fetchall():
        per.setdefault(rid, (role, {}))[1][qid] = {"value": loads_maybe(av), "dont_know": bool(dk)}
    from questionnaire.overlap import derive_for_respondent
    for rid, (_role, t1) in _t1_sources(cursor, engagement_id).items():
        if rid in per:
            per[rid][1].update(derive_for_respondent(t1, set(per[rid][1])))
    return sorted(per.values(), key=lambda x: _rank(x[0]))


def _carried(resp) -> str:
    """Appendix note for an answer carried from the governance questionnaire."""
    src = resp.get("derived_from") if isinstance(resp, dict) else None
    return f" (answered once, in the governance questionnaire as {src})" if src else ""


def _selected(resp) -> str:
    v = resp.get("value") if isinstance(resp, dict) else None
    if isinstance(v, dict):
        v = v.get("selected", v.get("value"))
    if isinstance(v, list):
        v = v[0] if v else None
    return "" if v is None else str(v)


def _prior_scores(cursor, company_id: str, exclude_report_id: str | None) -> list[dict]:
    cursor.execute(
        """
        SELECT calculated_at::date, score FROM scores
        WHERE company_id = %s AND framework = 'aiitsa' AND dimension = '__overall__'
          AND (%s::uuid IS NULL OR report_id <> %s::uuid)
        ORDER BY calculated_at DESC LIMIT 6
        """,
        [company_id, exclude_report_id, exclude_report_id],
    )
    return [{"date": d, "score": float(s)} for d, s in cursor.fetchall()]


def build_aiitsa_context(engagement_id: str, *, assessed_on: date | None = None,
                         exclude_report_id: str | None = None) -> dict[str, Any]:
    qindex = {q["id"]: q for q in AIITSA_QUESTIONS}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.id::text, c.name, c.industry, c.size_bracket, e.instrument
            FROM engagements e JOIN companies c ON c.id = e.company_id WHERE e.id = %s
            """,
            [engagement_id],
        )
        row = cursor.fetchone()
        company = {"id": row[0], "name": row[1], "industry": row[2], "size_bracket": row[3]} if row else {}
        instrument = row[4] if row else "aiitsa"
        primary, by_q, n = load_aiitsa_responses(cursor, engagement_id)
        per_resp = load_aiitsa_per_respondent(cursor, engagement_id)
        history = _prior_scores(cursor, company["id"], exclude_report_id) if company else []

    from scoring.aiitsa import aggregate_aiitsa
    if len(per_resp) > 1:
        result, aggregation = aggregate_aiitsa(
            [(role, score_aiitsa(answers, assessed_on=assessed_on)) for role, answers in per_resp],
            assessed_on=assessed_on)
    else:
        result = score_aiitsa(primary, assessed_on=assessed_on)
        aggregation = None

    areas = []
    for a in result.areas:
        gap_rows = []
        for qid in a.gaps[:6]:
            q = qindex[qid]
            gap_rows.append({"id": qid, "text": q["question_text"], "answer": _selected(primary.get(qid))})
        areas.append({
            "area": a.area, "score": a.score_0_100, "level": a.level, "level_label": a.level_label,
            "capped": a.capped, "answered": a.answered, "expected": a.expected, "dont_know": a.dont_know,
            "standard": a.minimum_standard, "gap_count": len(a.gaps), "gaps": gap_rows,
            "bar": int(round(a.score_0_100)),
        })

    visibility = [{"domain": DOMAIN_LABELS.get(v.domain, v.domain), "question": qindex[v.question_id]["question_text"],
                   "answer": v.answer or "", "zone": v.zone, "zone_label": ZONE_LABELS.get(v.zone, v.zone)}
                  for v in result.visibility]
    unknown_domains = [v["domain"] for v in visibility if v["zone"] == "unknown"]
    weakest = [x for x in areas if x["area"] in result.top_gaps[:3]]

    # Exposure statement: written from the numbers, no adjectives the
    # numbers do not support.
    if result.answered == 0:
        exposure = "No AIITSA answers were recorded for this engagement."
    else:
        exposure = (
            f"On {result.assessed_on.isoformat()}, {company.get('name', 'the company')} scored "
            f"{result.baseline_score_0_100:.0f} of 100 on the Defensible AI Security Baseline across "
            f"seven areas, a self-reported level of {result.baseline_level_label}. "
            f"{result.unknown_zone_ratio:.0%} of answers were \"Don't know\", which the audit treats as "
            f"unknown-zone exposure rather than a missing answer."
        )
        if unknown_domains:
            exposure += (" The Visibility Triangle places " + ", ".join(unknown_domains) +
                         " in the unknown zone: the respondent could not say whether a blind spot exists there.")

    appendix = []
    for q in AIITSA_QUESTIONS:
        entries = by_q.get(q["id"], [])
        if n > 1 and len(entries) > 1:
            answer = "; ".join(f"{_ROLE_LABELS.get(r, r or 'Respondent')}: {_selected(x) or 'not answered'}{_carried(x)}" for r, x in entries)
        else:
            answer = (_selected(primary.get(q["id"])) or "not answered") + _carried(primary.get(q["id"]))
        appendix.append({"qid": q["id"], "domain": q["domain_label"], "area": q["baseline_area"],
                         "question": q["question_text"], "answer": answer})

    divergence = None
    if aggregation and aggregation.get("dimensions"):
        rows = [{"area": d["dimension"], "leadership": round(d["leadership_mean"]), "workforce": round(d["workforce_mean"]),
                 "gap": round(d["divergence"]), "flagged": d["flagged"]}
                for d in aggregation["dimensions"] if d.get("leadership_mean") is not None and d.get("workforce_mean") is not None]
        rows.sort(key=lambda r: -abs(r["gap"]))
        divergence = {"respondent_count": aggregation["respondent_count"],
                      "roles": [_ROLE_LABELS.get(r, r) for r in aggregation["roles"]],
                      "threshold": int(aggregation["divergence_threshold"]), "rows": rows,
                      "flagged": [r for r in rows if r["flagged"]]}

    return {
        "company": company, "engagement_id": engagement_id, "instrument": instrument,
        "assessed_on": result.assessed_on, "respondent_count": n, "divergence": divergence,
        "aggregation": aggregation,
        "baseline": {"score": result.baseline_score_0_100, "level": result.baseline_level,
                     "level_label": result.baseline_level_label,
                     "unknown_zone_pct": round(result.unknown_zone_ratio * 100),
                     "answered": result.answered, "expected": result.expected},
        "exposure": exposure, "visibility": visibility, "unknown_domains": unknown_domains,
        "areas": areas, "weakest": weakest, "crosswalk": CROSSWALK, "roadmap": ROADMAP_90_DAY,
        "history": history, "appendix": appendix,
        "level_scale": ["Absent", "Partial", "Defensible", "Mature"],
    }


def _with_analysis(engagement_id: str, ctx: dict) -> dict:
    """Auditor's analysis per page and the formal opinion (never fatal)."""
    from reports.aiitsa_analysis import analyze_aiitsa, build_opinion
    try:
        ctx["ai"] = analyze_aiitsa(engagement_id, ctx)
    except Exception:  # noqa: BLE001
        logger.exception("AIITSA analysis failed; rendering without narratives")
        ctx["ai"] = {}
    ctx["opinion"] = build_opinion(ctx, (ctx["ai"] or {}).get("opinion_basis"))
    return ctx


def render_aiitsa_pack_html(engagement_id: str, **kw) -> str:
    return render_to_string("reports/aiitsa_pack.html", _with_analysis(engagement_id, build_aiitsa_context(engagement_id, **kw)))


def render_aiitsa_body_html(engagement_id: str, **kw) -> str:
    """The pages without cover or CSS, for embedding as Part II of a
    combined report."""
    ctx = _with_analysis(engagement_id, build_aiitsa_context(engagement_id, **kw))
    ctx["embedded"] = True
    return render_to_string("reports/_aiitsa_body.html", ctx)


def aiitsa_score_payload(ctx: dict[str, Any]) -> dict[str, Any]:
    """What scoring.persistence.persist_snapshot_scores stores for framework
    'aiitsa': the dated Baseline Score as __overall__ and one row per area."""
    b = ctx["baseline"]
    return {
        "overall": {"score_0_100": b["score"], "maturity_level": b["level"],
                    "maturity_label": b["level_label"], "assessed_on": ctx["assessed_on"].isoformat(),
                    "unknown_zone_pct": b["unknown_zone_pct"], "answered": b["answered"],
                    "expected": b["expected"], "self_serve_cap": "Partial",
                    "confidence_level": ("low" if b["unknown_zone_pct"] >= 25 else "medium")},
        "items": [{"name": a["area"], "score_0_100": a["score"], "maturity_level": a["level"],
                   "maturity_label": a["level_label"], "capped": a["capped"], "answered": a["answered"],
                   "expected": a["expected"], "dont_know": a["dont_know"], "gap_count": a["gap_count"],
                   "confidence_level": ("low" if a["answered"] and a["dont_know"] / a["answered"] >= 0.25 else "medium")}
                  for a in ctx["areas"]],
        "gaps": [w["area"] for w in ctx["weakest"]],
        "aggregation": ctx.get("aggregation"),
    }
