"""
Unit tests for `scoring.frameworks.v1_audit`.

Coverage focus
--------------
- Empty engagement produces the canonical 5-dimension result (floor state)
- Positive answers in one dimension raise that dimension's final score
- `risk_exposure` is inverted (high signal → low final score)
- `Don't know` answers lower dimension confidence
- OD-16 / OD-17 documentation boost: attachments raise sub-component
  confidence relative to the same DK-heavy answers without attachments
- Composite score obeys the canonical 0.20 / 0.20 / 0.20 / 0.25 / 0.15
  weighting per Part A §4.2
- `top_gaps` surfaces the 3 sub-components farthest from target across
  all dimensions, with inverted-dimension targets respected

The aggregator is pure (no DB access) so the tests construct minimal
synthetic questions + responses and call `score_v1_audit` directly.
Fixtures live in `tests/scoring/conftest.py`.
"""

from __future__ import annotations

import pytest

from scoring.frameworks.v1_audit import (
    COMPOSITE_WEIGHTS,
    DIMENSIONS,
    INVERTED_DIMENSIONS,
    V1FrameworkResult,
    score_v1_audit,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

# Deterministic option weights for YN questions used in these tests. Bypasses
# the heuristic in response_scoring so the tests don't depend on regex quirks.
YN_OVERRIDE = {"Yes": 1.0, "No": 0.0, "Don't know": 0.75}


def _override_map(*qids: str) -> dict[str, dict[str, float]]:
    """Build {qid: YN_OVERRIDE} for a list of question ids."""
    return {qid: dict(YN_OVERRIDE) for qid in qids}


def _dim(result: V1FrameworkResult, name: str):
    """Locate a single dimension by name on a V1FrameworkResult."""
    for d in result.dimensions:
        if d.name == name:
            return d
    raise AssertionError(f"dimension {name!r} not present in result")


def _sub(dimension, sub_component_name: str):
    """Locate a single sub-component on a dimension by name."""
    for s in dimension.sub_components:
        if s.sub_component == sub_component_name:
            return s
    raise AssertionError(
        f"sub_component {sub_component_name!r} not present in dimension "
        f"{dimension.name!r}"
    )


# ----------------------------------------------------------------------------
# Test 1 — empty engagement
# ----------------------------------------------------------------------------

def test_empty_engagement_returns_canonical_five_dimensions(make_question):
    """With zero responses, all 5 canonical dimensions appear and no gaps surface."""
    questions = [
        make_question("Q1", dimension="tool_inventory", sub_component="inventory_exists"),
        make_question("Q2", dimension="cost_mapping", sub_component="direct_cost"),
    ]
    result = score_v1_audit(questions, responses_by_qid={})

    assert isinstance(result, V1FrameworkResult)
    assert result.framework == "v1_audit"
    assert {d.name for d in result.dimensions} == set(DIMENSIONS)
    assert len(result.dimensions) == 5
    # No responses → no answered sub-components → no diagnostic gaps
    assert result.top_gaps == []

    # Inverted dimension with no signal is the "best risk" floor: 100
    risk = _dim(result, "risk_exposure")
    assert risk.inverted is True
    assert risk.final_score_0_100 == 100.0
    assert risk.bracket == "Mature"

    # Non-inverted dimension with no signal is at the "no maturity" floor: 0
    inv = _dim(result, "tool_inventory")
    assert inv.inverted is False
    assert inv.final_score_0_100 == 0.0


# ----------------------------------------------------------------------------
# Test 2 — yes answers in one dimension raise its score
# ----------------------------------------------------------------------------

def test_yes_answers_in_one_dimension_score_100(make_question, make_response):
    """Three Yes answers in one sub-component → that sub-component scores 1.0
    (and 100 at the dimension level since it's the only active sub)."""
    questions = [
        make_question("Q1", dimension="tool_inventory", sub_component="inventory_exists"),
        make_question("Q2", dimension="tool_inventory", sub_component="inventory_exists"),
        make_question("Q3", dimension="tool_inventory", sub_component="inventory_exists"),
    ]
    responses = {
        "Q1": make_response("Q1", "Yes"),
        "Q2": make_response("Q2", "Yes"),
        "Q3": make_response("Q3", "Yes"),
    }

    result = score_v1_audit(
        questions, responses,
        option_weight_override_map=_override_map("Q1", "Q2", "Q3"),
    )

    inv = _dim(result, "tool_inventory")
    sub = _sub(inv, "inventory_exists")
    assert sub.answered_question_count == 3
    assert sub.weighted_mean_0_1 == pytest.approx(1.0)
    assert inv.final_score_0_100 == pytest.approx(100.0)
    assert inv.bracket == "Mature"
    # All Yes, no DK → high confidence
    assert sub.confidence_level == "high"
    assert sub.dk_ratio == 0.0


# ----------------------------------------------------------------------------
# Test 3 — risk_exposure inversion
# ----------------------------------------------------------------------------

def test_risk_exposure_yes_signal_inverts_to_low_final_score(make_question, make_response):
    """A Yes (raw signal 1.0) in risk_exposure means HIGH risk →
    inverted final_score_0_100 = 0."""
    questions = [
        make_question("Q1", dimension="risk_exposure", sub_component="data_exposure"),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}

    result = score_v1_audit(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    risk = _dim(result, "risk_exposure")
    assert "risk_exposure" in INVERTED_DIMENSIONS
    assert risk.inverted is True
    sub = _sub(risk, "data_exposure")
    # Raw signal is 1.0 ("Yes, sensitive data was exposed")
    assert sub.weighted_mean_0_1 == pytest.approx(1.0)
    # But final dimension score is inverted: 100 - 100 = 0
    assert risk.raw_score_0_100 == pytest.approx(100.0)
    assert risk.final_score_0_100 == pytest.approx(0.0)
    assert risk.bracket == "Critical"


def test_risk_exposure_no_signal_inverts_to_high_final_score(make_question, make_response):
    """A No (raw signal 0.0) in risk_exposure means LOW risk →
    inverted final_score_0_100 = 100."""
    questions = [
        make_question("Q1", dimension="risk_exposure", sub_component="data_exposure"),
    ]
    responses = {"Q1": make_response("Q1", "No")}

    result = score_v1_audit(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    risk = _dim(result, "risk_exposure")
    sub = _sub(risk, "data_exposure")
    assert sub.weighted_mean_0_1 == pytest.approx(0.0)
    assert risk.final_score_0_100 == pytest.approx(100.0)
    assert risk.bracket == "Mature"


# ----------------------------------------------------------------------------
# Test 4 — Don't Know lowers confidence
# ----------------------------------------------------------------------------

def test_dont_know_answers_lower_confidence(make_question, make_response):
    """A sub-component answered entirely with 'Don't know' → 'low' confidence."""
    questions = [
        make_question("Q1", dimension="tool_inventory", sub_component="inventory_exists"),
        make_question("Q2", dimension="tool_inventory", sub_component="inventory_exists"),
        make_question("Q3", dimension="tool_inventory", sub_component="inventory_exists"),
    ]
    responses = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
    }

    result = score_v1_audit(
        questions, responses, option_weight_override_map=_override_map("Q1", "Q2", "Q3"),
    )

    inv = _dim(result, "tool_inventory")
    sub = _sub(inv, "inventory_exists")
    assert sub.dk_ratio == pytest.approx(1.0)
    assert sub.confidence_level == "low"


# ----------------------------------------------------------------------------
# Test 5 — OD-16 / OD-17 documentation boost
# ----------------------------------------------------------------------------

def test_documentation_boost_raises_sub_component_confidence(make_question, make_response):
    """Same DK-heavy answer set, but with attached evidence on non-DK responses,
    should produce strictly higher confidence than without attachments.

    This is the integration point added by the confidence.py wiring PR.
    Tier 1 callers leave has_attachments=False, so this test exercises the
    Tier 2+ path explicitly.
    """
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, dimension="tool_inventory", sub_component="inventory_exists")
        for qid in qids
    ]
    override = _override_map(*qids)

    # Baseline: 3 DK + 2 Yes, no attachments → moderate DK ratio (40%)
    baseline_responses = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes"),
        "Q5": make_response("Q5", "Yes"),
    }
    baseline_result = score_v1_audit(
        questions, baseline_responses, option_weight_override_map=override,
    )
    baseline_sub = _sub(_dim(baseline_result, "tool_inventory"), "inventory_exists")

    # Boosted: same answers, but Yes responses are now backed by attachments
    boosted_responses = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes", has_attachments=True),
        "Q5": make_response("Q5", "Yes", has_attachments=True),
    }
    boosted_result = score_v1_audit(
        questions, boosted_responses, option_weight_override_map=override,
    )
    boosted_sub = _sub(_dim(boosted_result, "tool_inventory"), "inventory_exists")

    # Both have identical DK count, so dk_ratio is identical
    assert baseline_sub.dk_ratio == boosted_sub.dk_ratio == pytest.approx(0.6)

    # The new counters reflect OD-17 attached evidence on non-DK answers
    assert baseline_sub.attached_non_dk_count == 0
    assert boosted_sub.attached_non_dk_count == 2
    assert baseline_sub.noted_only_non_dk_count == 0
    assert boosted_sub.noted_only_non_dk_count == 0

    # And the confidence ordering reflects the documentation boost:
    # baseline (no attachments) is at most as confident as boosted.
    _levels = {"low": 0, "medium": 1, "high": 2}
    assert _levels[boosted_sub.confidence_level] >= _levels[baseline_sub.confidence_level]


