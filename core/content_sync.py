"""Receiving endpoint for the WordPress content sync.

The srj-audit-sync WordPress plugin (on srjconsultingservices.com) POSTs
a JSON payload of the three content sources on a weekly WP-Cron schedule
or via the wp-admin "Sync Now" button:

    {
      "generated_at": "...", "source": "https://srjconsultingservices.com",
      "glossary": [{"term","definition","example","category"}, ...],
      "tools":    [{"tool_name","category","sort_order"}, ...],
      "laws":     [{"law_name","url","sort_order"}, ...]
    }

Auth: HMAC-SHA256 of the raw body with the shared secret
settings.CONTENT_SYNC_SECRET, sent as X-SRJ-Signature. Constant-time
comparison; missing/blank server secret disables the endpoint (403).

Upsert semantics per table:
  - present in payload  -> insert or update, is_active=TRUE
  - absent from payload -> is_active=FALSE (soft delete; nothing is ever
    hard-deleted so a bad parse on the WP side can't destroy data)

A sanity floor guards each dataset: if the payload contains fewer than
GUARD_MIN items for a dataset, that dataset is SKIPPED (not deactivated)
and flagged in the response — this stops a WP theme change that breaks
the parser from wiping the questionnaire's options.

Every sync writes an events row (event_type='content_sync') with a diff.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

GUARD_MIN = {"glossary": 100, "tools": 50, "laws": 20}


def _verify(request) -> bool:
    secret = getattr(settings, "CONTENT_SYNC_SECRET", "")
    if not secret:
        return False
    provided = request.headers.get("X-SRJ-Signature", "")
    expected = hmac.new(secret.encode(), request.body,
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, expected)


def _upsert_glossary(cursor, items: list[dict]) -> dict:
    names = []
    for it in items:
        term = (it.get("term") or "").strip()[:200]
        if not term:
            continue
        names.append(term)
        cursor.execute(
            """
            INSERT INTO synced_glossary_terms
                (term, definition, example, category, is_active, synced_at)
            VALUES (%s, %s, %s, %s, TRUE, NOW())
            ON CONFLICT (term) DO UPDATE SET
                definition = EXCLUDED.definition,
                example    = EXCLUDED.example,
                category   = EXCLUDED.category,
                is_active  = TRUE,
                synced_at  = NOW()
            """,
            (term, (it.get("definition") or "")[:2000],
             (it.get("example") or "")[:1000],
             (it.get("category") or "")[:120]),
        )
    cursor.execute(
        "UPDATE synced_glossary_terms SET is_active = FALSE "
        "WHERE is_active = TRUE AND NOT (term = ANY(%s))",
        (names,),
    )
    deactivated = cursor.rowcount
    return {"upserted": len(names), "deactivated": deactivated}


def _upsert_tools(cursor, items: list[dict]) -> dict:
    names = []
    for it in items:
        name = (it.get("tool_name") or "").strip()[:200]
        if not name:
            continue
        names.append(name)
        cursor.execute(
            """
            INSERT INTO synced_tools
                (tool_name, category, vendor, vendor_hq, governance_notes,
                 sort_order, is_active, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
            ON CONFLICT (tool_name) DO UPDATE SET
                category   = EXCLUDED.category,
                sort_order = EXCLUDED.sort_order,
                is_active  = TRUE,
                synced_at  = NOW()
            """,
            (name, (it.get("category") or "")[:160],
             (it.get("vendor") or "")[:160],
             (it.get("vendor_hq") or "")[:80],
             (it.get("governance_notes") or ""),
             int(it.get("sort_order") or 0)),
        )
    cursor.execute(
        "UPDATE synced_tools SET is_active = FALSE "
        "WHERE is_active = TRUE AND NOT (tool_name = ANY(%s))",
        (names,),
    )
    return {"upserted": len(names), "deactivated": cursor.rowcount}


def _upsert_laws(cursor, items: list[dict]) -> dict:
    names = []
    for it in items:
        name = (it.get("law_name") or "").strip()[:200]
        if not name:
            continue
        names.append(name)
        cursor.execute(
            """
            INSERT INTO synced_laws
                (law_name, category, url, sort_order, is_active, synced_at)
            VALUES (%s, %s, %s, %s, TRUE, NOW())
            ON CONFLICT (law_name) DO UPDATE SET
                category   = EXCLUDED.category,
                url        = EXCLUDED.url,
                sort_order = EXCLUDED.sort_order,
                is_active  = TRUE,
                synced_at  = NOW()
            """,
            (name, (it.get("category") or "")[:160],
             (it.get("url") or "")[:500],
             int(it.get("sort_order") or 0)),
        )
    cursor.execute(
        "UPDATE synced_laws SET is_active = FALSE "
        "WHERE is_active = TRUE AND NOT (law_name = ANY(%s))",
        (names,),
    )
    return {"upserted": len(names), "deactivated": cursor.rowcount}


@csrf_exempt
@require_http_methods(["POST"])
def content_sync_view(request):
    if not _verify(request):
        logger.warning("content_sync: signature verification failed")
        return HttpResponseForbidden("invalid signature")

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    results: dict = {}
    skipped: list[str] = []

    with transaction.atomic():
        with connection.cursor() as cursor:
            for key, fn in (("glossary", _upsert_glossary),
                            ("tools", _upsert_tools),
                            ("laws", _upsert_laws)):
                items = payload.get(key) or []
                if len(items) < GUARD_MIN[key]:
                    skipped.append(f"{key} ({len(items)} < {GUARD_MIN[key]} floor)")
                    continue
                results[key] = fn(cursor, items)

            cursor.execute(
                "INSERT INTO events (event_type, payload) VALUES (%s, %s)",
                ("content_sync", json.dumps({
                    "source": payload.get("source"),
                    "generated_at": payload.get("generated_at"),
                    "results": results,
                    "skipped": skipped,
                })),
            )

    # New content is live — drop the in-process loader caches so the
    # questionnaire picks it up on the next render instead of waiting
    # out the 5-minute TTL.
    try:
        from questionnaire.synced_content import clear_cache
        clear_cache()
    except Exception:  # noqa: BLE001
        pass

    return JsonResponse({"ok": True, "results": results, "skipped": skipped})
