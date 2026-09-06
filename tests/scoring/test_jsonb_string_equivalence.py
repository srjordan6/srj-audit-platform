"""Tests for jsonb-string equivalence in scoring.

Django's psycopg3 backend registers a no-op TextLoader for jsonb so that
JSONField.from_db_value can apply the model field's decoder. This project
reads responses through raw cursors, so the column arrives as a *string*.

Before core.dbjson.loads_maybe() was applied at the score_response entry
point, that string:
  - made _score_l5 fail int() and return a flat 0.5 for every Likert item;
  - passed _score_ss_or_yn's isinstance(str) check, so the option lookup
    missed and the JSON text itself was scored by the generic heuristic.

Neither symptom is visible without comparing the two shapes, which is what
these tests do: for every question type, the string form and the dict form
must produce the same score.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scoring.response_scoring import score_response


def _q(qid, qtype, options=None, overrides=None):
    """Minimal stand-in for a question row (question_bank rows are dicts,
    wrapped in a namespace by scoring.engine before scoring)."""
    return SimpleNamespace(
        id=qid,
        question_type=qtype,
        options=options or [],
        scoring_overrides=overrides,
        extended_metadata=None,
    )


CASES = [
    (_q("T1-G-009", "L5"), {"selected": "3"}),
    (_q("T1-G-010", "L5"), {"selected": "5"}),
    (_q("T1-A-002", "SS", ["Individual Contributor", "Manager", "Executive"]),
     {"selected": "Individual Contributor"}),
    (_q("T1-F-001", "YN", ["Yes", "No", "Don't know"]), {"selected": "Yes"}),
    (_q("T1-F-002", "YN", ["Yes", "No", "Don't know"]), {"selected": "Don't know"}),
    (_q("T1-B-001", "MS", ["ChatGPT", "Copilot", "Claude"]),
     {"selected": ["ChatGPT", "Claude"]}),
]


@pytest.mark.parametrize("question,answer", CASES, ids=lambda v: getattr(v, "id", ""))
def test_string_and_dict_answers_score_identically(question, answer):
    as_dict = score_response(question, answer)
    as_string = score_response(question, json.dumps(answer))
    assert as_string.value == as_dict.value
    assert as_string.is_dont_know == as_dict.is_dont_know
    assert as_string.excluded == as_dict.excluded


def test_likert_string_is_not_flattened_to_half():
    """The exact pre-fix symptom: every Likert answer scored 0.5."""
    q = _q("T1-G-009", "L5")
    assert score_response(q, '{"selected": "5"}').value == pytest.approx(1.0)
    assert score_response(q, '{"selected": "1"}').value == pytest.approx(0.0)


def test_single_select_string_resolves_the_real_option():
    """The silent one: the JSON blob must not reach the option heuristic."""
    q = _q("T1-F-001", "YN", ["Yes", "No", "Don't know"])
    yes = score_response(q, '{"selected": "Yes"}')
    no = score_response(q, '{"selected": "No"}')
    assert yes.value != no.value, "blob scored identically for opposite answers"
    assert yes.value == score_response(q, {"selected": "Yes"}).value


def test_plain_string_answers_are_untouched():
    """Non-JSON answers must pass through unchanged."""
    q = _q("T1-F-001", "YN", ["Yes", "No", "Don't know"])
    assert score_response(q, "Yes").value == score_response(q, {"selected": "Yes"}).value


def test_dont_know_flag_survives_the_string_form():
    q = _q("T1-F-002", "YN", ["Yes", "No", "Don't know"])
    assert score_response(q, '{"selected": "Don\'t know"}').is_dont_know is True


def test_law_inventory_is_excluded_not_unscored():
    q = _q("T1-A-006", "LAW_INVENTORY")
    r = score_response(q, '{"selected": ["EU AI Act", "HIPAA and AI"]}')
    assert r.excluded is True
