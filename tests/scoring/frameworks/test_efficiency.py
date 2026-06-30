"""
Unit tests for `scoring.frameworks.efficiency`.

Coverage focus
--------------
- Empty engagement: 2 components present, composite=0, "Critical" bracket
- Explicit `sub_component` / `component` mapping routes to named component
- Production `sub_component` field name is honored (alongside `component`)
- Section-rule fallback uses `question.subsection` (D.1/G.1 →
  outcome_alignment; D.2/D.3/G.2/G.3 → process_optimization)
- EXCLUSIVE EXPLICIT OVERRIDE — if a question has ANY explicit mapping,
  section rules contribute NOTHING for that question (unique-to-efficiency
  contract vs v2's section-rule union)
- Question with no subsection produces no section-rule contributions
- Bracket labels match V1's Critical/Concerning/Developing/Sound/Mature
- Composite = FIXED 50/50 weighting (not arithmetic mean) per Part A §4.5
- A component with zero answered contributions contributes 0 to the
  composite — the other component still counts at its 50% weight
- top_gaps returns up to 2 lowest-scoring ACTIVE components
- OD-16 / OD-17 documentation boost raises component confidence
- Tier 1 path (no notes/attachments) is no-op

Efficiency differs from V1 / V2 / V3 in three structural ways:
- Only 2 components (no further sub-hierarchy, no cross-cutting signals)
- FIXED 50/50 composite weighting — NOT a mean over active components
- EXCLUSIVE explicit override — if a question has ANY explicit mapping,
  section rules are skipped for that question (the docstring at
  efficiency.py:12-28 calls this out; production has G-questions
  diverging between the explicit map and Part A §4.5 section rule)
"""

from __future__ import annotations

import pytest

