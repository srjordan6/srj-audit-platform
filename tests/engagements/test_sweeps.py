"""Tests for engagements.sweeps — mock cursors, no Django settings."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from engagements import sweeps


UTC = timezone.utc


# ---------------------------------------------------------------------------
# sweep_editable_to_locked
# ---------------------------------------------------------------------------


def test_sweep_locked_uses_now_when_not_provided():
    cursor = MagicMock()
    cursor.rowcount = 0
    sweeps.sweep_editable_to_locked(cursor)
    sql_text = cursor.execute.call_args[0][0]
    assert "snapshot_state = 'Editable'" in sql_text
    assert "snapshot_state = 'Locked'" in sql_text


def test_sweep_locked_uses_provided_now():
    cursor = MagicMock()
    cursor.rowcount = 3
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    result = sweeps.sweep_editable_to_locked(cursor, now=now)
    params = cursor.execute.call_args[0][1]
    assert params == (now, now)
    assert result == 3


def test_sweep_locked_returns_rowcount():
    cursor = MagicMock()
    cursor.rowcount = 7
    assert sweeps.sweep_editable_to_locked(cursor) == 7


def test_sweep_locked_sets_lock_timestamp():
    cursor = MagicMock()
    cursor.rowcount = 1
    sweeps.sweep_editable_to_locked(cursor)
    sql_text = cursor.execute.call_args[0][0]
    assert "lock_timestamp" in sql_text


def test_sweep_locked_filters_by_window_end():
    cursor = MagicMock()
    cursor.rowcount = 0
    sweeps.sweep_editable_to_locked(cursor)
    sql_text = cursor.execute.call_args[0][0]
    assert "window_end_timestamp <= %s" in sql_text


def test_sweep_locked_zero_when_no_matches():
    cursor = MagicMock()
    cursor.rowcount = 0
    assert sweeps.sweep_editable_to_locked(cursor) == 0


# ---------------------------------------------------------------------------
# sweep_draft_to_expired
# ---------------------------------------------------------------------------


def test_sweep_expired_uses_180_day_interval():
    cursor = MagicMock()
    cursor.rowcount = 0
    sweeps.sweep_draft_to_expired(cursor)
    sql_text = cursor.execute.call_args[0][0]
    assert "INTERVAL '180 days'" in sql_text


def test_sweep_expired_filters_by_created_at():
    cursor = MagicMock()
    cursor.rowcount = 0
    sweeps.sweep_draft_to_expired(cursor)
    sql_text = cursor.execute.call_args[0][0]
    assert "created_at <= %s - INTERVAL '180 days'" in sql_text


def test_sweep_expired_only_targets_draft():
    cursor = MagicMock()
    cursor.rowcount = 0
    sweeps.sweep_draft_to_expired(cursor)
    sql_text = cursor.execute.call_args[0][0]
    assert "snapshot_state = 'Draft'" in sql_text
    assert "snapshot_state = 'Expired'" in sql_text


def test_sweep_expired_sets_expiry_timestamp():
    cursor = MagicMock()
    cursor.rowcount = 0
    sweeps.sweep_draft_to_expired(cursor)
    sql_text = cursor.execute.call_args[0][0]
    assert "expiry_timestamp = %s" in sql_text


def test_sweep_expired_returns_rowcount():
    cursor = MagicMock()
    cursor.rowcount = 5
    assert sweeps.sweep_draft_to_expired(cursor) == 5


def test_sweep_expired_uses_provided_now():
    cursor = MagicMock()
    cursor.rowcount = 2
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
    sweeps.sweep_draft_to_expired(cursor, now=now)
    params = cursor.execute.call_args[0][1]
    assert params == (now, now)


def test_sweep_expired_zero_when_no_matches():
    cursor = MagicMock()
    cursor.rowcount = 0
    assert sweeps.sweep_draft_to_expired(cursor) == 0
