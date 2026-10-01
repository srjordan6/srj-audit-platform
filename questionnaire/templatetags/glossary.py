"""Django template filter: glossary_annotate.

Usage in templates:

    {% load glossary %}
    {{ option|glossary_annotate|safe }}

Wraps each glossary term found in the input text with a small info-icon
link to the corresponding srjconsultingservices.com governance reference
page. See questionnaire/glossary.py for the term map and matching rules.

The filter itself HTML-escapes the input, so callers must NOT pipe an
already-escaped or already-safe value. The `|safe` chain on the caller
side is required so the emitted <span>/<a> markup renders as HTML.
"""

from __future__ import annotations

from django import template

from questionnaire.glossary import annotate

register = template.Library()


@register.filter(name="glossary_annotate")
def glossary_annotate(value):
    """Return HTML with glossary terms wrapped in info-icon spans.

    annotate() HTML-escapes its input before adding markup, so the result
    is safe by construction; marking it here lets templates drop |safe.
    """
    from django.utils.safestring import mark_safe
    return mark_safe(annotate(value if value is not None else ""))


_SECTION_NAMES = {
    "A": "Context & Identity",
    "B": "AI Tool Inventory & Discovery",
    "C": "Cost Mapping",
    "D": "Performance Measurement",
    "E": "Risk Exposure",
    "F": "Governance Gaps",
    "G": "Outcomes, Workflow & Confidence",
    "H": "Follow-up",
}


@register.filter(name="section_name")
def section_name(letter: str) -> str:
    """Map a section letter (A-H) to its human-readable topic name."""
    return _SECTION_NAMES.get((letter or "").upper(), str(letter or ""))


@register.filter(name="glossary_link")
def glossary_link(value):
    """Only the info-icon link(s) for the framework terms in an option, as
    a trailing fragment to place AFTER the option's <label>.

    Putting the <a> inside the <label> broke the checkbox's accessible
    name and made the option read as unlabeled to assistive technology
    and automated review (defects C1 and C25, 2026-09-28). The label is
    now plain text; the link stands beside it.
    """
    from django.utils.html import escape
    from django.utils.safestring import mark_safe
    from questionnaire.glossary import _COMPILED, _wrap
    text = value if value is not None else ""
    links = []
    for term, url, pattern in _COMPILED:
        m = pattern.search(text)
        if m and url not in [u for _, u in links]:
            links.append((m.group(0), url))
    if not links:
        return ""
    parts = []
    for matched, url in links:
        parts.append(
            f'<a class="glossary-info" href="{escape(url)}" target="_blank" rel="noopener" '
            f'aria-label="Learn about {escape(matched)}" title="Learn about {escape(matched)}">&#9432;</a>'
        )
    return mark_safe(" " + " ".join(parts))
