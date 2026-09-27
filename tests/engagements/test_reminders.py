"""Automatic reminder schedule (Part B-1 S.4.4)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone as tz

from engagements import reminders


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=tz.utc)


def _row(days_old, sent):
    return ("rid-%d-%d" % (days_old, sent), NOW - timedelta(days=days_old), sent)


def test_nothing_due_before_day_three():
    due = reminders.due_respondents(_Cursor([_row(2, 0)]), now=NOW)
    assert due == []


def test_first_reminder_at_day_three():
    assert reminders.due_respondents(_Cursor([_row(3, 0)]), now=NOW) == [("rid-3-0", 1)]


def test_second_reminder_only_after_day_seven():
    assert reminders.due_respondents(_Cursor([_row(5, 1)]), now=NOW) == []
    assert reminders.due_respondents(_Cursor([_row(7, 1)]), now=NOW) == [("rid-7-1", 2)]


def test_a_buyer_nudge_counts_as_a_reminder():
    # buyer already nudged twice: only the day-14 reminder remains
    assert reminders.due_respondents(_Cursor([_row(8, 2)]), now=NOW) == []
    assert reminders.due_respondents(_Cursor([_row(14, 2)]), now=NOW) == [("rid-14-2", 3)]


def test_one_reminder_per_run_even_if_far_behind():
    # 20 days old, never reminded: send #1 now, not three at once
    assert reminders.due_respondents(_Cursor([_row(20, 0)]), now=NOW) == [("rid-20-0", 1)]


def test_cap_is_three():
    assert reminders.due_respondents(_Cursor([_row(60, 3)]), now=NOW) == []
