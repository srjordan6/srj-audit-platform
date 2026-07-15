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
from questionnaire.resume_email import send_resume_email_async


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
        # Pass payment_status so the completion template can skip the
        # paywall for comped / paid engagements and instead confirm the
        # report is being generated + emailed.
        try:
            cursor.execute(
                "SELECT e.payment_status FROM engagements e "
                "JOIN respondents r ON r.engagement_id = e.id "
                "WHERE r.id = %s LIMIT 1",
                (respondent_id,),
            )
            row = cursor.fetchone()
            payment_status = row[0] if row else "free"
        except Exception:  # noqa: BLE001
            payment_status = "free"
        return render(request, template, {"payment_status": payment_status})

    # Track cursor position so the Previous / Forward buttons know where
    # the user just was without depending on client-side JS.
    request.session["current_question_id"] = ctx["question"].id
    request.session.modified = True  # force write; Django sometimes skips

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


def _render_ctx(request, ctx):
    """Shared render helper for Previous / Forward views.

    Also updates session["current_question_id"] so subsequent Previous /
    Forward / Save clicks know where the user just was.
    """
    request.session["current_question_id"] = ctx["question"].id
    request.session.modified = True  # force write; Django sometimes skips
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
            "prior_answer": ctx.get("prior_answer"),
            "progress": progress,
            "submit_url": "/q/submit/",
            "initial_question_template": ctx["partial"],
        },
    )


def _current_qid_from_session_or_query(request):
    return (
        request.session.get("current_question_id")
        or request.GET.get("current_question_id")
        or request.headers.get("X-Current-Question-Id")
        or ""
    ).strip() or None


@require_http_methods(["GET"])
def forward_question(request):
    """Render the visible question immediately AFTER the user's current
    position (tracked in session). Prefills prior_answer if the target
    question was already answered. Distinct from /q/next/ which is the
    auto-advance flow controller."""
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")
    current_qid = _current_qid_from_session_or_query(request)
    with connection.cursor() as cursor:
        ctx = services.get_next_visible_question_context_by_position(
            cursor, rid, current_qid
        )
    if ctx is None:
        return HttpResponseNotFound("no next question")
    return _render_ctx(request, ctx)


@require_http_methods(["POST"])
@csrf_protect
def regenerate_report_view(request):
    """Explicit user-triggered regeneration from /q/review/.

    User batches multiple edits, then clicks "Regenerate report" to
    trigger a single new PDF + Postmark send. AI narrative is reused
    from the ai_analysis_v2 events cache (no new Claude call).
    """
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")
    with connection.cursor() as cursor:
        try:
            from reports.auto_delivery import regenerate_after_edit
            regenerate_after_edit(cursor, rid)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception(
                "manual regenerate failed for %s", rid
            )
    return redirect("questionnaire:review")


@require_http_methods(["POST"])
@csrf_protect
def ai_recommend_laws_view(request):
    """Trigger a Claude Sonnet call to recommend AI-relevant laws.

    Uses the company profile we already know (industry, size, geographic
    footprint, revenue) + the 59-law catalog. Returns the LAW_INVENTORY
    partial re-rendered with recommendations overridden by the AI result.
    Cached in events.law_ai_recommendation so re-clicks return instantly.
    """
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    force = request.POST.get("force") == "1"
    with connection.cursor() as cursor:
        rctx = services._load_respondent_context(cursor, rid)
        answered = services.load_answered_by_id(cursor, rid)
        # Assemble the profile we send to Claude. Include revenue if the
        # respondent has already answered T1-A-007; otherwise omit it.
        # Prefer signup-captured company profile (industry / size /
        # revenue / geographic). Fall back to T1-A-005 and T1-A-007 for
        # any engagement created before those moved to signup.
        legacy_geo = (
            (answered.get("T1-A-005") or {}).get("selected")
            if isinstance(answered.get("T1-A-005"), dict) else None
        )
        legacy_rev = (
            (answered.get("T1-A-007") or {}).get("selected")
            if isinstance(answered.get("T1-A-007"), dict) else None
        )
        profile = {
            "industry": rctx.get("company_industry"),
            "size_bracket": rctx.get("company_size_bracket"),
            "role_of_respondent": rctx.get("respondent_role"),
            "geographic_footprint": rctx.get("geographic_footprint") or legacy_geo,
            "annual_revenue": rctx.get("annual_revenue") or legacy_rev,
            "regulations_the_user_already_checked": (
                (answered.get("T1-A-006") or {}).get("selected")
                if isinstance(answered.get("T1-A-006"), dict) else None
            ),
        }

        from questionnaire.law_ai_recommender import ai_recommend_laws
        ai_result = ai_recommend_laws(rid, profile, force_refresh=force)

        # Re-render the T1-A-006 partial with AI recommendations layered on top.
        # Find the T1-A-006 question object.
        from questionnaire import flow
        role = services.get_respondent_role(cursor, rid)
        visible = flow.questions_visible_to_role(role, answered)
        q_target = next((q for q in visible if q.id == "T1-A-006"), None)
        if not q_target:
            return HttpResponseNotFound("T1-A-006 not visible")
        services._decorate_question(q_target, answered, visible=visible, respondent_ctx=rctx)

        # Override recommendations with AI selections if the call succeeded.
        if ai_result.get("ok") and ai_result.get("selected"):
            q_target.recommended_laws = ai_result["selected"]
            q_target.recommended_set = set(ai_result["selected"])
        q_target.ai_recommendation = ai_result

    # Pre-check the AI's recommendations. Merge with anything the user
    # already had ticked, so we never LOSE their prior selections; we
    # only ADD the AI's picks on top. User can uncheck what they don't
    # want before hitting Save & continue.
    existing_prior = answered.get("T1-A-006") or {}
    existing_selected = existing_prior.get("selected") if isinstance(existing_prior, dict) else None
    existing_selected = list(existing_selected) if isinstance(existing_selected, list) else []
    merged_selected = list({*existing_selected, *(ai_result.get("selected") or [])})
    display_prior = {
        "selected": merged_selected,
        "other": existing_prior.get("other", "") if isinstance(existing_prior, dict) else "",
    }

    template = flow.partial_template_for_type(q_target.question_type)
    return render(
        request,
        template,
        {
            "question": q_target,
            "prior_answer": display_prior,
            "progress": _normalize_progress(flow.progress_for_role(role, answered)),
            "submit_url": "/q/submit/",
        },
    )


