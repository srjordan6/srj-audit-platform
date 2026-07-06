"""HTTP layer for questionnaire flow.

Thin views over questionnaire.services. Write endpoints wrapped by
@require_writable_state (Sprint D PR 3) to enforce OD-18 lifecycle.
"""

from __future__ import annotations

import json

from django.db import connection, transaction
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from questionnaire import services, session as session_module
from questionnaire.attestation import CURRENT_TIER_1_ATTESTATION
from questionnaire.decorators import require_writable_state


COMPLETE_TEMPLATE = "questionnaire/partials/_questionnaire_complete.html"


def _resolve_respondent_id(request) -> str | None:
    """Return respondent_id from session, then query param, then None."""
    rid = request.session.get("respondent_id")
    if not rid:
        rid = request.GET.get("respondent_id")
    return rid


def _render_context(request, ctx: dict | None):
    """Render either the next-question partial or the completion partial."""
    if ctx is None:
        return render(request, COMPLETE_TEMPLATE, {})
    return render(
        request,
        ctx["partial"],
        {
            "question": ctx["question"],
            "progress": ctx["progress"],
        },
    )


# ---------------------------------------------------------------------------
# Questionnaire flow (PR 6 + PR 3 edit-blocking)
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def next_question(request):
    """Return the current respondent's next question, or completion state."""
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")
    with connection.cursor() as cursor:
        ctx = services.get_next_question_context(cursor, rid)
    return _render_context(request, ctx)


@require_http_methods(["POST"])
@csrf_protect
@require_writable_state
def submit_response(request):
    """Persist the submitted answer, then return the next question."""
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    question_id = request.POST.get("question_id")
    if not question_id:
        return HttpResponseBadRequest("question_id required")

    answer_value_json = request.POST.get("answer_value_json")
    if not answer_value_json:
        return HttpResponseBadRequest("answer_value_json required")

    try:
        answer_value = json.loads(answer_value_json)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid answer_value_json")

    is_dont_know = request.POST.get("is_dont_know") == "true"

    with connection.cursor() as cursor:
        services.save_response(
            cursor, rid, question_id, answer_value, is_dont_know
        )
        ctx = services.get_next_question_context(cursor, rid)

    return _render_context(request, ctx)


# ---------------------------------------------------------------------------
# Session bootstrap (PR 7)
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
@csrf_protect
def start(request):
    """Landing page for a new Tier 1 questionnaire."""
    if request.method == "GET":
        return render(request, "questionnaire/start.html", {})

    required = [
        "email",
        "name",
        "role",
        "company_name",
        "company_industry",
        "company_size_bracket",
    ]
    values = {k: request.POST.get(k, "").strip() for k in required}
    missing = [k for k, v in values.items() if not v]
    if missing:
        return HttpResponseBadRequest(
            f"Missing fields: {', '.join(missing)}"
        )

    with transaction.atomic():
        with connection.cursor() as cursor:
            rid = services.create_engagement_and_respondent(
                cursor,
                email=values["email"],
                name=values["name"],
                role=values["role"],
                company_name=values["company_name"],
                company_industry=values["company_industry"],
                company_size_bracket=values["company_size_bracket"],
            )

    request.session["respondent_id"] = rid
    return redirect("questionnaire:attest")


@require_http_methods(["GET", "POST"])
@csrf_protect
def attest(request):
    """Attestation modal (GET) and signing (POST). Per Decision 7-8.

    POST is gated by @require_writable_state — Locked/Expired reject.
    Applied via _attest_post to keep GET path unblocked.
    """
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    if request.method == "GET":
        return render(
            request,
            "questionnaire/attestation_modal.html",
            {"attestation_text": CURRENT_TIER_1_ATTESTATION},
        )

    return _attest_post(request)


@require_writable_state
def _attest_post(request):
    """Sign attestation — separated so require_writable_state gates POST only."""
    rid = _resolve_respondent_id(request)
    with connection.cursor() as cursor:
        services.sign_attestation(cursor, rid, CURRENT_TIER_1_ATTESTATION)
    return redirect("questionnaire:next_question")


@require_http_methods(["GET"])
def resume(request, token: str):
    """Parse resume token, re-establish session, redirect to next question."""
    rid = session_module.parse_resume_token(token)
    if rid is None:
        return HttpResponseNotFound("resume link invalid or expired")
    request.session["respondent_id"] = rid
    return redirect("questionnaire:next_question")
