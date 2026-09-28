"""Buyer-facing respondent management for multi-respondent engagements.

Auth model for this sprint: a buyer reaches their engagement through a
signed magic link (/e/<token>/) that binds the engagement id into the
session, exactly as respondents and Tier 1 resume links already do.
Staff (Django admin login) can manage any engagement. Full buyer
accounts (Part B-1 S.1.2) are a later sprint; nothing here will need to
change when they arrive except _can_manage().

Confidentiality rule (B-1 S.1.2, enforced HERE, not in the template): the
buyer sees status and progress counts per respondent, never answers.
"""

from __future__ import annotations

from django.contrib import messages
from django.db import connection
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from engagements import coverage, invitations
from questionnaire import session as session_module

SESSION_KEY = "buyer_engagements"


def _can_manage(request, engagement_id: str) -> bool:
    if getattr(request.user, "is_staff", False):
        return True
    return str(engagement_id) in (request.session.get(SESSION_KEY) or [])


def _guard(request, engagement_id):
    if not _can_manage(request, str(engagement_id)):
        return HttpResponseForbidden("This engagement is not open in your session. Use the link from your email.")
    return None


@require_http_methods(["GET"])
def buyer_link(request, token: str):
    """Magic link for the buyer: binds the engagement into the session."""
    engagement_id = session_module.parse_resume_token(token, max_age_seconds=180 * 24 * 3600)
    if engagement_id is None:
        raise Http404("link invalid or expired")
    ids = set(request.session.get(SESSION_KEY) or [])
    ids.add(str(engagement_id))
    request.session[SESSION_KEY] = sorted(ids)
    return redirect("engagements:respondents", engagement_id=engagement_id)


