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
    """Return {question_id: parsed_answer_value_dict}.

    Django's default psycopg configuration returns JSONB columns as raw
    JSON strings rather than parsed dicts on this Django/psycopg version.
    Parse them here so downstream code (prior_answer prefill in
    Previous/Forward, _decorate_question T1-B-017 prefill, etc.) can
    treat the value as a dict uniformly.
    """
    cursor.execute(
        "SELECT question_id, answer_value FROM responses "
        "WHERE respondent_id = %s",
        (respondent_id,),
    )
    result: dict[str, Any] = {}
    for qid, raw in cursor.fetchall():
        if isinstance(raw, str):
            try:
                result[qid] = json.loads(raw)
            except (ValueError, TypeError):
                result[qid] = raw
        else:
            result[qid] = raw
    return result


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
    _decorate_question(q, answered, visible=visible, respondent_ctx=_load_respondent_context(cursor, respondent_id))
    return {
        "question": q,
        "partial": flow.partial_template_for_type(q.question_type),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
    }


def _last_answered_index(visible, answered) -> int:
    """1-based index of the furthest-answered visible question, or 0.

    Returned as position not array-index so it matches display_number.
    """
    last = 0
    for idx, q in enumerate(visible, start=1):
        if q.id in answered:
            last = idx
    return last


def get_next_visible_question_context_by_position(
    cursor,
    respondent_id: str,
    current_question_id: Optional[str] = None,
) -> Optional[dict]:
    """Return the visible question immediately AFTER current_question_id.

    Guard rail (per operator direction 2026-07-14): Next may not advance
    past the last-answered position. Save & continue is the only path
    that opens new territory.

    Returns None if:
      - the current question is unknown, OR
      - the next position would move beyond the furthest-answered index.
    """
    role = get_respondent_role(cursor, respondent_id)
    if role is None:
        return None
    answered = load_answered_by_id(cursor, respondent_id)
    visible = flow.questions_visible_to_role(role, answered)
    last_answered = _last_answered_index(visible, answered)

    current_idx_1based = None
    if current_question_id:
        for i, q in enumerate(visible, start=1):
            if q.id == current_question_id:
                current_idx_1based = i
                break

    if current_idx_1based is None:
        # Fallback: first-unanswered (matches natural forward flow).
        for q in visible:
            if q.id not in answered:
                next_q = q
                break
        else:
            return None
    else:
        next_pos = current_idx_1based + 1
        if next_pos > last_answered:
            return None  # blocked — no further-answered territory
        if next_pos > len(visible):
            return None
        next_q = visible[next_pos - 1]

    _decorate_question(next_q, answered, visible=visible, respondent_ctx=_load_respondent_context(cursor, respondent_id))
    return {
        "question": next_q,
        "partial": flow.partial_template_for_type(next_q.question_type),
        "prior_answer": answered.get(next_q.id),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
    }


