"""AI IT Security Audit(TM) question bank, Pillar II, instrument "aiitsa".

Source: AIITSA_Audit_Program_Source_Spec_v1_6 S.5/S.6 with the v1.9
conventions applied: every stored ID carries the AIITSA- prefix (S.13.1);
all 143 questions kept after the S.14.1 dedup pass against the Pillar I 138
(0 true duplicates; the closest pair, GOV-001 vs T1-F-010, is a different
fact asked of a different respondent, which the rule calls triangulation).

One answer scale for the whole instrument: Yes / Partially / No / Don't
know. "Don't know" scores as unknown-zone exposure (S.5, S.6).

baseline_area maps each question to one of the seven Defensible AI
Security Baseline areas (S.2.3). The spec names the areas but does not map
questions to them; the mapping is a build artefact, rule: the area whose
minimum defensible standard the question is evidence for. Each section has
a default area and AREA_OVERRIDES lists the exceptions. Changing an
assignment is a data edit here.

Trademark rule (S.12, OD-B): Visibility Triangle, Six-Domain Operating
View, Defensible AI Security Baseline, Four-Page Pack, AI Red Button and
Agent Identity Register render WITHOUT (TM). The product mark is
"AI IT Security Audit" with (TM) and no "The" (OD-01).

Records carry the same keys as questionnaire.question_bank.QUESTIONS so
flow, skip logic, partial templates and the review page work unchanged.
"""

from __future__ import annotations

INSTRUMENT = "aiitsa"
ANSWER_OPTIONS = ["Yes", "Partially", "No", "Don't know"]
BASELINE_AREAS = ["Inventory", "Access", "Data", "Vendors", "Incidents", "Governance", "Evidence"]
VISIBILITY_TRIANGLE = {"SCR-002", "SCR-003", "SCR-004", "SCR-005", "SCR-006", "SCR-007"}

# section -> (domain, label, default baseline area)
SECTIONS = {
    "SCR": ("screening", "Screening: The Opening Seven", None),
    "GOV": ("governance", "Security Governance & Risk Management", 'Governance'),
    "SOC": ("security_operations", "Security Operations", 'Incidents'),
    "ARC": ("architecture", "Architecture & Engineering", 'Access'),
    "APP": ("application_security", "Application & Product Security", 'Evidence'),
    "TPR": ("third_party_risk", "Third-Party & Supply Chain Risk", 'Vendors'),
    "DAT": ("data_protection", "Data Protection & Privacy", 'Data'),
    "INV": ("inventory", "Inventory Feeder", 'Inventory'),
}

AREA_OVERRIDES = {
    "SCR-001": "Evidence",
    "SCR-002": "Governance",
    "SCR-003": "Incidents",
    "SCR-004": "Access",
    "SCR-005": "Access",
    "SCR-006": "Vendors",
    "SCR-007": "Data",
    "GOV-006": "Evidence",
    "GOV-008": "Evidence",
    "GOV-009": "Evidence",
    "GOV-010": "Evidence",
    "GOV-011": "Evidence",
    "GOV-016": "Evidence",
    "SOC-011": "Access",
    "SOC-012": "Access",
    "ARC-001": "Inventory",
    "ARC-002": "Data",
    "ARC-003": "Inventory",
    "ARC-004": "Incidents",
    "ARC-006": "Evidence",
    "ARC-014": "Incidents",
    "ARC-019": "Incidents",
    "ARC-020": "Incidents",
    "ARC-021": "Incidents",
    "APP-002": "Incidents",
    "APP-003": "Access",
    "APP-004": "Data",
    "APP-005": "Data",
    "APP-006": "Incidents",
    "APP-009": "Incidents",
    "APP-010": "Incidents",
    "APP-012": "Incidents",
    "APP-013": "Incidents",
    "APP-014": "Access",
    "APP-015": "Access",
    "APP-016": "Data",
    "APP-021": "Data",
    "APP-023": "Data",
    "APP-024": "Access",
    "APP-025": "Incidents",
    "TPR-007": "Data",
    "TPR-009": "Data",
    "TPR-010": "Access",
    "TPR-011": "Data",
    "DAT-019": "Incidents",
    "DAT-021": "Access",
    "INV-002": "Vendors",
}

