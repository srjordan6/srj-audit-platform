"""Tests for engagements.lifecycle — pure logic, no DB, no Django settings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from engagements import lifecycle


UTC = timezone.utc


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_edit_window_is_168_hours_7_days():
    assert lifecycle.EDIT_WINDOW_HOURS == 168


def test_draft_expiry_is_180_days():
    assert lifecycle.DRAFT_EXPIRY_DAYS == 180


def test_state_names_match_postgres_enum():
    assert lifecycle.DRAFT == "Draft"
    assert lifecycle.EDITABLE == "Editable"
    assert lifecycle.LOCKED == "Locked"
    assert lifecycle.EXPIRED == "Expired"


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def test_is_writable_true_for_draft_and_editable():
    assert lifecycle.is_writable("Draft") is True
    assert lifecycle.is_writable("Editable") is True


def test_is_writable_false_for_locked_and_expired():
    assert lifecycle.is_writable("Locked") is False
    assert lifecycle.is_writable("Expired") is False


def test_is_terminal_true_for_locked_and_expired():
    assert lifecycle.is_terminal("Locked") is True
    assert lifecycle.is_terminal("Expired") is True


def test_is_terminal_false_for_draft_and_editable():
    assert lifecycle.is_terminal("Draft") is False
    assert lifecycle.is_terminal("Editable") is False


# ---------------------------------------------------------------------------
# Valid transitions (one-way per OD-18 §2)
# ---------------------------------------------------------------------------


def test_draft_can_go_to_editable():
    assert lifecycle.is_valid_transition("Draft", "Editable") is True


def test_draft_can_go_to_expired():
    assert lifecycle.is_valid_transition("Draft", "Expired") is True


def test_editable_can_go_to_locked():
    assert lifecycle.is_valid_transition("Editable", "Locked") is True


def test_editable_cannot_go_back_to_draft():
    assert lifecycle.is_valid_transition("Editable", "Draft") is False


def test_locked_cannot_transition_further():
    for target in ("Draft", "Editable", "Expired", "Locked"):
        assert lifecycle.is_valid_transition("Locked", target) is False


def test_expired_cannot_transition_further():
    for target in ("Draft", "Editable", "Locked", "Expired"):
        assert lifecycle.is_valid_transition("Expired", target) is False


def test_invalid_state_name_returns_false():
    assert lifecycle.is_valid_transition("BogusState", "Editable") is False
    assert lifecycle.is_valid_transition("Draft", "BogusState") is False


# ---------------------------------------------------------------------------
# Timestamp computation
# ---------------------------------------------------------------------------


def test_compute_window_end_adds_exactly_168_hours():
    ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    assert lifecycle.compute_window_end(ts) == ts + timedelta(hours=168)


def test_compute_window_end_equals_seven_days():
    ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    assert lifecycle.compute_window_end(ts) == ts + timedelta(days=7)


def test_compute_expiry_adds_exactly_180_days():
    ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    assert lifecycle.compute_expiry(ts) == ts + timedelta(days=180)


# ---------------------------------------------------------------------------
# decide_first_generation_transition
# ---------------------------------------------------------------------------


def test_first_generation_from_draft_returns_editable():
    assert lifecycle.decide_first_generation_transition("Draft") == "Editable"


def test_first_generation_from_editable_raises():
    with pytest.raises(ValueError, match="only valid from Draft"):
        lifecycle.decide_first_generation_transition("Editable")


def test_first_generation_from_locked_raises():
    with pytest.raises(ValueError):
        lifecycle.decide_first_generation_transition("Locked")


def test_first_generation_from_expired_raises():
    with pytest.raises(ValueError):
        lifecycle.decide_first_generation_transition("Expired")


# ---------------------------------------------------------------------------
# decide_regeneration_transition
# ---------------------------------------------------------------------------


def test_regeneration_from_editable_stays_editable():
    assert lifecycle.decide_regeneration_transition("Editable") == "Editable"


def test_regeneration_from_draft_raises():
    with pytest.raises(ValueError, match="only valid from Editable"):
        lifecycle.decide_regeneration_transition("Draft")


def test_regeneration_from_locked_raises():
    with pytest.raises(ValueError):
        lifecycle.decide_regeneration_transition("Locked")


# ---------------------------------------------------------------------------
# decide_window_expiry_transition
# ---------------------------------------------------------------------------


def test_window_expiry_after_end_returns_locked():
    window_end = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    now = window_end + timedelta(seconds=1)
    assert lifecycle.decide_window_expiry_transition("Editable", window_end, now) == "Locked"


def test_window_expiry_at_exact_end_returns_locked():
    """>= boundary — locking at the exact second is correct behavior."""
    window_end = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    assert lifecycle.decide_window_expiry_transition("Editable", window_end, window_end) == "Locked"


def test_window_expiry_before_end_returns_none():
    window_end = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    now = window_end - timedelta(hours=1)
    assert lifecycle.decide_window_expiry_transition("Editable", window_end, now) is None


def test_window_expiry_from_non_editable_state_returns_none():
    window_end = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    now = window_end + timedelta(hours=1)
    for state in ("Draft", "Locked", "Expired"):
        assert lifecycle.decide_window_expiry_transition(state, window_end, now) is None


def test_window_expiry_null_window_end_returns_none():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    assert lifecycle.decide_window_expiry_transition("Editable", None, now) is None


# ---------------------------------------------------------------------------
# decide_draft_expiry_transition
# ---------------------------------------------------------------------------


def test_draft_expiry_after_180_days_returns_expired():
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=180, seconds=1)
    assert lifecycle.decide_draft_expiry_transition("Draft", purchase, now) == "Expired"


def test_draft_expiry_at_exact_180_days_returns_expired():
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=180)
    assert lifecycle.decide_draft_expiry_transition("Draft", purchase, now) == "Expired"


def test_draft_expiry_before_180_days_returns_none():
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=179, hours=23)
    assert lifecycle.decide_draft_expiry_transition("Draft", purchase, now) is None


def test_draft_expiry_from_editable_returns_none():
    """Once generated, the 180-day cap no longer applies — the 7-day
    window governs lock timing instead."""
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=300)
    assert lifecycle.decide_draft_expiry_transition("Editable", purchase, now) is None


def test_draft_expiry_from_locked_returns_none():
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=300)
    assert lifecycle.decide_draft_expiry_transition("Locked", purchase, now) is None


# ---------------------------------------------------------------------------
# build_first_generation_update
# ---------------------------------------------------------------------------


def test_build_first_generation_update_returns_all_fields():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    update = lifecycle.build_first_generation_update("Draft", now=now)
    assert update["snapshot_state"] == "Editable"
    assert update["first_generation_timestamp"] == now
    assert update["window_end_timestamp"] == now + timedelta(hours=168)
    assert update["generation_count"] == 1


def test_build_first_generation_update_defaults_now_to_utc():
    update = lifecycle.build_first_generation_update("Draft")
    ts = update["first_generation_timestamp"]
    assert ts.tzinfo is not None
    # Freshly computed — must be within a few seconds of "now"
    delta = datetime.now(UTC) - ts
    assert abs(delta.total_seconds()) < 10


def test_build_first_generation_update_raises_from_non_draft():
    with pytest.raises(ValueError):
        lifecycle.build_first_generation_update("Editable")


# ---------------------------------------------------------------------------
# build_regeneration_update
# ---------------------------------------------------------------------------


def test_build_regeneration_update_uses_increment_marker():
    update = lifecycle.build_regeneration_update("Editable")
    assert update == {"generation_count__increment": 1}


def test_build_regeneration_update_raises_from_non_editable():
    with pytest.raises(ValueError):
        lifecycle.build_regeneration_update("Draft")


# ---------------------------------------------------------------------------
# build_lock_update
# ---------------------------------------------------------------------------


def test_build_lock_update_returns_dict_when_window_expired():
    window_end = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    now = window_end + timedelta(seconds=1)
    update = lifecycle.build_lock_update(
        "Editable",
        window_end,
        now=now,
        report_of_record_id="report-uuid",
        report_of_record_pdf_hash="a" * 64,
    )
    assert update["snapshot_state"] == "Locked"
    assert update["lock_timestamp"] == now
    assert update["report_of_record_id"] == "report-uuid"
    assert update["report_of_record_pdf_hash"] == "a" * 64


def test_build_lock_update_returns_none_before_window_end():
    window_end = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    now = window_end - timedelta(hours=1)
    assert lifecycle.build_lock_update("Editable", window_end, now=now) is None


def test_build_lock_update_returns_none_when_not_editable():
    window_end = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    now = window_end + timedelta(hours=1)
    assert lifecycle.build_lock_update("Draft", window_end, now=now) is None
    assert lifecycle.build_lock_update("Locked", window_end, now=now) is None


# ---------------------------------------------------------------------------
# build_expiry_update
# ---------------------------------------------------------------------------


def test_build_expiry_update_returns_dict_after_180_days():
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=180, seconds=1)
    update = lifecycle.build_expiry_update("Draft", purchase, now=now)
    assert update["snapshot_state"] == "Expired"
    assert update["expiry_timestamp"] == now


def test_build_expiry_update_returns_none_before_180_days():
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=100)
    assert lifecycle.build_expiry_update("Draft", purchase, now=now) is None


def test_build_expiry_update_returns_none_when_not_draft():
    purchase = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = purchase + timedelta(days=300)
    for state in ("Editable", "Locked", "Expired"):
        assert lifecycle.build_expiry_update(state, purchase, now=now) is None
