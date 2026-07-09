"""HTTP views for Stripe checkout and webhook.

- POST /billing/checkout/ : creates Stripe Checkout Session, returns redirect
- POST /billing/webhook/  : handles Stripe events, triggers report generation

Webhook is csrf-exempt (Stripe cannot send CSRF tokens). Signature
verification is the only integrity check — no signature = 400.
"""

from __future__ import annotations

import json
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
            "SELECT r.engagement_id, r.email FROM respondents r WHERE r.id = %s",
            (rid,),
        )
        row = cursor.fetchone()

    if row is None:
        return HttpResponseNotFound("respondent not found")

    engagement_id, buyer_email = str(row[0]), row[1]
    base = _base_url(request)
    price_id = os.environ.get("STRIPE_TIER_1_PRICE_ID")

    try:
        session = stripe_service.create_checkout_session(
            engagement_id=engagement_id,
            buyer_email=buyer_email,
            success_url=f"{base}/billing/success/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/q/next/",
            price_id=price_id,
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
