"""
scoring.frameworks.efficiency — Efficiency framework aggregator.

Implements the AI Efficiency & Process Optimization scoring engine per
Part A §4.5. Two component scores plus a composite:

    outcome_alignment       — Are AI investments tied to measurable outcomes?
    process_optimization    — Is AI genuinely improving processes vs. generating activity?

    efficiency = (outcome_alignment × 0.5) + (process_optimization × 0.5)

DUAL-LAYER MAPPING (with exclusive override)
--------------------------------------------
Same shape as v2_readiness, with one important difference:

* If a question has ANY explicit efficiency mapping in framework_mappings,
  ONLY those explicit mappings apply. Section rules do NOT add additional
  components to that question — explicit choices are exclusive.

* If a question has NO explicit efficiency mappings but matches a
  section rule, the section rule applies.

The exclusive-explicit rule resolves a real divergence in current data:
production places G.3 confidence-signal questions (T1-G-009, T1-G-012)
into `outcome_alignment` explicitly, while Part A §4.5 puts G.3 under
`process_optimization` as a section rule. The exclusive rule respects
the explicit placement and falls back to Part A's rule only for G.3
questions without explicit mappings (T1-G-010, T1-G-011).

SECTION RULES (Part A §4.5)
---------------------------
    outcome_alignment       D.1 (metric existence), G.1 (outcome alignment)
    process_optimization    D.2 (output quality), D.3 (comparative perf),
                            G.2 (process redesign), G.3 (confidence signals)

BRACKETS
--------
Reuses V1's Critical / Concerning / Developing / Sound / Mature labels.
Part A §4.5 did not define a unique maturity scale for efficiency; the
0-100 bracket spectrum is sufficient.

NO INVERSION, NO SUB-COMPONENTS, NO CROSS-CUTTING SIGNALS
---------------------------------------------------------
Both components measure positive signal (higher = better). The flat
question→component structure means no further hierarchy below the two
top-level components.

PURE AGGREGATION, NO DB
-----------------------
Same pattern as v1_audit / v2_readiness / v3_governance.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from questionnaire.question_bank import Question
from scoring.response_scoring import ResponseScore, score_response

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Framework configuration
# ----------------------------------------------------------------------------

FRAMEWORK_NAME = "efficiency"

EFFICIENCY_COMPONENTS: tuple[str, ...] = (
    "outcome_alignment",
    "process_optimization",
)

# Composite weights per Part A §4.5: 50/50.
COMPOSITE_WEIGHTS: dict[str, float] = {
    "outcome_alignment":    0.5,
    "process_optimization": 0.5,
}

# Section-rule fallback. Applied per Part A §4.5 to questions that have
# NO explicit efficiency mapping in their framework_mappings.
EFFICIENCY_SECTION_RULES: dict[str, list[str]] = {
    "outcome_alignment":    ["D.1", "G.1"],
    "process_optimization": ["D.2", "D.3", "G.2", "G.3"],
}

# Score brackets (same labels as V1 audit)
_BRACKET_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (20.0, "Critical"),
    (40.0, "Concerning"),
    (60.0, "Developing"),
    (80.0, "Sound"),
)
_BRACKET_TOP_LABEL = "Mature"

# Confidence thresholds (consistent across frameworks)
_CONFIDENCE_HIGH_MAX = 0.15
_CONFIDENCE_MEDIUM_MAX = 0.35


# ----------------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------------

ContributionSource = Literal["explicit", "section_rule"]


@dataclass(frozen=True)
class ResponseRecord:
    """One normalized response row. Shape-compatible with V1 / V2 / V3."""
    question_id: str
    answer_value: Any
    is_dont_know: bool = False
    has_note: bool = False
    has_attachments: bool = False


@dataclass(frozen=True)
class _ComponentAssignment:
    """Internal — one (question → component) mapping, before scoring."""
    component: str
    weight: float
    source: ContributionSource


@dataclass(frozen=True)
class EfficiencyContribution:
    """One question's contribution to one component's score."""
    question_id: str
    weight: float
    source: ContributionSource
    response_score: ResponseScore


@dataclass(frozen=True)
class EfficiencyComponentScore:
    """Aggregated score for one of the two efficiency components."""
    name: str                               # outcome_alignment | process_optimization
    contributions: list[EfficiencyContribution]
    weighted_mean_0_1: float
    score_0_100: float
    bracket: str
    dk_ratio: float
    confidence_level: str
    expected_count: int
    answered_count: int
    explicit_contribution_count: int
    section_rule_contribution_count: int


@dataclass(frozen=True)
class EfficiencyFrameworkResult:
    """Full efficiency result."""
    framework: str
    composite_score_0_100: float            # 0.5 × outcome + 0.5 × process
    composite_bracket: str
    overall_confidence_level: str
    overall_dk_ratio: float
    components: list[EfficiencyComponentScore]
    top_gaps: list[EfficiencyComponentScore]  # 1 or 2 — whichever components scored lowest


# ----------------------------------------------------------------------------
# Helpers
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
# Mapping resolution (dual-layer with exclusive explicit override)
# ----------------------------------------------------------------------------

def _extract_explicit_mappings(question: Question) -> list[_ComponentAssignment]:
    """Pull efficiency mappings from question.framework_mappings.

    Production data uses `sub_component` as the component-name field
    (no `component` field). The aggregator reads `sub_component` first
    and falls back to `component` for future-compat.
    """
    out: list[_ComponentAssignment] = []
    for m in question.framework_mappings or []:
        if m.get("framework") != FRAMEWORK_NAME:
            continue

        # Production uses sub_component; tolerate `component` as alternate name
        component = m.get("sub_component") or m.get("component")
        if not component:
            logger.info(
                "efficiency mapping on %s has no sub_component or component; ignoring",
                question.id,
            )
            continue

        if component not in EFFICIENCY_COMPONENTS:
            logger.info(
                "efficiency mapping on %s references unknown component %r; including anyway",
                question.id, component,
            )

        try:
            weight = float(m.get("weight", 1.0))
        except (TypeError, ValueError):
            logger.warning(
                "efficiency mapping on %s has non-numeric weight %r; defaulting to 1.0",
                question.id, m.get("weight"),
            )
            weight = 1.0

        out.append(_ComponentAssignment(
            component=component,
            weight=weight,
            source="explicit",
        ))

    return out


def _section_rule_assignments(question: Question) -> list[_ComponentAssignment]:
    """Apply EFFICIENCY_SECTION_RULES based on question.subsection."""
    if not question.subsection:
        return []
    out: list[_ComponentAssignment] = []
    for component, subsections in EFFICIENCY_SECTION_RULES.items():
        if question.subsection in subsections:
            out.append(_ComponentAssignment(
                component=component,
                weight=1.0,
                source="section_rule",
            ))
    return out


def _resolve_question_to_components(question: Question) -> list[_ComponentAssignment]:
    """Return all component assignments for one question.

    EXCLUSIVE explicit override: if the question has ANY explicit
    efficiency mapping, ONLY those apply. Section rules contribute
    only when no explicit mappings exist for the question.
    """
    explicit = _extract_explicit_mappings(question)
    if explicit:
        return explicit
    return _section_rule_assignments(question)


# ----------------------------------------------------------------------------
# Component scoring
# ----------------------------------------------------------------------------

def _score_component(
    component_name: str,
    question_assignments: list[tuple[Question, _ComponentAssignment]],
    responses_by_qid: dict[str, ResponseRecord],
    option_weight_override_map: dict[str, dict[str, float]] | None,
) -> EfficiencyComponentScore:
    """Compute one component's score from its assigned questions."""
    contributions: list[EfficiencyContribution] = []
    expected = len(question_assignments)
    dk_count = 0
    explicit_count = 0
    section_rule_count = 0

    for question, assignment in question_assignments:
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

        contributions.append(EfficiencyContribution(
            question_id=question.id,
            weight=assignment.weight,
            source=assignment.source,
            response_score=score,
        ))
        if score.is_dont_know:
            dk_count += 1
        if assignment.source == "explicit":
            explicit_count += 1
        else:
            section_rule_count += 1

    answered = len(contributions)

    if answered == 0:
        return EfficiencyComponentScore(
            name=component_name,
            contributions=[],
            weighted_mean_0_1=0.0,
            score_0_100=0.0,
            bracket="Critical",
            dk_ratio=0.0,
            confidence_level="low",
            expected_count=expected,
            answered_count=0,
            explicit_contribution_count=0,
            section_rule_contribution_count=0,
        )

    total_weight = sum(c.weight for c in contributions)
    if total_weight <= 0:
        weighted_mean = sum(c.response_score.value for c in contributions) / answered
    else:
        weighted_mean = (
            sum(c.weight * c.response_score.value for c in contributions)
            / total_weight
        )

    score_0_100 = weighted_mean * 100.0
    dk_ratio = dk_count / answered

    return EfficiencyComponentScore(
        name=component_name,
        contributions=contributions,
        weighted_mean_0_1=weighted_mean,
        score_0_100=score_0_100,
        bracket=bracket_for_score(score_0_100),
        dk_ratio=dk_ratio,
        confidence_level=confidence_for_dk_ratio(dk_ratio),
        expected_count=expected,
        answered_count=answered,
        explicit_contribution_count=explicit_count,
        section_rule_contribution_count=section_rule_count,
    )


