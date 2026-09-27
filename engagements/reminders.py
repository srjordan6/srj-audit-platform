"""Automatic respondent reminders (Part B-1 S.4.4).

Schedule relative to the invitation: day 3, day 7, day 14. Each respondent
gets at most one reminder per run and at most three automatic reminders in
total; buyer nudges from the dashboard share the same counter, so a buyer
who has already chased someone does not cause a fourth email.

Runs on demand from an authenticated endpoint (POST /e/reminders/run/,
header X-Reminder-Key) that the srj-platform-monitor Worker calls from a
daily cron. The Worker is the clock; Django is the policy. No Celery beat,
no RQ scheduler, nothing new to keep alive on the PC.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from engagements.invitations import nudge

logger = logging.getLogger(__name__)

# (minimum age of the invitation, reminder number it satisfies)
SCHEDULE = [(timedelta(days=3), 1), (timedelta(days=7), 2), (timedelta(days=14), 3)]
MAX_AUTOMATIC = 3


def due_respondents(cursor, now=None) -> list[tuple[str, int]]:
    """[(respondent_id, reminder_number_due)] for every respondent who has
    not finished, has not opted out, whose engagement is still open, and
    who is past the next threshold of the schedule."""
    now = now or timezone.now()
    cursor.execute(
        """
        SELECT r.id::text, r.created_at, coalesce(r.reminder_count, 0)
        FROM respondents r
        JOIN engagements e ON e.id = r.engagement_id
        WHERE e.tier IN ('tier_2', 'tier_3')
          AND e.status = 'in_progress'
          AND e.coverage_met_at IS NULL
          AND coalesce(r.status, 'invited') IN ('invited', 'in_progress')
          AND coalesce(r.reminders_disabled, false) = false
          AND coalesce(r.reminder_count, 0) < %s
        """,
        [MAX_AUTOMATIC],
    )
    due = []
    for rid, created, sent in cursor.fetchall():
        age = now - created
        # the highest schedule step this respondent has aged past
        reached = max((n for delta, n in SCHEDULE if age >= delta), default=0)
        if reached > sent:
            due.append((rid, sent + 1))
    return due


def run(cursor) -> dict:
    """Send every reminder that is due. Returns counts for the caller's log."""
    result = {"due": 0, "sent": 0, "skipped": 0, "failed": 0, "errors": []}
    for rid, number in due_respondents(cursor):
        result["due"] += 1
        try:
            ok, msg = nudge(cursor, rid)
        except Exception as exc:  # noqa: BLE001 - one bad address must not stop the batch
            ok, msg = False, str(exc)
        if ok:
            result["sent"] += 1
        elif "24 hours" in msg or "cooldown" in msg.lower():
            result["skipped"] += 1
        else:
            result["failed"] += 1
            result["errors"].append({"respondent_id": rid, "reminder": number, "error": msg[:200]})
    cursor.execute(
        "INSERT INTO events (event_type, payload) VALUES ('respondent_reminder_run', %s::jsonb)",
        [__import__("json").dumps(result)],
    )
    logger.info("respondent reminders: %s", result)
    return result
