"""
scoring.gap_actions — Map detected gaps to recommended actions.

Per Part A §5.4. The framework aggregators (v1_audit, v2_readiness,
v3_governance, efficiency) each surface a `top_gaps` list of
SubComponentScore / V2ModuleScore / V3StepScore / EfficiencyComponentScore
objects. This module translates those into structured GapAction records
that report templates render directly into the priority-gaps section.

CONTRACT
--------
Each gap action carries four fields:

    statement     — One sentence naming the gap in plain language.
    impact        — 1–2 sentences explaining the business consequence.
    action        — 1–2 sentences with the concrete first step.
    addresses_via — One canonical trademark identifying the methodology
                    that addresses the gap.

CANONICAL KEY FORMAT
--------------------
Keys are `{framework}.{dimension|module|step|component}.{condition}`.

The dimension/module/step/component component matches the canonical
name used in the framework aggregator. The condition describes the
specific failure mode (e.g. `no_inventory_exists`, `inventory_outdated`,
`shadow_ai_uncontrolled` for the V1 tool_inventory dimension).

v0.1 maps ONE canonical gap per sub_component / module / step /
component. Multi-severity gap variants (different actions for different
score depths) are deferred — when v0.2 wants them, add new keys with
condition suffixes like `_severe` / `_moderate` and update
`resolve_gap_action()` to branch on score.

TRADEMARK CONSTRAINTS
---------------------
The `addresses_via` field uses ONLY trademarks listed in the operator's
permitted-trademark set:

    AI Integration Checklist™              AI ROI Evaluation Framework™
    AI Performance Scorecard™              AI Performance Governance™
    AI Operational Risk Assessment™        AI Operational Risk Categories™
    AI Decision Accountability Framework™  AI Adoption Decision Framework™
    Standing AI Adoption Policy™           AI Operating Calendar™
    Operational Health Check™              Operational Integration & Workflow Adoption™
    Outcome Alignment Map™                 (… and the rest of the permitted set)

Reports must reference these surface forms verbatim. Drift control is
enforced upstream by `reports.trademark_config.CANONICAL_MARKS`.

LOOKUP
------
For each item in a framework result's `top_gaps`, call
`resolve_gap_action(framework_name, dimension_or_module_or_step, name)`.
Returns a `GapAction` or `None` if no canonical mapping exists for that
identifier. The report generator handles the None case by falling back
to a generic "this area scored low; further investigation recommended"
message.
"""

from __future__ import annotations

from dataclasses import dataclass


# ----------------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class GapAction:
    """One mapped gap with its recommended remediation."""
    key: str
    statement: str
    impact: str
    action: str
    addresses_via: str


# ----------------------------------------------------------------------------
# The canonical gap-to-action mapping
# ----------------------------------------------------------------------------
# Entries are grouped by framework. Each entry is keyed by a canonical
# identifier; resolve_gap_action looks the key up directly.

GAP_TO_ACTION: dict[str, GapAction] = {}


def _add(
    key: str,
    statement: str,
    impact: str,
    action: str,
    addresses_via: str,
) -> None:
    GAP_TO_ACTION[key] = GapAction(
        key=key,
        statement=statement,
        impact=impact,
        action=action,
        addresses_via=addresses_via,
    )


# --- V1 Audit: tool_inventory --------------------------------------------

_add(
    "v1_audit.tool_inventory.inventory_existence",
    "No AI tool inventory currently exists",
    "Without an inventory the company cannot demonstrate AI governance to "
    "auditors, regulators, or acquirers, and cannot reliably identify "
    "exposure to data, contract, or compliance risk.",
    "Run a 60-day inventory project covering every AI tool in active use: "
    "owner, cost, data accessed, purpose, approval status. Establish a "
    "quarterly review cadence with a named owner.",
    "AI Integration Checklist™",
)

_add(
    "v1_audit.tool_inventory.inventory_currency",
    "AI tool inventory exists but has not been refreshed in over 90 days",
    "Outdated inventory creates false confidence. Recent additions and "
    "retirements are invisible, and exposure analysis based on it is "
    "indefensible.",
    "Refresh the inventory within 30 days. Lock in a quarterly review "
    "cadence with calendar invites and a named owner.",
    "Operational Health Check™",
)

