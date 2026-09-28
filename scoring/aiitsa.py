"""Scoring for the AI IT Security Audit(TM) (Pillar II, instrument "aiitsa").

Spec: AIITSA_Audit_Program_Source_Spec v1.6 S.3, with v1.9 conventions.

  Unit of score   each of the seven Defensible AI Security Baseline areas
                  gets one maturity level: 0 Absent, 1 Partial,
                  2 Defensible, 3 Mature.
  Gate rule       questionnaire answers alone cap an area at Partial.
                  Defensible and Mature need a dated artefact verified at
                  the analyst tier (Tier 2, S.7). Self-serve therefore
                  yields 0 or 1 per area, never higher, and says so.
  Baseline Score  dated composite of the seven areas, 0-100, always shown
                  with its date (an undated score is indefensible by the
                  book's own standard).
  Unknown zone    "Don't know" is not a missing answer, it is exposure:
                  counted per area and, for the six Visibility Triangle
                  questions (SCR-002..007), per domain.

Answer values: Yes 1.0, Partially 0.5, No 0.0, Don't know 0.0 (and counted
as unknown). Equal question weights and equal area weights: the spec sets
neither, so the simplest defensible choice is used and recorded here.

Build decisions not in the spec, all data in this module:
  ABSENT_BELOW    an area whose mean is below 0.35 is Absent, else Partial.
  Area weights    equal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from questionnaire.aiitsa_question_bank import AIITSA_QUESTIONS, BASELINE_AREAS

ANSWER_VALUE = {"yes": 1.0, "partially": 0.5, "no": 0.0, "don't know": 0.0, "dont know": 0.0}
ABSENT_BELOW = 0.35
SELF_SERVE_CAP = 1          # gate rule: Partial is the ceiling without evidence
LEVEL_LABEL = {0: "Absent", 1: "Partial", 2: "Defensible", 3: "Mature"}

MINIMUM_STANDARD = {
    "Inventory": "Current, dated AI inventory covering sanctioned tools, suspected tools, embedded features, and agents",
    "Access": "Current enumeration of every non-human identity with AI-related privileges, agent API keys, MCP servers, with a completed access review cycle",
    "Data": "Data flow map tracing every category of sensitive data through every AI system that touches it",
    "Vendors": "Tiered vendor inventory classifying AI vendors by depth of data access and model training rights",
    "Incidents": "Documented and rehearsed AI incident response capability including a tested AI Red Button",
    "Governance": "AI risk register with specific entries for algorithmic risk, autonomous agents, and non-human identity",
    "Evidence": "A dated, scored Baseline scorecard documenting current state of all seven areas and the gap/remediation roadmap",
}

DOMAIN_OF_VT = {  # Visibility Triangle question -> domain it opens
    "AIITSA-SCR-002": "governance", "AIITSA-SCR-003": "security_operations",
    "AIITSA-SCR-004": "architecture", "AIITSA-SCR-005": "application_security",
    "AIITSA-SCR-006": "third_party_risk", "AIITSA-SCR-007": "data_protection",
}


@dataclass(frozen=True)
class AreaScore:
    area: str
    mean_0_1: float
    score_0_100: float
    level: int
    level_label: str
    capped: bool                 # True when the gate rule held the level down
    answered: int
    expected: int
    dont_know: int
    minimum_standard: str
    gaps: list[str] = field(default_factory=list)   # question ids answered No / Don't know


@dataclass(frozen=True)
class VisibilityZone:
    domain: str
    question_id: str
    answer: str | None
    zone: str                    # known | suspected | clear | unknown | unanswered


@dataclass(frozen=True)
class AIITSAResult:
    instrument: str
    assessed_on: date
    baseline_score_0_100: float
    baseline_level: int
    baseline_level_label: str
    areas: list[AreaScore]
    visibility: list[VisibilityZone]
    unknown_zone_ratio: float    # Don't know share across all answered
    answered: int
    expected: int
    top_gaps: list[str]          # areas ordered weakest first


def _value(resp: Any) -> tuple[float | None, bool]:
    """(numeric value, is_dont_know). None when the answer is unusable."""
    if resp is None:
        return None, False
    raw = resp.get("value") if isinstance(resp, dict) else getattr(resp, "answer_value", resp)
    if isinstance(raw, dict):
        raw = raw.get("selected", raw.get("value"))
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw is None:
        return None, False
    key = str(raw).strip().lower().replace("\u2019", "'")
    dk = key.startswith("don")
    if key not in ANSWER_VALUE:
        return None, False
    return ANSWER_VALUE[key], dk


def score_aiitsa(responses: dict[str, Any], *, questions: list[dict] | None = None,
                 assessed_on: date | None = None) -> AIITSAResult:
    """responses: {question_id: {"value": ..., "dont_know": bool}} as the
    platform loads them. Questions default to the full active bank."""
    questions = [q for q in (questions or AIITSA_QUESTIONS) if q.get("is_active", True)]
    assessed_on = assessed_on or date.today()

    per_area: dict[str, dict[str, Any]] = {a: {"vals": [], "dk": 0, "expected": 0, "gaps": []} for a in BASELINE_AREAS}
    visibility: list[VisibilityZone] = []
    total_answered = total_dk = 0

    for q in questions:
        area = per_area[q["baseline_area"]]
        area["expected"] += 1
        resp = responses.get(q["id"])
        val, dk = _value(resp)
        if resp is not None and (resp.get("dont_know") if isinstance(resp, dict) else False):
            val, dk = 0.0, True
        if q["id"] in DOMAIN_OF_VT:
            answer = None
            if resp is not None:
                raw = resp.get("value") if isinstance(resp, dict) else None
                answer = (raw.get("selected") if isinstance(raw, dict) else raw)
                answer = answer[0] if isinstance(answer, list) and answer else answer
            # "Can you name X that is wrong?" Yes = the risk is known (seen);
            # No = they cannot name one (suspected clear, or blind);
            # Don't know = the unknown zone the Visibility Triangle exists to expose.
            zone = ("unanswered" if answer is None else "unknown" if dk
                    else "known" if str(answer).lower() == "yes"
                    else "suspected" if str(answer).lower() == "partially" else "clear")
            visibility.append(VisibilityZone(DOMAIN_OF_VT[q["id"]], q["id"], answer, zone))
        if val is None:
            continue
        total_answered += 1
        area["vals"].append(val)
        if dk:
            area["dk"] += 1
            total_dk += 1
        if val < 1.0:
            area["gaps"].append(q["id"])

    areas: list[AreaScore] = []
    for name in BASELINE_AREAS:
        a = per_area[name]
        mean = (sum(a["vals"]) / len(a["vals"])) if a["vals"] else 0.0
        natural = 0 if mean < ABSENT_BELOW else 1 if mean < 0.7 else 2 if mean < 0.9 else 3
        level = min(natural, SELF_SERVE_CAP)
        areas.append(AreaScore(
            area=name, mean_0_1=mean, score_0_100=round(mean * 100, 1),
            level=level, level_label=LEVEL_LABEL[level], capped=natural > level,
            answered=len(a["vals"]), expected=a["expected"], dont_know=a["dk"],
            minimum_standard=MINIMUM_STANDARD[name], gaps=a["gaps"],
        ))

    scored = [x for x in areas if x.answered]
    baseline = (sum(x.mean_0_1 for x in scored) / len(scored) * 100) if scored else 0.0
    b_level = min(0 if baseline < ABSENT_BELOW * 100 else 1, SELF_SERVE_CAP)
    return AIITSAResult(
        instrument="aiitsa", assessed_on=assessed_on,
        baseline_score_0_100=round(baseline, 1),
        baseline_level=b_level, baseline_level_label=LEVEL_LABEL[b_level],
        areas=areas, visibility=visibility,
        unknown_zone_ratio=(total_dk / total_answered) if total_answered else 0.0,
        answered=total_answered, expected=len(questions),
        top_gaps=[x.area for x in sorted(scored, key=lambda x: x.mean_0_1)],
    )
