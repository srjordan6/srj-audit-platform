"""Flow controller logic for Tier 1 questionnaire.

Pure functions that determine the next question a respondent should see
given their role, current answers, and question bank state. No DB access;
no Django session state. All persistence handled by views.py.

Design contract
---------------
- Question bank is the source of truth (questionnaire.question_bank.QUESTIONS).
- Skip logic is evaluated via questionnaire.skip_logic (existing module).
- Role visibility is evaluated inline (simple set membership).
- Question ordering follows question_bank list order (sequence lock).

Public API
----------
- next_unanswered_question(role, answered_ids, skipped_ids) -> question or None
- questions_visible_to_role(role, answered_by_id) -> list of question dicts
- progress_for_role(role, answered_by_id) -> (completed_count, visible_count, pct)
- is_terminal(question) -> bool  (True if T1-H-006 or last visible question)
"""

from __future__ import annotations

from typing import Any, Optional
from types import SimpleNamespace

from questionnaire.question_bank import QUESTIONS
from questionnaire.skip_logic import should_skip


ROLE_ALL_TOKEN = "ALL"


def _as_ns(question: Any) -> SimpleNamespace:
    """Wrap a dict-shaped question in SimpleNamespace for attribute access.

    Idempotent: if already a SimpleNamespace, returned unchanged.
    Mirrors the pattern used in scoring/engine.py so callers of this
    module can rely on attribute access without knowing the underlying shape.
    """
    if isinstance(question, SimpleNamespace):
        return question
    return SimpleNamespace(**question)


def _role_visible(question_ns: SimpleNamespace, role: str) -> bool:
    """Return True if this question is visible to the given role.

    role_visibility is a list on the question. Empty list or containing
    ROLE_ALL_TOKEN means visible to every role.
    """
    visibility = getattr(question_ns, "role_visibility", None)
    if not visibility:
        return True
    if ROLE_ALL_TOKEN in visibility:
        return True
    return role in visibility


def questions_visible_to_role(
    role: str,
    answered_by_id: dict[str, Any],
) -> list[SimpleNamespace]:
    """Return every question the role can see, given current answers.

    Filters by (a) role visibility, then (b) skip logic. Preserves question
    bank ordering. Used by progress calculation and terminal detection.

    Args:
        role: Role code (e.g., 'CEO', 'CFO'). Matches values stored on
            respondent.role.
        answered_by_id: Mapping of question_id -> answer_value dict.
            Used by skip_logic to evaluate conditions.

    Returns:
        Ordered list of SimpleNamespace-wrapped questions the role must
        answer, after skip-logic filtering.
    """
    result: list[SimpleNamespace] = []
    for q in QUESTIONS:
        q_ns = _as_ns(q)
        if not _role_visible(q_ns, role):
            continue
        if should_skip(q_ns, answered_by_id):
            continue
        result.append(q_ns)
    return result


def next_unanswered_question(
    role: str,
    answered_by_id: dict[str, Any],
) -> Optional[SimpleNamespace]:
    """Return the next question the role must answer, or None if complete.

    Iterates the role-visible, skip-filtered question list in order and
    returns the first whose id is not present in answered_by_id.

    Args:
        role: Role code.
        answered_by_id: Mapping of question_id -> answer_value dict.

    Returns:
        The next question (SimpleNamespace), or None if all visible
        questions have been answered.
    """
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

    Percentage is a float in [0.0, 100.0]. If visible_count is 0 (which
    should not happen in practice — every role has at least Section A),
    returns (0, 0, 0.0) to avoid ZeroDivisionError.

    Skip-logic effects are baked in: visible_count reflects only questions
    that remain visible given current answers. Answering a question may
    hide downstream questions, changing both the numerator and denominator.
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

    Currently only T1-H-006 (the optional closing text field). Kept as a
    named predicate so PR 7's session-close logic has a stable hook.
    """
    q_ns = _as_ns(question)
    return q_ns.id == "T1-H-006"


def is_complete(role: str, answered_by_id: dict[str, Any]) -> bool:
    """Return True if the role has answered every visible question.

    Equivalent to next_unanswered_question(role, answered_by_id) is None
    but named for clarity in view code.
    """
    return next_unanswered_question(role, answered_by_id) is None


def partial_template_for_type(question_type: str) -> str:
    """Return the partial template path for a question type.

    Maps the 8 question types produced by the Tier 1 question bank to
    the 6 partial templates delivered in Sprint C PRs 1-5. SS/YN/NR all
    map to _question_single_select.html per PR 2's coverage decision.

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
