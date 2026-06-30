"""
Unit tests for `scoring.frameworks.v3_governance`.

Coverage focus
--------------
- Empty engagement: 6 canonical steps present, no cross-cutting signals
- `step` mapping routes question to the named step
- `cross_cutting_signal` mapping routes to the parallel signal track
- Cross-cutting signals do NOT contribute to the composite
- Questions with no v3_governance mapping are silently ignored
- Governance maturity labels (Absent/Reactive/Defined/Integrated/Continuous)
  match Part A §4.4 thresholds — distinct from V2's labels
- Composite is the mean of ACTIVE steps only (empty steps don't drag it)
- top_gaps surfaces 3 lowest-scoring ACTIVE steps (inactive excluded)
- Weighted aggregation within a step respects per-mapping weight
- OD-16 / OD-17 documentation boost raises confidence at BOTH the step
  and cross-cutting-signal levels (they share `_aggregate_contributions`)
- Tier 1 path (no notes/attachments) is no-op

V3 differs from V1 and V2 in three structural ways:
- 6 steps (not dimensions × sub_components or modules)
- Cross-cutting signals in a parallel result dataclass — diagnostic
  overlays, NOT included in the composite
- Maturity labels: Absent / Reactive / Defined / Integrated / Continuous
  (Part A §4.4) — distinct from V2's Ad hoc / Emerging / Defined /
  Managed / Optimizing
"""

from __future__ import annotations

import pytest

