"""Flow controller for Tier 1 questionnaire.

Thin wrapper over skip_logic.filter_questions_for_session which already
composes role visibility + cascade-aware skip logic in document order.
"""

from __future__ import annotations

from typing import Any, Optional
from types import SimpleNamespace

from questionnaire.question_bank import QUESTIONS
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


def _all_wrapped() -> list[SimpleNamespace]:
    """Return every question in bank order, wrapped for attribute access."""
    return [_as_ns(q) for q in QUESTIONS]


def questions_visible_to_role(
    role: str,
    answered_by_id: dict[str, Any],
) -> list[SimpleNamespace]:
    """Return every question the role can see, given current answers.

    Delegates to skip_logic.filter_questions_for_session which handles
    role visibility, skip-logic evaluation, and cascade tracking in one
    pass. Preserves question bank document order.
    """
    result = filter_questions_for_session(
        _all_wrapped(), role, answered_by_id
    )
    return result.visible


def next_unanswered_question(
    role: str,
    answered_by_id: dict[str, Any],
) -> Optional[SimpleNamespace]:
    """Return the next question the role must answer, or None if complete."""
    visible = questions_visible_to_role(role, answered_by_id)
    for q_ns in visible:
        if q_ns.id not in answered_by_id:
            return q_ns
    return None


def progress_for_role(
    role: str,
    answered_by_id: dict[str, Any],
) -> tuple[int, int, float]:
    """Return (completed_count, visible_count, percentage).

    Percentage is a float in [0.0, 100.0]. Returns (0, 0, 0.0) if visible
    count is 0 to avoid ZeroDivisionError.
    """
    visible = questions_visible_to_role(role, answered_by_id)
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
    return q_ns.id == "T1-H-006"


def is_complete(role: str, answered_by_id: dict[str, Any]) -> bool:
    """Return True if the role has answered every visible question."""
    return next_unanswered_question(role, answered_by_id) is None


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
    }
    if question_type not in mapping:
        raise ValueError(
            f"Unknown question_type '{question_type}' — "
            f"expected one of {sorted(mapping)}"
        )
    return mapping[question_type]