_add(
    "v1_audit.tool_inventory.shadow_ai",
    "Significant shadow AI adoption (employees using AI tools without "
    "central approval)",
    "Shadow AI creates uncontrolled data exposure, contractual conflict, "
    "and an unmanaged risk surface that does not appear in any audit, "
    "insurance, or board report.",
    "Survey employees on actual AI tool usage with amnesty for prior "
    "adoption. Bring high-value shadow tools into the formal inventory; "
    "retire or replace the rest.",
    "AI Integration Checklist™",
)

_add(
    "v1_audit.tool_inventory.approval_process",
    "No formal approval process before AI tools are adopted",
    "New tools enter the environment without security, contract, or "
    "compliance review. Exposure grows silently and ad hoc.",
    "Stand up a documented approval gate: business owner names the use "
    "case, IT/security reviews data handling, legal reviews terms. No "
    "tool goes live without sign-off.",
    "AI Adoption Decision Framework™",
)

_add(
    "v1_audit.tool_inventory.vendor_enabled_awareness",
    "Vendor-enabled AI features added by existing software vendors are "
    "not catalogued or reviewed",
    "Existing vendors are silently rolling out AI features that change "
    "the data-handling profile of trusted tools. These features bypass "
    "the company's normal AI approval gate.",
    "Audit every active SaaS contract for new AI features added in the "
    "past 24 months. Decide per feature: keep enabled, disable, or "
    "require a new contractual review.",
    "AI Integration Checklist™",
)

# --- V1 Audit: cost_mapping ----------------------------------------------

_add(
    "v1_audit.cost_mapping.total_spend",
    "No consolidated view of total AI-related spend across the company",
    "Without a single number, leadership cannot defend the AI budget to "
    "the board, evaluate ROI, or negotiate from a position of knowledge "
    "with vendors.",
    "Direct finance to produce a single monthly AI spend report covering "
    "subscriptions, API charges, professional services, hardware, and "
    "vendor-enabled feature upgrades. Track as a distinct budget line.",
    "AI ROI Evaluation Framework™",
)

_add(
    "v1_audit.cost_mapping.hidden_cost_awareness",
    "Hidden AI costs (error correction time, duplicated tools, "
    "customization, training) are not measured",
    "Direct subscription cost is typically 30–50% of true AI cost. "
    "Decisions based only on subscription pricing systematically "
    "under-estimate cost and over-estimate ROI.",
    "Run a one-month hidden-cost study: instrument time spent on AI "
    "error correction, tool overlap, and rework. Bake the multiplier "
    "into future ROI calculations.",
    "AI ROI Evaluation Framework™",
)

_add(
    "v1_audit.cost_mapping.roi_discipline",
    "No AI tool has had a documented ROI calculation in the past 12 months",
    "Without ROI discipline, money flows toward whichever tool the loudest "
    "internal advocate is championing. Capital efficiency degrades and "
    "renewal decisions are reactive.",
    "Pick the three highest-spend AI tools and run a structured ROI "
    "analysis per tool: business impact attributable, total cost, "
    "alternatives. Use the result to inform the next renewal cycle.",
    "AI ROI Evaluation Framework™",
)

_add(
    "v1_audit.cost_mapping.contract_tracking",
    "AI vendor contracts are not centrally tracked",
    "Renewal dates, exit costs, and usage-based pricing triggers are "
    "invisible. The company is exposed to surprise auto-renewals, "
    "uncontrolled overage charges, and lock-in.",
    "Pull every AI vendor contract into a central registry with renewal "
    "date, exit cost, usage-based pricing terms, and indemnification "
    "language. Assign a renewal owner per contract.",
    "AI Operational Risk Assessment™",
)

# --- V1 Audit: performance_measurement -----------------------------------

_add(
    "v1_audit.performance_measurement.per_use_case_metric_existence",
    "No defined success metrics for top AI use cases",
    "Without metrics, AI continuation is driven by sunk-cost reasoning "
    "and internal politics rather than business outcomes. Underperforming "
    "tools accumulate.",
    "For each of the three top AI use cases, define one quantitative "
    "success metric tied to revenue, cost, time, quality, or risk. "
    "Establish baseline and report cadence.",
    "AI Performance Scorecard™",
)

