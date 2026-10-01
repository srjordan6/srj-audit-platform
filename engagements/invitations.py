"""Multi-respondent invitations (Part B-1 S.4).

Buyer adds a respondent -> Respondent row (no User account, status
'invited') -> Postmark invitation carrying a signed magic link ->
respondent clicks /r/<token>/ -> session bound to that respondent ->
attestation -> role-gated questions.

Tokens reuse questionnaire.session (HMAC + timestamp): 30 days from
invitation_sent_at, extendable by the buyer in 30-day steps to 90
(engagements.extension_count). Tokens are NOT rotated on use, by design
(B-1 S.4.1): respondents resume from the same email link.

Every send is logged to events (respondent_invitation) so delivery can
be read back without asking anyone to paste anything.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from questionnaire import flow, session as session_module
from questionnaire.resume_email import _log_event

logger = logging.getLogger(__name__)

POSTMARK_API_URL = "https://api.postmarkapp.com/email"
DEFAULT_FROM = "reports@srjconsultingservices.com"
DEFAULT_REPLY_TO = "srj@srjconsultingservices.com"   # a mailbox a human reads; reports@ bounces (defect B7)
BASE_DAYS = 30
EXTENSION_DAYS = 30
MAX_EXTENSIONS = 2
NUDGE_COOLDOWN = timedelta(hours=24)

ROLE_LABELS = {
    "BOARD": "Board member", "CEO": "CEO", "CFO": "CFO / Finance lead",
    "CIO": "CIO", "CISO": "CISO / Security lead", "COO": "COO / Operations lead",
    "VP": "Vice President", "DIR": "Director", "MGR": "Manager",
    "IC": "Individual contributor", "HR": "HR lead",
}

INVITE_SUBJECT = "{buyer} has invited you to contribute to an AI audit"
INVITE_BODY = """Hi {name},

{buyer} at {company} has asked you to contribute to an AI audit of the
company. Your part is a questionnaire about how AI is actually used and
governed where you work.

  Your role in the audit: {role_label}
  Questions for your role:  approximately {count}
  Time:                     about {minutes} minutes, and you can stop and
                            resume from this same link.

Your answers are confidential to the audit platform. {buyer} sees only
whether you have started, are in progress, or have finished. Nobody at
{company} sees your individual answers. The report aggregates and
anonymizes.
{note_block}
Start here (link valid for {days} days):
{url}

If you have questions, reply to this email.

SRJ Consulting & Services LLC
"""

NUDGE_SUBJECT = "Reminder: {buyer} is waiting on your part of the AI audit"
NUDGE_BODY = """Hi {name},

A quick reminder that {buyer} at {company} is waiting on your questionnaire
for the AI audit. It takes about {minutes} minutes and you can pick up
where you left off:

{url}

