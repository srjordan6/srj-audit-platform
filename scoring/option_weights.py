"""
scoring.option_weights — Per-question option weight maps.

Replaces the heuristic fallback in `response_scoring.py` for questions
where the heuristic gets polarity or ordering wrong. v0.1 covers the
highest-leverage subset; questions not yet in the map fall back to the
heuristic.

CONVENTION
----------
Scores are normalized 0.0 to 1.0 where:

    0.0  = worst signal (lowest maturity / highest risk)
    1.0  = best signal (highest maturity / lowest risk)
    0.75 = canonical "Don't know" score per Part A 4.6 / OD-12 (DK penalty is 25% of a No answer's full penalty, so DK score = 1.0 - 0.25 = 0.75)

For risk_exposure dimension questions, V1's framework aggregator
INVERTS the score (high risk = low aggregate score). DO NOT pre-invert
here — write weights in their natural direction (1.0 = good behavior,
0.0 = bad behavior). The inversion happens at the framework layer.

POLARITY
--------
Each question carries a comment indicating polarity:

    REGULAR  — "Yes / first option" is the best signal (default case)
    REVERSE  — "Yes / first option" is the WORST signal (the question
               surfaces a problem; affirmative answers indicate the
               problem exists)
    MIXED    — Some affirmative answers are good, some bad (e.g.
               T1-B-023 where "Yes — value" vs "Yes — risk/compliance"
               carry different meanings)

NEUTRAL OPTIONS
---------------
Options like "N/A", "Decline to answer", or "I don't use AI tools"
score at 0.5 (neutral). These should not penalize the respondent for
not having an opinion or for the question being inapplicable.

The framework aggregators count these toward respondent completion
(per the 60% threshold rule) but contribute a neutral signal to the
sub-component average.

INTEGRATION WITH response_scoring.py
------------------------------------
`response_scoring.py` should consult this map before falling back to
heuristic. After this file lands, apply the following small patch to
response_scoring.py:

    from .option_weights import OPTION_WEIGHTS

    def _score_single_select(question, response):
        weights = OPTION_WEIGHTS.get(question.id)
        if weights is not None:
            selected = response.get("selected")
            if selected in weights:
                return weights[selected]
        return _heuristic_score_ss(question, response)

The same pattern applies to _score_yn_dontknow and _score_likert.

v0.1 SCOPE
----------
- All 28 YN/YN-extended questions (Tier 1)
- All 5 L5 questions (Tier 1)
- 3 SS frequency questions (T1-D-009, T1-D-010, T1-G-008)
- ~10 high-signal SS questions where heuristic fails

v0.2+ SCOPE (deferred)
- Remaining SS questions across all sections
- MS questions (require per-option weights + aggregation rule)
- NR questions (require per-bracket weights with question-specific
  "good range" definitions)
- RANK questions (require per-item weights for the ranked list)
"""

from __future__ import annotations


# Canonical Don't Know penalty per OD-12
DK_WEIGHT = 0.75

# Canonical neutral weight for N/A, Decline-to-answer, etc.
NEUTRAL = 0.5


# ---------------------------------------------------------------------------
# Option weight maps
# ---------------------------------------------------------------------------
# Keyed by question_id. Each entry is {option_label_string: weight_0_to_1}.
# Option strings MUST match production exactly (case-sensitive, em-dash vs
# hyphen matters). Source: SRJ MCP query on the questions table.

