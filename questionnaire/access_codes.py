"""Access-code (promo / tester comp) business logic.

Runtime model:
    access_codes rows are pre-issued by the operator (see the
    issue_access_code management command). Each row carries a max_uses
    counter and an expiration date. A row is "redeemable" when
    times_used < max_uses AND expires_at > now().

    A respondent enters the code on the /startaiaudit start form (or
    lands on the form pre-populated via ?code=<CODE>). validate_code
    resolves the code + confirms it's still redeemable. If it is, the
    caller creates the engagement, then calls redeem_code atomically:
    a single UPDATE ... WHERE times_used < max_uses AND expires_at > now()
    both increments the counter AND enforces the cap under concurrent
    submissions. If the UPDATE returns zero rows the code was exhausted
    in the meantime; the caller must undo the free-comping.

DB (public schema):
    access_codes(id, code, kind, percentage, label, notes, max_uses,
                 times_used, expires_at, created_by, created_at)
    access_code_redemptions(id, access_code_id, engagement_id,
                            respondent_email, redeemed_at)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AccessCode:
    """Row-shape mirror. All fields as returned by the SELECT below."""
    id: str
    code: str
    kind: str
    percentage: float
    label: Optional[str]
    max_uses: int
    times_used: int
    expires_at: datetime


def _normalize(code: str) -> str:
    """Codes are case-insensitive; trim whitespace defensively."""
    return (code or "").strip()


def validate_code(cursor, code: str) -> Optional[AccessCode]:
    """Return the AccessCode row if the code is currently redeemable, else None.

    Redeemable = exists AND times_used < max_uses AND expires_at > now().
    This is a READ; the atomic guard against exhaustion under concurrency
    lives in redeem_code().
    """
    normalized = _normalize(code)
    if not normalized:
        return None

    cursor.execute(
        """
        SELECT id, code, kind, percentage, label, max_uses, times_used, expires_at
          FROM access_codes
         WHERE LOWER(code) = LOWER(%s)
           AND times_used < max_uses
           AND expires_at > now()
         LIMIT 1
        """,
        (normalized,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return AccessCode(
        id=str(row[0]),
        code=row[1],
        kind=row[2],
        percentage=float(row[3]),
        label=row[4],
        max_uses=int(row[5]),
        times_used=int(row[6]),
        expires_at=row[7],
    )


def redeem_code(
    cursor,
    access_code_id: str,
    engagement_id: str,
    respondent_email: str,
) -> bool:
    """Atomically claim one use of the code for the given engagement.

    Returns True on success, False if the code was exhausted in the
    meantime (row-level race). Callers who get False must undo the free
    comping on the engagement (flip payment_status back to 'free',
    price_cents to the tier price).

    We do this in TWO statements inside the caller's transaction:
      1. UPDATE ... SET times_used = times_used + 1
         WHERE id = %s AND times_used < max_uses AND expires_at > now()
         RETURNING id
      2. If step 1 returned a row: INSERT into access_code_redemptions.
    """
    cursor.execute(
        """
        UPDATE access_codes
           SET times_used = times_used + 1
         WHERE id = %s
           AND times_used < max_uses
           AND expires_at > now()
         RETURNING id
        """,
        (access_code_id,),
    )
    updated = cursor.fetchone()
    if not updated:
        return False

    cursor.execute(
        """
        INSERT INTO access_code_redemptions
            (access_code_id, engagement_id, respondent_email)
        VALUES (%s, %s, %s)
        """,
        (access_code_id, engagement_id, respondent_email),
    )
    return True
