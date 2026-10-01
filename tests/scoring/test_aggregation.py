"""Multi-respondent aggregation (Part B-3 S.2) against the real scorers."""

from __future__ import annotations

import pytest

from scoring import aggregation
from scoring.frameworks import efficiency, v1_audit, v2_readiness, v3_governance


def _questions(make_question):
    """One question bank the four scorers all accept: v1 dims carry
    explicit sub_components; v2/v3/eff get their own mappings."""
    qs = []
    for i, (dim, sub) in enumerate([
        ("tool_inventory", "inventory_exists"), ("tool_inventory", "inventory_exists"),
        ("governance_gaps", "policy_exists"), ("governance_gaps", "policy_exists"),
    ]):
        qs.append(make_question(f"V1-{i}", framework="v1_audit", dimension=dim, sub_component=sub, weight=1.0))
    for i in range(2):
        qs.append(make_question(f"V2-{i}", framework="v2_readiness", dimension="operational_friction", weight=1.0))
    for i in range(2):
        qs.append(make_question(f"V3-{i}", framework="v3_governance", dimension="accountability_mapping", weight=1.0))
    for i in range(2):
        qs.append(make_question(f"E-{i}", framework="efficiency", dimension="outcome_alignment", weight=1.0))
    return qs


def _score_all(questions, responses):
    qids = [q.id for q in questions]
    ov = {q: {"Yes": 1.0, "No": 0.0} for q in qids}
    return (
        v1_audit.score_v1_audit(questions, responses, option_weight_override_map=ov),
        v2_readiness.score_v2_readiness(questions, responses, option_weight_override_map=ov),
        v3_governance.score_v3_governance(questions, responses, option_weight_override_map=ov),
        efficiency.score_efficiency(questions, responses, option_weight_override_map=ov),
    )


def _answers(make_response, questions, value):
    return {q.id: make_response(q.id, value) for q in questions}


@pytest.fixture
def two_respondents(make_question, make_response):
    qs = _questions(make_question)
    ceo = _score_all(qs, _answers(make_response, qs, "Yes"))   # leadership says everything is fine
    ic = _score_all(qs, _answers(make_response, qs, "No"))     # workforce says nothing is
    return qs, ceo, ic


def test_single_respondent_is_identity(two_respondents):
    qs, ceo, _ = two_respondents
    (v1, v2, v3, eff), summary = aggregation.aggregate([("CEO", ceo)])
    assert v1 is not ceo[0] or v1 == ceo[0]
    assert v1.composite_score_0_100 == pytest.approx(ceo[0].composite_score_0_100)
    assert summary.respondent_count == 1 and not summary.flagged


def test_result_types_are_preserved(two_respondents):
    _, ceo, ic = two_respondents
    (v1, v2, v3, eff), _ = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    assert isinstance(v1, v1_audit.V1FrameworkResult)
    assert isinstance(v2, v2_readiness.V2FrameworkResult)
    assert isinstance(v3, v3_governance.V3FrameworkResult)
    assert isinstance(eff, efficiency.EfficiencyFrameworkResult)


def test_role_weighted_mean_leans_toward_the_role_that_owns_the_dimension(two_respondents):
    """governance_gaps: CEO weight 2.0, IC 0.5. CEO=100, IC=0 -> 80, not 50."""
    _, ceo, ic = two_respondents
    (v1, _, _, _), _ = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    gov = next(d for d in v1.dimensions if d.name == "governance_gaps")
    assert gov.final_score_0_100 == pytest.approx(80.0)
    assert gov.bracket == v1_audit.bracket_for_score(80.0)


def test_workforce_owned_dimension_leans_the_other_way(two_respondents):
    """operational_friction: IC 2.0, CEO 0.5. CEO=100, IC=0 -> 20."""
    _, ceo, ic = two_respondents
    (_, v2, _, _), _ = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    fr = next(m for m in v2.modules if m.name == "operational_friction")
    assert fr.score_0_100 == pytest.approx(20.0)


def test_divergence_is_flagged_and_confidence_penalised(two_respondents):
    _, ceo, ic = two_respondents
    (v1, _, _, _), summary = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    gov = next(d for d in summary.dimensions if d.dimension == "governance_gaps")
    assert gov.leadership_mean == pytest.approx(100.0)
    assert gov.workforce_mean == pytest.approx(0.0)
    assert gov.divergence == pytest.approx(100.0) and gov.flagged
    dim = next(d for d in v1.dimensions if d.name == "governance_gaps")
    assert dim.confidence_level in ("medium", "low")      # penalised from high


def test_zero_weight_role_is_excluded_not_averaged(two_respondents):
    """efficiency.outcome_alignment gives IC weight 0: only the CEO counts."""
    _, ceo, ic = two_respondents
    (_, _, _, eff), summary = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    oa = next(c for c in eff.components if c.name == "outcome_alignment")
    assert oa.score_0_100 == pytest.approx(100.0)
    agg = next(d for d in summary.dimensions if d.dimension == "outcome_alignment")
    assert agg.contributing == 1 and agg.excluded == 1


def test_composites_are_recomputed_from_aggregated_items(two_respondents):
    _, ceo, ic = two_respondents
    (v1, v2, v3, eff), _ = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    # renormalised over assessed dimensions, same as v1_audit.score_framework
    assert v1.composite_score_0_100 == pytest.approx(aggregation._v1_composite(v1.dimensions))
    assert v3.composite_score_0_100 == pytest.approx(v3_governance._compute_composite(v3.steps))
    assert 0.0 <= v2.cri_score_0_100 <= 100.0
    assert eff.composite_bracket == efficiency.bracket_for_score(eff.composite_score_0_100)


def test_contested_questions_surface_disagreement(two_respondents):
    _, ceo, ic = two_respondents
    _, summary = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    assert summary.contested, "opposite answers must produce contested questions"
    top = summary.contested[0]
    assert top.respondents == 2 and top.stdev_0_1 == pytest.approx(0.5)


def test_agreeing_respondents_do_not_flag(make_question, make_response):
    qs = _questions(make_question)
    a = _score_all(qs, _answers(make_response, qs, "Yes"))
    b = _score_all(qs, _answers(make_response, qs, "Yes"))
    (v1, _, _, _), summary = aggregation.aggregate([("CEO", a), ("IC", b)])
    assert not summary.flagged
    assert all(c.stdev_0_1 == 0.0 for c in summary.contested)
    gov = next(d for d in v1.dimensions if d.name == "governance_gaps")
    assert gov.final_score_0_100 == pytest.approx(100.0)
    assert gov.confidence_level == "high"


def test_summary_serialises(two_respondents):
    _, ceo, ic = two_respondents
    _, summary = aggregation.aggregate([("CEO", ceo), ("IC", ic)])
    d = summary.as_dict()
    assert d["respondent_count"] == 2 and d["roles"] == ["CEO", "IC"]
    assert any(x["flagged"] for x in d["dimensions"])
