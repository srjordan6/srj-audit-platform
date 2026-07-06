"""Tests for Sprint D PR 5: countdown format + lifecycle context + banners."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from django.template import Context, Engine

from engagements import lifecycle
from questionnaire import services


UTC = timezone.utc
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


def _render(template_path, ctx=None):
    engine = Engine(dirs=[str(TEMPLATES_DIR)])
    return engine.get_template(template_path).render(Context(ctx or {}))


# ---------------------------------------------------------------------------
# lifecycle.format_countdown
# ---------------------------------------------------------------------------


def test_countdown_days_and_hours_format():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    window_end = now + timedelta(days=3, hours=5)
    text = lifecycle.format_countdown(window_end, now)
    assert text == "Edit window closes in 3 days, 5 hours"


def test_countdown_singular_day():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    window_end = now + timedelta(days=1, hours=2)
    text = lifecycle.format_countdown(window_end, now)
    assert "1 day," in text
    assert "days," not in text


def test_countdown_hours_and_minutes_format():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    window_end = now + timedelta(hours=5, minutes=30)
    text = lifecycle.format_countdown(window_end, now)
    assert text == "Edit window closes in 5 hours, 30 minutes"


def test_countdown_minutes_only():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    window_end = now + timedelta(minutes=45)
    text = lifecycle.format_countdown(window_end, now)
    assert text == "Edit window closes in 45 minutes"


def test_countdown_singular_minute():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    window_end = now + timedelta(minutes=1, seconds=30)
    text = lifecycle.format_countdown(window_end, now)
    assert text == "Edit window closes in 1 minute"


def test_countdown_expired_returns_none():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    window_end = now - timedelta(hours=1)
    assert lifecycle.format_countdown(window_end, now) is None


def test_countdown_at_boundary_returns_none():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    assert lifecycle.format_countdown(now, now) is None


def test_countdown_none_window_returns_none():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    assert lifecycle.format_countdown(None, now) is None


# ---------------------------------------------------------------------------
# services.get_lifecycle_context
# ---------------------------------------------------------------------------


def test_lifecycle_context_returns_all_fields():
    cursor = MagicMock()
    purchase = datetime(2026, 1, 1, tzinfo=UTC)
    window_end = datetime(2026, 7, 4, tzinfo=UTC)
    cursor.fetchone.return_value = ("Editable", window_end, purchase)
    ctx = services.get_lifecycle_context(cursor, "rid")
    assert ctx == {
        "state": "Editable",
        "window_end_ts": window_end,
        "purchase_ts": purchase,
    }


def test_lifecycle_context_none_when_respondent_missing():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    assert services.get_lifecycle_context(cursor, "missing") is None


def test_lifecycle_context_draft_has_null_window_end():
    cursor = MagicMock()
    purchase = datetime(2026, 1, 1, tzinfo=UTC)
    cursor.fetchone.return_value = ("Draft", None, purchase)
    ctx = services.get_lifecycle_context(cursor, "rid")
    assert ctx["state"] == "Draft"
    assert ctx["window_end_ts"] is None


def test_lifecycle_context_uses_parameterized_query():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("Draft", None, datetime(2026, 1, 1, tzinfo=UTC))
    services.get_lifecycle_context(cursor, "rid-123")
    sql_text = cursor.execute.call_args[0][0]
    sql_params = cursor.execute.call_args[0][1]
    assert "JOIN respondents" in sql_text
    assert "snapshot_state" in sql_text
    assert "window_end_timestamp" in sql_text
    assert sql_params == ("rid-123",)


# ---------------------------------------------------------------------------
# _locked.html template
# ---------------------------------------------------------------------------


def test_locked_template_shows_locked_heading():
    html = _render("questionnaire/partials/_locked.html")
    assert "Snapshot Locked" in html


def test_locked_template_mentions_7_day_window():
    html = _render("questionnaire/partials/_locked.html")
    assert "7-day" in html or "seven-day" in html


def test_locked_template_has_new_snapshot_cta():
    html = _render("questionnaire/partials/_locked.html")
    assert "Start a new snapshot" in html


def test_locked_template_uses_start_url():
    html = _render("questionnaire/partials/_locked.html")
    assert "/q/start/" in html


def test_locked_template_mentions_reports_remain_available():
    html = _render("questionnaire/partials/_locked.html")
    assert "view" in html.lower()
    assert "download" in html.lower()


def test_locked_template_uses_warning_styling():
    html = _render("questionnaire/partials/_locked.html")
    assert "alert-warning" in html


# ---------------------------------------------------------------------------
# _expired.html template
# ---------------------------------------------------------------------------


def test_expired_template_shows_expired_heading():
    html = _render("questionnaire/partials/_expired.html")
    assert "Snapshot Expired" in html


def test_expired_template_mentions_180_day_cap():
    html = _render("questionnaire/partials/_expired.html")
    assert "180-day" in html or "180 day" in html


def test_expired_template_has_new_snapshot_cta():
    html = _render("questionnaire/partials/_expired.html")
    assert "Start a new snapshot" in html


def test_expired_template_uses_start_url():
    html = _render("questionnaire/partials/_expired.html")
    assert "/q/start/" in html


def test_expired_template_states_price():
    html = _render("questionnaire/partials/_expired.html")
    assert "$399" in html


def test_expired_template_uses_danger_styling():
    html = _render("questionnaire/partials/_expired.html")
    assert "alert-danger" in html


# ---------------------------------------------------------------------------
# _countdown_banner.html template
# ---------------------------------------------------------------------------


def test_countdown_banner_renders_when_text_present():
    html = _render(
        "questionnaire/partials/_countdown_banner.html",
        {"countdown_text": "Edit window closes in 3 days, 5 hours"},
    )
    assert "3 days" in html
    assert "alert-info" in html


def test_countdown_banner_renders_nothing_when_text_absent():
    html = _render(
        "questionnaire/partials/_countdown_banner.html",
        {"countdown_text": None},
    )
    assert "alert" not in html


def test_countdown_banner_renders_nothing_when_text_empty():
    html = _render(
        "questionnaire/partials/_countdown_banner.html",
        {},
    )
    assert "alert" not in html


def test_countdown_banner_uses_strong_emphasis():
    html = _render(
        "questionnaire/partials/_countdown_banner.html",
        {"countdown_text": "test countdown"},
    )
    assert "<strong>" in html
    assert "test countdown" in html