@require_http_methods(["GET"])
def respondents(request, engagement_id):
    if (deny := _guard(request, engagement_id)):
        return deny
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT e.tier, e.snapshot_state::text, e.coverage_met_at, e.extension_count,
                   c.name, c.size_bracket, e.payment_status, e.price_cents,
                   lower(coalesce(u.email, ''))
            FROM engagements e LEFT JOIN companies c ON c.id = e.company_id
            LEFT JOIN users u ON u.id = e.buyer_user_id
            WHERE e.id = %s
            """,
            [str(engagement_id)],
        )
        row = cursor.fetchone()
        if row is None:
            raise Http404
        tier, state, met_at, ext, company, bracket, payment_status, price_cents, buyer_email = row
        cov = coverage.check_coverage(cursor, str(engagement_id))
        cursor.execute(
            """
            SELECT id::text, name, email, role, title, status,
                   coalesce(completion_percentage, 0), attestation_signed_at IS NOT NULL,
                   invitation_sent_at, last_activity_at, last_nudged_at
            FROM respondents
            WHERE engagement_id = %s AND status <> 'removed'
            ORDER BY created_at
            """,
            [str(engagement_id)],
        )
        rows = [{
            "id": r[0], "name": r[1], "email": r[2], "role": r[3],
            "role_label": invitations.ROLE_LABELS.get(r[3], r[3]), "title": r[4],
            "status": r[5], "percent": int(float(r[6]) * 100), "attested": r[7],
            "invited_at": r[8], "last_activity": r[9], "last_nudged": r[10],
            "counts": float(r[6]) >= coverage.MIN_COMPLETION and r[7],
            # the buyer's own row gets a direct link to answer for their role
            "own_link": (invitations.build_magic_link(r[0])
                         if buyer_email and (r[2] or "").lower() == buyer_email and r[5] != "completed" else None),
        } for r in cursor.fetchall()]
    req = coverage.REQUIREMENTS.get(bracket or "")
    return render(request, "engagements/respondents.html", {
        "engagement_id": str(engagement_id), "tier": tier, "state": state,
        "company": company, "size_bracket": bracket, "coverage": cov,
        "coverage_met_at": met_at, "extension_count": ext or 0,
        "respondents": rows, "roles": invitations.ROLE_LABELS,
        "payment_status": payment_status, "paid": payment_status in ("paid", "comped"),
        "price_label": (f"${(price_cents or 0) / 100:,.0f}" if price_cents else ""),
        "just_paid": request.GET.get("paid") == "1",
        "required_roles": [(label, n) for label, _, n in (req["roles"] if req else [])],
        "min_completion_pct": int(coverage.MIN_COMPLETION * 100),
    })


@require_http_methods(["POST"])
def add_respondent(request, engagement_id):
    if (deny := _guard(request, engagement_id)):
        return deny
    with connection.cursor() as cursor:
        cursor.execute("SELECT payment_status FROM engagements WHERE id = %s", [str(engagement_id)])
        _ps = cursor.fetchone()
    if _ps and _ps[0] not in ("paid", "comped", "free"):
        messages.error(request, "Complete payment before inviting respondents.")
        return redirect("engagements:respondents", engagement_id=engagement_id)
    try:
        with connection.cursor() as cursor:
            rid = invitations.create_respondent(
                cursor, str(engagement_id),
                email=request.POST.get("email", ""), name=request.POST.get("name", ""),
                role=request.POST.get("role", ""), title=request.POST.get("title", ""),
                personal_note=request.POST.get("note", ""),
            )
            ok, detail = invitations.send_invitation(cursor, rid)
        if ok:
            messages.success(request, f"Invitation sent to {request.POST.get('email')}.")
        else:
            messages.warning(request, f"Respondent added but the invitation email failed: {detail}. Use Nudge to retry.")
    except invitations.InvitationError as exc:
        messages.error(request, str(exc))
    return redirect("engagements:respondents", engagement_id=engagement_id)


# ----------------------------------------------------------------------------
# Automatic reminders: called by the srj-platform-monitor Worker's daily cron.
# ----------------------------------------------------------------------------

@csrf_exempt
@require_POST
def run_reminders(request):
    """POST /e/reminders/run/  with header X-Reminder-Key.

    The key lives in REMINDER_RUN_KEY (platform.env) and as a secret on the
    monitor Worker. An unset key disables the endpoint rather than opening
    it. Response is the run summary so the Worker can push a ntfy alert on
    failures.
    """
    import hmac
    import os

    expected = os.environ.get("REMINDER_RUN_KEY", "")
    provided = request.headers.get("X-Reminder-Key", "")
    if not expected or not hmac.compare_digest(expected, provided):
        raise Http404
    from engagements.reminders import run
    with connection.cursor() as cursor:
        summary = run(cursor)
    return JsonResponse(summary)


@require_http_methods(["POST"])
def nudge_respondent(request, engagement_id, respondent_id):
    if (deny := _guard(request, engagement_id)):
        return deny
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM respondents WHERE id=%s AND engagement_id=%s",
                           [str(respondent_id), str(engagement_id)])
            if not cursor.fetchone():
                raise Http404
            ok, detail = invitations.nudge(cursor, str(respondent_id))
        (messages.success if ok else messages.warning)(request, "Reminder sent." if ok else detail)
    except invitations.InvitationError as exc:
        messages.error(request, str(exc))
    return redirect("engagements:respondents", engagement_id=engagement_id)


@require_http_methods(["POST"])
def remove_respondent(request, engagement_id, respondent_id):
    if (deny := _guard(request, engagement_id)):
        return deny
    try:
        with connection.cursor() as cursor:
            invitations.remove_respondent(cursor, str(engagement_id), str(respondent_id))
        messages.success(request, "Respondent removed.")
    except invitations.InvitationError as exc:
        messages.error(request, str(exc))
    return redirect("engagements:respondents", engagement_id=engagement_id)


# ----------------------------------------------------------------------------
# Buyer login: the magic link IS the account. /e/login/ re-sends it.
# ----------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def buyer_login(request):
    sent = False
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        if email:
            with connection.cursor() as cursor:
                try:
                    invitations.send_buyer_login_links(cursor, email)
                except Exception:  # noqa: BLE001
                    pass
        sent = True   # same answer whether or not the address exists
    return render(request, "engagements/login.html", {"sent": sent})