_add(
    "v1_audit.performance_measurement.review_accountability",
    "AI performance is not reviewed on a defined cadence by named owners",
    "Performance issues compound silently. Decisions to expand or kill AI "
    "tools become emotional rather than evidence-based.",
    "Establish a monthly AI performance review meeting with named "
    "attendees, defined metrics, and standing decision rights to expand, "
    "refine, or pause each AI initiative.",
    "AI Performance Governance™",
)

_add(
    "v1_audit.performance_measurement.error_containment",
    "AI errors are not consistently caught before reaching customers or "
    "final decisions",
    "Customer-facing AI errors damage trust and create regulatory "
    "exposure. Internal errors propagate into financial reporting, "
    "hiring decisions, and contract terms.",
    "Define a high-stakes review process for AI outputs that touch "
    "customers, money, hiring, or legal positions. Require named human "
    "review before delivery.",
    "AI Decision Accountability Framework™",
)

_add(
    "v1_audit.performance_measurement.baseline_comparison",
    "No pre-AI baseline measurements exist for AI-touched processes",
    "Without a baseline, the company cannot prove whether AI improved or "
    "worsened the process. Vendor performance claims are accepted "
    "uncritically.",
    "Reconstruct or measure baselines for the three highest-impact "
    "AI-touched processes. Compare current AI-assisted performance "
    "honestly, including hidden costs and quality drift.",
    "AI Performance Scorecard™",
)

# --- V1 Audit: risk_exposure ---------------------------------------------

_add(
    "v1_audit.risk_exposure.data_exposure_existence",
    "Sensitive company information has been entered into external AI tools",
    "Confidential customer, employee, financial, or strategic data may "
    "be retained, used for vendor training, or exposed in a vendor "
    "breach. This is the single highest-consequence AI exposure pattern.",
    "Run an immediate data exposure audit: which AI tools have received "
    "what categories of data. For each, verify vendor data-handling "
    "terms and restrict use of regulated data via technical controls.",
    "AI Operational Risk Assessment™",
)

_add(
    "v1_audit.risk_exposure.data_classification_policy",
    "No documented data classification policy governs what data can flow "
    "into AI tools",
    "Employees default to convenience: any data may enter any tool. The "
    "company has no defensible answer to 'how did our customer data end "
    "up there?'",
    "Publish a one-page data classification policy with three tiers "
    "(public / internal / restricted) and explicit rules per tier for AI "
    "tool use. Pair with training and technical controls.",
    "Standing AI Adoption Policy™",
)

_add(
    "v1_audit.risk_exposure.vendor_compliance_verification",
    "AI vendor SOC 2 / ISO compliance has not been verified for major vendors",
    "Untested vendor claims of compliance create reliance on assertions "
    "that may not survive an actual audit. Insurance and contractual "
    "indemnification may be void.",
    "Request and review SOC 2 / ISO 27001 reports from the top five AI "
    "vendors by spend. File results in the central vendor registry; "
    "flag any vendor without current attestation.",
    "AI Operational Risk Categories™",
)

_add(
    "v1_audit.risk_exposure.high_stakes_use_categories",
    "AI is involved in high-stakes decisions (hiring, lending, pricing) "
    "without documented review",
    "Decisions in these categories create legal, regulatory (EEOC, CFPB, "
    "ECOA), and reputational risk if AI bias or error is later "
    "discovered.",
    "Map every AI use case in hiring, firing, promotion, pricing, "
    "lending, or credit. For each, document the human review point and "
    "the bias-audit cadence.",
    "AI Decision Accountability Framework™",
)

_add(
    "v1_audit.risk_exposure.ai_insurance_coverage",
    "No insurance policy specifically addresses AI-related liability",
    "Cyber policies typically exclude or limit AI-related claims. "
    "Liability for AI error or bias may fall entirely on the company "
    "with no carrier participation.",
    "Engage your broker on current AI-related coverage. Request a "
    "written summary of what is included, excluded, and the carrier's "
    "stance on AI-generated content liability.",
    "AI Operational Risk Categories™",
)

