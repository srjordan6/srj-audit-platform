"""OD-18 snapshot lifecycle state transitions — pure functions, no DB.

Implements the four-state one-way state machine defined in OD-18 §2:
Draft → Editable → Locked → Expired (with Draft → Expired as a terminal
branch when 180-day outer cap is reached without generation).

State constants match the Postgres ENUM `snapshot_state` created in
Sprint D PR 1: 'Draft', 'Editable', 'Locked', 'Expired'.
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
DRAFT_EXPIRY_DAYS = 180  # per OD-18 §4 (chargeback-window-aligned)


# ---------------------------------------------------------------------------
# Valid transitions (one-way per OD-18 §2)
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    DRAFT: frozenset({EDITABLE, EXPIRED}),
    EDITABLE: frozenset({LOCKED}),
    LOCKED: frozenset(),      # terminal
    EXPIRED: frozenset(),     # terminal
}


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def is_writable(state: str) -> bool:
    """Return True if questionnaire responses can still be created/updated.

    Only Draft and Editable allow writes. Locked and Expired are terminal.
    """
    return state in (DRAFT, EDITABLE)


def is_terminal(state: str) -> bool:
    """Return True if state cannot transition further."""
    return state in (LOCKED, EXPIRED)


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """Return True if from_state → to_state is a valid one-way transition."""
    if from_state not in ALL_STATES or to_state not in ALL_STATES:
        return False
    return to_state in VALID_TRANSITIONS[from_state]


# ---------------------------------------------------------------------------
# Timestamp computation
# ---------------------------------------------------------------------------


def compute_window_end(first_generation_ts: datetime) -> datetime:
    """Return the timestamp at which Editable → Locked auto-transitions."""
    return first_generation_ts + timedelta(hours=EDIT_WINDOW_HOURS)


def compute_expiry(purchase_ts: datetime) -> datetime:
    """Return the timestamp at which un-generated Drafts hard-expire."""
    return purchase_ts + timedelta(days=DRAFT_EXPIRY_DAYS)


# ---------------------------------------------------------------------------
# Transition decisions
# ---------------------------------------------------------------------------


def decide_first_generation_transition(current_state: str) -> str:
    """Compute the next state when the buyer generates their first report.

    Only valid from Draft. Any other current state raises ValueError —
    caller should have gated on is_writable() and generation_count == 0.
    """
    if current_state != DRAFT:
        raise ValueError(
            f"First generation only valid from Draft, got '{current_state}'"
        )
    return EDITABLE


def decide_regeneration_transition(current_state: str) -> str:
    """Compute the next state when the buyer regenerates within the window.

    Editable stays Editable — only generation_count increments, timestamps
    do not reset. Any state other than Editable raises ValueError.
    """
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
    """Compute the transition when the 7-day edit window sweep runs.

    Returns LOCKED if state is Editable and now >= window_end_ts. Returns
    None (no transition) otherwise. Never raises — sweep is idempotent.
    """
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
    """Compute the transition when the 180-day Draft sweep runs.

    Returns EXPIRED if state is Draft and now >= purchase_ts + 180 days.
    Returns None (no transition) otherwise. Never raises.
    """
    if current_state != DRAFT:
        return None
    if now >= compute_expiry(purchase_ts):
        return EXPIRED
    return None


# ---------------------------------------------------------------------------
# Full transition record — what a state-changing job should apply
# ---------------------------------------------------------------------------


def build_first_generation_update(
    current_state: str,
    now: Optional[datetime] = None,
) -> dict:
    """Return the field updates to apply on a first-report-generation event.

    Callers pass this dict to their DB layer to UPDATE the engagement row.
    Sets first_generation_timestamp, window_end_timestamp, snapshot_state,
    and increments generation_count.
    """
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
    """Return field updates for a regeneration event (increment count only).

    generation_count is expressed as a SQL expression so the caller knows
    to translate it as `generation_count = generation_count + 1` rather
    than reading and rewriting a cached value.
    """
    decide_regeneration_transition(current_state)  # raises if invalid
    return {"generation_count__increment": 1}


def build_lock_update(
    current_state: str,
    window_end_ts: Optional[datetime],
    now: Optional[datetime] = None,
    report_of_record_id: Optional[str] = None,
    report_of_record_pdf_hash: Optional[str] = None,
) -> Optional[dict]:
    """Return the field updates to apply on Editable→Locked transition.

    Returns None if the transition should not fire (state not Editable,
    or window not yet expired). Locks are irreversible so callers must
    pass the final report_of_record_id and report_of_record_pdf_hash.
    """
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
    """Return the field updates to apply on Draft→Expired transition.

    Returns None if the sweep should not fire (state not Draft, or not
    past the 180-day cap).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    next_state = decide_draft_expiry_transition(current_state, purchase_ts, now)
    if next_state is None:
        return None
    return {
        "snapshot_state": next_state,
        "expiry_timestamp": now,
    }
