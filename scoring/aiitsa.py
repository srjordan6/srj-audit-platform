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


def questions_in_scope(responses: dict[str, Any], tier: str | None = "tier_1") -> list[dict]:
    """The questions an engagement is scored against: the Tier 1 bank, or at
    Tier 2 the extended bank minus any gated set whose gate was answered
    No or Don't know, or not answered at all (OD-20: a skipped set never
    counts against the company)."""
    from questionnaire.aiitsa_question_bank import questions_for_tier
    out = []
    for q in questions_for_tier(tier):
        gate = (q.get("extended_metadata") or {}).get("gated_by")
        if gate:
            g = responses.get(gate)
            raw = g.get("value") if isinstance(g, dict) else None
            ans = raw.get("selected") if isinstance(raw, dict) else raw
            if ans is None or str(ans).lower() not in ("yes", "partially"):
                continue
        out.append(q)
    return out


def score_aiitsa(responses: dict[str, Any], *, questions: list[dict] | None = None,
                 assessed_on: date | None = None, tier: str | None = None) -> AIITSAResult:
    """responses: {question_id: {"value": ..., "dont_know": bool}} as the
    platform loads them. Questions default to the Tier 1 bank, or to the
    in-scope Tier 2 bank when tier is given."""
    if questions is None:
        questions = questions_in_scope(responses, tier or "tier_1")
    questions = [q for q in questions if q.get("is_active", True)]
    assessed_on = assessed_on or date.today()

    per_area: dict[str, dict[str, Any]] = {a: {"vals": [], "dk": 0, "expected": 0, "gaps": []} for a in BASELINE_AREAS}
    visibility: list[VisibilityZone] = []
    total_answered = total_dk = 0

    for q in questions:
        if not (q.get("scoring_weight", 1.0) or 0):
            continue                          # OD-20 gates: asked, never scored
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
        answered=total_answered, expected=sum(1 for q in questions if (q.get("scoring_weight", 1.0) or 0)),
        top_gaps=[x.area for x in sorted(scored, key=lambda x: x.mean_0_1)],
    )


# ----------------------------------------------------------------------------
# Multi-respondent aggregation (Tier 2 on the security instrument)
# ----------------------------------------------------------------------------
# The Baseline is a company-level fact, so N respondents are scored one at
# a time and their AREA means are averaged with the same leadership /
# workforce split Pillar I uses (scoring.tier_2_role_weights). Divergence
# per area at the same 20-point threshold. Don't-know exposure is the
# average share. Visibility Triangle zones take the most severe answer any
# respondent gave: one person who cannot say whether a blind spot exists
# means the company cannot say.

from statistics import fmean

_ZONE_SEVERITY = {"unknown": 4, "suspected": 3, "known": 2, "clear": 1, "unanswered": 0}
_DIVERGENCE_THRESHOLD = 20.0


def aggregate_aiitsa(per_respondent: list[tuple[str, AIITSAResult]], *,
                     assessed_on: date | None = None) -> tuple[AIITSAResult, dict[str, Any]]:
    """per_respondent: [(role, AIITSAResult), ...]. Returns the combined
    result and a summary dict {dimensions: [...], contested: [], roles}."""
    from scoring.tier_2_role_weights import LEADERSHIP, WORKFORCE
    if not per_respondent:
        raise ValueError("no respondents to aggregate")
    if len(per_respondent) == 1:
        r = per_respondent[0][1]
        return r, {"respondent_count": 1, "roles": [per_respondent[0][0]], "dimensions": [], "contested": []}

    assessed_on = assessed_on or max(r.assessed_on for _, r in per_respondent)
    roles = [role for role, _ in per_respondent]
    areas: list[AreaScore] = []
    dims: list[dict[str, Any]] = []
    for name in BASELINE_AREAS:
        per = [(role, next(a for a in r.areas if a.area == name)) for role, r in per_respondent]
        scored = [(role, a) for role, a in per if a.answered]
        if not scored:
            areas.append(per[0][1]); continue
        mean = fmean(a.mean_0_1 for _, a in scored)
        lead = [a.mean_0_1 for role, a in scored if role in LEADERSHIP]
        work = [a.mean_0_1 for role, a in scored if role in WORKFORCE]
        lm = fmean(lead) * 100 if lead else None
        wm = fmean(work) * 100 if work else None
        div = (lm - wm) if (lm is not None and wm is not None) else None
        flagged = div is not None and abs(div) >= _DIVERGENCE_THRESHOLD
        natural = 0 if mean < ABSENT_BELOW else 1 if mean < 0.7 else 2 if mean < 0.9 else 3
        level = min(natural, SELF_SERVE_CAP)
        gaps = sorted({g for _, a in scored for g in a.gaps})
        areas.append(AreaScore(
            area=name, mean_0_1=mean, score_0_100=round(mean * 100, 1),
            level=level, level_label=LEVEL_LABEL[level], capped=natural > level,
            answered=sum(a.answered for _, a in scored), expected=max(a.expected for _, a in scored),
            dont_know=sum(a.dont_know for _, a in scored),
            minimum_standard=MINIMUM_STANDARD[name], gaps=gaps,
        ))
        dims.append({"framework": "aiitsa", "dimension": name, "score_0_100": round(mean * 100, 1),
                     "contributing": len(scored), "excluded": len(per) - len(scored),
                     "leadership_mean": lm, "workforce_mean": wm, "divergence": div, "flagged": flagged})

    # Visibility Triangle: most severe zone per domain across respondents
    by_domain: dict[str, VisibilityZone] = {}
    for _, r in per_respondent:
        for v in r.visibility:
            cur = by_domain.get(v.domain)
            if cur is None or _ZONE_SEVERITY[v.zone] > _ZONE_SEVERITY[cur.zone]:
                by_domain[v.domain] = v
    visibility = [by_domain[d] for d in DOMAIN_OF_VT.values() if d in by_domain]

    scored_areas = [a for a in areas if a.answered]
    baseline = fmean(a.mean_0_1 for a in scored_areas) * 100 if scored_areas else 0.0
    b_level = min(0 if baseline < ABSENT_BELOW * 100 else 1, SELF_SERVE_CAP)
    answered = sum(r.answered for _, r in per_respondent)
    dk = sum(round(r.unknown_zone_ratio * r.answered) for _, r in per_respondent)
    combined = AIITSAResult(
        instrument="aiitsa", assessed_on=assessed_on,
        baseline_score_0_100=round(baseline, 1),
        baseline_level=b_level, baseline_level_label=LEVEL_LABEL[b_level],
        areas=areas, visibility=visibility,
        unknown_zone_ratio=(dk / answered) if answered else 0.0,
        answered=answered, expected=per_respondent[0][1].expected,
        top_gaps=[a.area for a in sorted(scored_areas, key=lambda a: a.mean_0_1)],
    )
    return combined, {"respondent_count": len(per_respondent), "roles": roles,
                      "divergence_threshold": _DIVERGENCE_THRESHOLD, "dimensions": dims, "contested": []}
