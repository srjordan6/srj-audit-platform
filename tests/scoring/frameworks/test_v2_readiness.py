"""
Unit tests for `scoring.frameworks.v2_readiness`.

Coverage focus
--------------
- Empty engagement produces all 6 canonical modules + CRI=0
- Explicit `module` mapping in framework_mappings routes correctly
- V2_MODULE_SECTION_RULES route questions WITHOUT explicit mappings
  based on `section` / `subsection`
- Explicit mapping wins when both layers target the same module
  (preserves sub_component + weight tuning)
- Overlapping subsections feed multiple modules (e.g., G.2 → 3 modules)
- Maturity-level brackets match Part A §4.3 thresholds
- CRI is the simple mean of the 6 module scores
- `top_gaps` returns the 3 LOWEST-scoring modules (no inversion in V2)
- OD-16 / OD-17 documentation boost raises module-level confidence
- Tier 1 path (no notes / attachments) degrades to one-factor model

V2 differs from V1 in three structural ways relevant to tests:
- modules (not dimensions × sub_components)
- no inversion — all modules are "higher = better readiness"
- dual-layer mapping (explicit + section/subsection fallback)

These tests exercise each of those axes explicitly.
"""

from __future__ import annotations

import pytest

from scoring.frameworks.v2_readiness import (
    V2_MODULES,
    V2_MODULE_SECTION_RULES,
    V2FrameworkResult,
    V2ModuleScore,
    maturity_for_score,
    score_v2_readiness,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

YN_OVERRIDE = {"Yes": 1.0, "No": 0.0, "Don't know": 0.75}


def _override_map(*qids: str) -> dict[str, dict[str, float]]:
    return {qid: dict(YN_OVERRIDE) for qid in qids}


def _module(result: V2FrameworkResult, name: str) -> V2ModuleScore:
    for m in result.modules:
        if m.name == name:
            return m
    raise AssertionError(f"module {name!r} not present in result")


# ----------------------------------------------------------------------------
# Test 1 — empty engagement
# ----------------------------------------------------------------------------

def test_empty_engagement_returns_six_modules(make_question):
    """Zero responses + a couple of unmapped questions → all 6 modules
    exist but score 0; CRI is 0; no gaps surface."""
    questions = [
        # Questions in section A — no v2 section rule matches section A —
        # so these are effectively ignored by v2_readiness.
        make_question("Q1", framework="v1_audit", dimension="tool_inventory",
                      sub_component="x", section="A"),
        make_question("Q2", framework="v1_audit", dimension="cost_mapping",
                      sub_component="x", section="A"),
    ]
    result = score_v2_readiness(questions, responses_by_qid={})

    assert isinstance(result, V2FrameworkResult)
    assert result.framework == "v2_readiness"
    assert {m.name for m in result.modules} == set(V2_MODULES)
    assert len(result.modules) == 6
    # No responses → every module is at the floor
    assert result.cri_score_0_100 == 0.0
    assert result.cri_maturity_level == 1
    assert result.cri_maturity_label == "Ad hoc"
    # No answered questions in any module → no diagnostic gaps
    assert result.top_gaps == []


# ----------------------------------------------------------------------------
# Test 2 — explicit module mapping
# ----------------------------------------------------------------------------

def test_explicit_module_mapping_routes_to_named_module(make_question, make_response):
    """A question with framework_mappings = [{framework: v2_readiness,
    module: workflow_readiness}] should land that question in
    workflow_readiness only (no other module)."""
    questions = [
        make_question("Q1", framework="v2_readiness", dimension="workflow_readiness"),
    ]
    responses = {"Q1": make_response("Q1", "Yes")}
    result = score_v2_readiness(
        questions, responses, option_weight_override_map=_override_map("Q1"),
    )

    wr = _module(result, "workflow_readiness")
    assert wr.answered_count == 1
    assert wr.score_0_100 == pytest.approx(100.0)
    assert wr.explicit_contribution_count == 1
    assert wr.section_rule_contribution_count == 0
    assert wr.maturity_level == 5
    assert wr.maturity_label == "Optimizing"

    # Other modules are empty
    for module_name in V2_MODULES:
        if module_name == "workflow_readiness":
            continue
        m = _module(result, module_name)
        assert m.answered_count == 0


# ----------------------------------------------------------------------------
# Test 3 — section-rule fallback
# ----------------------------------------------------------------------------

def test_section_rule_routes_question_with_no_explicit_v2_mapping(make_question, make_response):
    """A question in section D with NO v2_readiness mapping should still
    feed performance_measurement via V2_MODULE_SECTION_RULES (rule:
    sections=['D'])."""
    # The question has a v1_audit mapping only — no explicit v2 link.
    # But section='D' triggers the performance_measurement section rule.
    questions = [
        make_question("D1", framework="v1_audit",
                      dimension="performance_measurement", sub_component="x",
                      section="D", subsection="D.1"),
    ]
    responses = {"D1": make_response("D1", "Yes")}
    result = score_v2_readiness(
        questions, responses, option_weight_override_map=_override_map("D1"),
    )

    pm = _module(result, "performance_measurement")
    assert pm.answered_count == 1
    assert pm.section_rule_contribution_count == 1
    assert pm.explicit_contribution_count == 0
    assert pm.score_0_100 == pytest.approx(100.0)


def test_section_rule_subsection_match(make_question, make_response):
    """A question with subsection 'E.1' should be picked up by data_readiness
    via the subsection-rule path (V2_MODULE_SECTION_RULES['data_readiness']['subsections']
    includes 'E.1')."""
    questions = [
        make_question("E1", framework="v1_audit",
                      dimension="risk_exposure", sub_component="data_exposure",
                      section="E", subsection="E.1"),
    ]
    responses = {"E1": make_response("E1", "No")}  # No = low risk = good readiness
    result = score_v2_readiness(
        questions, responses, option_weight_override_map=_override_map("E1"),
    )

    dr = _module(result, "data_readiness")
    assert dr.answered_count == 1
    assert dr.section_rule_contribution_count == 1
    # "No" → 0.0 raw signal. V2 does NOT invert.
    # So data_readiness scores 0 (NOT 100 like the inverted V1 risk_exposure).
    assert dr.score_0_100 == pytest.approx(0.0)


# ----------------------------------------------------------------------------
# Test 4 — explicit wins over section rule
# ----------------------------------------------------------------------------

def test_explicit_mapping_wins_over_section_rule_on_same_module(make_question, make_response):
    """A question in subsection D.1 (section rule would put it in
    performance_measurement) WITH an explicit mapping to performance_measurement
    should be counted once via the explicit path — not double-counted."""
    questions = [
        make_question(
            "D1",
            framework="v2_readiness",
            dimension="performance_measurement",   # → module=performance_measurement
            section="D",
            subsection="D.1",
        ),
    ]
    responses = {"D1": make_response("D1", "Yes")}
    result = score_v2_readiness(
        questions, responses, option_weight_override_map=_override_map("D1"),
    )

    pm = _module(result, "performance_measurement")
    assert pm.answered_count == 1
    # Explicit mapping takes precedence — section_rule contribution NOT counted
    assert pm.explicit_contribution_count == 1
    assert pm.section_rule_contribution_count == 0


# ----------------------------------------------------------------------------
# Test 5 — overlapping subsections feed multiple modules
# ----------------------------------------------------------------------------

def test_g2_subsection_feeds_multiple_modules(make_question, make_response):
    """Subsection G.2 is in V2_MODULE_SECTION_RULES for THREE modules:
    workflow_readiness, people_readiness, operational_friction.
    One question with subsection='G.2' should land in all three (no
    explicit mappings present)."""
    questions = [
        make_question("G2A", framework="v1_audit",
                      dimension="governance_gaps", sub_component="x",
                      section="G", subsection="G.2"),
    ]
    responses = {"G2A": make_response("G2A", "Yes")}
    result = score_v2_readiness(
        questions, responses, option_weight_override_map=_override_map("G2A"),
    )

    # Sanity: confirm V2_MODULE_SECTION_RULES still has G.2 in the three modules
    g2_modules = {
        name for name, rules in V2_MODULE_SECTION_RULES.items()
        if "G.2" in (rules.get("subsections") or [])
    }
    assert g2_modules == {"workflow_readiness", "people_readiness", "operational_friction"}

    for mod_name in g2_modules:
        m = _module(result, mod_name)
        assert m.answered_count == 1, f"{mod_name} should include the G.2 question"
        assert m.section_rule_contribution_count == 1
        assert m.score_0_100 == pytest.approx(100.0)

    # And modules NOT covering G.2 stay empty
    untouched = set(V2_MODULES) - g2_modules
    for mod_name in untouched:
        m = _module(result, mod_name)
        assert m.answered_count == 0


# ----------------------------------------------------------------------------
# Test 6 — maturity level mapping
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_level,expected_label", [
    (0.0,   1, "Ad hoc"),
    (20.0,  1, "Ad hoc"),         # boundary: ≤20
    (20.01, 2, "Emerging"),
    (40.0,  2, "Emerging"),
    (40.01, 3, "Defined"),
    (60.0,  3, "Defined"),
    (60.01, 4, "Managed"),
    (80.0,  4, "Managed"),
    (80.01, 5, "Optimizing"),
    (100.0, 5, "Optimizing"),
])
def test_maturity_for_score_matches_part_a_thresholds(score, expected_level, expected_label):
    level, label = maturity_for_score(score)
    assert level == expected_level
    assert label == expected_label


