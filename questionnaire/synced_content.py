"""DB-first loaders for WordPress-synced content, with catalog fallback.

The srj-audit-sync WordPress plugin keeps three Postgres tables current
(synced_glossary_terms, synced_tools, synced_laws). These loaders read
those tables and fall back to the shipped Python catalogs
(questionnaire.tool_catalog / questionnaire.law_catalog) whenever the
tables are empty or unreachable — so the questionnaire works identically
on a fresh database, in dev, or if a sync has never run.

Results are cached per-process for CACHE_SECONDS to avoid a DB round
trip on every question render. The cache is deliberately short: after a
WP sync lands, the questionnaire picks it up within a few minutes with
no deploy and no restart.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)

CACHE_SECONDS = 300
_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, loader):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    value = loader()
    _cache[key] = (now, value)
    return value


def _rows(sql: str, params=()) -> list[tuple]:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


# ---------------------------------------------------------------------------
# Tools — categories shape identical to tool_catalog.CATEGORIES:
#   [(category_name, [tool_name, ...]), ...]
# ---------------------------------------------------------------------------

def tool_categories() -> list[tuple[str, list[str]]]:
    def load():
        try:
            rows = _rows(
                "SELECT category, tool_name FROM synced_tools "
                "WHERE is_active = TRUE ORDER BY category, sort_order, tool_name"
            )
        except Exception:  # noqa: BLE001
            logger.exception("synced_tools read failed; using catalog")
            rows = []
        if len(rows) < 50:   # sanity floor — mirror content_sync GUARD_MIN
            from questionnaire.tool_catalog import CATEGORIES
            return CATEGORIES
        by: "OrderedDict[str, list[str]]" = OrderedDict()
        for cat, name in rows:
            by.setdefault(cat or "Other", []).append(name)
        return list(by.items())
    return _cached("tools", load)


# ---------------------------------------------------------------------------
# Laws — categories shape identical to law_catalog.CATEGORIES:
#   [(category_name, [(law_name, url), ...]), ...]
# ---------------------------------------------------------------------------

def law_categories() -> list[tuple[str, list[tuple[str, str]]]]:
    def load():
        try:
            rows = _rows(
                "SELECT category, law_name, url FROM synced_laws "
                "WHERE is_active = TRUE ORDER BY category, sort_order, law_name"
            )
        except Exception:  # noqa: BLE001
            logger.exception("synced_laws read failed; using catalog")
            rows = []
        if len(rows) < 20:
            from questionnaire.law_catalog import CATEGORIES
            return CATEGORIES
        by: "OrderedDict[str, list[tuple[str, str]]]" = OrderedDict()
        for cat, name, url in rows:
            by.setdefault(cat or "Other", []).append((name, url))
        return list(by.items())
    return _cached("laws", load)


def laws_flat() -> list[str]:
    return [name for _, items in law_categories() for name, _ in items]


# ---------------------------------------------------------------------------
# Glossary — {term: (definition, category)} for the vocabulary annotator.
# ---------------------------------------------------------------------------

GLOSSARY_URL = "https://srjconsultingservices.com/resources/ai-glossary/"

# Curation (locked with Stephen 2026-07-21): only underline terms that
# genuinely help a non-technical respondent. Multi-word technical terms
# and recognized acronyms qualify; single common English words do not —
# linking every occurrence of "Agent" or "Training" would turn the
# questionnaire into a sea of underlines.
_STOP_SINGLE_WORDS = {
    "agent", "agents", "model", "models", "training", "memory", "planner",
    "prompt", "token", "tool", "tools", "workflow", "pipeline", "inference",
    "context", "alignment", "evaluation", "benchmark", "temperature",
    "embedding", "checkpoint", "dataset", "weights", "scratchpad", "sandbox",
    "guardrail", "guardrails", "grounding", "reasoning", "latency",
}

_ACRONYM_ALLOW = {
    "llm", "rag", "hitl", "rlhf", "sft", "moe", "gpu", "tpu", "api",
    "agi", "asi", "ocr", "nlp", "cot", "kv",
}


def glossary_terms() -> dict[str, str]:
    """Return {term: definition} for annotatable glossary terms."""
    def load():
        try:
            rows = _rows(
                "SELECT term, definition FROM synced_glossary_terms "
                "WHERE is_active = TRUE"
            )
        except Exception:  # noqa: BLE001
            logger.exception("synced_glossary_terms read failed")
            rows = []
        out: dict[str, str] = {}
        for term, definition in rows:
            t = (term or "").strip()
            if not t:
                continue
            low = t.lower()
            words = low.split()
            if len(words) == 1:
                # Single word: allow only recognized acronyms / initialisms
                # (all-caps in source, or in the allow list) that aren't
                # common English.
                if low in _STOP_SINGLE_WORDS:
                    continue
                if not (t.isupper() or low in _ACRONYM_ALLOW):
                    continue
            out[t] = definition or ""
        return out
    return _cached("glossary", load)


def clear_cache() -> None:
    _cache.clear()
