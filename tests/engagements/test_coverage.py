"""Coverage rules (Part B-1 S.3, Part A S.1.2) - pure-function tests."""

from __future__ import annotations

from engagements.coverage import RespondentSummary as R, evaluate


def _r(role, completion=1.0, attested=True, status="completed", n=[0]):
    n[0] += 1
    return R(id=f"r{n[0]}", role=role, completion=completion, attested=attested, status=status)


def test_tier_1_is_met_by_one_completed_respondent():
    rep = evaluate("tier_1", None, [_r("CEO")])
    assert rep.is_met and rep.minimum == 1


def test_tier_1_not_met_when_nobody_completed():
    rep = evaluate("tier_1", None, [_r("CEO", completion=0.3)])
    assert not rep.is_met


def test_small_company_met_with_ceo_ops_and_ic():
    rep = evaluate("tier_2", "1-25", [_r("CEO"), _r("MGR"), _r("IC")])
    assert rep.is_met, rep.missing_items


def test_small_company_missing_employee_is_named():
    rep = evaluate("tier_2", "1-25", [_r("CEO"), _r("MGR"), _r("VP")])
    assert not rep.is_met
    assert any("employee" in m for m in rep.missing_items)


def test_sixty_percent_rule_excludes_abandoners():
    rep = evaluate("tier_2", "1-25", [_r("CEO"), _r("MGR"), _r("IC", completion=0.59)])
    assert not rep.is_met
    assert rep.counted == 2
    assert any("59% answered" in m for m in rep.missing_items)


def test_unattested_respondent_does_not_count():
    rep = evaluate("tier_2", "1-25", [_r("CEO"), _r("MGR"), _r("IC", attested=False)])
    assert not rep.is_met
    assert any("attestation" in m for m in rep.missing_items)


def test_removed_respondents_are_ignored():
    rep = evaluate("tier_2", "1-25", [_r("CEO"), _r("MGR"), _r("IC"), _r("IC", status="removed")])
    assert rep.is_met and rep.invited == 3


def test_narrow_slots_are_filled_first():
    """A CIO must satisfy 'IT lead', not be spent on 'ops lead'."""
    rep = evaluate("tier_2", "26-100", [_r("CEO"), _r("CFO"), _r("CIO"), _r("COO"), _r("MGR")])
    assert rep.is_met, rep.missing_items


def test_mid_company_requires_two_directors_and_two_employees():
    base = [_r("CEO"), _r("CFO"), _r("CISO"), _r("COO"), _r("HR"), _r("DIR"), _r("IC")]
    rep = evaluate("tier_2", "101-500", base)
    assert not rep.is_met
    gaps = rep.details["role_gaps"]
    assert gaps == {"director": 1, "employee": 1}
    rep2 = evaluate("tier_2", "101-500", base + [_r("DIR"), _r("IC")])
    assert rep2.is_met, rep2.missing_items


def test_minimum_count_enforced_independently_of_roles():
    """Right roles, but too few bodies: 501-2000 needs 15."""
    roles = ["CEO", "CFO", "CIO", "COO", "HR", "VP", "VP", "MGR", "MGR", "MGR",
             "IC", "IC", "IC", "IC"]  # 14
    rep = evaluate("tier_2", "501-2000", [_r(x) for x in roles])
    assert not rep.is_met
    assert any("1 more completed" in m for m in rep.missing_items)


def test_unknown_bracket_blocks_with_explanation():
    rep = evaluate("tier_2", None, [_r("CEO")])
    assert not rep.is_met and "size bracket" in rep.missing_items[0]
