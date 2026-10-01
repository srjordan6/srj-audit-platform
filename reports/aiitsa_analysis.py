"""Auditor's analysis and opinion for the AI IT Security Audit(TM) report.

Same discipline as reports.ai_analysis (Pillar I): the model writes from
the scored data only, never issues the opinion itself, and every result is
stored once per engagement in events (aiitsa_analysis_v1) for audit
trail and reuse. Runs on the report model (OLLAMA_MODEL_REPORT) through
the OllamaClient in reports.ai_analysis.

Sections
  summary      Page 1: what the Baseline, the Visibility Triangle and the
               weakest areas say about this company's AI security posture.
  remediation  Page 2: how to read the gap-to-standard table and what to
               do first, in the method's fixed order.
  crosswalk    Page 3: which external obligations the gaps touch.
  baseline     Page 4: what the dated score means and what moves it.
  opinion      Page 5: exceptions, scope limitations, formal statement.

Opinion rule (platform-computed, not the model's): qualified when any
area is Absent, the Baseline is below 50, or the unknown zone is 25% or
more; otherwise unqualified. Material exceptions from the model also
qualify.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from django.conf import settings
from django.db import connection

from reports.ai_analysis import (OllamaClient, _is_hard_stop, _is_hard_stop_text,
                                 _parse_json_object, _record_failure)

logger = logging.getLogger(__name__)

EVENT_TYPE = "aiitsa_analysis_v1"
MAX_TOKENS_SECTION = 1500
MAX_TOKENS_OPINION = 3000

SYSTEM_PROMPT = (
    "You are the analysis engine for the SRJ AI Audit Platform, writing the "
    "auditor's analysis inside a paid AI IT Security Audit report for a small "
    "or mid-sized company. The audit scores seven areas of the Defensible AI "
    "Security Baseline (Inventory, Access, Data, Vendors, Incidents, "
    "Governance, Evidence) on four levels (Absent, Partial, Defensible, "
    "Mature); self-reported answers cap every area at Partial until an "
    "artefact is verified. \"Don't know\" is reported as unknown-zone "
    "exposure. You write in plain, direct, professional English, the voice of "
    "an experienced security auditor: factual, specific, no hype, no hedging "
    "filler. Base every statement ONLY on the data provided and cite the "
    "question ids (for example AIITSA-DAT-004) that evidence a finding. Never "
    "invent facts, tools, numbers or scores. Do not issue or imply an audit "
    "opinion; the platform computes that separately.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences, no prose "
    "before or after, in exactly this shape:\n"
    "{\"narrative\": \"2-3 paragraph analysis as a single string\", "
    "\"key_findings\": [\"finding 1\", \"finding 2\", \"finding 3\"], "
    "\"recommendations\": [\"action 1\", \"action 2\"]}\n"
    "3-5 key_findings and 2-4 recommendations, each one sentence, each "
    "naming the area and the question id(s) it rests on."
)

SECTION_PROMPTS = {
    "summary": (
        "Write the auditor's analysis for page 1, Executive Summary. Say what "
        "the dated Baseline Score and level mean for this company, what the "
        "Visibility Triangle shows (which domains are known, suspected, clear "
        "or in the unknown zone), and what the three weakest areas have in "
        "common. Name the single most consequential exposure first."
    ),
    "remediation": (
        "Write the auditor's analysis for page 2, Remediation Roadmap. For "
        "the weakest areas, say what the minimum defensible standard requires "
        "and what the answered questions show is missing. Order the actions "
        "the way the method's 90-day roadmap orders them (mandate and "
        "coalition, then discovery and inventory, then identities and agent "
        "boundaries, then testing, vendors, data flows and incident "
        "rehearsal, then assembly). Do not reorder the roadmap."
    ),
    "crosswalk": (
        "Write the auditor's analysis for page 3, Framework Crosswalk. Using "
        "only the crosswalk rows provided, say which external obligations and "
        "frameworks the company's gaps most directly touch, and which single "
        "artefact would satisfy the most of them at once. Frameworks are "
        "references, not certifications; say so once."
    ),
    "baseline": (
        "Write the auditor's analysis for page 4, Baseline Score. Explain what "
        "the dated score measures, why every level is capped at Partial in a "
        "self-reported audit, which areas would move the score most if their "
        "artefact were produced and verified, and what a re-assessment in 90 "
        "days should be expected to show if the roadmap is followed."
    ),
}

OPINION_SYSTEM_PROMPT = (
    "You are the opinion-basis engine for the SRJ AI Audit Platform's AI IT "
    "Security Audit. You are given the company's scored answer set across "
    "seven Baseline areas, the minimum defensible standard for each, the "
    "Visibility Triangle zones, and every question answered No or Don't "
    "know with its text. Identify the exceptions the evidence supports. "
    "Rules: cite an exception ONLY when specific answers affirmatively "
    "evidence it, naming the question ids; treat a Don't know or unanswered "
    "question as a scope limitation, not a finding, unless the unknown "
    "itself is the exposure (a company that cannot say whether its agents "
    "hold production credentials has an exposure, not a gap in the audit). "
    "Classify each exception as \"material\" (would reasonably prevent an "
    "unqualified opinion on its own or with related exceptions) or "
    "\"notable\". Report at most 12 exceptions, most material first. "
    "Separately list scope limitations. Do not invent evidence.\n\n"
    "Also write opinion_statement: a formal two-sentence auditor's opinion "
    "in EXACTLY this structure. Sentence 1: 'In our opinion, except for the "
    "[summary of the material exception areas] detailed in the Basis for "
    "Qualified Opinion section, the company's AI security posture provides "
    "[what the evidence supports it provides].' Sentence 2: 'However, until "
    "the noted deficiencies are reconciled through [the two or three most "
    "important remediations drawn from the exceptions], the current "
    "environment represents [a characterization of the residual risk] that "
    "prevents a full endorsement of a defensible AI security baseline.' "
    "Ground every bracketed element in the actual exceptions; do not copy "
    "the example wording verbatim. If there are no material exceptions, "
    "write an unqualified two-sentence opinion in the same register.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences:\n"
    "{\"exceptions\": [{\"area\": \"Data\", \"finding\": \"one-sentence statement "
    "of the condition at this company\", \"evidence\": \"question ids and the "
    "answers that evidence it\", \"materiality\": \"material\"}], "
    "\"scope_limitations\": [\"...\"], \"opinion_statement\": \"In our opinion, "
    "...\"}"
)


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

def _area_rows(ctx: dict) -> list[dict]:
    return [{"area": a["area"], "score_0_100": a["score"], "level": a["level_label"], "capped": a["capped"],
             "answered": a["answered"], "expected": a["expected"], "dont_know": a["dont_know"],
             "gap_count": a["gap_count"], "minimum_standard": a["standard"],
             "gaps": [{"id": g["id"], "question": g["text"], "answer": g["answer"]} for g in a["gaps"]]}
            for a in ctx["areas"]]


def _payload(section_key: str, ctx: dict) -> dict:
    base = {
        "company": {k: ctx["company"].get(k) for k in ("name", "industry", "size_bracket")},
        "assessed_on": ctx["assessed_on"].isoformat(),
        "respondent_count": ctx["respondent_count"],
        "baseline": ctx["baseline"],
        "weakest_areas": [w["area"] for w in ctx["weakest"]],
    }
    if section_key in ("summary", "opinion"):
        base["visibility_triangle"] = [{"domain": v["domain"], "question": v["question"], "answer": v["answer"], "zone": v["zone"]}
                                       for v in ctx["visibility"]]
        base["areas"] = _area_rows(ctx)
        if ctx.get("divergence"):
            base["leadership_vs_workforce"] = ctx["divergence"]["rows"]
    elif section_key == "remediation":
        base["areas"] = _area_rows(ctx)
        base["roadmap_90_day"] = [{"when": w, "workstream": s} for w, s in ctx["roadmap"]]
    elif section_key == "crosswalk":
        base["areas"] = [{"area": a["area"], "score_0_100": a["score"], "level": a["level_label"], "gap_count": a["gap_count"]} for a in ctx["areas"]]
        base["crosswalk"] = [{"area": r[0], "ai_specific": r[1], "management_systems": r[2], "threat_and_assurance": r[3], "regulatory": r[4]} for r in ctx["crosswalk"]]
    elif section_key == "baseline":
        base["areas"] = [{"area": a["area"], "score_0_100": a["score"], "level": a["level_label"], "capped": a["capped"], "answered": a["answered"], "dont_know": a["dont_know"], "minimum_standard": a["standard"]} for a in ctx["areas"]]
        base["history"] = [{"date": h["date"].isoformat(), "score": h["score"]} for h in ctx["history"]]
    if section_key == "opinion":
        base["all_gaps"] = [{"id": r["qid"], "area": r["area"], "domain": r["domain"], "question": r["question"], "answer": r["answer"]}
                            for r in ctx["appendix"] if r["answer"] and r["answer"].split(";")[0].strip().split(":")[-1].strip() in ("No", "Don't know", "not answered")]
    return base


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------

def _validate_section(parsed):
    if not isinstance(parsed, dict) or not parsed.get("narrative"):
        return None
    return {
        "narrative": str(parsed["narrative"]),
        "key_findings": [str(x) for x in (parsed.get("key_findings") or [])][:5],
        "recommendations": [str(x) for x in (parsed.get("recommendations") or [])][:4],
    }


def _validate_opinion(parsed):
    if not isinstance(parsed, dict) or "exceptions" not in parsed:
        return None
    exceptions = []
    for e in (parsed.get("exceptions") or [])[:12]:
        if not isinstance(e, dict) or not e.get("finding"):
            continue
        exceptions.append({
            "area": str(e.get("area") or ""), "finding": str(e["finding"]),
            "evidence": str(e.get("evidence") or ""),
            "materiality": ("material" if str(e.get("materiality", "")).lower() == "material" else "notable"),
        })
    return {"exceptions": exceptions,
            "scope_limitations": [str(s) for s in parsed.get("scope_limitations") or []][:8],
            "opinion_statement": str(parsed.get("opinion_statement") or "")}


def _chat(client, model, system, prompt, max_tokens, validator):
    last = None
    for attempt in (1, 2):
        msgs = [{"role": "user", "content": prompt}] if attempt == 1 else [
            {"role": "user", "content": prompt}, {"role": "assistant", "content": last or ""},
            {"role": "user", "content": "That was not valid JSON in the required shape. Respond again with ONLY the JSON object, nothing else."}]
        m = client.messages.create(model=model, max_tokens=max_tokens, system=system, messages=msgs)
        last = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        out = validator(_parse_json_object(last))
        if out is not None:
            return out
    return None


# ---------------------------------------------------------------------------
# Opinion (platform rule + model exceptions)
# ---------------------------------------------------------------------------

def build_opinion(ctx: dict, basis: dict | None) -> dict:
    drivers = []
    b = ctx["baseline"]
    if b["answered"] == 0:
        drivers.append("No answers were recorded, so no opinion can be expressed.")
    absent = [a["area"] for a in ctx["areas"] if a["answered"] and a["level_label"] == "Absent"]
    if absent:
        drivers.append("Absent level in " + ", ".join(absent) + ".")
    if b["answered"] and b["score"] < 50:
        drivers.append(f"Baseline Score {b['score']:.0f} of 100 is below the 50-point qualification threshold.")
    if b["unknown_zone_pct"] >= 25:
        drivers.append(f"Unknown-zone exposure of {b['unknown_zone_pct']}% of answers, at or above the 25% material-uncertainty threshold.")
    unknown = [v["domain"] for v in ctx["visibility"] if v["zone"] == "unknown"]
    if unknown:
        drivers.append("Visibility Triangle unknown zone in " + ", ".join(unknown) + ".")
    exceptions = (basis or {}).get("exceptions") or []
    material = [e for e in exceptions if e["materiality"] == "material"]
    kind = "qualified" if (drivers or material) else "unqualified"
    if b["answered"] == 0:
        kind = "disclaimer"
    return {"kind": kind, "drivers": drivers, "exceptions": exceptions,
            "scope_limitations": (basis or {}).get("scope_limitations") or [],
            "statement": (basis or {}).get("opinion_statement") or ""}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_stored(engagement_id):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM events WHERE event_type = %s AND payload->>'engagement_id' = %s "
                "ORDER BY created_at DESC LIMIT 1", [EVENT_TYPE, str(engagement_id)])
            row = cursor.fetchone()
        if not row:
            return None
        from core.dbjson import loads_maybe
        payload = loads_maybe(row[0]) or {}
        return payload.get("sections") or None
    except Exception:  # noqa: BLE001
        logger.exception("aiitsa_analysis: load failed")
        return None


def _store(engagement_id, sections, model):
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO events (event_type, payload) VALUES (%s, %s)",
                           [EVENT_TYPE, json.dumps({"engagement_id": str(engagement_id), "model": model, "sections": sections})])
    except Exception:  # noqa: BLE001
        logger.exception("aiitsa_analysis: store failed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def analyze_aiitsa(engagement_id, ctx: dict) -> dict[str, Any]:
    """Return {summary, remediation, crosswalk, baseline, opinion_basis} or
    whatever subset succeeded; {} when the layer is off or unreachable."""
    if not getattr(settings, "AI_ANALYSIS_ENABLED", True):
        return {}
    stored = _load_stored(engagement_id)
    if stored:
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

    sections: dict[str, Any] = {}
    failures = []
    for key, instruction in SECTION_PROMPTS.items():
        try:
            prompt = instruction + "\n\nDATA:\n" + json.dumps(_payload(key, ctx), default=str)
            out = _chat(client, model, SYSTEM_PROMPT, prompt, MAX_TOKENS_SECTION, _validate_section)
            if out:
                sections[key] = out
        except Exception as exc:  # noqa: BLE001
            logger.exception("aiitsa_analysis: %s failed", key)
            failures.append((key, str(exc)[:300]))
            if _is_hard_stop(exc):
                break
    if not any(_is_hard_stop_text(f[1]) for f in failures):
        try:
            prompt = "COMPANY DATA:\n" + json.dumps(_payload("opinion", ctx), default=str)
            out = _chat(client, model, OPINION_SYSTEM_PROMPT, prompt, MAX_TOKENS_OPINION, _validate_opinion)
            if out:
                sections["opinion_basis"] = out
        except Exception as exc:  # noqa: BLE001
            logger.exception("aiitsa_analysis: opinion failed")
            failures.append(("opinion_basis", str(exc)[:300]))
    if failures:
        _record_failure(engagement_id, model, failures, len(sections))
    if sections:
        _store(engagement_id, sections, model)
    return sections
