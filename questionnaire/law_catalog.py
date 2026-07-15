"""AI-governance law/framework catalog for T1-A-006 LAW_INVENTORY.

Source: ai-governance-coverage.csv (Stephen, 2026-07-15). 59 rows.
Every URL points to the srjconsultingservices.com reference page for
that framework/law. Categories are derived from URL path.
"""

from __future__ import annotations

# CATEGORIES: [(category_title, [(law_name, srj_url), ...]), ...]
CATEGORIES = [
    ('International Standards & Frameworks', [
        ('ISO/IEC 42001', 'https://srjconsultingservices.com/ai-governance/iso-42001/'),
        ('ISO/IEC 22989', 'https://srjconsultingservices.com/ai-governance/iso-22989/'),
        ('NIST AI Risk Management Framework', 'https://srjconsultingservices.com/ai-governance/nist-ai-rmf/'),
    ]),
    ('EU / International', [
        ('EU AI Act', 'https://srjconsultingservices.com/ai-governance/eu-ai-act/'),
        ('EU Cyber Resilience Act', 'https://srjconsultingservices.com/ai-governance/eu-cyber-resilience-act/'),
        ('EU Product Liability Directive', 'https://srjconsultingservices.com/ai-governance/eu-product-liability/'),
        ('NIS2 Directive', 'https://srjconsultingservices.com/ai-governance/nis2/'),
        ('DORA', 'https://srjconsultingservices.com/ai-governance/dora/'),
        ('CETS 225', 'https://srjconsultingservices.com/ai-governance/coe-framework-convention/'),
    ]),
    ('Top-level Frameworks & US Federal', [
        ('NYDFS Part 500', 'https://srjconsultingservices.com/ai-governance/nydfs-part-500/'),
        ('Federal Contractor AI', 'https://srjconsultingservices.com/ai-governance/federal-contractor-ai/'),
        ('State Privacy Laws', 'https://srjconsultingservices.com/ai-governance/state-privacy-laws/'),
        ('New York City AI Laws', 'https://srjconsultingservices.com/ai-governance/nyc-ai-laws/'),
        ('State AI Laws', 'https://srjconsultingservices.com/ai-governance/state-ai-laws/'),
        ('Federal AI Legislation', 'https://srjconsultingservices.com/ai-governance/federal-ai-legislation/'),
        ('SR 11-7 and the 2026 Model Risk Guidance', 'https://srjconsultingservices.com/ai-governance/sr-11-7/'),
        ('Agency Enforcement', 'https://srjconsultingservices.com/ai-governance/agency-enforcement/'),
        ('Sector Rules', 'https://srjconsultingservices.com/ai-governance/sector-rules/'),
        ('Financial Reporting Rules for AI', 'https://srjconsultingservices.com/ai-governance/financial-reporting/'),
        ('Director Oversight', 'https://srjconsultingservices.com/ai-governance/director-oversight/'),
        ('General Business Governance', 'https://srjconsultingservices.com/ai-governance/general-business-governance/'),
        ('Vendor Disclosure', 'https://srjconsultingservices.com/ai-governance/vendor-disclosure/'),
        ('Data Management Frameworks', 'https://srjconsultingservices.com/ai-governance/data-management-frameworks/'),
    ]),
    ('US Agency Enforcement', [
        ('FTC AI Enforcement', 'https://srjconsultingservices.com/ai-governance/agency-enforcement/ftc-ai-enforcement/'),
        ('EEOC AI Enforcement', 'https://srjconsultingservices.com/ai-governance/agency-enforcement/eeoc-ai-enforcement/'),
        ('CFPB AI Enforcement', 'https://srjconsultingservices.com/ai-governance/agency-enforcement/cfpb-ai-enforcement/'),
        ('SEC AI Enforcement', 'https://srjconsultingservices.com/ai-governance/agency-enforcement/sec-ai-enforcement/'),
        ('HHS OCR AI Enforcement', 'https://srjconsultingservices.com/ai-governance/agency-enforcement/hhs-ocr-ai-enforcement/'),
    ]),
    ('State AI Laws', [
        ('Colorado AI Act', 'https://srjconsultingservices.com/ai-governance/state-ai-laws/colorado-ai-act/'),
        ('Texas Responsible AI Governance Act', 'https://srjconsultingservices.com/ai-governance/state-ai-laws/texas-ai-act/'),
        ('California AI Laws', 'https://srjconsultingservices.com/ai-governance/state-ai-laws/california-ai-laws/'),
        ('Illinois AI Laws', 'https://srjconsultingservices.com/ai-governance/state-ai-laws/illinois-ai-laws/'),
        ('Connecticut AI Act', 'https://srjconsultingservices.com/ai-governance/state-ai-laws/connecticut-ai-act/'),
        ('Tennessee ELVIS Act', 'https://srjconsultingservices.com/ai-governance/state-ai-laws/tennessee-elvis-act/'),
    ]),
    ('New York City AI Laws', [
        ('NYC Local Law 144', 'https://srjconsultingservices.com/ai-governance/nyc-ai-laws/nyc-ll-144/'),
        ('NYC Local Law 35', 'https://srjconsultingservices.com/ai-governance/nyc-ai-laws/nyc-ll-35/'),
    ]),
    ('Sector Rules (HIPAA, GDPR, FCRA, etc.)', [
        ('HIPAA and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/hipaa-ai/'),
        ('COPPA and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/coppa-ai/'),
        ('GDPR and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/gdpr-ai/'),
        ('GLBA and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/glba-ai/'),
        ('FCRA and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/fcra-ai/'),
        ('ECOA and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/ecoa-ai/'),
        ('Title VII and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/title-vii-ai/'),
        ('WARN Act and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/warn-ai/'),
        ('FERPA and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/ferpa-ai/'),
        ('FINRA and AI', 'https://srjconsultingservices.com/ai-governance/sector-rules/finra-ai/'),
    ]),
    ('Financial Reporting for AI', [
        ('FASB ASU 2025-06', 'https://srjconsultingservices.com/ai-governance/financial-reporting/fasb-asu-2025-06/'),
        ('AICPA AI Guidance', 'https://srjconsultingservices.com/ai-governance/financial-reporting/aicpa-ai-guidance/'),
        ('PCAOB AI Guidance', 'https://srjconsultingservices.com/ai-governance/financial-reporting/pcaob-ai-guidance/'),
        ('SOX 302 and 404 for AI', 'https://srjconsultingservices.com/ai-governance/financial-reporting/sox-302-404-ai/'),
    ]),
    ('General Business Governance (ISO, SOC 2, NIST CSF, COSO)', [
        ('ISO 27001 and AI', 'https://srjconsultingservices.com/ai-governance/general-business-governance/iso-27001-ai/'),
        ('SOC 2 and AI', 'https://srjconsultingservices.com/ai-governance/general-business-governance/soc-2-ai/'),
        ('NIST Cybersecurity Framework and AI', 'https://srjconsultingservices.com/ai-governance/general-business-governance/nist-csf-ai/'),
        ('COSO ERM and AI', 'https://srjconsultingservices.com/ai-governance/general-business-governance/coso-erm-ai/'),
    ]),
    ('Vendor Disclosure (SBOM / AIBOM)', [
        ('Software Bill of Materials', 'https://srjconsultingservices.com/ai-governance/vendor-disclosure/sbom/'),
        ('AI Bill of Materials', 'https://srjconsultingservices.com/ai-governance/vendor-disclosure/aibom/'),
    ]),
    ('Data Management Frameworks', [
        ('DAMA-DMBOK', 'https://srjconsultingservices.com/ai-governance/data-management-frameworks/dama-dmbok/'),
        ('EDM Council DCAM', 'https://srjconsultingservices.com/ai-governance/data-management-frameworks/dcam/'),
        ('CDMC Cloud Data Management', 'https://srjconsultingservices.com/ai-governance/data-management-frameworks/cdmc/'),
    ]),
]

# Flat list of law names in canonical rendering order — feeds T1-A-006
# `options` list at DB-load time.
LAWS_FLAT = [name for _, items in CATEGORIES for name, _ in items]
