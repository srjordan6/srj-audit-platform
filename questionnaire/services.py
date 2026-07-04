"""Service layer for questionnaire orchestration.

Pure functions that combine flow.py logic with DB access via a cursor
parameter. Views are thin wrappers over these. Testable with mocked
cursors — no Django settings required for unit tests.

All DB access uses parameterized queries; no ORM. Matches the discipline
of scoring/frameworks/*.py which stays DB-independent.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from questionnaire import flow


def load_answered_by_id(cursor, respondent_id: str) -> dict[str, Any]:
    """Return {question_id: answer_value} for every response by this respondent.

    Uses parameterized query; safe against injection. Returns empty dict
    if respondent has no responses yet.
    """
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

    UNIQUE(respondent_id, question_id) constraint means re-answering the
    same question updates the existing row rather than creating a duplicate.
    answered_at is refreshed on update.
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
    """Return context dict for rendering next question, or None if done.

    Returns:
        {
            "question": SimpleNamespace,
            "partial": str,           # partial template path
            "progress": (int, int, float),
            "role": str,
        }
        or None if respondent is unknown OR has answered every visible
        question.
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
