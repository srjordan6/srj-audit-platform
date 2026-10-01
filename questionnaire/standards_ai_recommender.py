"""AI suggestions for T1-A-011 voluntary standards (2026-10-01).

Runs on the questionnaire-time model (OLLAMA_MODEL, the flash model) when
the respondent reaches T1-A-011. Suggests the standards a company with
this profile is most likely to align with or be asked about by customers,
insurers or regulators, each with a one-line reason. Suggestions are
shown, not ticked: the question asks what the company actually aligns
with, and only the respondent knows that. Cached per respondent and
profile in events (standards_ai_recommendation); a failure falls back to
the rule-based suggestions in standards_catalog.LAW_SUGGESTS.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

from django.conf import settings
from django.db import connection

from questionnaire.standards_catalog import GROUPS, LAW_SUGGESTS, STANDARD_LABELS

logger = logging.getLogger(__name__)

EVENT_TYPE = "standards_ai_recommendation"
MAX_TOKENS = 1500

SYSTEM_PROMPT = (
    "You help a respondent to an AI governance audit answer one question: "
    "which voluntary AI, security, risk and data standards does the company "
    "align with or claim compliance to, including those required by customer "
    "contracts or insurance policies. From the company profile (industry, "
    "size, revenue, footprint, the laws and regulations it said it operates "
    "under) suggest the standards it is most likely to align with or be asked "
    "about. Choose ONLY from the catalog provided, using the exact labels. "
    "Suggest between 4 and 12, most relevant first. Do not suggest a standard "
    "the profile gives no reason for: a 20-person services firm with no "
    "federal contracts is not asked for CMMC or FedRAMP. Give each a reason "
    "of at most 18 words naming the fact in the profile that drives it.\n\n"
    "Respond with ONLY a JSON object, no prose:\n"
    "{\"summary\": \"one sentence\", \"suggested\": [\"label\", ...], "
    "\"reasons\": {\"label\": \"reason\", ...}}"
)


def _hash(profile: dict) -> str:
    return hashlib.sha256(json.dumps(profile, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _cached(respondent_id: str, h: str):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM events WHERE event_type = %s AND payload->>'respondent_id' = %s "
                "AND payload->>'profile_hash' = %s ORDER BY created_at DESC LIMIT 1",
                [EVENT_TYPE, str(respondent_id), h])
            row = cursor.fetchone()
        if row:
            p = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            return p.get("result")
    except Exception:  # noqa: BLE001
        logger.exception("standards suggest: cache read failed")
    return None


def _store(respondent_id: str, h: str, result: dict) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO events (event_type, payload) VALUES (%s, %s)",
                           [EVENT_TYPE, json.dumps({"respondent_id": str(respondent_id), "profile_hash": h, "result": result})])
    except Exception:  # noqa: BLE001
        logger.exception("standards suggest: cache write failed")


def rule_based(laws: list[str]) -> dict:
    out: list[str] = []
    reasons: dict[str, str] = {}
    for law in laws or []:
        for label in LAW_SUGGESTS.get(law, []):
            if label not in out:
                out.append(label)
                reasons[label] = f"Commonly expected of companies under {law.replace(' and AI', '')}."
    return {"suggested": out, "reasons": reasons, "summary": "", "source": "rules"}


def suggest_standards(respondent_id: str, profile: dict) -> dict:
    """{"suggested": [labels], "reasons": {label: reason}, "summary": str,
    "source": "ai" | "rules"}. Never raises."""
    fallback = rule_based(profile.get("laws") or [])
    if not getattr(settings, "AI_ANALYSIS_ENABLED", True):
        return fallback
    h = _hash(profile)
    hit = _cached(respondent_id, h)
    if hit:
        return hit
    try:
        provider = (os.environ.get("AI_ANALYSIS_PROVIDER") or "ollama").strip().lower()
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=getattr(settings, "ANTHROPIC_API_KEY", ""))
            model = getattr(settings, "AI_ANALYSIS_MODEL", "claude-sonnet-4-5")
        else:
            from reports.ai_analysis import OllamaClient
            client = OllamaClient(os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434",
                                  os.environ.get("OLLAMA_API_KEY", ""))
            model = os.environ.get("OLLAMA_MODEL") or "deepseek-v4.1-flash"
        prompt = "COMPANY PROFILE AND CATALOG:\n" + json.dumps(
            {"company_profile": profile, "catalog": [{"group": g, "labels": labels} for g, labels in GROUPS]})
        m = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
                                   messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        from reports.ai_analysis import _parse_json_object
        parsed = _parse_json_object(text) or {}
        suggested = [s for s in (parsed.get("suggested") or []) if s in STANDARD_LABELS][:12]
        if not suggested:
            return fallback
        reasons = {k: str(v)[:160] for k, v in (parsed.get("reasons") or {}).items() if k in suggested}
        result = {"suggested": suggested, "reasons": reasons,
                  "summary": str(parsed.get("summary") or "")[:300], "source": "ai", "model": model}
        _store(respondent_id, h, result)
        return result
    except Exception:  # noqa: BLE001
        logger.exception("standards suggest failed; using rules")
        return fallback
