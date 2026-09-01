"""AI-governance law/framework catalog for T1-A-006 LAW_INVENTORY.

Source: ai-governance-coverage.csv (Stephen, 2026-07-15). LAWS_FLAT is 61
entries as of 2026-07-29 (an earlier docstring said 59; recount confirms 61).
This count is quoted in public marketing copy — update both together.
Every URL points to the theworldofai.org reference page for
that framework/law. Categories are derived from URL path.
"""

from __future__ import annotations

# CATEGORIES: [(category_title, [(law_name, srj_url), ...]), ...]
CATEGORIES = [
    ('International Standards & Frameworks', [
        ('ISO/IEC 42001', 'https://theworldofai.org/ai-compliance/iso-42001/'),
        ('ISO/IEC 22989', 'https://theworldofai.org/ai-compliance/iso-22989/'),
        ('NIST AI Risk Management Framework', 'https://theworldofai.org/ai-compliance/nist-ai-rmf/'),
    ]),
    ('EU / International', [
        ('EU AI Act', 'https://theworldofai.org/ai-compliance/eu-ai-act/'),
        ('EU Cyber Resilience Act', 'https://theworldofai.org/ai-compliance/eu-cyber-resilience-act/'),
        ('EU Product Liability Directive', 'https://theworldofai.org/ai-compliance/eu-product-liability/'),
        ('NIS2 Directive', 'https://theworldofai.org/ai-compliance/nis2/'),
        ('DORA', 'https://theworldofai.org/ai-compliance/dora/'),
        ('CETS 225', 'https://theworldofai.org/ai-compliance/coe-framework-convention/'),
        ('China AI Regulation', 'https://theworldofai.org/ai-compliance/china-ai-regulation/'),
        ('Global AI Laws', 'https://theworldofai.org/ai-compliance/global-ai-laws/'),
    ]),
    ('Top-level Frameworks & US Federal', [
        ('NYDFS Part 500', 'https://theworldofai.org/ai-compliance/nydfs-part-500/'),
        ('Federal Contractor AI', 'https://theworldofai.org/ai-compliance/federal-contractor-ai/'),
        ('State Privacy Laws', 'https://theworldofai.org/ai-compliance/state-privacy-laws/'),
        ('New York City AI Laws', 'https://theworldofai.org/ai-compliance/nyc-ai-laws/'),
        ('State AI Laws', 'https://theworldofai.org/ai-compliance/state-ai-laws/'),
        ('Federal AI Legislation', 'https://theworldofai.org/ai-compliance/federal-ai-legislation/'),
        ('SR 11-7 and the 2026 Model Risk Guidance', 'https://theworldofai.org/ai-compliance/sr-11-7/'),
        ('Agency Enforcement', 'https://theworldofai.org/ai-compliance/agency-enforcement/'),
        ('Sector Rules', 'https://theworldofai.org/ai-compliance/sector-rules/'),
        ('Financial Reporting Rules for AI', 'https://theworldofai.org/ai-compliance/financial-reporting/'),
        ('Director Oversight', 'https://theworldofai.org/ai-compliance/director-oversight/'),
        ('General Business Governance', 'https://theworldofai.org/ai-compliance/general-business-governance/'),
        ('Vendor Disclosure', 'https://theworldofai.org/ai-compliance/vendor-disclosure/'),
        ('Data Management Frameworks', 'https://theworldofai.org/ai-compliance/data-management-frameworks/'),
    ]),
    ('US Agency Enforcement', [
        ('FTC AI Enforcement', 'https://theworldofai.org/ai-compliance/ftc-ai-enforcement/'),
        ('EEOC AI Enforcement', 'https://theworldofai.org/ai-compliance/eeoc-ai-enforcement/'),
        ('CFPB AI Enforcement', 'https://theworldofai.org/ai-compliance/cfpb-ai-enforcement/'),
        ('SEC AI Enforcement', 'https://theworldofai.org/ai-compliance/sec-ai-enforcement/'),
        ('HHS OCR AI Enforcement', 'https://theworldofai.org/ai-compliance/hhs-ocr-ai-enforcement/'),
    ]),
    ('State AI Laws', [
        ('Colorado AI Act', 'https://theworldofai.org/ai-compliance/colorado-ai-act/'),
        ('Texas Responsible AI Governance Act', 'https://theworldofai.org/ai-compliance/texas-ai-act/'),
        ('California AI Laws', 'https://theworldofai.org/ai-compliance/california-ai-laws/'),
        ('Illinois AI Laws', 'https://theworldofai.org/ai-compliance/illinois-ai-laws/'),
        ('Connecticut AI Act', 'https://theworldofai.org/ai-compliance/connecticut-ai-act/'),
        ('Tennessee ELVIS Act', 'https://theworldofai.org/ai-compliance/tennessee-elvis-act/'),
    ]),
    ('New York City AI Laws', [
        ('NYC Local Law 144', 'https://theworldofai.org/ai-compliance/nyc-ll-144/'),
        ('NYC Local Law 35', 'https://theworldofai.org/ai-compliance/nyc-ll-35/'),
    ]),
    ('Sector Rules (HIPAA, GDPR, FCRA, etc.)', [
        ('HIPAA and AI', 'https://theworldofai.org/ai-compliance/hipaa-ai/'),
        ('COPPA and AI', 'https://theworldofai.org/ai-compliance/coppa-ai/'),
        ('GDPR and AI', 'https://theworldofai.org/ai-compliance/gdpr-ai/'),
        ('GLBA and AI', 'https://theworldofai.org/ai-compliance/glba-ai/'),
        ('FCRA and AI', 'https://theworldofai.org/ai-compliance/fcra-ai/'),
        ('ECOA and AI', 'https://theworldofai.org/ai-compliance/ecoa-ai/'),
        ('Title VII and AI', 'https://theworldofai.org/ai-compliance/title-vii-ai/'),
        ('WARN Act and AI', 'https://theworldofai.org/ai-compliance/warn-ai/'),
        ('FERPA and AI', 'https://theworldofai.org/ai-compliance/ferpa-ai/'),
        ('FINRA and AI', 'https://theworldofai.org/ai-compliance/finra-ai/'),
    ]),
    ('Financial Reporting for AI', [
        ('FASB ASU 2025-06', 'https://theworldofai.org/ai-compliance/fasb-asu-2025-06/'),
        ('AICPA AI Guidance', 'https://theworldofai.org/ai-compliance/aicpa-ai-guidance/'),
        ('PCAOB AI Guidance', 'https://theworldofai.org/ai-compliance/pcaob-ai-guidance/'),
        ('SOX 302 and 404 for AI', 'https://theworldofai.org/ai-compliance/sox-302-404-ai/'),
    ]),
    ('General Business Governance (ISO, SOC 2, NIST CSF, COSO)', [
        ('ISO 27001 and AI', 'https://theworldofai.org/ai-compliance/iso-27001-ai/'),
        ('SOC 2 and AI', 'https://theworldofai.org/ai-compliance/soc-2-ai/'),
        ('NIST Cybersecurity Framework and AI', 'https://theworldofai.org/ai-compliance/nist-csf-ai/'),
        ('COSO ERM and AI', 'https://theworldofai.org/ai-compliance/coso-erm-ai/'),
    ]),
    ('Vendor Disclosure (SBOM / AIBOM)', [
        ('Software Bill of Materials', 'https://theworldofai.org/ai-compliance/sbom/'),
        ('AI Bill of Materials', 'https://theworldofai.org/ai-compliance/aibom/'),
    ]),
    ('Data Management Frameworks', [
        ('DAMA-DMBOK', 'https://theworldofai.org/ai-compliance/dama-dmbok/'),
        ('EDM Council DCAM', 'https://theworldofai.org/ai-compliance/dcam/'),
        ('CDMC Cloud Data Management', 'https://theworldofai.org/ai-compliance/cdmc/'),
    ]),
]

# Flat list of law names in canonical rendering order — feeds T1-A-006
# `options` list at DB-load time.
LAWS_FLAT = [name for _, items in CATEGORIES for name, _ in items]
