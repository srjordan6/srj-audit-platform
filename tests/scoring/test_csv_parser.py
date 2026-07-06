"""Tests for scoring.csv_parser."""

from __future__ import annotations

import pytest

from scoring import csv_parser


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_parses_single_row():
    csv = "question_id,framework,weight,dimension\nT1-A-001,iso-42001,3,governance\n"
    result = csv_parser.parse_mapping_csv(csv)
    assert result == {
        "T1-A-001": [{"framework": "iso-42001", "weight": 3, "dimension": "governance"}]
    }


def test_groups_multiple_rows_per_question():
    csv = (
        "question_id,framework,weight,dimension\n"
        "T1-A-001,iso-42001,3,governance\n"
        "T1-A-001,eu-ai-act,2,risk\n"
    )
    result = csv_parser.parse_mapping_csv(csv)
    assert len(result["T1-A-001"]) == 2
    frameworks = {e["framework"] for e in result["T1-A-001"]}
    assert frameworks == {"iso-42001", "eu-ai-act"}


def test_multiple_questions():
    csv = (
        "question_id,framework,weight,dimension\n"
        "T1-A-001,iso-42001,3,governance\n"
        "T1-B-005,nist-ai-rmf,4,ai_risk\n"
    )
    result = csv_parser.parse_mapping_csv(csv)
    assert set(result.keys()) == {"T1-A-001", "T1-B-005"}


def test_integer_weight():
    csv = "question_id,framework,weight,dimension\nT1-A-001,iso-42001,3,gov\n"
    result = csv_parser.parse_mapping_csv(csv)
    assert result["T1-A-001"][0]["weight"] == 3
    assert isinstance(result["T1-A-001"][0]["weight"], int)


def test_float_weight():
    csv = "question_id,framework,weight,dimension\nT1-A-001,iso-42001,2.5,gov\n"
    result = csv_parser.parse_mapping_csv(csv)
    assert result["T1-A-001"][0]["weight"] == 2.5
    assert isinstance(result["T1-A-001"][0]["weight"], float)


def test_strips_whitespace():
    csv = "question_id,framework,weight,dimension\n  T1-A-001 , iso-42001 , 3 , gov \n"
    result = csv_parser.parse_mapping_csv(csv)
    assert "T1-A-001" in result
    assert result["T1-A-001"][0]["framework"] == "iso-42001"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_missing_column_raises():
    csv = "question_id,framework,weight\nT1-A-001,iso-42001,3\n"
    with pytest.raises(ValueError, match="missing required columns"):
        csv_parser.parse_mapping_csv(csv)


def test_non_numeric_weight_raises():
    csv = "question_id,framework,weight,dimension\nT1-A-001,iso-42001,high,gov\n"
    with pytest.raises(ValueError, match="row 2"):
        csv_parser.parse_mapping_csv(csv)


def test_empty_row_skipped():
    csv = (
        "question_id,framework,weight,dimension\n"
        ",,,\n"
        "T1-A-001,iso-42001,3,gov\n"
    )
    result = csv_parser.parse_mapping_csv(csv)
    assert list(result.keys()) == ["T1-A-001"]


def test_blank_qid_skipped():
    csv = (
        "question_id,framework,weight,dimension\n"
        ",iso-42001,3,gov\n"
        "T1-A-001,iso-42001,3,gov\n"
    )
    result = csv_parser.parse_mapping_csv(csv)
    assert list(result.keys()) == ["T1-A-001"]


def test_empty_csv_returns_empty_dict():
    csv = "question_id,framework,weight,dimension\n"
    result = csv_parser.parse_mapping_csv(csv)
    assert result == {}


def test_header_only_no_data_ok():
    csv = "question_id,framework,weight,dimension\n"
    assert csv_parser.parse_mapping_csv(csv) == {}
