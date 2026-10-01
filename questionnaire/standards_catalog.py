"""Voluntary standards for T1-A-011 (2026-10-01).

T1-A-011 is the one place a respondent names the AI, security, risk and
data standards the company aligns with or claims compliance to, including
those a customer contract or insurance policy requires. T1-A-006 asks
about laws and regulations only; the framework entries that used to sit
in it now live here, and any a respondent already ticked there carry over
as pre-checks. The ten original labels are kept verbatim so stored
answers keep their meaning.
"""

from __future__ import annotations

GROUPS: list[tuple[str, list[str]]] = [
    ("AI management and AI security", [
        "ISO 42001 (AI management system)",
        "ISO/IEC 42005 (AI system impact assessment)",
        "ISO/IEC 23894 (AI risk management)",
        "ISO/IEC 5338 (AI system life cycle)",
        "ISO/IEC 22989 (AI terminology reference)",
        "NIST AI RMF (AI Risk Management Framework)",
        "NIST AI 600-1 (Generative AI Profile)",
        "OWASP Top 10 for LLM Applications",
        "OWASP Agentic AI security guidance",
        "MITRE ATLAS (adversarial threats to AI systems)",
        "Google SAIF (Secure AI Framework)",
        "CSA AI Controls Matrix (AICM)",
        "HITRUST AI Security Assessment",
        "IEEE 7000 series (ethically aligned design)",
    ]),
    ("Information security and privacy", [
        "ISO 27001 (Information security management)",
        "ISO/IEC 27017 (cloud security controls)",
        "ISO/IEC 27018 (personal data in public cloud)",
        "ISO/IEC 27701 (privacy information management)",
        "NIST CSF (Cybersecurity Framework)",
        "NIST SP 800-53 (security and privacy controls)",
        "NIST SP 800-171 (controlled unclassified information)",
        "NIST SP 800-207 (Zero Trust architecture)",
        "NIST SSDF (SP 800-218 / 218A secure software development)",
        "CIS Critical Security Controls",
        "CSA Cloud Controls Matrix (CCM)",
        "SOC 1",
        "SOC 2",
        "PCI DSS",
        "HITRUST CSF",
        "CMMC 2.0",
        "FedRAMP",
        "StateRAMP",
    ]),
    ("Governance, risk and resilience", [
        "COSO ERM (Enterprise Risk Management)",
        "COSO Internal Control framework",
        "COBIT",
        "ISO 31000 (risk management)",
        "ISO 22301 (business continuity)",
        "SR 11-7 / OCC model risk management guidance",
    ]),
    ("Data management", [
        "DAMA-DMBOK (Data Management Body of Knowledge)",
        "DCAM (Data Management Capability Assessment Model)",
        "CDMC (Cloud Data Management Capabilities)",
    ]),
    ("Customer and insurer questionnaires you answer", [
        "SIG (Shared Assessments Standardized Information Gathering)",
        "CSA CAIQ (Consensus Assessments Initiative Questionnaire)",
        "HECVAT (higher education vendor assessment)",
        "Insurer cyber or AI supplemental application",
        "Customer-specific AI or security questionnaire",
    ]),
]

OPT_OUTS = ["Other (specify)", "None of these", "Don't know"]

OPTIONS: list[str] = [label for _, labels in GROUPS for label in labels] + OPT_OUTS
STANDARD_LABELS: set[str] = {label for _, labels in GROUPS for label in labels}
GROUP_OF: dict[str, str] = {label: g for g, labels in GROUPS for label in labels}

# Framework entries that used to be selectable in the T1-A-006 law
# inventory, mapped to their T1-A-011 label. They are removed from
# T1-A-006 (laws only) and a prior tick there pre-checks the label here.
LAW_NAME_TO_STANDARD: dict[str, str] = {
    "ISO/IEC 42001": "ISO 42001 (AI management system)",
    "ISO/IEC 22989": "ISO/IEC 22989 (AI terminology reference)",
    "NIST AI Risk Management Framework": "NIST AI RMF (AI Risk Management Framework)",
    "ISO 27001 and AI": "ISO 27001 (Information security management)",
    "SOC 2 and AI": "SOC 2",
    "NIST Cybersecurity Framework and AI": "NIST CSF (Cybersecurity Framework)",
    "COSO ERM and AI": "COSO ERM (Enterprise Risk Management)",
    "DAMA-DMBOK": "DAMA-DMBOK (Data Management Body of Knowledge)",
    "EDM Council DCAM": "DCAM (Data Management Capability Assessment Model)",
    "CDMC Cloud Data Management": "CDMC (Cloud Data Management Capabilities)",
}

# Everything that is a framework or a hub page, not a law, and so no longer
# offered in T1-A-006.
FRAMEWORK_LAW_NAMES: set[str] = set(LAW_NAME_TO_STANDARD) | {
    "General Business Governance", "Data Management Frameworks",
}

# Rule-based suggestions from the laws a respondent selected in T1-A-006,
# used when the AI suggester is unavailable.
LAW_SUGGESTS: dict[str, list[str]] = {
    "HIPAA and AI": ["HITRUST CSF", "NIST CSF (Cybersecurity Framework)"],
    "HHS OCR AI Enforcement": ["HITRUST CSF"],
    "GDPR and AI": ["ISO/IEC 27701 (privacy information management)", "ISO 27001 (Information security management)"],
    "EU AI Act": ["ISO 42001 (AI management system)", "ISO/IEC 42005 (AI system impact assessment)"],
    "GLBA and AI": ["SOC 2", "NIST CSF (Cybersecurity Framework)"],
    "NYDFS Part 500": ["NIST CSF (Cybersecurity Framework)"],
    "Federal Contractor AI": ["NIST SP 800-171 (controlled unclassified information)", "CMMC 2.0", "FedRAMP"],
    "SR 11-7 and the 2026 Model Risk Guidance": ["SR 11-7 / OCC model risk management guidance"],
    "SOX 302 and 404 for AI": ["COSO Internal Control framework", "SOC 1"],
    "Financial Reporting Rules for AI": ["COSO Internal Control framework", "SOC 1"],
    "FERPA and AI": ["HECVAT (higher education vendor assessment)"],
    "DORA": ["ISO 22301 (business continuity)", "ISO 27001 (Information security management)"],
    "NIS2 Directive": ["ISO 27001 (Information security management)"],
}
