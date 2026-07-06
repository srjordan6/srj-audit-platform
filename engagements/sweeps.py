"""OD-18 lifecycle background sweeps.

Pure cursor-based functions that apply state transitions on scheduled runs:
- sweep_editable_to_locked: Editable → Locked when window_end has passed
- sweep_draft_to_expired: Draft → Expired when 180-day cap has passed

Both functions return the count of engagements transitioned. Callers wrap
in transactions and schedule via management commands (see
engagements/management/commands/).

Note: sweep_editable_to_locked leaves report_of_record_id and
report_of_record_pdf_hash NULL. Wiring those requires the report generation
pipeline to be triggered (Sprint E). For MVP, lock_timestamp and
snapshot_state are set atomically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def sweep_editable_to_locked(cursor, now: Optional[datetime] = None) -> int:
    """Transition Editable engagements past window_end to Locked.

    Idempotent: only Editable rows are affected. Returns transition count.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cursor.execute(
        "UPDATE engagements "
        "SET snapshot_state = 'Locked', lock_timestamp = %s "
        "WHERE snapshot_state = 'Editable' "
        "AND window_end_timestamp <= %s",
        (now, now),
    )
    return cursor.rowcount


def sweep_draft_to_expired(cursor, now: Optional[datetime] = None) -> int:
    """Transition Draft engagements past 180-day cap to Expired.

    Cap is measured from engagements.created_at (purchase timestamp).
    Returns transition count.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cursor.execute(
        "UPDATE engagements "
        "SET snapshot_state = 'Expired', expiry_timestamp = %s "
        "WHERE snapshot_state = 'Draft' "
        "AND created_at <= %s - INTERVAL '180 days'",
        (now, now),
    )
    return cursor.rowcount
