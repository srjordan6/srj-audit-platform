"""AI IT Security Audit scoring (spec v1.6 S.3): gate rule, unknown zone, areas."""
from __future__ import annotations

from datetime import date

from questionnaire.aiitsa_question_bank import AIITSA_QUESTIONS, BASELINE_AREAS
from scoring import aiitsa


def _all(answer):
    return {q["id"]: {"value": {"selected": answer}, "dont_know": answer == "Don't know"} for q in AIITSA_QUESTIONS}


def test_bank_shape():
    assert len(AIITSA_QUESTIONS) == 143
    assert all(q["id"].startswith("AIITSA-") for q in AIITSA_QUESTIONS)
    assert len({q["id"] for q in AIITSA_QUESTIONS}) == 143
    assert all(q["options"] == ["Yes", "Partially", "No", "Don't know"] for q in AIITSA_QUESTIONS)
    assert all(q["baseline_area"] in BASELINE_AREAS for q in AIITSA_QUESTIONS)
    assert sum(1 for q in AIITSA_QUESTIONS if q["visibility_triangle"]) == 6


def test_gate_rule_caps_self_serve_at_partial():
    r = aiitsa.score_aiitsa(_all("Yes"), assessed_on=date(2026, 9, 27))
    assert r.baseline_score_0_100 == 100.0
    assert all(a.level == 1 and a.level_label == "Partial" and a.capped for a in r.areas)
    assert r.baseline_level_label == "Partial"
    assert r.assessed_on == date(2026, 9, 27)


def test_all_no_is_absent():
    r = aiitsa.score_aiitsa(_all("No"))
    assert r.baseline_score_0_100 == 0.0
    assert all(a.level == 0 and not a.capped for a in r.areas)
    assert r.top_gaps[0] in BASELINE_AREAS


def test_dont_know_is_unknown_zone_exposure_not_missing():
    r = aiitsa.score_aiitsa(_all("Don't know"))
    assert r.answered == 143 and r.unknown_zone_ratio == 1.0
    assert all(a.dont_know == a.answered for a in r.areas)
    assert all(v.zone == "unknown" for v in r.visibility)


def test_visibility_triangle_zones():
    resp = _all("Partially")
    resp["AIITSA-SCR-002"] = {"value": {"selected": "Yes"}, "dont_know": False}
    resp["AIITSA-SCR-003"] = {"value": {"selected": "No"}, "dont_know": False}
    resp["AIITSA-SCR-004"] = {"value": {"selected": "Don't know"}, "dont_know": True}
    r = aiitsa.score_aiitsa(resp)
    zones = {v.domain: v.zone for v in r.visibility}
    assert zones["governance"] == "known"
    assert zones["security_operations"] == "clear"
    assert zones["architecture"] == "unknown"
    assert zones["application_security"] == "suspected"


def test_partial_answers_score_half():
    r = aiitsa.score_aiitsa(_all("Partially"))
    assert r.baseline_score_0_100 == 50.0
    assert all(a.level == 1 for a in r.areas)


def test_unanswered_questions_do_not_count():
    resp = {q["id"]: {"value": {"selected": "Yes"}, "dont_know": False} for q in AIITSA_QUESTIONS[:10]}
    r = aiitsa.score_aiitsa(resp)
    assert r.answered == 10 and r.expected == 143
    unscored = [a for a in r.areas if a.answered == 0]
    assert all(a.level == 0 and a.score_0_100 == 0.0 for a in unscored)


def test_gaps_list_the_questions_that_need_work():
    resp = _all("Yes")
    resp["AIITSA-GOV-001"] = {"value": {"selected": "No"}, "dont_know": False}
    r = aiitsa.score_aiitsa(resp)
    gov = next(a for a in r.areas if a.area == "Governance")
    assert gov.gaps == ["AIITSA-GOV-001"]
    assert r.top_gaps[0] == "Governance"
