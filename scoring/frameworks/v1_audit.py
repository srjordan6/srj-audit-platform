"""
scoring.frameworks.v1_audit — V1 audit framework aggregator.

Implements the AI Business Enablement Audit scoring engine per Part A §4.2.
Aggregates per-question response scores into the canonical 5 dimensions,
applies risk-exposure inversion, computes confidence levels, identifies
top gaps, and produces a composite 0-100 score.

DIMENSIONS (canonical, production-aligned)
------------------------------------------
    tool_inventory          21 sub-components, weight 0.20
    cost_mapping            13 sub-components, weight 0.20
    performance_measurement 15 sub-components, weight 0.20
    risk_exposure           33 sub-components, weight 0.25  (INVERTED)
    governance_gaps         17 sub-components, weight 0.15

Composite = 0.20·inv + 0.20·cost + 0.20·perf + 0.25·risk + 0.15·gov
All terms are post-inversion. The composite weight on risk is higher than
the others because risk exposure carries the greatest downside per
Part A §4.2.

INVERSION
---------
risk_exposure is INVERTED: per-response signal of 1.0 ("yes, sensitive
data has been entered into AI tools") means HIGH RISK, which is BAD for
the dimension score. We invert at the dimension-aggregation step:
    final_0_100 = 100 - raw_0_100

DIMENSION_ALIASES
-----------------
Production data includes one orphan mapping on T1-A-014 with
`dimension: "governance"` (singular, missing sub_component) instead of
the canonical `governance_gaps`. We alias it silently with a log
warning. Backport fix to question_bank.py and production data deferred.

SCORE BRACKETS (Part A §4.2)
----------------------------
    0-20    Critical
    21-40   Concerning
    41-60   Developing
    61-80   Sound
    81-100  Mature

CONFIDENCE
----------
Per-sub-component confidence = function of Don't Know ratio:
    0-15%    high
    16-35%   medium
    36%+     low
Dimension confidence aggregates DK ratios across active sub-components,
weighted by answered_question_count.

TOP GAPS
--------
The 3 sub-components farthest from target across all dimensions. Target
is 1.0 for non-inverted dimensions, 0.0 for inverted (risk_exposure).
Gap magnitude = distance from target. Top-3 means biggest 3 gaps.
Used to drive report priority-gaps section.

PURE AGGREGATION
----------------
No DB access. Caller (engine.py, separate module) loads responses from
the DB, converts to ResponseRecord, and calls score_v1_audit. This keeps
the aggregator unit-testable without a database.

DESIGN: SUB-COMPONENT EQUAL WEIGHTING
-------------------------------------
v0.1 weights all sub-components equally within a dimension. Production
data has 13-29 sub-components per dimension; Part A §4.2 specified
coarser groupings with explicit point budgets (e.g., 30/25/20/15/10 for
tool_inventory). The granularity expanded between Part A draft and
production build. Reconciling those point budgets to the current
sub-component count is deferred to a later tuning pass — but the
aggregator architecture supports it (replace the equal-weighting in
_aggregate_dimension with budget-aware weighting via a future
SUB_COMPONENT_BUDGETS constant).
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

FRAMEWORK_NAME = "v1_audit"

# Canonical dimensions in canonical order (Part A §4.2)
DIMENSIONS: tuple[str, ...] = (
    "tool_inventory",
    "cost_mapping",
    "performance_measurement",
    "risk_exposure",
    "governance_gaps",
)

# Dimensions whose raw signal is inverted at aggregation time. A high
# per-response score in these dimensions means a BAD state of the world.
INVERTED_DIMENSIONS = frozenset({"risk_exposure"})

# Composite weights per Part A §4.2. Sum to 1.0.
COMPOSITE_WEIGHTS: dict[str, float] = {
    "tool_inventory":          0.20,
    "cost_mapping":            0.20,
    "performance_measurement": 0.20,
    "risk_exposure":           0.25,
    "governance_gaps":         0.15,
}

# Production data has one orphan: T1-A-014 maps to "governance" (singular,
# missing sub_component). Alias to governance_gaps with a log warning.
DIMENSION_ALIASES: dict[str, str] = {
    "governance": "governance_gaps",
}

# Score brackets per Part A §4.2
_BRACKET_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (20.0, "Critical"),
    (40.0, "Concerning"),
    (60.0, "Developing"),
    (80.0, "Sound"),
)
_BRACKET_TOP_LABEL = "Mature"

# Confidence thresholds (% Don't Know responses)
_CONFIDENCE_HIGH_MAX = 0.15
_CONFIDENCE_MEDIUM_MAX = 0.35


# ----------------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ResponseRecord:
    """One row from the responses table, normalized for scoring.

    The caller (engine.py) builds ResponseRecord instances from DB rows
    and passes them to score_v1_audit. This decouples the aggregator
    from Django/ORM specifics.

    has_note / has_attachments are OD-16 / OD-17 hooks for the
    confidence-boost path; the aggregator records them but the v0.1
    confidence model does not yet bump confidence for documented
    responses. Wiring that into the confidence calculation is a later
    tuning pass.
    """
    question_id: str
    answer_value: Any
    is_dont_know: bool = False
    has_note: bool = False
    has_attachments: bool = False


@dataclass(frozen=True)
class QuestionContribution:
    """One question's contribution to a sub-component score."""
    question_id: str
    weight: float                # from framework_mappings.weight (0.5 / 1.0 / 2.0)
    response_score: ResponseScore


