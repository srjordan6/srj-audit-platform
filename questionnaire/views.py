"""HTTP layer for questionnaire flow.

Thin views over questionnaire.services. All orchestration lives in
services.py so views stay focused on HTTP concerns (parsing request,
resolving session, rendering template).

HTMX contract:
- GET /q/next/ returns a partial that swaps into #question-shell
- POST /q/submit/ returns the next question partial (or completion state)

Respondent identity resolution:
- Primary: request.session["respondent_id"] (set by PR 7 magic-link flow)
- Dev fallback: ?respondent_id=<uuid> query param
"""

from __future__ import annotations

import json

from django.db import connection
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from questionnaire import services


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
