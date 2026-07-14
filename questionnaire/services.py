"""Service layer for questionnaire orchestration.

Cursor-based, no ORM. respondents.company_id and responses.company_id are
NOT NULL — services pull company_id from context and include in INSERTs.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from questionnaire import flow


# ---------------------------------------------------------------------------
# Response persistence
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


def get_respondent_company_id(cursor, respondent_id: str) -> Optional[str]:
    """Return the company_id of the engagement owning this respondent."""
    cursor.execute(
        "SELECT company_id FROM respondents WHERE id = %s",
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
    """Upsert a response row. Fetches company_id from respondent (NOT NULL)."""
    company_id = get_respondent_company_id(cursor, respondent_id)
    if company_id is None:
        raise ValueError(f"respondent {respondent_id} not found")

    cursor.execute(
        """
        INSERT INTO responses
            (respondent_id, question_id, answer_value, is_dont_know, company_id)
        VALUES (%s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (respondent_id, question_id)
        DO UPDATE SET
            answer_value = EXCLUDED.answer_value,
            is_dont_know = EXCLUDED.is_dont_know,
            answered_at = NOW()
        """,
        (respondent_id, question_id, json.dumps(answer_value), is_dont_know, company_id),
    )


def get_next_question_context(
    cursor,
    respondent_id: str,
) -> Optional[dict]:
    role = get_respondent_role(cursor, respondent_id)
    if role is None:
        return None
    answered = load_answered_by_id(cursor, respondent_id)
    visible = flow.questions_visible_to_role(role, answered)
    q = None
    for candidate in visible:
        if candidate.id not in answered:
            q = candidate
            break
    if q is None:
        return None
    _decorate_question(q, answered, visible=visible)
    return {
        "question": q,
        "partial": flow.partial_template_for_type(q.question_type),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
    }


def get_next_visible_question_context_by_position(
    cursor,
    respondent_id: str,
    current_question_id: Optional[str] = None,
) -> Optional[dict]:
    """Return the visible question immediately AFTER current_question_id.

    Mirror of get_previous_visible_question_context but +1 instead of -1.
    If current_question_id is None or not found, falls back to the first
    unanswered visible question. Returns None if the respondent is
    already at the end of the flow.
    """
    role = get_respondent_role(cursor, respondent_id)
    if role is None:
        return None
    answered = load_answered_by_id(cursor, respondent_id)
    visible = flow.questions_visible_to_role(role, answered)

    next_q = None
    if current_question_id:
        for i, q in enumerate(visible):
            if q.id == current_question_id:
                if i + 1 < len(visible):
                    next_q = visible[i + 1]
                break

    if next_q is None:
        # Fallback: first unanswered visible question.
        for q in visible:
            if q.id not in answered:
                next_q = q
                break

    if next_q is None:
        return None

    _decorate_question(next_q, answered, visible=visible)
    return {
        "question": next_q,
        "partial": flow.partial_template_for_type(next_q.question_type),
        "prior_answer": answered.get(next_q.id),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
    }


def get_previous_visible_question_context(
    cursor,
    respondent_id: str,
    current_question_id: Optional[str] = None,
) -> Optional[dict]:
    """Return the visible question immediately before current_question_id.

    If current_question_id is None (or not found among visible questions),
    returns the LAST-ANSWERED visible question — a safe fallback so the
    "Previous" button always does something sensible.

    Returned dict is shaped like get_next_question_context but also
    carries a 'prior_answer' key so the partial pre-fills the input(s).
    Returns None when there is no earlier answered question (e.g., the
    respondent is already on the first question).
    """
    role = get_respondent_role(cursor, respondent_id)
    if role is None:
        return None
    answered = load_answered_by_id(cursor, respondent_id)
    visible = flow.questions_visible_to_role(role, answered)

    prev_q = None
    if current_question_id:
        for i, q in enumerate(visible):
            if q.id == current_question_id:
                if i > 0:
                    prev_q = visible[i - 1]
                break

    if prev_q is None:
        # Fallback: last answered visible question.
        for q in visible:
            if q.id in answered:
                prev_q = q

    if prev_q is None:
        return None

    _decorate_question(prev_q, answered, visible=visible)
    return {
        "question": prev_q,
        "partial": flow.partial_template_for_type(prev_q.question_type),
        "prior_answer": answered.get(prev_q.id),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
    }


def _decorate_question(q, answered, visible=None):
    """Inject dynamic context onto a question SimpleNamespace before render.

    - display_number: 1-based position in the visible list, so the header
      shows contiguous numbering (Q1..QN) even when is_active=False
      questions are skipped in the middle of a section.
    - TOOL_INVENTORY: attach the canonical tool_catalog.CATEGORIES so the
      partial can render the categorized checklist.
    - T1-B-017 (MATRIX 'top 3 tools by spend'): prefill matrix_rows from
      the respondent's T1-A-000 tool inventory answer if available, so
      the respondent sees their tools as row placeholders instead of
      generic 'Tool 1 / Tool 2 / Tool 3'.
    """
    if visible is not None:
        for idx, vq in enumerate(visible, start=1):
            if vq.id == q.id:
                q.display_number = idx
                q.total_visible = len(visible)
                break
        else:
            q.display_number = None
            q.total_visible = len(visible)
    if q.question_type == "TOOL_INVENTORY":
        from questionnaire.tool_catalog import CATEGORIES
        q.tool_categories = CATEGORIES
        return

    if q.id == "T1-B-017":
        # load_answered_by_id returns {question_id: answer_value}. The
        # T1-A-000 answer_value is {"selected": [...], "other": "..."}.
        av = answered.get("T1-A-000")
        if av and isinstance(av, dict):
            selected = list(av.get("selected") or [])
            other = (av.get("other") or "").strip()
            if other:
                selected += [t.strip() for t in other.split(",") if t.strip()]
            if selected:
                # Prefill up to the number of rows the question already
                # declares. Preserve declared count so we don't shrink.
                current_rows = list(q.matrix_rows or [])
                for i, tool in enumerate(selected[: len(current_rows)]):
                    current_rows[i] = tool
                q.matrix_rows = current_rows


# ---------------------------------------------------------------------------
# Engagement bootstrap
# ---------------------------------------------------------------------------


def create_engagement_and_respondent(
    cursor,
    email: str,
    name: str,
    role: str,
    company_name: str,
    company_industry: str,
    company_size_bracket: str,
    access_code_row=None,
) -> str:
    """Create/find company + user, then create engagement + respondent.

    If access_code_row is passed (as returned by
    questionnaire.access_codes.validate_code), the engagement is comped
    (payment_status='comped', price_cents=0) and a redemption row is
    written atomically. The caller MUST have already validated the code;
    if the redeem_code UPDATE loses the race (code exhausted between
    validation and this call), we raise ValueError so the outer view
    rolls back the transaction and re-renders the form with an error.
    """
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

    if access_code_row is not None:
        # Comped engagement — no Stripe path, payment_status = 'comped'.
        cursor.execute(
            "INSERT INTO engagements "
            "(company_id, buyer_user_id, tier, status, payment_status, price_cents) "
            "VALUES (%s, %s, 'tier_1', 'in_progress', 'comped', 0) RETURNING id",
            (company_id, user_id),
        )
    else:
        cursor.execute(
            "INSERT INTO engagements "
            "(company_id, buyer_user_id, tier, status, payment_status, price_cents) "
            "VALUES (%s, %s, 'tier_1', 'in_progress', 'free', 0) RETURNING id",
            (company_id, user_id),
        )
    engagement_id = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO respondents "
        "(engagement_id, user_id, email, name, role, company_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (engagement_id, user_id, email, name, role, company_id),
    )
    respondent_id = cursor.fetchone()[0]

    if access_code_row is not None:
        # Atomic claim + redemption record. If the UPDATE loses the race
        # (someone else drained the last use between validate and here),
        # raise so the whole transaction rolls back and the user sees an
        # error rather than a silent partial state.
        from questionnaire.access_codes import redeem_code
        ok = redeem_code(
            cursor,
            access_code_id=access_code_row.id,
            engagement_id=str(engagement_id),
            respondent_email=email,
        )
        if not ok:
            raise ValueError("access_code_exhausted")

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
# Lifecycle state lookup
# ---------------------------------------------------------------------------


def get_engagement_state(cursor, respondent_id: str) -> Optional[str]:
    cursor.execute(
        "SELECT e.snapshot_state FROM engagements e "
        "JOIN respondents r ON r.engagement_id = e.id "
        "WHERE r.id = %s",
        (respondent_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_lifecycle_context(cursor, respondent_id: str) -> Optional[dict]:
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