SRJ Consulting & Services LLC
"""


class InvitationError(Exception):
    pass


def _estimate(role: str, instrument: str = "tier_1") -> tuple[int, int]:
    """Question count and minutes for a role, from the live bank."""
    try:
        n = len(flow.questions_visible_to_role(role, {}, instrument))
    except Exception:  # noqa: BLE001
        n = 100
    return n, max(10, round(n * 0.33))


def build_magic_link(respondent_id: str) -> str:
    base = os.environ.get("PLATFORM_BASE_URL", "https://aiauditforcompanies.com").rstrip("/")
    return f"{base}/r/{session_module.make_resume_token(respondent_id)}/"


def token_max_age_seconds(extension_count: int) -> int:
    days = BASE_DAYS + EXTENSION_DAYS * min(int(extension_count or 0), MAX_EXTENSIONS)
    return days * 24 * 3600


AUDIT_LABELS = {"combined": "Both audits", "tier_1": "AI Audit Snapshot (governance)",
                "aiitsa": "AI IT Security Audit"}


def create_respondent(cursor, engagement_id: str, *, email: str, name: str,
                      role: str, title: str | None = None,
                      personal_note: str | None = None,
                      audits: str | None = None) -> str:
    """audits (OD-19 Tier 2 routing): on a combined engagement the buyer
    invites each person to tier_1, aiitsa or combined; on a single-audit
    engagement it is always the engagement's instrument."""
    role = (role or "").upper().strip()
    if role not in ROLE_LABELS:
        raise InvitationError(f"unknown role {role!r}")
    email = (email or "").strip().lower()
    if "@" not in email:
        raise InvitationError("a valid email address is required")
    name = (name or "").strip()
    if not name:
        raise InvitationError("a name is required")

    cursor.execute("SELECT company_id, coalesce(instrument, 'tier_1') FROM engagements WHERE id = %s", [engagement_id])
    row = cursor.fetchone()
    if row is None:
        raise InvitationError("engagement not found")
    company_id, instrument = row
    audits = (audits or "").strip().lower() or None
    if instrument != "combined":
        audits = None                      # single audit: nothing to route
    elif audits not in (None, "combined", "tier_1", "aiitsa"):
        raise InvitationError(f"unknown audit selection {audits!r}")

    cursor.execute(
        """
        SELECT id FROM respondents
        WHERE engagement_id = %s AND lower(email) = %s AND status <> 'removed'
        """,
        [engagement_id, email],
    )
    if cursor.fetchone():
        raise InvitationError(f"{email} is already a respondent on this engagement")

    cursor.execute(
        """
        INSERT INTO respondents
            (engagement_id, company_id, email, name, role, title,
             buyer_personal_note, status, invitation_sent_at, audits)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'invited', NULL, %s)
        RETURNING id::text
        """,
        [engagement_id, company_id, email, name, role, title or None,
         (personal_note or "")[:500] or None, audits],
    )
    return cursor.fetchone()[0]


