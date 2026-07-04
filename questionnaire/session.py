"""Resume token helpers.

HMAC-SHA256 signed tokens carrying respondent_id + timestamp. Valid 30
days per Part A §2.6. Keyed from Django settings.SECRET_KEY when
configured, else RESUME_TOKEN_KEY env var (for standalone tests).

Format: b64u(payload) + "." + b64u(mac)
where payload = f"{ts}:{respondent_id}".encode()
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from typing import Optional


TOKEN_MAX_AGE_SECONDS = 30 * 24 * 3600


def _get_key() -> bytes:
    try:
        from django.conf import settings
        if settings.configured and getattr(settings, "SECRET_KEY", None):
            return settings.SECRET_KEY.encode()
    except Exception:
        pass
    return os.environ.get("RESUME_TOKEN_KEY", "insecure-dev-key").encode()


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_resume_token(respondent_id: str) -> str:
    ts = str(int(time.time()))
    payload = f"{ts}:{respondent_id}".encode()
    mac = hmac.new(_get_key(), payload, hashlib.sha256).digest()
    return f"{_b64u_encode(payload)}.{_b64u_encode(mac)}"


def parse_resume_token(
    token: str,
    max_age_seconds: int = TOKEN_MAX_AGE_SECONDS,
) -> Optional[str]:
    try:
        payload_b64, mac_b64 = token.split(".", 1)
        payload = _b64u_decode(payload_b64)
        mac_provided = _b64u_decode(mac_b64)
    except Exception:
        return None
    mac_expected = hmac.new(_get_key(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(mac_provided, mac_expected):
        return None
    try:
        ts_str, respondent_id = payload.decode().split(":", 1)
        ts = int(ts_str)
    except (ValueError, UnicodeDecodeError):
        return None
    if time.time() - ts > max_age_seconds:
        return None
    return respondent_id