@require_http_methods(["GET"])
def jump_to_position(request):
    """Slider-driven jump to a specific position in the visible flow.

    Accepts ?position=N (1-based). Position must be within already-
    answered territory (or the first-unanswered slot). Anything higher
    is clamped by the services layer so the slider can't escape.
    """
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")
    pos = request.GET.get("position", "").strip()
    with connection.cursor() as cursor:
        ctx = services.get_question_context_by_position(cursor, rid, pos)
    if ctx is None:
        return HttpResponseNotFound("invalid position")
    return _render_ctx(request, ctx)


@require_http_methods(["GET"])
def previous_question(request):
    """Render the visible question immediately BEFORE the user's current
    position (tracked in session). Prefills prior_answer. Returns 404
    if the respondent is already on the first question."""
    rid = _resolve_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")
    current_qid = _current_qid_from_session_or_query(request)
    with connection.cursor() as cursor:
        ctx = services.get_previous_visible_question_context(
            cursor, rid, current_qid
        )
    if ctx is None:
        return HttpResponseNotFound("no previous question")
    return _render_ctx(request, ctx)


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
    other_tools = request.POST.get("other_tools", "").strip()
    other_specify = request.POST.get("other_specify", "").strip()

    # Detect TEXT-type questions so we can accept an empty submit (they're
    # typically optional) and store the answer under the shape the TEXT
    # partial reads back for prefill: {"text": "..."}.
    try:
        from questionnaire.question_bank import QUESTIONS as _Q
        _q_lookup = {q['id']: q for q in _Q}
        _q_type = (_q_lookup.get(question_id) or {}).get('question_type')
        _q_required = (_q_lookup.get(question_id) or {}).get('required', True)
    except Exception:  # noqa: BLE001
        _q_type = None
        _q_required = True

    if _q_type == "TEXT":
        text_val = request.POST.get("answer", "")
        # Strip only leading/trailing whitespace; preserve internal.
        text_val = text_val.strip() if isinstance(text_val, str) else ""
        # Optional TEXT questions accept empty submits (stored as empty string).
        if not text_val and _q_required:
            return HttpResponseBadRequest("answer required")
        answer_value = {"text": text_val}
        is_dont_know = request.POST.get("is_dont_know") == "true"
        with connection.cursor() as cursor:
            services.save_response(
                cursor, rid, question_id, answer_value, is_dont_know
            )
            # First completion auto-generates; post-completion edits do
            # not — user clicks Regenerate on /q/review/.
            try:
                if services.get_next_question_context(cursor, rid) is None:
                    from reports.auto_delivery import on_respondent_complete
                    on_respondent_complete(cursor, rid)
            except Exception:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).exception(
                    "post-TEXT auto-delivery trigger failed for %s", rid
                )
            if request.GET.get("next") == "review" or request.POST.get("next") == "review":
                return redirect("questionnaire:review")
            return _dispatch_by_state(request, cursor, rid)
    if answer_value_json:
        try:
            answer_value = json.loads(answer_value_json)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("invalid answer_value_json")
    else:
        answer = request.POST.get("answer")
        answers = request.POST.getlist("answer")
        # TOOL_INVENTORY posts include a companion "other_tools" textarea.
        # If it's present we always emit the dict-with-selected shape so
        # the "other" value never gets dropped when zero checkboxes are
        # ticked (respondent may have ONLY custom tools).
        if other_tools:
            answer_value = {"selected": answers or [], "other": other_tools}
        elif len(answers) > 1:
            answer_value = {"selected": answers}
            if other_specify:
                answer_value["other"] = other_specify
        elif answer:
            answer_value = {"selected": answer}
            if other_specify:
                answer_value["other"] = other_specify
        else:
            matrix = (
                _parse_matrix_grid_from_post(request.POST)
                or _parse_matrix_choice_from_post(request.POST)
            )
            if matrix:
                answer_value = matrix
            else:
                # An empty TOOL_INVENTORY submission (no tools checked,
                # no other-tools text) is still a valid answer — treat
                # zero-check submits from that question as an empty
                # selection rather than a 400.
                if request.POST.get("data-question-type") == "TOOL_INVENTORY" or \
                   request.POST.get("question_id", "").endswith("A-000"):
                    answer_value = {"selected": [], "other": ""}
                else:
                    return HttpResponseBadRequest("answer required")

    is_dont_know = request.POST.get("is_dont_know") == "true"
    with connection.cursor() as cursor:
        services.save_response(
            cursor, rid, question_id, answer_value, is_dont_know
        )
        # Phase 2c: first completion auto-generates + emails the report.
        # Post-completion edits do NOT auto-regenerate — the user clicks
        # "Regenerate report" on /q/review/ once they're done batching
        # edits. Keeps Postmark + WeasyPrint cost bounded to one run per
        # batch instead of one per keystroke.
        try:
            more_ahead = services.get_next_question_context(cursor, rid) is not None
            if not more_ahead:
                from reports.auto_delivery import on_respondent_complete
                on_respondent_complete(cursor, rid)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception(
                "post-save auto-delivery trigger failed for %s", rid
            )
        # Phase 2d: edits from the review page return to the review list.
        if request.GET.get("next") == "review" or request.POST.get("next") == "review":
            return redirect("questionnaire:review")
        return _dispatch_by_state(request, cursor, rid)