def _postmark(payload: dict) -> tuple[bool, str]:
    token = os.environ.get("POSTMARK_SERVER_TOKEN", "")
    if not token:
        return False, "POSTMARK_SERVER_TOKEN not set"
    req = urllib.request.Request(
        POSTMARK_API_URL, data=json.dumps(payload).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "X-Postmark-Server-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, resp.read().decode()[:500]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:500] if hasattr(exc, "read") else ""
        return False, f"HTTP {exc.code}: {body}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def _context(cursor, respondent_id: str) -> dict:
    cursor.execute(
        """
        SELECT r.email, r.name, r.role, r.buyer_personal_note, r.engagement_id::text,
               c.name, coalesce(nullif(u.name, ''), u.email),
               e.extension_count, coalesce(r.audits, e.instrument, 'tier_1')
        FROM respondents r
        JOIN engagements e ON e.id = r.engagement_id
        LEFT JOIN companies c ON c.id = e.company_id
        LEFT JOIN users u ON u.id = e.buyer_user_id
        WHERE r.id = %s
        """,
        [respondent_id],
    )
    row = cursor.fetchone()
    if row is None:
        raise InvitationError("respondent not found")
    email, name, role, note, engagement_id, company, buyer, ext, instrument = row
    count, minutes = _estimate(role, instrument)
    return {
        "email": email, "name": name or "there", "role": role,
        "role_label": ROLE_LABELS.get(role, role), "note": note,
        "engagement_id": engagement_id, "company": company or "your company",
        "buyer": (buyer or "The buyer").strip(), "count": count, "minutes": minutes,
        "days": BASE_DAYS + EXTENSION_DAYS * min(int(ext or 0), MAX_EXTENSIONS),
    }


def send_invitation(cursor, respondent_id: str) -> tuple[bool, str]:
    ctx = _context(cursor, respondent_id)
    url = build_magic_link(respondent_id)
    note_block = f"\nA note from {ctx['buyer']}:\n\n    {ctx['note']}\n" if ctx["note"] else ""
    ok, detail = _postmark({
        "From": os.environ.get("REPORT_FROM_EMAIL", DEFAULT_FROM),
        "ReplyTo": os.environ.get("REPLY_TO_EMAIL", DEFAULT_REPLY_TO),
        "To": ctx["email"],
        "Subject": INVITE_SUBJECT.format(buyer=ctx["buyer"]),
        "TextBody": INVITE_BODY.format(url=url, note_block=note_block, **ctx),
        "MessageStream": "outbound",
    })
    if ok:
        cursor.execute(
            "UPDATE respondents SET invitation_sent_at = NOW() WHERE id = %s",
            [respondent_id],
        )
    _log_event("respondent_invitation", {
        "respondent_id": respondent_id, "engagement_id": ctx["engagement_id"],
        "email": ctx["email"], "role": ctx["role"],
        "status": "delivered" if ok else "failed", "detail": detail,
    })
    return ok, detail


def nudge(cursor, respondent_id: str) -> tuple[bool, str]:
    """Buyer-triggered reminder, rate-limited to one per 24h (B-1 S.4.3)."""
    cursor.execute(
        "SELECT last_nudged_at, status FROM respondents WHERE id = %s", [respondent_id]
    )
    row = cursor.fetchone()
    if row is None:
        raise InvitationError("respondent not found")
    last, status = row
    if status in ("completed", "removed"):
        return False, f"respondent is {status}"
    if last and timezone.now() - last < NUDGE_COOLDOWN:
        return False, "already nudged in the last 24 hours"
    ctx = _context(cursor, respondent_id)
    ok, detail = _postmark({
        "From": os.environ.get("REPORT_FROM_EMAIL", DEFAULT_FROM),
        "ReplyTo": os.environ.get("REPLY_TO_EMAIL", DEFAULT_REPLY_TO),
        "To": ctx["email"],
        "Subject": NUDGE_SUBJECT.format(buyer=ctx["buyer"]),
        "TextBody": NUDGE_BODY.format(url=build_magic_link(respondent_id), **ctx),
        "MessageStream": "outbound",
    })
    if ok:
        cursor.execute(
            "UPDATE respondents SET last_nudged_at = NOW(), reminder_count = coalesce(reminder_count,0)+1 WHERE id = %s",
            [respondent_id],
        )
    _log_event("respondent_nudge", {
        "respondent_id": respondent_id, "engagement_id": ctx["engagement_id"],
        "status": "delivered" if ok else "failed", "detail": detail,
    })
    return ok, detail


def remove_respondent(cursor, engagement_id: str, respondent_id: str) -> None:
    cursor.execute(
        """
        UPDATE respondents SET status = 'removed'
        WHERE id = %s AND engagement_id = %s AND status <> 'completed'
        """,
        [respondent_id, engagement_id],
    )
    if cursor.rowcount == 0:
        raise InvitationError("respondent not found, or already completed (completed respondents cannot be removed)")


# ----------------------------------------------------------------------------
# Buyer notification on each respondent completion (Part B-1 S.4.5)
# ----------------------------------------------------------------------------

BUYER_PROGRESS_SUBJECT = "{company} AI audit: {done} of {total} respondents complete"
BUYER_PROGRESS_BODY = """Hi {buyer},

{respondent_name} ({role}) has just completed their part of the {company} AI audit.

Progress: {done} of {total} invited respondents complete.
{coverage_line}

Manage respondents, nudge stragglers or add people here:
{url}

This link is private to you and stays valid for 180 days.

SRJ Consulting & Services
"""


def build_buyer_link(engagement_id: str) -> str:
    base = os.environ.get("BASE_URL", "https://aiauditforcompanies.com").rstrip("/")
    return f"{base}/e/link/{session_module.make_resume_token(str(engagement_id))}/"


def notify_buyer_progress(cursor, engagement_id: str, respondent_id: str, cov) -> tuple[bool, str]:
    """Tell the buyer one more respondent finished and what coverage still
    needs. Called from the completion path for Tier 2/3 when coverage is
    not yet met (the report email itself covers the met case)."""
    cursor.execute(
        """
        SELECT u.email, coalesce(nullif(u.name, ''), u.email), c.name,
               r.name, r.role,
               (SELECT count(*) FROM respondents x WHERE x.engagement_id = e.id
                   AND coalesce(x.status,'invited') <> 'removed'),
               (SELECT count(*) FROM respondents x WHERE x.engagement_id = e.id
                   AND x.status = 'completed')
        FROM engagements e
        JOIN users u ON u.id = e.buyer_user_id
        LEFT JOIN companies c ON c.id = e.company_id
        JOIN respondents r ON r.id = %s
        WHERE e.id = %s
        """,
        [respondent_id, engagement_id],
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return False, "no buyer email"
    buyer_email, buyer_name, company, rname, role, total, done = row
    if cov.is_met:
        coverage_line = "Coverage is met: the compiled report is being generated now."
    else:
        needs = "; ".join(cov.missing_items[:4]) if cov.missing_items else "more respondents"
        coverage_line = f"Still needed before the report can be compiled: {needs}."
    ctx = {"buyer": buyer_name, "company": company or "your company", "respondent_name": rname,
           "role": role, "done": done, "total": total, "coverage_line": coverage_line,
           "url": build_buyer_link(engagement_id)}
    ok, msg = _postmark({
        "From": os.environ.get("REPORT_FROM_EMAIL", DEFAULT_FROM),
        "ReplyTo": os.environ.get("REPLY_TO_EMAIL", DEFAULT_REPLY_TO),
        "To": buyer_email,
        "Subject": BUYER_PROGRESS_SUBJECT.format(**ctx),
        "TextBody": BUYER_PROGRESS_BODY.format(**ctx),
        "MessageStream": "outbound",
    })
    cursor.execute(
        "INSERT INTO events (event_type, payload) VALUES ('buyer_progress_notice', %s::jsonb)",
        [json.dumps({"engagement_id": str(engagement_id), "respondent_id": str(respondent_id),
                     "to": buyer_email, "done": done, "total": total, "coverage_met": cov.is_met,
                     "status": "delivered" if ok else "failed", "postmark": msg[:300]})],
    )
    return ok, msg


# ----------------------------------------------------------------------------
# Buyer dashboard link (after Tier 2 payment, and on request from /e/login/)
# ----------------------------------------------------------------------------

BUYER_LINK_SUBJECT = "{company} AI audit: your respondents dashboard"
BUYER_LINK_BODY = """Hi {buyer},

Your Tier 2 AI audit for {company} is ready to staff. Invite the people who will answer for their roles, watch progress, and nudge stragglers here:

{url}

This link is private to you and stays valid for 180 days. When enough respondents have completed their part, the compiled report is generated and emailed to you automatically.

SRJ Consulting & Services
"""


def send_buyer_dashboard_link(cursor, engagement_id: str) -> tuple[bool, str]:
    cursor.execute(
        """
        SELECT u.email, coalesce(nullif(u.name, ''), u.email), c.name
        FROM engagements e JOIN users u ON u.id = e.buyer_user_id
        LEFT JOIN companies c ON c.id = e.company_id WHERE e.id = %s
        """,
        [engagement_id],
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return False, "no buyer email"
    email, buyer, company = row
    ctx = {"buyer": buyer, "company": company or "your company", "url": build_buyer_link(engagement_id)}
    ok, msg = _postmark({
        "From": os.environ.get("REPORT_FROM_EMAIL", DEFAULT_FROM),
        "ReplyTo": os.environ.get("REPLY_TO_EMAIL", DEFAULT_REPLY_TO),
        "To": email,
        "Subject": BUYER_LINK_SUBJECT.format(**ctx),
        "TextBody": BUYER_LINK_BODY.format(**ctx),
        "MessageStream": "outbound",
    })
    cursor.execute(
        "INSERT INTO events (event_type, payload) VALUES ('buyer_link_sent', %s::jsonb)",
        [json.dumps({"engagement_id": str(engagement_id), "to": email,
                     "status": "delivered" if ok else "failed", "postmark": msg[:300]})],
    )
    return ok, msg


def send_buyer_login_links(cursor, email: str) -> int:
    """/e/login/: every open Tier 2/3 engagement this email bought gets a
    fresh dashboard link. Returns how many were sent; the caller never
    reveals whether the address exists."""
    cursor.execute(
        """
        SELECT e.id::text FROM engagements e JOIN users u ON u.id = e.buyer_user_id
        WHERE lower(u.email) = lower(%s) AND e.tier IN ('tier_2', 'tier_3')
          AND e.status = 'in_progress'
        ORDER BY e.created_at DESC LIMIT 10
        """,
        [email.strip()],
    )
    sent = 0
    for (eid,) in cursor.fetchall():
        ok, _ = send_buyer_dashboard_link(cursor, eid)
        sent += 1 if ok else 0
    return sent
