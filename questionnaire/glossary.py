"""Glossary term annotator for questionnaire option labels.

Scans respondent-facing option label text and inserts a small info-icon
link next to any glossary term found. Links target srjconsultingservices.com
governance reference pages.

Scope (locked with Stephen 2026-07-12):
  - Applied to OPTION LABELS only (radio/checkbox labels, matrix rows/
    columns, matrix cell options, rank items). NOT to question stems
    or help text.
  - EVERY occurrence of a term in a given label is annotated (not just
    the first).
  - Abbreviations link (e.g. "GDPR" -> the GDPR-and-AI page).
  - Longest match wins: "NIST AI Risk Management Framework" is preferred
    over "NIST" when both would match at the same position.

Rendering: `annotate(text)` returns HTML with each matched term wrapped
in a <span class="glossary-term">{term}<a class="glossary-info" ...>ⓘ</a></span>.
Callers must mark the return value safe. A Django template filter
(questionnaire.templatetags.glossary.glossary_annotate) is provided.
"""

from __future__ import annotations

import re
from html import escape as html_escape

# ---------------------------------------------------------------------------
# Term -> URL map. Longest / most-specific phrases FIRST inside each grouping
# so `sorted(TERMS, key=len, reverse=True)` in annotate() prefers them.
#
# Aliases (abbreviations, common shortenings) live at the bottom and point
# to the same URL as their canonical full term.
# ---------------------------------------------------------------------------

_BASE = "https://srjconsultingservices.com/ai-governance"

