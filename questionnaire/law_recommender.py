"""Rule-based recommender for T1-A-006 (LAW_INVENTORY).

Given what we already know about the respondent's company —
industry (NAICS sector, from signup), geographic footprint (T1-A-005),
and employee-size bracket (signup) — return the subset of the 59-law
catalog they likely need to track.

Public entry: ``recommend_laws(industry, size_bracket, geographic) -> list[str]``.
Returned strings are law_name values exactly as they appear in
questionnaire.law_catalog.CATEGORIES, so the partial can match them.

Design notes:
- Rules are deterministic and fast (no AI call at question render).
- Universal frameworks (NIST AI RMF, ISO 42001) apply to every company.
- Rules err on the side of inclusion — better to over-recommend than
  under-recommend, since the user can uncheck what doesn't apply.
- Called via services._decorate_question; keep imports lightweight.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Universal recommendations — applied to every company.
# ---------------------------------------------------------------------------

UNIVERSAL = [
    "NIST AI Risk Management Framework",
    "ISO/IEC 42001",
    "FTC AI Enforcement",
]


# ---------------------------------------------------------------------------
# NAICS 2-digit sector -> law_name list. Keys are the sector prefix of the
# stored "XX — Title" or "XX-YY — Title" industry string from the signup form.
# ---------------------------------------------------------------------------

NAICS_RULES: dict[str, list[str]] = {
    # Agriculture, Forestry, Fishing and Hunting
    "11": ["Federal Contractor AI"],
    # Mining, Quarrying, and Oil and Gas Extraction
    "21": ["Federal Contractor AI"],
    # Utilities
    "22": ["NIS2 Directive", "SEC AI Enforcement"],
    # Construction
    "23": ["Federal Contractor AI", "Title VII and AI"],
    # Manufacturing
    "31": ["Software Bill of Materials", "AI Bill of Materials",
           "EU Product Liability Directive", "EU Cyber Resilience Act",
           "Federal Contractor AI"],
    "32": ["Software Bill of Materials", "AI Bill of Materials",
           "EU Product Liability Directive", "EU Cyber Resilience Act",
           "Federal Contractor AI"],
    "33": ["Software Bill of Materials", "AI Bill of Materials",
           "EU Product Liability Directive", "EU Cyber Resilience Act",
           "Federal Contractor AI"],
    # Wholesale Trade
    "42": ["FTC AI Enforcement"],
    # Retail Trade
    "44": ["FTC AI Enforcement", "State Privacy Laws"],
    "45": ["FTC AI Enforcement", "State Privacy Laws"],
    # Transportation and Warehousing
    "48": ["Federal Contractor AI"],
    "49": ["Federal Contractor AI"],
    # Information (Software, Media, Tech)
    "51": ["State Privacy Laws", "GDPR and AI", "COPPA and AI",
           "SOC 2 and AI", "ISO 27001 and AI",
           "Software Bill of Materials", "AI Bill of Materials",
           "SEC AI Enforcement"],
    # Finance and Insurance
    "52": ["GLBA and AI", "FCRA and AI", "ECOA and AI",
           "SR 11-7 and the 2026 Model Risk Guidance",
           "NYDFS Part 500", "CFPB AI Enforcement",
           "SEC AI Enforcement", "FINRA and AI",
           "SOX 302 and 404 for AI", "FASB ASU 2025-06",
           "AICPA AI Guidance", "PCAOB AI Guidance",
           "DORA"],
    # Real Estate and Rental and Leasing
    "53": ["FCRA and AI", "ECOA and AI", "State Privacy Laws"],
    # Professional, Scientific, and Technical Services
    "54": ["SOC 2 and AI", "ISO 27001 and AI", "State Privacy Laws",
           "Federal Contractor AI"],
    # Management of Companies and Enterprises
    "55": ["Director Oversight", "COSO ERM and AI",
           "SOX 302 and 404 for AI", "SEC AI Enforcement"],
    # Administrative and Support and Waste Management
    "56": ["Title VII and AI", "EEOC AI Enforcement", "WARN Act and AI"],
    # Educational Services
    "61": ["FERPA and AI", "COPPA and AI", "State Privacy Laws",
           "Title VII and AI"],
    # Health Care and Social Assistance
    "62": ["HIPAA and AI", "HHS OCR AI Enforcement",
           "State Privacy Laws", "COPPA and AI",
           "Title VII and AI"],
    # Arts, Entertainment, and Recreation
    "71": ["Tennessee ELVIS Act", "State Privacy Laws"],
    # Accommodation and Food Services
    "72": ["Title VII and AI", "State Privacy Laws"],
    # Other Services
    "81": ["Title VII and AI", "State Privacy Laws"],
    # Public Administration
    "92": ["Federal AI Legislation", "Federal Contractor AI",
           "Agency Enforcement", "State AI Laws"],
}


# ---------------------------------------------------------------------------
# Geographic footprint -> jurisdictional laws.
# Matches on substrings so the T1-A-005 answer (e.g. "Multi-state, US
# including California and New York") triggers the right rules.
# ---------------------------------------------------------------------------

GEO_RULES: list[tuple[str, list[str]]] = [
    ("EU",           ["EU AI Act", "GDPR and AI", "NIS2 Directive",
                      "DORA", "EU Product Liability Directive",
                      "EU Cyber Resilience Act", "CETS 225"]),
    ("European",     ["EU AI Act", "GDPR and AI"]),
    ("Global",       ["EU AI Act", "GDPR and AI", "CETS 225",
                      "Global AI Laws", "China AI Regulation"]),
    ("California",   ["California AI Laws", "State Privacy Laws"]),
    ("Colorado",     ["Colorado AI Act"]),
    ("Texas",        ["Texas Responsible AI Governance Act"]),
    ("Illinois",     ["Illinois AI Laws"]),
    ("Connecticut",  ["Connecticut AI Act"]),
    ("Tennessee",    ["Tennessee ELVIS Act"]),
    ("New York",     ["New York City AI Laws",
                      "NYC Local Law 144",
                      "NYC Local Law 35",
                      "NYDFS Part 500"]),
    ("NYC",          ["NYC Local Law 144", "NYC Local Law 35"]),
    ("Multi-state",  ["State AI Laws", "State Privacy Laws"]),
    ("Multiple states", ["State AI Laws", "State Privacy Laws"]),
]


# ---------------------------------------------------------------------------
# Employee size buckets that trigger employment / workforce laws.
# Bracket strings come from signup form (company_size_bracket).
# ---------------------------------------------------------------------------

EMPLOYER_THRESHOLDS: list[tuple[str, list[str]]] = [
    # 15+ employees triggers most federal employment discrimination law.
    ("26-100",    ["Title VII and AI", "EEOC AI Enforcement"]),
    ("101-500",   ["Title VII and AI", "EEOC AI Enforcement",
                   "WARN Act and AI"]),
    ("501-2000",  ["Title VII and AI", "EEOC AI Enforcement",
                   "WARN Act and AI", "NYC Local Law 144"]),
    ("2001-5000", ["Title VII and AI", "EEOC AI Enforcement",
                   "WARN Act and AI", "NYC Local Law 144",
                   "SEC AI Enforcement"]),
    ("5000+",     ["Title VII and AI", "EEOC AI Enforcement",
                   "WARN Act and AI", "NYC Local Law 144",
                   "SEC AI Enforcement", "Director Oversight"]),
]


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

def _naics_prefix(industry: Optional[str]) -> Optional[str]:
    """Pull the leading NAICS sector code from '31-33 -- Manufacturing' etc."""
    if not industry:
        return None
    head = industry.split()[0]  # '31-33' or '11' or 'Other'
    if not head or not head[:2].isdigit():
        return None
    return head[:2]  # keep two digits — always addresses NAICS_RULES key


def recommend_laws(
    industry: Optional[str] = None,
    size_bracket: Optional[str] = None,
    geographic: Optional[Any] = None,
) -> list[str]:
    """Return an ordered, de-duplicated list of recommended law_name values.

    Order matches the canonical CATEGORIES order in law_catalog.py so the
    template can efficiently check membership by set lookup regardless.
    """
    seen: set[str] = set()
    out: list[str] = []

    def push(names: Iterable[str]):
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)

    push(UNIVERSAL)

    prefix = _naics_prefix(industry)
    if prefix and prefix in NAICS_RULES:
        push(NAICS_RULES[prefix])
    # Try both digits of a 3-digit-based prefix (e.g. NAICS 31 rule fires for '31')
    # Already handled by _naics_prefix returning 2 chars.

    # Geographic: T1-A-005 can be a string OR a dict {selected: str|[str]}
    geo_text = ""
    if isinstance(geographic, dict):
        sel = geographic.get("selected")
        if isinstance(sel, list):
            geo_text = " ".join(str(s) for s in sel)
        elif isinstance(sel, str):
            geo_text = sel
    elif isinstance(geographic, str):
        geo_text = geographic
    for keyword, names in GEO_RULES:
        if keyword.lower() in geo_text.lower():
            push(names)

    if size_bracket:
        for bracket, names in EMPLOYER_THRESHOLDS:
            if bracket == size_bracket:
                push(names)
                break

    return out
