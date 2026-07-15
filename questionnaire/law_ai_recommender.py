"""AI (Claude Sonnet) law recommender for T1-A-006.

Given the company profile we already know (industry / size / geographic
footprint / revenue) + the canonical 59-law CSV catalog, ask Claude to
return which laws the company should track and one-line reasoning per
selection.

Public entry: ``ai_recommend_laws(profile, prior_selected=None) -> dict``.

Return shape:
    {
        "selected":   ["EU AI Act", "HIPAA and AI", ...],
        "reasoning":  {"EU AI Act": "Sells to EU customers.", ...},
        "summary":    "Two-sentence rationale for the overall recommendation.",
        "model":      "claude-sonnet-4-5",
        "ok":         True,
        "error":      None,
    }

Cached to the events table with event_type='law_ai_recommendation' keyed
by (respondent_id, profile hash) so re-clicks are free.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from django.conf import settings
from django.db import connection

from questionnaire.law_catalog import CATEGORIES as LAW_CATEGORIES


logger = logging.getLogger(__name__)

EVENT_TYPE = "law_ai_recommendation"
DEFAULT_MODEL = getattr(settings, "AI_ANALYSIS_MODEL", "claude-sonnet-4-5")
MAX_TOKENS = 2048

SYSTEM_PROMPT = """You are an AI governance analyst helping a company
identify which AI-relevant laws, regulations, and frameworks it must
track. You will be given (a) the company's profile and (b) the complete
canonical catalog of 59 laws/frameworks the SRJ AI Audit Platform
recognizes. For every law that is likely to apply to this company,
return the exact law_name string from the catalog and a single short
sentence explaining why it applies.

Rules:
- Include only laws from the provided catalog. Do NOT invent names.
- Include laws that apply even indirectly (e.g. via vendors, customers,
  or contracts) — err on the side of inclusion since respondents can
  uncheck later. Do not, however, include laws with no plausible link.
- Universal frameworks (NIST AI RMF, ISO/IEC 42001) apply to every
  company; always include them.
- Employer-scoped laws (Title VII, WARN Act, EEOC enforcement) apply
  once the company has any employees; err on the side of inclusion for
  any company with a size_bracket above the smallest.
- Sector-specific laws (HIPAA, GLBA, FERPA, FCRA, ECOA, FINRA) apply
  when the industry clearly matches — do NOT include for unrelated
  industries.
- Geographic laws (EU AI Act, state AI acts, NYC laws) apply only when
  the company's footprint clearly touches that jurisdiction.
- Do NOT flag more than ~25 laws unless the company profile clearly
  warrants it (rare).

Respond with a single JSON object, no prose outside it:
{
  "summary": "<two short sentences of overall reasoning>",
  "selected": ["law_name_1", "law_name_2", ...],
  "reasoning": {"law_name_1": "why it applies", ...}
}"""


def _catalog_for_prompt() -> list[dict]:
    """Flatten the CATEGORIES nested tuples into a compact prompt payload."""
    out = []
    for cat_name, items in LAW_CATEGORIES:
        for law_name, url in items:
            out.append({"name": law_name, "category": cat_name})
    return out


def _profile_hash(profile: dict) -> str:
    """Stable digest of the company profile so we can cache per shape."""
    serialized = json.dumps(profile, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _load_cached(respondent_id: str, profile_hash: str) -> Optional[dict]:
    """Return a prior AI recommendation if profile hasn't changed."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM events "
                "WHERE event_type = %s "
                "  AND payload->>'respondent_id' = %s "
                "  AND payload->>'profile_hash' = %s "
                "ORDER BY created_at DESC LIMIT 1",
                (EVENT_TYPE, str(respondent_id), profile_hash),
            )
            row = cursor.fetchone()
            if row:
                payload = row[0]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                return payload.get("result")
    except Exception:  # noqa: BLE001
        logger.exception("law_ai_recommender: cache read failed")
    return None


def _store_result(respondent_id: str, profile_hash: str, profile: dict, result: dict) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO events (id, event_type, payload) "
                "VALUES (gen_random_uuid(), %s, %s::jsonb)",
                [EVENT_TYPE, json.dumps({
                    "respondent_id": str(respondent_id),
                    "profile_hash": profile_hash,
                    "profile": profile,
                    "result": result,
                })],
            )
    except Exception:  # noqa: BLE001
        logger.exception("law_ai_recommender: cache write failed")


def _parse_json(text: str) -> Optional[dict]:
    """Tolerate stray text around the JSON body Sonnet returns."""
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
        except (ValueError, TypeError):
            return None
    return None


def _validate(parsed: Any) -> Optional[dict]:
    if not isinstance(parsed, dict):
        return None
    valid_names = {name for _, items in LAW_CATEGORIES for name, _ in items}
    selected_raw = parsed.get("selected") or []
    if not isinstance(selected_raw, list):
        selected_raw = []
    selected = [s for s in selected_raw if isinstance(s, str) and s in valid_names]
    reasoning_raw = parsed.get("reasoning") or {}
    if not isinstance(reasoning_raw, dict):
        reasoning_raw = {}
    reasoning = {k: str(v)[:400] for k, v in reasoning_raw.items() if k in selected}
    summary = str(parsed.get("summary") or "")[:1000]
    return {
        "selected": selected,
        "reasoning": reasoning,
        "summary": summary,
    }


def ai_recommend_laws(
    respondent_id: str,
    profile: dict,
    force_refresh: bool = False,
) -> dict:
    """Return AI-recommended laws for a respondent's company profile."""
    result_base = {
        "selected": [],
        "reasoning": {},
        "summary": "",
        "model": DEFAULT_MODEL,
        "ok": False,
        "error": None,
        "cached": False,
    }

    profile_hash = _profile_hash(profile)

    if not force_refresh:
        cached = _load_cached(respondent_id, profile_hash)
        if cached:
            cached_out = dict(result_base)
            cached_out.update(cached)
            cached_out["cached"] = True
            cached_out["ok"] = True
            return cached_out

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        result_base["error"] = "ANTHROPIC_API_KEY not configured"
        return result_base
    if not getattr(settings, "AI_ANALYSIS_ENABLED", True):
        result_base["error"] = "AI analysis disabled"
        return result_base

    try:
        import anthropic
    except ImportError:
        result_base["error"] = "anthropic package not installed"
        return result_base

    client = anthropic.Anthropic(api_key=api_key)

    payload = {
        "company_profile": profile,
        "law_catalog": _catalog_for_prompt(),
    }
    user_prompt = "COMPANY PROFILE + LAW CATALOG:\n" + json.dumps(payload, indent=2)

    try:
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(
            b.text for b in message.content if getattr(b, "type", "") == "text"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("law_ai_recommender: API call failed")
        result_base["error"] = f"{type(exc).__name__}: {exc}"[:400]
        return result_base

    parsed = _validate(_parse_json(text))
    if not parsed:
        result_base["error"] = "AI response could not be parsed"
        return result_base

    result_base.update(parsed)
    result_base["ok"] = True
    _store_result(respondent_id, profile_hash, profile, {
        "selected": parsed["selected"],
        "reasoning": parsed["reasoning"],
        "summary": parsed["summary"],
        "model": DEFAULT_MODEL,
    })
    return result_base
