"""
scoring.confidence — documentation-boosted confidence calculation (OD-16/OD-17).

This module owns the confidence-level decision for the four framework
aggregators (v1_audit, v2_readiness, v3_governance, efficiency). It
supersedes the inline `confidence_for_dk_ratio` helper currently
duplicated across those files.

WHAT'S NEW vs. THE v0.1 MODEL
-----------------------------
The v0.1 confidence model in each framework uses a single signal: the
Don't Know ratio. Sub-components dominated by "Don't know" responses
are flagged low confidence; those with few DKs are flagged high.

OD-16 (response notes) and OD-17 (response attachments) capture
additional respondent behavior: when a respondent attaches an evidence
document or writes a qualifying note on a substantive (non-DK)
response, that's a structural signal the answer is grounded.

The two-factor model accounts for both:

    effective_dk_ratio = max(0, raw_dk_ratio − documentation_boost)

where `documentation_boost` is weighted by the share of NON-DK
responses backed by notes or attachments. DK responses get no
documentation credit even if they have attachments — by construction:
the inputs `attached_non_dk_count` and `noted_only_non_dk_count` only
count overlap with non-DK responses. This prevents gaming (a
respondent can't dodge a low-confidence signal by attaching irrelevant
files to "Don't know") and matches the data the aggregator has
available row-by-row anyway.

CONFIDENCE THRESHOLDS (PRESERVED FROM v1_audit.py)
--------------------------------------------------
    effective_dk ≤ 0.15  → high
    effective_dk ≤ 0.35  → medium
    otherwise            → low

BOOST WEIGHTS (TUNABLE)
-----------------------
    ATTACHMENT_BOOST_FACTOR = 0.20
    NOTE_BOOST_FACTOR       = 0.05

Attachments are 4× stronger than notes. An attachment is documentary
evidence (vendor contract, policy text, audit workpaper); a note is
the respondent's qualification of an answer. Both are positive
signals; attachments are more verifiable.

WHY THESE NUMBERS
-----------------
At realistic data densities the boost has surgical effect:

    Scenario                                          raw_dk  boost  effective  level
    0 DK, 5 of 10 non-DK answers attached             0.00    0.10   0.00       high
    3 DK, 5 of 7 non-DK answers attached              0.30    0.10   0.20       medium
    3 DK, all 7 non-DK answers attached               0.30    0.14   0.16       medium
    1 DK, all 9 non-DK answers attached               0.10    0.18   0.00       high
    5 DK, all 5 non-DK answers attached               0.50    0.10   0.40       low

In particular, 30%+ DK responses remain medium even with full
attachment coverage on the substantive responses — high DK is a
structural signal that documentation can't paper over. This is
intentional.

API
---
- `ConfidenceSignal` is the input dataclass: counts of answered
  responses, dont-know responses, and the disjoint subsets of non-DK
  responses with attachments / notes-only.
- `compute_confidence(signal) -> ConfidenceResult` is the main entry
  point. ConfidenceResult includes the raw and effective DK ratios,
  the documentation boost magnitude, the resulting level, and a
  human-readable rationale string for report templates.
- `confidence_for_dk_ratio(dk_ratio) -> str` is the backward-compatible
  one-factor helper for callers not yet wired into the two-factor model.

INTEGRATION PATH
----------------
Each framework aggregator (v1_audit.py, v2_readiness.py,
v3_governance.py, efficiency.py) currently calls a local
`confidence_for_dk_ratio(dk_ratio)`. The integration pass should:

1. In `_score_sub_component`, track these counters alongside dk_count:
       attached_non_dk = sum(1 for r in records
                             if not r.is_dont_know and r.has_attachments)
       noted_only_non_dk = sum(1 for r in records
                               if not r.is_dont_know
                               and r.has_note
                               and not r.has_attachments)
2. Build a `ConfidenceSignal` from those counts.
3. Replace `confidence_for_dk_ratio(dk_ratio)` with
   `compute_confidence(signal).level`.
4. Optionally surface `compute_confidence(signal).rationale` to the
   report context so the report can say "high confidence — supported
   by attached evidence on 4 of 5 substantive responses" instead of
   just "high".

The integration is a separate PR per the SRJ commit discipline. This
module ships standalone and exercises pure functions only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Tunable constants
# ----------------------------------------------------------------------------

# Weight applied to the share of non-DK responses backed by attachments.
# Attachments are evidence; treat them as the strongest positive signal.
ATTACHMENT_BOOST_FACTOR: float = 0.20

# Weight applied to the share of non-DK responses with notes but no
# attachment. A note qualifies the answer but is not documentary
# evidence; weight it well below attachments.
NOTE_BOOST_FACTOR: float = 0.05

# Confidence-level thresholds applied to the effective DK ratio.
# Preserved exactly from the v0.1 inline definition in v1_audit.py.
HIGH_CONFIDENCE_MAX_DK: float = 0.15
MEDIUM_CONFIDENCE_MAX_DK: float = 0.35


# ----------------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfidenceSignal:
    """Input counts for a single sub-component's confidence calculation.

    Attributes
    ----------
    answered_count
        Number of responses that contributed to the sub-component score
        (i.e. were not excluded by question type or skip logic).
    dk_count
        Number of those responses that were "Don't know."
    attached_non_dk_count
        Number of NON-DK responses with at least one attachment.
        Counted regardless of whether the response also has a note.
    noted_only_non_dk_count
        Number of NON-DK responses with a note but NO attachment.
        Disjoint from `attached_non_dk_count` — a response with both
        a note and an attachment is counted in `attached_non_dk_count`
        only (no double-counting).

    Invariants enforced in __post_init__:
        attached_non_dk_count + noted_only_non_dk_count ≤ non_dk_count
    """
    answered_count: int
    dk_count: int
    attached_non_dk_count: int
    noted_only_non_dk_count: int

    def __post_init__(self) -> None:
        if self.answered_count < 0:
            raise ValueError(f"answered_count must be ≥ 0, got {self.answered_count}")
        if self.dk_count < 0 or self.dk_count > self.answered_count:
            raise ValueError(
                f"dk_count must be in [0, {self.answered_count}], got {self.dk_count}"
            )
        non_dk = self.answered_count - self.dk_count
        if self.attached_non_dk_count < 0 or self.attached_non_dk_count > non_dk:
            raise ValueError(
                f"attached_non_dk_count must be in [0, {non_dk}], "
                f"got {self.attached_non_dk_count}"
            )
        if self.noted_only_non_dk_count < 0 or self.noted_only_non_dk_count > non_dk:
            raise ValueError(
                f"noted_only_non_dk_count must be in [0, {non_dk}], "
                f"got {self.noted_only_non_dk_count}"
            )
        if self.attached_non_dk_count + self.noted_only_non_dk_count > non_dk:
            raise ValueError(
                f"attached_non_dk_count + noted_only_non_dk_count "
                f"({self.attached_non_dk_count + self.noted_only_non_dk_count}) "
                f"must not exceed non-DK count ({non_dk})"
            )

    @property
    def dk_ratio(self) -> float:
        """Fraction of answered responses that were Don't Know."""
        if self.answered_count == 0:
            return 0.0
        return self.dk_count / self.answered_count

    @property
    def non_dk_count(self) -> int:
        """Count of substantive (non-DK) responses."""
        return self.answered_count - self.dk_count


