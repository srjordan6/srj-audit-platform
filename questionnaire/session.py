"""Resume token helpers.

Django-signed tokens carrying a respondent_id, valid 30 days per
Part A §2.6. Prod uses SECRET_KEY from settings; tests configure
their own SECRET_KEY at import time.
"""

from __future__ import annotations

from typing import Optional

from django.core.signing import (
    BadSignature,
    SignatureExpired,
    TimestampSigner,
)


TOKEN_MAX_AGE_SECONDS = 30 * 24 * 3600  # 30 days per Part A §2.6


def make_resume_token(respondent_id: str) -> str:
    """Sign a respondent_id into a URL-safe timestamped token."""
    return TimestampSigner().sign(str(respondent_id))


def parse_resume_token(
    token: str,
    max_age_seconds: int = TOKEN_MAX_AGE_SECONDS,
) -> Optional[str]:
    """Return respondent_id if token is valid and unexpired, else None."""
    try:
        return TimestampSigner().unsign(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