from scoring.frameworks.v3_governance import (
    V3_STEPS,
    V3CrossCuttingSignalScore,
    V3FrameworkResult,
    V3StepScore,
    maturity_for_score,
    score_v3_governance,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

YN_OVERRIDE = {"Yes": 1.0, "No": 0.0, "Don't know": 0.75}


def _override_map(*qids: str) -> dict[str, dict[str, float]]:
    return {qid: dict(YN_OVERRIDE) for qid in qids}


def _step(result: V3FrameworkResult, name: str) -> V3StepScore:
    for s in result.steps:
        if s.name == name:
            return s
    raise AssertionError(f"step {name!r} not present in result")


def _signal(result: V3FrameworkResult, name: str) -> V3CrossCuttingSignalScore:
    for s in result.cross_cutting_signals:
        if s.name == name:
            return s
    raise AssertionError(f"cross_cutting_signal {name!r} not present in result")


def _signal_mapping(signal_name: str, weight: float = 1.0) -> list[dict]:
    """Build framework_mappings list for a cross-cutting signal question.

    The conftest's `dimension=` shorthand maps to `step=` for v3_governance;
    cross-cutting signals require the explicit `mappings=` kwarg.
    """
    return [{
        "framework": "v3_governance",
        "cross_cutting_signal": signal_name,
        "weight": weight,
    }]


# ----------------------------------------------------------------------------
# Test 1 — empty engagement
# ----------------------------------------------------------------------------

def test_empty_engagement_returns_six_steps_no_signals(make_question):
    """Zero responses, only non-v3 questions present → 6 canonical steps
    are emitted (all empty), zero cross-cutting signals, composite=0,
    'Absent' maturity, no top_gaps."""
    questions = [
        # v1_audit question — has no v3 mapping, must be ignored
        make_question("Q1", framework="v1_audit", dimension="tool_inventory",
                      sub_component="x"),
    ]
    result = score_v3_governance(questions, responses_by_qid={})

    assert isinstance(result, V3FrameworkResult)
    assert result.framework == "v3_governance"
    assert {s.name for s in result.steps} == set(V3_STEPS)
    assert len(result.steps) == 6
    # Cross-cutting signals list is empty when none are populated by the
    # input (signals appear only for categories that have at least one
    # mapping in the questions provided)
    assert result.cross_cutting_signals == []
    assert result.composite_score_0_100 == 0.0
    assert result.composite_maturity_level == 1
    assert result.composite_maturity_label == "Absent"
    assert result.top_gaps == []


# ----------------------------------------------------------------------------
# Test 2 — step mapping
# ----------------------------------------------------------------------------

def test_step_mapping_routes_to_named_step(make_question, make_response):
    """A question with framework_mappings = [{framework: v3_governance,
    step: accountability_mapping}] should land in accountability_mapping
    only, with no leakage into other steps or signals."""
    questions = [
        make_question("Q1", framework="v3_governance",
                      dimension="accountability_mapping"),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}
    result = score_v3_governance(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    am = _step(result, "accountability_mapping")
    assert am.answered_count == 1
    assert am.score_0_100 == pytest.approx(100.0)
    assert am.maturity_level == 5
    assert am.maturity_label == "Continuous"

    # Other steps are empty
    for step_name in V3_STEPS:
        if step_name == "accountability_mapping":
            continue
        s = _step(result, step_name)
        assert s.answered_count == 0

    # No cross-cutting signals populated
    assert result.cross_cutting_signals == []


# ----------------------------------------------------------------------------
# Test 3 — cross-cutting signal mapping
# ----------------------------------------------------------------------------

def test_cross_cutting_signal_appears_separately_not_in_steps(
    make_question, make_response,
):
    """A `cross_cutting_signal` mapping populates the
    cross_cutting_signals list — NOT any step."""
    questions = [
        make_question(
            "Q1",
            mappings=_signal_mapping("autonomous_execution_readiness", weight=2.5),
        ),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}
    result = score_v3_governance(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    # The signal is populated
    assert len(result.cross_cutting_signals) == 1
    signal = _signal(result, "autonomous_execution_readiness")
    assert signal.answered_count == 1
    assert signal.score_0_100 == pytest.approx(100.0)

    # NO step has any answered contributions
    for step_name in V3_STEPS:
        s = _step(result, step_name)
        assert s.answered_count == 0


def test_cross_cutting_signal_does_not_contribute_to_composite(
    make_question, make_response,
):
    """Composite = mean of active step scores. A cross-cutting signal
    answered Yes should NOT raise the composite above 0 when no step is
    answered."""
    questions = [
        make_question(
            "Q1", mappings=_signal_mapping("personal_defensibility"),
        ),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}
    result = score_v3_governance(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    # The signal is populated and scored 100
    signal = _signal(result, "personal_defensibility")
    assert signal.score_0_100 == pytest.approx(100.0)

    # Composite is still 0 — no step has any answered contribution
    assert result.composite_score_0_100 == 0.0
    assert result.composite_maturity_label == "Absent"


# ----------------------------------------------------------------------------
# Test 4 — unmapped question ignored
# ----------------------------------------------------------------------------

def test_question_without_v3_mapping_is_ignored(make_question, make_response):
    """A question with only v1_audit / v2_readiness / efficiency mappings
    must not feed any v3 step or signal."""
    questions = [
        make_question("Q1", framework="v1_audit",
                      dimension="tool_inventory", sub_component="x"),
        make_question("Q2", framework="v2_readiness",
                      dimension="workflow_readiness"),
        make_question("Q3", framework="efficiency",
                      dimension="outcome_alignment"),
    ]
    responses = {
        "Q1": make_response("Q1", "Yes"),
        "Q2": make_response("Q2", "Yes"),
        "Q3": make_response("Q3", "Yes"),
    }
    result = score_v3_governance(
        questions, responses,
        option_weight_override_map=_override_map("Q1", "Q2", "Q3"),
    )

    # All 6 steps remain empty
    for step_name in V3_STEPS:
        assert _step(result, step_name).answered_count == 0
    assert result.cross_cutting_signals == []
    assert result.composite_score_0_100 == 0.0


# ----------------------------------------------------------------------------
# Test 5 — Governance maturity scale matches Part A §4.4
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_level,expected_label", [
    (0.0,   1, "Absent"),
    (20.0,  1, "Absent"),          # boundary: ≤20
    (20.01, 2, "Reactive"),
    (40.0,  2, "Reactive"),
    (40.01, 3, "Defined"),
    (60.0,  3, "Defined"),
    (60.01, 4, "Integrated"),
    (80.0,  4, "Integrated"),
    (80.01, 5, "Continuous"),
    (100.0, 5, "Continuous"),
])
def test_maturity_for_score_matches_part_a_thresholds(
    score, expected_level, expected_label,
):
    """Part A §4.4 Governance scale uses distinct labels from V2 Readiness."""
    level, label = maturity_for_score(score)
    assert level == expected_level
    assert label == expected_label


# ----------------------------------------------------------------------------
# Test 6 — composite uses ACTIVE steps only
# ----------------------------------------------------------------------------

def test_composite_is_mean_of_active_steps_only(make_question, make_response):
    """When only 2 of 6 steps have answered questions, composite is the
    mean of THOSE 2 — not (sum / 6). This is the contract in
    _compute_composite (line 451: active = answered_count > 0)."""
    questions = [
        make_question("QAM", framework="v3_governance",
                      dimension="accountability_mapping"),
        make_question("QDE", framework="v3_governance",
                      dimension="data_exposure_assessment"),
    ]
    # Yes → 100, No → 0 → mean of 100 + 0 over 2 active steps = 50
    responses = {
        "QAM": make_response("QAM", "Yes"),
        "QDE": make_response("QDE", "No"),
    }
    result = score_v3_governance(
        questions, responses, option_weight_override_map=_override_map("QAM", "QDE"),
    )

    # 4 steps empty + 2 active scoring 100 and 0
    assert result.composite_score_0_100 == pytest.approx(50.0)
    # 50 ≤ 60 → level 3 / Defined
    assert result.composite_maturity_level == 3
    assert result.composite_maturity_label == "Defined"


# ----------------------------------------------------------------------------
# Test 7 — top_gaps
# ----------------------------------------------------------------------------

def test_top_gaps_returns_three_lowest_scoring_active_steps(
    make_question, make_response,
):
    """Build 5 active steps with descending scores. top_gaps must return
    the 3 lowest, and must NOT include any inactive step (one step has
    no questions at all)."""
    layout = {
        "accountability_mapping":         ("QAM", "Yes"),
        "data_exposure_assessment":       ("QDE", "Yes"),
        "decision_influence_review":      ("QDI", "No"),    # gap
        "vendor_risk_inventory":          ("QVR", "No"),    # gap
        "framework_crosswalk_readiness":  ("QFC", "No"),    # gap
        # incident_response_readiness intentionally has no question
    }
    questions = [
        make_question(qid, framework="v3_governance", dimension=step_name)
        for step_name, (qid, _) in layout.items()
    ]
    responses = {
        qid: make_response(qid, ans) for (qid, ans) in layout.values()
    }
    result = score_v3_governance(
        questions, responses,
        option_weight_override_map=_override_map(*(qid for qid, _ in layout.values())),
    )

    assert len(result.top_gaps) == 3
    gap_names = {g.name for g in result.top_gaps}
    # The 3 No-answered steps are gaps
    assert gap_names == {
        "decision_influence_review",
        "vendor_risk_inventory",
        "framework_crosswalk_readiness",
    }
    # The inactive step is NOT a gap (no diagnostic signal)
    assert "incident_response_readiness" not in gap_names
    # The Yes-answered steps are not gaps
    assert "accountability_mapping" not in gap_names
    assert "data_exposure_assessment" not in gap_names


# ----------------------------------------------------------------------------
# Test 8 — weighted aggregation within a step
# ----------------------------------------------------------------------------

def test_weighted_aggregation_within_step(make_question, make_response):
    """Within accountability_mapping, two questions: Q1 (weight 3.0) answered
    Yes (1.0), Q2 (weight 1.0) answered No (0.0). Weighted mean =
    (3.0 * 1.0 + 1.0 * 0.0) / (3.0 + 1.0) = 0.75 → 75."""
    questions = [
        make_question("Q1", framework="v3_governance",
                      dimension="accountability_mapping", weight=3.0),
        make_question("Q2", framework="v3_governance",
                      dimension="accountability_mapping", weight=1.0),
    ]
    responses = {
        "Q1": make_response("Q1", "Yes"),
        "Q2": make_response("Q2", "No"),
    }
    result = score_v3_governance(
        questions, responses, option_weight_override_map=_override_map("Q1", "Q2"),
    )
    am = _step(result, "accountability_mapping")
    assert am.answered_count == 2
    assert am.weighted_mean_0_1 == pytest.approx(0.75)
    assert am.score_0_100 == pytest.approx(75.0)
    assert am.maturity_level == 4
    assert am.maturity_label == "Integrated"


# ----------------------------------------------------------------------------
# Test 9 — OD-16 / OD-17 boost at step level
# ----------------------------------------------------------------------------

def test_documentation_boost_raises_step_confidence(make_question, make_response):
    """Same DK-heavy answer set, but Yes responses backed by attachments
    should produce step confidence at least as high as without
    attachments. OD-17 counter must reflect the attachments."""
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, framework="v3_governance",
                      dimension="accountability_mapping")
        for qid in qids
    ]
    override = _override_map(*qids)

    baseline = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes"),
        "Q5": make_response("Q5", "Yes"),
    }
    baseline_result = score_v3_governance(
        questions, baseline, option_weight_override_map=override,
    )
    baseline_am = _step(baseline_result, "accountability_mapping")

    boosted = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes", has_attachments=True),
        "Q5": make_response("Q5", "Yes", has_attachments=True),
    }
    boosted_result = score_v3_governance(
        questions, boosted, option_weight_override_map=override,
    )
    boosted_am = _step(boosted_result, "accountability_mapping")

    # DK ratio is identical
    assert baseline_am.dk_ratio == boosted_am.dk_ratio == pytest.approx(0.6)
    # OD-17 counters reflect the attachments
    assert baseline_am.attached_non_dk_count == 0
    assert boosted_am.attached_non_dk_count == 2
    # Confidence ordering: boosted >= baseline
    levels = {"low": 0, "medium": 1, "high": 2}
    assert levels[boosted_am.confidence_level] >= levels[baseline_am.confidence_level]


