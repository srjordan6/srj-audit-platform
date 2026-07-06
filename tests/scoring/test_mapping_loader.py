"""Tests for scoring.mapping_loader."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from scoring import mapping_loader as loader


# ---------------------------------------------------------------------------
# validate_mapping_entry
# ---------------------------------------------------------------------------


def test_valid_entry_returns_no_errors():
    entry = {"framework": "iso-42001", "weight": 3, "dimension": "governance"}
    assert loader.validate_mapping_entry(entry) == []


def test_missing_framework_key_error():
    errors = loader.validate_mapping_entry({"weight": 1, "dimension": "x"})
    assert any("framework" in e for e in errors)


def test_unknown_framework_id_error():
    errors = loader.validate_mapping_entry(
        {"framework": "bogus-fw", "weight": 1, "dimension": "x"}
    )
    assert any("unknown framework" in e for e in errors)


def test_missing_weight_key_error():
    errors = loader.validate_mapping_entry(
        {"framework": "iso-42001", "dimension": "x"}
    )
    assert any("weight" in e for e in errors)


def test_non_numeric_weight_error():
    errors = loader.validate_mapping_entry(
        {"framework": "iso-42001", "weight": "high", "dimension": "x"}
    )
    assert any("weight must be numeric" in e for e in errors)


def test_missing_dimension_key_error():
    errors = loader.validate_mapping_entry(
        {"framework": "iso-42001", "weight": 1}
    )
    assert any("dimension" in e for e in errors)


def test_internal_aggregator_id_is_valid():
    entry = {"framework": "v1_audit", "weight": 5, "dimension": "audit"}
    assert loader.validate_mapping_entry(entry) == []


# ---------------------------------------------------------------------------
# validate_mappings
# ---------------------------------------------------------------------------


def test_valid_mappings_return_empty():
    mappings = {
        "T1-A-001": [{"framework": "iso-42001", "weight": 1, "dimension": "x"}],
    }
    assert loader.validate_mappings(mappings) == {}


def test_mapping_with_error_returns_error_dict():
    mappings = {"T1-A-001": [{"framework": "bogus", "weight": 1, "dimension": "x"}]}
    errors = loader.validate_mappings(mappings)
    assert "T1-A-001" in errors


def test_non_list_mapping_returns_error():
    mappings = {"T1-A-001": {"not": "a list"}}
    errors = loader.validate_mappings(mappings)
    assert "T1-A-001" in errors
    assert any("list" in e for e in errors["T1-A-001"])


def test_non_dict_entry_returns_error():
    mappings = {"T1-A-001": ["not a dict"]}
    errors = loader.validate_mappings(mappings)
    assert "T1-A-001" in errors


# ---------------------------------------------------------------------------
# load_existing_mappings
# ---------------------------------------------------------------------------


def test_load_existing_returns_list():
    cursor = MagicMock()
    cursor.fetchone.return_value = ([{"framework": "v1_audit", "weight": 3, "dimension": "x"}],)
    result = loader.load_existing_mappings(cursor, "T1-A-001")
    assert result == [{"framework": "v1_audit", "weight": 3, "dimension": "x"}]


def test_load_existing_returns_empty_when_null():
    cursor = MagicMock()
    cursor.fetchone.return_value = (None,)
    assert loader.load_existing_mappings(cursor, "T1-A-001") == []


def test_load_existing_returns_empty_when_row_missing():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    assert loader.load_existing_mappings(cursor, "T1-Z-999") == []


def test_load_existing_parses_json_string():
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        '[{"framework": "v1_audit", "weight": 1, "dimension": "x"}]',
    )
    result = loader.load_existing_mappings(cursor, "T1-A-001")
    assert result == [{"framework": "v1_audit", "weight": 1, "dimension": "x"}]


# ---------------------------------------------------------------------------
# _merge_preserving_internal
# ---------------------------------------------------------------------------


def test_merge_keeps_internal_and_adds_external():
    existing = [{"framework": "v1_audit", "weight": 3, "dimension": "audit"}]
    new_external = [{"framework": "iso-42001", "weight": 2, "dimension": "gov"}]
    result = loader._merge_preserving_internal(existing, new_external)
    assert len(result) == 2
    frameworks = {e["framework"] for e in result}
    assert frameworks == {"v1_audit", "iso-42001"}


def test_merge_drops_existing_external():
    """Old external mappings replaced by new; internal preserved."""
    existing = [
        {"framework": "v1_audit", "weight": 3, "dimension": "audit"},
        {"framework": "iso-42001", "weight": 1, "dimension": "old"},  # will be dropped
    ]
    new_external = [{"framework": "iso-42001", "weight": 5, "dimension": "new"}]
    result = loader._merge_preserving_internal(existing, new_external)
    assert len(result) == 2
    iso_entry = next(e for e in result if e["framework"] == "iso-42001")
    assert iso_entry["weight"] == 5
    assert iso_entry["dimension"] == "new"


def test_merge_with_no_new_external_keeps_internal():
    existing = [{"framework": "v1_audit", "weight": 3, "dimension": "audit"}]
    result = loader._merge_preserving_internal(existing, [])
    assert result == existing


def test_merge_with_no_existing_uses_new():
    result = loader._merge_preserving_internal(
        [], [{"framework": "iso-42001", "weight": 1, "dimension": "x"}]
    )
    assert len(result) == 1
    assert result[0]["framework"] == "iso-42001"


# ---------------------------------------------------------------------------
# apply_framework_mappings
# ---------------------------------------------------------------------------


def test_apply_merge_mode_calls_load_then_update():
    cursor = MagicMock()
    # First call: SELECT load_existing_mappings
    # Second call: UPDATE
    cursor.fetchone.return_value = ([{"framework": "v1_audit", "weight": 3, "dimension": "x"}],)
    cursor.rowcount = 1

    mappings = {
        "T1-A-001": [{"framework": "iso-42001", "weight": 2, "dimension": "y"}],
    }
    count = loader.apply_framework_mappings(cursor, mappings, mode="merge")

    assert count == 1
    # 1 SELECT + 1 UPDATE
    assert cursor.execute.call_count == 2


def test_apply_replace_mode_skips_load():
    cursor = MagicMock()
    cursor.rowcount = 1
    mappings = {
        "T1-A-001": [{"framework": "iso-42001", "weight": 2, "dimension": "y"}],
    }
    count = loader.apply_framework_mappings(cursor, mappings, mode="replace")

    assert count == 1
    # Only UPDATE, no SELECT
    assert cursor.execute.call_count == 1


def test_apply_replace_uses_new_entries_verbatim():
    cursor = MagicMock()
    cursor.rowcount = 1
    new_entries = [{"framework": "iso-42001", "weight": 5, "dimension": "gov"}]
    loader.apply_framework_mappings(
        cursor, {"T1-A-001": new_entries}, mode="replace"
    )
    sql_params = cursor.execute.call_args[0][1]
    written_json = sql_params[0]
    assert json.loads(written_json) == new_entries


def test_apply_unknown_mode_raises():
    with pytest.raises(ValueError, match="unknown mode"):
        loader.apply_framework_mappings(MagicMock(), {}, mode="bogus")


def test_apply_returns_zero_when_no_rows_updated():
    cursor = MagicMock()
    cursor.rowcount = 0
    cursor.fetchone.return_value = (None,)
    count = loader.apply_framework_mappings(
        cursor,
        {"T1-Z-999": [{"framework": "iso-42001", "weight": 1, "dimension": "x"}]},
        mode="replace",
    )
    assert count == 0


def test_apply_multiple_questions_counts_updates():
    cursor = MagicMock()
    cursor.rowcount = 1
    mappings = {
        "T1-A-001": [{"framework": "iso-42001", "weight": 1, "dimension": "x"}],
        "T1-A-002": [{"framework": "eu-ai-act", "weight": 2, "dimension": "y"}],
        "T1-A-003": [{"framework": "nist-ai-rmf", "weight": 3, "dimension": "z"}],
    }
    count = loader.apply_framework_mappings(cursor, mappings, mode="replace")
    assert count == 3
    assert cursor.execute.call_count == 3