# ----------------------------------------------------------------------------
# Test 7 — CRI is the mean of module scores
# ----------------------------------------------------------------------------

def test_cri_is_mean_of_six_module_scores(make_question, make_response):
    """Build one Yes response in each of the 6 modules → every module
    scores 100 → CRI = 100. Then knock one module down to 0 → CRI = 500/6."""
    qids_per_module = {
        "workflow_readiness":         "QWR",
        "data_readiness":             "QDR",
        "people_readiness":           "QPR",
        "leadership_accountability":  "QLA",
        "performance_measurement":    "QPM",
        "operational_friction":       "QOF",
    }
    questions = [
        make_question(
            qid, framework="v2_readiness", dimension=mod_name,
        )
        for mod_name, qid in qids_per_module.items()
    ]

    # All Yes → CRI = 100
    all_yes = {qid: make_response(qid, "Yes") for qid in qids_per_module.values()}
    result = score_v2_readiness(
        questions, all_yes,
        option_weight_override_map=_override_map(*qids_per_module.values()),
    )
    assert result.cri_score_0_100 == pytest.approx(100.0)
    assert result.cri_maturity_level == 5
    assert result.cri_maturity_label == "Optimizing"

    # Knock workflow_readiness down to 0 (No) → 5×100 + 1×0 = 500/6 ≈ 83.33
    mixed = dict(all_yes)
    mixed["QWR"] = make_response("QWR", "No")
    result2 = score_v2_readiness(
        questions, mixed,
        option_weight_override_map=_override_map(*qids_per_module.values()),
    )
    assert result2.cri_score_0_100 == pytest.approx(500.0 / 6.0)
    assert result2.cri_maturity_level == 5