from scoring.frameworks.efficiency import (
    COMPOSITE_WEIGHTS,
    EFFICIENCY_COMPONENTS,
    EFFICIENCY_SECTION_RULES,
    EfficiencyComponentScore,
    EfficiencyFrameworkResult,
    bracket_for_score,
    score_efficiency,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

YN_OVERRIDE = {"Yes": 1.0, "No": 0.0, "Don't know": 0.75}


def _override_map(*qids: str) -> dict[str, dict[str, float]]:
    return {qid: dict(YN_OVERRIDE) for qid in qids}


def _component(result: EfficiencyFrameworkResult, name: str) -> EfficiencyComponentScore:
    for c in result.components:
        if c.name == name:
            return c
    raise AssertionError(f"component {name!r} not present in result")


# ----------------------------------------------------------------------------
# Test 1 — empty engagement
# ----------------------------------------------------------------------------

def test_empty_engagement_returns_two_components(make_question):
    """Zero responses + only non-efficiency questions → 2 components in
    canonical order, composite=0, 'Critical' bracket, no gaps."""
    questions = [
        # v1_audit question without efficiency-eligible subsection
        make_question("Q1", framework="v1_audit", dimension="tool_inventory",
                      sub_component="x", section="A", subsection="A.1"),
    ]
    result = score_efficiency(questions, responses_by_qid={})

    assert isinstance(result, EfficiencyFrameworkResult)
    assert result.framework == "efficiency"
    assert {c.name for c in result.components} == set(EFFICIENCY_COMPONENTS)
    # Canonical order check (Part A §4.5 lists outcome_alignment first)
    assert [c.name for c in result.components] == list(EFFICIENCY_COMPONENTS)
    assert len(result.components) == 2
    assert result.composite_score_0_100 == 0.0
    assert result.composite_bracket == "Critical"
    assert result.top_gaps == []


# ----------------------------------------------------------------------------
# Test 2 — explicit mapping (conftest shorthand uses `component` field)
# ----------------------------------------------------------------------------

def test_explicit_component_field_routes_to_named_component(make_question, make_response):
    """The conftest shorthand emits {framework: efficiency, component: X};
    efficiency.py reads `sub_component` first with `component` as a fallback
    — both should route correctly. This test exercises the `component`
    fallback path."""
    questions = [
        make_question("Q1", framework="efficiency",
                      dimension="outcome_alignment"),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    oa = _component(result, "outcome_alignment")
    assert oa.answered_count == 1
    assert oa.score_0_100 == pytest.approx(100.0)
    assert oa.explicit_contribution_count == 1
    assert oa.section_rule_contribution_count == 0
    assert oa.bracket == "Mature"

    # process_optimization is empty
    po = _component(result, "process_optimization")
    assert po.answered_count == 0


# ----------------------------------------------------------------------------
# Test 3 — sub_component field name (production data shape)
# ----------------------------------------------------------------------------

def test_production_sub_component_field_routes_correctly(make_question, make_response):
    """Production data uses `sub_component` on efficiency mappings (not
    `component`). The aggregator must honor that field name — this test
    builds the mapping with `sub_component` explicitly via the
    `mappings=` kwarg."""
    questions = [
        make_question("Q1", mappings=[{
            "framework": "efficiency",
            "sub_component": "process_optimization",
            "weight": 1.0,
        }]),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    po = _component(result, "process_optimization")
    assert po.answered_count == 1
    assert po.score_0_100 == pytest.approx(100.0)
    assert po.explicit_contribution_count == 1


# ----------------------------------------------------------------------------
# Test 4 — section-rule fallback for questions without explicit mappings
# ----------------------------------------------------------------------------

def test_section_rule_routes_d1_to_outcome_alignment(make_question, make_response):
    """A question with subsection='D.1' and no explicit efficiency mapping
    should land in outcome_alignment via EFFICIENCY_SECTION_RULES."""
    questions = [
        make_question("D1A", framework="v1_audit",
                      dimension="performance_measurement",
                      sub_component="metric_existence",
                      section="D", subsection="D.1"),
    ]
    responses = {"D1A": make_response("D1A", "Yes")}
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("D1A"),
    )

    oa = _component(result, "outcome_alignment")
    assert oa.answered_count == 1
    assert oa.section_rule_contribution_count == 1
    assert oa.explicit_contribution_count == 0
    assert oa.score_0_100 == pytest.approx(100.0)


def test_section_rule_routes_d2_to_process_optimization(make_question, make_response):
    """A question with subsection='D.2' and no explicit efficiency mapping
    should land in process_optimization via EFFICIENCY_SECTION_RULES."""
    questions = [
        make_question("D2A", framework="v1_audit",
                      dimension="performance_measurement",
                      sub_component="output_quality",
                      section="D", subsection="D.2"),
    ]
    responses = {"D2A": make_response("D2A", "Yes")}
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("D2A"),
    )

    po = _component(result, "process_optimization")
    assert po.answered_count == 1
    assert po.section_rule_contribution_count == 1
    assert po.score_0_100 == pytest.approx(100.0)


def test_section_rule_g3_routes_to_process_optimization(make_question, make_response):
    """The docstring at efficiency.py:23-28 documents the G.3 divergence:
    production has SOME G.3 questions explicitly placed in outcome_alignment
    while the Part A §4.5 section rule puts G.3 in process_optimization.
    For a G.3 question with NO explicit efficiency mapping, the section
    rule must fire and place it in process_optimization."""
    questions = [
        make_question("G3A", framework="v1_audit",
                      dimension="governance_gaps",
                      sub_component="confidence",
                      section="G", subsection="G.3"),
    ]
    responses = {"G3A": make_response("G3A", "Yes")}
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("G3A"),
    )

    po = _component(result, "process_optimization")
    assert po.answered_count == 1
    assert po.section_rule_contribution_count == 1

    # And NOT to outcome_alignment (section rule only routes G.3 to process)
    oa = _component(result, "outcome_alignment")
    assert oa.answered_count == 0


# ----------------------------------------------------------------------------
# Test 5 — EXCLUSIVE explicit override (the unique-to-efficiency contract)
# ----------------------------------------------------------------------------