@dataclass(frozen=True)
class ConfidenceResult:
    """Output of the two-factor confidence calculation."""
    raw_dk_ratio: float           # before any boost
    documentation_boost: float    # subtracted from raw_dk_ratio
    effective_dk_ratio: float     # max(0, raw - boost)
    level: str                    # "high" / "medium" / "low"
    rationale: str                # human-readable explanation for reports


# ----------------------------------------------------------------------------
# Public functions
# ----------------------------------------------------------------------------

def confidence_for_dk_ratio(dk_ratio: float) -> str:
    """Map a DK ratio (0.0–1.0) to a confidence label.

    This is the backward-compatible one-factor helper. Callers that
    haven't yet wired in the two-factor model can use this directly.
    Behavior matches the inline definition currently in v1_audit.py.

    >>> confidence_for_dk_ratio(0.0)
    'high'
    >>> confidence_for_dk_ratio(0.15)
    'high'
    >>> confidence_for_dk_ratio(0.16)
    'medium'
    >>> confidence_for_dk_ratio(0.35)
    'medium'
    >>> confidence_for_dk_ratio(0.36)
    'low'
    >>> confidence_for_dk_ratio(1.0)
    'low'
    """
    if dk_ratio <= HIGH_CONFIDENCE_MAX_DK:
        return "high"
    if dk_ratio <= MEDIUM_CONFIDENCE_MAX_DK:
        return "medium"
    return "low"