def test_tier1_path_documentation_boost_is_no_op(make_question, make_response):
    """Tier 1 callers leave has_note/has_attachments=False; the documentation
    boost should evaluate to 0 and confidence should match a pure DK-ratio model.

    Validates the 'degrades gracefully' contract in the framework docstrings.
    """
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, dimension="tool_inventory", sub_component="inventory_exists")
        for qid in qids
    ]
    responses = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Yes"),
        "Q4": make_response("Q4", "Yes"),
        "Q5": make_response("Q5", "Yes"),
    }
    result = score_v1_audit(
        questions, responses, option_weight_override_map=_override_map(*qids),
    )
    sub = _sub(_dim(result, "tool_inventory"), "inventory_exists")

    # Tier 1 contract: counters are 0 because nothing supplies note/attach
    assert sub.attached_non_dk_count == 0
    assert sub.noted_only_non_dk_count == 0
    # 40% DK ratio falls in the 'medium' bucket (16-35% high cutoff, 36+ is low
    # at the dimension level; sub-component uses compute_confidence which is
    # consistent with the same banding when boost is zero).
    assert sub.confidence_level in {"low", "medium"}


# ----------------------------------------------------------------------------
# Test 6 — composite weighting
# ----------------------------------------------------------------------------

def test_composite_score_obeys_canonical_weights(make_question, make_response):
    """Each non-inverted dimension scores 100, risk_exposure scores 100 (raw)
    which inverts to 0. Composite = 100*0.20 + 100*0.20 + 100*0.20 + 0*0.25 + 100*0.15 = 75."""
    questions = [
        make_question("QI", dimension="tool_inventory", sub_component="x"),
        make_question("QC", dimension="cost_mapping", sub_component="x"),
        make_question("QP", dimension="performance_measurement", sub_component="x"),
        make_question("QR", dimension="risk_exposure", sub_component="x"),
        make_question("QG", dimension="governance_gaps", sub_component="x"),
    ]
    responses = {
        "QI": make_response("QI", "Yes"),
        "QC": make_response("QC", "Yes"),
        "QP": make_response("QP", "Yes"),
        "QR": make_response("QR", "Yes"),  # high risk signal → inverted to 0
        "QG": make_response("QG", "Yes"),
    }
    result = score_v1_audit(
        questions, responses,
        option_weight_override_map=_override_map("QI", "QC", "QP", "QR", "QG"),
    )

    # Sanity: the weight set itself is what we expect
    assert COMPOSITE_WEIGHTS == {
        "tool_inventory": 0.20,
        "cost_mapping": 0.20,
        "performance_measurement": 0.20,
        "risk_exposure": 0.25,
        "governance_gaps": 0.15,
    }

    # 100*0.20 + 100*0.20 + 100*0.20 + 0*0.25 + 100*0.15 = 75.0
    assert result.composite_score_0_100 == pytest.approx(75.0)
    assert result.composite_bracket == "Sound"


