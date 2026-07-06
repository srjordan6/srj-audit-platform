"""Tests for reports.generator and reports.audit.

Mocks module-level function references so WeasyPrint/pypdf aren't imported
during test collection. No Django settings required.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from reports import audit, generator


UTC = timezone.utc


# ---------------------------------------------------------------------------
# build_watermarked_html
# ---------------------------------------------------------------------------


def test_watermark_includes_email():
    html = generator.build_watermarked_html("", "buyer@example.com", "s", "t")
    assert "buyer@example.com" in html


def test_watermark_includes_snapshot_id():
    html = generator.build_watermarked_html("", "e", "snap-XYZ", "t")
    assert "snap-XYZ" in html


def test_watermark_includes_generated_at():
    html = generator.build_watermarked_html("", "e", "s", "2026-07-04T12:00:00")
    assert "2026-07-04T12:00:00" in html


def test_watermark_wraps_content():
    html = generator.build_watermarked_html("<p>my content</p>", "e", "s", "t")
    assert "<p>my content</p>" in html
    assert "<!DOCTYPE" in html


def test_watermark_uses_diagonal_transform():
    html = generator.build_watermarked_html("", "e", "s", "t")
    assert "rotate(-30deg)" in html


def test_watermark_uses_low_opacity():
    html = generator.build_watermarked_html("", "e", "s", "t")
    assert "opacity: 0.08" in html


def test_watermark_uses_position_fixed():
    html = generator.build_watermarked_html("", "e", "s", "t")
    assert "position: fixed" in html


def test_watermark_delimiter_is_middle_dot():
    html = generator.build_watermarked_html("", "buyer@x.com", "snap-1", "2026-01-01")
    assert "buyer@x.com \u00b7 snap-1 \u00b7 2026-01-01" in html


# ---------------------------------------------------------------------------
# compute_pdf_hash
# ---------------------------------------------------------------------------


def test_hash_matches_sha256():
    data = b"pdf content"
    assert generator.compute_pdf_hash(data) == hashlib.sha256(data).hexdigest()


def test_hash_is_64_hex_chars():
    assert len(generator.compute_pdf_hash(b"x")) == 64


def test_hash_different_inputs_produce_different_hashes():
    assert generator.compute_pdf_hash(b"a") != generator.compute_pdf_hash(b"b")


# ---------------------------------------------------------------------------
# generate_locked_report — pipeline orchestration (mocks WeasyPrint + pypdf)
# ---------------------------------------------------------------------------


@patch("reports.generator.encrypt_pdf")
@patch("reports.generator.html_to_pdf_bytes")
def test_generate_locked_report_returns_encrypted_and_hash(mock_pdf, mock_enc):
    mock_pdf.return_value = b"raw_pdf"
    mock_enc.return_value = b"encrypted_pdf"
    generated_at = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)

    pdf_bytes, pdf_hash = generator.generate_locked_report(
        content_html="<p>report</p>",
        buyer_email="buyer@example.com",
        snapshot_id="snap-uuid",
        generated_at=generated_at,
        owner_password="secret",
    )

    assert pdf_bytes == b"encrypted_pdf"
    assert pdf_hash == hashlib.sha256(b"encrypted_pdf").hexdigest()


@patch("reports.generator.encrypt_pdf")
@patch("reports.generator.html_to_pdf_bytes")
def test_generate_locked_report_injects_watermark_into_html(mock_pdf, mock_enc):
    mock_pdf.return_value = b"raw"
    mock_enc.return_value = b"enc"
    generated_at = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)

    generator.generate_locked_report(
        content_html="<p>c</p>",
        buyer_email="buyer@x.com",
        snapshot_id="s1",
        generated_at=generated_at,
        owner_password="pw",
    )

    html_passed = mock_pdf.call_args[0][0]
    assert "buyer@x.com" in html_passed
    assert "s1" in html_passed


@patch("reports.generator.encrypt_pdf")
@patch("reports.generator.html_to_pdf_bytes")
def test_generate_locked_report_passes_owner_password_to_encrypt(mock_pdf, mock_enc):
    mock_pdf.return_value = b"raw"
    mock_enc.return_value = b"enc"
    generator.generate_locked_report(
        content_html="",
        buyer_email="e",
        snapshot_id="s",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        owner_password="the-owner-password",
    )
    mock_enc.assert_called_once_with(b"raw", "the-owner-password")


# ---------------------------------------------------------------------------
# audit.log_report_download
# ---------------------------------------------------------------------------


def test_log_download_calls_insert_events():
    cursor = MagicMock()
    audit.log_report_download(cursor, "eng", "user", "ip", "ua", "v1_audit")
    cursor.execute.assert_called_once()
    assert "INSERT INTO events" in cursor.execute.call_args[0][0]


def test_log_download_event_type_is_report_downloaded():
    cursor = MagicMock()
    audit.log_report_download(cursor, "e", "u", "ip", "ua")
    assert cursor.execute.call_args[0][1][0] == "report.downloaded"


def test_log_download_actor_and_engagement_ids():
    cursor = MagicMock()
    audit.log_report_download(cursor, "eng-uuid", "user-uuid", "ip", "ua")
    params = cursor.execute.call_args[0][1]
    assert params[1] == "user-uuid"
    assert params[2] == "eng-uuid"


def test_log_download_payload_includes_framework():
    cursor = MagicMock()
    audit.log_report_download(cursor, "e", "u", "ip", "ua", report_framework="v2_readiness")
    payload = json.loads(cursor.execute.call_args[0][1][3])
    assert payload["report_framework"] == "v2_readiness"


def test_log_download_payload_null_framework_when_absent():
    cursor = MagicMock()
    audit.log_report_download(cursor, "e", "u", "ip", "ua")
    payload = json.loads(cursor.execute.call_args[0][1][3])
    assert payload["report_framework"] is None


def test_log_download_captures_ip_and_user_agent():
    cursor = MagicMock()
    audit.log_report_download(cursor, "e", "u", "203.0.113.5", "Firefox/123.0")
    params = cursor.execute.call_args[0][1]
    assert params[4] == "203.0.113.5"
    assert params[5] == "Firefox/123.0"
