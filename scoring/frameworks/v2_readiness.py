"""
scoring.frameworks.v2_readiness — V2 readiness framework aggregator.

Implements the AI Readiness & Performance Assessment scoring engine per
Part A §4.3. Aggregates per-question response scores into 6 canonical
modules, computes the Cumulative Readiness Index (CRI), assigns
maturity levels (1-5), and identifies top gaps.

MODULES (canonical, per Part A §4.3)
------------------------------------
    workflow_readiness          Workflow integration signals  (B.1, B.5, G.1, G.2)
    data_readiness              Data exposure / classification / lineage  (E.1, E.2, E.6)
    people_readiness            Shadow AI / training / adoption  (B.2, F.2, G.2)
    leadership_accountability   Policy / governance / liability / confidence  (F.1, F.3, F.4, G.3)
    performance_measurement     Metric / quality / comparative  (all of D)
    operational_friction        Output quality / adoption friction  (D.2, G.2)

CRI = mean of the 6 module scores. No risk inversion (V2 modules are all
"higher = better readiness"). Equal weighting across modules.

DUAL-LAYER MAPPING
------------------
Each question is mapped to modules via two layers:

1. EXPLICIT — question.framework_mappings entries with framework='v2_readiness'.
   Production currently has 13 such mappings across 5 modules. Explicit
   mappings can specify a sub_component, override the default weight, and
   are authoritative when present.

2. SECTION_RULES — V2_MODULE_SECTION_RULES (declared in this module).
   Mirrors Part A §4.3 "Primarily from T1-X questions" intent by
   bucketing whole sections or subsections into modules. Used as
   fallback when no explicit mapping is present for a (question, module)
   pair. Marked provisional in contribution telemetry.

The aggregator unions both layers per question. If both layers map a
question to the same module, the explicit one wins (preserves
sub_component and weight tuning). Reports can inspect the
explicit_count / section_rule_count split per module to measure
mapping-config maturity.

MATURITY LEVELS (Part A §4.3)
-----------------------------
    0-20      Level 1   Ad hoc
    21-40     Level 2   Emerging
    41-60     Level 3   Defined
    61-80     Level 4   Managed
    81-100    Level 5   Optimizing

Same brackets as v1_audit are used internally but the user-facing label
is the maturity level (Ad hoc / Emerging / etc.) rather than the V1
Critical / Sound / Mature labels.

OVERLAPS
--------
Some subsections appear in multiple module rules (e.g., G.2 feeds
people_readiness, operational_friction, AND workflow_readiness). This
is intentional — V2 is multi-perspective re-aggregation, and a single
question can be a signal for several modules at once. CRI averaging
handles the natural double-counting; per-module scores still mean what
they say within the lens of that module.

PURE AGGREGATION, NO DB
-----------------------
Same architecture as v1_audit.py: caller passes list[Question] +
dict[str, ResponseRecord]; module computes scores. Engine.py
orchestrator (separate module) handles DB load.

CONFIDENCE (two-factor model, OD-16/OD-17)
------------------------------------------
Module-level confidence delegates to scoring.confidence.compute_confidence
exactly as v1_audit does at sub-component level: per-module counts of
non-DK responses backed by attached evidence (OD-17) or qualifying
notes (OD-16) are fed into the two-factor model. Tier 1 has no notes
or attachments per the locked capability ceiling, so both counters
stay at 0 and the result is identical to the one-factor DK-only label.

Framework-level (CRI) confidence remains on the one-factor
`confidence_for_dk_ratio` helper since the CRI aggregates module DK
ratios; per-response documentation signals are captured at the module
level and exposed on V2ModuleScore for future rollup.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from questionnaire.question_bank import Question
from scoring.confidence import ConfidenceSignal, compute_confidence
from scoring.response_scoring import ResponseScore, score_response

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Framework configuration
# ----------------------------------------------------------------------------

FRAMEWORK_NAME = "v2_readiness"

V2_MODULES: tuple[str, ...] = (
    "workflow_readiness",
    "data_readiness",
    "people_readiness",
    "leadership_accountability",
    "performance_measurement",
    "operational_friction",
)

# Section / subsection fallback rules. Mirrors Part A §4.3's "primarily
# from T1-X questions" intent. Each module entry may specify:
#   sections     — list of section codes ("B", "D", etc.); ALL questions
#                  in that section apply
#   subsections  — list of subsection codes ("B.1", "G.2", etc.); only
#                  questions with matching subsection apply
# Both can be present and are unioned.
V2_MODULE_SECTION_RULES: dict[str, dict[str, list[str]]] = {
    "workflow_readiness": {
        "subsections": ["B.1", "B.5", "G.1", "G.2"],
    },
    "data_readiness": {
        "subsections": ["E.1", "E.2", "E.6"],
    },
    "people_readiness": {
        "subsections": ["B.2", "F.2", "G.2"],
    },
    "leadership_accountability": {
        "subsections": ["F.1", "F.3", "F.4", "G.3"],
    },
    "performance_measurement": {
        "sections": ["D"],
    },
    "operational_friction": {
        "subsections": ["D.2", "G.2"],
    },
}

# Score brackets (shared with v1_audit but with maturity-level labels)
_BRACKET_THRESHOLDS: tuple[tuple[float, int, str], ...] = (
    (20.0, 1, "Ad hoc"),
    (40.0, 2, "Emerging"),
    (60.0, 3, "Defined"),
    (80.0, 4, "Managed"),
    (100.0, 5, "Optimizing"),
)

# Confidence thresholds — used at CRI / framework level
_CONFIDENCE_HIGH_MAX = 0.15
_CONFIDENCE_MEDIUM_MAX = 0.35


# ----------------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------------

ContributionSource = Literal["explicit", "section_rule"]


@dataclass(frozen=True)
class ResponseRecord:
    """One normalized response row. Identical shape to v1_audit.ResponseRecord
    so callers can pass the same dict to both aggregators.

    has_note / has_attachments are OD-16 / OD-17 signals consumed by the
    two-factor confidence model. On Tier 1 they are always False per the
    locked capability ceiling; the model degrades gracefully.
    """
    question_id: str
    answer_value: Any
    is_dont_know: bool = False
    has_note: bool = False
    has_attachments: bool = False


@dataclass(frozen=True)
class _ModuleAssignment:
    """Internal — one (question → module) mapping, before scoring."""
    module: str
    weight: float
    source: ContributionSource
    sub_component: str | None  # always None for section_rule; may be set for explicit


@dataclass(frozen=True)
class V2ModuleContribution:
    """One question's contribution to one module's score."""
    question_id: str
    weight: float
    source: ContributionSource
    sub_component: str | None
    response_score: ResponseScore


@dataclass(frozen=True)
class V2ModuleScore:
    """Aggregated score for one V2 module.

    attached_non_dk_count and noted_only_non_dk_count are the OD-16 /
    OD-17 signal counts fed into compute_confidence; they default to 0
    so callers built before the documentation-boost integration remain
    valid, and they're available for CRI-level rollup in a future pass.
    """
    name: str
    contributions: list[V2ModuleContribution]
    weighted_mean_0_1: float
    score_0_100: float
    bracket: str   # same string as maturity_label, kept for parity with V1
    maturity_level: int   # 1-5
    maturity_label: str   # Ad hoc / Emerging / ...
    dk_ratio: float
    confidence_level: str
    expected_count: int
    answered_count: int
    # Source telemetry: how much of this score came from each layer
    explicit_contribution_count: int
    section_rule_contribution_count: int
    # OD-16 / OD-17 documentation signal counts
    attached_non_dk_count: int = 0
    noted_only_non_dk_count: int = 0


@dataclass(frozen=True)
class V2FrameworkResult:
    """Full V2 readiness result."""
    framework: str
    cri_score_0_100: float   # Cumulative Readiness Index
    cri_bracket: str
    cri_maturity_level: int
    cri_maturity_label: str
    overall_confidence_level: str
    overall_dk_ratio: float
    modules: list[V2ModuleScore]
    top_gaps: list[V2ModuleScore]   # 3 lowest-scoring modules


# ----------------------------------------------------------------------------
# Bracket / maturity / confidence helpers
# ----------------------------------------------------------------------------

def maturity_for_score(score_0_100: float) -> tuple[int, str]:
    """Return (level_int_1_5, label) for a 0-100 score."""
    for threshold, level, label in _BRACKET_THRESHOLDS:
        if score_0_100 <= threshold:
            return (level, label)
    return (5, "Optimizing")


def confidence_for_dk_ratio(dk_ratio: float) -> str:
    """One-factor confidence label from a DK ratio.

    Used at CRI / framework level where only an aggregate DK ratio is
    available. Module-level confidence delegates to
    scoring.confidence.compute_confidence (two-factor with OD-16/OD-17
    documentation boost).
    """
    if dk_ratio <= _CONFIDENCE_HIGH_MAX:
        return "high"
    if dk_ratio <= _CONFIDENCE_MEDIUM_MAX:
        return "medium"
    return "low"


# ----------------------------------------------------------------------------
# Mapping resolution (dual-layer)
# ----------------------------------------------------------------------------

def _extract_explicit_mappings(question: Question) -> list[_ModuleAssignment]:
    """Pull v2_readiness mappings from question.framework_mappings."""
    out: list[_ModuleAssignment] = []
    for m in question.framework_mappings or []:
        if m.get("framework") != FRAMEWORK_NAME:
            continue
        module = m.get("module")
        if not module:
            continue
        if module not in V2_MODULES:
            logger.info(
                "v2_readiness explicit mapping on %s references unknown module %r; including anyway",
                question.id, module,
            )
        try:
            weight = float(m.get("weight", 1.0))
        except (TypeError, ValueError):
            logger.warning(
                "v2_readiness mapping on %s has non-numeric weight %r; defaulting to 1.0",
                question.id, m.get("weight"),
            )
            weight = 1.0
        out.append(_ModuleAssignment(
            module=module,
            weight=weight,
            source="explicit",
            sub_component=m.get("sub_component"),
        ))
    return out


def _section_rule_assignments(question: Question) -> list[_ModuleAssignment]:
    """Apply V2_MODULE_SECTION_RULES to one question."""
    out: list[_ModuleAssignment] = []
    for module_name, rules in V2_MODULE_SECTION_RULES.items():
        matched = False
        sections = rules.get("sections") or []
        if question.section in sections:
            matched = True
        if not matched:
            subsections = rules.get("subsections") or []
            if question.subsection and question.subsection in subsections:
                matched = True
        if matched:
            out.append(_ModuleAssignment(
                module=module_name,
                weight=1.0,
                source="section_rule",
                sub_component=None,
            ))
    return out


def _resolve_question_to_modules(question: Question) -> dict[str, _ModuleAssignment]:
    """Return {module: _ModuleAssignment} for one question.

    Explicit mappings take precedence over section-rule mappings when both
    target the same module.
    """
    by_module: dict[str, _ModuleAssignment] = {}

    # Lay down section-rule assignments first
    for a in _section_rule_assignments(question):
        by_module[a.module] = a

    # Then overlay explicit mappings (they win)
    for a in _extract_explicit_mappings(question):
        by_module[a.module] = a

    return by_module


# ----------------------------------------------------------------------------
# Module scoring
# ----------------------------------------------------------------------------

def _score_module(
    module_name: str,
    question_assignments: list[tuple[Question, _ModuleAssignment]],
    responses_by_qid: dict[str, ResponseRecord],
    option_weight_override_map: dict[str, dict[str, float]] | None,
) -> V2ModuleScore:
    """Compute one module's score from its assigned questions.

    Tracks `attached_non_dk_count` and `noted_only_non_dk_count` —
    disjoint counts of non-DK responses backed by attached evidence or
    qualifying notes — and feeds them to compute_confidence for the
    two-factor confidence label.
    """
    contributions: list[V2ModuleContribution] = []
    expected = len(question_assignments)
    dk_count = 0
    explicit_count = 0
    section_rule_count = 0
    attached_non_dk_count = 0
    noted_only_non_dk_count = 0

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

        contributions.append(V2ModuleContribution(
            question_id=question.id,
            weight=assignment.weight,
            source=assignment.source,
            sub_component=assignment.sub_component,
            response_score=score,
        ))
        if score.is_dont_know:
            dk_count += 1
        elif response.has_attachments:
            attached_non_dk_count += 1
        elif response.has_note:
            noted_only_non_dk_count += 1
        if assignment.source == "explicit":
            explicit_count += 1
        else:
            section_rule_count += 1

    answered = len(contributions)

    if answered == 0:
        # No data — return a low-confidence empty score
        return V2ModuleScore(
            name=module_name,
            contributions=[],
            weighted_mean_0_1=0.0,
            score_0_100=0.0,
            bracket="Ad hoc",
            maturity_level=1,
            maturity_label="Ad hoc",
            dk_ratio=0.0,
            confidence_level="low",
            expected_count=expected,
            answered_count=0,
            explicit_contribution_count=0,
            section_rule_contribution_count=0,
            attached_non_dk_count=0,
            noted_only_non_dk_count=0,
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
    level, label = maturity_for_score(score_0_100)
    dk_ratio = dk_count / answered

    signal = ConfidenceSignal(
        answered_count=answered,
        dk_count=dk_count,
        attached_non_dk_count=attached_non_dk_count,
        noted_only_non_dk_count=noted_only_non_dk_count,
    )

    return V2ModuleScore(
        name=module_name,
        contributions=contributions,
        weighted_mean_0_1=weighted_mean,
        score_0_100=score_0_100,
        bracket=label,
        maturity_level=level,
        maturity_label=label,
        dk_ratio=dk_ratio,
        confidence_level=compute_confidence(signal).level,
        expected_count=expected,
        answered_count=answered,
        explicit_contribution_count=explicit_count,
        section_rule_contribution_count=section_rule_count,
        attached_non_dk_count=attached_non_dk_count,
        noted_only_non_dk_count=noted_only_non_dk_count,
    )


# ----------------------------------------------------------------------------
# CRI + top gaps
# ----------------------------------------------------------------------------

def _compute_cri(modules: list[V2ModuleScore]) -> float:
    """Cumulative Readiness Index: mean of module scores, equal weighting.

    Excludes modules with zero answered contributions (no data) from the
    mean. If no module has any data, returns 0.
    """
    active = [m for m in modules if m.answered_count > 0]
    if not active:
        return 0.0
    return sum(m.score_0_100 for m in active) / len(active)


def _identify_top_gaps(
    modules: list[V2ModuleScore],
    n: int = 3,
) -> list[V2ModuleScore]:
    """Return n lowest-scoring active modules.

    Modules with no answered contributions are excluded (no diagnostic
    signal). For V2, "gap" always means low score — no inversion.
    """
    active = [m for m in modules if m.answered_count > 0]
    active.sort(key=lambda m: m.score_0_100)
    return active[:n]


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------

def score_v2_readiness(
    questions: list[Question],
    responses_by_qid: dict[str, ResponseRecord],
    *,
    option_weight_override_map: dict[str, dict[str, float]] | None = None,
) -> V2FrameworkResult:
    """Compute the V2 readiness framework score.

    Parameters
    ----------
    questions
        All questions to consider — typically the full Tier 1 bank.
        Questions matching neither an explicit v2_readiness mapping nor a
        section/subsection rule are ignored.
    responses_by_qid
        {question_id: ResponseRecord} for the engagement.
    option_weight_override_map
        Optional per-question option-weight maps (forwarded to
        response_scoring).

    Returns
    -------
    V2FrameworkResult with CRI score, 6 module scores, maturity levels,
    confidence, and top 3 gaps.
    """
    # Group questions by module (each question may belong to multiple)
    by_module: dict[str, list[tuple[Question, _ModuleAssignment]]] = defaultdict(list)

    for q in questions:
        mappings = _resolve_question_to_modules(q)
        for module_name, assignment in mappings.items():
            by_module[module_name].append((q, assignment))

    # Score each canonical module (preserves canonical order even if some
    # modules ended up empty)
    module_scores: list[V2ModuleScore] = []
    for module_name in V2_MODULES:
        assignments = by_module.get(module_name, [])
        module_scores.append(_score_module(
            module_name, assignments,
            responses_by_qid, option_weight_override_map,
        ))

    cri = _compute_cri(module_scores)
    cri_level, cri_label = maturity_for_score(cri)

    # Overall DK ratio weighted by answered_count per module
    total_answered = sum(m.answered_count for m in module_scores)
    weighted_dk = sum(m.dk_ratio * m.answered_count for m in module_scores)
    overall_dk = weighted_dk / total_answered if total_answered else 0.0

    return V2FrameworkResult(
        framework=FRAMEWORK_NAME,
        cri_score_0_100=cri,
        cri_bracket=cri_label,
        cri_maturity_level=cri_level,
        cri_maturity_label=cri_label,
        overall_confidence_level=confidence_for_dk_ratio(overall_dk),
        overall_dk_ratio=overall_dk,
        modules=module_scores,
        top_gaps=_identify_top_gaps(module_scores, n=3),
    )