@dataclass(frozen=True)
class SubComponentScore:
    """Aggregated score for one sub-component within a dimension.

    weighted_mean_0_1 is the LITERAL signal (0=respondent picked the
    negative end, 1=respondent picked the positive end). Inversion is
    handled at the dimension level, not here.
    """
    dimension: str
    sub_component: str
    contributions: list[QuestionContribution]
    expected_question_count: int    # questions mapped to this sub
    answered_question_count: int    # how many had a non-excluded response
    weighted_mean_0_1: float
    dk_ratio: float
    confidence_level: str           # "high" / "medium" / "low"


@dataclass(frozen=True)
class V1DimensionScore:
    """One of the 5 V1 audit dimensions."""
    name: str
    inverted: bool
    sub_components: list[SubComponentScore]
    raw_score_0_100: float          # pre-inversion mean of sub-components
    final_score_0_100: float        # post-inversion (== raw if not inverted)
    bracket: str                    # Critical / Concerning / Developing / Sound / Mature
    confidence_level: str
    dk_ratio: float
    answered_count: int
    expected_count: int


@dataclass(frozen=True)
class V1FrameworkResult:
    """Full V1 audit result, ready for report generation."""
    framework: str
    composite_score_0_100: float
    composite_bracket: str
    overall_confidence_level: str
    overall_dk_ratio: float
    dimensions: list[V1DimensionScore]
    top_gaps: list[SubComponentScore]   # 3 sub-components farthest from target


# ----------------------------------------------------------------------------
# Bracket and confidence helpers
# ----------------------------------------------------------------------------

def bracket_for_score(score_0_100: float) -> str:
    for threshold, name in _BRACKET_THRESHOLDS:
        if score_0_100 <= threshold:
            return name
    return _BRACKET_TOP_LABEL


def confidence_for_dk_ratio(dk_ratio: float) -> str:
    if dk_ratio <= _CONFIDENCE_HIGH_MAX:
        return "high"
    if dk_ratio <= _CONFIDENCE_MEDIUM_MAX:
        return "medium"
    return "low"


# ----------------------------------------------------------------------------
# Mapping extraction
# ----------------------------------------------------------------------------

def _extract_v1_mappings(
    question: Question,
) -> list[tuple[str, str, float]]:
    """Return [(dimension, sub_component, weight)] for v1_audit mappings.

    Applies DIMENSION_ALIASES with a log warning. Treats missing
    sub_component as "_unspecified" (preserves the orphan question's
    contribution without losing visibility of the data quality issue).
    """
    out: list[tuple[str, str, float]] = []
    for m in question.framework_mappings or []:
        if m.get("framework") != FRAMEWORK_NAME:
            continue
        dim = m.get("dimension")
        if not dim:
            continue
        dim_canonical = DIMENSION_ALIASES.get(dim, dim)
        if dim_canonical != dim:
            logger.info(
                "v1_audit aliasing dimension %r -> %r on question %s",
                dim, dim_canonical, question.id,
            )
        sub = m.get("sub_component") or "_unspecified"
        if sub == "_unspecified":
            logger.info(
                "v1_audit mapping on %s has no sub_component (using _unspecified)",
                question.id,
            )
        try:
            weight = float(m.get("weight", 1.0))
        except (TypeError, ValueError):
            logger.warning(
                "v1_audit mapping on %s has non-numeric weight %r; defaulting to 1.0",
                question.id, m.get("weight"),
            )
            weight = 1.0
        out.append((dim_canonical, sub, weight))
    return out


