"""Service layer for questionnaire orchestration.

Pure functions that combine flow.py logic with DB access via a cursor
parameter. Views are thin wrappers over these. Testable with mocked
cursors — no Django settings required for unit tests.

All DB access uses parameterized queries; no ORM. Callers are responsible
for wrapping multi-statement operations in a transaction.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from questionnaire import flow


# ---------------------------------------------------------------------------
# Response persistence (PR 6)
# ---------------------------------------------------------------------------


def load_answered_by_id(cursor, respondent_id: str) -> dict[str, Any]:
    """Return {question_id: answer_value} for every response by this respondent."""
    cursor.execute(
        "SELECT question_id, answer_value FROM responses "
        "WHERE respondent_id = %s",
        (respondent_id,),
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_respondent_role(cursor, respondent_id: str) -> Optional[str]:
    """Return the role string for this respondent, or None if not found."""
    cursor.execute(
        "SELECT role FROM respondents WHERE id = %s",
        (respondent_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return row[0]


def save_response(
    cursor,
    respondent_id: str,
    question_id: str,
    answer_value: dict,
    is_dont_know: bool = False,
) -> None:
    """Upsert a response row.

    UNIQUE(respondent_id, question_id) means re-answering the same
    question updates the existing row rather than creating a duplicate.
    """
    cursor.execute(
        """
        INSERT INTO responses
            (respondent_id, question_id, answer_value, is_dont_know)
        VALUES (%s, %s, %s::jsonb, %s)
        ON CONFLICT (respondent_id, question_id)
        DO UPDATE SET
            answer_value = EXCLUDED.answer_value,
            is_dont_know = EXCLUDED.is_dont_know,
            answered_at = NOW()
        """,
        (respondent_id, question_id, json.dumps(answer_value), is_dont_know),
    )


def get_next_question_context(
    cursor,
    respondent_id: str,
) -> Optional[dict]:
    """Return context for rendering next question, or None if done.

    Returns:
        {
            "question": SimpleNamespace,
            "partial": str,
            "progress": (int, int, float),
            "role": str,
        }
        or None if respondent unknown OR all visible questions answered.
    """
    role = get_respondent_role(cursor, respondent_id)
    if role is None:
        return None
    answered = load_answered_by_id(cursor, respondent_id)
    q = flow.next_unanswered_question(role, answered)
    if q is None:
        return None
    return {
        "question": q,
        "partial": flow.partial_template_for_type(q.question_type),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
    }


# ---------------------------------------------------------------------------
# Engagement bootstrap (PR 7)
# ---------------------------------------------------------------------------


def create_engagement_and_respondent(
    cursor,
    email: str,
    name: str,
    role: str,
    company_name: str,
    company_industry: str,
    company_size_bracket: str,
) -> str:
    """Create or find company + user, then create engagement + respondent.

    Returns the new respondent_id (str UUID). Caller is responsible for
    wrapping in a transaction — this function issues up to 5 statements.

    Company match is exact-name; user match is exact-email. Duplicates by
    slight variations (extra spaces, casing) create new rows. Enhance later
    if needed.
    """
    # Company: find or create
    cursor.execute(
        "SELECT id FROM companies WHERE name = %s LIMIT 1",
        (company_name,),
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            "INSERT INTO companies (name, industry, size_bracket) "
            "VALUES (%s, %s, %s) RETURNING id",
            (company_name, company_industry, company_size_bracket),
        )
        row = cursor.fetchone()
    company_id = row[0]

    # User: find or create (Tier 1 anonymous-then-claimed per Part A §2.6)
    cursor.execute(
        "SELECT id FROM users WHERE email = %s LIMIT 1",
        (email,),
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            "INSERT INTO users (email, name, company_id, is_active) "
            "VALUES (%s, %s, %s, TRUE) RETURNING id",
            (email, name, company_id),
        )
        row = cursor.fetchone()
    user_id = row[0]

    # Engagement: always new (each Tier 1 purchase = new snapshot per OD-18)
    cursor.execute(
        "INSERT INTO engagements "
        "(company_id, buyer_user_id, tier, status, payment_status, price_cents) "
        "VALUES (%s, %s, 'tier_1', 'in_progress', 'free', 0) RETURNING id",
        (company_id, user_id),
    )
    engagement_id = cursor.fetchone()[0]

    # Respondent: for Tier 1, one respondent per engagement (Decision 7-5)
    cursor.execute(
        "INSERT INTO respondents "
        "(engagement_id, user_id, email, name, role) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (engagement_id, user_id, email, name, role),
    )
    respondent_id = cursor.fetchone()[0]

    return str(respondent_id)


def sign_attestation(
    cursor,
    respondent_id: str,
    attestation_text: str,
) -> None:
    """Record attestation timestamp and text version on the respondent row."""
    cursor.execute(
        "UPDATE respondents "
        "SET attestation_signed_at = NOW(), attestation_text = %s "
        "WHERE id = %s",
        (attestation_text, respondent_id),
    )


def is_attestation_signed(cursor, respondent_id: str) -> bool:
    """Return True if respondent has already signed the attestation."""
    cursor.execute(
        "SELECT attestation_signed_at IS NOT NULL "
        "FROM respondents WHERE id = %s",
        (respondent_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return False
    return bool(row[0])