_add(
    "v1_audit.risk_exposure.bias_audit_discipline",
    "No documented bias-audit discipline for AI tools influencing people "
    "or pricing decisions",
    "Regulatory regimes including EEOC, CFPB, and NYC Local Law 144 "
    "require bias auditing for AI in employment and credit. Failure to "
    "audit is itself a defensibility gap.",
    "Identify every AI tool in scope for bias audit. For each, define "
    "the audit frequency, the population studied, and the disparate "
    "impact threshold. Document each cycle.",
    "AI Operational Risk Assessment™",
)

_add(
    "v1_audit.risk_exposure.autonomous_action_scope",
    "Autonomous AI execution operates without defined circuit breakers "
    "or scope limits",
    "Agentic AI systems acting without bounds can take irreversible "
    "actions (sending communications, executing transactions) before "
    "humans can intervene.",
    "For every autonomous-execution AI in use, document the action "
    "scope, the kill switch, and the human approval gates. Restrict the "
    "blast radius until governance catches up.",
    "AI Decision Accountability Framework™",
)

# --- V1 Audit: governance_gaps -------------------------------------------

_add(
    "v1_audit.governance_gaps.policy_existence",
    "No published AI usage policy",
    "Without a policy, employees, vendors, and regulators have no "
    "anchor. Every team improvises differently and the company has no "
    "defensible position.",
    "Publish a one-page AI usage policy covering approved tools, data "
    "classification, prohibited uses, and incident reporting. Require "
    "annual employee attestation.",
    "Standing AI Adoption Policy™",
)

_add(
    "v1_audit.governance_gaps.governance_structures",
    "No named executive is formally accountable for AI outcomes",
    "Accountability without a name is not accountability. AI initiatives "
    "stall, contradict each other, and produce no escalation path when "
    "things go wrong.",
    "Designate a named AI accountability lead at the executive level "
    "(CIO/COO/CFO). Document the role in the org chart with explicit "
    "decision authority and reporting cadence.",
    "AI Decision Accountability Framework™",
)

_add(
    "v1_audit.governance_gaps.action_discipline",
    "No documented executive review cadence for AI matters",
    "AI decisions get made reactively in hallway conversations rather "
    "than in a standing forum with documented rationale.",
    "Add a quarterly AI review to the executive calendar. Standing "
    "agenda: inventory updates, performance against metrics, incident "
    "review, and pending approval decisions.",
    "AI Operating Calendar™",
)

_add(
    "v1_audit.governance_gaps.incident_response_process",
    "No documented incident response process for AI-related failures",
    "When AI fails publicly (an error reaches a customer, a data leak is "
    "discovered, a regulator inquires) the company has no runbook. "
    "Response is improvised and damage compounds.",
    "Draft a one-page AI incident response runbook: who is notified "
    "within the first hour, who decides on customer communication, who "
    "talks to regulators. Run a tabletop exercise within 90 days.",
    "AI Operational Risk Assessment™",
)

_add(
    "v1_audit.governance_gaps.risk_register",
    "AI risks are not on the corporate risk register",
    "AI risk is invisible to the board's risk-oversight function. ERM "
    "frameworks (COSO, etc.) treat it as out-of-scope. Insurance "
    "renewals proceed without AI considered.",
    "Add AI as a named risk category on the corporate risk register "
    "with sub-categories for data, decision, vendor, and reputational "
    "risk. Review at every risk committee meeting.",
    "AI Operational Risk Categories™",
)

_add(
    "v1_audit.governance_gaps.training_program",
    "No AI training program exists for employees",
    "Without training, the company depends on individual employees' "
    "intuition about safe and appropriate AI use. Errors and policy "
    "violations are inevitable.",
    "Launch a required annual AI training covering data classification, "
    "approved tools, prohibited uses, and incident reporting. Track "
    "completion in the LMS.",
    "Standing AI Adoption Policy™",
)

# --- V2 Readiness: by module ---------------------------------------------