def test_explicit_mapping_blocks_section_rules_entirely(make_question, make_response):
    """A question with subsection='G.3' (which the section rule routes to
    process_optimization) AND an explicit efficiency mapping to
    outcome_alignment should land ONLY in outcome_alignment.

    This is the unique-to-efficiency contract — unlike v2 where explicit
    and section rule are unioned per module, efficiency's explicit
    mapping completely BLOCKS section rule contributions for that
    question. Documented at efficiency.py:12-28."""
    questions = [
        make_question(
            "G3A",
            framework="efficiency",
            dimension="outcome_alignment",   # explicit → outcome_alignment
            section="G",
            subsection="G.3",                # section rule → process_optimization
        ),
    ]
    responses = {"G3A": make_response("G3A", "Yes")}
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("G3A"),
    )

    # Explicit wins — outcome_alignment gets the contribution
    oa = _component(result, "outcome_alignment")
    assert oa.answered_count == 1
    assert oa.explicit_contribution_count == 1
    assert oa.section_rule_contribution_count == 0

    # process_optimization gets NOTHING (section rule blocked by exclusive override)
    po = _component(result, "process_optimization")
    assert po.answered_count == 0
    assert po.section_rule_contribution_count == 0


# ----------------------------------------------------------------------------
# Test 6 — no subsection means no section-rule contribution
# ----------------------------------------------------------------------------

def test_question_without_subsection_no_section_rule_contribution(
    make_question, make_response,
):
    """A question with subsection=None should not match any section rule
    even if its section is otherwise relevant."""
    questions = [
        make_question("Q1", framework="v1_audit",
                      dimension="cost_mapping", sub_component="x",
                      section="C", subsection=None),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    for component_name in EFFICIENCY_COMPONENTS:
        assert _component(result, component_name).answered_count == 0


# ----------------------------------------------------------------------------
# Test 7 — bracket labels (V1 set)
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_bracket", [
    (0.0,   "Critical"),
    (20.0,  "Critical"),       # boundary: ≤20
    (20.01, "Concerning"),
    (40.0,  "Concerning"),
    (40.01, "Developing"),
    (60.0,  "Developing"),
    (60.01, "Sound"),
    (80.0,  "Sound"),
    (80.01, "Mature"),
    (100.0, "Mature"),
])
def test_bracket_for_score_matches_thresholds(score, expected_bracket):
    """Efficiency reuses V1 audit's bracket labels per Part A §4.5
    (distinct from V2 Readiness / V3 Governance maturity labels)."""
    assert bracket_for_score(score) == expected_bracket


# ----------------------------------------------------------------------------
# Test 8 — composite is FIXED 50/50 weighting, not a mean
# ----------------------------------------------------------------------------

def test_composite_is_fixed_50_50_weighted(make_question, make_response):
    """Composite = (outcome × 0.5) + (process × 0.5) per Part A §4.5.

    With outcome=100 and process=0, composite=50 (not 50 by coincidence —
    fixed weighted sum). With outcome=80 and process=40, composite=60."""
    # Confirm the weights are 0.5/0.5 in the module config
    assert COMPOSITE_WEIGHTS == {"outcome_alignment": 0.5, "process_optimization": 0.5}

    questions = [
        make_question("QOA", framework="efficiency",
                      dimension="outcome_alignment"),
        make_question("QPO", framework="efficiency",
                      dimension="process_optimization"),
    ]
    # Outcome → Yes (100), Process → No (0)
    responses = {
        "QOA": make_response("QOA", "Yes"),
        "QPO": make_response("QPO", "No"),
    }
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("QOA", "QPO"),
    )
    assert result.composite_score_0_100 == pytest.approx(50.0)
    assert result.composite_bracket == "Developing"


def test_composite_uses_zero_for_empty_component(make_question, make_response):
    """A component with zero answered contributions contributes 0 to the
    composite — the other component's score is still halved at 0.5
    weighting. This is the documented contract at efficiency.py:_compute_composite."""
    questions = [
        make_question("QOA", framework="efficiency",
                      dimension="outcome_alignment"),
        # No process_optimization questions provided
    ]
    responses = {"QOA": make_response("QOA", "Yes")}   # → 100
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map("QOA"),
    )
    # outcome=100 × 0.5 + process=0 × 0.5 = 50 (NOT 100)
    assert result.composite_score_0_100 == pytest.approx(50.0)
    assert _component(result, "outcome_alignment").answered_count == 1
    assert _component(result, "process_optimization").answered_count == 0


# ----------------------------------------------------------------------------
# Test 9 — top_gaps shape (at most 2)
# ----------------------------------------------------------------------------