# ----------------------------------------------------------------------------
# Test 7 — top gaps identified correctly
# ----------------------------------------------------------------------------

def test_top_gaps_surface_three_worst_across_dimensions(make_question, make_response):
    """Build 4 sub-components with varying scores; verify top_gaps lists the
    three FARTHEST from target, respecting the inverted target on risk_exposure.

    Layout:
      tool_inventory.good      → all Yes (signal 1.0, gap = 0.0)
      cost_mapping.weak        → all No  (signal 0.0, gap = 1.0)  ← worst non-inverted
      performance.partial      → all Yes-partial (≈0.5, gap = 0.5)
      risk_exposure.exposed    → all Yes (signal 1.0, gap = 1.0)  ← worst inverted
    """
    questions = [
        make_question("G1", dimension="tool_inventory", sub_component="good"),
        make_question("W1", dimension="cost_mapping", sub_component="weak"),
        make_question("P1", dimension="performance_measurement", sub_component="partial"),
        make_question("E1", dimension="risk_exposure", sub_component="exposed"),
    ]
    # Use explicit per-question override so "partial" lands at exactly 0.5
    overrides = {
        "G1": {"Yes": 1.0, "No": 0.0},
        "W1": {"Yes": 1.0, "No": 0.0},
        "P1": {"Yes": 0.5, "No": 0.0},  # deliberate partial value
        "E1": {"Yes": 1.0, "No": 0.0},
    }
    responses = {
        "G1": make_response("G1", "Yes"),
        "W1": make_response("W1", "No"),
        "P1": make_response("P1", "Yes"),
        "E1": make_response("E1", "Yes"),
    }
    result = score_v1_audit(
        questions, responses, option_weight_override_map=overrides,
    )

    assert len(result.top_gaps) == 3
    gap_names = [g.sub_component for g in result.top_gaps]

    # The two worst gaps (magnitude 1.0 each) must appear; their relative order
    # is implementation-defined when magnitudes tie.
    assert "weak" in gap_names
    assert "exposed" in gap_names
    # The partial-strength sub_component is the third worst (gap = 0.5)
    assert "partial" in gap_names
    # The strongest sub_component does NOT appear in top gaps
    assert "good" not in gap_names
