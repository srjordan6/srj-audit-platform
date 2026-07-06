"""Service layer for questionnaire orchestration."""

from __future__ import annotations

import json
from typing import Any, Optional

from questionnaire import flow


# ---------------------------------------------------------------------------
# Response persistence (PR 6)
# ---------------------------------------------------------------------------


def load_answered_by_id(cursor, respondent_id: str) -> dict[str, Any]:
    cursor.execute(
        "SELECT question_id, answer_value FROM responses "
        "WHERE respondent_id = %s",
        (respondent_id,),
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_respondent_role(cursor, respondent_id: str) -> Optional[str]:
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

    cursor.execute(
        "INSERT INTO engagements "
        "(company_id, buyer_user_id, tier, status, payment_status, price_cents) "
        "VALUES (%s, %s, 'tier_1', 'in_progress', 'free', 0) RETURNING id",
        (company_id, user_id),
    )
    engagement_id = cursor.fetchone()[0]

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
    cursor.execute(
        "UPDATE respondents "
        "SET attestation_signed_at = NOW(), attestation_text = %s "
        "WHERE id = %s",
        (attestation_text, respondent_id),
    )


def is_attestation_signed(cursor, respondent_id: str) -> bool:
    cursor.execute(
        "SELECT attestation_signed_at IS NOT NULL "
        "FROM respondents WHERE id = %s",
        (respondent_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return False
    return bool(row[0])


# ---------------------------------------------------------------------------
# Lifecycle state lookup (Sprint D PR 3 + PR 5)
# ---------------------------------------------------------------------------


def get_engagement_state(cursor, respondent_id: str) -> Optional[str]:
    """Return the snapshot_state of the engagement owning this respondent."""
    cursor.execute(
        "SELECT e.snapshot_state FROM engagements e "
        "JOIN respondents r ON r.engagement_id = e.id "
        "WHERE r.id = %s",
        (respondent_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_lifecycle_context(cursor, respondent_id: str) -> Optional[dict]:
    """Return snapshot_state + window_end_ts + purchase_ts for lifecycle rendering.

    Used by views to dispatch to Locked/Expired banners and compute countdown.
    """
    cursor.execute(
        "SELECT e.snapshot_state, e.window_end_timestamp, e.created_at "
        "FROM engagements e "
        "JOIN respondents r ON r.engagement_id = e.id "
        "WHERE r.id = %s",
        (respondent_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "state": row[0],
        "window_end_ts": row[1],
        "purchase_ts": row[2],
    }