# ----------------------------------------------------------------------------
# Test 10 — OD-16 / OD-17 boost at cross-cutting signal level
# ----------------------------------------------------------------------------

def test_documentation_boost_raises_cross_cutting_signal_confidence(
    make_question, make_response,
):
    """Cross-cutting signals share `_aggregate_contributions` with steps,
    so the OD-17 boost must work identically on V3CrossCuttingSignalScore.
    This is a separate test from the step-level boost because the two
    code paths could regress independently."""
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, mappings=_signal_mapping("autonomous_execution_readiness"))
        for qid in qids
    ]
    override = _override_map(*qids)

    baseline = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes"),
        "Q5": make_response("Q5", "Yes"),
    }
    baseline_result = score_v3_governance(
        questions, baseline, option_weight_override_map=override,
    )
    baseline_sig = _signal(baseline_result, "autonomous_execution_readiness")

    boosted = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes", has_attachments=True),
        "Q5": make_response("Q5", "Yes", has_attachments=True),
    }
    boosted_result = score_v3_governance(
        questions, boosted, option_weight_override_map=override,
    )
    boosted_sig = _signal(boosted_result, "autonomous_execution_readiness")

    assert baseline_sig.dk_ratio == boosted_sig.dk_ratio == pytest.approx(0.6)
    assert baseline_sig.attached_non_dk_count == 0
    assert boosted_sig.attached_non_dk_count == 2
    levels = {"low": 0, "medium": 1, "high": 2}
    assert levels[boosted_sig.confidence_level] >= levels[baseline_sig.confidence_level]


# ----------------------------------------------------------------------------
# Test 11 — Tier 1 path (no boost) is no-op
# ----------------------------------------------------------------------------

def test_tier1_path_no_documentation_boost(make_question, make_response):
    """Tier 1 callers leave has_note/has_attachments=False; OD-16/OD-17
    counters stay at 0 and the confidence label matches the one-factor
    DK-ratio model."""
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, framework="v3_governance",
                      dimension="accountability_mapping")
        for qid in qids
    ]
    responses = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Yes"),
        "Q4": make_response("Q4", "Yes"),
        "Q5": make_response("Q5", "Yes"),
    }
    result = score_v3_governance(
        questions, responses, option_weight_override_map=_override_map(*qids),
    )
    am = _step(result, "accountability_mapping")
    # 40% DK
    assert am.dk_ratio == pytest.approx(0.4)
    assert am.attached_non_dk_count == 0
    assert am.noted_only_non_dk_count == 0
    # 40% DK on the Tier 1 path → confidence is bounded at medium or below
    assert am.confidence_level in {"low", "medium"}
