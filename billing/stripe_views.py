"""HTTP views for Stripe checkout and webhook.

- POST /billing/checkout/ : creates Stripe Checkout Session, returns redirect
- POST /billing/webhook/  : handles Stripe events, triggers report generation

Webhook is csrf-exempt (Stripe cannot send CSRF tokens). Signature
verification is the only integrity check — no signature = 400.
"""

from __future__ import annotations

import json
import logging
import os

from django.db import connection, transaction
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
)
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods

from billing import stripe_service
from questionnaire import services as q_services
from reports import services as r_services

logger = logging.getLogger(__name__)


def _base_url(request) -> str:
    """Return the site base URL for building success/cancel URLs."""
    base = os.environ.get("BASE_URL")
    if base:
        return base.rstrip("/")
    return f"{request.scheme}://{request.get_host()}"


@require_http_methods(["POST"])
@csrf_protect
def create_checkout(request):
    """Create a Stripe Checkout Session for the current respondent.

    Reads respondent_id from session, resolves engagement + email, then
    creates a Stripe Checkout Session. Returns 303 redirect to Stripe.
    """
    rid = request.session.get("respondent_id")
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT r.engagement_id, r.email, coalesce(e.instrument, 'tier_1') "
            "FROM respondents r JOIN engagements e ON e.id = r.engagement_id WHERE r.id = %s",
            (rid,),
        )
        row = cursor.fetchone()

    if row is None:
        return HttpResponseNotFound("respondent not found")

    engagement_id, buyer_email, instrument = str(row[0]), row[1], row[2]
    base = _base_url(request)
    offer = stripe_service.OFFERS.get(instrument, stripe_service.OFFERS["tier_1"])
    price_id = os.environ.get(offer["price_env"]) or None

    try:
        session = stripe_service.create_checkout_session(
            engagement_id=engagement_id,
            buyer_email=buyer_email,
            success_url=f"{base}/billing/success/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/q/next/",
            price_id=price_id,
            unit_amount_cents=offer["cents"],
            product_name=offer["name"],
            product_description=offer["description"],
        )
    except RuntimeError as e:
        return HttpResponseBadRequest(str(e))

    return redirect(session["url"])


@require_http_methods(["GET", "POST"])
def create_tier2_checkout(request, engagement_id):
    """Stripe Checkout for a Tier 2 engagement the session's buyer manages.
    Amount is the company-size price (billing.pricing); paid before any
    respondent is invited (Part B-1 S.3.1)."""
    from engagements.buyer_views import _can_manage
    from billing.pricing import get_tier_2_price_cents
    engagement_id = str(engagement_id)
    if not _can_manage(request, engagement_id):
        return HttpResponseNotFound("engagement not found")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT u.email, c.size_bracket, c.name, e.payment_status, e.tier "
            "FROM engagements e JOIN users u ON u.id = e.buyer_user_id "
            "LEFT JOIN companies c ON c.id = e.company_id WHERE e.id = %s",
            (engagement_id,),
        )
        row = cursor.fetchone()
    if row is None or row[4] != "tier_2":
        return HttpResponseNotFound("engagement not found")
    buyer_email, bracket, company, payment_status, _ = row
    if payment_status in ("paid", "comped"):
        return redirect("engagements:respondents", engagement_id=engagement_id)
    cents = get_tier_2_price_cents(bracket)
    base = _base_url(request)
    try:
        session = stripe_service.create_checkout_session(
            engagement_id=engagement_id,
            buyer_email=buyer_email,
            success_url=f"{base}/e/{engagement_id}/respondents/?paid=1",
            cancel_url=f"{base}/e/{engagement_id}/respondents/",
            price_id=os.environ.get("STRIPE_TIER_2_PRICE_ID_" + (bracket or "").replace("-", "_").replace("+", "plus")) or None,
            unit_amount_cents=cents,
            product_name="AI Audit: Self-Service Audit (Tier 2)",
            product_description=f"Multi-respondent audit for {company or 'your company'} ({bracket or 'size'} employees)",
            tier="tier_2",
        )
    except RuntimeError as e:
        return HttpResponseBadRequest(str(e))
    return redirect(session["url"])


@require_http_methods(["POST"])
@csrf_exempt
def webhook(request):
    """Handle Stripe webhook events. Currently reacts to:

    - checkout.session.completed → triggers generate_and_lock,
      which transitions engagement Draft→Editable.

    Other event types are acknowledged with 200 but no-op.
    """
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe_service.verify_webhook_signature(payload, sig_header)
    except RuntimeError as e:
        return HttpResponseBadRequest(str(e))
    except Exception:
        return HttpResponseBadRequest("invalid signature")

    metadata = stripe_service.extract_checkout_completed_metadata(event)
    if metadata is None:
        return HttpResponse("ok", status=200)  # ack non-target events

    if metadata.get("tier") == "tier_2":
        # Tier 2 is paid up front: record the payment, tell the buyer where
        # to invite people, and do NOT generate. The report comes when
        # coverage is met (reports.auto_delivery).
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE engagements SET payment_status = 'paid', price_cents = coalesce(%s, price_cents) "
                "WHERE id = %s AND payment_status <> 'paid' RETURNING id",
                (metadata.get("amount_total"), metadata["engagement_id"]),
            )
            first_time = cursor.fetchone() is not None
            cursor.execute(
                "INSERT INTO events (event_type, payload) VALUES ('tier2_payment', %s::jsonb)",
                (json.dumps({"engagement_id": metadata["engagement_id"], "buyer_email": metadata["buyer_email"],
                             "amount_total": metadata.get("amount_total"), "session_id": metadata.get("session_id"),
                             "first_time": first_time}),),
            )
            if first_time:
                try:
                    from engagements.invitations import send_buyer_dashboard_link
                    send_buyer_dashboard_link(cursor, metadata["engagement_id"])
                except Exception:  # noqa: BLE001
                    logger.exception("buyer dashboard link after payment failed")
        return JsonResponse({"tier": "tier_2", "paid": True}, status=200)

    owner_password = os.environ.get("PDF_OWNER_PASSWORD")
    if not owner_password:
        return HttpResponseBadRequest("PDF_OWNER_PASSWORD not set")

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                report_id, _, pdf_hash = r_services.generate_and_lock(
                    cursor,
                    engagement_id=metadata["engagement_id"],
                    buyer_email=metadata["buyer_email"],
                    owner_password=owner_password,
                )
    except ValueError as e:
        # Terminal state / missing engagement — return 200 to prevent retries
        return JsonResponse({"warning": str(e)}, status=200)

    return JsonResponse({
        "report_id": report_id,
        "pdf_hash": pdf_hash,
    }, status=200)


@require_http_methods(["GET"])
def success(request):
    """Landing page after Stripe checkout completion.

    Confirms payment to the buyer. Actual PDF delivery happens via the
    webhook trigger — this page shows a success message and a link to
    view/download the report.
    """
    from django.shortcuts import render
    return render(request, "billing/success.html", {
        "session_id": request.GET.get("session_id", ""),
    })