TERMS: dict[str, str] = {
    # ---- Framework hub + top-level buckets --------------------------------
    "AI Governance": f"{_BASE}/",
    "State AI Laws": f"{_BASE}/state-ai-laws/",
    "Federal AI Legislation": f"{_BASE}/federal-ai-legislation/",
    "Agency Enforcement": f"{_BASE}/agency-enforcement/",
    "Sector Rules": f"{_BASE}/sector-rules/",
    "Financial Reporting Rules for AI": f"{_BASE}/financial-reporting/",
    "Director Oversight": f"{_BASE}/director-oversight/",
    "General Business Governance": f"{_BASE}/general-business-governance/",
    "Vendor Disclosure": f"{_BASE}/vendor-disclosure/",
    "Data Management Frameworks": f"{_BASE}/data-management-frameworks/",
    "New York City AI Laws": f"{_BASE}/nyc-ai-laws/",

    # ---- Named standards --------------------------------------------------
    "ISO/IEC 42001": f"{_BASE}/iso-42001/",
    "ISO/IEC 22989": f"{_BASE}/iso-22989/",
    "NIST AI Risk Management Framework": f"{_BASE}/nist-ai-rmf/",
    "SR 11-7 and OCC 2013-29": f"{_BASE}/sr-11-7/",

    # ---- Named laws / acts ------------------------------------------------
    "EU AI Act": f"{_BASE}/eu-ai-act/",
    "NYC Local Law 144": f"{_BASE}/nyc-ai-laws/nyc-ll-144/",
    "NYC Local Law 35": f"{_BASE}/nyc-ai-laws/nyc-ll-35/",
    "Colorado AI Act": f"{_BASE}/state-ai-laws/colorado-ai-act/",
    "Texas Responsible AI Governance Act": f"{_BASE}/state-ai-laws/texas-ai-act/",
    "California AI Laws": f"{_BASE}/state-ai-laws/california-ai-laws/",
    "Illinois AI Laws": f"{_BASE}/state-ai-laws/illinois-ai-laws/",
    "Connecticut AI Act": f"{_BASE}/state-ai-laws/connecticut-ai-act/",
    "Tennessee ELVIS Act": f"{_BASE}/state-ai-laws/tennessee-elvis-act/",

    # ---- Agency enforcement -----------------------------------------------
    "FTC AI Enforcement": f"{_BASE}/agency-enforcement/ftc-ai-enforcement/",
    "EEOC AI Enforcement": f"{_BASE}/agency-enforcement/eeoc-ai-enforcement/",
    "CFPB AI Enforcement": f"{_BASE}/agency-enforcement/cfpb-ai-enforcement/",
    "SEC AI Enforcement": f"{_BASE}/agency-enforcement/sec-ai-enforcement/",
    "HHS OCR AI Enforcement": f"{_BASE}/agency-enforcement/hhs-ocr-ai-enforcement/",

    # ---- Sector rules + statutes ------------------------------------------
    "HIPAA and AI": f"{_BASE}/sector-rules/hipaa-ai/",
    "COPPA and AI": f"{_BASE}/sector-rules/coppa-ai/",
    "GDPR and AI": f"{_BASE}/sector-rules/gdpr-ai/",
    "GLBA and AI": f"{_BASE}/sector-rules/glba-ai/",
    "FCRA and AI": f"{_BASE}/sector-rules/fcra-ai/",
    "ECOA and AI": f"{_BASE}/sector-rules/ecoa-ai/",
    "Title VII and AI": f"{_BASE}/sector-rules/title-vii-ai/",
    "WARN Act and AI": f"{_BASE}/sector-rules/warn-ai/",

    # ---- Financial reporting ----------------------------------------------
    "FASB ASU 2025-06": f"{_BASE}/financial-reporting/fasb-asu-2025-06/",
    "AICPA AI Guidance": f"{_BASE}/financial-reporting/aicpa-ai-guidance/",
    "PCAOB AI Guidance": f"{_BASE}/financial-reporting/pcaob-ai-guidance/",
    "SOX 302 and 404 for AI": f"{_BASE}/financial-reporting/sox-302-404-ai/",

    # ---- General business governance --------------------------------------
    "ISO 27001 and AI": f"{_BASE}/general-business-governance/iso-27001-ai/",
    "SOC 2 and AI": f"{_BASE}/general-business-governance/soc-2-ai/",
    "NIST Cybersecurity Framework and AI": f"{_BASE}/general-business-governance/nist-csf-ai/",
    "COSO ERM and AI": f"{_BASE}/general-business-governance/coso-erm-ai/",

    # ---- Vendor disclosure ------------------------------------------------
    "Software Bill of Materials": f"{_BASE}/vendor-disclosure/sbom/",
    "AI Bill of Materials": f"{_BASE}/vendor-disclosure/aibom/",

    # ---- Data management --------------------------------------------------
    "DAMA-DMBOK": f"{_BASE}/data-management-frameworks/dama-dmbok/",
    "EDM Council DCAM": f"{_BASE}/data-management-frameworks/dcam/",
    "CDMC Cloud Data Management": f"{_BASE}/data-management-frameworks/cdmc/",

    # ---- Aliases / common abbreviations -----------------------------------
    # (These point to the same URL as their canonical entry. Placed here so
    # the longest-match precedence in annotate() prefers the canonical
    # phrase when both would fire at the same position.)
    "NIST AI RMF": f"{_BASE}/nist-ai-rmf/",
    "AI RMF": f"{_BASE}/nist-ai-rmf/",
    "NIST CSF": f"{_BASE}/general-business-governance/nist-csf-ai/",
    "ISO 42001": f"{_BASE}/iso-42001/",
    "ISO 22989": f"{_BASE}/iso-22989/",
    "SR 11-7": f"{_BASE}/sr-11-7/",
    "OCC 2013-29": f"{_BASE}/sr-11-7/",
    "Local Law 144": f"{_BASE}/nyc-ai-laws/nyc-ll-144/",
    "Local Law 35": f"{_BASE}/nyc-ai-laws/nyc-ll-35/",
    "LL 144": f"{_BASE}/nyc-ai-laws/nyc-ll-144/",
    "LL 35": f"{_BASE}/nyc-ai-laws/nyc-ll-35/",
    "Texas AI Act": f"{_BASE}/state-ai-laws/texas-ai-act/",
    "TRAIGA": f"{_BASE}/state-ai-laws/texas-ai-act/",
    "ELVIS Act": f"{_BASE}/state-ai-laws/tennessee-elvis-act/",
    "HIPAA": f"{_BASE}/sector-rules/hipaa-ai/",
    "COPPA": f"{_BASE}/sector-rules/coppa-ai/",
    "GDPR": f"{_BASE}/sector-rules/gdpr-ai/",
    "GLBA": f"{_BASE}/sector-rules/glba-ai/",
    "FCRA": f"{_BASE}/sector-rules/fcra-ai/",
    "ECOA": f"{_BASE}/sector-rules/ecoa-ai/",
    "Title VII": f"{_BASE}/sector-rules/title-vii-ai/",
    "WARN Act": f"{_BASE}/sector-rules/warn-ai/",
    "FASB": f"{_BASE}/financial-reporting/fasb-asu-2025-06/",
    "ASU 2025-06": f"{_BASE}/financial-reporting/fasb-asu-2025-06/",
    "AICPA": f"{_BASE}/financial-reporting/aicpa-ai-guidance/",
    "PCAOB": f"{_BASE}/financial-reporting/pcaob-ai-guidance/",
    "SOX 302": f"{_BASE}/financial-reporting/sox-302-404-ai/",
    "SOX 404": f"{_BASE}/financial-reporting/sox-302-404-ai/",
    "SOX": f"{_BASE}/financial-reporting/sox-302-404-ai/",
    "ISO 27001": f"{_BASE}/general-business-governance/iso-27001-ai/",
    "SOC 2": f"{_BASE}/general-business-governance/soc-2-ai/",
    "SOC2": f"{_BASE}/general-business-governance/soc-2-ai/",
    "COSO ERM": f"{_BASE}/general-business-governance/coso-erm-ai/",
    "COSO": f"{_BASE}/general-business-governance/coso-erm-ai/",
    "DMBOK": f"{_BASE}/data-management-frameworks/dama-dmbok/",
    "DAMA": f"{_BASE}/data-management-frameworks/dama-dmbok/",
    "DCAM": f"{_BASE}/data-management-frameworks/dcam/",
    "CDMC": f"{_BASE}/data-management-frameworks/cdmc/",
    "SBOM": f"{_BASE}/vendor-disclosure/sbom/",
    "AIBOM": f"{_BASE}/vendor-disclosure/aibom/",
    "AI BOM": f"{_BASE}/vendor-disclosure/aibom/",
    "FTC": f"{_BASE}/agency-enforcement/ftc-ai-enforcement/",
    "EEOC": f"{_BASE}/agency-enforcement/eeoc-ai-enforcement/",
    "CFPB": f"{_BASE}/agency-enforcement/cfpb-ai-enforcement/",
    "SEC": f"{_BASE}/agency-enforcement/sec-ai-enforcement/",
    "HHS OCR": f"{_BASE}/agency-enforcement/hhs-ocr-ai-enforcement/",
}


