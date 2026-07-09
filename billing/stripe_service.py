"""Stripe integration service layer.

Pure Python functions (no Django dependency) for creating checkout sessions
and verifying webhook signatures. Stripe SDK lazy-imported for test isolation.
"""

from __future__ import annotations

import os
from typing import Any, Optional


TIER_1_UNIT_AMOUNT_CENTS = 39900  # $399 per OD-18 pricing lock


def create_checkout_session(
    engagement_id: str,
    buyer_email: str,
    success_url: str,
    cancel_url: str,
    price_id: Optional[str] = None,
    unit_amount_cents: int = TIER_1_UNIT_AMOUNT_CENTS,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for Tier 1 snapshot purchase.

    Two configurations:
    - price_id passed: uses that pre-configured Stripe Price object
    - price_id None: creates inline price_data with unit_amount_cents

    Returns dict with 'id', 'url', 'payment_intent'. The URL is where the
    browser must redirect for buyer to complete payment.

    Metadata carries engagement_id + buyer_email so the webhook handler can
    trigger the right generate_and_lock call after payment succeeds.
    """
    import stripe
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    stripe.api_key = api_key

    if price_id:
        line_items = [{"price": price_id, "quantity": 1}]
    else:
        line_items = [{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "AI Audit Snapshot",
                    "description": "Tier 1 AI Audit — locked PDF report",
                },
                "unit_amount": unit_amount_cents,
            },
            "quantity": 1,
        }]

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=line_items,
        customer_email=buyer_email,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "engagement_id": engagement_id,
            "buyer_email": buyer_email,
        },
    )

    return {
        "id": session.id,
        "url": session.url,
        "payment_intent": getattr(session, "payment_intent", None),
    }


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature and return the parsed event.

    Raises stripe.error.SignatureVerificationError on failure. Callers
    should catch and return 400. Signing secret from env var
    STRIPE_WEBHOOK_SECRET.
    """
    import stripe
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not set")
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def extract_checkout_completed_metadata(event: dict) -> Optional[dict]:
    """From a checkout.session.completed event, return metadata dict.

    Returns None if event type doesn't match or metadata absent.
    """
    if event.get("type") != "checkout.session.completed":
        return None
    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata") or {}
    engagement_id = metadata.get("engagement_id")
    buyer_email = metadata.get("buyer_email")
    if not engagement_id or not buyer_email:
        return None
    return {
        "engagement_id": engagement_id,
        "buyer_email": buyer_email,
        "session_id": session.get("id"),
        "payment_intent": session.get("payment_intent"),
    }
