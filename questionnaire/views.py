"""HTTP layer for questionnaire flow.

Sprint D PR 5: lifecycle-aware rendering. State-based dispatch:
- Locked  -> _locked.html
- Expired -> _expired.html
- Editable -> include countdown_text in context
- Draft   -> standard question rendering
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
COMPLETE_SHELL_TEMPLATE = "questionnaire/complete_shell.html"
LOCKED_TEMPLATE = "questionnaire/partials/_locked.html"
EXPIRED_TEMPLATE = "questionnaire/partials/_expired.html"


def _resolve_respondent_id(request) -> str | None:
    rid = request.session.get("respondent_id")
    if not rid:
        rid = request.GET.get("respondent_id")
    return rid


def _normalize_progress(progress):
    """Coerce progress into {current, total, percent} with safe ints."""
    if not progress:
        return {}
    if isinstance(progress, tuple):
        if len(progress) < 2:
            return {}
        current = int(progress[0] or 0)
        total = int(progress[1] or 0)
    elif isinstance(progress, dict):
        current = int(progress.get("current") or 0)
        total = int(progress.get("total") or 0)
        if "percent" in progress and progress["percent"] is not None:
            percent = int(progress["percent"])
            return {"current": current, "total": total, "percent": percent}
    else:
        return {}
    percent = int(round((current / total) * 100)) if total else 0
    return {"current": current, "total": total, "percent": percent}


def _parse_matrix_grid_from_post(post):
    """Grid pattern: row_name_<i> + cell_<row>_<col>=<option>."""
    rows = {}
    for key in post.keys():
        if key.startswith("row_name_"):
            idx = key[len("row_name_"):]
            rows.setdefault(idx, {})["name"] = (post.get(key) or "").strip()
        elif key.startswith("cell_"):
            parts = key.split("_")
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                _, row_idx, col_idx = parts
                rows.setdefault(row_idx, {}).setdefault("cells", {})[col_idx] = post.get(key)
    if not rows:
        return None
    return {"matrix_type": "grid", "rows": rows}


def _parse_matrix_choice_from_post(post):
    """Choice pattern: row_<i>=<selected column label>."""
    rows = {}
    for key in post.keys():
        if key.startswith("row_") and not key.startswith("row_name_"):
            idx = key[len("row_"):]
            if idx.isdigit():
                rows[idx] = post.get(key)
    if not rows:
        return None
    return {"matrix_type": "choice", "rows": rows}


def _dispatch_by_state(request, cursor, respondent_id: str):
    """Render Locked/Expired/complete/next-question based on lifecycle state."""
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
        is_htmx = request.headers.get("HX-Request") == "true"
        template = COMPLETE_TEMPLATE
        if not is_htmx and request.method == "GET":
            template = COMPLETE_SHELL_TEMPLATE
        return render(request, template, {})

    countdown_text = None
    if state == lifecycle.EDITABLE:
        countdown_text = lifecycle.format_countdown(
            lifecycle_ctx["window_end_ts"],
            datetime.now(timezone.utc),
        )

    progress = _normalize_progress(ctx.get("progress"))

    template = ctx["partial"]
    is_htmx = request.headers.get("HX-Request") == "true"
    if not is_htmx and request.method == "GET":
        template = "questionnaire/question_shell.html"
    return render(
        request,
        template,
        {
            "question": ctx["question"],
            "progress": progress,
            "countdown_text": countdown_text,
            "submit_url": "/q/submit/",
            "initial_question_template": ctx["partial"],
        },
    )


@require_http_methods(["GET"])
def next_question(request):
    """Return the current respondent's next question or lifecycle banner."""
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")
    if request.session.get("respondent_id") != rid:
        request.session["respondent_id"] = rid
    with connection.cursor() as cursor:
        return _dispatch_by_state(request, cursor, rid)


@require_http_methods(["POST"])
@csrf_protect
@require_writable_state
def submit_response(request):
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    question_id = request.POST.get("question_id") or request.POST.get("data-question-id")
    if not question_id:
        question_id = request.META.get("HTTP_X_QUESTION_ID")
    if not question_id:
        return HttpResponseBadRequest("question_id required")

    answer_value_json = request.POST.get("answer_value_json")
    if answer_value_json:
        try:
            answer_value = json.loads(answer_value_json)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("invalid answer_value_json")
    else:
        answer = request.POST.get("answer")
        answers = request.POST.getlist("answer")
        if len(answers) > 1:
            answer_value = {"selected": answers}
        elif answer:
            answer_value = {"selected": answer}
        else:
            matrix = (
                _parse_matrix_grid_from_post(request.POST)
                or _parse_matrix_choice_from_post(request.POST)
            )
            if matrix:
                answer_value = matrix
            else:
                return HttpResponseBadRequest("answer required")

    is_dont_know = request.POST.get("is_dont_know") == "true"
    with connection.cursor() as cursor:
        services.save_response(
            cursor, rid, question_id, answer_value, is_dont_know
        )
        return _dispatch_by_state(request, cursor, rid)


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