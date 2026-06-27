"""
scoring.frameworks.v3_governance — V3 governance framework aggregator.

Implements the AI Risk & Governance Review scoring engine per Part A §4.4.
Aggregates per-question response scores into 6 canonical steps (the
6-Step Review Process), assigns governance maturity levels, computes
the composite, and produces a parallel set of cross-cutting signal
scores that V3 reports use to surface specific risk patterns.

THE 6 STEPS (canonical, per Part A §4.4)
----------------------------------------
    1. accountability_mapping         (8 mappings)
    2. data_exposure_assessment       (9 mappings)
    3. decision_influence_review      (8 mappings)
    4. vendor_risk_inventory          (6 mappings)
    5. framework_crosswalk_readiness  (10 mappings)
    6. incident_response_readiness    (4 mappings)

Composite = mean of the 6 step scores (active steps only). Equal
weighting across steps; Part A §4.4 did not specify differential
weights.

GOVERNANCE MATURITY SCALE (Part A §4.4)
---------------------------------------
    0-20    Level 1  Absent
    21-40   Level 2  Reactive
    41-60   Level 3  Defined
    61-80   Level 4  Integrated
    81-100  Level 5  Continuous

These labels are distinct from the V2 readiness scale (Ad hoc / Emerging
/ Defined / Managed / Optimizing). Reports must use the correct labels
per framework — the report layer should ask the result for
maturity_label rather than hardcoding strings.

CROSS-CUTTING SIGNALS
---------------------
V3 includes 10 questions tagged with a `cross_cutting_signal` instead of
a step. These don't roll into any of the 6 steps; they're diagnostic
overlays surfaced separately in V3 reports. Production currently has
5 signal categories:

    autonomous_execution_readiness  (4 questions, weights 2.0–2.5)
    personal_defensibility          (3 questions, weights 1.5–2.0)
    governance_cadence              (1 question)
    per_system_documentation        (1 question)
    regulatory_confidence           (1 question)

The aggregator produces V3CrossCuttingSignalScore for each populated
category. They contribute to the result for report rendering but are
NOT included in the composite (Part A §4.4 didn't define them; they
were added during Sprint A gap audit). Reports can surface them as
sidebar callouts or as confidence modifiers.

NO INVERSION
------------
Unlike V1's risk_exposure, all V3 steps measure positive governance
signal (higher = more mature governance). No inversion at aggregation.

PURE AGGREGATION, NO DB
-----------------------
Same architecture as v1_audit.py / v2_readiness.py.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from questionnaire.question_bank import Question
from scoring.response_scoring import ResponseScore, score_response

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Framework configuration
# ----------------------------------------------------------------------------

FRAMEWORK_NAME = "v3_governance"

# The 6 canonical steps, in canonical order (Part A §4.4)
V3_STEPS: tuple[str, ...] = (
    "accountability_mapping",
    "data_exposure_assessment",
    "decision_influence_review",
    "vendor_risk_inventory",
    "framework_crosswalk_readiness",
    "incident_response_readiness",
)

# Governance maturity scale (Part A §4.4)
_MATURITY_THRESHOLDS: tuple[tuple[float, int, str], ...] = (
    (20.0, 1, "Absent"),
    (40.0, 2, "Reactive"),
    (60.0, 3, "Defined"),
    (80.0, 4, "Integrated"),
    (100.0, 5, "Continuous"),
)

# Confidence thresholds (consistent across frameworks)
_CONFIDENCE_HIGH_MAX = 0.15
_CONFIDENCE_MEDIUM_MAX = 0.35


# ----------------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ResponseRecord:
    """One normalized response row. Shape-compatible with V1 / V2.

    has_note / has_attachments are OD-16 / OD-17 hooks; not yet wired
    into V3 confidence calculation in v0.1.
    """
    question_id: str
    answer_value: Any
    is_dont_know: bool = False
    has_note: bool = False
    has_attachments: bool = False


@dataclass(frozen=True)
class V3StepContribution:
    """One question's contribution to one step's score."""
    question_id: str
    weight: float
    response_score: ResponseScore


@dataclass(frozen=True)
class V3StepScore:
    """Aggregated score for one of the 6 V3 review steps."""
    name: str
    contributions: list[V3StepContribution]
    weighted_mean_0_1: float
    score_0_100: float
    maturity_level: int            # 1–5
    maturity_label: str            # Absent / Reactive / Defined / Integrated / Continuous
    dk_ratio: float
    confidence_level: str
    expected_count: int
    answered_count: int


@dataclass(frozen=True)
class V3CrossCuttingSignalScore:
    """One cross-cutting signal category (autonomous_execution_readiness, etc).

    Cross-cutting signals are surfaced separately in V3 reports and do
    NOT contribute to the composite. They are diagnostic overlays.
    """
    name: str
    contributions: list[V3StepContribution]
    weighted_mean_0_1: float
    score_0_100: float
    dk_ratio: float
    confidence_level: str
    expected_count: int
    answered_count: int


@dataclass(frozen=True)
class V3FrameworkResult:
    """Full V3 governance result."""
    framework: str
    composite_score_0_100: float       # mean of 6 active step scores
    composite_maturity_level: int
    composite_maturity_label: str
    overall_confidence_level: str
    overall_dk_ratio: float
    steps: list[V3StepScore]
    cross_cutting_signals: list[V3CrossCuttingSignalScore]
    top_gaps: list[V3StepScore]        # 3 lowest-scoring active steps


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def maturity_for_score(score_0_100: float) -> tuple[int, str]:
    """Return (level_int_1_5, label) for a 0–100 governance score."""
    for threshold, level, label in _MATURITY_THRESHOLDS:
        if score_0_100 <= threshold:
            return (level, label)
    return (5, "Continuous")


def confidence_for_dk_ratio(dk_ratio: float) -> str:
    if dk_ratio <= _CONFIDENCE_HIGH_MAX:
        return "high"
    if dk_ratio <= _CONFIDENCE_MEDIUM_MAX:
        return "medium"
    return "low"


# ----------------------------------------------------------------------------
# Mapping extraction
# ----------------------------------------------------------------------------

def _extract_v3_mappings(
    question: Question,
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Return ([(step, weight)], [(cross_cutting_signal, weight)]) for one question.

    A single question can have multiple V3 mappings — typically one step
    mapping or one cross-cutting signal mapping, but the schema allows
    both simultaneously. The aggregator handles whatever the data says.
    """
    step_mappings: list[tuple[str, float]] = []
    cross_cutting_mappings: list[tuple[str, float]] = []

    for m in question.framework_mappings or []:
        if m.get("framework") != FRAMEWORK_NAME:
            continue

        try:
            weight = float(m.get("weight", 1.0))
        except (TypeError, ValueError):
            logger.warning(
                "v3_governance mapping on %s has non-numeric weight %r; defaulting to 1.0",
                question.id, m.get("weight"),
            )
            weight = 1.0

        step = m.get("step")
        signal = m.get("cross_cutting_signal")

        if step:
            if step not in V3_STEPS:
                logger.info(
                    "v3_governance mapping on %s references unknown step %r; including anyway",
                    question.id, step,
                )
            step_mappings.append((step, weight))
        elif signal:
            cross_cutting_mappings.append((signal, weight))
        else:
            logger.info(
                "v3_governance mapping on %s has neither step nor cross_cutting_signal; ignoring",
                question.id,
            )

    return step_mappings, cross_cutting_mappings


