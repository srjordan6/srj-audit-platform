"""Framework mapping loader.

Applies external framework mappings to questions.framework_mappings JSONB.
Preserves internal aggregator mappings (v1_audit, v2_readiness, etc.) by
default; passes mode='replace' to fully overwrite.

Mapping entry shape (matches existing questions.framework_mappings format):
    {"framework": "iso-42001", "weight": 3, "dimension": "governance"}

Callers construct a dict of {question_id: [entry, entry, ...]} and pass to
apply_framework_mappings(cursor, mappings). Validation via registry.
"""

from __future__ import annotations

import json
from typing import Any

from scoring import framework_registry as registry


def validate_mapping_entry(entry: dict) -> list[str]:
    """Return list of validation errors for a single mapping entry."""
    errors = []
    if "framework" not in entry:
        errors.append("missing 'framework' key")
    elif not registry.is_valid_framework_id(entry["framework"]):
        errors.append(f"unknown framework id: {entry['framework']}")
    if "weight" not in entry:
        errors.append("missing 'weight' key")
    elif not isinstance(entry["weight"], (int, float)):
        errors.append(f"weight must be numeric, got {type(entry['weight']).__name__}")
    if "dimension" not in entry:
        errors.append("missing 'dimension' key")
    elif not isinstance(entry["dimension"], str):
        errors.append("dimension must be a string")
    return errors


def validate_mappings(mappings: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Return {question_id: [errors...]} for every invalid mapping.

    Empty dict means all mappings valid. Callers should refuse to apply
    if any errors exist.
    """
    errors: dict[str, list[str]] = {}
    for qid, entries in mappings.items():
        qid_errors: list[str] = []
        if not isinstance(entries, list):
            qid_errors.append("mappings must be a list")
        else:
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    qid_errors.append(f"entry [{i}] must be a dict")
                    continue
                for err in validate_mapping_entry(entry):
                    qid_errors.append(f"entry [{i}]: {err}")
        if qid_errors:
            errors[qid] = qid_errors
    return errors


def load_existing_mappings(cursor, question_id: str) -> list[dict]:
    """Return current framework_mappings array for a question, or empty list."""
    cursor.execute(
        "SELECT framework_mappings FROM questions WHERE id = %s",
        (question_id,),
    )
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return []
    if isinstance(row[0], list):
        return row[0]
    if isinstance(row[0], str):
        return json.loads(row[0])
    return []


def _merge_preserving_internal(
    existing: list[dict],
    new_external: list[dict],
) -> list[dict]:
    """Keep internal aggregator entries; replace all external entries with new ones."""
    kept_internal = [
        e for e in existing
        if e.get("framework") in registry.INTERNAL_AGGREGATOR_IDS
    ]
    return kept_internal + new_external


def apply_framework_mappings(
    cursor,
    mappings: dict[str, list[dict]],
    mode: str = "merge",
) -> int:
    """Apply external framework mappings to questions.framework_mappings.

    mode='merge' (default): preserve existing internal aggregator entries,
        replace/add external framework entries per this input.
    mode='replace': overwrite entire framework_mappings array.

    Callers should run validate_mappings() first and refuse on any errors.
    Returns count of questions successfully updated.

    Raises ValueError on unknown mode.
    """
    if mode not in ("merge", "replace"):
        raise ValueError(f"unknown mode '{mode}' — expected 'merge' or 'replace'")

    updated = 0
    for question_id, new_entries in mappings.items():
        if mode == "merge":
            existing = load_existing_mappings(cursor, question_id)
            final_entries = _merge_preserving_internal(existing, new_entries)
        else:
            final_entries = new_entries

        cursor.execute(
            "UPDATE questions SET framework_mappings = %s::jsonb WHERE id = %s",
            (json.dumps(final_entries), question_id),
        )
        if cursor.rowcount > 0:
            updated += 1

    return updated
