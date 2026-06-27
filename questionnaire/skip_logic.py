"""
skip_logic — Skip-logic evaluator for the SRJ AI Audit Platform.

Decides which questions to surface to a given respondent based on:

  1. Role visibility (the question's `role_visibility` list)
  2. Skip-logic conditions referencing earlier responses

Implements the three operators referenced in question_bank.py:

    answer_equals            — 12 uses
    answer_does_not_include  —  3 uses
    answer_only_includes     —  1 use

This module is pure logic: no Django imports, no DB. It can be exercised
in unit tests without bootstrapping the ORM.

USAGE
-----

    from questionnaire.question_bank import QUESTIONS, get_questions_for_role
    from questionnaire.skip_logic import filter_questions_for_session

    # Walk a respondent's session
    role = "CEO"
    responses = {"T1-A-001": "yes", "T1-A-002": ["AI Risk Council"]}

    result = filter_questions_for_session(
        questions=QUESTIONS,
        role=role,
        responses=responses,
    )

    for q in result.visible:
        print(q.id, q.question_text[:60])

    for qid, reason in result.skipped.items():
        print(f"skipped {qid}: {reason}")

CONTRACT
--------

- Forward references are forbidden. A question's skip_logic.depends_on must
  refer to a question that PRECEDES it in document order. The validator
  enforces this; the runtime walker assumes it.

- Cascade rule: if A is skipped, every question whose skip_logic depends
  on A is also skipped, with reason `dependency_skipped`. This applies
  transitively through chains.

- Missing-response rule: if the runtime is asked about a question whose
  dependency has not yet been answered AND was not skipped, the function
  returns show=True with reason `dependency_unanswered`. This is
  intentionally permissive — the UI should typically only ask after the
  dependency is satisfied, but defensive runtime should not crash.

- Operator semantics live in `_eval_*` functions below.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from questionnaire.question_bank import Question

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Reason codes
# ----------------------------------------------------------------------------
# These strings are stable: they're logged, surfaced in audit trails, and
# inspected by tests. Do not rename without coordinated grep.

REASON_NO_SKIP_LOGIC = "no_skip_logic"
REASON_ROLE_EXCLUDED = "role_excluded"
REASON_DEPENDENCY_SKIPPED = "dependency_skipped"
REASON_DEPENDENCY_UNANSWERED = "dependency_unanswered"
REASON_CONDITION_MET = "condition_met"
REASON_CONDITION_NOT_MET = "condition_not_met"
REASON_UNKNOWN_OPERATOR = "unknown_operator"
REASON_MALFORMED_SKIP_LOGIC = "malformed_skip_logic"


# ----------------------------------------------------------------------------
# Decision record
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class SkipDecision:
    """Result of evaluating a single question."""

    show: bool
    reason: str

    @classmethod
    def show_(cls, reason: str) -> "SkipDecision":
        return cls(show=True, reason=reason)

    @classmethod
    def hide(cls, reason: str) -> "SkipDecision":
        return cls(show=False, reason=reason)


# ----------------------------------------------------------------------------
# Role visibility
# ----------------------------------------------------------------------------

ROLE_VISIBILITY_ALL = "all"


def is_visible_to_role(question: Question, role: str) -> bool:
    """Return True if the question's role_visibility includes this role.

    A role_visibility list containing the literal string "all" matches
    every role. An empty/missing list is treated as "all" for safety
    (defensive default).
    """
    rv = question.role_visibility
    if not rv:
        return True
    if ROLE_VISIBILITY_ALL in rv:
        return True
    return role in rv


# ----------------------------------------------------------------------------
# Operator implementations
# ----------------------------------------------------------------------------

def _eval_answer_equals(response: Any, expected: Any) -> bool:
    """True iff response == expected (direct equality)."""
    return response == expected


def _eval_answer_does_not_include(response: Any, value: Any) -> bool:
    """True iff `value` is NOT among the response.

    Multi-select responses are lists/tuples/sets; single-value responses
    are bare scalars. None responses are treated as "does not include
    anything", which is True.
    """
    if response is None:
        return True
    if isinstance(response, (list, tuple, set)):
        return value not in response
    return response != value


def _eval_answer_only_includes(response: Any, allowed: Iterable[Any]) -> bool:
    """True iff every item in `response` is within the `allowed` set.

    For multi-select responses, this is set-containment plus non-emptiness
    (an empty response is not "only A and B" — it's nothing). For single
    scalars, returns True if the response is in `allowed`.
    """
    if response is None:
        return False
    allowed_set = set(allowed)
    if isinstance(response, (list, tuple, set)):
        return len(response) > 0 and set(response).issubset(allowed_set)
    return response in allowed_set


OPERATORS = {
    "answer_equals": _eval_answer_equals,
    "answer_does_not_include": _eval_answer_does_not_include,
    "answer_only_includes": _eval_answer_only_includes,
}


# ----------------------------------------------------------------------------
# Per-question evaluation
# ----------------------------------------------------------------------------

def evaluate_skip_logic(
    question: Question,
    responses: dict[str, Any],
    skipped_ids: set[str],
) -> SkipDecision:
    """Decide whether one question should be shown.

    Parameters
    ----------
    question     : the Question dataclass
    responses    : {question_id: response_value} for questions answered so far
    skipped_ids  : set of question IDs that were skipped earlier in this
                   session (used for cascade detection)

    Does NOT consider role visibility — call `is_visible_to_role` separately,
    or use `filter_questions_for_session` which composes both checks.
    """
    sl = question.skip_logic
    if not sl:
        return SkipDecision.show_(REASON_NO_SKIP_LOGIC)

    depends_on = sl.get("depends_on")
    operator = sl.get("operator")

    if not depends_on or not operator:
        logger.warning("Question %s has malformed skip_logic: %r", question.id, sl)
        return SkipDecision.show_(REASON_MALFORMED_SKIP_LOGIC)

    # Cascade: if the dependency was itself skipped, skip this one too.
    if depends_on in skipped_ids:
        return SkipDecision.hide(REASON_DEPENDENCY_SKIPPED)

    # Dependency not yet answered? Permissive default: show.
    if depends_on not in responses:
        return SkipDecision.show_(REASON_DEPENDENCY_UNANSWERED)

    response = responses[depends_on]

    # answer_only_includes uses a `values` list; the other two use a single
    # `value`. Tolerate both shapes for the list operator in case a writer
    # used `value: [...]` instead of `values: [...]`.
    if operator == "answer_only_includes":
        allowed = sl.get("values")
        if allowed is None:
            v = sl.get("value")
            allowed = v if isinstance(v, (list, tuple, set)) else [v]
        condition_met = _eval_answer_only_includes(response, allowed)
    elif operator in OPERATORS:
        expected = sl.get("value")
        condition_met = OPERATORS[operator](response, expected)
    else:
        logger.warning(
            "Question %s uses unknown skip-logic operator %r", question.id, operator
        )
        return SkipDecision.show_(REASON_UNKNOWN_OPERATOR)

    return (
        SkipDecision.show_(REASON_CONDITION_MET)
        if condition_met
        else SkipDecision.hide(REASON_CONDITION_NOT_MET)
    )


# ----------------------------------------------------------------------------
# Session-level walker
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class FilterResult:
    """Result of processing an entire session."""

    visible: list[Question]
    skipped: dict[str, str]  # {question_id: reason}

    def summary(self) -> str:
        return (
            f"FilterResult(visible={len(self.visible)}, "
            f"skipped={len(self.skipped)})"
        )


def filter_questions_for_session(
    questions: list[Question],
    role: str,
    responses: dict[str, Any],
) -> FilterResult:
    """Walk questions in document order; return the visible subset.

    Cascade-aware: if A is skipped, any question depending on A is skipped
    with reason `dependency_skipped`.

    Role filtering runs first; role-excluded questions get reason
    `role_excluded` and are NOT eligible to be skip-logic dependencies
    (they're simply not part of the session). Their IDs are tracked in
    `skipped` so a downstream question that depends on a role-hidden
    question will cascade-skip.
    """
    visible: list[Question] = []
    skipped: dict[str, str] = {}

    for q in questions:
        if not is_visible_to_role(q, role):
            skipped[q.id] = REASON_ROLE_EXCLUDED
            continue

        decision = evaluate_skip_logic(q, responses, set(skipped.keys()))

        if decision.show:
            visible.append(q)
        else:
            skipped[q.id] = decision.reason

    return FilterResult(visible=visible, skipped=skipped)


# ----------------------------------------------------------------------------
# Validation (offline checks before deployment)
# ----------------------------------------------------------------------------

def validate_all_skip_logic_references(questions: list[Question]) -> list[str]:
    """Return error strings for any structural problems with skip_logic.

    Checks performed:
        - depends_on references a question that exists in the bank
        - depends_on references a question PRECEDING the dependent (no
          forward or self references)
        - operator is one of the recognized three
        - operator-required field is present (`value` or `values`)

    Returns an empty list if all skip_logic references are valid.
    """
    errors: list[str] = []
    by_id = {q.id: q for q in questions}
    order_index = {q.id: i for i, q in enumerate(questions)}

    for q in questions:
        sl = q.skip_logic
        if not sl:
            continue

        depends_on = sl.get("depends_on")
        operator = sl.get("operator")

        if not depends_on:
            errors.append(f"{q.id}: skip_logic missing 'depends_on'")
            continue

        if depends_on not in by_id:
            errors.append(
                f"{q.id}: depends_on references unknown question {depends_on!r}"
            )
            continue

        if order_index[depends_on] >= order_index[q.id]:
            errors.append(
                f"{q.id}: forward or self reference to {depends_on} "
                f"(dependency must precede current question)"
            )

        if not operator:
            errors.append(f"{q.id}: skip_logic missing 'operator'")
        elif operator not in OPERATORS:
            errors.append(f"{q.id}: unknown operator {operator!r}")
        elif operator == "answer_only_includes":
            if "values" not in sl and "value" not in sl:
                errors.append(
                    f"{q.id}: answer_only_includes requires 'values' (or 'value')"
                )
        else:
            if "value" not in sl:
                errors.append(f"{q.id}: operator {operator!r} requires 'value'")

    return errors


def get_skip_logic_dependencies(
    questions: list[Question],
) -> dict[str, str]:
    """Return {question_id: depends_on_id} for every question with skip_logic.

    Useful for building a DAG visualization or for cascade impact analysis
    (e.g. "if I change T1-A-001, which downstream questions are affected?").
    """
    deps: dict[str, str] = {}
    for q in questions:
        if q.skip_logic:
            depends_on = q.skip_logic.get("depends_on")
            if depends_on:
                deps[q.id] = depends_on
    return deps


def get_downstream_questions(
    target_id: str,
    questions: list[Question],
) -> list[str]:
    """Return all question IDs that depend (directly or transitively) on target_id.

    Walks the dependency graph in topological order. Useful for impact
    analysis when editing a single question — e.g. "if I rephrase T1-A-001,
    which other questions might need re-review?".
    """
    deps = get_skip_logic_dependencies(questions)
    # Invert: depends_on -> [list of dependents]
    inverted: dict[str, list[str]] = {}
    for q_id, dep_id in deps.items():
        inverted.setdefault(dep_id, []).append(q_id)

    visited: set[str] = set()
    stack = [target_id]
    while stack:
        current = stack.pop()
        for dependent in inverted.get(current, []):
            if dependent not in visited:
                visited.add(dependent)
                stack.append(dependent)
    return sorted(visited)
