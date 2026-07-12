"""Review & edit views for the 7-day edit window (Phase 2d).

/q/review/           - list every answered question with the stored answer.
/q/edit/<qid>/       - re-render one question's form; submit posts to the
                       existing /q/submit/ endpoint with ?next=review so the
                       respondent returns to the review list after saving.

Editable only while the engagement is in a writable state (Draft/Editable);
Locked/Expired render the list read-only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from django.db import connection
from django.http import HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from engagements import lifecycle
from questionnaire import flow, services
from questionnaire.question_bank import QUESTIONS


def _resolve_respondent_id(request):
    rid = request.session.get("respondent_id")
    if not rid:
        rid = request.GET.get("respondent_id")
    return rid


def _format_answer(value, is_dont_know):
    """Compact human-readable answer for the review table."""
    if value is None:
        return "Not answered"
    if isinstance(value, dict):
        if value.get("_placeholder"):
            return "Not captured"
        if "selected" in value:
            sel = value["selected"]
            text = "; ".join(str(s) for s in sel) if isinstance(sel, list) else str(sel)
        elif "ranked" in value:
            ranked = value.get("ranked") or []
            text = " > ".join(str(r) for r in ranked) if ranked else "Not captured"
        elif "rows" in value:
            text = f"Matrix response ({len(value['rows'])} rows)"
        else:
            text = "Recorded"
    else:
        text = str(value)
    if is_dont_know:
        text += " (Don't know)"
    return text


@require_http_methods(["GET"])
def review(request):
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    with connection.cursor() as cursor:
        lifecycle_ctx = services.get_lifecycle_context(cursor, rid)
        if lifecycle_ctx is None:
            return HttpResponseNotFound("respondent not found")
        role = services.get_respondent_role(cursor, rid)
        cursor.execute(
            "SELECT question_id, answer_value, is_dont_know "
            "FROM responses WHERE respondent_id = %s",
            (rid,),
        )
        answers = {row[0]: (row[1], bool(row[2])) for row in cursor.fetchall()}

    state = lifecycle_ctx["state"]
    editable = lifecycle.is_writable(state)
    countdown_text = None
    if state == lifecycle.EDITABLE and lifecycle_ctx.get("window_end_ts"):
        countdown_text = lifecycle.format_countdown(
            lifecycle_ctx["window_end_ts"], datetime.now(timezone.utc)
        )

    rows = []
    for q in QUESTIONS:
        qid = q["id"]
        if qid not in answers:
            continue  # not part of this respondent's flow / unanswered
        value, dont_know = answers[qid]
        rows.append({
            "qid": qid,
            "section": q.get("section", ""),
            "question": q["question_text"],
            "answer": _format_answer(value, dont_know),
        })

    return render(request, "questionnaire/review.html", {
        "rows": rows,
        "editable": editable,
        "state": state,
        "countdown_text": countdown_text,
        "answered_count": len(rows),
        "role": role,
    })


@require_http_methods(["GET"])
def edit_question(request, question_id: str):
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    with connection.cursor() as cursor:
        lifecycle_ctx = services.get_lifecycle_context(cursor, rid)
    if lifecycle_ctx is None:
        return HttpResponseNotFound("respondent not found")
    if not lifecycle.is_writable(lifecycle_ctx["state"]):
        return render(request, "questionnaire/partials/_locked.html", {})

    q = next((x for x in QUESTIONS if x["id"] == question_id), None)
    if q is None:
        return HttpResponseNotFound("question not found")

    partial = flow.partial_template_for_type(q["question_type"])
    return render(request, "questionnaire/question_shell.html", {
        "question": q,
        "progress": {},
        "countdown_text": None,
        "submit_url": "/q/submit/?next=review",
        "initial_question_template": partial,
    })
