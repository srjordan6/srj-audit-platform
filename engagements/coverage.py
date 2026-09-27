"""Tier 2 coverage check (Part B-1 S.3, Part A S.1.2).

An engagement may generate a multi-respondent report only when it has
enough respondents, in the right role mix, who have each done enough of
the questionnaire to count. This module is the single place those rules
live; the buyer dashboard, the completion trigger and the "Generate
report" action all call check_coverage() and act on the same answer.

Locked rules
  * A respondent counts toward coverage only if completion_percentage
    >= 0.60 (B-1 S.3.2 DECISION LOCKED) AND they have signed the
    attestation (B-1 S.1.3 coverage check).
  * Minimum respondent count and required role mix come from the
    company's size bracket (Part A S.1.2 table).
  * Tier 1 is single-respondent by definition and is always "met".

Where Part A S.1.2 names a role family rather than a count ("functional
VPs", "ops lead", "IT lead"), the counts below are the build's reading of
it and are marked in REQUIREMENTS. Adjusting them is a data change, not a
code change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MIN_COMPLETION = 0.60

# Role vocabulary is the question bank's role_visibility vocabulary.
LEADERSHIP = {"BOARD", "CEO", "CFO", "CIO", "CISO", "COO"}
WORKFORCE = {"VP", "DIR", "MGR", "IC", "HR"}
ALL_ROLES = LEADERSHIP | WORKFORCE

OPS_LEAD = {"COO", "VP", "DIR", "MGR"}
IT_LEAD = {"CIO", "CISO"}

# (label, roles that satisfy the slot, how many are required)
REQUIREMENTS: dict[str, dict[str, Any]] = {
    "1-25": {
        "minimum": 3,
        "roles": [("CEO", {"CEO"}, 1), ("ops lead", OPS_LEAD, 1), ("employee", {"IC"}, 1)],
    },
    "26-100": {
        "minimum": 5,
        "roles": [("CEO", {"CEO"}, 1), ("CFO / finance", {"CFO"}, 1),
                  ("IT lead", IT_LEAD, 1), ("ops lead", {"COO", "VP", "DIR"}, 1),
                  ("line manager", {"MGR"}, 1)],
    },
    "101-500": {
        "minimum": 8,
        "roles": [("CEO", {"CEO"}, 1), ("CFO", {"CFO"}, 1), ("CIO / CISO", IT_LEAD, 1),
                  ("COO", {"COO"}, 1), ("HR", {"HR"}, 1), ("director", {"DIR"}, 2),
                  ("employee", {"IC"}, 2)],
    },
    "501-2000": {
        "minimum": 15,
        # "functional VPs" read as 2 (build choice)
        "roles": [("CEO", {"CEO"}, 1), ("CFO", {"CFO"}, 1), ("CIO / CISO", IT_LEAD, 1),
                  ("COO", {"COO"}, 1), ("HR", {"HR"}, 1), ("VP", {"VP"}, 2),
                  ("line manager", {"MGR"}, 3), ("employee", {"IC"}, 5)],
    },
    "2001-5000": {
        "minimum": 20,
        # "VPs" read as 3 (build choice)
        "roles": [("CEO", {"CEO"}, 1), ("CFO", {"CFO"}, 1), ("CIO / CISO", IT_LEAD, 1),
                  ("COO", {"COO"}, 1), ("HR", {"HR"}, 1), ("VP", {"VP"}, 3),
                  ("director", {"DIR"}, 5), ("line manager", {"MGR"}, 7),
                  ("employee", {"IC"}, 3)],
    },
    "5000+": {
        "minimum": 25,
        "roles": [("CEO", {"CEO"}, 1), ("CFO", {"CFO"}, 1), ("CIO / CISO", IT_LEAD, 1),
                  ("COO", {"COO"}, 1), ("HR", {"HR"}, 1), ("VP", {"VP"}, 3),
                  ("director", {"DIR"}, 5), ("line manager", {"MGR"}, 7),
                  ("employee", {"IC"}, 8)],
    },
}


@dataclass(frozen=True)
class RespondentSummary:
    id: str
    role: str
    completion: float          # 0..1
    attested: bool
    status: str                # invited / in_progress / completed / removed

    @property
    def counts(self) -> bool:
        return (self.status != "removed"
                and self.completion >= MIN_COMPLETION
                and self.attested)


@dataclass
class CoverageReport:
    is_met: bool
    tier: str
    size_bracket: str | None
    minimum: int
    counted: int
    invited: int
    missing_items: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def evaluate(tier: str, size_bracket: str | None,
             respondents: list[RespondentSummary]) -> CoverageReport:
    """Pure function: the whole rule set, no database. Tested directly."""
    active = [r for r in respondents if r.status != "removed"]
    counted = [r for r in active if r.counts]

    if tier == "tier_1":
        return CoverageReport(
            is_met=len(counted) >= 1, tier=tier, size_bracket=size_bracket,
            minimum=1, counted=len(counted), invited=len(active),
            missing_items=[] if counted else ["the respondent has not completed the questionnaire"],
            details={"rule": "tier_1 is single-respondent"},
        )

    req = REQUIREMENTS.get(size_bracket or "")
    if req is None:
        return CoverageReport(
            is_met=False, tier=tier, size_bracket=size_bracket, minimum=0,
            counted=len(counted), invited=len(active),
            missing_items=["company size bracket is not set; it decides the required respondents"],
        )

    missing: list[str] = []
    if len(counted) < req["minimum"]:
        missing.append(
            f"{req['minimum'] - len(counted)} more completed respondent(s) "
            f"({len(counted)} of {req['minimum']} minimum)")

    # Role mix: each counted respondent can satisfy exactly one slot.
    # Fill the narrowest slots first so a CIO isn't spent on "ops lead"
    # when "IT lead" also needs them.
    pool = {r.id: r.role for r in counted}
    slots = sorted(req["roles"], key=lambda s: len(s[1]))
    role_gaps: dict[str, int] = {}
    for label, allowed, need in slots:
        have = 0
        for rid, role in list(pool.items()):
            if have >= need:
                break
            if role in allowed:
                have += 1
                del pool[rid]
        if have < need:
            role_gaps[label] = need - have
    for label, gap in role_gaps.items():
        missing.append(f"{gap} more {label} respondent(s) completed and attested")

    # Explain the in-flight ones so the buyer knows what to chase.
    not_yet = [r for r in active if not r.counts]
    for r in not_yet:
        why = []
        if r.completion < MIN_COMPLETION:
            why.append(f"{int(r.completion * 100)}% answered, needs {int(MIN_COMPLETION * 100)}%")
        if not r.attested:
            why.append("attestation not signed")
        if why:
            missing.append(f"{r.role} respondent: " + ", ".join(why))

    return CoverageReport(
        is_met=not missing, tier=tier, size_bracket=size_bracket,
        minimum=req["minimum"], counted=len(counted), invited=len(active),
        missing_items=missing,
        details={"role_gaps": role_gaps, "min_completion": MIN_COMPLETION},
    )


def load_respondents(cursor, engagement_id: str) -> list[RespondentSummary]:
    cursor.execute(
        """
        SELECT id::text, coalesce(role, ''), coalesce(completion_percentage, 0),
               attestation_signed_at IS NOT NULL, coalesce(status, 'invited')
        FROM respondents WHERE engagement_id = %s
        """,
        [engagement_id],
    )
    return [RespondentSummary(rid, role, float(pct), bool(att), status)
            for rid, role, pct, att, status in cursor.fetchall()]


def check_coverage(cursor, engagement_id: str) -> CoverageReport:
    """Database-backed entry point used by views and the completion trigger."""
    cursor.execute(
        """
        SELECT e.tier, c.size_bracket
        FROM engagements e LEFT JOIN companies c ON c.id = e.company_id
        WHERE e.id = %s
        """,
        [engagement_id],
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"engagement {engagement_id} not found")
    tier, size_bracket = row
    return evaluate(tier or "tier_1", size_bracket, load_respondents(cursor, engagement_id))
