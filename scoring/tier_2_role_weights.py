"""Role-weight profiles for multi-respondent aggregation (Part B-3 S.2.1).

role_weight(role, framework, dimension) in {0, 0.5, 1.0, 1.5, 2.0}.
0 means "this role's view does not inform this dimension". Anything not
listed defaults to 1.0, so a new role or dimension degrades to a plain
weighted mean rather than an error.

B-3 gives the table as illustrative and calls the full table a build
artefact; this is that artefact. The shape of every row follows the same
logic: the people who OPERATE a thing rate its friction and adoption; the
people ACCOUNTABLE for a thing rate its governance, risk and outcomes.
Adjusting a weight is a data change here, not a code change.
"""

from __future__ import annotations

LEADERSHIP = frozenset({"BOARD", "CEO", "CFO", "CIO", "CISO", "COO"})
WORKFORCE = frozenset({"VP", "DIR", "MGR", "IC", "HR"})

_EXEC_HEAVY = {"BOARD": 2.0, "CEO": 2.0, "CFO": 1.5, "CIO": 1.5, "CISO": 1.5, "COO": 1.5,
               "VP": 1.0, "DIR": 1.0, "HR": 1.0, "MGR": 0.5, "IC": 0.5}
_TECH_HEAVY = {"CISO": 2.0, "CIO": 2.0, "COO": 1.5, "CFO": 1.0, "CEO": 1.0, "BOARD": 0.5,
               "VP": 1.0, "DIR": 1.0, "HR": 0.5, "MGR": 0.5, "IC": 0.5}
_FLOOR_HEAVY = {"IC": 2.0, "MGR": 2.0, "VP": 1.5, "DIR": 1.5, "HR": 1.5, "COO": 1.0,
                "CEO": 0.5, "CFO": 0.5, "CIO": 0.5, "CISO": 0.5, "BOARD": 0.0}
_FINANCE_HEAVY = {"CEO": 2.0, "CFO": 2.0, "COO": 1.5, "BOARD": 1.5, "VP": 1.0, "DIR": 1.0,
                  "CIO": 1.0, "CISO": 0.5, "HR": 0.5, "MGR": 0.5, "IC": 0.0}

ROLE_WEIGHTS: dict[tuple[str, str], dict[str, float]] = {
    # V1 The AI Business Enablement Audit
    ("v1_audit", "tool_inventory"):          _TECH_HEAVY | {"IC": 1.0, "MGR": 1.0},
    ("v1_audit", "risk_exposure"):           _TECH_HEAVY | {"IC": 0.5},
    ("v1_audit", "governance_gaps"):         _EXEC_HEAVY | {"CISO": 2.0},
    ("v1_audit", "cost_mapping"):            _FINANCE_HEAVY,
    ("v1_audit", "performance_measurement"): _FINANCE_HEAVY | {"MGR": 1.0, "IC": 0.5},
    # V2 The AI Readiness & Performance Assessment
    ("v2_readiness", "workflow_readiness"):        _FLOOR_HEAVY,
    ("v2_readiness", "operational_friction"):      _FLOOR_HEAVY,
    ("v2_readiness", "people_readiness"):          _FLOOR_HEAVY | {"HR": 2.0},
    ("v2_readiness", "data_readiness"):            _TECH_HEAVY | {"MGR": 1.0},
    ("v2_readiness", "leadership_accountability"): _EXEC_HEAVY | {"IC": 1.0, "MGR": 1.0},
    ("v2_readiness", "performance_measurement"):   _FINANCE_HEAVY | {"MGR": 1.0, "IC": 0.5},
    # V3 AI Risk & Governance Review
    ("v3_governance", "accountability_mapping"):        _EXEC_HEAVY | {"CISO": 2.0, "IC": 0.0},
    ("v3_governance", "data_exposure_assessment"):      _TECH_HEAVY | {"IC": 0.5, "MGR": 0.5},
    ("v3_governance", "vendor_risk_inventory"):         _TECH_HEAVY | {"CFO": 1.5},
    ("v3_governance", "decision_influence_review"):     _EXEC_HEAVY | {"MGR": 1.0, "IC": 1.0},
    ("v3_governance", "incident_response_readiness"):   _TECH_HEAVY,
    ("v3_governance", "framework_crosswalk_readiness"): _EXEC_HEAVY | {"CISO": 2.0, "CIO": 2.0, "IC": 0.0},
    # V4 The AI Efficiency & Process Optimization
    ("efficiency", "outcome_alignment"):     _FINANCE_HEAVY | {"IC": 0.0, "MGR": 0.5},
    ("efficiency", "process_optimization"):  _FLOOR_HEAVY | {"COO": 1.5, "BOARD": 0.5},
}


def role_weight(role: str | None, framework: str, dimension: str) -> float:
    profile = ROLE_WEIGHTS.get((framework, dimension))
    if profile is None or not role:
        return 1.0
    return float(profile.get(role.upper(), 1.0))