def test_top_gaps_returns_up_to_two_active_components(make_question, make_response):
    """With only 2 components, top_gaps maxes out at 2 entries. With one
    component active and the other empty, top_gaps has exactly 1 entry."""
    # Case A: both components active
    questions_both = [
        make_question("QOA", framework="efficiency",
                      dimension="outcome_alignment"),
        make_question("QPO", framework="efficiency",
                      dimension="process_optimization"),
    ]
    responses_both = {
        "QOA": make_response("QOA", "No"),    # score 0
        "QPO": make_response("QPO", "Yes"),   # score 100
    }
    result_both = score_efficiency(
        questions_both, responses_both,
        option_weight_override_map=_override_map("QOA", "QPO"),
    )
    assert len(result_both.top_gaps) == 2
    # The lower-scoring component is first
    assert result_both.top_gaps[0].name == "outcome_alignment"
    assert result_both.top_gaps[1].name == "process_optimization"

    # Case B: only one component active
    questions_one = [
        make_question("QOA", framework="efficiency", dimension="outcome_alignment"),
    ]
    responses_one = {"QOA": make_response("QOA", "Yes")}
    result_one = score_efficiency(
        questions_one, responses_one,
        option_weight_override_map=_override_map("QOA"),
    )
    assert len(result_one.top_gaps) == 1
    assert result_one.top_gaps[0].name == "outcome_alignment"


# ----------------------------------------------------------------------------
# Test 10 — OD-16 / OD-17 documentation boost
# ----------------------------------------------------------------------------

def test_documentation_boost_raises_component_confidence(make_question, make_response):
    """Same DK-heavy answer set, but Yes responses backed by attachments
    should produce component confidence at least as high as without
    attachments."""
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, framework="efficiency",
                      dimension="outcome_alignment")
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
    baseline_result = score_efficiency(
        questions, baseline, option_weight_override_map=override,
    )
    baseline_oa = _component(baseline_result, "outcome_alignment")

    boosted = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes", has_attachments=True),
        "Q5": make_response("Q5", "Yes", has_attachments=True),
    }
    boosted_result = score_efficiency(
        questions, boosted, option_weight_override_map=override,
    )
    boosted_oa = _component(boosted_result, "outcome_alignment")

    # DK ratio is identical
    assert baseline_oa.dk_ratio == boosted_oa.dk_ratio == pytest.approx(0.6)
    # OD-17 counters reflect attachments
    assert baseline_oa.attached_non_dk_count == 0
    assert boosted_oa.attached_non_dk_count == 2
    # Confidence ordering: boosted >= baseline
    levels = {"low": 0, "medium": 1, "high": 2}
    assert levels[boosted_oa.confidence_level] >= levels[baseline_oa.confidence_level]


def test_tier1_path_no_documentation_boost(make_question, make_response):
    """Tier 1 callers leave has_note/has_attachments=False; OD-16/OD-17
    counters stay at 0 and confidence matches the one-factor DK-ratio
    model."""
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, framework="efficiency",
                      dimension="outcome_alignment")
        for qid in qids
    ]
    responses = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Yes"),
        "Q4": make_response("Q4", "Yes"),
        "Q5": make_response("Q5", "Yes"),
    }
    result = score_efficiency(
        questions, responses, option_weight_override_map=_override_map(*qids),
    )
    oa = _component(result, "outcome_alignment")
    assert oa.dk_ratio == pytest.approx(0.4)
    assert oa.attached_non_dk_count == 0
    assert oa.noted_only_non_dk_count == 0
    assert oa.confidence_level in {"low", "medium"}


# ----------------------------------------------------------------------------
# Test 11 — section-rule config integrity check
# ----------------------------------------------------------------------------

def test_section_rule_config_matches_part_a_intent():
    """Sanity-check that EFFICIENCY_SECTION_RULES still expresses the
    Part A §4.5 intent. Locks the public config shape so a future config
    edit gets caught here rather than silently breaking section-rule
    fallback routing."""
    assert EFFICIENCY_SECTION_RULES == {
        "outcome_alignment":    ["D.1", "G.1"],
        "process_optimization": ["D.2", "D.3", "G.2", "G.3"],
    }
