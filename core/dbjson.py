"""Decoding for jsonb columns read through raw SQL cursors.

Django's psycopg3 backend registers a no-op TextLoader for jsonb so that
JSONField.from_db_value can apply the model field's own decoder
(django/db/backends/postgresql/psycopg_any.py). Models are unaffected --
but this project reads most tables through raw cursors, and those get the
jsonb column back as a *string*, not a dict.

Left undecoded that string silently degrades:
  - scoring scored the JSON text through the option heuristic instead of
    the respondent's selection;
  - the review page and the report appendix rendered
    {"selected": "Yes"} to the reader via str(value).

Use loads_maybe() on any jsonb value pulled from a raw cursor. It decodes
JSON objects and arrays and passes everything else through untouched, so
it is safe to apply unconditionally.
"""

from __future__ import annotations

import json
from typing import Any


def loads_maybe(value: Any) -> Any:
    """Return a decoded object for JSON text; anything else unchanged."""
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except Exception:  # noqa: BLE001
            return value
    if isinstance(value, str):
        t = value.strip()
        if t[:1] in ("{", "[") and t[-1:] in ("}", "]"):
            try:
                return json.loads(t)
            except (ValueError, TypeError):
                return value
    return value
