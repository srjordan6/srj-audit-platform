"""Tests for billing.stripe_service."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from billing import stripe_service


# ---------------------------------------------------------------------------
# create_checkout_session
# ---------------------------------------------------------------------------


@patch("stripe.checkout.Session.create")
def test_create_checkout_session_uses_price_id_when_provided(mock_create):
    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"
    mock_session.payment_intent = "pi_test_456"
    mock_create.return_value = mock_session

    os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
    result = stripe_service.create_checkout_session(
        engagement_id="eng-uuid",
        buyer_email="buyer@x.com",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        price_id="price_XYZ",
    )

    assert result["url"] == "https://checkout.stripe.com/pay/cs_test_123"
    assert result["id"] == "cs_test_123"
    assert result["payment_intent"] == "pi_test_456"

    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["line_items"] == [{"price": "price_XYZ", "quantity": 1}]


@patch("stripe.checkout.Session.create")
def test_create_checkout_session_uses_inline_price_when_no_price_id(mock_create):
    mock_create.return_value = MagicMock(
        id="cs_test", url="https://x", payment_intent=None
    )
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"

    stripe_service.create_checkout_session(
        engagement_id="eng",
        buyer_email="e@x.com",
        success_url="https://s",
        cancel_url="https://c",
    )

    call_kwargs = mock_create.call_args[1]
    line_item = call_kwargs["line_items"][0]
    assert "price_data" in line_item
    assert line_item["price_data"]["unit_amount"] == 39900
    assert line_item["price_data"]["currency"] == "usd"


@patch("stripe.checkout.Session.create")
def test_create_checkout_session_carries_metadata(mock_create):
    mock_create.return_value = MagicMock(
        id="cs", url="https://x", payment_intent=None
    )
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"

    stripe_service.create_checkout_session(
        engagement_id="eng-uuid",
        buyer_email="buyer@x.com",
        success_url="s",
        cancel_url="c",
    )

    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["metadata"] == {
        "engagement_id": "eng-uuid",
        "buyer_email": "buyer@x.com",
    }


@patch("stripe.checkout.Session.create")
def test_create_checkout_session_passes_customer_email(mock_create):
    mock_create.return_value = MagicMock(
        id="cs", url="https://x", payment_intent=None
    )
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"

    stripe_service.create_checkout_session(
        engagement_id="e", buyer_email="buyer@x.com",
        success_url="s", cancel_url="c",
    )

    assert mock_create.call_args[1]["customer_email"] == "buyer@x.com"


def test_create_checkout_raises_when_secret_key_missing():
    os.environ.pop("STRIPE_SECRET_KEY", None)
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        stripe_service.create_checkout_session(
            engagement_id="e", buyer_email="b",
            success_url="s", cancel_url="c",
        )


# ---------------------------------------------------------------------------
# verify_webhook_signature
# ---------------------------------------------------------------------------


@patch("stripe.Webhook.construct_event")
def test_verify_webhook_returns_event(mock_construct):
    mock_construct.return_value = {"type": "checkout.session.completed"}
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
    result = stripe_service.verify_webhook_signature(b"payload", "sig_header")
    assert result == {"type": "checkout.session.completed"}
    mock_construct.assert_called_once_with(b"payload", "sig_header", "whsec_test")


def test_verify_webhook_raises_when_secret_missing():
    os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
    with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
        stripe_service.verify_webhook_signature(b"p", "s")


# ---------------------------------------------------------------------------
# extract_checkout_completed_metadata
# ---------------------------------------------------------------------------


def test_extract_returns_metadata_for_matching_event():
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test",
            "payment_intent": "pi_test",
            "metadata": {
                "engagement_id": "eng-uuid",
                "buyer_email": "b@x.com",
            },
        }},
    }
    result = stripe_service.extract_checkout_completed_metadata(event)
    assert result == {
        "engagement_id": "eng-uuid",
        "buyer_email": "b@x.com",
        "session_id": "cs_test",
        "payment_intent": "pi_test",
    }


def test_extract_returns_none_for_wrong_event_type():
    event = {"type": "customer.created", "data": {"object": {}}}
    assert stripe_service.extract_checkout_completed_metadata(event) is None


def test_extract_returns_none_when_metadata_absent():
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {}}},
    }
    assert stripe_service.extract_checkout_completed_metadata(event) is None


def test_extract_returns_none_when_engagement_id_missing():
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"buyer_email": "b@x.com"}}},
    }
    assert stripe_service.extract_checkout_completed_metadata(event) is None
