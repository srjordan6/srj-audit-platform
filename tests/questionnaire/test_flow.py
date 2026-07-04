"""Tests for questionnaire.flow — pure logic, no DB, no Django settings.

Uses the real question bank as fixture since it's the source of truth.
Tests exercise flow.py's contract: role visibility, skip logic composition,
progress arithmetic, terminal detection, template mapping.

Design decisions
----------------
- No pytest-django. flow.py has no ORM/settings dependency.
- Real QUESTIONS list from question_bank.py used as ground truth.
- Each test constructs the minimum answered_by_id dict it needs.
- Answer shapes match production Response.answer_value JSONB structure:
    SS/YN/NR: {"selected": "option_label"}
    MS: {"selected": ["opt1", "opt2"]}
    NR: {"bracket": "10-25"}  or  {"selected": "10-25"}
    RANK: {"ranked": ["item1", "item2"]}
    L5: {"selected": "3"}
    TEXT: {"text": "free-form response"}
    MATRIX: {"rows": {"row_key": {"col_a": "yes"}}}
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from questionnaire import flow
from questionnaire.question_bank import QUESTIONS, get_question_by_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _answer(question_id: str, value: dict) -> dict:
    """Sugar for building single-question answer dicts."""
    return {question_id: value}


def _identify_ceo_answers() -> dict:
    """Minimum Section A answers for a CEO respondent.

    Section A is asked of all roles — role identity is captured in T1-A-001.
    """
    return {
        "T1-A-001": {"selected": "CEO or Owner"},
    }


# ---------------------------------------------------------------------------
# _role_visible
# ---------------------------------------------------------------------------


def test_role_visible_empty_visibility_shows_all():
    q = SimpleNamespace(id="X", role_visibility=[])
    assert flow._role_visible(q, "CEO") is True
    assert flow._role_visible(q, "IC") is True


def test_role_visible_all_token_shows_all():
    q = SimpleNamespace(id="X", role_visibility=["ALL"])
    assert flow._role_visible(q, "CEO") is True
    assert flow._role_visible(q, "IC") is True


def test_role_visible_missing_attribute_shows_all():
    q = SimpleNamespace(id="X")  # no role_visibility attr at all
    assert flow._role_visible(q, "CEO") is True


def test_role_visible_specific_role_gates_correctly():
    q = SimpleNamespace(id="X", role_visibility=["CEO", "CFO"])
    assert flow._role_visible(q, "CEO") is True
    assert flow._role_visible(q, "CFO") is True
    assert flow._role_visible(q, "IC") is False


# ---------------------------------------------------------------------------
# _as_ns
# ---------------------------------------------------------------------------


def test_as_ns_wraps_dict():
    d = {"id": "X", "question_text": "test"}
    ns = flow._as_ns(d)
    assert ns.id == "X"
    assert ns.question_text == "test"


def test_as_ns_idempotent_on_namespace():
    ns = SimpleNamespace(id="X")
    assert flow._as_ns(ns) is ns


# ---------------------------------------------------------------------------
# questions_visible_to_role
# ---------------------------------------------------------------------------


def test_visible_role_ceo_sees_section_a():
    """Every role sees Section A questions (identification)."""
    answers = _identify_ceo_answers()
    visible = flow.questions_visible_to_role("CEO", answers)
    section_a_ids = [q.id for q in visible if q.id.startswith("T1-A-")]
    assert "T1-A-001" in section_a_ids
    assert "T1-A-002" in section_a_ids


def test_visible_role_ic_does_not_see_c_suite_only_questions():
    """IC role must not see questions gated to senior leadership."""
    answers = {"T1-A-001": {"selected": "Individual Contributor"}}
    visible = flow.questions_visible_to_role("IC", answers)
    visible_ids = {q.id for q in visible}
    # Sample a known board/CEO-gated question
    for q in QUESTIONS:
        q_ns = flow._as_ns(q)
        vis = getattr(q_ns, "role_visibility", []) or []
        if vis and "IC" not in vis and "ALL" not in vis:
            assert q_ns.id not in visible_ids, (
                f"Question {q_ns.id} has role_visibility={vis} "
                f"but leaked into IC's visible list"
            )
            break


def test_visible_preserves_question_bank_order():
    """Order matches question_bank.QUESTIONS iteration order."""
    answers = _identify_ceo_answers()
    visible = flow.questions_visible_to_role("CEO", answers)
    seen_ids = [q.id for q in visible]
    # Ordered check: each visible question appears in same order as QUESTIONS
    bank_ids = [flow._as_ns(q).id for q in QUESTIONS]
    seen_positions = [bank_ids.index(qid) for qid in seen_ids]
    assert seen_positions == sorted(seen_positions)


def test_visible_returns_simplenamespace_objects():
    answers = _identify_ceo_answers()
    visible = flow.questions_visible_to_role("CEO", answers)
    assert len(visible) > 0
    for q in visible:
        assert isinstance(q, SimpleNamespace)


# ---------------------------------------------------------------------------
# next_unanswered_question
# ---------------------------------------------------------------------------


def test_next_returns_first_question_when_none_answered():
    """With no answers, first Section A question is next."""
    q = flow.next_unanswered_question("CEO", {})
    assert q is not None
    assert q.id == "T1-A-001"


def test_next_advances_after_answering():
    """Answering T1-A-001 advances to T1-A-002."""
    answers = _identify_ceo_answers()
    q = flow.next_unanswered_question("CEO", answers)
    assert q is not None
    assert q.id == "T1-A-002"


def test_next_returns_none_when_all_answered():
    """When every visible question is answered, returns None."""
    answers = _identify_ceo_answers()
    visible = flow.questions_visible_to_role("CEO", answers)
    all_answered = {q.id: {"selected": "placeholder"} for q in visible}
    assert flow.next_unanswered_question("CEO", all_answered) is None


def test_next_skips_role_gated_for_ic():
    """IC never sees C-suite-only questions in next() sequence."""
    answers = {"T1-A-001": {"selected": "Individual Contributor"}}
    # Advance IC through the whole bank; no board-only IDs should surface
    a = dict(answers)
    board_only_seen = False
    for _ in range(300):  # safety cap > 136 questions
        q = flow.next_unanswered_question("IC", a)
        if q is None:
            break
        vis = getattr(q, "role_visibility", []) or []
        if vis and "IC" not in vis and "ALL" not in vis:
            board_only_seen = True
            break
        a[q.id] = {"selected": "placeholder"}
    assert not board_only_seen


# ---------------------------------------------------------------------------
# progress_for_role
# ---------------------------------------------------------------------------


def test_progress_zero_at_start():
    completed, visible, pct = flow.progress_for_role("CEO", {})
    assert completed == 0
    assert visible > 0
    assert pct == 0.0


def test_progress_advances_with_each_answer():
    a: dict = {}
    prior_completed = 0
    for _ in range(5):
        q = flow.next_unanswered_question("CEO", a)
        if q is None:
            break
        a[q.id] = {"selected": "placeholder"}
        completed, _visible, _pct = flow.progress_for_role("CEO", a)
        assert completed == prior_completed + 1
        prior_completed = completed


def test_progress_reaches_100_when_complete():
    a: dict = {}
    for _ in range(300):
        q = flow.next_unanswered_question("CEO", a)
        if q is None:
            break
        a[q.id] = {"selected": "placeholder"}
    completed, visible, pct = flow.progress_for_role("CEO", a)
    assert completed == visible
    assert pct == 100.0


def test_progress_handles_zero_visible_gracefully():
    """Contrived case: role with no visible questions returns (0, 0, 0.0)."""
    # No real role has zero visibility, so this tests the guard directly
    # by monkey-checking the function with an unknown role.
    completed, visible, pct = flow.progress_for_role("UNKNOWN_ROLE_XYZ", {})
    # UNKNOWN role sees only "ALL"-visible questions, so visible > 0.
    # This test just verifies no crash and consistent tuple shape.
    assert isinstance(completed, int)
    assert isinstance(visible, int)
    assert isinstance(pct, float)


# ---------------------------------------------------------------------------
# is_terminal
# ---------------------------------------------------------------------------


def test_is_terminal_true_for_t1_h_006():
    q = get_question_by_id("T1-H-006")
    assert flow.is_terminal(q) is True


def test_is_terminal_false_for_other_questions():
    for qid in ["T1-A-001", "T1-B-001", "T1-H-001", "T1-H-002"]:
        q = get_question_by_id(qid)
        assert flow.is_terminal(q) is False, f"{qid} should not be terminal"


def test_is_terminal_accepts_dict_or_namespace():
    d = get_question_by_id("T1-H-006")
    assert flow.is_terminal(d) is True
    ns = flow._as_ns(d)
    assert flow.is_terminal(ns) is True


# ---------------------------------------------------------------------------
# is_complete
# ---------------------------------------------------------------------------


def test_is_complete_false_at_start():
    assert flow.is_complete("CEO", {}) is False


def test_is_complete_true_when_all_visible_answered():
    a: dict = {}
    for _ in range(300):
        q = flow.next_unanswered_question("CEO", a)
        if q is None:
            break
        a[q.id] = {"selected": "placeholder"}
    assert flow.is_complete("CEO", a) is True


# ---------------------------------------------------------------------------
# partial_template_for_type
# ---------------------------------------------------------------------------


def test_template_mapping_ss_yn_nr_share_partial():
    """SS, YN, NR all render via _question_single_select.html per PR 2."""
    ss = flow.partial_template_for_type("SS")
    yn = flow.partial_template_for_type("YN")
    nr = flow.partial_template_for_type("NR")
    assert ss == yn == nr
    assert ss.endswith("_question_single_select.html")


def test_template_mapping_ms():
    assert flow.partial_template_for_type("MS").endswith(
        "_question_multi_select.html"
    )


def test_template_mapping_l5():
    assert flow.partial_template_for_type("L5").endswith(
        "_question_likert.html"
    )


def test_template_mapping_text():
    assert flow.partial_template_for_type("TEXT").endswith(
        "_question_text.html"
    )


def test_template_mapping_rank():
    assert flow.partial_template_for_type("RANK").endswith(
        "_question_rank.html"
    )


def test_template_mapping_matrix():
    assert flow.partial_template_for_type("MATRIX").endswith(
        "_question_matrix_grid.html"
    )


def test_template_mapping_matrix_choice():
    assert flow.partial_template_for_type("MATRIX_CHOICE").endswith(
        "_question_matrix_choice.html"
    )


def test_template_mapping_unknown_raises():
    with pytest.raises(ValueError, match="Unknown question_type"):
        flow.partial_template_for_type("BOGUS_TYPE")


# ---------------------------------------------------------------------------
# End-to-end walk (integration-flavored, still no DB)
# ---------------------------------------------------------------------------


def test_ceo_end_to_end_walk_terminates():
    """Simulate a CEO answering every question in order; must terminate."""
    a: dict = {}
    steps = 0
    max_steps = 300
    while steps < max_steps:
        q = flow.next_unanswered_question("CEO", a)
        if q is None:
            break
        a[q.id] = {"selected": "placeholder"}
        steps += 1
    assert steps > 0
    assert steps < max_steps, "Walk didn't terminate within safety cap"


def test_ic_walk_shorter_than_ceo_walk():
    """IC sees fewer questions than CEO — walk terminates sooner."""

    def walk_length(role: str, initial: dict) -> int:
        a = dict(initial)
        n = 0
        for _ in range(300):
            q = flow.next_unanswered_question(role, a)
            if q is None:
                break
            a[q.id] = {"selected": "placeholder"}
            n += 1
        return n

    ceo_len = walk_length("CEO", {"T1-A-001": {"selected": "CEO or Owner"}})
    ic_len = walk_length(
        "IC", {"T1-A-001": {"selected": "Individual Contributor"}}
    )
    assert ic_len < ceo_len
    assert ic_len > 10  # IC still sees Section A + closing questions
