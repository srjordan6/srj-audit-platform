"""Flow controller for Tier 1 questionnaire.

Thin wrapper over skip_logic.filter_questions_for_session which already
composes role visibility + cascade-aware skip logic in document order.
"""

from __future__ import annotations

from typing import Any, Optional
from types import SimpleNamespace

from questionnaire.question_bank import QUESTIONS

# Instruments (Part B / AIITSA spec S.13): which question bank a
# respondent walks. Pillar I is "tier_1"; the AI IT Security Audit(TM) is
# "aiitsa"; "combined" is both, Pillar I first. engagements.instrument
# names it; everything below takes it as a keyword with the Pillar I
# default, so existing callers are unchanged.
INSTRUMENTS = ("tier_1", "aiitsa", "combined")


def bank_for(instrument: str | None = "tier_1") -> list[dict]:
    instrument = instrument or "tier_1"
    if instrument == "tier_1":
        return QUESTIONS
    from questionnaire.aiitsa_question_bank import AIITSA_QUESTIONS
    if instrument == "aiitsa":
        return AIITSA_QUESTIONS
    if instrument == "combined":
        return list(QUESTIONS) + list(AIITSA_QUESTIONS)
    raise ValueError(f"unknown instrument {instrument!r}")
from questionnaire.skip_logic import filter_questions_for_session


def _as_ns(question: Any) -> SimpleNamespace:
    """Wrap dict-shaped question in SimpleNamespace for attribute access.

    Idempotent: if already a SimpleNamespace, returned unchanged.
    Matches the pattern in scoring/engine.py so skip_logic (which uses
    attribute access) can consume question_bank's dict-shaped entries.
    """
    if isinstance(question, SimpleNamespace):
        return question
    return SimpleNamespace(**question)


def _all_wrapped(instrument: str | None = "tier_1") -> list[SimpleNamespace]:
    """Return every ACTIVE question in bank order, wrapped for attribute access.

    Questions with is_active=False are dropped here — the single choke
    point for runtime visibility. Downstream (skip_logic, next_unanswered,
    previous/forward navigation, scoring wiring by ID) all inherit this.
    """
    active = [q for q in bank_for(instrument) if q.get("is_active", True)]
    return [_as_ns(q) for q in active]


def questions_visible_to_role(
    role: str,
    answered_by_id: dict[str, Any],
    instrument: str | None = "tier_1",
) -> list[SimpleNamespace]:
    """Return every question the role can see, given current answers.

    Delegates to skip_logic.filter_questions_for_session which handles
    role visibility, skip-logic evaluation, and cascade tracking in one
    pass. Preserves question bank document order.
    """
    result = filter_questions_for_session(
        _all_wrapped(instrument), role, answered_by_id
    )
    if instrument != "combined":
        return result.visible
    # OD-19: a security question that asks what a governance question this
    # respondent sees already asked is not asked twice (questionnaire.overlap).
    from questionnaire.overlap import skipped_for
    ids = {q.id for q in result.visible}
    drop = skipped_for(ids)
    return [q for q in result.visible if q.id not in drop] if drop else result.visible


def next_unanswered_question(
    role: str,
    answered_by_id: dict[str, Any],
    instrument: str | None = "tier_1",
) -> Optional[SimpleNamespace]:
    """Return the next question the role must answer, or None if complete."""
    visible = questions_visible_to_role(role, answered_by_id, instrument)
    for q_ns in visible:
        if q_ns.id not in answered_by_id:
            return q_ns
    return None


def progress_for_role(
    role: str,
    answered_by_id: dict[str, Any],
    instrument: str | None = "tier_1",
) -> tuple[int, int, float]:
    """Return (completed_count, visible_count, percentage).

    Percentage is a float in [0.0, 100.0]. Returns (0, 0, 0.0) if visible
    count is 0 to avoid ZeroDivisionError.
    """
    visible = questions_visible_to_role(role, answered_by_id, instrument)
    visible_count = len(visible)
    if visible_count == 0:
        return (0, 0, 0.0)
    completed_count = sum(1 for q in visible if q.id in answered_by_id)
    pct = (completed_count / visible_count) * 100.0
    return (completed_count, visible_count, pct)


def is_terminal(question: Any) -> bool:
    """Return True if this question terminates the questionnaire.

    Only T1-H-006 (the optional closing text field). Kept as a named
    predicate so PR 7's session-close logic has a stable hook.
    """
    q_ns = _as_ns(question)
    return q_ns.id in ("T1-H-006", "AIITSA-INV-003")


def is_complete(role: str, answered_by_id: dict[str, Any], instrument: str | None = "tier_1") -> bool:
    """Return True if the role has answered every visible question."""
    return next_unanswered_question(role, answered_by_id, instrument) is None


def partial_template_for(question: Any) -> str:
    """Partial for a question object. Same as partial_template_for_type
    except that a MATRIX whose extended_metadata.matrix_input_pattern is
    single_selection_per_row (T1-F-002) renders the choice partial: one
    radio group per row across the columns. Routing by type alone sent it
    to the grid partial, which drew two radios (selected / not_selected)
    in every one of the 28 cells (defect C2, 2026-09-28)."""
    qtype = getattr(question, "question_type", None) or (question.get("question_type") if isinstance(question, dict) else "")
    ext = getattr(question, "extended_metadata", None)
    if ext is None and isinstance(question, dict):
        ext = question.get("extended_metadata")
    ext = ext or {}
    if qtype == "MATRIX" and ext.get("matrix_input_pattern") == "single_selection_per_row":
        return "questionnaire/partials/_question_matrix_choice.html"
    return partial_template_for_type(qtype)


def partial_template_for_type(question_type: str) -> str:
    """Return the partial template path for a question type.

    Maps 8 question types to 6 partials delivered in Sprint C PRs 1-5.
    SS/YN/NR share _question_single_select.html per PR 2's coverage
    decision.

    Raises ValueError on unknown type — flow controller should never
    encounter one, but explicit failure beats silent template-not-found.
    """
    mapping = {
        "SS": "questionnaire/partials/_question_single_select.html",
        "YN": "questionnaire/partials/_question_single_select.html",
        "NR": "questionnaire/partials/_question_single_select.html",
        "MS": "questionnaire/partials/_question_multi_select.html",
        "L5": "questionnaire/partials/_question_likert.html",
        "TEXT": "questionnaire/partials/_question_text.html",
        "RANK": "questionnaire/partials/_question_rank.html",
        "MATRIX": "questionnaire/partials/_question_matrix_grid.html",
        "MATRIX_CHOICE": "questionnaire/partials/_question_matrix_choice.html",
        "TOOL_INVENTORY": "questionnaire/partials/_question_tool_inventory.html",
        "LAW_INVENTORY": "questionnaire/partials/_question_law_inventory.html",
    }
    if question_type not in mapping:
        raise ValueError(
            f"Unknown question_type '{question_type}' — "
            f"expected one of {sorted(mapping)}"
        )
    return mapping[question_type]