OPTION_WEIGHTS: dict[str, dict[str, float]] = {

    # =====================================================================
    # YN questions — Section B (Tool Inventory)
    # =====================================================================

    # REGULAR — external request for inventory is a positive accountability signal
    "T1-B-008": {
        "Yes": 1.0,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # MIXED — IC self-reporting on shadow AI; honesty is the signal, not
    # the underlying behavior (which is what the dimension scores measure)
    "T1-B-013": {
        "Yes — regularly": 0.0,    # shadow AI exists
        "Yes — occasionally": 0.25,
        "No": 1.0,
        "I'm not sure": DK_WEIGHT,
        "Decline to answer": NEUTRAL,
    },

    # MIXED — tool retirement signals discipline regardless of cause
    "T1-B-023": {
        "Yes — value": 1.0,           # discipline kicked in
        "Yes — risk/compliance": 1.0,  # discipline kicked in
        "Yes — both": 1.0,
        "No tools retired": 0.25,      # no signal of pruning discipline
        "Don't know": DK_WEIGHT,
    },

    # =====================================================================
    # YN questions — Section C (Cost Mapping)
    # =====================================================================

    # REVERSE — unidentified AI charges = bad signal (rogue spend)
    "T1-C-005": {
        "Yes — multiple times": 0.0,
        "Yes — once": 0.25,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — switching cost reviewed = good
    "T1-C-013": {
        "Yes — comprehensive": 1.0,
        "Yes — for some vendors": 0.5,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — monitored usage-based pricing is good; unmonitored is exposure
    "T1-C-014": {
        "Yes — monitored": 1.0,
        "Yes — unmonitored": 0.25,    # contracts exist but no control
        "No": 0.75,                    # no usage-based exposure at all
        "Don't know": DK_WEIGHT,
    },

    # =====================================================================
    # YN/SS questions — Section D (Performance Measurement)
    # =====================================================================

    # REVERSE — continued despite missing target = lack of discipline
    "T1-D-007": {
        "Yes": 0.0,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
        "No targets exist": 0.0,       # absence of targets is itself a gap
    },

    # REGULAR — killed for missing target = governance maturity
    "T1-D-008": {
        "Yes": 1.0,
        "No": 0.25,                    # could be no targets, could be lax
        "Don't know": DK_WEIGHT,
    },

    # SS REVERSE polarity — Daily wrong = worst signal
    "T1-D-009": {
        "Daily": 0.0,
        "Weekly": 0.2,
        "Monthly": 0.4,
        "Rarely": 0.75,
        "Never": 1.0,
        "I don't use AI tools": NEUTRAL,
    },

    # SS REGULAR polarity — Always caught = best signal
    "T1-D-010": {
        "Always": 1.0,
        "Usually": 0.75,
        "Sometimes": 0.5,
        "Rarely": 0.25,
        "Never": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REVERSE — error reached customer = bad
    "T1-D-012": {
        "Yes — multiple": 0.0,
        "Yes — once": 0.25,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # REVERSE — error disclosed to regulator = bad (underlying event dominates)
    "T1-D-013": {
        "Yes": 0.0,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # L5 — trust in AI outputs, higher = better
    "T1-D-014": {
        "1 (not at all)": 0.0,
        "2": 0.25,
        "3": 0.5,
        "4": 0.75,
        "5 (strongly trust)": 1.0,
    },

    # REGULAR — formal benchmarking = best, informal = partial
    "T1-D-015": {
        "Yes — formal": 1.0,
        "Yes — informal": 0.5,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — baseline comparison performed = good
    "T1-D-016": {
        "Yes": 1.0,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — always-required vendor data = best
    "T1-D-017": {
        "Yes — always": 1.0,
        "Sometimes": 0.5,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — both customer and employee satisfaction measured = best
    "T1-D-018": {
        "Yes — both": 1.0,
        "Customers only": 0.6,
        "Employees only": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # =====================================================================
    # YN questions — Section E (Risk Exposure)
    # NOTE: V1 framework aggregator INVERTS this dimension. Write weights
    # in their natural direction; do not pre-invert.
    # =====================================================================

    # REGULAR — vendor terms reviewed = good
    "T1-E-003": {
        "Yes — all": 1.0,
        "Some": 0.5,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REVERSE — vendor confirmed to retain/train = bad
    "T1-E-004": {
        "Yes — confirmed": 0.0,
        "Suspected": 0.25,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — notice provided = good (with N/A as neutral)
    "T1-E-005": {
        "Yes": 1.0,
        "No": 0.0,
        "N/A": NEUTRAL,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — mapping complete = good
    "T1-E-006": {
        "Yes — complete": 1.0,
        "Partial": 0.5,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — classification policy in place = good
    "T1-E-007": {
        "Yes": 1.0,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — tools constrained by classification = good
    "T1-E-008": {
        "Yes": 1.0,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REVERSE — AI content misattributed = bad
    "T1-E-012": {
        "Yes": 0.0,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # REVERSE — AI content published without disclosure = bad
    "T1-E-014": {
        "Yes — known": 0.0,
        "Suspected": 0.1,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # REVERSE — vendor security incident = bad
    "T1-E-017": {
        "Yes": 0.0,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — indemnification reviewed = good
    "T1-E-020": {
        "Yes — comprehensive": 1.0,
        "Yes — some": 0.5,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — counsel provided opinion = good
    "T1-E-022": {
        "Yes": 1.0,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # =====================================================================
    # YN questions — Section F (Governance Gaps)
    # =====================================================================

    # REGULAR — board has taken action on AI review = good
    "T1-F-006": {
        "Yes — multiple actions": 1.0,
        "Yes — at least one": 0.6,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — audits conducted = good
    "T1-F-009": {
        "Yes — external": 1.0,
        "Yes — internal": 0.7,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # =====================================================================
    # YN/SS questions — Section G (Performance, Efficiency & Outcomes)
    # =====================================================================

    # REGULAR — AI tied to outcomes in budgeting = good
    "T1-G-002": {
        "Yes": 1.0,
        "No": 0.0,
        "Partial": 0.5,
        "Don't know": DK_WEIGHT,
    },

    # REVERSE — processes worsened by AI = bad
    "T1-G-006": {
        "Yes": 0.0,
        "No": 1.0,
        "Don't know": DK_WEIGHT,
    },

    # SS REVERSE polarity — Constantly working around = worst
    "T1-G-008": {
        "Constantly": 0.0,
        "Often": 0.2,
        "Sometimes": 0.4,
        "Rarely": 0.75,
        "Never": 1.0,
        "N/A": NEUTRAL,
    },

    # L5 — confidence in AI value, higher = better
    "T1-G-009": {
        "1 (no confidence)": 0.0,
        "2": 0.25,
        "3": 0.5,
        "4": 0.75,
        "5 (high confidence)": 1.0,
    },

    # L5 — generic 1-5 confidence scales (G-010, G-011, G-012)
    "T1-G-010": {"1": 0.0, "2": 0.25, "3": 0.5, "4": 0.75, "5": 1.0},
    "T1-G-011": {"1": 0.0, "2": 0.25, "3": 0.5, "4": 0.75, "5": 1.0},
    "T1-G-012": {"1": 0.0, "2": 0.25, "3": 0.5, "4": 0.75, "5": 1.0},

    # =====================================================================
    # High-signal SS questions — Section B (Tool Inventory)
    # =====================================================================

    # REGULAR — inventory existence with maturity ramp
    "T1-B-001": {
        "Yes — comprehensive and current": 1.0,
        "Yes — partial or outdated": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — inventory recency
    "T1-B-003": {
        "Within 30 days": 1.0,
        "30-90 days ago": 0.75,
        "90 days to 6 months ago": 0.4,
        "Over 6 months ago": 0.1,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — named individual owner is best
    "T1-B-004": {
        "Named individual": 1.0,
        "Committee or team": 0.75,
        "External consultant": 0.5,
        "No clear owner": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — time-to-produce inventory under external pressure
    "T1-B-007": {
        "Same day": 1.0,
        "1-3 days": 0.75,
        "About a week": 0.5,
        "Over a week": 0.25,
        "Impossible currently": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — approval process required and followed = best
    "T1-B-024": {
        "Yes — required and consistently followed": 1.0,
        "Yes — exists but inconsistent": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # =====================================================================
    # High-signal SS questions — Section F (Governance)
    # =====================================================================

    # REGULAR — published policy with training = best
    "T1-F-001": {
        "Yes — current and trained": 1.0,
        "Yes — written but not trained": 0.5,
        "Drafted but not published": 0.25,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — formal executive accountability = best
    "T1-F-002": {
        "Yes — formally": 1.0,
        "Yes — informally": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — AI as standing exec topic
    "T1-F-003": {
        "Yes — every meeting": 1.0,
        "Most meetings": 0.75,
        "Occasionally": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — board AI reporting cadence
    "T1-F-004": {
        "Yes — regularly": 1.0,
        "Yes — once or twice": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
        "I'm not at that level": NEUTRAL,
    },

    # REGULAR — incident response readiness
    "T1-F-008": {
        "Yes — tested": 1.0,
        "Yes — written only": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — required training is best
    "T1-F-011": {
        "Yes — required": 1.0,
        "Yes — optional": 0.4,
        "No": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # =====================================================================
    # V3 frameworks additions (2026-06-28: DORA / NIS2 / EU PLD / CoE batch)
    # All 9 are REGULAR polarity SS questions with maturity ramps. E-031 /
    # E-032 / E-033 sit in the risk_exposure dimension — written in natural
    # direction; V1 aggregator inverts at the dimension layer.
    # =====================================================================

    # REGULAR — public sub-processor disclosure > on-request > stale-on-request > none
    "T1-E-031": {
        "Yes — publicly available list maintained and updated": 1.0,
        "Yes — available to customers on request, kept current": 0.7,
        "Yes — available on request, but not actively maintained": 0.35,
        "No — no customer-facing AI sub-processor disclosure": 0.0,
        "Don't know": DK_WEIGHT,
        "N/A — no customer-facing role or no AI sub-processors": NEUTRAL,
    },

    # REGULAR — standard AI rider > case-by-case > generic procurement > none
    "T1-E-032": {
        "Yes — standard AI rider/addendum applied to every new AI vendor contract": 1.0,
        "Yes — AI-specific terms negotiated case-by-case, no standard rider": 0.5,
        "Yes — generic procurement terms used, no AI-specific provisions": 0.15,
        "No — no AI-specific procurement discipline": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — designed AND tested > designed not tested > partial coverage > none
    "T1-E-033": {
        "Yes — for every fundamental-rights use case, human override capability is designed in and tested": 1.0,
        "Yes — designed in but not tested": 0.55,
        "Yes — for some fundamental-rights use cases, not all": 0.3,
        "No — fundamental-rights AI use cases exist but no human override designed": 0.0,
        "Don't know": DK_WEIGHT,
        "N/A — no fundamental-rights AI use cases": NEUTRAL,
    },

    # REGULAR — formal taxonomy with full risk-register mapping is the standard
    "T1-F-026": {
        "Yes — V1 Ch 7 taxonomy (or equivalent) adopted, with all categories mapped to risk register entries": 1.0,
        "Yes — taxonomy adopted, mapping to risk register partial": 0.65,
        "Yes — informal or draft taxonomy in use, not adopted formally": 0.3,
        "No — no AI-specific risk taxonomy": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — disciplined workpaper log > inconsistent > informal > none
    "T1-F-027": {
        "Yes — maintained per audit cycle with scope, findings, and evidence references": 1.0,
        "Yes — maintained but inconsistently populated": 0.5,
        "Yes — informal workpapers only": 0.25,
        "No — no AI internal audit log maintained": 0.0,
        "Don't know": DK_WEIGHT,
        "N/A — no internal audit function": NEUTRAL,
    },

    # REGULAR — minutes on defined cadence > occasional > informal > none
    "T1-F-028": {
        "Yes — documented minutes from regular management reviews of AI on a defined cadence": 1.0,
        "Yes — minutes captured occasionally, not at defined cadence": 0.5,
        "Yes — informal notes only": 0.25,
        "No — no documented management review of AI": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — register with verification > without verification > ad-hoc > none
    "T1-F-029": {
        "Yes — register maintained with owners, target dates, and verification of completion": 1.0,
        "Yes — register maintained but without verification step": 0.5,
        "Yes — ad-hoc tracking, no formal register": 0.25,
        "No — no AI corrective action register": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — tested communication protocol covering all stakeholders > untested > partial > none
    "T1-F-030": {
        "Yes — documented protocol covering internal stakeholders, regulators, and customers; tested at least annually": 1.0,
        "Yes — documented but not tested": 0.5,
        "Yes — ad-hoc or partial coverage": 0.25,
        "No — no AI-incident communication protocol": 0.0,
        "Don't know": DK_WEIGHT,
    },

    # REGULAR — per-use-case decision influence with explicit tier; ramp by coverage
    "T1-F-031": {
        "Yes — documented and approved for every AI use case, with decision-influence tier assigned": 1.0,
        "Yes — documented for most use cases, approval inconsistent": 0.6,
        "Yes — documented for some use cases (>=50%)": 0.4,
        "Partial — documented for a minority of use cases (<50%)": 0.2,
        "No — decision influence not documented per use case": 0.0,
        "Don't know": DK_WEIGHT,
    },
}


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_option_weight(question_id: str, option: str) -> float | None:
    """Return the weight for a specific (question, option) pair.

    Returns None if either the question or the option is not in the map.
    Callers should fall back to heuristic scoring in that case.
    """
    weights = OPTION_WEIGHTS.get(question_id)
    if weights is None:
        return None
    return weights.get(option)


def has_explicit_weights(question_id: str) -> bool:
    """Whether explicit weights exist for this question."""
    return question_id in OPTION_WEIGHTS


def coverage_summary() -> dict[str, int]:
    """Return per-section count of questions with explicit weights.

    Useful for telemetry: 'How much of the question bank is curated vs.
    heuristic?'
    """
    out: dict[str, int] = {}
    for qid in OPTION_WEIGHTS:
        # qid format: T1-A-001 → section is the second segment
        parts = qid.split("-")
        if len(parts) >= 3:
            section = parts[1]
            out[section] = out.get(section, 0) + 1
    return out


def all_curated_question_ids() -> list[str]:
    """Return every question id that has explicit weights, sorted."""
    return sorted(OPTION_WEIGHTS.keys())
