"""AI narrative analysis layer for the Tier 1 report (Phase 2a).

Calls the Claude API once per report category and returns structured
narratives that reports/report_render.py merges into the template context
under the "ai" key. The scoring engine remains the source of truth for all
numbers and for the opinion; the model only writes analysis AROUND the
computed scores and the respondent's answers.

Design guarantees:
- Report generation NEVER fails because of this module. Any error (no API
  key, network, rate limit, malformed model output) degrades to an empty
  dict for that section and the template renders without the AI block.
- Output for each engagement is persisted to the events table
  (event_type='ai_analysis_v1') for auditability and reuse: regenerating a
  report inside the 7-day edit window reuses the stored analysis instead of
  re-billing the API. Persistence failures are non-fatal.

Settings used (audit_platform/settings/base.py):
  ANTHROPIC_API_KEY     API key; empty disables the layer silently.
  AI_ANALYSIS_MODEL     Model name (default claude-sonnet-4-5).
  AI_ANALYSIS_ENABLED   Master switch (default True).
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

EVENT_TYPE = "ai_analysis_v2"  # v2: adds opinion_basis checklist evaluation
MAX_TOKENS_PER_SECTION = 1500
MAX_TOKENS_OPINION = 3000

# ---------------------------------------------------------------------------
# Prompts - one per report category. Edit freely; no code changes needed.
# Each prompt receives a JSON payload of that section's Q&A and scores.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are the analysis engine for the SRJ AI Audit Platform, writing the "
    "auditor's analysis inside a paid Tier 1 AI audit report for a small or "
    "mid-sized company. You write in plain, direct, professional English - "
    "the voice of an experienced auditor: factual, specific, no hype, no "
    "hedging filler. Base every statement ONLY on the data provided. Never "
    "invent facts, tools, numbers, or scores. Where the respondent answered "
    "\"Don't know\" or a response is missing, treat that itself as a finding "
    "about visibility. Do not issue or imply an audit opinion "
    "(qualified/unqualified) - the platform computes that separately.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences, no prose "
    "before or after, in exactly this shape:\n"
    "{\"narrative\": \"2-3 paragraph analysis as a single string\", "
    "\"key_findings\": [\"finding 1\", \"finding 2\", \"finding 3\"], "
    "\"recommendations\": [\"action 1\", \"action 2\"]}\n"
    "3-5 key_findings, 2-4 recommendations, each one sentence."
)

SECTION_PROMPTS = {
    "section1": (
        "Write the auditor's analysis for Section 1 - Audit Findings. Cover "
        "what the AI Tool Inventory, Fully Loaded Cost Map, and Shadow AI "
        "Surface data show about how well this company actually knows its "
        "own AI footprint; what the governance gaps mean in business terms; "
        "and what the Performative vs Operational comparison says about "
        "whether AI effort is producing work or producing appearances."
    ),
    "section2": (
        "Write the auditor's analysis for Section 2 - AI Readiness "
        "Scorecard. Interpret the composite readiness score and the six "
        "conditions (workflow readiness, data reliability, adoption "
        "pattern, governance, NEYR directional, Operational Leakage "
        "Factor directional). Explain what the weekly review-and-fix time "
        "signals imply for leakage, and which condition is the binding "
        "constraint on readiness."
    ),
    "section3": (
        "Write the auditor's analysis for Section 3 - AI Risk & Governance "
        "Review. Interpret the data exposure, decision influence, vendor "
        "risk, framework crosswalk, and per-use-case governance evidence. "
        "Name the sharpest risk concentration and what the maturity scores "
        "imply about the company's ability to absorb an AI incident."
    ),
    "section4": (
        "Write the auditor's analysis for Section 4 - AI Efficiency & "
        "Process Optimization. Interpret the Workflow Reality Map and AI "
        "Efficiency Tax evidence against the efficiency scorecard. Say "
        "where time and money are leaking, and what the 90-day plan items "
        "should accomplish if executed."
    ),
    "section5": (
        "Write the executive summary analysis for Section 5 - Summary of "
        "Findings. Synthesize across all four framework scores: the single "
        "most important strength, the single most important weakness, and "
        "the overall trajectory this posture puts the company on. Do NOT "
        "state an opinion kind - the platform prints the opinion "
        "separately. 2 paragraphs maximum."
    ),
}


OPINION_SYSTEM_PROMPT = (
    "You are the opinion-basis engine for the SRJ AI Audit Platform. You are "
    "given (a) the audit's 100-point qualified-opinion checklist across five "
    "research domains and (b) the respondent's complete answer set with "
    "framework scores. Identify which checklist conditions the evidence "
    "supports. Rules: cite a point ONLY when a specific answer affirmatively "
    "evidences the condition, or when a \"Don't know\" / unanswered response "
    "creates a scope limitation on that point. Quote or closely paraphrase "
    "the evidencing answer. Classify each exception as \"material\" (would "
    "reasonably prevent an unqualified opinion on its own or combined with "
    "related exceptions) or \"notable\" (worth reporting, not opinion-"
    "determinative). Report at most 12 exceptions, most material first. "
    "Separately list scope limitations (areas the audit could not assess "
    "because responses were missing or \"Don't know\"). Do not invent "
    "evidence.\n\n"
    "Also write opinion_statement: a formal two-sentence auditor's opinion "
    "in EXACTLY this structure - Sentence 1: 'In our opinion, except for "
    "the [summary of the material exception categories] detailed in the "
    "Basis for Qualified Opinion section, the audited AI [architecture/"
    "posture] provides [what the evidence supports it provides].' "
    "Sentence 2: 'However, until the noted deficiencies are reconciled "
    "through [the two or three most important remediations drawn from the "
    "exceptions], the current environment represents [a characterization "
    "of the residual risk] that prevents a full endorsement of sustainable "
    "AI maturity.' Ground every bracketed element in the actual exceptions "
    "found; do not copy the example wording verbatim.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences:\n"
    "{\"exceptions\": [{\"point\": 1, \"domain\": \"...\", \"finding\": "
    "\"one-sentence statement of the condition at this company\", "
    "\"evidence\": \"the answer(s) that evidence it\", \"materiality\": "
    "\"material\"}], \"scope_limitations\": [\"...\"], "
    "\"opinion_statement\": \"In our opinion, except for ...\"}"
)


# ---------------------------------------------------------------------------
# Payload slicing - keep each API call small and relevant
# ---------------------------------------------------------------------------

def _framework_summaries(context):
    out = []
    for f in context.get("frameworks", []):
        if f.get("error"):
            continue
        out.append({
            "framework": f["framework"].get("display_name"),
            "overall": f.get("overall"),
        })
    return out


def _section_payload(section_key, context):
    company = context.get("company") or {}
    base = {
        "company": {
            "industry": company.get("industry"),
            "size_bracket": company.get("size_bracket"),
        },
    }
    # Tool inventory discrepancy signal is relevant to Section 1 (governance
    # gaps / accountability), Section 3 (risk exposure), and the opinion
    # basis. Attach whenever available so the model can quote it.
    tis = context.get("tool_inventory_signal") or {}
    if tis and tis.get("flags"):
        base["tool_inventory_signal"] = {
            "inventory_count": tis.get("inventory_count"),
            "leadership_count": tis.get("leadership_count"),
            "personal_count": tis.get("personal_count"),
            "delta_vs_leadership": tis.get("delta_vs_leadership"),
            "delta_vs_personal": tis.get("delta_vs_personal"),
            "flags": tis.get("flags", []),
            "narrative": tis.get("narrative"),
        }
    if section_key == "section1":
        base.update({
            "artifacts": context.get("section1", []),
            "governance_gaps": (context.get("gap_analysis") or {}).get("gaps", []),
            "performative_vs_operational": context.get("perf_vs_op"),
            "policy_fields": context.get("policy_fields", []),
        })
    elif section_key == "section2":
        base.update({
            "composite": context.get("v2_overall"),
            "six_conditions": context.get("conditions", []),
            "neyr_olf_signals": context.get("neyr_olf_signals", []),
            "condition_narratives": context.get("condition_narratives", []),
        })
    elif section_key == "section3":
        base.update({
            "artifacts": context.get("section3", []),
            "maturity": context.get("maturity"),
        })
    elif section_key == "section4":
        base.update({
            "artifacts": context.get("section4", []),
            "efficiency_scorecard": context.get("eff_scorecard"),
            "ninety_day_plan": context.get("ninety_day", []),
        })
    elif section_key == "section5":
        base.update({
            "framework_scores": _framework_summaries(context),
            "governance_gaps": (context.get("gap_analysis") or {}).get("gaps", []),
            "efficiency_gaps": (context.get("eff_scorecard") or {}).get("gaps", []),
        })
    return base


# ---------------------------------------------------------------------------
# API call + JSON parsing
# ---------------------------------------------------------------------------

def _parse_json_object(text):
    """Parse the model reply; tolerate stray text around the JSON object."""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    if not isinstance(text, str):
        return None
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            return None
    return None


def _validate(parsed):
    if not isinstance(parsed, dict):
        return None
    narrative = parsed.get("narrative")
    if not narrative or not isinstance(narrative, str):
        return None
    return {
        "narrative": narrative.strip(),
        "key_findings": [str(x) for x in parsed.get("key_findings") or []][:5],
        "recommendations": [str(x) for x in parsed.get("recommendations") or []][:4],
    }


def _call_section(client, model, section_key, payload):
    prompt = (
        SECTION_PROMPTS[section_key]
        + "\n\nDATA:\n"
        + json.dumps(payload, default=str)
    )
    last_text = None
    for attempt in (1, 2):
        message = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS_PER_SECTION,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
            if attempt == 1
            else [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": last_text or ""},
                {"role": "user", "content":
                    "That was not valid JSON in the required shape. Respond "
                    "again with ONLY the JSON object, nothing else."},
            ],
        )
        last_text = "".join(
            b.text for b in message.content if getattr(b, "type", "") == "text"
        )
        result = _validate(_parse_json_object(last_text))
        if result is not None:
            return result
        logger.warning(
            "ai_analysis: %s attempt %d returned unparseable output",
            section_key, attempt,
        )
    return None


def _validate_opinion(parsed):
    if not isinstance(parsed, dict) or "exceptions" not in parsed:
        return None
    exceptions = []
    for e in (parsed.get("exceptions") or [])[:12]:
        if not isinstance(e, dict) or not e.get("finding"):
            continue
        exceptions.append({
            "point": e.get("point"),
            "domain": str(e.get("domain") or ""),
            "finding": str(e["finding"]),
            "evidence": str(e.get("evidence") or ""),
            "materiality": ("material"
                            if str(e.get("materiality", "")).lower() == "material"
                            else "notable"),
        })
    return {
        "exceptions": exceptions,
        "scope_limitations": [str(s) for s in parsed.get("scope_limitations") or []][:8],
        "opinion_statement": str(parsed.get("opinion_statement") or ""),
    }


def _call_opinion_basis(client, model, context):
    from reports.opinion_checklist import checklist_text
    payload = {
        "framework_scores": _framework_summaries(context),
        "all_questions_and_answers": context.get("appendix", []),
    }
    # Elevate tool-inventory discrepancy so the model considers it as a
    # candidate Basis exception. material_discrepancy in flags should
    # produce an exception in domain D2 (Tool Inventory & Discovery).
    tis = context.get("tool_inventory_signal") or {}
    if tis and tis.get("flags"):
        payload["tool_inventory_signal"] = {
            "inventory_count": tis.get("inventory_count"),
            "leadership_count": tis.get("leadership_count"),
            "personal_count": tis.get("personal_count"),
            "delta_vs_leadership": tis.get("delta_vs_leadership"),
            "delta_vs_personal": tis.get("delta_vs_personal"),
            "flags": tis.get("flags", []),
            "narrative": tis.get("narrative"),
            "guidance_for_model": (
                "If flags contain 'material_discrepancy', 'leadership_underestimate', "
                "or 'personal_use_exceeds_inventory', emit an exception in domain 'D2' "
                "with finding 'Tool inventory head-count discrepancy' and evidence "
                "quoting the specific delta from the narrative. Materiality = 'material' "
                "if the absolute delta is >= 3 tools, else 'notable'."
            ),
        }
    prompt = (
        "QUALIFIED-OPINION CHECKLIST (100 points):\n"
        + checklist_text()
        + "\n\nRESPONDENT DATA:\n"
        + json.dumps(payload, default=str)
    )
    last_text = None
    for attempt in (1, 2):
        message = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS_OPINION,
            system=OPINION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
            if attempt == 1
            else [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": last_text or ""},
                {"role": "user", "content":
                    "That was not valid JSON in the required shape. Respond "
                    "again with ONLY the JSON object, nothing else."},
            ],
        )
        last_text = "".join(
            b.text for b in message.content if getattr(b, "type", "") == "text"
        )
        result = _validate_opinion(_parse_json_object(last_text))
        if result is not None:
            return result
        logger.warning(
            "ai_analysis: opinion_basis attempt %d returned unparseable output",
            attempt,
        )
    return None


# ---------------------------------------------------------------------------
# Persistence (audit trail + reuse). Failures are non-fatal by design.
# ---------------------------------------------------------------------------

def _load_stored(engagement_id):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload FROM events
                WHERE event_type = %s
                  AND payload->>'engagement_id' = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                [EVENT_TYPE, str(engagement_id)],
            )
            row = cursor.fetchone()
        if not row:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        sections = payload.get("sections")
        if sections:
            logger.info("ai_analysis: reusing stored analysis for %s",
                        engagement_id)
            return sections
    except Exception:  # noqa: BLE001
        logger.exception("ai_analysis: stored-analysis lookup failed")
    return None


def _store(engagement_id, sections, model):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO events (event_type, payload) VALUES (%s, %s)",
                [EVENT_TYPE, json.dumps({
                    "engagement_id": str(engagement_id),
                    "model": model,
                    "sections": sections,
                })],
            )
    except Exception:  # noqa: BLE001
        logger.exception("ai_analysis: persist failed (non-fatal)")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_report(engagement_id, context):
    """Return {"section1": {...}, ..., "section5": {...}} or {} on failure.

    Each section value: {"narrative": str, "key_findings": [str],
    "recommendations": [str]}. Missing sections simply don't render.
    """
    if not getattr(settings, "AI_ANALYSIS_ENABLED", True):
        return {}
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.info("ai_analysis: no ANTHROPIC_API_KEY - skipping")
        return {}

    stored = _load_stored(engagement_id)
    if stored:
        return stored

    try:
        import anthropic
    except ImportError:
        logger.warning("ai_analysis: anthropic package not installed")
        return {}

    model = getattr(settings, "AI_ANALYSIS_MODEL", "claude-sonnet-4-5")
    client = anthropic.Anthropic(api_key=api_key)

    sections = {}
    for section_key in SECTION_PROMPTS:
        try:
            result = _call_section(
                client, model, section_key,
                _section_payload(section_key, context),
            )
            if result:
                sections[section_key] = result
        except Exception:  # noqa: BLE001
            logger.exception("ai_analysis: %s failed", section_key)

    # Opinion basis: evaluate answers against the 100-point checklist
    try:
        result = _call_opinion_basis(client, model, context)
        if result:
            sections["opinion_basis"] = result
    except Exception:  # noqa: BLE001
        logger.exception("ai_analysis: opinion_basis failed")

    if sections:
        _store(engagement_id, sections, model)
    return sections