def get_question_context_by_position(
    cursor,
    respondent_id: str,
    position: int,
) -> Optional[dict]:
    """Jump to the visible question at 1-based ``position``.

    Enforces the same guard as Next: position may not exceed the
    furthest-answered index (so the slider can only visit territory the
    respondent has already seen). Returns None if position is out of
    range.
    """
    role = get_respondent_role(cursor, respondent_id)
    if role is None:
        return None
    answered = load_answered_by_id(cursor, respondent_id)
    visible = flow.questions_visible_to_role(role, answered)
    last_answered = _last_answered_index(visible, answered)

    try:
        pos = int(position)
    except (TypeError, ValueError):
        return None

    if pos < 1 or pos > len(visible):
        return None
    # Slider may only visit already-answered territory. If no questions
    # answered yet, reject any jump (nothing to go back to). Save & continue
    # is the only path that opens new territory.
    if last_answered < 1 or pos > last_answered:
        return None

    target = visible[pos - 1]
    _decorate_question(target, answered, visible=visible, respondent_ctx=_load_respondent_context(cursor, respondent_id))
    return {
        "question": target,
        "partial": flow.partial_template_for_type(target.question_type),
        "prior_answer": answered.get(target.id),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
        "last_answered_position": last_answered,
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

    _decorate_question(prev_q, answered, visible=visible, respondent_ctx=_load_respondent_context(cursor, respondent_id))
    return {
        "question": prev_q,
        "partial": flow.partial_template_for_type(prev_q.question_type),
        "prior_answer": answered.get(prev_q.id),
        "progress": flow.progress_for_role(role, answered),
        "role": role,
    }


def _load_respondent_context(cursor, respondent_id: str) -> dict:
    """Return company-level context for recommendation logic.

    {company_industry, company_size_bracket, respondent_role, respondent_email}.
    Non-fatal — returns {} if the lookup fails.
    """
    try:
        cursor.execute(
            "SELECT c.industry, c.size_bracket, r.role, r.email, "
            "       c.annual_revenue, c.geographic_footprint "
            "FROM respondents r JOIN companies c ON c.id = r.company_id "
            "WHERE r.id = %s LIMIT 1",
            (respondent_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {}
        return {
            "company_industry": row[0],
            "company_size_bracket": row[1],
            "respondent_role": row[2],
            "respondent_email": row[3],
            "annual_revenue": row[4],
            "geographic_footprint": row[5],
        }
    except Exception:  # noqa: BLE001
        return {}


def _decorate_question(q, answered, visible=None, respondent_ctx=None):
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
        # Furthest-answered position drives the slider's max attribute
        # so users can only jump within already-visited territory.
        q.last_answered_position = _last_answered_index(visible, answered)
    if q.question_type == "TOOL_INVENTORY":
        from questionnaire.tool_catalog import CATEGORIES
        q.tool_categories = CATEGORIES
        return

    if q.question_type == "LAW_INVENTORY":
        from questionnaire.law_catalog import CATEGORIES
        from questionnaire.law_recommender import recommend_laws
        q.law_categories = CATEGORIES
        ctx = respondent_ctx or {}
        # Prefer signup-captured profile fields. Fall back to legacy
        # T1-A-005 / T1-A-007 answers for engagements that pre-date the
        # signup-profile expansion.
        geo = (
            ctx.get("geographic_footprint")
            or answered.get("T1-A-005")
        )
        q.recommended_laws = recommend_laws(
            industry=ctx.get("company_industry"),
            size_bracket=ctx.get("company_size_bracket"),
            geographic=geo,
        )
        q.recommended_set = set(q.recommended_laws)
        q.recommendation_inputs = {
            "industry": ctx.get("company_industry"),
            "size_bracket": ctx.get("company_size_bracket"),
            "geographic": (
                (answered.get("T1-A-005") or {}).get("selected")
                if isinstance(answered.get("T1-A-005"), dict) else None
            ),
        }
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
    annual_revenue: str = "",
    geographic_footprint: str = "",
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
            "INSERT INTO companies "
            "(name, industry, size_bracket, annual_revenue, geographic_footprint) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (company_name, company_industry, company_size_bracket,
             annual_revenue or None, geographic_footprint or None),
        )
        row = cursor.fetchone()
    else:
        # Company already existed — update the profile fields to whatever
        # this latest signup declared (last-write-wins).
        cursor.execute(
            "UPDATE companies SET "
            "  industry = COALESCE(NULLIF(%s, ''), industry), "
            "  size_bracket = COALESCE(NULLIF(%s, ''), size_bracket), "
            "  annual_revenue = COALESCE(NULLIF(%s, ''), annual_revenue), "
            "  geographic_footprint = COALESCE(NULLIF(%s, ''), geographic_footprint) "
            "WHERE id = %s",
            (company_industry, company_size_bracket,
             annual_revenue, geographic_footprint, row[0]),
        )
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
