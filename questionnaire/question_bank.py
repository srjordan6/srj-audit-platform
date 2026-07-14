"""
Tier 1 question bank for SRJ AI Audit Platform.

Generated from production database 2026-06-28.
Source: srj-audit-db (Render Ohio) — table public.questions where tier='tier_1' and is_active=true.

Total: 136 questions across 8 sections.
  Section A — Context & Identity:                    15 questions
  Section B — AI Tool Inventory & Discovery:         21 questions
  Section C — Cost Mapping:                          13 questions
  Section D — Performance Measurement:               15 questions
  Section E — Risk Exposure:                         30 questions
  Section F — Governance Gaps:                       28 questions
  Section G — Outcomes, Workflow & Confidence:       11 questions
  Section H — Follow-up:                              3 questions

Schema columns match public.questions: id, tier, section, sequence_number,
question_text, question_type, options, matrix_rows, matrix_columns, skip_logic,
role_visibility, required, scoring_weight, framework_mappings, notes, is_active,
scoring_overrides, extended_metadata.

Framework mapping conventions:
  - v1_audit dimensions (5 canonical): tool_inventory, cost_mapping,
    performance_measurement, risk_exposure, governance_gaps
  - v2_readiness modules: leadership_accountability, workflow_readiness,
    operational_friction, people_readiness, performance_measurement
  - v3_governance steps (6 canonical): accountability_mapping,
    data_exposure_assessment, decision_influence_review,
    framework_crosswalk_readiness, incident_response_readiness,
    vendor_risk_inventory
  - efficiency sub_components: outcome_alignment, process_optimization
  - context (weight=0): respondent/company metadata only
  - lead_gen (weight=0): follow-up routing only
  - cross_cutting_signal: feeds report attention flags, not step scores
"""

from decimal import Decimal


