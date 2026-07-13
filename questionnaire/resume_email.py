"""Send-a-resume-link email helper.

Fires on questionnaire start (see questionnaire/views.py::start). Mints a
30-day HMAC-signed resume token via questionnaire.session.make_resume_token,
builds the branded resume URL from settings.PLATFORM_BASE_URL, POSTs to
Postmark, and logs the outcome to the events table.

Design:
    * Fire-and-forget: called from a daemon thread in views.py so the
      HTTP response to the user is not blocked on Postmark latency.
    * Non-fatal: any exception is caught and logged as an event; the
      user's session proceeds regardless. If email fails they still
      have the browser session cookie to continue in this tab.
    * Idempotency: this helper is invoked once at start. If we later add
      a "resend resume link" button, that path can call this same helper.

Env vars honored (both must be set for delivery):
    POSTMARK_SERVER_TOKEN   - Postmark server API token
    REPORT_FROM_EMAIL       - From address (defaults to reports@srjconsultingservices.com)
    PLATFORM_BASE_URL       - Public site URL (e.g., https://aiauditforcompanies.com)
"""

from __future__ import annotations

import base64
import json
import os
import traceback
import urllib.error
import urllib.request

from django.conf import settings
from django.db import connection

from questionnaire.session import make_resume_token


POSTMARK_API_URL = "https://api.postmarkapp.com/email"
DEFAULT_FROM = "reports@srjconsultingservices.com"

EMAIL_SUBJECT = "Your AI Audit resume link - come back any time in the next 30 days"

EMAIL_BODY = (
    "Hi {name},\n\n"
    "Thanks for starting the AI Audit for {company}. This email is your\n"
    "personal resume link - use it any time in the next 30 days to pick up\n"
    "exactly where you left off, from any device.\n\n"
    "Resume link:\n"
    "{resume_url}\n\n"
    "The link is unique to you. If you close your browser or switch devices,\n"
    "just open this email and click the link.\n\n"
    "Questions? Reply to this email.\n\n"
    "- SRJ Consulting & Services LLC\n"
    "  aiauditforcompanies.com\n"
)


def _log_event(event_type: str, payload: dict) -> None:
    """Insert an events row. Uses a fresh cursor so it's safe from any thread."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO events (id, event_type, payload) "
                "VALUES (gen_random_uuid(), %s, %s::jsonb)",
                [event_type, json.dumps(payload)],
            )
    except Exception:  # noqa: BLE001
        # Logging must never crash the caller.
        pass


def build_resume_url(respondent_id: str) -> str:
    """Public helper: mint token + build the full branded resume URL."""
    token = make_resume_token(respondent_id)
    base = getattr(settings, "PLATFORM_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/q/resume/{token}/"


def send_resume_email(
    respondent_id: str,
    email: str,
    name: str,
    company: str,
    engagement_id: str | None = None,
) -> tuple[bool, str]:
    """Send the resume-link email. Returns (ok, detail)."""
    try:
        resume_url = build_resume_url(respondent_id)
    except Exception as exc:  # noqa: BLE001
        detail = f"token_build_failed: {type(exc).__name__}: {exc}"
        _log_event("resume_link_sent", {
            "respondent_id": respondent_id,
            "engagement_id": engagement_id,
            "email": email,
            "status": "failed",
            "detail": detail,
        })
        return False, detail

    token = os.environ.get("POSTMARK_SERVER_TOKEN", "")
    if not token:
        detail = "POSTMARK_SERVER_TOKEN not set - resume email skipped"
        _log_event("resume_link_sent", {
            "respondent_id": respondent_id,
            "engagement_id": engagement_id,
            "email": email,
            "resume_url": resume_url,
            "status": "skipped_no_token",
            "detail": detail,
        })
        return False, detail

    from_email = os.environ.get("REPORT_FROM_EMAIL", DEFAULT_FROM)
    payload = {
        "From": from_email,
        "To": email,
        "Subject": EMAIL_SUBJECT,
        "TextBody": EMAIL_BODY.format(
            name=name or "there",
            company=company or "your company",
            resume_url=resume_url,
        ),
        "MessageStream": "outbound",
    }

    req = urllib.request.Request(
        POSTMARK_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": token,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            _log_event("resume_link_sent", {
                "respondent_id": respondent_id,
                "engagement_id": engagement_id,
                "email": email,
                "resume_url": resume_url,
                "status": "delivered",
                "postmark_response": body[:500],
            })
            return True, body[:500]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:500] if hasattr(exc, "read") else ""
        detail = f"HTTP {exc.code}: {body}"
        _log_event("resume_link_sent", {
            "respondent_id": respondent_id,
            "engagement_id": engagement_id,
            "email": email,
            "resume_url": resume_url,
            "status": "failed",
            "detail": detail,
        })
        return False, detail
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        _log_event("resume_link_sent", {
            "respondent_id": respondent_id,
            "engagement_id": engagement_id,
            "email": email,
            "resume_url": resume_url,
            "status": "failed",
            "detail": detail,
            "traceback": traceback.format_exc()[:1000],
        })
        return False, detail


def send_resume_email_async(
    respondent_id: str,
    email: str,
    name: str,
    company: str,
    engagement_id: str | None = None,
) -> None:
    """Fire-and-forget: spawn a daemon thread that sends the resume email.

    Called from the start view so the user's HTTP response is not blocked
    on Postmark latency. Any error is caught by send_resume_email and logged
    to events; the request path never sees an exception from here.
    """
    import threading

    def _run():
        try:
            send_resume_email(
                respondent_id=respondent_id,
                email=email,
                name=name,
                company=company,
                engagement_id=engagement_id,
            )
        finally:
            # A background thread gets its own DB connection; close it.
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass

    t = threading.Thread(target=_run, name="send_resume_email", daemon=True)
    t.start()
