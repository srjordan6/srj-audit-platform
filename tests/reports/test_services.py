"""Tests for reports.services.generate_and_lock."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from reports import services


UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _cursor_with_engagement(state="Draft", generation_count=0, company_id="company-uuid"):
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (state, company_id, generation_count),  # _get_engagement
        (5,),                                    # _count_responses
        ("report-uuid",),                        # _insert_report RETURNING id
    ]
    return cursor


# ---------------------------------------------------------------------------
# generate_and_lock — Draft → Editable
# ---------------------------------------------------------------------------


@patch("reports.services.generator.generate_locked_report")
def test_draft_transitions_to_editable_with_first_gen_fields(mock_gen):
    mock_gen.return_value = (b"pdf-bytes", "sha256-hex")
    cursor = _cursor_with_engagement(state="Draft")
    now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=UTC)

    report_id, pdf_bytes, pdf_hash = services.generate_and_lock(
        cursor,
        engagement_id="eng-uuid",
        buyer_email="buyer@x.com",
        owner_password="owner-pw",
        now=now,
    )

    assert report_id == "report-uuid"
    assert pdf_bytes == b"pdf-bytes"
    assert pdf_hash == "sha256-hex"

    # Last UPDATE (5th execute call: get engagement + count responses + insert report + update engagement)
    update_sql = cursor.execute.call_args_list[-1][0][0]
    update_params = cursor.execute.call_args_list[-1][0][1]
    assert "UPDATE engagements SET" in update_sql
    assert "snapshot_state" in update_sql
    assert "first_generation_timestamp" in update_sql
    assert "window_end_timestamp" in update_sql
    assert update_params[0] == "Editable"


@patch("reports.services.generator.generate_locked_report")
def test_draft_generates_pdf_with_correct_metadata(mock_gen):
    mock_gen.return_value = (b"pdf", "hash")
    cursor = _cursor_with_engagement(state="Draft")
    now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=UTC)

    services.generate_and_lock(
        cursor, "eng-uuid", "buyer@x.com", "pw", now=now
    )

    call_kwargs = mock_gen.call_args[1]
    assert call_kwargs["buyer_email"] == "buyer@x.com"
    assert call_kwargs["snapshot_id"] == "eng-uuid"
    assert call_kwargs["owner_password"] == "pw"
    assert call_kwargs["generated_at"] == now


# ---------------------------------------------------------------------------
# generate_and_lock — Editable (regeneration)
# ---------------------------------------------------------------------------


@patch("reports.services.generator.generate_locked_report")
def test_editable_increments_generation_count_only(mock_gen):
    mock_gen.return_value = (b"pdf", "hash")
    cursor = _cursor_with_engagement(state="Editable", generation_count=2)

    services.generate_and_lock(
        cursor, "eng-uuid", "buyer@x.com", "pw", now=datetime(2026, 7, 8, tzinfo=UTC),
    )

    update_sql = cursor.execute.call_args_list[-1][0][0]
    assert "generation_count = generation_count + 1" in update_sql
    assert "report_of_record_id" in update_sql
    # Editable does NOT touch first_generation_timestamp or window_end_timestamp
    assert "first_generation_timestamp" not in update_sql
    assert "window_end_timestamp" not in update_sql


# ---------------------------------------------------------------------------
# generate_and_lock — terminal states reject
# ---------------------------------------------------------------------------


@patch("reports.services.generator.generate_locked_report")
def test_locked_state_raises(mock_gen):
    cursor = _cursor_with_engagement(state="Locked")
    with pytest.raises(ValueError, match="terminal"):
        services.generate_and_lock(
            cursor, "eng-uuid", "buyer@x.com", "pw",
        )
    mock_gen.assert_not_called()


@patch("reports.services.generator.generate_locked_report")
def test_expired_state_raises(mock_gen):
    cursor = _cursor_with_engagement(state="Expired")
    with pytest.raises(ValueError, match="terminal"):
        services.generate_and_lock(
            cursor, "eng-uuid", "buyer@x.com", "pw",
        )
    mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Engagement not found
# ---------------------------------------------------------------------------


@patch("reports.services.generator.generate_locked_report")
def test_missing_engagement_raises(mock_gen):
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match="not found"):
        services.generate_and_lock(
            cursor, "eng-missing", "buyer@x.com", "pw",
        )
    mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Reports INSERT metadata
# ---------------------------------------------------------------------------


@patch("reports.services.generator.generate_locked_report")
def test_report_insert_captures_size_and_email(mock_gen):
    mock_gen.return_value = (b"a" * 1234, "hash")
    cursor = _cursor_with_engagement(state="Draft")

    services.generate_and_lock(
        cursor, "eng-uuid", "buyer@x.com", "pw",
    )

    # Third execute call is INSERT INTO reports
    insert_sql = cursor.execute.call_args_list[2][0][0]
    insert_params = cursor.execute.call_args_list[2][0][1]
    assert "INSERT INTO reports" in insert_sql
    assert 1234 in insert_params  # file_size_bytes
    assert "buyer@x.com" in insert_params  # delivered_to_email


# ---------------------------------------------------------------------------
# Content rendering — placeholder for MVP
# ---------------------------------------------------------------------------


def test_placeholder_content_includes_engagement_id():
    html = services._render_placeholder_content("eng-abc", 42)
    assert "eng-abc" in html
    assert "42" in html
    assert "<h1>" in html