@require_http_methods(["GET", "POST"])
@csrf_protect
def start(request):
    if request.method == "GET":
        # Pre-fill the access-code input from ?code=<CODE> so LinkedIn/
        # marketing URLs can include the promo in the query string.
        prefill_code = request.GET.get("code", "").strip()
        from questionnaire.naics_catalog import SECTORS as NAICS_SECTORS
        return render(
            request,
            "questionnaire/start.html",
            {
                "prefill_code": prefill_code,
                "naics_sectors": NAICS_SECTORS,
            },
        )

    required = [
        "email",
        "name",
        "role",
        "company_name",
        "company_industry",
        "company_size_bracket",
        "annual_revenue",
        "geographic_footprint",
    ]
    values = {k: request.POST.get(k, "").strip() for k in required}
    missing = [k for k, v in values.items() if not v]
    if missing:
        return HttpResponseBadRequest(
            f"Missing fields: {', '.join(missing)}"
        )

    # Optional access code - promotional/tester full-comp code.
    submitted_code = request.POST.get("access_code", "").strip()
    access_code_row = None
    if submitted_code:
        from questionnaire.access_codes import validate_code
        with connection.cursor() as cursor:
            access_code_row = validate_code(cursor, submitted_code)
        if access_code_row is None:
            # Re-render the form with the user's inputs preserved and an
            # error surface on the code field. Do NOT proceed to create
            # an engagement.
            from questionnaire.naics_catalog import SECTORS as NAICS_SECTORS
            return render(
                request,
                "questionnaire/start.html",
                {
                    "prefill_code": submitted_code,
                    "prefill_values": values,
                    "naics_sectors": NAICS_SECTORS,
                    "access_code_error": (
                        "That code is not recognized, has already been "
                        "fully redeemed, or has expired. Double-check "
                        "the code or continue without one."
                    ),
                },
                status=400,
            )

    try:
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
                    annual_revenue=values["annual_revenue"],
                    geographic_footprint=values["geographic_footprint"],
                    access_code_row=access_code_row,
                )
    except ValueError as exc:
        # Currently the only ValueError services raises is the
        # access_code_exhausted race. Re-render the form with a friendly
        # error rather than blow up.
        if str(exc) == "access_code_exhausted":
            from questionnaire.naics_catalog import SECTORS as NAICS_SECTORS
            return render(
                request,
                "questionnaire/start.html",
                {
                    "prefill_values": values,
                    "naics_sectors": NAICS_SECTORS,
                    "access_code_error": (
                        "That code was just fully redeemed by another "
                        "user before you finished submitting. Try a "
                        "different code or continue without one."
                    ),
                },
                status=409,
            )
        raise

    request.session["respondent_id"] = rid

    # Fire-and-forget resume-link email. The user gets a 30-day-valid
    # personal link so they can pick up from any device, any time. Non-
    # fatal: any failure is logged to events.resume_link_sent; the
    # browser session cookie still lets this tab continue.
    try:
        send_resume_email_async(
            respondent_id=rid,
            email=values["email"],
            name=values["name"],
            company=values["company_name"],
        )
    except Exception:  # noqa: BLE001
        # Belt and suspenders - the async wrapper already catches, but
        # do not let anything here block the redirect.
        pass

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