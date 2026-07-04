"""Tests for questionnaire.session and PR-7 additions to services.

Django signing requires SECRET_KEY. Since this test file doesn't otherwise
need Django settings, we configure a minimal in-process settings on import.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from django.conf import settings


if not settings.configured:
    settings.configure(
        SECRET_KEY="test-secret-not-for-production-use",
        USE_TZ=True,
    )


from questionnaire import services, session  # noqa: E402
from questionnaire.attestation import (  # noqa: E402
    CURRENT_TIER_1_ATTESTATION,
    TIER_1_ATTESTATION_V1,
)


# ---------------------------------------------------------------------------
# Token round-trip
# ---------------------------------------------------------------------------


def test_make_and_parse_token_round_trip():
    token = session.make_resume_token("some-uuid")
    assert session.parse_resume_token(token) == "some-uuid"


def test_parse_tampered_token_returns_none():
    token = session.make_resume_token("some-uuid")
    tampered = token[:-1] + ("X" if token[-1] != "X" else "Y")
    assert session.parse_resume_token(tampered) is None


def test_parse_junk_token_returns_none():
    assert session.parse_resume_token("not-a-real-token") is None


def test_parse_expired_token_returns_none():
    token = session.make_resume_token("some-uuid")
    # max_age_seconds=-1 forces expiry regardless of clock skew
    assert session.parse_resume_token(token, max_age_seconds=-1) is None


def test_token_max_age_constant_is_30_days():
    assert session.TOKEN_MAX_AGE_SECONDS == 30 * 24 * 3600


# ---------------------------------------------------------------------------
# Attestation constants
# ---------------------------------------------------------------------------


def test_current_attestation_matches_v1():
    assert CURRENT_TIER_1_ATTESTATION == TIER_1_ATTESTATION_V1


def test_attestation_contains_locked_phrases():
    """Decision 7-8 wording must be preserved verbatim."""
    text = TIER_1_ATTESTATION_V1
    assert "I confirm that I am the role I have indicated" in text
    assert "accurate to the best of my knowledge" in text
    assert "authorized to provide this information about my company" in text
    assert "self-reported answers" in text


# ---------------------------------------------------------------------------
# create_engagement_and_respondent
# ---------------------------------------------------------------------------


def test_create_engagement_uses_existing_company_and_user():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        ("company-uuid",),      # company SELECT hit
        ("user-uuid",),         # user SELECT hit
        ("engagement-uuid",),   # engagement INSERT RETURNING
        ("respondent-uuid",),   # respondent INSERT RETURNING
    ]
    rid = services.create_engagement_and_respondent(
        cursor,
        email="test@example.com",
        name="Test Buyer",
        role="CEO",
        company_name="Acme Corp",
        company_industry="Technology",
        company_size_bracket="26-100",
    )
    assert rid == "respondent-uuid"
    assert cursor.execute.call_count == 4


def test_create_engagement_creates_new_company_when_missing():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        None,                       # company SELECT miss
        ("new-company-uuid",),      # company INSERT RETURNING
        ("user-uuid",),             # user SELECT hit
        ("engagement-uuid",),
        ("respondent-uuid",),
    ]
    rid = services.create_engagement_and_respondent(
        cursor,
        email="test@example.com",
        name="Test",
        role="CEO",
        company_name="NewCo",
        company_industry="Tech",
        company_size_bracket="1-25",
    )
    assert rid == "respondent-uuid"
    assert cursor.execute.call_count == 5


def test_create_engagement_creates_new_user_when_missing():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        ("company-uuid",),       # company SELECT hit
        None,                    # user SELECT miss
        ("new-user-uuid",),      # user INSERT RETURNING
        ("engagement-uuid",),
        ("respondent-uuid",),
    ]
    rid = services.create_engagement_and_respondent(
        cursor,
        email="new@example.com",
        name="New Buyer",
        role="CFO",
        company_name="Acme",
        company_industry="Tech",
        company_size_bracket="26-100",
    )
    assert rid == "respondent-uuid"
    assert cursor.execute.call_count == 5


def test_create_engagement_inserts_with_tier_1_defaults():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        ("company-uuid",),
        ("user-uuid",),
        ("engagement-uuid",),
        ("respondent-uuid",),
    ]
    services.create_engagement_and_respondent(
        cursor,
        email="x@y.z",
        name="X",
        role="CEO",
        company_name="Co",
        company_industry="T",
        company_size_bracket="1-25",
    )
    engagement_sql = cursor.execute.call_args_list[2][0][0]
    assert "'tier_1'" in engagement_sql
    assert "'in_progress'" in engagement_sql
    assert "'free'" in engagement_sql


# ---------------------------------------------------------------------------
# sign_attestation
# ---------------------------------------------------------------------------


def test_sign_attestation_updates_row():
    cursor = MagicMock()
    services.sign_attestation(cursor, "rid", TIER_1_ATTESTATION_V1)
    cursor.execute.assert_called_once()
    sql_text = cursor.execute.call_args[0][0]
    assert "UPDATE respondents" in sql_text
    assert "attestation_signed_at" in sql_text
    assert "NOW()" in sql_text


def test_sign_attestation_passes_text_and_id_as_params():
    cursor = MagicMock()
    services.sign_attestation(cursor, "rid-123", TIER_1_ATTESTATION_V1)
    params = cursor.execute.call_args[0][1]
    assert params == (TIER_1_ATTESTATION_V1, "rid-123")


# ---------------------------------------------------------------------------
# is_attestation_signed
# ---------------------------------------------------------------------------


def test_is_attestation_signed_true():
    cursor = MagicMock()
    cursor.fetchone.return_value = (True,)
    assert services.is_attestation_signed(cursor, "rid") is True


def test_is_attestation_signed_false_when_null():
    cursor = MagicMock()
    cursor.fetchone.return_value = (False,)
    assert services.is_attestation_signed(cursor, "rid") is False


def test_is_attestation_signed_false_when_respondent_missing():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    assert services.is_attestation_signed(cursor, "rid") is False
