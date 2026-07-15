"""Maps option-strings on law-adjacent questions to law_name values from
questionnaire.law_catalog.

Used by services._decorate_question to filter downstream questions'
option lists to only the laws the user selected on T1-A-006. Options
NOT present in these maps are universal (e.g. "Other (specify)",
"None of these", "Don't know", "Other (specify)") and always remain
visible so the user retains agency.

Value can be:
- str  — single law_name in the LAW_INVENTORY catalog
- list — multiple law_names (option maps to more than one)

The runtime filter (see services._filter_options_by_laws) keeps an
option when EITHER its mapped law_name(s) intersect with the selected
set OR the option isn't in the map at all (universal fallthrough).
"""

from __future__ import annotations

# Mapping per-question. Keys are question IDs; values are dicts
# {option_string_verbatim: law_name_or_list}.

QUESTION_OPTION_LAW_MAP: dict[str, dict[str, object]] = {

    # T1-A-011 — voluntary standards. Every option is a specific framework.
    "T1-A-011": {
        "ISO 42001 (AI management system)":                "ISO/IEC 42001",
        "NIST AI RMF (AI Risk Management Framework)":      "NIST AI Risk Management Framework",
        "ISO/IEC 22989 (AI terminology reference)":        "ISO/IEC 22989",
        "NIST CSF (Cybersecurity Framework)":              "NIST Cybersecurity Framework and AI",
        "ISO 27001 (Information security management)":     "ISO 27001 and AI",
        "SOC 2":                                           "SOC 2 and AI",
        "COSO ERM (Enterprise Risk Management)":           "COSO ERM and AI",
        "DAMA-DMBOK (Data Management Body of Knowledge)":  "DAMA-DMBOK",
        "DCAM (Data Management Capability Assessment Model)": "EDM Council DCAM",
        "CDMC (Cloud Data Management Capabilities)":       "CDMC Cloud Data Management",
    },

    # T1-A-013 — contractual expectations. Only one item maps to laws in
    # the catalog (SBOM/AIBOM). The rest are contract-generic and always
    # shown.
    "T1-A-013": {
        "SBOM/AIBOM (software/AI bill of materials) contractual expectations":
            ["Software Bill of Materials", "AI Bill of Materials"],
    },

    # T1-E-029 — vendor contract provisions. Several options tie to laws.
    "T1-E-029": {
        "BAAs for HIPAA-covered data":       "HIPAA and AI",
        "GLBA Safeguards flow-down":         "GLBA and AI",
        "Data Processing Agreements (GDPR)": "GDPR and AI",
        "SBOM/AIBOM disclosure obligations":
            ["Software Bill of Materials", "AI Bill of Materials"],
    },

    # T1-F-013 — ISO 42001 gate-check.
    "T1-F-013": {
        # Whole question is only relevant when the user selected ISO/IEC
        # 42001. Handled separately in the filter (whole-question skip
        # instead of per-option filter — see _decorate_question).
    },

    # T1-F-014 — NIST AI RMF gate-check. Same whole-question skip pattern.
    "T1-F-014": {},
}


# Whole-question skip: hide these questions entirely if the user did NOT
# select the listed law in T1-A-006. Kept separate from per-option
# filtering because the whole question is meaningless otherwise.
WHOLE_QUESTION_LAW_GATE: dict[str, str] = {
    "T1-F-013": "ISO/IEC 42001",
    "T1-F-014": "NIST AI Risk Management Framework",
}
