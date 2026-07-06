"""Tests for scoring.framework_registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from scoring import framework_registry as reg


# ---------------------------------------------------------------------------
# Priority 1 batch constants
# ---------------------------------------------------------------------------


def test_priority_1_has_exactly_5_frameworks():
    assert len(reg.PRIORITY_1_FRAMEWORKS) == 5


def test_priority_1_includes_launch_batch():
    for fw_id in ["sr-11-7", "iso-42001", "nist-ai-rmf", "eu-ai-act", "nist-csf-2"]:
        assert fw_id in reg.PRIORITY_1_FRAMEWORKS


def test_every_priority_1_has_required_fields():
    for fw_id, fw in reg.PRIORITY_1_FRAMEWORKS.items():
        assert "name" in fw
        assert "category" in fw
        assert "priority" in fw
        assert fw["priority"] == 1
        assert fw["category"] in reg.VALID_CATEGORIES


# ---------------------------------------------------------------------------
# Internal aggregators
# ---------------------------------------------------------------------------


def test_internal_aggregators_include_4_scoring_frameworks():
    for agg in ["v1_audit", "v2_readiness", "v3_governance", "efficiency"]:
        assert agg in reg.INTERNAL_AGGREGATOR_IDS


def test_internal_aggregators_include_context_and_lead_gen():
    assert "context" in reg.INTERNAL_AGGREGATOR_IDS
    assert "lead_gen" in reg.INTERNAL_AGGREGATOR_IDS


# ---------------------------------------------------------------------------
# all_framework_ids
# ---------------------------------------------------------------------------


def test_all_ids_includes_both_external_and_internal():
    all_ids = reg.all_framework_ids()
    assert "iso-42001" in all_ids
    assert "v1_audit" in all_ids


def test_all_ids_count_5_external_plus_6_internal():
    assert len(reg.all_framework_ids()) == 11


# ---------------------------------------------------------------------------
# is_valid_framework_id
# ---------------------------------------------------------------------------


def test_valid_external_framework_id():
    assert reg.is_valid_framework_id("eu-ai-act") is True


def test_valid_internal_aggregator_id():
    assert reg.is_valid_framework_id("v1_audit") is True


def test_unknown_framework_id_returns_false():
    assert reg.is_valid_framework_id("bogus-framework") is False


def test_empty_string_returns_false():
    assert reg.is_valid_framework_id("") is False


# ---------------------------------------------------------------------------
# is_external_framework
# ---------------------------------------------------------------------------


def test_external_framework_yes():
    assert reg.is_external_framework("iso-42001") is True


def test_internal_aggregator_is_not_external():
    assert reg.is_external_framework("v1_audit") is False


def test_unknown_id_is_not_external():
    assert reg.is_external_framework("bogus") is False


# ---------------------------------------------------------------------------
# get_framework / get_display_name
# ---------------------------------------------------------------------------


def test_get_framework_returns_dict():
    fw = reg.get_framework("nist-ai-rmf")
    assert fw is not None
    assert fw["name"] == "NIST AI Risk Management Framework"
    assert fw["category"] == "standard"


def test_get_framework_none_for_unknown():
    assert reg.get_framework("bogus") is None


def test_get_display_name_matches_registry():
    assert reg.get_display_name("eu-ai-act") == "EU AI Act"


def test_get_display_name_none_for_unknown():
    assert reg.get_display_name("bogus") is None


# ---------------------------------------------------------------------------
# frameworks_by_category
# ---------------------------------------------------------------------------


def test_category_regulation_returns_eu_ai_act():
    result = reg.frameworks_by_category("regulation")
    assert "eu-ai-act" in result


def test_category_standard_returns_multiple():
    result = reg.frameworks_by_category("standard")
    assert "iso-42001" in result
    assert "nist-ai-rmf" in result
    assert "nist-csf-2" in result


def test_category_guidance_returns_sr_11_7():
    result = reg.frameworks_by_category("guidance")
    assert result == ["sr-11-7"]


def test_invalid_category_returns_empty_list():
    assert reg.frameworks_by_category("nonsense") == []


# ---------------------------------------------------------------------------
# load_registry_from_db
# ---------------------------------------------------------------------------


def test_load_from_db_uses_active_filter():
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    reg.load_registry_from_db(cursor)
    sql = cursor.execute.call_args[0][0]
    assert "active = TRUE" in sql
    assert "ORDER BY priority" in sql


def test_load_from_db_returns_dict_per_row():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("iso-42001", "ISO/IEC 42001 AI Management System", "desc", "standard", 1, True),
    ]
    result = reg.load_registry_from_db(cursor)
    assert len(result) == 1
    assert result[0]["id"] == "iso-42001"
    assert result[0]["category"] == "standard"
    assert result[0]["priority"] == 1
    assert result[0]["active"] is True


def test_load_from_db_returns_empty_list_when_no_rows():
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    assert reg.load_registry_from_db(cursor) == []