# ----------------------------------------------------------------------------
# Generic weighted-mean aggregation (shared between steps and signals)
# ----------------------------------------------------------------------------

def _aggregate_contributions(
    questions_with_weights: list[tuple[Question, float]],
    responses_by_qid: dict[str, ResponseRecord],
    option_weight_override_map: dict[str, dict[str, float]] | None,
) -> tuple[list[V3StepContribution], float, float, int, int]:
    """Score a bag of (question, weight) tuples.

    Returns (contributions, weighted_mean_0_1, dk_ratio, expected, answered).
    Common helper used by both step scoring and cross-cutting signal scoring.
    """
    contributions: list[V3StepContribution] = []
    expected = len(questions_with_weights)
    dk_count = 0

    for question, weight in questions_with_weights:
        response = responses_by_qid.get(question.id)
        if response is None:
            continue

        override = (
            option_weight_override_map.get(question.id)
            if option_weight_override_map
            else None
        )
        score = score_response(
            question, response.answer_value,
            option_weight_override=override,
        )
        if score.excluded:
            continue

        contributions.append(V3StepContribution(
            question_id=question.id,
            weight=weight,
            response_score=score,
        ))
        if score.is_dont_know:
            dk_count += 1

    answered = len(contributions)
    if answered == 0:
        return ([], 0.0, 0.0, expected, 0)

    total_weight = sum(c.weight for c in contributions)
    if total_weight <= 0:
        weighted_mean = sum(c.response_score.value for c in contributions) / answered
    else:
        weighted_mean = (
            sum(c.weight * c.response_score.value for c in contributions)
            / total_weight
        )
    dk_ratio = dk_count / answered

    return (contributions, weighted_mean, dk_ratio, expected, answered)


# ----------------------------------------------------------------------------
# Step scoring
# ----------------------------------------------------------------------------

def _score_step(
    step_name: str,
    questions_with_weights: list[tuple[Question, float]],
    responses_by_qid: dict[str, ResponseRecord],
    option_weight_override_map: dict[str, dict[str, float]] | None,
) -> V3StepScore:
    contributions, weighted_mean, dk_ratio, expected, answered = _aggregate_contributions(
        questions_with_weights, responses_by_qid, option_weight_override_map,
    )

    if answered == 0:
        return V3StepScore(
            name=step_name,
            contributions=[],
            weighted_mean_0_1=0.0,
            score_0_100=0.0,
            maturity_level=1,
            maturity_label="Absent",
            dk_ratio=0.0,
            confidence_level="low",
            expected_count=expected,
            answered_count=0,
        )

    score_0_100 = weighted_mean * 100.0
    level, label = maturity_for_score(score_0_100)

    return V3StepScore(
        name=step_name,
        contributions=contributions,
        weighted_mean_0_1=weighted_mean,
        score_0_100=score_0_100,
        maturity_level=level,
        maturity_label=label,
        dk_ratio=dk_ratio,
        confidence_level=confidence_for_dk_ratio(dk_ratio),
        expected_count=expected,
        answered_count=answered,
    )