def _term_pattern(term: str) -> re.Pattern:
    """Word-boundary, case-insensitive regex for a single term.

    Word boundaries use \\b where the surrounding chars are word chars.
    For terms starting or ending with non-word chars (slash, hyphen,
    space) we omit \\b on that side and rely on the escaped literal.
    """
    esc = re.escape(term)

    def _left_boundary(t: str) -> str:
        return r"\b" if t[:1].isalnum() else r"(?<![A-Za-z0-9])"

    def _right_boundary(t: str) -> str:
        return r"\b" if t[-1:].isalnum() else r"(?![A-Za-z0-9])"

    pattern = f"{_left_boundary(term)}{esc}{_right_boundary(term)}"
    return re.compile(pattern, re.IGNORECASE)


# Precompile term regexes sorted by descending length so longer /
# more-specific matches beat their abbreviations at the same position.
_COMPILED: list[tuple[str, str, re.Pattern]] = [
    (term, url, _term_pattern(term))
    for term, url in sorted(TERMS.items(), key=lambda kv: (-len(kv[0]), kv[0]))
]


# Marker used during two-pass annotation to protect already-linked spans
# from being re-scanned by later (shorter) terms.
_SENTINEL_OPEN = "\x00SRJGLOSS_START\x00"
_SENTINEL_CLOSE = "\x00SRJGLOSS_END\x00"


def _wrap(match_text: str, url: str) -> str:
    """Build the info-icon span HTML for a single match."""
    esc_term = html_escape(match_text, quote=True)
    esc_url = html_escape(url, quote=True)
    aria = html_escape(f"Learn about {match_text}", quote=True)
    icon = (
        f'<a class="glossary-info" href="{esc_url}" target="_blank" '
        f'rel="noopener" aria-label="{aria}" title="{aria}">&#9432;</a>'
    )
    return (
        f'{_SENTINEL_OPEN}<span class="glossary-term">'
        f"{esc_term}{icon}"
        f"</span>{_SENTINEL_CLOSE}"
    )


def annotate(text: str) -> str:
    """Return HTML with each glossary term wrapped in an info-icon span.

    Input `text` is treated as PLAIN TEXT (HTML-escaped before scanning)
    so callers don't need to worry about markup injection from question
    data. Longest / most-specific terms match first; already-linked
    spans are protected from re-annotation via sentinel markers, which
    are stripped before returning.
    """
    if not text:
        return ""

    # Escape once; work on the escaped string. Term text uses characters
    # that pass through escape unchanged (no <, >, &, "), so the escaped
    # text still matches the compiled patterns.
    out = html_escape(str(text), quote=False)

    for term, url, pattern in _COMPILED:
        def _sub(match: re.Match, u=url) -> str:
            # If this match sits inside an already-wrapped sentinel span,
            # skip it. We check the surrounding text via string slicing:
            start = match.start()
            # Look backward for the nearest sentinel of either kind.
            preceding = out[:start]
            last_open = preceding.rfind(_SENTINEL_OPEN)
            last_close = preceding.rfind(_SENTINEL_CLOSE)
            if last_open > last_close:
                # We're inside an already-linked span; leave untouched.
                return match.group(0)
            return _wrap(match.group(0), u)

        out = pattern.sub(_sub, out)

    # Strip sentinels; keep the wrapped HTML.
    out = out.replace(_SENTINEL_OPEN, "").replace(_SENTINEL_CLOSE, "")
    return out
