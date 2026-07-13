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
def glossary_annotate(value) -> str:
    """Return HTML with glossary terms wrapped in info-icon spans."""
    return annotate(value if value is not None else "")