# (id, text) in document order. Screening SCR-001 is the audit's opening
# question; the seven screening items are always asked first (S.5).
ROWS = [
    ("SCR-001", 'Can you prove your AI exposure is known, controlled, and governed with a dated, reviewable document that would survive regulator or enterprise-customer scrutiny today?'),
    ("SCR-002", 'Can you name an AI risk that is missing from your risk register?'),
    ("SCR-003", 'Can you name an AI-enabled attack that would never alert in your SOC?'),
    ("SCR-004", 'Can you name a non-human identity in your environment that cannot be enumerated?'),
    ("SCR-005", 'Can you name an agent action that bypasses your deployment pipeline?'),
    ("SCR-006", 'Can you name a vendor model that is learning from your company data?'),
    ("SCR-007", 'Can you name an AI data path in your environment that is not mapped?'),
    ("GOV-001", 'Does your risk register contain a specific entry for algorithmic/AI model risk?'),
    ("GOV-002", 'Does your risk register contain a specific entry for autonomous agents?'),
    ("GOV-003", 'Does your risk register contain a specific entry for non-human identities?'),
    ("GOV-004", 'Is AI risk reported to leadership on a defined cadence?'),
    ("GOV-005", "Is AI security reflected as a line in this year's budget?"),
    ("GOV-006", 'Can you show the board the document proving GOV-004 and GOV-005?'),
    ("GOV-007", 'Is there a named individual accountable if an AI system becomes the vector for a security incident?'),
    ("GOV-008", 'Can you produce the document naming that person today, before harm occurs?'),
    ("GOV-009", 'Do you have a defined AI audit method documented before any external audit begins?'),
    ("GOV-010", 'Do you have a dated, scored security Baseline covering AI exposure?'),
    ("GOV-011", 'Do you have a one-page framework reference mapping your AI controls to external frameworks?'),
    ("GOV-012", 'Have you named the specific event that would trigger audit scope expansion or a board-level AI inquiry?'),
    ("GOV-013", 'Does your governance structure define how AI risk reaches the board?'),
    ("GOV-014", 'Is there a cross-functional coalition (CISO, CIO, CRO, GC) named for AI security ownership?'),
    ("GOV-015", 'Is accountability for AI failures documented, not informal?'),
    ("GOV-016", 'Do you know your posture for the regulators most likely to ask about AI?'),
    ("GOV-017", 'Does your risk appetite statement explicitly address AI-specific risks?'),
    ("GOV-018", 'Does your cyber insurance / risk-transfer posture cover AI-specific incidents, and has the carrier been asked?'),
    ("SOC-001", 'If an AI agent went off-script in production, would something in your stack catch it?'),
    ("SOC-002", 'Would something in your stack contain it?'),
    ("SOC-003", 'Do you know how fast containment would happen?'),
    ("SOC-004", 'Can you rapidly revoke AI API tokens and model credentials (an "AI red button" capability)?'),
    ("SOC-005", 'Has that revocation procedure been tested, with a dated result?'),
    ("SOC-006", 'Do you know what happens operationally immediately after revocation?'),
    ("SOC-007", 'Has your detection stack been tuned against AI-specific threat techniques (e.g., MITRE ATLAS categories)?'),
    ("SOC-008", 'Do you maintain a coverage matrix of AI threat techniques vs. current detections?'),
    ("SOC-009", 'Is AI incident response integrated into your existing IR plan?'),
    ("SOC-010", 'Has an AI-specific incident response been rehearsed, with a date you can cite?'),
    ("SOC-011", 'Do you know what your defensive AI tools can act on autonomously vs. what requires human approval?'),
    ("SOC-012", 'Is the authority granting that autonomy documented?'),
    ("SOC-013", 'Have you verified what alerts your AI triage tooling is suppressing?'),
    ("SOC-014", 'If a suppressed alert turned out to be a real threat, could the team reconstruct the decision, confidence score, and context?'),
    ("SOC-015", "Are defensive AI decisions, escalations, and false positives logged and reviewable outside the tool's own console?"),
    ("SOC-016", 'Is there a named owner, performance measure, and reassessment cadence for each defensive AI capability?'),
    ("SOC-017", 'Is your defensive AI tuned to your specific threat model rather than a generic scoring model?'),
    ("SOC-018", 'Does SOC detection cover AI-enabled phishing and deepfake-enabled social engineering?'),
    ("SOC-019", 'Do your threat intelligence sources include AI-specific adversary tradecraft?'),
    ("SOC-020", 'Do IR playbooks cover AI-native incidents: prompt injection, model exfiltration, agent compromise?'),
    ("SOC-021", 'Do DR/BC plans cover AI workloads, model artifacts, and AI-dependent business processes?'),
    ("SOC-022", 'Has patching/vulnerability cadence been reassessed for AI-accelerated exploit windows?'),
    ("SOC-023", 'Are your own AI systems red-teamed / adversarially tested on a defined cadence, not just pre-production?'),
    ("ARC-001", 'For each production AI system, do you know its model lineage?'),
    ("ARC-002", 'Do you know what data it retrieves?'),
    ("ARC-003", 'Do you know what tools it can invoke?'),
    ("ARC-004", 'Do you know what telemetry it emits?'),
    ("ARC-005", 'Do you know what guardrails contain it?'),
    ("ARC-006", 'Do you know what evidence trail it leaves?'),
    ("ARC-007", 'Have you calculated the blast radius, the worst-case outcome if excess permissions were exploited?'),
    ("ARC-008", 'Do you maintain a current enumeration of every non-human identity with AI-related privileges?'),
    ("ARC-009", 'Does every agent have an identity-register entry with a named owner?'),
    ("ARC-010", "Does each agent's permitted-actions list map completely to its permission scope, with no excess permissions?"),
    ("ARC-011", "Is each agent's authority chain complete, with no missing approvals?"),
    ("ARC-012", "Is each agent's data-access scope fully classified, with authorizations for all regulated data stores?"),
    ("ARC-013", 'Are agent guardrails configured and tested, with results documented?'),
    ("ARC-014", 'Is agent invocation logging complete, monitored, and retained per IR and regulatory requirements?'),
    ("ARC-015", 'Has each agent passed a pre-production prompt-injection test?'),
    ("ARC-016", 'Do MCP servers hold only the permissions required for their configured operations?'),
    ("ARC-017", 'Are agent/MCP credentials stored in an approved secret-management system with access controls, logging, and version history?'),
    ("ARC-018", 'Was the last credential rotation performed within the policy window?'),
    ("ARC-019", 'Can you detect agent access at unusual times, to unusual systems, or at unusual volumes?'),
    ("ARC-020", 'Can you tell when an agent acts beyond the authority of the user who invoked it?'),
    ("ARC-021", 'Have you tested, not just documented, what would contain each AI system if it went wrong?'),
    ("ARC-022", 'Does your Zero Trust architecture cover AI traffic patterns, agent-to-agent calls, model API consumption, RAG pipelines, embedding store access (per NIST SP 800-207)?'),
    ("ARC-023", 'Have network, endpoint, and hybrid-cloud controls been evaluated for AI-related blind spots?'),
    ("ARC-024", 'Is MFA resilient against AI-enabled credential attacks, and are credential exposure pathways mapped?'),
    ("APP-001", 'Does every AI feature have a threat model naming attackers, assets, attack paths, and mitigating controls?'),
    ("APP-002", "Do you know what happens if the model receives an instruction it wasn't designed to follow (prompt injection)?"),
    ("APP-003", "Do you know what the model has access to that it shouldn't use?"),
    ("APP-004", "Do you know what the retrieval pipeline trusts that it shouldn't?"),
    ("APP-005", "Do you know what the model's output reaches that it shouldn't?"),
    ("APP-006", 'Do you monitor for model behavior change between reviews (drift)?'),
    ("APP-007", 'Did every AI feature meet defined release criteria before reaching production, with named owners?'),
    ("APP-008", 'Is there an AI-specific secure-development-lifecycle addendum governing new AI builds?'),
    ("APP-009", "Do you know your AI security tooling's false-positive rate over the last 90 days?"),
    ("APP-010", 'Is that rate acceptable given finding volume?'),
    ("APP-011", 'Is scanning tuned to the languages, frameworks, and patterns your developers actually use?'),
    ("APP-012", 'Are identified AI vulnerabilities remediated against a defined SLA?'),
    ("APP-013", 'Is that SLA being met?'),
    ("APP-014", 'Do you know what repositories your coding assistants read?'),
    ("APP-015", 'Do you know what secrets they touch?'),
    ("APP-016", 'Do you know what data they send to the model provider?'),
    ("APP-017", 'Is assistant-generated code reviewed under a defined process?'),
    ("APP-018", 'Are AI-built applications held to the same standard as the rest of the business, with evidence?'),
    ("APP-019", 'Is there MLOps governance for model approval, deployment, retirement, and model incident response?'),
    ("APP-020", 'Has exposure been assessed against the OWASP LLM Top 10 vulnerability classes?'),
    ("APP-021", 'Are output validation controls in place for AI-generated content before it reaches users or systems?'),
    ("APP-022", 'Have AI vendor integrations and internal AI service endpoints had an API security review?'),
    ("APP-023", 'Are defenses in place against training data poisoning for models you train or fine-tune?'),
    ("APP-024", 'Are controls in place against model theft and extraction (weights, system prompts, distillation via API)?'),
    ("APP-025", 'Are model endpoints protected against unbounded consumption, rate limits, cost caps, DoS controls?'),
    ("TPR-001", 'Have you reviewed existing contracts for AI terms agreed to before anyone was paying attention to AI?'),
    ("TPR-002", 'Do you know which vendor contracts authorize model training on your data?'),
    ("TPR-003", 'Do you know which authorize fine-tuning on customer data?'),
    ("TPR-004", 'Do you know which authorize sharing your data with a third-party model provider?'),
    ("TPR-005", 'Do your contracts require notification before a vendor adds AI features?'),
    ("TPR-006", 'Do they give you the right to opt out of AI features?'),
    ("TPR-007", 'For each AI vendor, do you know what data categories its AI features process, at what classification, in what volume?'),
    ("TPR-008", "Do you know whether each vendor's AI makes or influences security decisions vs. producing informational output a human reviews?"),
    ("TPR-009", "Do you know each vendor's third-party model provider, and is it named as a sub-processor in the DPA?"),
    ("TPR-010", 'Do vendor integrations hold connections broader than the primary service requires?'),
    ("TPR-011", "Do you know each vendor's tenant-isolation model for your data in its model infrastructure?"),
    ("TPR-012", 'Do you know how model version updates are communicated and what behavioral changes accompany them?'),
    ("TPR-013", 'Do contracts define notification timelines for data breach, inference-data exposure, and model-provider breach?'),
    ("TPR-014", 'Can you opt out of or delay AI feature changes affecting data handling or training rights?'),
    ("TPR-015", 'Do you maintain a tiered vendor inventory classified by depth of data access and training rights?'),
    ("TPR-016", 'Have DPAs been re-reviewed since vendors added AI, and have model-provider chains changed since last review?'),
    ("TPR-017", "Can you name which contracts grant training rights you didn't realize you granted?"),
    ("TPR-018", 'Are open-source AI dependencies evaluated for provenance, maintenance posture, and known vulnerabilities?'),
    ("TPR-019", 'Does your vendor security questionnaire cover AI-specific risks?'),
    ("TPR-020", 'Is model supply chain exposure assessed, model weights, training data provenance, fine-tuning pipelines?'),
    ("DAT-001", 'Do you have a data flow map tracing every category of sensitive data through every AI system that touches it?'),
    ("DAT-002", 'Can you prove sensitive data is handled appropriately at every point along the AI path?'),
    ("DAT-003", 'Can you demonstrate a lawful basis for each AI processing activity involving personal data?'),
    ("DAT-004", 'Do you know where regulated personal data enters your AI systems?'),
    ("DAT-005", 'Do you know where it goes and who can access it?'),
    ("DAT-006", 'Do you know whether it is used for training?'),
    ("DAT-007", 'For each data category: do you know where it came from, who owns it, and its classification?'),
    ("DAT-008", 'Do you know the consent or contractual basis governing its use in each AI workflow?'),
    ("DAT-009", 'Do you know where it is stored before entering the AI workflow, and who can retrieve it?'),
    ("DAT-010", "Do you know whether it enters a model provider's environment (direct API or vendor-hosted)?"),
    ("DAT-011", 'Do you know whether the provider retains it after the API call completes?'),
    ("DAT-012", 'Is data stripped, masked, blocked, or approved before entering AI training workflows?'),
    ("DAT-013", 'Before entering fine-tuning workflows?'),
    ("DAT-014", 'Before entering retrieval corpora?'),
    ("DAT-015", 'Before entering prompt workflows (direct model input)?'),
    ("DAT-016", 'Before model output is returned to users or written to downstream systems?'),
    ("DAT-017", 'Do you know what form data takes when it exits the AI workflow (output, embedding, retrieval result, intermediate representation) and what consumes it?'),
    ("DAT-018", 'If a data subject exercises erasure, can you prove it was satisfied, including embeddings, training data, and vendor-retained inference data?'),
    ("DAT-019", 'Is AI service endpoint monitoring in your network DLP stack (prompts are data)?'),
    ("DAT-020", 'Are lifecycle and retention controls applied to AI-related data, including prompts and outputs?'),
    ("DAT-021", 'Is encryption posture verified across AI workloads, including model artifacts and embedding stores?'),
    ("DAT-022", 'Is privacy compliance posture for AI documented under GDPR, CCPA, and applicable state frameworks?'),
    ("DAT-023", 'Has model inversion / membership inference risk been assessed for models trained on sensitive data?'),
    ("INV-001", 'Do you maintain a current, dated four-layer AI inventory: sanctioned, shadow, embedded, agentic?'),
    ("INV-002", 'Does your vendor-intake checklist ask whether a product includes AI features and what data those features process?'),
    ("INV-003", 'Have you defined your "unknown zone", what you know you don\'t yet see, with a discovery method per entry?'),
]


def _build() -> list[dict]:
    out = []
    for seq, (short, text) in enumerate(ROWS, start=1):
        sec = short[:3]
        domain, label, default_area = SECTIONS[sec]
        area = AREA_OVERRIDES.get(short, default_area)
        if area is None:
            raise ValueError(f"{short} has no baseline area")
        out.append({
            "id": f"AIITSA-{short}", "tier": "tier_1", "instrument": INSTRUMENT,
            "section": sec, "sequence_number": seq,
            "domain": domain, "domain_label": label, "baseline_area": area,
            "visibility_triangle": short in VISIBILITY_TRIANGLE,
            "question_text": text, "question_type": "SS", "options": list(ANSWER_OPTIONS),
            "matrix_rows": None, "matrix_columns": None, "skip_logic": None,
            "role_visibility": ["all"], "required": True, "scoring_weight": 1.0,
            "framework_mappings": [], "notes": None, "is_active": True,
            "scoring_overrides": None, "extended_metadata": None,
        })
    return out


AIITSA_QUESTIONS: list[dict] = _build()
DOMAINS = [v[0] for v in SECTIONS.values()]