_add(
    "v2_readiness.workflow_readiness",
    "Workflow integration of AI is ad hoc rather than designed",
    "AI tools are bolted onto existing workflows without re-design. "
    "Benefit is captured by individual employees rather than at the "
    "process or organizational level.",
    "Pick two high-value AI use cases and run a structured workflow "
    "redesign: map current state, define target state, identify the "
    "human-AI hand-off points, and roll out with measurement.",
    "Operational Integration & Workflow Adoption™",
)

_add(
    "v2_readiness.data_readiness",
    "Data readiness for AI use is low — classification, lineage, and "
    "exposure controls are missing",
    "Without data discipline, AI either fails to deliver value (garbage "
    "in) or creates uncontrolled exposure (sensitive data flowing into "
    "untrusted tools).",
    "Establish a three-tier data classification policy, document data "
    "lineage for the top AI use cases, and enforce classification-based "
    "tool restrictions via technical controls.",
    "AI Operational Risk Categories™",
)

_add(
    "v2_readiness.people_readiness",
    "People readiness for AI is low — training, role clarity, and adoption "
    "discipline are missing",
    "Employees either work around AI tools (capturing no benefit) or use "
    "them indiscriminately (creating exposure). Skill gaps are not "
    "addressed systematically.",
    "Launch a required AI fluency training. Define role-specific AI "
    "competencies. Track adoption signals (utilization, error rates, "
    "workaround frequency) at the team level.",
    "Standing AI Adoption Policy™",
)

_add(
    "v2_readiness.leadership_accountability",
    "Leadership accountability for AI outcomes is weak",
    "AI is treated as IT's problem, not a leadership concern. "
    "Strategic alignment, capital allocation, and risk decisions happen "
    "without senior ownership.",
    "Name an executive AI lead at the C-level. Add AI as a standing "
    "agenda item at executive and board meetings. Require quarterly "
    "AI accountability reports to the board.",
    "AI Decision Accountability Framework™",
)

_add(
    "v2_readiness.performance_measurement",
    "Performance measurement for AI is informal or absent",
    "Without measurement, AI continuation is governed by vendor "
    "rhetoric and internal advocacy. Capital and attention flow to "
    "tools that may not be delivering value.",
    "Define a minimum performance dashboard for AI: utilization, "
    "outcome metrics, error rates, time savings. Review at the "
    "executive level monthly.",
    "AI Performance Scorecard™",
)

_add(
    "v2_readiness.operational_friction",
    "AI tools are creating operational friction rather than reducing it",
    "Employees work around AI tools, spend time correcting errors, or "
    "abandon them silently. Reported productivity gains do not match "
    "actual experience on the ground.",
    "Survey users of the three highest-spend AI tools on actual "
    "experience. Identify friction points. Decide per tool: improve, "
    "replace, or retire.",
    "Operational Health Check™",
)

# --- V3 Governance: by step -----------------------------------------------

_add(
    "v3_governance.accountability_mapping",
    "AI accountability is not mapped to named owners and roles",
    "Without an accountability map, decisions stall, incidents have no "
    "owner, and the company cannot answer 'who decided that?' for any "
    "AI-related outcome.",
    "Produce a one-page accountability map: for AI strategy, policy, "
    "incidents, vendor management, and performance, identify the named "
    "owner and the escalation path.",
    "AI Decision Accountability Framework™",
)

_add(
    "v3_governance.data_exposure_assessment",
    "Data exposure across AI tools has not been systematically assessed",
    "The company cannot answer what categories of data are flowing into "
    "which AI tools under what contractual terms. Risk is uncountable "
    "and uncontrollable.",
    "Conduct a structured data exposure assessment per AI tool: data "
    "categories, sensitivity, vendor data-handling terms, and "
    "compensating controls. Document findings centrally.",
    "AI Operational Risk Assessment™",
)

_add(
    "v3_governance.decision_influence_review",
    "AI influence on consequential decisions has not been reviewed",
    "High-stakes decisions (hiring, lending, pricing, regulatory "
    "filings) may be influenced by AI without documented human review. "
    "Liability concentrates silently.",
    "Inventory every business decision touched by AI. For each, "
    "document the AI influence, the human review point, and the "
    "documentation trail for regulatory defensibility.",
    "AI Decision Accountability Framework™",
)