def _group_questions_by_dim_sub(
    questions: list[Question],
) -> dict[str, dict[str, list[tuple[Question, float]]]]:
    """Build {dimension: {sub_component: [(question, weight)]}}."""
    grouped: dict[str, dict[str, list[tuple[Question, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for q in questions:
        for dim, sub, weight in _extract_v1_mappings(q):
            grouped[dim][sub].append((q, weight))
    return grouped


# ----------------------------------------------------------------------------
# Sub-component scoring
# ----------------------------------------------------------------------------

def _score_sub_component(
    dimension: str,
    sub_component: str,
    questions_with_weights: list[tuple[Question, float]],
    responses_by_qid: dict[str, ResponseRecord],
    option_weight_override_map: dict[str, dict[str, float]] | None,
) -> SubComponentScore:
    """Compute a sub-component score as the weighted mean of question signals.

    Unanswered questions are silently excluded from the mean (they simply
    don't contribute). Excluded response types (TEXT, RANK) are also
    skipped. expected_question_count reflects the total assigned;
    answered_question_count reflects what actually contributed.
    """
    contributions: list[QuestionContribution] = []
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

        contributions.append(QuestionContribution(
            question_id=question.id,
            weight=weight,
            response_score=score,
        ))
        if score.is_dont_know:
            dk_count += 1

    answered = len(contributions)

    if answered == 0:
        return SubComponentScore(
            dimension=dimension,
            sub_component=sub_component,
            contributions=[],
            expected_question_count=expected,
            answered_question_count=0,
            weighted_mean_0_1=0.0,
            dk_ratio=0.0,
            confidence_level="low",
        )

    total_weight = sum(c.weight for c in contributions)
    if total_weight <= 0:
        # Degenerate: weights all zero. Fall back to simple mean.
        weighted_mean = sum(c.response_score.value for c in contributions) / answered
    else:
        weighted_mean = (
            sum(c.weight * c.response_score.value for c in contributions)
            / total_weight
        )

    dk_ratio = dk_count / answered
    return SubComponentScore(
        dimension=dimension,
        sub_component=sub_component,
        contributions=contributions,
        expected_question_count=expected,
        answered_question_count=answered,
        weighted_mean_0_1=weighted_mean,
        dk_ratio=dk_ratio,
        confidence_level=confidence_for_dk_ratio(dk_ratio),
    )


# ----------------------------------------------------------------------------
# Dimension aggregation
# ----------------------------------------------------------------------------

def _aggregate_dimension(
    dimension: str,
    sub_component_scores: list[SubComponentScore],
) -> V1DimensionScore:
    """Aggregate sub-components into a dimension score (0-100).

    v0.1: equal weighting across active sub-components (those with at
    least one answered question). Inactive sub-components (no responses
    at all) are kept in the result for visibility but excluded from the
    mean. See module docstring for the future SUB_COMPONENT_BUDGETS
    extension path.
    """
    inverted = dimension in INVERTED_DIMENSIONS

    active = [s for s in sub_component_scores if s.answered_question_count > 0]
    total_expected = sum(s.expected_question_count for s in sub_component_scores)
    total_answered = sum(s.answered_question_count for s in active)

    if not active:
        return V1DimensionScore(
            name=dimension,
            inverted=inverted,
            sub_components=sub_component_scores,
            raw_score_0_100=0.0,
            final_score_0_100=100.0 if inverted else 0.0,  # no risk signal = best risk score
            bracket=_BRACKET_TOP_LABEL if inverted else "Critical",
            confidence_level="low",
            dk_ratio=0.0,
            answered_count=0,
            expected_count=total_expected,
        )

    mean_0_1 = sum(s.weighted_mean_0_1 for s in active) / len(active)
    raw_0_100 = mean_0_1 * 100.0
    final_0_100 = 100.0 - raw_0_100 if inverted else raw_0_100

    # Weight DK ratios by answered_question_count to avoid a sparse sub
    # dominating the dimension-level confidence signal.
    weighted_dk_sum = sum(s.dk_ratio * s.answered_question_count for s in active)
    dim_dk_ratio = weighted_dk_sum / total_answered if total_answered else 0.0

    return V1DimensionScore(
        name=dimension,
        inverted=inverted,
        sub_components=sub_component_scores,
        raw_score_0_100=raw_0_100,
        final_score_0_100=final_0_100,
        bracket=bracket_for_score(final_0_100),
        confidence_level=confidence_for_dk_ratio(dim_dk_ratio),
        dk_ratio=dim_dk_ratio,
        answered_count=total_answered,
        expected_count=total_expected,
    )


# ----------------------------------------------------------------------------
# Gap identification
# ----------------------------------------------------------------------------

def _gap_magnitude(sub: SubComponentScore) -> float:
    """Distance from target.

    Non-inverted dimensions: target=1.0; gap = 1.0 − signal.
    Inverted dimensions: target=0.0; gap = signal.
    """
    if sub.dimension in INVERTED_DIMENSIONS:
        return sub.weighted_mean_0_1
    return 1.0 - sub.weighted_mean_0_1


def _identify_top_gaps(
    dimensions: list[V1DimensionScore],
    n: int = 3,
) -> list[SubComponentScore]:
    """Return n sub-components with the largest gap from target.

    Excludes sub-components with no answered questions (they have no
    diagnostic signal).
    """
    all_subs: list[SubComponentScore] = []
    for d in dimensions:
        for s in d.sub_components:
            if s.answered_question_count > 0:
                all_subs.append(s)

    all_subs.sort(key=_gap_magnitude, reverse=True)
    return all_subs[:n]


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------

def score_v1_audit(
    questions: list[Question],
    responses_by_qid: dict[str, ResponseRecord],
    *,
    option_weight_override_map: dict[str, dict[str, float]] | None = None,
) -> V1FrameworkResult:
    """Compute the V1 audit framework score from questions and responses.

    Parameters
    ----------
    questions
        All questions to consider — typically the full Tier 1 bank.
        Questions without v1_audit mappings are silently ignored.
    responses_by_qid
        {question_id: ResponseRecord} for the engagement. Questions in
        `questions` whose IDs are absent from this dict are treated as
        unanswered (excluded from sub-component means).
    option_weight_override_map
        Optional per-question option-weight maps for use by the
        response_scoring layer (future option_weights.py). Passed
        through transparently.

    Returns
    -------
    V1FrameworkResult with composite + dimension scores, confidence,
    brackets, and top gaps.
    """
    grouped = _group_questions_by_dim_sub(questions)

    dimensions: list[V1DimensionScore] = []
    for dim_name in DIMENSIONS:
        sub_map = grouped.get(dim_name, {})
        sub_scores = [
            _score_sub_component(
                dim_name, sub_name, qs_w,
                responses_by_qid, option_weight_override_map,
            )
            for sub_name, qs_w in sorted(sub_map.items())
        ]
        dimensions.append(_aggregate_dimension(dim_name, sub_scores))

    composite = sum(
        d.final_score_0_100 * COMPOSITE_WEIGHTS[d.name]
        for d in dimensions
    )

    total_answered = sum(d.answered_count for d in dimensions)
    weighted_dk = sum(d.dk_ratio * d.answered_count for d in dimensions)
    overall_dk = weighted_dk / total_answered if total_answered else 0.0

    return V1FrameworkResult(
        framework=FRAMEWORK_NAME,
        composite_score_0_100=composite,
        composite_bracket=bracket_for_score(composite),
        overall_confidence_level=confidence_for_dk_ratio(overall_dk),
        overall_dk_ratio=overall_dk,
        dimensions=dimensions,
        top_gaps=_identify_top_gaps(dimensions, n=3),
    )
