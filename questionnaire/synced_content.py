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

def _tool_short_name(raw: str) -> str:
    """Extract the display name from the WP page's verbose entry format.

    The tools page renders entries as
        "AI21 Labs API (AI21 Labs, Israel) — Jurassic models; enterprise..."
    and the plugin captures the whole line. Checkbox labels (and stored
    answer values, which must stay match-able across syncs) want just
    "AI21 Labs API". Split on the em/en dash first, then strip a
    trailing "(Vendor, HQ)" parenthetical — but ONLY a trailing one, so
    names like "v0 (Vercel)" from the shipped catalog stay intact when
    they arrive without a description.
    """
    name = raw.split(" — ")[0].split(" – ")[0].strip()
    # Strip a "(Vendor, HQ)" parenthetical only when a comma marks it as
    # a vendor/location pair; "v0 (Vercel)" and "DALL-E (OpenAI)" keep
    # their parens because they're part of the recognized product name.
    import re as _re
    m = _re.match(r"^(.*\S)\s+\(([^()]*,[^()]*)\)$", name)
    if m:
        name = m.group(1).strip()
    return name[:200]


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
        seen: set[str] = set()
        for cat, raw in rows:
            name = _tool_short_name(raw or "")
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            by.setdefault(cat or "Other", []).append(name)
        return list(by.items())
    return _cached("tools", load)


# ---------------------------------------------------------------------------
# Laws — categories shape identical to law_catalog.CATEGORIES:
#   [(category_name, [(law_name, url), ...]), ...]
#
# The WP hub-page harvest is anchor-based and inevitably noisy: it picks
# up in-copy links ("Read what changed", "four matter"), utility pages
# (AI Tools, Sources & References), and short-name duplicates ("NIS2"
# next to "NIS2 Directive"). Cleaning here rather than in the plugin
# means a plugin parser regression can never dirty the questionnaire.
# Categories come from the shipped catalog (the WP hub page carries no
# category markup per anchor); genuinely new laws land in a trailing
# "Recently Added" bucket until the catalog is regenerated.
# ---------------------------------------------------------------------------

_LAW_JUNK_EXACT = {
    "ai tools", "ai tools catalog", "sources & references", "sources",
    "four matter", "home", "read more", "learn more",
}
_LAW_JUNK_PREFIXES = ("read ", "see ", "learn ", "explore ")

# Pages that are navigation/utility rather than laws.
_LAW_JUNK_URL_PARTS = ("/ai-tools", "/sources")


def _law_is_junk(name: str, url: str) -> bool:
    low = name.lower().strip()
    if low in _LAW_JUNK_EXACT:
        return True
    if low.startswith(_LAW_JUNK_PREFIXES):
        return True
    return any(p in (url or "") for p in _LAW_JUNK_URL_PARTS)


def law_categories() -> list[tuple[str, list[tuple[str, str]]]]:
    def load():
        try:
            rows = _rows(
                "SELECT law_name, url FROM synced_laws "
                "WHERE is_active = TRUE ORDER BY sort_order, law_name"
            )
        except Exception:  # noqa: BLE001
            logger.exception("synced_laws read failed; using catalog")
            rows = []

        from questionnaire.law_catalog import CATEGORIES as CATALOG

        # Clean + dedupe: drop junk anchors, then keep the LONGEST name
        # per URL so "NIS2 Directive" beats "NIS2".
        by_url: dict[str, str] = {}
        for name, url in rows:
            name = (name or "").strip()
            if not name or _law_is_junk(name, url):
                continue
            key = (url or name).rstrip("/")
            if key not in by_url or len(name) > len(by_url[key]):
                by_url[key] = name
        synced = {v: k for k, v in by_url.items()}   # name -> url

        if len(synced) < 20:
            return CATALOG

        # Rebuild in catalog category order; anything the WP page has
        # that the catalog doesn't know goes into "Recently Added".
        out: list[tuple[str, list[tuple[str, str]]]] = []
        seen: set[str] = set()
        for cat_name, items in CATALOG:
            keep = []
            for law_name, cat_url in items:
                if law_name in synced:
                    keep.append((law_name, synced[law_name] or cat_url))
                    seen.add(law_name)
            if keep:
                out.append((cat_name, keep))
        extras = [(n, u) for n, u in sorted(synced.items()) if n not in seen]
        if extras:
            out.append(("Recently Added", extras))
        return out
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
