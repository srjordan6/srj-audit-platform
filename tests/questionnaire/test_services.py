"""Tests for questionnaire.services — mock cursors, no Django settings.

Uses unittest.mock.MagicMock to simulate psycopg cursor behavior. Real
DB integration tests belong in PR 7 alongside session infrastructure.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from questionnaire import services


# ---------------------------------------------------------------------------
# load_answered_by_id
# ---------------------------------------------------------------------------


def test_load_answered_empty():
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    result = services.load_answered_by_id(cursor, "some-uuid")
    assert result == {}


def test_load_answered_with_responses():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("T1-A-001", {"selected": "CEO or Owner"}),
        ("T1-A-002", {"selected": "1-3 years"}),
    ]
    result = services.load_answered_by_id(cursor, "some-uuid")
    assert result == {
        "T1-A-001": {"selected": "CEO or Owner"},
        "T1-A-002": {"selected": "1-3 years"},
    }


def test_load_answered_uses_parameterized_query():
    """Confirm respondent_id passed as parameter, not string-interpolated."""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    services.load_answered_by_id(cursor, "some-uuid")
    call_args = cursor.execute.call_args
    sql_text = call_args[0][0]
    sql_params = call_args[0][1]
    assert "%s" in sql_text
    assert sql_params == ("some-uuid",)


# ---------------------------------------------------------------------------
# get_respondent_role
# ---------------------------------------------------------------------------


def test_get_respondent_role_returns_role():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("CEO",)
    assert services.get_respondent_role(cursor, "some-uuid") == "CEO"


def test_get_respondent_role_returns_none_when_missing():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    assert services.get_respondent_role(cursor, "missing-uuid") is None


# ---------------------------------------------------------------------------
# save_response
# ---------------------------------------------------------------------------


def test_save_response_calls_execute_once():
    cursor = MagicMock()
    services.save_response(cursor, "rid", "T1-A-001", {"selected": "CEO"})
    cursor.execute.assert_called_once()


def test_save_response_serializes_answer_as_json():
    cursor = MagicMock()
    services.save_response(cursor, "rid", "T1-A-001", {"selected": "CEO"})
    sql_params = cursor.execute.call_args[0][1]
    # 3rd positional param is the serialized answer_value
    serialized = sql_params[2]
    parsed = json.loads(serialized)
    assert parsed == {"selected": "CEO"}


def test_save_response_default_is_dont_know_false():
    cursor = MagicMock()
    services.save_response(cursor, "rid", "T1-A-001", {"selected": "CEO"})
    sql_params = cursor.execute.call_args[0][1]
    assert sql_params[3] is False


def test_save_response_is_dont_know_true():
    cursor = MagicMock()
    services.save_response(
        cursor, "rid", "T1-A-001", {"selected": "Don't know"}, is_dont_know=True
    )
    sql_params = cursor.execute.call_args[0][1]
    assert sql_params[3] is True


def test_save_response_uses_upsert():
    """SQL must include ON CONFLICT clause for idempotent re-answers."""
    cursor = MagicMock()
    services.save_response(cursor, "rid", "T1-A-001", {"selected": "CEO"})
    sql_text = cursor.execute.call_args[0][0]
    assert "ON CONFLICT" in sql_text
    assert "DO UPDATE" in sql_text


# ---------------------------------------------------------------------------
# get_next_question_context
# ---------------------------------------------------------------------------


def _setup_cursor(role: str | None, answered_rows: list[tuple]) -> MagicMock:
    """Configure a mock cursor for a get_next_question_context call.

    fetchone returns the role tuple (or None); fetchall returns the answers.
    """
    cursor = MagicMock()
    if role is None:
        cursor.fetchone.return_value = None
    else:
        cursor.fetchone.return_value = (role,)
    cursor.fetchall.return_value = answered_rows
    return cursor


def test_next_context_returns_first_when_no_answers():
    cursor = _setup_cursor(role="CEO", answered_rows=[])
    ctx = services.get_next_question_context(cursor, "rid")
    assert ctx is not None
    assert ctx["question"].id == "T1-A-001"
    assert ctx["role"] == "CEO"
    assert ctx["partial"].endswith("_question_single_select.html")


def test_next_context_advances_after_answer():
    cursor = _setup_cursor(
        role="CEO",
        answered_rows=[("T1-A-001", {"selected": "CEO or Owner"})],
    )
    ctx = services.get_next_question_context(cursor, "rid")
    assert ctx is not None
    assert ctx["question"].id == "T1-A-002"


def test_next_context_returns_none_when_role_unknown():
    cursor = _setup_cursor(role=None, answered_rows=[])
    ctx = services.get_next_question_context(cursor, "rid")
    assert ctx is None


def test_next_context_progress_tuple_shape():
    cursor = _setup_cursor(role="CEO", answered_rows=[])
    ctx = services.get_next_question_context(cursor, "rid")
    assert ctx is not None
    completed, visible, pct = ctx["progress"]
    assert completed == 0
    assert visible > 0
    assert pct == 0.0


def test_next_context_returns_none_when_all_answered():
    """Simulate having answered every visible question."""
    from questionnaire.flow import questions_visible_to_role

    role_answers = {"T1-A-001": {"selected": "CEO or Owner"}}
    all_visible = questions_visible_to_role("CEO", role_answers)
    answered_rows = [(q.id, {"selected": "x"}) for q in all_visible]
    cursor = _setup_cursor(role="CEO", answered_rows=answered_rows)
    ctx = services.get_next_question_context(cursor, "rid")
    assert ctx is None
