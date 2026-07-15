"""Bot-protection helpers for the public /startaiaudit/ endpoint.

Three layers, cheapest first:

1. Honeypot: hidden form field 'website'. Bots that blindly fill inputs
   trip this; real users never see it. `is_honeypot_hit()` returns True
   when the field has ANY value — the view should silently drop the
   request (fake-succeed).

2. Rate limit: 3 POSTs per IP per hour, backed by Django's cache
   (Redis in production per settings.RQ_QUEUES; LocMem in dev).
   `is_rate_limited()` returns True when the caller has exceeded the
   window.

3. Cloudflare Turnstile: server-side token verification against
   https://challenges.cloudflare.com/turnstile/v0/siteverify.
   `verify_turnstile()` returns True if the token is valid or if
   Turnstile isn't configured (env var missing) — the honeypot + rate
   limit still guard the endpoint in that case.

Environment variables:
    TURNSTILE_SITE_KEY   public site key (rendered in template)
    TURNSTILE_SECRET_KEY private secret (used server-side only)

Both empty = Turnstile disabled (dev-friendly).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

# ---------- Honeypot ---------------------------------------------------------

HONEYPOT_FIELD = "website"


def is_honeypot_hit(request) -> bool:
    """True if the hidden honeypot field has any content."""
    value = (request.POST.get(HONEYPOT_FIELD) or "").strip()
    return bool(value)


# ---------- Rate limit -------------------------------------------------------

_RATE_LIMIT_MAX = 3        # requests
_RATE_LIMIT_WINDOW = 3600  # seconds


def _client_ip(request) -> str:
    """Best-effort client IP; honors X-Forwarded-For behind Cloudflare."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def is_rate_limited(request, key_suffix: str = "start") -> bool:
    """Increment counter for this IP+endpoint; return True if over limit.

    Uses django.core.cache — Redis in prod, LocMem in dev. Silent fail
    (return False) if cache is misconfigured; the other layers still
    apply so we never block a legit user because of infra hiccups.
    """
    ip = _client_ip(request)
    cache_key = f"botproto:{key_suffix}:{ip}"
    try:
        current = cache.get(cache_key, 0)
        if current >= _RATE_LIMIT_MAX:
            return True
        # add=True is race-safe on Redis but LocMem doesn't support it;
        # follow the standard set-with-TTL pattern.
        if current == 0:
            cache.set(cache_key, 1, timeout=_RATE_LIMIT_WINDOW)
        else:
            cache.incr(cache_key)
    except Exception as exc:  # noqa: BLE001
        log.warning("rate_limit_cache_error", extra={"err": str(exc)})
        return False
    return False


# ---------- Cloudflare Turnstile --------------------------------------------

TURNSTILE_VERIFY_URL = (
    "https://challenges.cloudflare.com/turnstile/v0/siteverify"
)


def turnstile_configured() -> bool:
    return bool(getattr(settings, "TURNSTILE_SECRET_KEY", ""))


def turnstile_site_key() -> str:
    return getattr(settings, "TURNSTILE_SITE_KEY", "") or ""


def verify_turnstile(request, timeout_s: float = 5.0) -> bool:
    """Verify the cf-turnstile-response token against Cloudflare.

    Returns True if:
      - Turnstile isn't configured (env vars missing) — other layers apply.
      - Token is valid per Cloudflare.
    Returns False if configured but token missing/invalid/network-fail.
    """
    if not turnstile_configured():
        return True
    secret = settings.TURNSTILE_SECRET_KEY
    token = (request.POST.get("cf-turnstile-response") or "").strip()
    if not token:
        return False
    ip = _client_ip(request)
    started = time.time()
    try:
        resp = requests.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": secret, "response": token, "remoteip": ip},
            timeout=timeout_s,
        )
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "turnstile_verify_network_error",
            extra={"err": str(exc), "elapsed_ms": int((time.time() - started) * 1000)},
        )
        return False
    ok = bool(payload.get("success"))
    if not ok:
        log.info(
            "turnstile_verify_failed",
            extra={"codes": payload.get("error-codes"), "ip": ip},
        )
    return ok
