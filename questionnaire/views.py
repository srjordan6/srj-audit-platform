"""HTTP layer for questionnaire flow.

Sprint D PR 5: lifecycle-aware rendering. State-based dispatch:
- Locked  → _locked.html
- Expired → _expired.html
- Editable → include countdown_text in context
- Draft   → standard question rendering
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from django.db import connection, transaction
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from engagements import lifecycle
from questionnaire import services, session as session_module
from questionnaire.attestation import CURRENT_TIER_1_ATTESTATION
from questionnaire.decorators import require_writable_state


COMPLETE_TEMPLATE = "questionnaire/partials/_questionnaire_complete.html"
LOCKED_TEMPLATE = "questionnaire/partials/_locked.html"
EXPIRED_TEMPLATE = "questionnaire/partials/_expired.html"


def _resolve_respondent_id(request) -> str | None:
    rid = request.session.get("respondent_id")
    if not rid:
        rid = request.GET.get("respondent_id")
    return rid


def _dispatch_by_state(request, cursor, respondent_id: str):
    """Render Locked/Expired/complete/next-question based on lifecycle state.

    Returns an HttpResponse. Locked/Expired short-circuit before question
    lookup. Editable adds countdown_text to context. Draft renders normally.
    """
    lifecycle_ctx = services.get_lifecycle_context(cursor, respondent_id)
    if lifecycle_ctx is None:
        return HttpResponseNotFound("respondent not found")

    state = lifecycle_ctx["state"]
    if state == lifecycle.LOCKED:
        return render(request, LOCKED_TEMPLATE, {})
    if state == lifecycle.EXPIRED:
        return render(request, EXPIRED_TEMPLATE, {})

    ctx = services.get_next_question_context(cursor, respondent_id)
    if ctx is None:
        return render(request, COMPLETE_TEMPLATE, {})

    countdown_text = None
    if state == lifecycle.EDITABLE:
        countdown_text = lifecycle.format_countdown(
            lifecycle_ctx["window_end_ts"],
            datetime.now(timezone.utc),
        )

template = ctx["partial"]
    is_htmx = request.headers.get("HX-Request") == "true"
    if not is_htmx and request.method == "GET":
        template = "questionnaire/question_shell.html"
    return render(
        request,
        template,
        {
            "question": ctx["question"],
            "progress": ctx["progress"],
            "countdown_text": countdown_text,
            "submit_url": "/q/submit/",
            "initial_question_template": ctx["partial"],
        },
    )

# ---------------------------------------------------------------------------
# Questionnaire flow
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def next_question(request):
    """Return the current respondent's next question or lifecycle banner."""
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")
    with connection.cursor() as cursor:
        return _dispatch_by_state(request, cursor, rid)


@require_http_methods(["POST"])
@csrf_protect
@require_writable_state
def submit_response(request):
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
        return _dispatch_by_state(request, cursor, rid)


# ---------------------------------------------------------------------------
# Session bootstrap
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
@csrf_protect
def start(request):
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
    rid = _resolve_respondent_id(request)
    with connection.cursor() as cursor:
        services.sign_attestation(cursor, rid, CURRENT_TIER_1_ATTESTATION)
    return redirect("questionnaire:next_question")


@require_http_methods(["GET"])
def resume(request, token: str):
    rid = session_module.parse_resume_token(token)
    if rid is None:
        return HttpResponseNotFound("resume link invalid or expired")
    request.session["respondent_id"] = rid
    return redirect("questionnaire:next_question")
