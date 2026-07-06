"""Tests for edit-blocking (Sprint D PR 3).

Mocks Django Response classes so tests run without settings configuration.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from questionnaire import services


# ---------------------------------------------------------------------------
# services.get_engagement_state
# ---------------------------------------------------------------------------


def test_get_engagement_state_returns_state_when_respondent_exists():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("Editable",)
    assert services.get_engagement_state(cursor, "rid") == "Editable"


def test_get_engagement_state_returns_none_when_respondent_missing():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    assert services.get_engagement_state(cursor, "missing") is None


def test_get_engagement_state_uses_parameterized_query():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("Draft",)
    services.get_engagement_state(cursor, "rid-123")
    sql_text = cursor.execute.call_args[0][0]
    sql_params = cursor.execute.call_args[0][1]
    assert "%s" in sql_text
    assert "JOIN respondents" in sql_text
    assert sql_params == ("rid-123",)


def test_get_engagement_state_returns_locked():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("Locked",)
    assert services.get_engagement_state(cursor, "rid") == "Locked"


def test_get_engagement_state_returns_expired():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("Expired",)
    assert services.get_engagement_state(cursor, "rid") == "Expired"


# ---------------------------------------------------------------------------
# require_writable_state decorator
# ---------------------------------------------------------------------------


def _mock_request(respondent_id="rid"):
    req = MagicMock()
    req.session = {"respondent_id": respondent_id} if respondent_id else {}
    req.GET = {}
    return req


def _wrapped_dummy_view():
    from questionnaire.decorators import require_writable_state
    called = {"count": 0}

    @require_writable_state
    def view(request, *args, **kwargs):
        called["count"] += 1
        return "ok"

    return view, called


def _sentinel_response(status):
    r = MagicMock()
    r.status_code = status
    r.content = b""
    return r


@patch("questionnaire.decorators._response_403")
@patch("questionnaire.decorators._response_404")
@patch("questionnaire.decorators.connection")
@patch("questionnaire.decorators.services.get_engagement_state")
def test_decorator_calls_view_when_state_draft(get_state, conn, r404, r403):
    get_state.return_value = "Draft"
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    view, called = _wrapped_dummy_view()
    result = view(_mock_request())
    assert result == "ok"
    assert called["count"] == 1
    r403.assert_not_called()
    r404.assert_not_called()


@patch("questionnaire.decorators._response_403")
@patch("questionnaire.decorators._response_404")
@patch("questionnaire.decorators.connection")
@patch("questionnaire.decorators.services.get_engagement_state")
def test_decorator_calls_view_when_state_editable(get_state, conn, r404, r403):
    get_state.return_value = "Editable"
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    view, called = _wrapped_dummy_view()
    result = view(_mock_request())
    assert result == "ok"
    assert called["count"] == 1
    r403.assert_not_called()


@patch("questionnaire.decorators._response_403")
@patch("questionnaire.decorators._response_404")
@patch("questionnaire.decorators.connection")
@patch("questionnaire.decorators.services.get_engagement_state")
def test_decorator_returns_403_when_state_locked(get_state, conn, r404, r403):
    get_state.return_value = "Locked"
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    r403.return_value = _sentinel_response(403)
    view, called = _wrapped_dummy_view()
    result = view(_mock_request())
    assert called["count"] == 0
    r403.assert_called_once_with("Locked")


@patch("questionnaire.decorators._response_403")
@patch("questionnaire.decorators._response_404")
@patch("questionnaire.decorators.connection")
@patch("questionnaire.decorators.services.get_engagement_state")
def test_decorator_returns_403_when_state_expired(get_state, conn, r404, r403):
    get_state.return_value = "Expired"
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    r403.return_value = _sentinel_response(403)
    view, called = _wrapped_dummy_view()
    view(_mock_request())
    assert called["count"] == 0
    r403.assert_called_once_with("Expired")


@patch("questionnaire.decorators._response_403")
@patch("questionnaire.decorators._response_404")
@patch("questionnaire.decorators.connection")
@patch("questionnaire.decorators.services.get_engagement_state")
def test_decorator_returns_404_when_respondent_id_missing(get_state, conn, r404, r403):
    r404.return_value = _sentinel_response(404)
    view, called = _wrapped_dummy_view()
    view(_mock_request(respondent_id=None))
    assert called["count"] == 0
    get_state.assert_not_called()
    r404.assert_called_once_with("respondent_id required")


@patch("questionnaire.decorators._response_403")
@patch("questionnaire.decorators._response_404")
@patch("questionnaire.decorators.connection")
@patch("questionnaire.decorators.services.get_engagement_state")
def test_decorator_returns_404_when_respondent_not_found(get_state, conn, r404, r403):
    get_state.return_value = None
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    r404.return_value = _sentinel_response(404)
    view, called = _wrapped_dummy_view()
    view(_mock_request())
    assert called["count"] == 0
    r404.assert_called_once_with("respondent not found")