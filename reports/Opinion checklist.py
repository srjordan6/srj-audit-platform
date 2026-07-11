 PY
"""Qualified-opinion checklist (Phase 2b).
 
100 specific conditions the auditor watches for when identifying, validating,
and formulating a qualified opinion, grouped into five research domains:
governance/data access, executive oversight/financial controls, organizational
readiness/operational maturity, leadership accountability/human-in-the-loop,
and risk management/continuous auditing.
 
Source: operator-supplied checklist, 2026-07-11. Edit text freely; the AI
opinion-basis evaluation reads this list at call time - no other code changes
needed.
 
Each entry: (point_number, domain, condition_text).
"""
 
D1 = "AI Governance & Data Access Controls"
D2 = "Executive Oversight & Financial Controls"
D3 = "Organizational Readiness & Operational Maturity"
D4 = "Leadership Accountability & Human-in-the-Loop"
D5 = "AI Risk Management & Continuous Auditing"
 
CHECKLIST = [
    (1, D1, "Absence of a formalized data access protocol across external systems."),
    (2, D1, "Lack of explicit categorizations defining what data is strictly prohibited inside external generative environments."),
    (3, D1, "Failure to verify third-party vendor data-retention and model-training opt-out policies."),
    (4, D1, "Employees using unsanctioned personal accounts to log into business-critical AI platforms."),
    (5, D1, "Absence of centralized vendor screening for API-driven model integrations."),
    (6, D1, "Omission of intellectual property (IP) indemnity clauses in enterprise AI contracts."),
    (7, D1, "Processing sensitive customer personally identifiable information (PII) without localized anonymization layers."),
    (8, D1, "Lack of explicit corporate policies defining permitted vs. restricted data categories."),
    (9, D1, "Absence of an established protocol for revoking tool access during employee offboarding."),
    (10, D1, "Lack of legal or compliance review before deploying models trained on mixed external data sources."),
    (11, D1, "Failure to match localized data sovereignty mandates with the physical storage locations of vendor servers."),
    (12, D1, "Omission of automatic session timeouts or credential rotations for high-access AI developer sandboxes."),
    (13, D1, "Absence of localized data loss prevention (DLP) filters between employee inputs and external APIs."),
    (14, D1, "Exposure of proprietary source code via employee copy-paste actions into public debugging interfaces."),
    (15, D1, "Lack of a formal approval process for adding new experimental plug-ins to active operational tools."),
    (16, D1, "Relying entirely on vendor terms-of-service updates without executing localized compliance reviews."),
    (17, D1, "Inadequate security screening for browser extensions that utilize background AI screen-scraping features."),
    (18, D1, "Sharing protected health information (PHI) or corporate financial records with generic consumer-tier accounts."),
    (19, D1, "Lack of data-sharing disclosures provided to end customers whose inputs train external systems."),
    (20, D1, "Absence of a centralized, secure repository for API keys used across distributed microservices."),
    (21, D2, "Inability of the executive team to define absolute cumulative monthly spend across all active AI platforms."),
    (22, D2, "Tool duplication resulting from different departments independently purchasing overlapping AI subscription tiers."),
    (23, D2, "Proliferation of hidden costs tied to unreviewed departmental expenses and card-on-file subscriptions."),
    (24, D2, "Lack of a structured dashboard showing total active licenses across the enterprise network."),
    (25, D2, "Failure to tie AI investments to concrete, measurable business performance metrics."),
    (26, D2, "Inaccurate or speculative calculations regarding the true return on investment (ROI) of deployed software."),
    (27, D2, "Relying on qualitative employee satisfaction metrics rather than quantitative output improvements."),
    (28, D2, "Failure to account for implementation downtime and staff retraining costs when building financial baselines."),
    (29, D2, "Absence of clear contractual limits on consumption-based API billing tiers, risking unexpected budget overruns."),
    (30, D2, "Untracked software subscription renewals occurring automatically without active utility evaluations."),
    (31, D2, "Lack of corporate alignment between the AI budget and core, overarching strategic business goals."),
    (32, D2, "Inability to track productivity gains dynamically down to the department level."),
    (33, D2, "Absence of capital allocation frameworks specifically built to evaluate new model procurement cycles."),
    (34, D2, "Relying on vendor-supplied performance figures rather than independent internal testing data."),
    (35, D2, "Failure to audit legacy software platforms to identify feature overlap with newly introduced native AI capabilities."),
    (36, D2, "Neglecting to calculate the recurring costs of secondary infrastructure, cloud data storage, and compute pipelines."),
    (37, D2, "Lack of an executive veto process for unauthorized tier upgrades initiated by line managers."),
    (38, D2, "Relying on project-based financial assessments rather than establishing permanent, ongoing cost reviews."),
    (39, D2, "Absence of clear amortization paths for bespoke model training expenditures."),
    (40, D2, "Failure to reconcile AI vendor billing anomalies within standard 30-day accounting cycles."),
    (41, D3, "Prevalence of hidden Shadow AI - tools leveraged natively by employees completely outside corporate IT view."),
    (42, D3, "Fragmentation of adoption, leading to severe variances in execution quality between different departments."),
    (43, D3, "Absence of a centralized, updated corporate AI inventory containing names, use cases, and ownership roles."),
    (44, D3, "Lack of standardized technical onboarding or usage tutorials for newly introduced automated workflows."),
    (45, D3, "Operating out of a reactive posture - scrambling to review technology only after an operational bug occurs."),
    (46, D3, "Relying entirely on out-of-the-box system assumptions without testing localized operational edge cases."),
    (47, D3, "Lack of cross-departmental coordination regarding successful automated workflow best practices."),
    (48, D3, "Extreme dependency on specific employee-built scripts that lack corporate documentation or transition paths."),
    (49, D3, "High friction between traditional legacy IT infrastructure and newly implemented operational endpoints."),
    (50, D3, "Failure to update internal standard operating procedures (SOPs) to accurately reflect automated task variations."),
    (51, D3, "Staff members defaulting back to manual work loops due to technical friction within the automated system."),
    (52, D3, "Absence of an operational fallback plan or manual override in the event of an extended vendor service outage."),
    (53, D3, "Disconnection between technical implementation teams and the actual business operators deploying the tool."),
    (54, D3, "Lack of a formal change management framework to handle workforce transitions and role adaptations."),
    (55, D3, "Relying on a project-based adoption mindset rather than managing automation as a long-term business function."),
    (56, D3, "System architectures that lack modular flexibility, creating an inability to easily swap out unoptimized backend models."),
    (57, D3, "Absence of standard KPIs to monitor long-term tool depreciation or accuracy decay."),
    (58, D3, "Inadequate internal training regarding the basic capabilities and technical limits of prompt-based architectures."),
    (59, D3, "Failure to run parallel testing environments before migrating old legacy workflows over to automated nodes."),
    (60, D3, "Inconsistent deployment criteria that vary widely based on individual team preferences rather than corporate standards."),
    (61, D4, "Operating high-accountability AI systems without an explicitly assigned, named human owner."),
    (62, D4, "Lack of mandatory, documented human-in-the-loop verification protocols prior to external data distribution."),
    (63, D4, "Automated distribution of customer-facing communication or compliance documents completely free of human oversight."),
    (64, D4, "Relying on automated workflows to execute critical legal, financial, or contract evaluations without expert validation."),
    (65, D4, "Absence of documented sign-offs or approvals for consequential AI-driven operational outputs."),
    (66, D4, "Disconnection between theoretical corporate policy guidelines and day-to-day employee operational habits."),
    (67, D4, "Vague definitions of ultimate liability between technical developers, departmental management, and vendors."),
    (68, D4, "Failure to build explicit workflow triggers that remove employee ambiguity on when tools must or must not be used."),
    (69, D4, "Neglecting to execute formal validation loops on all algorithmic recommendation outputs used by executives."),
    (70, D4, "Lack of structured governance onboarding protocols designed specifically for incoming executive leaders."),
    (71, D4, "Omission of audit logs that record which human operator approved an automated system output."),
    (72, D4, "Blind reliance on automated dashboard metrics without periodic deep-dive sanity testing by senior management."),
    (73, D4, "Absence of an internal whistleblowing mechanism for employees to escalate discovered algorithmic biases or system flaws."),
    (74, D4, "Inadequate human validation steps inside automated HR, resume screening, or performance ranking systems."),
    (75, D4, "Disregarding warning signals from front-line operators regarding consistent model inaccuracies or hallucinations."),
    (76, D4, "Failure to tie management performance bonuses to compliance metrics within their specific AI implementations."),
    (77, D4, "Lack of an explicit corporate review requirement checklist based on the system's operational impact rating."),
    (78, D4, "Relying entirely on developer sign-off for operational software without securing functional business unit approvals."),
    (79, D4, "Absence of an active, named committee or officer responsible for ongoing policy alignment."),
    (80, D4, "Failure to re-verify human reviewer competency levels as tools introduce advanced updates or structural changes."),
    (81, D5, "Absence of a formal classification matrix to tier tools by low, medium, or high operational risk levels."),
    (82, D5, "Risk exposure accumulating incrementally via undetected, minor performance drifts over time."),
    (83, D5, "Failure to implement a recurring policy verification loop within the quarterly governance cycle."),
    (84, D5, "Relying exclusively on one-off, project-based initial approvals instead of conducting continuous monitoring."),
    (85, D5, "Lack of rigorous stress-testing or red-teaming on systems exposed directly to public-facing environments."),
    (86, D5, "Inadequate incident response frameworks to manage data leaks, offensive outputs, or model failures."),
    (87, D5, "Failure to analyze how a vendor's financial stability or API structure could impact ongoing operations."),
    (88, D5, "Relying on static documentation that fails to reflect rapid, real-time software updates."),
    (89, D5, "Inability to quickly isolate or take a compromised system offline without breaking adjacent business components."),
    (90, D5, "Lack of comprehensive, unedited audit logs detailing system inputs, internal routing, and terminal outputs."),
    (91, D5, "Failure to run third-party model assessments on highly custom or fine-tuned corporate network applications."),
    (92, D5, "Absence of an inventory tracking mechanism to log emerging compliance and regulatory rules against current deployments."),
    (93, D5, "Neglecting to verify the algorithmic provenance and licensing structure of base operational models."),
    (94, D5, "Omission of data bias monitoring across systems that directly affect customer pricing or credit assessments."),
    (95, D5, "Lack of a formalized, mandatory monthly inventory check-in to catch hidden operational variations."),
    (96, D5, "Failure to evaluate how third-party plug-ins handle and store localized data inputs."),
    (97, D5, "Inadequate security patching schedules for localized model servers and adjacent data ingestion pipelines."),
    (98, D5, "Relying on basic firewalls without deploying advanced security protocols optimized specifically for AI vectors."),
    (99, D5, "Absence of clear contractual remedies or exit strategies if a vital vendor suddenly changes their data privacy policy."),
    (100, D5, "Reconciling systemic model flaws via superficial prompt adjustments rather than addressing core governance architecture failures."),
]
 
 
def checklist_text() -> str:
    """Render the checklist as compact numbered text for the AI prompt."""
    lines = []
    current_domain = None
    for num, domain, text in CHECKLIST:
        if domain != current_domain:
            lines.append(f"\n## {domain}")
            current_domain = domain
        lines.append(f"{num}. {text}")
    return "\n".join(lines)