# ----------------------------------------------------------------------------
# Test 8 — top_gaps surfaces the three lowest modules
# ----------------------------------------------------------------------------

def test_top_gaps_surfaces_three_lowest_scoring_modules(make_question, make_response):
    """Give 4 modules a 'No' answer and 2 modules a 'Yes' answer. The 4
    No-answered modules score 0, but only 3 should appear in top_gaps."""
    layout = {
        "workflow_readiness":         ("QWR", "No"),
        "data_readiness":             ("QDR", "No"),
        "people_readiness":           ("QPR", "No"),
        "leadership_accountability":  ("QLA", "No"),
        "performance_measurement":    ("QPM", "Yes"),
        "operational_friction":       ("QOF", "Yes"),
    }
    questions = [
        make_question(qid, framework="v2_readiness", dimension=mod_name)
        for mod_name, (qid, _) in layout.items()
    ]
    responses = {
        qid: make_response(qid, ans) for (qid, ans) in layout.values()
    }
    result = score_v2_readiness(
        questions, responses,
        option_weight_override_map=_override_map(*(qid for qid, _ in layout.values())),
    )

    assert len(result.top_gaps) == 3
    # The three gaps are all No-answered modules with score 0
    gap_names = {g.name for g in result.top_gaps}
    no_modules = {m for m, (_, ans) in layout.items() if ans == "No"}
    assert gap_names.issubset(no_modules)
    # The two Yes modules never appear in gaps
    assert "performance_measurement" not in gap_names
    assert "operational_friction" not in gap_names


# ----------------------------------------------------------------------------
# Test 9 — OD-16 / OD-17 documentation boost
# ----------------------------------------------------------------------------

def test_documentation_boost_raises_module_confidence(make_question, make_response):
    """Same DK-heavy answer set, but Yes responses backed by attachments
    should produce module confidence at least as high as without
    attachments (parity with the v1_audit sub-component test)."""
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, framework="v2_readiness", dimension="workflow_readiness")
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
    baseline_result = score_v2_readiness(questions, baseline, option_weight_override_map=override)
    baseline_wr = _module(baseline_result, "workflow_readiness")

    boosted = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Don't know", is_dk=True),
        "Q4": make_response("Q4", "Yes", has_attachments=True),
        "Q5": make_response("Q5", "Yes", has_attachments=True),
    }
    boosted_result = score_v2_readiness(questions, boosted, option_weight_override_map=override)
    boosted_wr = _module(boosted_result, "workflow_readiness")

    # Identical DK ratios
    assert baseline_wr.dk_ratio == boosted_wr.dk_ratio == pytest.approx(0.6)
    # OD-17 counters reflect the attachments
    assert baseline_wr.attached_non_dk_count == 0
    assert boosted_wr.attached_non_dk_count == 2
    # Confidence ordering: boosted >= baseline
    levels = {"low": 0, "medium": 1, "high": 2}
    assert levels[boosted_wr.confidence_level] >= levels[baseline_wr.confidence_level]


def test_tier1_path_module_documentation_boost_is_no_op(make_question, make_response):
    """Tier 1 callers leave has_note/has_attachments=False; the documentation
    boost should evaluate to 0 and confidence should match the one-factor
    DK-ratio model."""
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    questions = [
        make_question(qid, framework="v2_readiness", dimension="workflow_readiness")
        for qid in qids
    ]
    responses = {
        "Q1": make_response("Q1", "Don't know", is_dk=True),
        "Q2": make_response("Q2", "Don't know", is_dk=True),
        "Q3": make_response("Q3", "Yes"),
        "Q4": make_response("Q4", "Yes"),
        "Q5": make_response("Q5", "Yes"),
    }
    result = score_v2_readiness(
        questions, responses, option_weight_override_map=_override_map(*qids),
    )
    wr = _module(result, "workflow_readiness")
    assert wr.attached_non_dk_count == 0
    assert wr.noted_only_non_dk_count == 0
    # 40% DK → 'medium' or 'low' (Tier 1 contract: no boost can lift this above medium)
    assert wr.confidence_level in {"low", "medium"}
