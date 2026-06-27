"""
response_scoring — Score a single response to a single question.

This module is the foundational primitive for all framework scoring
engines (v1_audit, v2_readiness, v3_governance, efficiency). Each
framework aggregates these per-response values across multiple questions
according to dimension/module/step weights documented in Part A §4.

WHAT THIS MODULE DOES
---------------------
Takes a Question dataclass and a raw answer value (as stored in the
responses.answer_value JSONB column) and returns a `ResponseScore` with
a normalized value in [0.0, 1.0] plus audit metadata.

The value is the LITERAL signal strength of the response — "how much
did the respondent select the positive end of the option set." Whether
that signal is positive or negative for a given dimension is the
responsibility of the framework aggregator, NOT this module. For
example, on a risk-exposure question ("has sensitive data been entered
into an AI tool?") a "Yes" answer scores 1.0 here, and the V1 risk
dimension scorer inverts it: dimension_score = 1 - mean(response_scores).

DECISION 7-11 (25% Don't Know rule)
-----------------------------------
By default, "Don't know" responses score 0.75 — equivalent to applying
25% of a "No" answer's penalty. This signals that uncertainty itself is
diagnostic without treating every gap as a full failure.

OD-12 OVERRIDES (F-013, F-014)
------------------------------
Some questions need to score certain answers as full No penalty rather
than the partial 25% penalty. F-013 and F-014 in particular flag this
via question.scoring_overrides[option_value_map] with explicit per-option
values. Pattern:

    scoring_overrides = {
        "option_value_map": {
            "Don't know what AI literacy is": 0.0,
        }
    }

The override is honored before the default Don't Know heuristic, so a
literal "Don't know" string with an explicit mapping in option_value_map
uses that mapping.

OPTION WEIGHT SOURCES (precedence order)
----------------------------------------
1. question.scoring_overrides["option_value_map"] — per-question explicit
2. option_weight_override kwarg — caller-supplied (option_weights.py)
3. question.scoring_overrides["_dont_know_value"] — DK-only override
4. Default heuristics — text-pattern inference (coarse; flagged in note)

The default heuristics produce sensible-looking scores from option text
alone ("Yes" → 1.0, "Yes — partial" → 0.5, "No" → 0.0, "Don't know" →
0.75). They will be replaced for each question as audit_platform/scoring/
option_weights.py is populated. The `note` field on ResponseScore tracks
which path was taken so downstream telemetry can measure heuristic
coverage.

EXCLUDED TYPES
--------------
- TEXT (H-006 only): freeform; returns excluded=True
- RANK: handled by framework-specific alignment scorers, not by this
  module; returns excluded=True with a note. The raw ranked list is
  preserved in raw_answer for those framework scorers to inspect.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from questionnaire.question_bank import Question

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Result type
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ResponseScore:
    """Normalized score plus audit metadata for one response."""

    value: float                    # [0.0, 1.0] for scored types; 0.0 for excluded
    raw_answer: Any                 # original answer for audit
    is_dont_know: bool              # respondent expressed uncertainty
    excluded: bool = False          # type not numerically scored (TEXT, RANK)
    override_applied: str | None = None  # which override path produced this score
    note: str | None = None         # debug breadcrumb (heuristic used, etc.)

    @classmethod
    def excluded_(cls, raw_answer: Any, note: str = "freeform_text") -> "ResponseScore":
        return cls(
            value=0.0,
            raw_answer=raw_answer,
            is_dont_know=False,
            excluded=True,
            note=note,
        )


# ----------------------------------------------------------------------------
# Don't-know detection
# ----------------------------------------------------------------------------

_DONT_KNOW_PATTERNS = [
    re.compile(r"^don'?t\s+know$", re.IGNORECASE),
    re.compile(r"^i'?m\s+not\s+sure$", re.IGNORECASE),
    re.compile(r"^not\s+sure$", re.IGNORECASE),
    re.compile(r"^decline\s+to\s+answer$", re.IGNORECASE),
]

DONT_KNOW_DEFAULT_VALUE = 0.75  # = 1.0 - 0.25 (25% of "No"-penalty)


def looks_like_dont_know(option_text: str) -> bool:
    if not isinstance(option_text, str):
        return False
    return any(p.match(option_text.strip()) for p in _DONT_KNOW_PATTERNS)


# ----------------------------------------------------------------------------
# Default option heuristics (coarse fallback; replaced by option_weights.py)
# ----------------------------------------------------------------------------

_YES_FULL_PATTERNS = [
    re.compile(r"^yes\s*[—-]\s*(comprehensive|robust|fully|formal|current|all|complete)", re.I),
    re.compile(r"^yes$", re.I),
    re.compile(r"^always$", re.I),
    re.compile(r"^very\s+confident$", re.I),
    re.compile(r"^fully\s+(approved|comprehensive|tied)", re.I),
    re.compile(r"^required\s+and\s+(consistently\s+)?followed", re.I),
    re.compile(r"^tested\b", re.I),
]

_YES_PARTIAL_PATTERNS = [
    re.compile(r"^yes\s*[—-]\s*(partial|informal|outdated|some|once|drafted)", re.I),
    re.compile(r"^partial(ly)?$", re.I),
    re.compile(r"^somewhat", re.I),
    re.compile(r"^mostly", re.I),
    re.compile(r"^suspected$", re.I),
    re.compile(r"^written\s+only", re.I),
    re.compile(r"^loosely\s+tied", re.I),
    re.compile(r"^exists\s+on\s+paper", re.I),
]

_NO_PATTERNS = [
    re.compile(r"^no$", re.I),
    re.compile(r"^no\s*[—-]", re.I),
    re.compile(r"^never$", re.I),
    re.compile(r"^none(\s+of\s+these)?$", re.I),
    re.compile(r"^not\s+at\s+all$", re.I),
    re.compile(r"^no\s+confidence$", re.I),
]


def heuristic_option_value(option: str) -> tuple[float, str]:
    """Return (score in [0,1], heuristic_label) for a single option string."""
    if not isinstance(option, str):
        return (0.5, "fallback_non_string")
    o = option.strip()
    if looks_like_dont_know(o):
        return (DONT_KNOW_DEFAULT_VALUE, "heuristic_dont_know")
    for p in _YES_FULL_PATTERNS:
        if p.search(o):
            return (1.0, "heuristic_yes_full")
    for p in _YES_PARTIAL_PATTERNS:
        if p.search(o):
            return (0.5, "heuristic_yes_partial")
    for p in _NO_PATTERNS:
        if p.search(o):
            return (0.0, "heuristic_no")
    return (0.5, "heuristic_fallback_neutral")


# ----------------------------------------------------------------------------
# Option resolution (precedence-ordered)
# ----------------------------------------------------------------------------

def _resolve_option_value(
    question: Question,
    option_text: str,
    option_weight_override: dict[str, float] | None,
) -> tuple[float, str]:
    """Resolve a single option's score, honoring overrides in precedence order.

    Returns (value, source_label). source_label is one of:
        'override_explicit'      — question.scoring_overrides.option_value_map
        'override_external'      — caller-supplied option_weight_override map
        'override_dont_know'     — question.scoring_overrides._dont_know_value
        'heuristic_*'            — fallback heuristics (coarse)
    """
    overrides = question.scoring_overrides or {}

    # 1. Per-question explicit option map
    option_value_map = overrides.get("option_value_map") or {}
    if option_text in option_value_map:
        return (float(option_value_map[option_text]), "override_explicit")

    # 2. Caller-supplied option_weights.py override
    if option_weight_override and option_text in option_weight_override:
        return (float(option_weight_override[option_text]), "override_external")

    # 3. Question-level Don't Know override
    if looks_like_dont_know(option_text):
        if "_dont_know_value" in overrides:
            return (float(overrides["_dont_know_value"]), "override_dont_know")
        return (DONT_KNOW_DEFAULT_VALUE, "heuristic_dont_know")

    # 4. Generic heuristic
    return heuristic_option_value(option_text)


# ----------------------------------------------------------------------------
# Per-question-type scorers
# ----------------------------------------------------------------------------

def _score_text(question, answer, **kwargs) -> ResponseScore:
    """TEXT (H-006): freeform — excluded from numeric scoring."""
    return ResponseScore.excluded_(answer)


def _score_rank(question, answer, **kwargs) -> ResponseScore:
    """RANK: framework aggregators handle ranked-list alignment scoring.

    This module excludes RANK from a single normalized value because
    "T1-G-001 has cost-reduction ranked #2" doesn't carry a defensible
    universal score. The raw ranked list is preserved in raw_answer for
    framework-specific use.
    """
    return ResponseScore.excluded_(answer, note="rank_excluded_from_numeric")


def _score_l5(question, answer, **kwargs) -> ResponseScore:
    """Likert 1-5: linearly map to [0, 1] (value 1 → 0.0, value 5 → 1.0)."""
    try:
        if isinstance(answer, dict):
            val = int(answer.get("value") or answer.get("selected"))
        else:
            val = int(answer)
    except (ValueError, TypeError):
        logger.warning("L5 question %s got non-numeric answer: %r", question.id, answer)
        return ResponseScore(
            value=0.5, raw_answer=answer, is_dont_know=False,
            note="invalid_l5_value",
        )
    val = max(1, min(5, val))
    return ResponseScore(
        value=(val - 1) / 4.0,
        raw_answer=answer,
        is_dont_know=False,
        note=f"l5_value_{val}",
    )


def _extract_single_selection(answer: Any) -> str | None:
    """Pull a single selected option string out of various answer shapes."""
    if isinstance(answer, dict):
        return answer.get("selected") or answer.get("value")
    if isinstance(answer, str):
        return answer
    return None


def _score_ss_or_yn(
    question: Question,
    answer: Any,
    *,
    option_weight_override: dict[str, float] | None = None,
    **kwargs,
) -> ResponseScore:
    """Score a single-select or yes/no/DK question."""
    selected = _extract_single_selection(answer)
    if not isinstance(selected, str):
        logger.warning("SS/YN question %s got non-string answer: %r", question.id, answer)
        return ResponseScore(
            value=0.5, raw_answer=answer, is_dont_know=False,
            note="invalid_selection",
        )

    value, source = _resolve_option_value(question, selected, option_weight_override)
    is_dk = looks_like_dont_know(selected)
    override = source if source.startswith("override_") else None

    return ResponseScore(
        value=value,
        raw_answer=answer,
        is_dont_know=is_dk,
        override_applied=override,
        note=source if override is None else None,
    )


def _score_ms(
    question: Question,
    answer: Any,
    *,
    option_weight_override: dict[str, float] | None = None,
    **kwargs,
) -> ResponseScore:
    """Score a multi-select. Default aggregation: mean of selected option weights.

    Per-question scoring_overrides may switch aggregation via
    scoring_overrides["ms_aggregation"] ∈ {"mean", "max", "sum_capped"}.
    """
    if isinstance(answer, dict):
        selected = answer.get("selected") or answer.get("values") or []
    elif isinstance(answer, list):
        selected = answer
    else:
        selected = []

    if not selected:
        # Empty selection on an MS question is itself a signal — typically
        # "respondent skipped" or "none apply." Treat as 0.0.
        return ResponseScore(
            value=0.0, raw_answer=answer, is_dont_know=False, note="ms_empty",
        )

    values: list[float] = []
    overrides_seen: list[str] = []
    has_dk = False

    for option in selected:
        if not isinstance(option, str):
            continue
        v, source = _resolve_option_value(question, option, option_weight_override)
        values.append(v)
        if looks_like_dont_know(option):
            has_dk = True
        if source.startswith("override_"):
            overrides_seen.append(source)

    if not values:
        return ResponseScore(
            value=0.5, raw_answer=answer, is_dont_know=False,
            note="ms_no_resolved_options",
        )

    overrides = question.scoring_overrides or {}
    agg = overrides.get("ms_aggregation", "mean")
    if agg == "max":
        score = max(values)
    elif agg == "sum_capped":
        score = min(1.0, sum(values))
    else:
        score = sum(values) / len(values)

    return ResponseScore(
        value=score,
        raw_answer=answer,
        is_dont_know=has_dk and len(selected) == 1,
        override_applied=";".join(overrides_seen) or None,
        note=f"ms_{agg}_of_{len(values)}",
    )


def _score_nr(
    question: Question,
    answer: Any,
    *,
    option_weight_override: dict[str, float] | None = None,
    **kwargs,
) -> ResponseScore:
    """Score a numeric-range bracket. Default: ordinal position in options list.

    Treats brackets as ordered low→high in their option list. Lowest bracket
    scores 0.0, highest scores 1.0, with linear spacing in between (after
    excluding Don't Know-style options from the denominator).

    Whether higher = better is the framework aggregator's responsibility.
    """
    if isinstance(answer, dict):
        selected = (
            answer.get("bracket")
            or answer.get("selected")
            or answer.get("value")
        )
    else:
        selected = answer

    if not isinstance(selected, str):
        return ResponseScore(
            value=0.5, raw_answer=answer, is_dont_know=False,
            note="nr_invalid_bracket",
        )

    if looks_like_dont_know(selected):
        overrides = question.scoring_overrides or {}
        dk_value = float(overrides.get("_dont_know_value", DONT_KNOW_DEFAULT_VALUE))
        return ResponseScore(
            value=dk_value, raw_answer=answer, is_dont_know=True,
            note="nr_dont_know",
        )

    # Explicit override path
    overrides = question.scoring_overrides or {}
    option_value_map = overrides.get("option_value_map") or {}
    if selected in option_value_map:
        return ResponseScore(
            value=float(option_value_map[selected]),
            raw_answer=answer, is_dont_know=False,
            override_applied="override_explicit",
        )
    if option_weight_override and selected in option_weight_override:
        return ResponseScore(
            value=float(option_weight_override[selected]),
            raw_answer=answer, is_dont_know=False,
            override_applied="override_external",
        )

    # Ordinal default
    if question.options and selected in question.options:
        scored_opts = [o for o in question.options if not looks_like_dont_know(o)]
        if selected in scored_opts:
            n = len(scored_opts)
            if n <= 1:
                return ResponseScore(
                    value=0.5, raw_answer=answer, is_dont_know=False,
                    note="nr_single_option",
                )
            idx = scored_opts.index(selected)
            return ResponseScore(
                value=idx / (n - 1),
                raw_answer=answer, is_dont_know=False,
                note=f"nr_ordinal_{idx}_of_{n - 1}",
            )

    return ResponseScore(
        value=0.5, raw_answer=answer, is_dont_know=False,
        note="nr_fallback",
    )


def _score_matrix(
    question: Question,
    answer: Any,
    *,
    option_weight_override: dict[str, float] | None = None,
    **kwargs,
) -> ResponseScore:
    """Score a matrix question.

    Two patterns are recognized via question.extended_metadata["matrix_pattern"]:

      "yes_no_dontknow_grid"           — rows × cols of YN/DK answers.
                                         Default for B-017 / D-001 shape.
                                         Score = mean of all cell values.

      "single_selection_per_row"       — F-002 only. Each row has one selected
                                         option; per-row option maps live in
                                         question.scoring_overrides[row_option_maps].
    """
    if not isinstance(answer, dict):
        return ResponseScore(
            value=0.5, raw_answer=answer, is_dont_know=False,
            note="matrix_invalid_shape",
        )

    rows_data = answer.get("rows") or {}
    if not rows_data:
        return ResponseScore(
            value=0.0, raw_answer=answer, is_dont_know=False, note="matrix_no_rows",
        )

    extended = question.extended_metadata or {}
    pattern = extended.get("matrix_pattern", "yes_no_dontknow_grid")
    overrides = question.scoring_overrides or {}

    cell_values: list[float] = []
    dk_count = 0
    total_cells = 0

    if pattern == "yes_no_dontknow_grid":
        for row_name, row_cells in rows_data.items():
            if not isinstance(row_cells, dict):
                continue
            for col_name, cell_val in row_cells.items():
                total_cells += 1
                if isinstance(cell_val, str):
                    v, _ = heuristic_option_value(cell_val)
                    cell_values.append(v)
                    if looks_like_dont_know(cell_val):
                        dk_count += 1

    elif pattern == "single_selection_per_row":
        row_maps = overrides.get("row_option_maps", {})
        for row_name, selected in rows_data.items():
            total_cells += 1
            if not isinstance(selected, str):
                continue
            row_map = row_maps.get(row_name) or {}
            if selected in row_map:
                cell_values.append(float(row_map[selected]))
            else:
                v, _ = heuristic_option_value(selected)
                cell_values.append(v)
            if looks_like_dont_know(selected):
                dk_count += 1

    else:
        logger.warning(
            "Question %s has unknown matrix_pattern %r", question.id, pattern,
        )

    if not cell_values:
        return ResponseScore(
            value=0.0, raw_answer=answer, is_dont_know=False,
            note=f"matrix_{pattern}_no_cells",
        )

    mean = sum(cell_values) / len(cell_values)
    dk_ratio = dk_count / total_cells if total_cells else 0
    return ResponseScore(
        value=mean,
        raw_answer=answer,
        is_dont_know=dk_ratio >= 0.5,
        note=f"matrix_{pattern}_{len(cell_values)}_cells_dk_{dk_ratio:.0%}",
    )


# ----------------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------------

SCORERS = {
    "SS": _score_ss_or_yn,
    "YN": _score_ss_or_yn,   # YN is structurally a 2-3 option SS
    "MS": _score_ms,
    "NR": _score_nr,
    "L5": _score_l5,
    "RANK": _score_rank,
    "MATRIX": _score_matrix,
    "TEXT": _score_text,
}


def score_response(
    question: Question,
    answer_value: Any,
    *,
    option_weight_override: dict[str, float] | None = None,
) -> ResponseScore:
    """Score one response against one question.

    Returns a ResponseScore with value in [0.0, 1.0] for scored types,
    or excluded=True for TEXT and RANK.

    Honors question.scoring_overrides (e.g. OD-12 literacy overrides on
    F-013 / F-014) and an optional caller-supplied option_weight_override
    map (intended for the per-question maps in option_weights.py).

    Falls back to text-pattern heuristics when no explicit option weights
    are configured. The `note` field on the returned ResponseScore
    records which path produced the value, so coverage of heuristic-vs-
    tuned scoring can be measured at the engagement level.
    """
    scorer = SCORERS.get(question.question_type)
    if scorer is None:
        logger.warning(
            "No scorer registered for question_type %r on %s",
            question.question_type, question.id,
        )
        return ResponseScore(
            value=0.5, raw_answer=answer_value, is_dont_know=False,
            note=f"unknown_type_{question.question_type}",
        )
    return scorer(question, answer_value, option_weight_override=option_weight_override)