# ----------------------------------------------------------------------------
# Composite + top gaps
# ----------------------------------------------------------------------------

def _compute_composite(components: list[EfficiencyComponentScore]) -> float:
    """Weighted composite per Part A §4.5: 50/50.

    If a component has zero answered contributions, it contributes 0 to
    the composite (no signal). The composite still reflects the other
    component's score, halved.
    """
    composite = 0.0
    for c in components:
        weight = COMPOSITE_WEIGHTS.get(c.name, 0.0)
        composite += c.score_0_100 * weight
    return composite


def _identify_top_gaps(
    components: list[EfficiencyComponentScore],
    n: int = 2,
) -> list[EfficiencyComponentScore]:
    """Return lowest-scoring active components, up to n.

    With only 2 components, the "top gaps" list is typically 1 or 2
    entries — the component(s) most in need of attention.
    """
    active = [c for c in components if c.answered_count > 0]
    active.sort(key=lambda c: c.score_0_100)
    return active[:n]


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------

def score_efficiency(
    questions: list[Question],
    responses_by_qid: dict[str, ResponseRecord],
    *,
    option_weight_override_map: dict[str, dict[str, float]] | None = None,
) -> EfficiencyFrameworkResult:
    """Compute the efficiency framework score.

    Parameters
    ----------
    questions
        All questions to consider — typically the full Tier 1 bank.
        Questions that match neither an explicit efficiency mapping nor
        a section rule are ignored.
    responses_by_qid
        {question_id: ResponseRecord} for the engagement.
    option_weight_override_map
        Optional per-question option-weight maps (forwarded to
        response_scoring).

    Returns
    -------
    EfficiencyFrameworkResult with composite, 2 component scores,
    confidence, and top gaps.
    """
    by_component: dict[str, list[tuple[Question, _ComponentAssignment]]] = defaultdict(list)

    for q in questions:
        for assignment in _resolve_question_to_components(q):
            by_component[assignment.component].append((q, assignment))

    component_scores: list[EfficiencyComponentScore] = []
    for component_name in EFFICIENCY_COMPONENTS:
        component_scores.append(_score_component(
            component_name,
            by_component.get(component_name, []),
            responses_by_qid,
            option_weight_override_map,
        ))

    composite = _compute_composite(component_scores)

    total_answered = sum(c.answered_count for c in component_scores)
    weighted_dk = sum(c.dk_ratio * c.answered_count for c in component_scores)
    overall_dk = weighted_dk / total_answered if total_answered else 0.0

    return EfficiencyFrameworkResult(
        framework=FRAMEWORK_NAME,
        composite_score_0_100=composite,
        composite_bracket=bracket_for_score(composite),
        overall_confidence_level=confidence_for_dk_ratio(overall_dk),
        overall_dk_ratio=overall_dk,
        components=component_scores,
        top_gaps=_identify_top_gaps(component_scores, n=2),
    )