def compute_confidence(signal: ConfidenceSignal) -> ConfidenceResult:
    """Compute the two-factor confidence for a sub-component.

    Combines the Don't Know ratio (negative signal) with the
    documentation share (positive signal) into an effective DK ratio,
    then applies the same threshold table as the one-factor model.

    Positional order: (answered_count, dk_count, attached_non_dk_count,
    noted_only_non_dk_count).

    Examples
    --------
    Zero responses → low confidence with no signal:

    >>> r = compute_confidence(ConfidenceSignal(0, 0, 0, 0))
    >>> r.level
    'low'
    >>> r.rationale
    'No responses contributed to this sub-component.'

    All answered, no DK, no documentation → clean high:

    >>> r = compute_confidence(ConfidenceSignal(10, 0, 0, 0))
    >>> (r.raw_dk_ratio, r.documentation_boost, r.level)
    (0.0, 0.0, 'high')

    Half DK, no documentation → low:

    >>> compute_confidence(ConfidenceSignal(10, 5, 0, 0)).level
    'low'

    Half DK, full attachment coverage on the answered half → still low
    (attachments don't rescue 50% DK):

    >>> r = compute_confidence(ConfidenceSignal(10, 5, 5, 0))
    >>> round(r.documentation_boost, 4)
    0.1
    >>> round(r.effective_dk_ratio, 4)
    0.4
    >>> r.level
    'low'

    30% DK, attachments on every non-DK response → medium:

    >>> r = compute_confidence(ConfidenceSignal(10, 3, 7, 0))
    >>> round(r.documentation_boost, 4)
    0.14
    >>> round(r.effective_dk_ratio, 4)
    0.16
    >>> r.level
    'medium'

    10% DK, attachments on every non-DK response → high (boost saves it):

    >>> r = compute_confidence(ConfidenceSignal(10, 1, 9, 0))
    >>> round(r.documentation_boost, 4)
    0.18
    >>> round(r.effective_dk_ratio, 4)
    0.0
    >>> r.level
    'high'

    All DK — by construction, attached_non_dk_count and
    noted_only_non_dk_count must both be 0; no boost is possible:

    >>> r = compute_confidence(ConfidenceSignal(10, 10, 0, 0))
    >>> r.documentation_boost
    0.0
    >>> r.level
    'low'

    Notes count too, but at 1/4 the weight of attachments:

    >>> r = compute_confidence(ConfidenceSignal(10, 0, 0, 10))
    >>> round(r.documentation_boost, 4)
    0.05
    >>> r.level
    'high'

    Validation rejects impossible overlap (attached count > non-DK count):

    >>> ConfidenceSignal(10, 8, 5, 0)
    Traceback (most recent call last):
        ...
    ValueError: attached_non_dk_count must be in [0, 2], got 5
    """
    if signal.answered_count == 0:
        return ConfidenceResult(
            raw_dk_ratio=0.0,
            documentation_boost=0.0,
            effective_dk_ratio=0.0,
            level="low",
            rationale="No responses contributed to this sub-component.",
        )

    raw_dk = signal.dk_ratio
    boost = _documentation_boost(signal)
    effective = max(0.0, raw_dk - boost)
    level = confidence_for_dk_ratio(effective)
    rationale = _build_rationale(signal, raw_dk, boost, effective, level)

    return ConfidenceResult(
        raw_dk_ratio=raw_dk,
        documentation_boost=boost,
        effective_dk_ratio=effective,
        level=level,
        rationale=rationale,
    )


# ----------------------------------------------------------------------------
# Private helpers
# ----------------------------------------------------------------------------

def _documentation_boost(signal: ConfidenceSignal) -> float:
    """Compute the documentation boost from documented non-DK responses.

    Direct calculation — the caller has already counted the exact
    non-DK overlap in `attached_non_dk_count` and
    `noted_only_non_dk_count`. The two counts are disjoint by
    construction (no double-counting).
    """
    if signal.answered_count == 0:
        return 0.0
    return (
        ATTACHMENT_BOOST_FACTOR * signal.attached_non_dk_count / signal.answered_count
        + NOTE_BOOST_FACTOR * signal.noted_only_non_dk_count / signal.answered_count
    )


def _build_rationale(
    signal: ConfidenceSignal,
    raw_dk: float,
    boost: float,
    effective: float,
    level: str,
) -> str:
    """Build a human-readable rationale for the report.

    Returns one sentence describing the dominant signal driving the
    confidence label. Used by report templates to say "high confidence
    — supported by attached evidence on 4 of 5 responses" instead of
    just "high".
    """
    n = signal.answered_count
    dk = signal.dk_count
    att = signal.attached_non_dk_count
    noted = signal.noted_only_non_dk_count

    if level == "high" and boost > 0.01:
        if att > 0:
            return (
                f"High confidence — supported by attached evidence on "
                f"{att} of {n} response{'s' if n != 1 else ''}."
            )
        return (
            f"High confidence — respondent notes on {noted} of {n} "
            f"response{'s' if n != 1 else ''}."
        )
    if level == "high":
        return f"High confidence — minimal uncertainty in {n} response{'s' if n != 1 else ''}."
    if level == "medium" and dk > 0:
        if boost > 0.01:
            return (
                f"Medium confidence — {dk} of {n} responses were 'Don't know,' "
                f"partially offset by documentation on substantive responses."
            )
        return f"Medium confidence — {dk} of {n} responses were 'Don't know.'"
    if level == "medium":
        return f"Medium confidence based on {n} response{'s' if n != 1 else ''}."
    if level == "low" and dk > 0:
        return (
            f"Low confidence — {dk} of {n} responses were 'Don't know'; "
            f"the gap exceeds what documentation can offset."
        )
    return f"Low confidence — limited signal in {n} response{'s' if n != 1 else ''}."