_add(
    "v3_governance.vendor_risk_inventory",
    "AI vendor risk has not been inventoried and assessed",
    "Without a vendor risk inventory the company has no view of "
    "concentration risk, switching cost, or contractual indemnification "
    "across its AI footprint.",
    "Build a vendor risk register covering: SOC 2/ISO status, data "
    "handling, indemnification, switching cost, and concentration. "
    "Review annually.",
    "AI Operational Risk Categories™",
)

_add(
    "v3_governance.framework_crosswalk_readiness",
    "Mapping of AI program to regulatory and voluntary frameworks is "
    "incomplete",
    "When a regulator, customer, or insurer asks 'how does your AI "
    "program align with ISO 42001 / NIST AI RMF / EU AI Act / SR 11-7?' "
    "the company has no defensible answer.",
    "Identify the regulatory and voluntary frameworks applicable to "
    "your industry. Build a crosswalk mapping current AI controls to "
    "each framework. Maintain quarterly.",
    "AI Risk & Governance Review™",
)

_add(
    "v3_governance.incident_response_readiness",
    "AI incident response capability has not been tested",
    "When an AI incident occurs (data leak, customer-facing error, "
    "regulator inquiry) the company will improvise. First-hour "
    "decisions will be made without authority or playbook.",
    "Write an AI incident response runbook. Tabletop-test it within "
    "90 days using a realistic scenario. Iterate based on findings.",
    "AI Operational Risk Assessment™",
)

# --- Efficiency: by component ---------------------------------------------

_add(
    "efficiency.outcome_alignment",
    "AI investments are not tied to measurable business outcomes",
    "Without outcome alignment, AI spend becomes a series of "
    "individually-defensible tools that collectively cannot be shown to "
    "be improving the business. ROI conversations stall.",
    "For every AI investment, require an explicit outcome statement "
    "tied to revenue, cost, quality, or risk. Measure quarterly and "
    "expand, refine, or pause based on results.",
    "Outcome Alignment Map™",
)

_add(
    "efficiency.process_optimization",
    "Processes have not been optimized around AI — workarounds and "
    "friction dominate",
    "AI is generating activity rather than improving processes. "
    "Reported productivity gains do not survive contact with actual "
    "user experience.",
    "Pick two high-spend AI processes and run a structured process "
    "redesign: measure baseline, define target, redesign the workflow, "
    "and re-measure after 90 days.",
    "Operational Integration & Workflow Adoption™",
)


# ----------------------------------------------------------------------------
# Lookup
# ----------------------------------------------------------------------------

def resolve_gap_action(
    framework: str,
    identifier: str,
    *,
    sub_component: str | None = None,
) -> GapAction | None:
    """Look up the GapAction for a given gap identifier.

    Parameters
    ----------
    framework
        One of: 'v1_audit', 'v2_readiness', 'v3_governance', 'efficiency'.
    identifier
        For V1: dimension name (e.g. 'tool_inventory', 'risk_exposure')
        For V2: module name (e.g. 'workflow_readiness')
        For V3: step name (e.g. 'accountability_mapping')
        For Efficiency: component name (e.g. 'outcome_alignment')
    sub_component
        For V1 only: the specific sub_component name. Other frameworks
        ignore this parameter.

    Returns
    -------
    GapAction if a canonical mapping exists; None otherwise. The report
    generator handles None by emitting a generic fallback message.
    """
    if framework == "v1_audit" and sub_component:
        key = f"{framework}.{identifier}.{sub_component}"
        return GAP_TO_ACTION.get(key)

    # V2/V3/Efficiency: module/step/component name is the key suffix
    key = f"{framework}.{identifier}"
    return GAP_TO_ACTION.get(key)


def get_all_gap_keys() -> list[str]:
    """Return every defined gap key, useful for coverage audits."""
    return sorted(GAP_TO_ACTION.keys())


def coverage_summary() -> dict[str, int]:
    """Return {framework: count} for telemetry."""
    out: dict[str, int] = {}
    for key in GAP_TO_ACTION:
        framework = key.split(".", 1)[0]
        out[framework] = out.get(framework, 0) + 1
    return out
