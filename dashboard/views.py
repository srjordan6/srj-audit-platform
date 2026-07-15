"""Operator dashboard views. Staff-only.

Three pages:
  /dashboard/                       -- company + engagement list
  /dashboard/engagement/<uuid:eid>/ -- full Q&A drill-in + operator notes
  /dashboard/analytics/             -- per-question cumulative stats
"""

from __future__ import annotations

import json
from collections import defaultdict
from uuid import UUID

from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from dashboard.stats import question_stats
from questionnaire.question_bank import QUESTIONS


# ---------------------------------------------------------------------------
# 1. Engagements list — everyone who has started
# ---------------------------------------------------------------------------

@staff_member_required
def engagement_list(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT e.id, e.tier, e.payment_status, e.snapshot_state,
                   e.price_cents, e.generation_count, e.created_at,
                   e.completed_at,
                   c.name AS company_name, c.industry, c.size_bracket,
                   c.annual_revenue, c.geographic_footprint,
                   r.email, r.name AS respondent_name, r.role,
                   (SELECT COUNT(*) FROM responses WHERE respondent_id = r.id)
                       AS answered
            FROM engagements e
            JOIN respondents r ON r.engagement_id = e.id
            JOIN companies c   ON c.id = e.company_id
            ORDER BY e.created_at DESC
            """
        )
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

    # Rough total-visible baseline per role (used only for progress %).
    total_baseline = sum(1 for q in QUESTIONS if q.get("is_active", True))

    for r in rows:
        r["progress_pct"] = (
            round(r["answered"] / total_baseline * 100.0, 1)
            if total_baseline else 0.0
        )

    return render(request, "dashboard/engagements.html", {
        "engagements": rows,
        "total_baseline": total_baseline,
    })


# ---------------------------------------------------------------------------
# 2. Engagement detail — full Q&A + operator notes
# ---------------------------------------------------------------------------

def _fetch_engagement_context(cursor, engagement_id: str) -> dict | None:
    cursor.execute(
        """
        SELECT e.id, e.tier, e.payment_status, e.snapshot_state,
               e.price_cents, e.generation_count,
               e.created_at, e.completed_at,
               e.first_generation_timestamp, e.window_end_timestamp,
               c.name AS company_name, c.industry, c.size_bracket,
               c.annual_revenue, c.geographic_footprint,
               r.id AS respondent_id, r.email, r.name AS respondent_name, r.role
        FROM engagements e
        JOIN respondents r ON r.engagement_id = e.id
        JOIN companies c   ON c.id = e.company_id
        WHERE e.id = %s LIMIT 1
        """,
        (str(engagement_id),),
    )
    row = cursor.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _fetch_responses(cursor, respondent_id: str) -> list[dict]:
    cursor.execute(
        "SELECT question_id, answer_value, is_dont_know "
        "FROM responses WHERE respondent_id = %s",
        (str(respondent_id),),
    )
    out = []
    for qid, av, dk in cursor.fetchall():
        if isinstance(av, str):
            try:
                av = json.loads(av)
            except (ValueError, TypeError):
                pass
        out.append({"question_id": qid, "answer_value": av, "is_dont_know": dk})
    return out


def _format_answer(av) -> str:
    if av is None:
        return "(not answered)"
    if isinstance(av, dict):
        if "selected" in av:
            sel = av["selected"]
            if isinstance(sel, list):
                text = "; ".join(str(s) for s in sel)
            else:
                text = str(sel)
            if av.get("other"):
                text += f" · Other: {av['other']}"
            return text or "(empty)"
        if "ranked" in av:
            return " > ".join(str(r) for r in av["ranked"] or [])
        if "text" in av:
            return av["text"] or "(empty)"
        if "rows" in av:
            return f"Matrix ({len(av['rows'])} rows)"
    return str(av)


@staff_member_required
def engagement_detail(request, engagement_id):
    try:
        UUID(str(engagement_id))
    except (ValueError, TypeError):
        return HttpResponseBadRequest("invalid engagement id")

    with connection.cursor() as cursor:
        ctx = _fetch_engagement_context(cursor, engagement_id)
        if ctx is None:
            return HttpResponseNotFound("engagement not found")
        answers = _fetch_responses(cursor, ctx["respondent_id"])
        cursor.execute(
            "SELECT id, operator_email, note, created_at, updated_at "
            "FROM operator_notes WHERE engagement_id = %s "
            "ORDER BY created_at DESC",
            (str(engagement_id),),
        )
        notes = [
            {"id": n[0], "operator_email": n[1], "note": n[2],
             "created_at": n[3], "updated_at": n[4]}
            for n in cursor.fetchall()
        ]

    ans_by_qid = {a["question_id"]: a for a in answers}

    # Emit rows grouped by section, iterating in question-bank order so
    # the operator sees the same sequence the respondent saw.
    sections: dict[str, list[dict]] = defaultdict(list)
    for q in QUESTIONS:
        if not q.get("is_active", True):
            continue
        a = ans_by_qid.get(q["id"])
        sections[q.get("section", "")].append({
            "qid": q["id"],
            "question_text": q["question_text"],
            "question_type": q["question_type"],
            "answered": a is not None,
            "answer_text": _format_answer(a["answer_value"]) if a else "(not answered)",
            "is_dont_know": bool(a and a.get("is_dont_know")),
        })

    section_blocks = [
        {"section": sec, "questions": qs}
        for sec, qs in sorted(sections.items())
    ]

    return render(request, "dashboard/engagement_detail.html", {
        "eng": ctx,
        "sections": section_blocks,
        "notes": notes,
        "answered_count": sum(1 for r in section_blocks for q in r["questions"] if q["answered"]),
        "total_visible": sum(len(r["questions"]) for r in section_blocks),
    })


@require_http_methods(["POST"])
@csrf_protect
@staff_member_required
def engagement_add_note(request, engagement_id):
    note = (request.POST.get("note") or "").strip()
    if not note:
        return redirect("dashboard:engagement_detail", engagement_id=engagement_id)
    operator = getattr(request.user, "email", "") or "operator"
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO operator_notes (engagement_id, operator_email, note) "
            "VALUES (%s, %s, %s)",
            (str(engagement_id), operator, note),
        )
    return redirect("dashboard:engagement_detail", engagement_id=engagement_id)


# ---------------------------------------------------------------------------
# 3. Cumulative analytics — per-question stats
# ---------------------------------------------------------------------------

@staff_member_required
def analytics(request):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT question_id, respondent_id, answer_value, is_dont_know "
            "FROM responses"
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM engagements")
        total_engagements = cursor.fetchone()[0]
        cursor.execute("SELECT id, role FROM respondents")
        respondents_by_id = {
            str(rid): (role or "") for rid, role in cursor.fetchall()
        }

    total_respondents = len(respondents_by_id)

    all_rows = []
    for qid, rid, av, dk in rows:
        if isinstance(av, str):
            try:
                av = json.loads(av)
            except (ValueError, TypeError):
                pass
        all_rows.append({
            "question_id": qid,
            "respondent_id": str(rid) if rid else None,
            "answer_value": av,
            "is_dont_know": dk,
        })

    per_question = []
    for q in QUESTIONS:
        if not q.get("is_active", True):
            continue
        per_question.append(question_stats(
            q, all_rows,
            respondents_by_id=respondents_by_id,
            total_respondents=total_respondents,
        ))

    # Group by section for readability.
    by_section: dict[str, list[dict]] = defaultdict(list)
    for row in per_question:
        by_section[row["section"]].append(row)
    section_blocks = [
        {"section": sec, "questions": qs}
        for sec, qs in sorted(by_section.items())
    ]

    return render(request, "dashboard/analytics.html", {
        "sections": section_blocks,
        "total_engagements": total_engagements,
        "total_respondents": total_respondents,
        "total_responses": len(all_rows),
    })
