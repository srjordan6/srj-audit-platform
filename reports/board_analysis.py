"""Auditor's analysis and opinion for the Combined Board Analysis (OD-19).

When a company buys both audits at Tier 2 it receives the governance
report, the security report, and this third document, which reads the
two together for the board and carries the ONE opinion the engagement
gets. Same discipline as reports.ai_analysis and reports.aiitsa_analysis:
the model writes from the scored data only and never issues the opinion;
results are stored once per engagement (board_analysis_v1); failures are
recorded loudly; runs on the report model.

Sections
  compound   where governance gaps and security gaps make each other worse
  roadmap    one prioritised roadmap across both audits
  decisions  the decisions only the board can make
  opinion    exceptions across both audits, scope limitations, statement
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from django.conf import settings
from django.db import connection

from reports.ai_analysis import OllamaClient, _is_hard_stop, _is_hard_stop_text, _record_failure
from reports.aiitsa_analysis import _chat, _validate_opinion, _validate_section

logger = logging.getLogger(__name__)

EVENT_TYPE = "board_analysis_v1"
MAX_TOKENS_SECTION = 1800
MAX_TOKENS_OPINION = 6000

SYSTEM_PROMPT = (
    "You are the analysis engine for the SRJ AI Audit Platform, writing the "
    "auditor's analysis inside a Combined Board Analysis for a company that "
    "commissioned two audits at once: the AI Audit Snapshot (governance, "
    "readiness, efficiency; four scored frameworks; qualified-opinion "
    "checklist) and the AI IT Security Audit (seven Baseline areas, "
    "Visibility Triangle, dated Baseline Score). Several people answered "
    "each audit; leadership and workforce disagreement is measured. Your "
    "reader is the board. Write in plain, direct, professional English, "
    "the voice of an experienced auditor briefing directors: factual, "
    "specific, no hype, no hedging filler, no jargon the board has not been "
    "given. Base every statement ONLY on the data provided and name the "
    "audit, the dimension or area, and the question ids that evidence a "
    "finding. Never invent facts, tools, numbers or scores. Do not issue or "
    "imply an audit opinion; the platform computes that separately.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences, no prose "
    "before or after, in exactly this shape:\n"
    "{\"narrative\": \"2-4 paragraph analysis as a single string\", "
    "\"key_findings\": [\"finding 1\", \"finding 2\", \"finding 3\"], "
    "\"recommendations\": [\"action 1\", \"action 2\"]}\n"
    "3-5 key_findings and 2-4 recommendations, each one sentence."
)

SECTION_PROMPTS = {
    "compound": (
        "Write section 2, Where governance and security compound. Read the "
        "two audits against each other. Where a governance weakness (no "
        "inventory, no owner, no policy, no board cadence, low readiness) and "
        "a security weakness (unknown identities, unmapped data, no incident "
        "capability, unverified vendors) describe the same underlying "
        "condition, say so and name both sides. Where one audit is "
        "materially stronger than the other, say what that asymmetry means "
        "for the board. Where leadership and the workforce disagree in "
        "either audit, say which disagreement matters most."
    ),
    "roadmap": (
        "Write section 3, One roadmap. The two reports each carry their own "
        "roadmap; the board needs one. Order the first 90 days so that work "
        "which serves both audits comes first (mandate and named owners, the "
        "inventory, the data map, the incident capability), then the work "
        "each audit needs alone. Name the owner role for each move and what "
        "evidence the board should ask to see at the end of each 30 days. "
        "Do not reorder the security method's fixed sequence inside its own "
        "lane."
    ),
    "decisions": (
        "Write section 4, Decisions for the board. List the four to six "
        "decisions only the board can take, each stated as a decision (what "
        "to decide, by when, on what evidence), drawn from both audits: "
        "appetite, accountability, budget, oversight cadence, disclosure "
        "and insurance posture, and whether to commission the analyst-tier "
        "verification that lifts the self-reported caps."
    ),
}

OPINION_SYSTEM_PROMPT = (
    "You are the opinion-basis engine for the SRJ AI Audit Platform's "
    "Combined Board Analysis. You are given the scored results, computed "
    "opinion drivers and the already-identified exceptions of BOTH audits "
    "(governance and security), with the question ids that evidence each. "
    "Produce the combined basis: consolidate the exceptions of both audits "
    "into at most 10, most material first, merging any that describe the "
    "same condition from two sides (name both audits in such a merged "
    "exception), each with the question ids as evidence and a materiality of "
    "\"material\" or \"notable\". List scope limitations across both "
    "audits. Do not invent evidence.\n\n"
    "Also write opinion_statement: a formal two-sentence auditor's opinion "
    "on the company's overall AI posture, governance and security together, "
    "in EXACTLY this structure. Sentence 1: 'In our opinion, except for the "
    "[summary of the material exception areas] detailed in the Basis for "
    "Qualified Opinion section, the company's overall AI posture provides "
    "[what the evidence supports it provides].' Sentence 2: 'However, until "
    "the noted deficiencies are reconciled through [the two or three most "
    "important remediations], the current environment represents [a "
    "characterization of the residual risk] that prevents a full "
    "endorsement of the company's AI governance and security.' Ground every "
    "bracketed element in the actual exceptions. If there are no material "
    "exceptions, write an unqualified two-sentence opinion in the same "
    "register.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences:\n"
    "{\"exceptions\": [{\"area\": \"Governance / Data\", \"finding\": "
    "\"...\", \"evidence\": \"question ids and answers\", \"materiality\": "
    "\"material\"}], \"scope_limitations\": [\"...\"], "
    "\"opinion_statement\": \"In our opinion, ...\"}"
)


def _payload(section_key: str, ctx: dict) -> dict:
    g, s = ctx["gov"], ctx["sec"]
    base = {
        "company": ctx["company"],
        "respondents": {"governance": g["respondent_count"], "security": s["respondent_count"]},
        "governance": {
            "frameworks": [{"name": f["framework"]["display_name"], "score_0_100": f["overall"].get("score_0_100"),
                            "maturity": f["overall"].get("maturity_label"), "dk_ratio": f["overall"].get("dk_ratio"),
                            "weakest_items": [{"name": i.get("label") or i.get("name"), "score": i.get("score_0_100"),
                                               "maturity": i.get("maturity_label")}
                                              for i in sorted((f.get("items") or []), key=lambda i: (i.get("score_0_100") is None, i.get("score_0_100") or 0))[:3]]}
                           for f in g["frameworks"] if not f.get("error")],
            "priority_gaps": g["priority_gaps"][:8],
            "divergence": g["divergence"],
            "opinion_drivers": g["opinion"].get("drivers") or [],
            "exceptions": g["opinion"].get("exceptions") or [],
        },
        "security": {
            "baseline": s["baseline"],
            "areas": [{"area": a["area"], "score_0_100": a["score"], "level": a["level_label"], "gap_count": a["gap_count"],
                       "gaps": [{"id": x["id"], "question": x["text"], "answer": x["answer"]} for x in a["gaps"][:4]]}
                      for a in s["areas"]],
            "visibility_triangle": [{"domain": v["domain"], "zone": v["zone"]} for v in s["visibility"]],
            "divergence": (s.get("divergence") or {}).get("rows"),
            "opinion_drivers": s["opinion"].get("drivers") or [],
            "exceptions": s["opinion"].get("exceptions") or [],
        },
    }
    if section_key == "roadmap":
        base["security"]["roadmap_90_day"] = [{"when": w, "workstream": x} for w, x in s["roadmap"]]
        base["governance"]["ninety_day"] = g["ninety_day"]
    return base


def _load_stored(engagement_id):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM events WHERE event_type = %s AND payload->>'engagement_id' = %s "
                           "ORDER BY created_at DESC LIMIT 1", [EVENT_TYPE, str(engagement_id)])
            row = cursor.fetchone()
        if not row:
            return None
        from core.dbjson import loads_maybe
        return (loads_maybe(row[0]) or {}).get("sections") or None
    except Exception:  # noqa: BLE001
        logger.exception("board_analysis: load failed")
        return None


def _store(engagement_id, sections, model):
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO events (event_type, payload) VALUES (%s, %s)",
                           [EVENT_TYPE, json.dumps({"engagement_id": str(engagement_id), "model": model, "sections": sections})])
    except Exception:  # noqa: BLE001
        logger.exception("board_analysis: store failed")


def build_opinion(ctx: dict, basis: dict | None) -> dict:
    """One opinion on both audits: qualified when either audit's own rule
    qualifies, or when a material exception survives consolidation."""
    g, s = ctx["gov"]["opinion"], ctx["sec"]["opinion"]
    drivers = [f"Governance audit: {d}" for d in (g.get("drivers") or [])] + \
              [f"Security audit: {d}" for d in (s.get("drivers") or [])]
    exceptions = (basis or {}).get("exceptions") or []
    material = [e for e in exceptions if e.get("materiality") == "material"]
    kind = "qualified" if (drivers or material or g.get("kind") == "qualified" or s.get("kind") == "qualified") else "unqualified"
    if s.get("kind") == "disclaimer" and not ctx["gov"]["frameworks"]:
        kind = "disclaimer"
    return {"kind": kind, "drivers": drivers, "exceptions": exceptions,
            "scope_limitations": (basis or {}).get("scope_limitations") or [],
            "statement": (basis or {}).get("opinion_statement") or ""}


def analyze_board(engagement_id, ctx: dict) -> dict[str, Any]:
    if not getattr(settings, "AI_ANALYSIS_ENABLED", True):
        return {}
    stored = _load_stored(engagement_id) or {}
    missing = [k for k in (*SECTION_PROMPTS, "opinion_basis") if k not in stored]
    if not missing:
        return stored
    provider = (os.environ.get("AI_ANALYSIS_PROVIDER") or "ollama").strip().lower()
    if provider == "anthropic":
        api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
        if not api_key:
            return {}
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model = getattr(settings, "AI_ANALYSIS_MODEL", "claude-sonnet-4-5")
    else:
        model = os.environ.get("OLLAMA_MODEL_REPORT") or os.environ.get("OLLAMA_MODEL_NARRATIVE") or "deepseek-v4-pro"
        client = OllamaClient(os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434",
                              os.environ.get("OLLAMA_API_KEY", ""))
    sections: dict[str, Any] = dict(stored)
    failures = []
    for key, instruction in SECTION_PROMPTS.items():
        if key in sections:
            continue
        try:
            prompt = instruction + "\n\nDATA:\n" + json.dumps(_payload(key, ctx), default=str)
            out = _chat(client, model, SYSTEM_PROMPT, prompt, MAX_TOKENS_SECTION, _validate_section)
            if out:
                sections[key] = out
        except Exception as exc:  # noqa: BLE001
            logger.exception("board_analysis: %s failed", key)
            failures.append((key, str(exc)[:300]))
            if _is_hard_stop(exc):
                break
    if "opinion_basis" not in sections and not any(_is_hard_stop_text(f[1]) for f in failures):
        try:
            prompt = "COMPANY DATA:\n" + json.dumps(_payload("opinion", ctx), default=str)
            out = _chat(client, model, OPINION_SYSTEM_PROMPT, prompt, MAX_TOKENS_OPINION, _validate_opinion)
            if out:
                sections["opinion_basis"] = out
        except Exception as exc:  # noqa: BLE001
            logger.exception("board_analysis: opinion failed")
            failures.append(("opinion_basis", str(exc)[:300]))
    if failures:
        _record_failure(engagement_id, model, failures, len(sections))
    if any(k in sections for k in missing):
        _store(engagement_id, sections, model)
    return sections