TIER_1_QUESTIONS = [

    # ===== Section A — Context & Identity (15 questions + tool inventory) =====

    # T1-A-000 — TOOL INVENTORY. Renders first (sequence_number 0).
    # Captures which AI tools the company uses; downstream questions
    # (starting with T1-B-017 "top 3 tools by spend") pre-fill from this
    # answer. Options field carries the flat list for legacy scoring;
    # the categorized rendering is driven by questionnaire.tool_catalog
    # via services._decorate_question at render time.
    {
        "id": 'T1-A-000',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 0,
        "question_text": "Which AI tools does your company currently use? Check every tool anyone at the company uses.",
        "question_type": 'TOOL_INVENTORY',
        "options": [],  # Filled from tool_catalog at render time.
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": False,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'framework': 'context',
                'sub_component': 'tool_inventory_seed'
            }
        ],
        "notes": "Seeds the audit tool inventory; downstream questions filter to this set.",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'renders_categorized': True,
            'allows_other_free_text': True,
        },
    },
    {
        "id": 'T1-A-001',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 1,
        "question_text": 'Your role in the company',
        "question_type": 'SS',
        "options": [
            'Board Member',
            'CEO or Owner',
            'CFO',
            'CIO',
            'CISO',
            'COO',
            'VP',
            'Director',
            'Line Manager',
            'Individual Contributor',
            'Other'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'respondent_role',
                'framework': 'context'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-002',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 2,
        "question_text": 'How long have you been in this role?',
        "question_type": 'SS',
        "options": ['Under 1 year', '1-3 years', '3-7 years', '7+ years'],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'respondent_tenure',
                'framework': 'context'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        # DEACTIVATED 2026-07-14 — company size is already captured on
        # the start form as `company_size_bracket`. Kept in the bank as
        # historical context; is_active=False skips it during rendering.
        "id": 'T1-A-003',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 3,
        "question_text": 'Company size (employees, including part-time)',
        "question_type": 'SS',
        "options": [
            '1-25', '26-100', '101-500', '501-2,000', '2,001-5,000', '5,000+',
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": False,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {'weight': 0, 'dimension': 'company_size', 'framework': 'context'}
        ],
        "notes": "Redundant with start-form company_size_bracket; deactivated 2026-07-14.",
        "is_active": False,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        # DEACTIVATED 2026-07-14 — replaced by T1-A-015 (NAICS sector
        # dropdown) + T1-A-016 (subsegment). Kept in the bank for history.
        "id": 'T1-A-004',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 4,
        "question_text": 'Primary industry',
        "question_type": 'SS',
        "options": [
            'Professional Services', 'Financial Services', 'Healthcare',
            'Manufacturing', 'Retail/Ecommerce', 'Technology/Software',
            'Construction', 'Education', 'Government/Public Sector',
            'Nonprofit', 'Real Estate', 'Hospitality',
            'Transportation/Logistics', 'Other',
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": False,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {'weight': 0, 'dimension': 'industry', 'framework': 'context'}
        ],
        "notes": "Replaced by T1-A-015 (NAICS sector) + T1-A-016 (subsegment); deactivated 2026-07-14.",
        "is_active": False,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-005',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 5,
        "question_text": 'Geographic operating footprint',
        "question_type": 'SS',
        "options": [
            'Single state, US',
            'Multi-state, US',
            'North America',
            'Global',
            'Other'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'geographic_scope',
                'framework': 'context'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-006',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 6,
        "question_text": 'Regulations and laws with legal or supervisory force that apply to your company. This question covers laws and regulator-enforced rules only. Voluntary standards, governance frameworks, and contractual expectations are covered in the next three questions.',
        "question_type": 'MS',
        "options": [
            'HIPAA (and HHS OCR enforcement)',
            'GLBA',
            'FERPA (education)',
            'DFARS',
            'FedRAMP',
            'SR 11-7 (Fed banking model risk)',
            'OCC 2013-29 (OCC banking model risk)',
            'NYDFS Part 500',
            'FINRA',
            'FTC enforcement (Section 5, algorithmic disclosure)',
            'EEOC enforcement (employment AI)',
            'CFPB enforcement (consumer finance AI)',
            'SEC enforcement (AI disclosures, AI-washing)',
            'NYC Local Law 144 (AEDT)',
            'Colorado AI Act',
            'Texas TRAIGA',
            'California ADMT',
            'Illinois HB3773',
            'State employment AI laws beyond NYC LL144, CO, IL',
            'State financial AI rules beyond NYDFS',
            'Sectoral examiner guidance not yet rule-issued',
            'State privacy law (CCPA and similar)',
            'EU AI Act',
            'GDPR (DPIAs for AI processing)',
            'DORA (Digital Operational Resilience Act)',
            'NIS2 (Network and Information Security Directive 2)',
            'EU Revised Product Liability Directive (2024/2853)',
            'Council of Europe Framework Convention on AI (CETS 225)',
            'Industry-specific rules (specify)',
            'None',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'regulatory_environment',
                'framework': 'context'
            },
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2 expansion: added Colorado AI Act, Texas TRAIGA, California ADMT per SRJ_Tier_1_New_Questions_Revision_v1_20260623.md | 2026-06-28: Expanded for 30-framework evidence package architecture (OD-14). Scope tightened to regulations only; SOC 2/ISO 42001/NIST AI RMF moved to T1-A-011 voluntary standards. | 2026-06-28: Added 3 options per OD-14 gap audit. Now 27 options.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-007',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 7,
        "question_text": 'Approximate annual revenue',
        "question_type": 'NR',
        "options": [
            'Under $5M',
            '$5-25M',
            '$25-100M',
            '$100M-$1B',
            'Over $1B',
            'Decline to answer'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'revenue_bracket',
                'framework': 'context'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-008',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 8,
        "question_text": 'How long has your company been using any AI tools?',
        "question_type": 'SS',
        "options": [
            'Under 6 months',
            '6-12 months',
            '1-2 years',
            '2-5 years',
            '5+ years',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'ai_adoption_history',
                'framework': 'context'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-009',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 9,
        "question_text": 'Was your AI adoption strategy formally approved by leadership before tools were deployed?',
        "question_type": 'SS',
        "options": ['Yes — fully', 'Yes — partially', 'No', "I'm not sure"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'approval_discipline'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-010',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 10,
        "question_text": 'Why are you completing this assessment? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Board requested',
            'Acquirer due diligence',
            'Regulatory preparation',
            'Insurance renewal',
            'Internal initiative',
            'Vendor evaluation',
            'Consultant recommendation',
            'Personal curiosity',
            'Other'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'intent',
                'framework': 'context'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-011',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 11,
        "question_text": 'Voluntary AI, data, and security standards your company aligns with or claims compliance to. Includes standards required by customer contracts or insurance policies.',
        "question_type": 'MS',
        "options": [
            'ISO 42001 (AI management system)',
            'NIST AI RMF (AI Risk Management Framework)',
            'ISO/IEC 22989 (AI terminology reference)',
            'NIST CSF (Cybersecurity Framework)',
            'ISO 27001 (Information security management)',
            'SOC 2',
            'COSO ERM (Enterprise Risk Management)',
            'DAMA-DMBOK (Data Management Body of Knowledge)',
            'DCAM (Data Management Capability Assessment Model)',
            'CDMC (Cloud Data Management Capabilities)',
            'Other (specify)',
            'None of these',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'voluntary_standards',
                'framework': 'context'
            },
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW question added for 30-framework evidence package architecture (OD-14). Separates voluntary standards from regulations (T1-A-006), governance frameworks (T1-A-012), and contractual expectations (T1-A-013).',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-012',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 12,
        "question_text": "Governance and fiduciary frameworks that bear on your board's or executive team's AI oversight obligations.",
        "question_type": 'MS',
        "options": [
            'Caremark fiduciary duty (Delaware caselaw on board oversight)',
            'NACD AI governance guidance',
            'ISS AI governance guidance (proxy advisor)',
            'Glass Lewis AI governance guidance (proxy advisor)',
            'SEC AI-related disclosure expectations (10-K risk factors, proxy)',
            'Audit committee AI oversight expectations',
            'Other (specify)',
            'None of these',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'CFO',
            'COO',
            'CIO',
            'CISO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'governance_frameworks',
                'framework': 'context'
            },
            {
                'step': 'accountability_mapping',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW question added for 30-framework evidence package architecture (OD-14). Captures board-level fiduciary frameworks distinct from regulations. Role-gated to senior leadership.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-013',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 13,
        "question_text": 'Contractual and supply chain expectations that require AI-related evidence from your company.',
        "question_type": 'MS',
        "options": [
            'Customer contract AI clauses (riders, addenda)',
            'Insurance underwriting AI requirements',
            'Cyber insurance AI underwriting questionnaires',
            'M&A due diligence AI questions',
            'SBOM/AIBOM (software/AI bill of materials) contractual expectations',
            'DTSA reasonable measures (trade secret protection)',
            'Vendor security assessment AI requirements (enterprise customer questionnaires)',
            'Other (specify)',
            'None of these',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'CFO',
            'COO',
            'CIO',
            'CISO',
            'VP',
            'DIR'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'contractual_expectations',
                'framework': 'context'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW question added for 30-framework evidence package architecture (OD-14). Captures contractual sources of AI evidence obligations distinct from regulations and voluntary standards. | 2026-06-28: Added cyber insurance AI underwriting questionnaires per OD-14.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-014',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 14,
        "question_text": 'Across the regulatory, voluntary, governance, and contractual items you selected in the previous four questions, what is the dominant cadence at which your company must produce evidence?',
        "question_type": 'SS',
        "options": [
            'All scheduled (annual or periodic reports due)',
            'Mostly on-demand (produce when an examiner, customer, broker, acquirer, or plaintiff asks)',
            'Mostly event-driven (only when an incident, regulatory inquiry, or litigation occurs)',
            'Mix of scheduled and on-demand',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'CFO',
            'COO',
            'CIO',
            'CISO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'dimension': 'evidence_cadence',
                'framework': 'context'
            },
            {
                'step': 'incident_response_readiness',
                'weight': 0.5,
                'framework': 'v3_governance'
            },
            {
                'weight': 0.5,
                'dimension': 'governance',
                'framework': 'v1_audit'
            }
        ],
        "notes": '2026-06-28: NEW question added for 30-framework evidence package architecture (OD-14). Diagnostic: customers who misidentify cadence (e.g., believing Caremark is scheduled annually) are surfaced as governance gap.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-A-015',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 15,
        "question_text": "Which NAICS sector best describes your company's primary line of business?",
        "question_type": 'SS',
        "options": [
            '11 — Agriculture, Forestry, Fishing and Hunting',
            '21 — Mining, Quarrying, and Oil and Gas Extraction',
            '22 — Utilities',
            '23 — Construction',
            '31-33 — Manufacturing',
            '42 — Wholesale Trade',
            '44-45 — Retail Trade',
            '48-49 — Transportation and Warehousing',
            '51 — Information',
            '52 — Finance and Insurance',
            '53 — Real Estate and Rental and Leasing',
            '54 — Professional, Scientific, and Technical Services',
            '55 — Management of Companies and Enterprises',
            '56 — Administrative, Support, Waste Management and Remediation',
            '61 — Educational Services',
            '62 — Health Care and Social Assistance',
            '71 — Arts, Entertainment, and Recreation',
            '72 — Accommodation and Food Services',
            '81 — Other Services (except Public Administration)',
            '92 — Public Administration',
            'Other',
            "Don't know",
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {'weight': 0, 'dimension': 'naics_sector', 'framework': 'context'},
            {'step': 'framework_crosswalk_readiness', 'weight': 0.5, 'framework': 'v3_governance'}
        ],
        "notes": '2026-07-14: converted from free-form industry to NAICS 2-digit sector dropdown per operator request. Enables correct scoping of sector-specific evidence packages.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'other_text_field': True,
            'source': 'NAICS 2-digit sector, US Census Bureau',
        },
    },
    {
        # T1-A-016 — Sub-segment refinement inside the T1-A-015 NAICS sector.
        # Added 2026-07-14 alongside the T1-A-015 conversion.
        "id": 'T1-A-016',
        "tier": 'tier_1',
        "section": 'A',
        "sequence_number": 16,
        "question_text": "Which sub-segment best describes your company's regulated AI exposure? Choose the option closest to your business, or 'Not applicable' if none apply.",
        "question_type": 'SS',
        "options": [
            'Healthcare: Provider',
            'Healthcare: Payer',
            'Healthcare: Pharma / Medical Device',
            'Healthcare: Health IT vendor',
            'Healthcare: Other',
            'Financial: Bank or credit union',
            'Financial: Broker-dealer',
            'Financial: Investment adviser',
            'Financial: Non-bank lender',
            'Financial: Insurer',
            'Financial: Fintech',
            'Financial: Other',
            'Education: K-12',
            'Education: Higher education',
            'Education: Ed-tech vendor',
            'Education: Other',
            'Government: Federal',
            'Government: State',
            'Government: Local',
            'Government: Defense contractor',
            'Government: Other',
            'Other (specify)',
            'Not applicable to my sector',
            "Don't know",
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": False,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {'weight': 0, 'framework': 'context', 'sub_component': 'regulated_subsegment'}
        ],
        "notes": "Sub-segment refinement inside the T1-A-015 NAICS sector.",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'other_text_field': True,
            'depends_on': 'T1-A-015',
        },
    },

    # ===== Section B — AI Tool Inventory & Discovery (21 questions) =====

    {
        "id": 'T1-B-001',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 1,
        "question_text": 'Does a single document exist that lists every AI tool currently in active use across the company?',
        "question_type": 'SS',
        "options": [
            'Yes — comprehensive and current',
            'Yes — partial or outdated',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'inventory_existence'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-002',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 2,
        "question_text": 'What does that inventory include? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Tool name',
            'Owner',
            'Cost',
            'Purpose',
            'Data accessed',
            'Vendor',
            'Date adopted',
            'Approval status',
            'Performance metric',
            'Review cadence',
            'Contract terms',
            'Risk classification',
            'Vendor-enabled AI features',
            'Other (specify)',
            'None of these'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-B-001',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'inventory_completeness'
            }
        ],
        "notes": "v1.2: added 'Vendor-enabled AI features' checkbox to absorb eliminated T1-B-020",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-003',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 3,
        "question_text": 'When was the inventory last updated?',
        "question_type": 'SS',
        "options": [
            'Within 30 days',
            '30-90 days ago',
            '90 days to 6 months ago',
            'Over 6 months ago',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-B-001',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'inventory_currency'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-004',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 4,
        "question_text": 'Who maintains the inventory?',
        "question_type": 'SS',
        "options": [
            'Named individual',
            'Committee or team',
            'External consultant',
            'No clear owner',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-B-001',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'inventory_ownership'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-005',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 5,
        "question_text": 'Has anyone attempted to create an AI tool inventory?',
        "question_type": 'SS',
        "options": ['Yes — abandoned', 'Yes — in progress', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-B-001',
                    'answer_value': ['Yes — comprehensive and current', 'Yes — partial or outdated']
                }
            ]
        },
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'inventory_attempted'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-006',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 6,
        "question_text": "Why hasn't an inventory been built? (select all that apply)",
        "question_type": 'MS',
        "options": [
            'No one assigned',
            'Not seen as priority',
            'Too complex',
            'Political resistance',
            "Don't know what to include",
            'Already exists in other documents',
            'Other'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-B-001',
                    'answer_value': ['Yes — comprehensive and current', 'Yes — partial or outdated']
                }
            ]
        },
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'barriers'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-007',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 7,
        "question_text": 'If a regulator or acquirer asked for a complete AI tool inventory today, how long would it take to produce?',
        "question_type": 'SS',
        "options": [
            'Same day',
            '1-3 days',
            'About a week',
            'Over a week',
            'Impossible currently',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'external_readiness'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-008',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 8,
        "question_text": 'Have you been asked for an AI tool inventory in the past 3 months by anyone external (auditor, insurer, customer, board)?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'external_pressure'
            }
        ],
        "notes": 'v1.2: time horizon standardized to past 3 months per audit Decision 4. Watch-item (pilot watch list entry #1): 3-month window may miss companies whose last inventory request was 6 months ago',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-009',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 9,
        "question_text": 'How many AI tools does leadership believe are in use across the company?',
        "question_type": 'NR',
        "options": [
            '0',
            '1-3',
            '4-10',
            '11-25',
            '26-50',
            '51-100',
            '100+',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'leadership_tool_count'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-010',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 10,
        "question_text": 'How confident is that number?',
        "question_type": 'SS',
        "options": [
            'Very confident',
            'Somewhat confident',
            'Not very confident',
            'Guessing',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'leadership_confidence'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-011',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 11,
        "question_text": 'How many AI tools do you personally use for work tasks?',
        "question_type": 'NR',
        "options": [
            'None',
            '1-2',
            '3-5',
            '6-10',
            'More than 10',
            'Prefer not to say'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['IC', 'MGR'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'ic_tool_count'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-013',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 13,
        "question_text": 'Have you ever used a personal account, free tool, or browser extension with AI features for work tasks?',
        "question_type": 'YN',
        "options": [
            'Yes — regularly',
            'Yes — occasionally',
            'No',
            "I'm not sure",
            'Decline to answer'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['IC', 'MGR'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'shadow_ai'
            }
        ],
        "notes": 'v1.2: T1-B-012 was eliminated (overlapped with B-013); B-013 retained as the governance-relevant shadow AI signal',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-014',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 14,
        "question_text": 'Have any AI tools been adopted at the team or department level without central IT or leadership approval?',
        "question_type": 'SS',
        "options": ['Yes — frequently', 'Yes — occasionally', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO',
            'VP',
            'DIR'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'shadow_adoption'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-015',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 15,
        "question_text": 'To what extent has the company identified vendor-enabled AI features in its existing software stack (in the past 3 months)?',
        "question_type": 'SS',
        "options": [
            'Aware and have a complete list',
            'Aware and have a partial list',
            'Suspected but not inventoried',
            'Not aware of any',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'vendor_enabled_awareness'
            }
        ],
        "notes": 'v1.2: T1-B-015 (revised) absorbs eliminated T1-B-018; consolidates vendor-enabled AI awareness and inventory rigor into one five-option scale',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-016',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 16,
        "question_text": 'Has the company conducted endpoint or network discovery to identify AI tool usage?',
        "question_type": 'SS',
        "options": ['Yes — recently', 'Yes — over 12 months ago', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'discovery_discipline'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-017',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 17,
        "question_text": 'For the top 3 AI tools by spend or strategic importance in your company, indicate which of the following apply:',
        "question_type": 'MATRIX',
        "options": None,
        "matrix_rows": ['Tool 1', 'Tool 2', 'Tool 3'],
        "matrix_columns": [
            'The tool has a documented business purpose',
            'The tool has a named owner accountable for outcomes',
            "The tool's cost is documented",
            "The tool's performance is measured against a defined outcome",
            'Someone can describe what data the tool accesses',
            "The vendor's data-handling terms have been reviewed in the past 12 months",
            'The tool was approved through a formal process before deployment',
            "The tool's continued use has been justified in the past 12 months",
            'An AI/Software bill of materials is documented for this tool',
            'Vendor flow-down clauses match downstream regulatory requirements (BAA, GLBA, DTSA, CMMC)'
        ],
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'per_tool_detail'
            }
        ],
        "notes": 'Respondent first names 3 tools, then answers yes/no/dontknow on each of 8 attributes per tool. 24 data points internally. | 2026-06-28: Added 2 columns for SBOM/AIBOM and vendor flow-down evidence (OD-14).',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'matrix_cell_options': ['Yes', 'No', "Don't know"]
        },
    },
    {
        "id": 'T1-B-019',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 19,
        "question_text": 'Which categories of vendor-enabled AI features are confirmed active in your environment? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'CRM AI',
            'Email & calendar AI',
            'Accounting/finance AI',
            'HR/payroll AI',
            'Helpdesk AI',
            'Collaboration platform AI',
            'Contract management AI',
            'Project management AI',
            'Cybersecurity AI',
            'Marketing automation AI',
            'Document management AI',
            'Other (specify)',
            'None confirmed',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'vendor_enabled_categories'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-021',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 21,
        "question_text": 'How many AI tools have been added in the past 3 months?',
        "question_type": 'NR',
        "options": [
            '0',
            '1-3',
            '4-10',
            '11-25',
            '25+',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'additions_velocity'
            }
        ],
        "notes": 'v1.2: time horizon standardized to past 3 months',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-022',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 22,
        "question_text": 'How many AI tools have been retired in the past 3 months?',
        "question_type": 'NR',
        "options": [
            '0',
            '1-3',
            '4-10',
            '11+',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'retirements_discipline'
            }
        ],
        "notes": 'v1.2: time horizon standardized to past 3 months',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-023',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 23,
        "question_text": 'Were any tools retired because they failed to deliver value, or because of risk/compliance concerns?',
        "question_type": 'YN',
        "options": [
            'Yes — value',
            'Yes — risk/compliance',
            'Yes — both',
            'No tools retired',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'kill_discipline'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-B-024',
        "tier": 'tier_1',
        "section": 'B',
        "sequence_number": 24,
        "question_text": 'Is there a defined approval process required before a new AI tool is adopted?',
        "question_type": 'SS',
        "options": [
            'Yes — required and consistently followed',
            'Yes — exists but inconsistent',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'tool_inventory',
                'framework': 'v1_audit',
                'sub_component': 'approval_process'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },

    # ===== Section C — Cost Mapping (13 questions) =====

    {
        "id": 'T1-C-002',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 2,
        "question_text": 'What does that spend report include? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Subscriptions',
            'Per-seat licenses',
            'API/usage charges',
            'Professional services',
            'Hardware',
            'Training costs',
            'Consulting',
            'Vendor-enabled feature upgrades',
            'Other (specify)',
            'None of these'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-C-006',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'spend_report_completeness'
            }
        ],
        "notes": 'v1.2: T1-C-001 eliminated (overlapped with C-006); skip logic redirected to C-006 reference',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-003',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 3,
        "question_text": 'Total monthly AI spend, all sources combined',
        "question_type": 'NR',
        "options": [
            '$0',
            'Under $500',
            '$500-$2,500',
            '$2,500-$10,000',
            '$10,000-$50,000',
            '$50,000-$250,000',
            '$250,000+',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'total_spend'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-004',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 4,
        "question_text": 'How confident is that number?',
        "question_type": 'SS',
        "options": ['Very confident', 'Somewhat', 'Guessing', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0.5,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'spend_confidence'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-005',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 5,
        "question_text": 'Have any AI charges appeared on company cards in the past 3 months that no one initially could identify?',
        "question_type": 'YN',
        "options": ['Yes — multiple times', 'Yes — once', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'CIO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'shadow_spend'
            }
        ],
        "notes": 'v1.2: time horizon standardized to past 3 months',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-006',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 6,
        "question_text": 'Is AI spend tracked as a distinct budget line in financial reporting?',
        "question_type": 'SS',
        "options": [
            'Yes — at company level',
            'Yes — at department level',
            'Partial',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'budget_line_discipline'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-007',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 7,
        "question_text": 'Which of the following hidden AI costs has the company quantified or documented (in the past 3 months)? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Time spent correcting AI output errors',
            'Time spent on AI tools that overlap or duplicate function',
            'Customizations or integrations not in original cost projections',
            'Training and skill-up costs beyond initial onboarding',
            'Vendor lock-in or switching costs',
            'Other (specify)',
            'None of the above',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'hidden_cost_awareness'
            }
        ],
        "notes": 'v1.2: T1-C-007 (revised) absorbs eliminated T1-C-008 and T1-C-009. Two new categories added (training, switching). Per-checkbox scoring in scoring engine.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-010',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 10,
        "question_text": 'In a typical week, how much time do you estimate is spent reviewing or fixing AI outputs?',
        "question_type": 'SS',
        "options": [
            'Under 30 minutes',
            '30 minutes to 2 hours',
            '2-5 hours',
            'Over 5 hours',
            "I don't track this"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['MGR', 'IC'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'ic_error_correction_time'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-011',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 11,
        "question_text": 'What multiple of subscription cost do you estimate hidden costs (time, errors, training, integration) add?',
        "question_type": 'NR',
        "options": [
            '1x (subscription = total cost)',
            '1.5x',
            '2x',
            '3x or more',
            "Haven't measured",
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_only_includes',
                    'question_id': 'T1-C-007',
                    'answer_value': ['None of the above', "Don't know"]
                }
            ]
        },
        "role_visibility": ['CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'hidden_cost_multiplier'
            }
        ],
        "notes": "v1.2: skip logic added per audit Section 6.1 — skip if C-007 returned only 'None of the above' or 'Don't know'",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-012',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 12,
        "question_text": 'Are AI vendor contracts centrally tracked?',
        "question_type": 'SS',
        "options": ['Yes — comprehensive', 'Partial', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CFO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'contract_tracking'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-013',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 13,
        "question_text": 'Have you reviewed exit costs or switching costs for any AI vendors?',
        "question_type": 'YN',
        "options": ['Yes — comprehensive', 'Yes — for some vendors', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CFO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'exit_cost_awareness'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-014',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 14,
        "question_text": 'Do AI contracts include usage-based pricing components that could escalate?',
        "question_type": 'YN',
        "options": ['Yes — monitored', 'Yes — unmonitored', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CFO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'usage_pricing_awareness'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-015',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 15,
        "question_text": 'Has anyone calculated the ROI of any AI tool in the past 3 months?',
        "question_type": 'SS',
        "options": ['Yes — rigorous', 'Yes — informal estimate', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'roi_discipline'
            }
        ],
        "notes": "v1.2: time horizon standardized to past 3 months. Watch-item (pilot watch list entry #4): ROI exercises are typically annual or semi-annual; 3-month window may consistently return 'No' from companies that do this work annually.",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-C-016',
        "tier": 'tier_1',
        "section": 'C',
        "sequence_number": 16,
        "question_text": 'If asked by the board today, could you defend every dollar of AI spend?',
        "question_type": 'SS',
        "options": [
            'Yes — fully',
            'Mostly',
            'Partially',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'cost_mapping',
                'framework': 'v1_audit',
                'sub_component': 'board_defensibility'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },

    # ===== Section D — Performance Measurement (15 questions) =====

    {
        "id": 'T1-D-001',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 1,
        "question_text": "For the company's top 3 AI use cases by spend or strategic importance, indicate which apply (past 3 months):",
        "question_type": 'MATRIX',
        "options": None,
        "matrix_rows": ['Use case 1', 'Use case 2', 'Use case 3'],
        "matrix_columns": [
            'Success metrics are defined',
            'Metrics are tied to specific business outcomes',
            'Baseline measurements from before AI deployment exist',
            'Performance is reviewed on a defined cadence',
            'AI artifact registry exists (model card, training data lineage, evaluation results, version history)',
            'Documented risk owner is accountable for this use case'
        ],
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'per_use_case_metric_existence'
            },
            {
                'module': 'performance_measurement',
                'weight': 1.0,
                'framework': 'v2_readiness'
            }
        ],
        "notes": 'v1.2: revised matrix absorbs eliminated D-002, D-003, D-004. Produces 12 data points internally (3 use cases × 4 columns). UX pattern follows existing T1-B-017 matrix. | 2026-06-28: Added 2 columns for EU AI Act Annex IV/SR 11-7/NIST AI RMF documentation + COSO ERM risk ownership (OD-14).',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'matrix_cell_options': ['Yes', 'No', "Don't know"],
            'matrix_row_input_type': 'respondent_provides_name'
        },
    },
    {
        "id": 'T1-D-005',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 5,
        "question_text": 'Who reviews AI performance metrics?',
        "question_type": 'SS',
        "options": [
            'Executive team',
            'Functional leaders',
            'Individual tool owners',
            'No one consistently',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'review_accountability'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-007',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 7,
        "question_text": 'Has any AI tool been continued despite consistently missing its target metric?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know", 'No targets exist'],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'continuation_discipline'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-008',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 8,
        "question_text": 'Has any AI tool been killed because it missed its target metric?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'kill_discipline'
            }
        ],
        "notes": 'v1.2: T1-G-003 eliminated (was functionally identical to D-008); D-008 retained as canonical kill-discipline signal',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-009',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 9,
        "question_text": 'How often do you encounter AI outputs that are confidently wrong?',
        "question_type": 'SS',
        "options": [
            'Daily',
            'Weekly',
            'Monthly',
            'Rarely',
            'Never',
            "I don't use AI tools"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['MGR', 'IC', 'DIR'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'ic_error_frequency'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-010',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 10,
        "question_text": 'How often are AI errors caught before reaching customers or final decisions?',
        "question_type": 'SS',
        "options": [
            'Always',
            'Usually',
            'Sometimes',
            'Rarely',
            'Never',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'error_containment'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-011',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 11,
        "question_text": 'Is there a defined review process for high-stakes AI outputs (customer communications, financial decisions, hiring)?',
        "question_type": 'SS',
        "options": ['Yes — documented', 'Yes — informal', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'high_stakes_review_process'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-012',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 12,
        "question_text": 'Has any AI error reached a customer or external party in the past 3 months?',
        "question_type": 'YN',
        "options": ['Yes — multiple', 'Yes — once', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO',
            'VP',
            'DIR',
            'BOARD'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'external_error_incidents'
            }
        ],
        "notes": 'v1.2: time horizon standardized to past 3 months',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-013',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 13,
        "question_text": 'Has any AI error been disclosed to a regulator or auditor?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'regulatory_disclosure'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-014',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 14,
        "question_text": 'How much do you trust the AI outputs in your day-to-day workflow?',
        "question_type": 'L5',
        "options": [
            '1 (not at all)',
            '2',
            '3',
            '4',
            '5 (strongly trust)'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['MGR', 'IC'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'ic_trust_likert'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-015',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 15,
        "question_text": 'Have any AI tools been benchmarked against alternatives?',
        "question_type": 'YN',
        "options": ['Yes — formal', 'Yes — informal', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'benchmarking_discipline'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-016',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 16,
        "question_text": 'Has AI performance been compared against pre-AI process baselines?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'baseline_comparison'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-017',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 17,
        "question_text": 'Are AI tool vendors required to provide performance data?',
        "question_type": 'YN',
        "options": ['Yes — always', 'Sometimes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO', 'CIO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'vendor_performance_data'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-018',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 18,
        "question_text": 'Have you measured customer or employee satisfaction with AI-touched processes?',
        "question_type": 'YN',
        "options": [
            'Yes — both',
            'Customers only',
            'Employees only',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'stakeholder_satisfaction'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-D-019',
        "tier": 'tier_1',
        "section": 'D',
        "sequence_number": 19,
        "question_text": 'For AI systems involved in hiring, promotion, lending, credit, or other regulated decisions, has a documented bias audit or fair lending review been conducted in the past 12 months?',
        "question_type": 'SS',
        "options": [
            'Yes — independent third-party audit',
            'Yes — internal review',
            'Yes — vendor-provided',
            'No — but planned',
            'No',
            'N/A — no regulated-decision AI',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'COO',
            'HR',
            'CIO',
            'CISO',
            'BOARD'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'bias_audit_discipline_documented'
            },
            {
                'step': 'decision_influence_review',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW per OD-14 gap audit. Primary evidence for EEOC, CFPB; supports NYC LL144 (E-024), Colorado AI Act, California ADMT, FINRA bias-for-recommendations.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },

    # ===== Section E — Risk Exposure (30 questions) =====

    {
        "id": 'T1-E-001',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 1,
        "question_text": 'Has sensitive company information been entered into any external AI tool?',
        "question_type": 'SS',
        "options": ['Yes — known', 'Suspected', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO', 'CEO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'data_exposure_existence'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-002',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 2,
        "question_text": 'What categories of sensitive information? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Customer PII',
            'Employee PII',
            'PHI (health information)',
            'Financial',
            'Contracts',
            'Intellectual property',
            'Strategic plans',
            'Source code',
            'Credentials/passwords',
            'Litigation-related',
            'Other'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-E-001',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['CIO', 'CISO', 'CEO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'data_exposure_categories'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-003',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 3,
        "question_text": 'Have AI vendor data-handling terms been reviewed by legal counsel?',
        "question_type": 'YN',
        "options": ['Yes — all', 'Some', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CISO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'legal_review_discipline'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 0.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-004',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 4,
        "question_text": 'Have any AI tools been confirmed to retain or train on submitted data?',
        "question_type": 'YN',
        "options": ['Yes — confirmed', 'Suspected', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CISO', 'CIO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'data_retention_awareness'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-005',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 5,
        "question_text": 'Have data subjects (customers, employees) been notified about AI processing where required by law?',
        "question_type": 'YN',
        "options": ['Yes', 'No', 'N/A', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CISO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'notification_compliance'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 0.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-006',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 6,
        "question_text": 'Have you mapped which AI tools touch regulated data?',
        "question_type": 'YN',
        "options": ['Yes — complete', 'Partial', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'regulated_data_mapping'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-007',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 7,
        "question_text": 'Is there a documented data classification policy in place?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'data_classification_policy'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 0.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-008',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 8,
        "question_text": 'Are AI tools constrained by data classification?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-E-007',
                    'answer_value': ['No']
                }
            ]
        },
        "role_visibility": ['CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'data_classification_enforcement'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 0.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-009',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 9,
        "question_text": 'Has AI been involved in any of the following high-stakes decisions or outputs in the past 3 months? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Hiring, firing, or promotion decisions',
            'Pricing, lending, or credit decisions',
            'Legal filings or contracts',
            'Regulatory submissions or filings',
            'Financial reporting or audit documentation',
            'Court filings or litigation-related documents',
            'Other (specify)',
            'None of the above',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO',
            'HR',
            'BOARD'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'high_stakes_use_categories'
            },
            {
                'step': 'decision_influence_review',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2: revised multi-select absorbs eliminated E-010, E-013, E-016. Per-checkbox scoring; presence of any high-stakes category counts as primary risk signal. Time horizon tightened to past 3 months.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-011',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 11,
        "question_text": 'Is any AI tool generating customer-facing communications without human review?',
        "question_type": 'SS',
        "options": ['Yes — routinely', 'Sometimes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'COO', 'VP', 'DIR'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'unreviewed_external_output'
            },
            {
                'step': 'decision_influence_review',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-012',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 12,
        "question_text": 'Are AI tools generating content that could be misattributed to a human?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'attribution_risk'
            },
            {
                'step': 'decision_influence_review',
                'weight': 0.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-014',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 14,
        "question_text": 'Has any AI-produced content been published or sent externally without disclosure?',
        "question_type": 'YN',
        "options": ['Yes — known', 'Suspected', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'undisclosed_external_publication'
            },
            {
                'step': 'decision_influence_review',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-015',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 15,
        "question_text": 'Are any AI tools embedded in customer-facing communications?',
        "question_type": 'SS',
        "options": ['Yes — disclosed to customers', 'Yes — not disclosed', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'customer_facing_disclosure'
            },
            {
                'step': 'decision_influence_review',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-017',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 17,
        "question_text": 'Have any AI vendors disclosed a security incident affecting your data in the past 3 months?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'vendor_incident_disclosure'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2: time horizon changed from past 24 months to past 3 months per audit Decision 4',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-018',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 18,
        "question_text": 'Have you confirmed AI vendor SOC 2 or ISO compliance?',
        "question_type": 'SS',
        "options": ['Yes — all major vendors', 'Some', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'vendor_compliance_verification'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-019',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 19,
        "question_text": 'Could you switch from your most-used AI vendor within 90 days if required?',
        "question_type": 'SS',
        "options": ['Yes — easily', 'With significant effort', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CIO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'vendor_switching_capability'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 0.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-020',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 20,
        "question_text": 'Have you reviewed indemnification language in AI vendor contracts?',
        "question_type": 'YN',
        "options": ['Yes — comprehensive', 'Yes — some', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CFO', 'CEO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'indemnification_review'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 0.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-021',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 21,
        "question_text": 'Does any insurance policy specifically address AI-related liability?',
        "question_type": 'SS',
        "options": [
            'Yes — named coverage',
            'Possibly included in cyber policy',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'ai_insurance_coverage'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-022',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 22,
        "question_text": 'Has counsel provided an opinion on AI-related liability exposure?',
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'liability_opinion'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-023',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 23,
        "question_text": 'If AI is involved in hiring, promotion, or termination decisions, has a bias audit been conducted in the past 12 months?',
        "question_type": 'SS',
        "options": ['Yes — by independent auditor', 'Yes — internally', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_does_not_include',
                    'question_id': 'T1-E-009',
                    'answer_value': ['Hiring, firing, or promotion decisions']
                }
            ]
        },
        "role_visibility": ['CEO', 'HR', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'bias_audit_discipline'
            },
            {
                'step': 'decision_influence_review',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2 NEW: E.5 Bias and fairness audits. 12-month horizon retained (not 3-month) because bias audits are typically annual; documented exception to Decision 4 default.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-024',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 24,
        "question_text": 'For hiring in New York City, has the company complied with the annual bias audit requirement under NYC Local Law 144?',
        "question_type": 'SS',
        "options": ['Yes — current', 'Yes — in progress', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_does_not_include',
                    'question_id': 'T1-E-009',
                    'answer_value': ['Hiring, firing, or promotion decisions']
                },
                {
                    'type': 'answer_does_not_include',
                    'question_id': 'T1-A-006',
                    'answer_value': ['NYC Local Law 144']
                }
            ]
        },
        "role_visibility": ['CEO', 'HR'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'nyc_ll144_compliance'
            },
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2 NEW: E.5 Bias and fairness audits. Skip logic: skipped unless E-009 includes hiring AND A-006 includes NYC Local Law 144.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-025',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 25,
        "question_text": 'Are any AI tools operating in an autonomous or agentic mode — taking actions, executing transactions, or modifying systems without per-action human approval?',
        "question_type": 'SS',
        "options": ['Yes — known', 'Suspected', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'autonomous_execution_presence'
            },
            {
                'weight': 2.5,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'autonomous_execution_readiness'
            }
        ],
        "notes": "v1.2 NEW: E.6 Autonomous and agentic execution. Gateway question for E-026/E-027/E-028. Watch-item (pilot watch list entry #10): 'Agentic' is a new 2026 mid-market term; may under-detect. OD-13: when E-025 = No, Autonomous Execution Readiness sub-dimension scores as 100 (skip-satisfied). When E-025 = Don't know, scores at 25% No-penalty.",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-026',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 26,
        "question_text": 'For AI systems operating autonomously, has the company defined the approved scope of autonomous action (what the AI is allowed to do unsupervised)?',
        "question_type": 'SS',
        "options": ['Yes — documented', 'Informally', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-E-025',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['CIO', 'CISO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'autonomous_action_scope'
            },
            {
                'weight': 2.0,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'autonomous_execution_readiness'
            }
        ],
        "notes": 'v1.2 NEW: E.6. Per OD-13, skipping this question via E-025=No yields full marks at the sub-dimension level (Autonomous Execution Readiness), not a redistribution of weight.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-027',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 27,
        "question_text": 'For AI systems operating autonomously, are there documented circuit breakers — defined conditions under which the AI must stop and escalate to a human?',
        "question_type": 'SS',
        "options": [
            'Yes — documented and tested',
            'Yes — documented only',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-E-025',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['CIO', 'CISO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'autonomous_circuit_breakers'
            },
            {
                'weight': 2.5,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'autonomous_execution_readiness'
            }
        ],
        "notes": 'v1.2 NEW: E.6',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-028',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 28,
        "question_text": 'For AI systems operating autonomously, are there gating controls on the external systems the AI can access (CRM, finance system, customer-facing channels)?',
        "question_type": 'SS',
        "options": ['Yes — comprehensive', 'Partial', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-E-025',
                    'answer_value': ['No', "Don't know"]
                }
            ]
        },
        "role_visibility": ['CIO', 'CISO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'autonomous_access_gating'
            },
            {
                'weight': 2.5,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'autonomous_execution_readiness'
            }
        ],
        "notes": 'v1.2 NEW: E.6',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-029',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 29,
        "question_text": 'For AI vendors handling regulated or sensitive data, which contractual provisions exist? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'BAAs for HIPAA-covered data',
            'GLBA Safeguards flow-down',
            'Data Processing Agreements (GDPR)',
            'DFARS 252.204-7012 flow-down',
            'Trade-secret protection clauses (DTSA-aligned)',
            'SBOM/AIBOM disclosure obligations',
            'Right to audit',
            'Subprocessor disclosure',
            'Indemnification for AI errors',
            'Other (specify)',
            'None of these',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CISO', 'CIO', 'CFO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'vendor_flow_downs'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW per OD-14 gap audit. Single highest-leverage vendor-evidence question — feeds HIPAA, GLBA, GDPR DPA, DFARS, DTSA, SBOM/AIBOM, ISO 27001 supplier.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {'other_text_field': True},
    },
    {
        "id": 'T1-E-030',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 30,
        "question_text": "For public-facing claims about your company's AI capabilities (marketing copy, investor communications, sales pitches, SEC filings), is there a documented process for substantiating those claims before publication?",
        "question_type": 'SS',
        "options": [
            'Yes — required and consistently followed',
            'Yes — recommended',
            'No',
            "Don't know",
            'N/A — no public AI claims'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'external_claim_substantiation'
            },
            {
                'step': 'decision_influence_review',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW per OD-14 gap audit. Primary evidence for FTC Section 5, SEC AI-washing; supports NACD board oversight.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-031',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 31,
        "question_text": 'Does your company publish a customer-facing list of AI sub-processors (publicly available or available to customers on request) — the customer-facing AI Third-Party Governance Statement?',
        "question_type": 'SS',
        "options": [
            'Yes — publicly available list maintained and updated',
            'Yes — available to customers on request, kept current',
            'Yes — available on request, but not actively maintained',
            'No — no customer-facing AI sub-processor disclosure',
            "Don't know",
            'N/A — no customer-facing role or no AI sub-processors'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'subprocessor_disclosure'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for DORA third-party oversight and EU PLD value-chain liability.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-032',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 32,
        "question_text": 'Does your company use a standard AI-specific procurement rider or contract addendum when entering new AI vendor agreements?',
        "question_type": 'SS',
        "options": [
            'Yes — standard AI rider/addendum applied to every new AI vendor contract',
            'Yes — AI-specific terms negotiated case-by-case, no standard rider',
            'Yes — generic procurement terms used, no AI-specific provisions',
            'No — no AI-specific procurement discipline',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CFO', 'CIO', 'CISO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'procurement_discipline'
            },
            {
                'step': 'vendor_risk_inventory',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for NIS2 Article 21(2)(d) supply chain security.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-E-033',
        "tier": 'tier_1',
        "section": 'E',
        "sequence_number": 33,
        "question_text": 'For AI use cases affecting fundamental rights (employment, credit, healthcare, education, housing, public benefits), has human override capability been designed into each use case?',
        "question_type": 'SS',
        "options": [
            'Yes — for every fundamental-rights use case, human override capability is designed in and tested',
            'Yes — designed in but not tested',
            'Yes — for some fundamental-rights use cases, not all',
            'No — fundamental-rights AI use cases exist but no human override designed',
            "Don't know",
            'N/A — no fundamental-rights AI use cases'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'human_oversight_per_use_case'
            },
            {
                'step': 'decision_influence_review',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Optional question per audit §4.3, included per operator default decision. Surfaces signal for CoE CETS 225 meaningful human control.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },

    # ===== Section F — Governance Gaps (28 questions) =====

    {
        "id": 'T1-F-001',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 1,
        "question_text": 'Is there a published AI usage policy?',
        "question_type": 'SS',
        "options": [
            'Yes — current and trained',
            'Yes — written but not trained',
            'Drafted but not published',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'policy_existence'
            },
            {
                'step': 'accountability_mapping',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-002',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 2,
        "question_text": 'For each of the following governance structures, indicate the current state (past 3 months):',
        "question_type": 'MATRIX',
        "options": None,
        "matrix_rows": [
            'Named executive accountable for AI outcomes',
            'AI as a standing topic at executive meetings',
            'Board has received AI reporting',
            'AI steering committee or governance body',
            'Board minutes from last 12 months document AI risk discussion',
            'Audit committee has reviewed AI-specific risks in the last 12 months',
            'Board AI competency disclosed in proxy or board-skills matrix'
        ],
        "matrix_columns": ['Yes — formal', 'Yes — informal', 'No', "Don't know"],
        "skip_logic": None,
        "role_visibility": ['BOARD', 'CEO', 'CFO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'governance_structures'
            },
            {
                'step': 'accountability_mapping',
                'weight': 2.0,
                'framework': 'v3_governance'
            },
            {
                'weight': 1.0,
                'dimension': 'performance_measurement',
                'framework': 'v1_audit',
                'sub_component': 'board_reporting_crossfeed',
                'applies_to_row': 'Board has received AI reporting'
            }
        ],
        "notes": 'v1.2: revised matrix absorbs eliminated F-003, F-004, F-005. Row 3 (board AI reporting) cross-feeds Dimension 3 (Performance Measurement) per patch spec §4-A, replacing the input previously provided by eliminated T1-D-006. Watch-item (pilot watch list entry #2): 3-month window on row 3 may miss prior board cycle for quarterly-meeting boards. | 2026-06-28: Added 3 rows for Caremark/NACD/ISS/Glass Lewis evidence (OD-14).',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'matrix_cell_options': ['selected', 'not_selected'],
            'matrix_input_pattern': 'single_selection_per_row'
        },
    },
    {
        "id": 'T1-F-006',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 6,
        "question_text": 'Has the company taken any action based on a formal AI review?',
        "question_type": 'YN',
        "options": ['Yes — multiple actions', 'Yes — at least one', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['BOARD', 'CEO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'action_discipline'
            },
            {
                'step': 'accountability_mapping',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-007',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 7,
        "question_text": 'Is there a documented process for evaluating new AI tools before adoption?',
        "question_type": 'SS',
        "options": ['Yes — required and followed', 'Yes — recommended', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CIO', 'CISO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'adoption_evaluation_process'
            },
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-008',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 8,
        "question_text": 'Is there a documented incident response process for AI-related failures?',
        "question_type": 'SS',
        "options": ['Yes — tested', 'Yes — written only', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CISO', 'CIO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'incident_response_process'
            },
            {
                'step': 'incident_response_readiness',
                'weight': 2.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-009',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 9,
        "question_text": 'Have any AI-related audits been conducted (internal or external) in the past 12 months?',
        "question_type": 'YN',
        "options": ['Yes — external', 'Yes — internal', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'audit_discipline'
            }
        ],
        "notes": 'v1.2: 12-month horizon retained per audit Decision 4 watch-item logic (external audits are typically annual). Watch-item (pilot watch list entry #3).',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-010',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 10,
        "question_text": 'Are AI risks on the corporate risk register?',
        "question_type": 'SS',
        "options": [
            'Yes — with named owners, treatment plans, and defined board cadence',
            'Yes — with owners and treatment plans, no board cadence',
            'Yes — with owners only',
            'Yes — listed but without owners or treatment plans',
            'No — AI risks not on register',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['BOARD', 'CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'risk_register'
            },
            {
                'step': 'accountability_mapping',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: Expanded from YN to 6-option SS to capture COSO ERM/SR 11-7 evidence (risk ownership, treatment plans, board cadence) per OD-14.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-011',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 11,
        "question_text": 'Is there a training program for employees on appropriate AI use?',
        "question_type": 'SS',
        "options": ['Yes — required', 'Yes — optional', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'training_program'
            },
            {
                'module': 'people_readiness',
                'weight': 1.0,
                'framework': 'v2_readiness'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-012',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 12,
        "question_text": 'What are the top three barriers to better AI outcomes in the company? (rank top 3)',
        "question_type": 'RANK',
        "options": [
            'Employee skill',
            'Leadership attention',
            'Data quality',
            'Unclear ROI',
            'Regulatory uncertainty',
            'Budget',
            'Cultural resistance',
            'Vendor complexity',
            'No clear ownership',
            'Technology limitations'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'barrier_ranking'
            }
        ],
        "notes": "v1.2: F-012 broadened from CEO/CFO/COO/BOARD to all roles per audit Section 3.1 (absorbs eliminated H-001). Title changed from 'barriers to better AI governance' to 'barriers to better AI outcomes' to capture H-001's broader framing.",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'rank_max': 3
        },
    },
    {
        "id": 'T1-F-013',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 13,
        "question_text": 'Has the company assessed its AI use cases against ISO/IEC 42001 (the AI management system standard)?',
        "question_type": 'SS',
        "options": [
            'Yes — formal assessment',
            'Yes — informal review',
            'No',
            "Don't know what ISO 42001 is"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'BOARD', 'CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": "v1.2 NEW: F.3 Framework alignment readiness. Watch-item (pilot watch list entry #5): SMB respondents may not recognize 'ISO/IEC 42001' by name; conversion rate to 'Yes — formal assessment' likely under 5% at SMB. The literacy-gap signal is the intended detection mechanism.",
        "is_active": True,
        "scoring_overrides": {
            'dont_know_what_x_is_treatment': {
                'rule': 'OD-12_option_A',
                'penalty': '100%_of_no_penalty',
                'rationale': "Per OD-12 (2026-06-23), this response variant is scored as 100% of a 'No' penalty rather than the 25% default for ordinary 'Don't know' responses. The respondent is not aligned to the framework, and the literacy gap itself is diagnostic.",
                'report_flag': 'framework_literacy_gap_iso_42001',
                'answer_value': "Don't know what ISO 42001 is"
            }
        },
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-014',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 14,
        "question_text": 'Has the company assessed its AI use cases against the NIST AI Risk Management Framework?',
        "question_type": 'SS',
        "options": [
            'Yes — formal assessment',
            'Yes — informal review',
            'No',
            "Don't know what the NIST AI RMF is"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'BOARD', 'CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2 NEW: F.3. Watch-item (pilot watch list entry #6): NIST AI RMF has higher US name recognition than ISO 42001 but still likely under 15% formal-assessment rate at SMB.',
        "is_active": True,
        "scoring_overrides": {
            'dont_know_what_x_is_treatment': {
                'rule': 'OD-12_option_A',
                'penalty': '100%_of_no_penalty',
                'rationale': "Per OD-12 (2026-06-23), this response variant is scored as 100% of a 'No' penalty rather than the 25% default.",
                'report_flag': 'framework_literacy_gap_nist_ai_rmf',
                'answer_value': "Don't know what the NIST AI RMF is"
            }
        },
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-015',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 15,
        "question_text": 'For AI systems with EU customers, employees, or partners, have they been classified against the EU AI Act risk tiers?',
        "question_type": 'SS',
        "options": [
            'Yes — classified, documented',
            'Yes — classified informally',
            'No',
            'N/A — no EU exposure',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'BOARD', 'CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2 NEW: F.3. Watch-item (pilot watch list entry #7): EU exposure detection problem; cross-validate against A-005 (global geography) and A-006 (EU AI Act regulation selected) — companies with EU exposure but no formal recognition may route to N/A incorrectly.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-016',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 16,
        "question_text": 'For AI systems with EU AI Act exposure, has provider vs. deployer position been identified for each system?',
        "question_type": 'SS',
        "options": ['Yes — for all systems', 'Yes — for some', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": {
            'combine': 'any',
            'conditions': [
                {
                    'type': 'answer_equals',
                    'question_id': 'T1-F-015',
                    'answer_value': ['N/A — no EU exposure']
                }
            ]
        },
        "role_visibility": ['CEO', 'BOARD', 'CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": "v1.2 NEW: F.3. Watch-item (pilot watch list entry #8): technical EU AI Act concept; most likely to score 'Don't know' or 'No' at SMB even when companies are subject to the EU AI Act.",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-017',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 17,
        "question_text": "If a regulator opened an inquiry today on an AI system, could the responsible executive produce a documented record of the system's risk classification, controls, and oversight history within 5 business days?",
        "question_type": 'SS',
        "options": ['Yes — confident', 'Yes — with effort', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'incident_response_readiness',
                'weight': 2.0,
                'framework': 'v3_governance'
            },
            {
                'weight': 1.5,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'personal_defensibility'
            }
        ],
        "notes": "v1.2 NEW: F.4 Personal defensibility. Watch-item (pilot watch list entry #9): self-report optimism bias; cross-validate against F-008 (incident response process) — if F-008 = 'No' but F-017 = 'Yes — with effort,' flag inconsistency in Tier 1 report copy.",
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-018',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 18,
        "question_text": 'If an acquirer or insurance carrier asked how AI risk is governed, is there a single document or dossier ready to share?',
        "question_type": 'SS',
        "options": [
            'Yes — current and ready',
            'Yes — but would need updates',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'personal_defensibility'
            }
        ],
        "notes": 'v1.2 NEW: F.4. Feeds Personal Defensibility cross-cutting signal that appears in Tier 1 report as attention flag rather than a step score.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-019',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 19,
        "question_text": 'Have AI use cases been classified by impact tier (Critical / High / Moderate / Low)?',
        "question_type": 'SS',
        "options": ['Yes — all use cases', 'Some', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'BOARD', 'CIO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'accountability_mapping',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2 NEW: F.5 Use-case governance discipline',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-020',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 20,
        "question_text": 'Are per-use-case governance records (dossier, profile, or equivalent) maintained for the highest-impact AI systems?',
        "question_type": 'SS',
        "options": ['Yes — comprehensive', 'Partial', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CIO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'accountability_mapping',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'v1.2 NEW: F.5',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-021',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 21,
        "question_text": 'Is AI governance conducted on a recurring documented cadence (monthly, quarterly, annual)?',
        "question_type": 'SS',
        "options": ['Yes — all three cadences', 'Some cadences', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'governance_cadence'
            }
        ],
        "notes": 'v1.2 NEW: F.5. Feeds overall AI Governance Maturity Scale level rather than a single step score.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-022',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 22,
        "question_text": 'For your highest-impact AI use cases (per T1-F-019 classification), does each have a system-level documentation package including: purpose, training data sources, model version, evaluation results, known limitations, and human-oversight controls?',
        "question_type": 'SS',
        "options": [
            'Yes — comprehensive for all high-impact systems',
            'Yes — partial',
            'No — but in progress',
            'No',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CIO', 'CISO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'accountability_mapping',
                'weight': 2.5,
                'framework': 'v3_governance'
            },
            {
                'weight': 2.0,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'per_system_documentation'
            }
        ],
        "notes": '2026-06-28: NEW per OD-14 gap audit. Primary evidence for EU AI Act Annex IV, SR 11-7/OCC 2013-29 model development, NIST AI RMF Map, ISO 42001 lifecycle, Caremark, SOC 2 processing integrity.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-023',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 23,
        "question_text": 'For AI systems handling regulated, customer, or proprietary data, is data lineage documented (where data came from, how it was prepared, how it flows into training or inference, and where outputs go)?',
        "question_type": 'SS',
        "options": ['Yes — for all in-scope AI systems', 'Yes — for some', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CIO', 'CISO', 'COO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'data_lineage_documentation'
            },
            {
                'step': 'data_exposure_assessment',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW per OD-14 gap audit. Primary evidence for DAMA-DMBOK, DCAM/CDMC; supports GDPR DPIA, HIPAA ePHI tracking, ISO 27001 asset/data flow.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-024',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 24,
        "question_text": 'If a customer, regulator, or acquirer asked which of your AI systems are subject to sector-specific regulation (HIPAA, GLBA, FERPA, DFARS, EU AI Act high-risk, NYC LL144, etc.), could you provide a current mapping within 5 business days?',
        "question_type": 'SS',
        "options": [
            'Yes — current map exists',
            'Yes — could compile in 5 days',
            'No',
            "Don't know",
            'N/A — no regulated AI'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'CEO',
            'CIO',
            'CISO',
            'COO',
            'CFO',
            'BOARD'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 2.5,
                'framework': 'v3_governance'
            },
            {
                'weight': 1.5,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'personal_defensibility'
            }
        ],
        "notes": '2026-06-28: NEW per OD-14 gap audit. Cross-cutting examiner-readiness signal across all sector-regulated frameworks. Companion to F-017/F-018.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-025',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 25,
        "question_text": 'If a regulator-notifiable AI incident occurred (e.g., NYDFS Part 500, DFARS 252.204-7012, GDPR Article 33 — 72-hour windows; DORA — 4-hour initial; NIS2 — 24-hour early warning, 72-hour notification, 1-month final report), how confident is the company in meeting the shortest applicable notification deadline?',
        "question_type": 'SS',
        "options": [
            'Confident — documented and tested',
            'Confident — documented only',
            'Likely could meet it',
            'No — not prepared',
            "Don't know",
            'N/A — no notifiable obligations'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CISO', 'CIO', 'CFO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'incident_notification_window_readiness'
            },
            {
                'step': 'incident_response_readiness',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": '2026-06-28: NEW per OD-14 gap audit. Companion to F-008 (process exists) and F-017 (5-day inquiry response). Captures the shortest-window scenario that NYDFS, DFARS, GDPR all impose.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-026',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 26,
        "question_text": 'Has your company adopted an AI-specific operational risk taxonomy (e.g., the V1 Ch 7 AI Operational Risk Categories or equivalent), with each category mapped to entries in the corporate risk register?',
        "question_type": 'SS',
        "options": [
            'Yes — V1 Ch 7 taxonomy (or equivalent) adopted, with all categories mapped to risk register entries',
            'Yes — taxonomy adopted, mapping to risk register partial',
            'Yes — informal or draft taxonomy in use, not adopted formally',
            'No — no AI-specific risk taxonomy',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['BOARD', 'CEO', 'CFO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'risk_taxonomy'
            },
            {
                'step': 'accountability_mapping',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for DORA ICT risk management and CoE accountability/traceability.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-027',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 27,
        "question_text": 'Does your company maintain a documented AI internal audit log capturing scope, findings, and evidence for each review (the AI Internal Audit Workpaper Log)?',
        "question_type": 'SS',
        "options": [
            'Yes — maintained per audit cycle with scope, findings, and evidence references',
            'Yes — maintained but inconsistently populated',
            'Yes — informal workpapers only',
            'No — no AI internal audit log maintained',
            "Don't know",
            'N/A — no internal audit function'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['BOARD', 'CEO', 'CFO', 'CISO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'internal_audit_evidence'
            },
            {
                'step': 'framework_crosswalk_readiness',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for DORA, EU PLD evidence disclosure, CoE accountability/traceability.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-028',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 28,
        "question_text": 'Does your company maintain documented minutes of management reviews specifically covering AI risk, performance, and incidents (the AI Management Review Minutes Log)?',
        "question_type": 'SS',
        "options": [
            'Yes — documented minutes from regular management reviews of AI on a defined cadence',
            'Yes — minutes captured occasionally, not at defined cadence',
            'Yes — informal notes only',
            'No — no documented management review of AI',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'CFO',
            'CIO',
            'CISO',
            'COO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'management_review_evidence'
            },
            {
                'step': 'accountability_mapping',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for EU PLD evidence disclosure and CoE accountability/traceability.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-029',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 29,
        "question_text": 'Does your company maintain a documented register of corrective actions taken in response to AI incidents, audit findings, or management review items (the AI Corrective Action Register)?',
        "question_type": 'SS',
        "options": [
            'Yes — register maintained with owners, target dates, and verification of completion',
            'Yes — register maintained but without verification step',
            'Yes — ad-hoc tracking, no formal register',
            'No — no AI corrective action register',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'COO',
            'CISO',
            'CIO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'corrective_action_register'
            },
            {
                'step': 'incident_response_readiness',
                'weight': 1.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for NIS2 incident reporting follow-through and CoE accountability/traceability.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-030',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 30,
        "question_text": 'During an AI-related incident, does your company have a documented communication protocol covering internal stakeholders (legal, board, executives), external regulators, and affected customers (the AI Communication Alignment Protocol)?',
        "question_type": 'SS',
        "options": [
            'Yes — documented protocol covering internal stakeholders, regulators, and customers; tested at least annually',
            'Yes — documented but not tested',
            'Yes — ad-hoc or partial coverage',
            'No — no AI-incident communication protocol',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'CISO',
            'CIO',
            'COO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'dimension': 'risk_exposure',
                'framework': 'v1_audit',
                'sub_component': 'incident_communication_protocol'
            },
            {
                'step': 'incident_response_readiness',
                'weight': 1.5,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for DORA major incident notification and NIS2 significant incident reporting.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-F-031',
        "tier": 'tier_1',
        "section": 'F',
        "sequence_number": 31,
        "question_text": 'For each AI use case in your company, has the decision influence (e.g., advisory, recommendation-with-human-confirmation, autonomous) been documented and approved (Decision Influence Matrix tier assessment per V1 Ch 5)?',
        "question_type": 'SS',
        "options": [
            'Yes — documented and approved for every AI use case, with decision-influence tier assigned',
            'Yes — documented for most use cases, approval inconsistent',
            'Yes — documented for some use cases (>=50%)',
            'Partial — documented for a minority of use cases (<50%)',
            'No — decision influence not documented per use case',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": [
            'BOARD',
            'CEO',
            'CFO',
            'COO',
            'CIO'
        ],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 2.0,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'decision_influence_documentation'
            },
            {
                'step': 'decision_influence_review',
                'weight': 2.0,
                'framework': 'v3_governance'
            }
        ],
        "notes": 'Added 2026-06-28 per V3 New Frameworks Gap Audit (Drive 1x_2FpyPqEDwm0csmGhiQFA-SRIMZ7yKI). Surfaces signal for EU PLD strict liability and CoE meaningful human control.',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },

    # ===== Section G — Outcomes, Workflow & Confidence (11 questions) =====

    {
        "id": 'T1-G-001',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 1,
        "question_text": 'What outcomes does leadership want AI to produce, in order of priority? (rank top 5)',
        "question_type": 'RANK',
        "options": [
            'Cost reduction',
            'Revenue growth',
            'Speed',
            'Quality',
            'Risk reduction',
            'Customer experience',
            'Employee productivity',
            'Competitive position',
            'Compliance',
            'Innovation'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO', 'COO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'leadership_accountability',
                'weight': 1.5,
                'framework': 'v2_readiness'
            },
            {
                'weight': 2.0,
                'framework': 'efficiency',
                'sub_component': 'outcome_alignment'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'rank_max': 5
        },
    },
    {
        "id": 'T1-G-002',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 2,
        "question_text": 'Are AI investments tied to specific business outcomes in budgeting?',
        "question_type": 'YN',
        "options": ['Yes', 'No', 'Partial', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'CFO'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'leadership_accountability',
                'weight': 1.0,
                'framework': 'v2_readiness'
            },
            {
                'weight': 1.5,
                'framework': 'efficiency',
                'sub_component': 'outcome_alignment'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-004',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 4,
        "question_text": 'If the company expanded AI use 3x, would current governance support it?',
        "question_type": 'SS',
        "options": ['Yes — easily', 'With adjustments', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['CEO', 'COO', 'BOARD'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'leadership_accountability',
                'weight': 1.0,
                'framework': 'v2_readiness'
            },
            {
                'weight': 0.5,
                'dimension': 'governance_gaps',
                'framework': 'v1_audit',
                'sub_component': 'scalability_readiness'
            }
        ],
        "notes": 'v1.2: G-003 eliminated as redundant with D-008; G-004 retained',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-005',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 5,
        "question_text": 'Which processes have been redesigned around AI in the past 3 months? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Sales',
            'Marketing',
            'Customer service',
            'HR/recruiting',
            'Finance/accounting',
            'Operations',
            'IT',
            'Legal',
            'Product',
            'Research',
            'Compliance',
            'Other (specify)',
            'None',
            "Don't know"
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['COO', 'VP', 'DIR'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'workflow_readiness',
                'weight': 1.5,
                'framework': 'v2_readiness'
            },
            {
                'weight': 1.5,
                'framework': 'efficiency',
                'sub_component': 'process_optimization'
            }
        ],
        "notes": 'v1.2: time horizon standardized to past 3 months',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-006',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 6,
        "question_text": "Have any processes been worsened by AI introduction that you're aware of?",
        "question_type": 'YN',
        "options": ['Yes', 'No', "Don't know"],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['COO', 'VP', 'DIR'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'operational_friction',
                'weight': 1.5,
                'framework': 'v2_readiness'
            },
            {
                'weight': 1.5,
                'framework': 'efficiency',
                'sub_component': 'process_optimization'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-007',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 7,
        "question_text": 'In your day-to-day work, does AI make things easier or harder overall?',
        "question_type": 'SS',
        "options": [
            'Much easier',
            'Somewhat easier',
            'Neutral',
            'Somewhat harder',
            'Much harder'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['MGR', 'IC'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'operational_friction',
                'weight': 1.5,
                'framework': 'v2_readiness'
            },
            {
                'weight': 1.0,
                'framework': 'efficiency',
                'sub_component': 'process_optimization'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-008',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 8,
        "question_text": 'How often do you work around an AI tool instead of using it as intended?',
        "question_type": 'SS',
        "options": [
            'Constantly',
            'Often',
            'Sometimes',
            'Rarely',
            'Never',
            'N/A'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['MGR', 'IC'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'operational_friction',
                'weight': 1.5,
                'framework': 'v2_readiness'
            },
            {
                'weight': 1.0,
                'framework': 'efficiency',
                'sub_component': 'process_optimization'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-009',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 9,
        "question_text": 'Confidence that the company is getting value from its AI spend',
        "question_type": 'L5',
        "options": [
            '1 (no confidence)',
            '2',
            '3',
            '4',
            '5 (high confidence)'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'leadership_accountability',
                'weight': 1.0,
                'framework': 'v2_readiness',
                'sub_component': 'value_confidence'
            },
            {
                'weight': 1.0,
                'framework': 'efficiency',
                'sub_component': 'outcome_alignment'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-010',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 10,
        "question_text": 'Confidence that the company would survive regulatory scrutiny of its AI use today',
        "question_type": 'L5',
        "options": [
            '1',
            '2',
            '3',
            '4',
            '5'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.0,
                'framework': 'v3_governance',
                'cross_cutting_signal': 'regulatory_confidence'
            },
            {
                'module': 'leadership_accountability',
                'weight': 0.5,
                'framework': 'v2_readiness'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-011',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 11,
        "question_text": 'Confidence that AI risks are understood at the leadership level',
        "question_type": 'L5',
        "options": [
            '1',
            '2',
            '3',
            '4',
            '5'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'module': 'leadership_accountability',
                'weight': 1.0,
                'framework': 'v2_readiness',
                'sub_component': 'risk_understanding'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-G-012',
        "tier": 'tier_1',
        "section": 'G',
        "sequence_number": 12,
        "question_text": "Confidence that the company's AI program is aligned with stated business outcomes",
        "question_type": 'L5',
        "options": [
            '1',
            '2',
            '3',
            '4',
            '5'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 1.5,
                'framework': 'efficiency',
                'sub_component': 'outcome_alignment'
            },
            {
                'module': 'leadership_accountability',
                'weight': 0.5,
                'framework': 'v2_readiness'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },

    # ===== Section H — Follow-up (3 questions) =====

    {
        "id": 'T1-H-002',
        "tier": 'tier_1',
        "section": 'H',
        "sequence_number": 2,
        "question_text": 'Which of the following would you like to receive based on these findings? (select all that apply)',
        "question_type": 'MS',
        "options": [
            'Industry peer comparison',
            'Structured remediation roadmap',
            'Conversation about a deeper SRJ audit',
            'Email me the report only',
            'None of the above'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'framework': 'lead_gen',
                'sub_component': 'follow_up_preferences'
            }
        ],
        "notes": 'v1.2: revised multi-select absorbs eliminated H-003 and H-005. Downstream Postmark email automation flow must branch on multi-select checkbox selections rather than the original three yes/no answers (flagged in patch spec §7 deferred items).',
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-H-004',
        "tier": 'tier_1',
        "section": 'H',
        "sequence_number": 4,
        "question_text": "What's your preferred follow-up method?",
        "question_type": 'SS',
        "options": [
            'Email me the report',
            'Email me + brief call',
            'Send to my CEO',
            'No follow-up'
        ],
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": True,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'framework': 'lead_gen',
                'sub_component': 'contact_preference'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": None,
    },
    {
        "id": 'T1-H-006',
        "tier": 'tier_1',
        "section": 'H',
        "sequence_number": 6,
        "question_text": "Anything we should know that the questionnaire didn't ask? (optional, max 1000 characters)",
        "question_type": 'TEXT',
        "options": None,
        "matrix_rows": None,
        "matrix_columns": None,
        "skip_logic": None,
        "role_visibility": ['all'],
        "required": False,
        "scoring_weight": Decimal('1.00'),
        "framework_mappings": [
            {
                'weight': 0,
                'framework': 'lead_gen',
                'sub_component': 'freeform_feedback'
            }
        ],
        "notes": None,
        "is_active": True,
        "scoring_overrides": None,
        "extended_metadata": {
            'max_length': 1000
        },
    },
]


# Convenience aliases
QUESTIONS = TIER_1_QUESTIONS

# Type alias for question dicts; used as a type hint in scoring.frameworks.*
# (annotations are lazy under `from __future__ import annotations`, so this
# alias only needs to be importable, not strictly correct as a generic).
Question = dict


def get_questions_by_section(section: str) -> list:
    """Return all questions in a given section (A through H), ordered by sequence_number."""
    return [q for q in TIER_1_QUESTIONS if q["section"] == section]


def get_question_by_id(question_id: str) -> dict | None:
    """Return a single question by its id (e.g., 'T1-A-006'), or None if not found."""
    for q in TIER_1_QUESTIONS:
        if q["id"] == question_id:
            return q
    return None
