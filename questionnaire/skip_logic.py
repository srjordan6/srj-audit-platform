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
from typing import Any, Iterable, Optional

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
# New-format ({combine, conditions}) reasons. In the new format the
# conditions describe when to SKIP, so "met" hides and "not met" shows —
# distinct codes keep audit trails unambiguous versus the legacy polarity.
REASON_SKIP_CONDITION_MET = "skip_condition_met"
REASON_SKIP_CONDITION_NOT_MET = "skip_condition_not_met"


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
# New-format evaluator: {"combine": "any"|"all", "conditions": [...]}
# ----------------------------------------------------------------------------
# SEMANTICS (verified against all 15 uses in the bank, 2026-07-19):
# conditions describe when to SKIP the question — the opposite polarity of
# the legacy format. Example: T1-B-002 "What does that inventory include?"
# has condition {type: answer_equals, question_id: T1-B-001,
# answer_value: ["No", "Don't know"]} — if the respondent said no inventory
# exists, asking what it includes is nonsense, so the question is skipped.
#
# Condition types (answer_value is a list in all current data; scalars
# tolerated):
#   answer_equals           — response matches ANY of the listed values
#                             (multi-select response: any intersection)
#   answer_does_not_include — response contains NONE of the listed values
#   answer_only_includes    — response is non-empty and every selected item
#                             is within the listed values
#
# combine: "any" — skip if ANY condition is true (the only value in current
# data); "all" — skip only if ALL conditions are true.
#
# Unanswered dependency: permissive-show, matching the legacy contract. If
# a referenced question was itself skipped (cascade), its absence from
# `responses` yields the same permissive-show — acceptable because every
# current dependency target has no skip_logic of its own.


def _extract_answer(raw: Any) -> Any:
    """Normalize a stored answer_value into a scalar or list for comparison.

    Stored shapes: {"selected": "No"}, {"selected": [..], "other": ".."},
    {"ranked": [..]}, {"text": ".."}, or bare scalars from legacy tests.
    """
    if isinstance(raw, dict):
        if "selected" in raw:
            return raw["selected"]
        if "ranked" in raw:
            return raw["ranked"]
        if "text" in raw:
            return raw["text"]
    return raw


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _eval_condition(cond: dict, responses: dict[str, Any]) -> Optional[bool]:
    """Evaluate one new-format condition.

    Returns True/False, or None when the referenced question has no
    answer yet (caller treats None as not-evaluable → permissive show).
    """
    dep_id = cond.get("question_id")
    ctype = cond.get("type")
    values = _as_list(cond.get("answer_value"))

    if not dep_id or not ctype:
        logger.warning("Malformed skip-logic condition: %r", cond)
        return None
    if dep_id not in responses:
        return None

    answer = _extract_answer(responses[dep_id])
    answer_items = _as_list(answer)

    if ctype == "answer_equals":
        # Any overlap between the respondent's answer and the value list.
        return any(item in values for item in answer_items)
    if ctype == "answer_does_not_include":
        return not any(item in values for item in answer_items)
    if ctype == "answer_only_includes":
        return len(answer_items) > 0 and all(
            item in values for item in answer_items
        )

    logger.warning("Unknown skip-logic condition type %r", ctype)
    return None


def evaluate_new_format(
    sl: dict,
    responses: dict[str, Any],
) -> SkipDecision:
    """Evaluate a {combine, conditions} skip_logic block.

    Conditions describe when to SKIP. Non-evaluable conditions (missing
    answers, malformed) are dropped; if none remain, permissive-show.
    """
    conditions = sl.get("conditions") or []
    combine = (sl.get("combine") or "any").lower()

    results = [_eval_condition(c, responses) for c in conditions]
    evaluable = [r for r in results if r is not None]

    if not evaluable:
        return SkipDecision.show_(REASON_DEPENDENCY_UNANSWERED)

    should_skip = (
        all(evaluable) if combine == "all" else any(evaluable)
    )
    return (
        SkipDecision.hide(REASON_SKIP_CONDITION_MET)
        if should_skip
        else SkipDecision.show_(REASON_SKIP_CONDITION_NOT_MET)
    )


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

    # New-format skip_logic: {combine, conditions[]} — conditions describe
    # when to SKIP. Fully evaluated as of 2026-07-19 (was permissive-show).
    if "conditions" in sl:
        return evaluate_new_format(sl, responses)

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

    _NEW_CONDITION_TYPES = {
        "answer_equals", "answer_does_not_include", "answer_only_includes",
    }

    for q in questions:
        sl = q.skip_logic
        if not sl:
            continue

        # New-format {combine, conditions} validation.
        if "conditions" in sl:
            combine = (sl.get("combine") or "any").lower()
            if combine not in ("any", "all"):
                errors.append(f"{q.id}: unknown combine {combine!r}")
            conditions = sl.get("conditions") or []
            if not conditions:
                errors.append(f"{q.id}: skip_logic has empty conditions")
            for i, cond in enumerate(conditions):
                dep_id = cond.get("question_id")
                ctype = cond.get("type")
                if not dep_id:
                    errors.append(f"{q.id}: condition[{i}] missing question_id")
                elif dep_id not in by_id:
                    errors.append(
                        f"{q.id}: condition[{i}] references unknown "
                        f"question {dep_id!r}"
                    )
                elif order_index[dep_id] >= order_index[q.id]:
                    errors.append(
                        f"{q.id}: condition[{i}] forward/self reference "
                        f"to {dep_id}"
                    )
                if ctype not in _NEW_CONDITION_TYPES:
                    errors.append(
                        f"{q.id}: condition[{i}] unknown type {ctype!r}"
                    )
                if "answer_value" not in cond:
                    errors.append(
                        f"{q.id}: condition[{i}] missing answer_value"
                    )
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