# ----------------------------------------------------------------------------
# Cross-cutting signal scoring
# ----------------------------------------------------------------------------

def _score_cross_cutting_signal(
    signal_name: str,
    questions_with_weights: list[tuple[Question, float]],
    responses_by_qid: dict[str, ResponseRecord],
    option_weight_override_map: dict[str, dict[str, float]] | None,
) -> V3CrossCuttingSignalScore:
    contributions, weighted_mean, dk_ratio, expected, answered = _aggregate_contributions(
        questions_with_weights, responses_by_qid, option_weight_override_map,
    )

    return V3CrossCuttingSignalScore(
        name=signal_name,
        contributions=contributions,
        weighted_mean_0_1=weighted_mean,
        score_0_100=weighted_mean * 100.0,
        dk_ratio=dk_ratio,
        confidence_level=confidence_for_dk_ratio(dk_ratio) if answered > 0 else "low",
        expected_count=expected,
        answered_count=answered,
    )


# ----------------------------------------------------------------------------
# Composite + top gaps
# ----------------------------------------------------------------------------

def _compute_composite(steps: list[V3StepScore]) -> float:
    """Mean of active step scores (equal weighting per Part A §4.4)."""
    active = [s for s in steps if s.answered_count > 0]
    if not active:
        return 0.0
    return sum(s.score_0_100 for s in active) / len(active)


def _identify_top_gaps(
    steps: list[V3StepScore],
    n: int = 3,
) -> list[V3StepScore]:
    """Return n lowest-scoring active steps.

    Steps with no answered contributions are excluded — they have no
    diagnostic signal. V3 has no inversion, so lowest score == biggest gap.
    """
    active = [s for s in steps if s.answered_count > 0]
    active.sort(key=lambda s: s.score_0_100)
    return active[:n]


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------

def score_v3_governance(
    questions: list[Question],
    responses_by_qid: dict[str, ResponseRecord],
    *,
    option_weight_override_map: dict[str, dict[str, float]] | None = None,
) -> V3FrameworkResult:
    """Compute the V3 governance framework score.

    Parameters
    ----------
    questions
        All questions to consider — typically the full Tier 1 bank.
        Questions without v3_governance mappings are silently ignored.
    responses_by_qid
        {question_id: ResponseRecord} for the engagement.
    option_weight_override_map
        Optional per-question option-weight maps (forwarded to
        response_scoring).

    Returns
    -------
    V3FrameworkResult containing the composite, 6 step scores, all
    populated cross-cutting signal scores, and the top 3 gaps.
    """
    # Bucket questions by step and cross-cutting signal
    by_step: dict[str, list[tuple[Question, float]]] = defaultdict(list)
    by_signal: dict[str, list[tuple[Question, float]]] = defaultdict(list)

    for q in questions:
        step_maps, signal_maps = _extract_v3_mappings(q)
        for step_name, weight in step_maps:
            by_step[step_name].append((q, weight))
        for signal_name, weight in signal_maps:
            by_signal[signal_name].append((q, weight))

    # Score each canonical step (preserves order, even if empty)
    step_scores: list[V3StepScore] = []
    for step_name in V3_STEPS:
        step_scores.append(_score_step(
            step_name, by_step.get(step_name, []),
            responses_by_qid, option_weight_override_map,
        ))

    # Score each populated cross-cutting signal (sorted by name for stable output)
    signal_scores: list[V3CrossCuttingSignalScore] = []
    for signal_name in sorted(by_signal.keys()):
        signal_scores.append(_score_cross_cutting_signal(
            signal_name, by_signal[signal_name],
            responses_by_qid, option_weight_override_map,
        ))

    composite = _compute_composite(step_scores)
    composite_level, composite_label = maturity_for_score(composite)

    # Overall DK ratio weighted by answered count across steps + signals
    all_scored = [
        *((s.dk_ratio, s.answered_count) for s in step_scores),
        *((s.dk_ratio, s.answered_count) for s in signal_scores),
    ]
    total_answered = sum(ac for _, ac in all_scored)
    weighted_dk = sum(dk * ac for dk, ac in all_scored)
    overall_dk = weighted_dk / total_answered if total_answered else 0.0

    return V3FrameworkResult(
        framework=FRAMEWORK_NAME,
        composite_score_0_100=composite,
        composite_maturity_level=composite_level,
        composite_maturity_label=composite_label,
        overall_confidence_level=confidence_for_dk_ratio(overall_dk),
        overall_dk_ratio=overall_dk,
        steps=step_scores,
        cross_cutting_signals=signal_scores,
        top_gaps=_identify_top_gaps(step_scores, n=3),
    )
