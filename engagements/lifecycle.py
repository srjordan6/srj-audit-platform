"""OD-18 snapshot lifecycle state transitions — pure functions, no DB.

Implements the four-state one-way state machine defined in OD-18 §2:
Draft → Editable → Locked → Expired (with Draft → Expired as a terminal
branch when 180-day outer cap is reached without generation).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# State constants (must match Postgres snapshot_state enum)
# ---------------------------------------------------------------------------

DRAFT = "Draft"
EDITABLE = "Editable"
LOCKED = "Locked"
EXPIRED = "Expired"

ALL_STATES = frozenset({DRAFT, EDITABLE, LOCKED, EXPIRED})


# ---------------------------------------------------------------------------
# OD-18 timing constants
# ---------------------------------------------------------------------------

EDIT_WINDOW_HOURS = 168  # 7 days per OD-18 §2.2
DRAFT_EXPIRY_DAYS = 180  # per OD-18 §4


# ---------------------------------------------------------------------------
# Valid transitions (one-way per OD-18 §2)
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    DRAFT: frozenset({EDITABLE, EXPIRED}),
    EDITABLE: frozenset({LOCKED}),
    LOCKED: frozenset(),
    EXPIRED: frozenset(),
}


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def is_writable(state: str) -> bool:
    return state in (DRAFT, EDITABLE)


def is_terminal(state: str) -> bool:
    return state in (LOCKED, EXPIRED)


def is_valid_transition(from_state: str, to_state: str) -> bool:
    if from_state not in ALL_STATES or to_state not in ALL_STATES:
        return False
    return to_state in VALID_TRANSITIONS[from_state]


# ---------------------------------------------------------------------------
# Timestamp computation
# ---------------------------------------------------------------------------


def compute_window_end(first_generation_ts: datetime) -> datetime:
    return first_generation_ts + timedelta(hours=EDIT_WINDOW_HOURS)


def compute_expiry(purchase_ts: datetime) -> datetime:
    return purchase_ts + timedelta(days=DRAFT_EXPIRY_DAYS)


# ---------------------------------------------------------------------------
# Transition decisions
# ---------------------------------------------------------------------------


def decide_first_generation_transition(current_state: str) -> str:
    if current_state != DRAFT:
        raise ValueError(
            f"First generation only valid from Draft, got '{current_state}'"
        )
    return EDITABLE


def decide_regeneration_transition(current_state: str) -> str:
    if current_state != EDITABLE:
        raise ValueError(
            f"Regeneration only valid from Editable, got '{current_state}'"
        )
    return EDITABLE


def decide_window_expiry_transition(
    current_state: str,
    window_end_ts: Optional[datetime],
    now: datetime,
) -> Optional[str]:
    if current_state != EDITABLE:
        return None
    if window_end_ts is None:
        return None
    if now >= window_end_ts:
        return LOCKED
    return None


def decide_draft_expiry_transition(
    current_state: str,
    purchase_ts: datetime,
    now: datetime,
) -> Optional[str]:
    if current_state != DRAFT:
        return None
    if now >= compute_expiry(purchase_ts):
        return EXPIRED
    return None


# ---------------------------------------------------------------------------
# Countdown formatting (Sprint D PR 5)
# ---------------------------------------------------------------------------


def format_countdown(
    window_end_ts: Optional[datetime],
    now: datetime,
) -> Optional[str]:
    """Return human-readable time remaining, or None if expired/absent.

    Formats:
      >=24h    "Edit window closes in X days, Y hours"
      <24h,>=1h "Edit window closes in Y hours, Z minutes"
      <1h     "Edit window closes in Z minutes"
      <=0    None (window already closed — caller should show locked banner)
    """
    if window_end_ts is None:
        return None
    delta = window_end_ts - now
    total_seconds = delta.total_seconds()
    if total_seconds <= 0:
        return None
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    if days > 0:
        d_unit = "day" if days == 1 else "days"
        h_unit = "hour" if hours == 1 else "hours"
        return f"Edit window closes in {days} {d_unit}, {hours} {h_unit}"
    if hours > 0:
        h_unit = "hour" if hours == 1 else "hours"
        m_unit = "minute" if minutes == 1 else "minutes"
        return f"Edit window closes in {hours} {h_unit}, {minutes} {m_unit}"
    m_unit = "minute" if minutes == 1 else "minutes"
    return f"Edit window closes in {minutes} {m_unit}"


# ---------------------------------------------------------------------------
# Full transition record — what a state-changing job should apply
# ---------------------------------------------------------------------------


def build_first_generation_update(
    current_state: str,
    now: Optional[datetime] = None,
) -> dict:
    next_state = decide_first_generation_transition(current_state)
    if now is None:
        now = datetime.now(timezone.utc)
    return {
        "snapshot_state": next_state,
        "first_generation_timestamp": now,
        "window_end_timestamp": compute_window_end(now),
        "generation_count": 1,
    }


def build_regeneration_update(current_state: str) -> dict:
    decide_regeneration_transition(current_state)
    return {"generation_count__increment": 1}


def build_lock_update(
    current_state: str,
    window_end_ts: Optional[datetime],
    now: Optional[datetime] = None,
    report_of_record_id: Optional[str] = None,
    report_of_record_pdf_hash: Optional[str] = None,
) -> Optional[dict]:
    if now is None:
        now = datetime.now(timezone.utc)
    next_state = decide_window_expiry_transition(current_state, window_end_ts, now)
    if next_state is None:
        return None
    return {
        "snapshot_state": next_state,
        "lock_timestamp": now,
        "report_of_record_id": report_of_record_id,
        "report_of_record_pdf_hash": report_of_record_pdf_hash,
    }


def build_expiry_update(
    current_state: str,
    purchase_ts: datetime,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    if now is None:
        now = datetime.now(timezone.utc)
    next_state = decide_draft_expiry_transition(current_state, purchase_ts, now)
    if next_state is None:
        return None
    return {
        "snapshot_state": next_state,
        "expiry_timestamp": now,
    }
