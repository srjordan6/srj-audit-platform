"""Automatic report generation + email delivery on questionnaire completion.

Phase 2c. When a respondent answers their final question:

1. `on_respondent_complete(respondent_id)` is called from
   questionnaire.views.submit_response. It stamps respondents.completed_at
   and engagements.completed_at (idempotent - first caller wins), then
   spawns a daemon thread and returns immediately so the respondent sees
   the completion page with zero delay.
2. The thread generates the report via reports.services.generate_and_lock
   (scoring + AI narrative + opinion basis + WeasyPrint, ~2-4 minutes on
   first generation) and emails the PDF to the respondent via Postmark.
3. Every attempt is logged to the events table
   (event_type='report_delivery') so delivery can be audited via SQL.

Environment variables (set in Render):
  POSTMARK_SERVER_TOKEN   Postmark server API token. Empty = email skipped
                          (generation still runs and is logged).
  REPORT_FROM_EMAIL       Verified Postmark sender signature.
                          Default: reports@aiauditforcompanies.com
  REPORT_OWNER_PASSWORD   PDF owner password for generate_and_lock.
                          Default: derived from SECRET_KEY.

Design guarantees:
- Never raises into the request cycle: every failure is caught + logged.
- Idempotent: a second call for the same respondent is a no-op, so a page
  reload on the completion screen cannot double-send.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import urllib.request
from datetime import datetime, timezone

from django.conf import settings

logger = logging.getLogger(__name__)

POSTMARK_API_URL = "https://api.postmarkapp.com/email"
DEFAULT_FROM = "reports@aiauditforcompanies.com"

EMAIL_SUBJECT = "Your AI Audit Snapshot report is ready"
EMAIL_BODY = (
    "Hello {name},\n\n"
    "Thank you for completing the AI Audit questionnaire for {company}.\n\n"
    "Your Tier 1 AI Audit Snapshot report is attached to this email as a "
    "PDF. It contains the audit findings, readiness scorecard, risk and "
    "governance review, efficiency analysis, and the auditor's opinion "
    "with its full basis.\n\n"
    "If you have any questions about your report, reply to this email.\n\n"
    "SRJ AI Audit Platform\n"
)


def _log_event(cursor, payload: dict) -> None:
    cursor.execute(
        "INSERT INTO events (id, event_type, payload) "
        "VALUES (gen_random_uuid(), 'report_delivery', %s::jsonb)",
        [json.dumps(payload, default=str)],
    )


def _mark_complete(cursor, respondent_id: str):
    """Stamp completed_at on respondent + engagement. Returns
    (engagement_id, email, name, company_name) if this call performed the
    transition, or None if already completed (idempotency guard)."""
    cursor.execute(
        "UPDATE respondents SET completed_at = NOW(), status = 'completed' "
        "WHERE id = %s AND completed_at IS NULL "
        "RETURNING engagement_id, email, name",
        [respondent_id],
    )
    row = cursor.fetchone()
    if row is None:
        return None  # already completed earlier - do not re-trigger
    engagement_id, email, name = str(row[0]), row[1], row[2]
    cursor.execute(
        "UPDATE engagements SET completed_at = COALESCE(completed_at, NOW()) "
        "WHERE id = %s",
        [engagement_id],
    )
    cursor.execute(
        "SELECT c.name FROM companies c "
        "JOIN engagements e ON e.company_id = c.id WHERE e.id = %s",
        [engagement_id],
    )
    crow = cursor.fetchone()
    company_name = crow[0] if crow else ""
    return engagement_id, email, name, company_name


def _send_postmark(to_email: str, name: str, company: str,
                   pdf_bytes: bytes, engagement_id: str) -> tuple[bool, str]:
    token = os.environ.get("POSTMARK_SERVER_TOKEN", "")
    if not token:
        return False, "POSTMARK_SERVER_TOKEN not set - email skipped"
    from_email = os.environ.get("REPORT_FROM_EMAIL", DEFAULT_FROM)
    payload = {
        "From": from_email,
        "To": to_email,
        "Subject": EMAIL_SUBJECT,
        "TextBody": EMAIL_BODY.format(name=name or "there",
                                      company=company or "your company"),
        "MessageStream": "outbound",
        "Attachments": [{
            "Name": f"AI_Audit_Snapshot_{str(engagement_id)[:8]}.pdf",
            "Content": base64.b64encode(pdf_bytes).decode(),
            "ContentType": "application/pdf",
        }],
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
            return True, body[:500]
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        return False, f"HTTP {exc.code}: {exc.read().decode()[:500]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def _owner_password() -> str:
    return (os.environ.get("REPORT_OWNER_PASSWORD")
            or settings.SECRET_KEY[:32])


def _worker(engagement_id: str, email: str, name: str, company: str) -> None:
    """Background thread: generate report, mark delivered, email PDF.

    Two-phase logging: emit an event at EACH major step so a crash mid-
    pipeline pinpoints the failing step. Traceback string is captured
    into the final failure event so we don't need to correlate with
    Render live logs.
    """
    import traceback
    # A new thread gets its own DB connection; close it when done.
    from django.db import connection, transaction

    result = {
        "engagement_id": engagement_id,
        "to": email,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    def _log_step(step: str, extra=None):
        try:
            with connection.cursor() as c:
                _log_event(c, {**result, "step": step, **(extra or {})})
        except Exception:  # noqa: BLE001
            logger.exception("auto_delivery: log_step %s failed", step)

    try:
        _log_step("worker_started")
        from reports.services import generate_and_lock

        _log_step("calling_generate_and_lock")
        with transaction.atomic():
            with connection.cursor() as cursor:
                report_id, pdf_bytes, pdf_hash = generate_and_lock(
                    cursor,
                    engagement_id,
                    buyer_email=email,
                    owner_password=_owner_password(),
                )
        result["report_id"] = report_id
        result["pdf_bytes"] = len(pdf_bytes)
        result["pdf_hash"] = pdf_hash
        _log_step("pdf_generated", {"report_id": report_id, "pdf_bytes": len(pdf_bytes)})

        sent, detail = _send_postmark(email, name, company,
                                      pdf_bytes, engagement_id)
        result["email_sent"] = sent
        result["email_detail"] = detail
        _log_step("postmark_return", {"email_sent": sent, "email_detail": detail[:200] if detail else None})

        with connection.cursor() as cursor:
            if sent:
                cursor.execute(
                    "UPDATE reports SET delivered_at = NOW() WHERE id = %s",
                    [report_id],
                )
            result["status"] = "delivered" if sent else "generated_not_emailed"
            _log_event(cursor, result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("auto_delivery: generation/delivery failed for %s",
                         engagement_id)
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()[:4000]
        try:
            with connection.cursor() as cursor:
                _log_event(cursor, result)
        except Exception:  # noqa: BLE001
            logger.exception("auto_delivery: failed to log failure event")
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass


def regenerate_after_edit(cursor, respondent_id: str) -> bool:
    """Regenerate the locked PDF after an in-window answer edit.

    Distinct from on_respondent_complete (which is idempotent on
    completed_at). This path fires whenever a respondent whose
    engagement is already Editable saves an answer, so the report of
    record reflects the latest state. AI narrative is NOT re-called —
    ai_analysis._load_stored returns the cached sections from the first
    generation (per operator direction 2026-07-15: no repeat Claude
    calls on regeneration to keep cost bounded).
    """
    try:
        cursor.execute(
            "SELECT e.id, r.email, r.name, c.name, e.snapshot_state "
            "FROM respondents r "
            "JOIN engagements e ON e.id = r.engagement_id "
            "JOIN companies c ON c.id = e.company_id "
            "WHERE r.id = %s LIMIT 1",
            (respondent_id,),
        )
        row = cursor.fetchone()
    except Exception:  # noqa: BLE001
        logger.exception("regenerate_after_edit: lookup failed for %s",
                         respondent_id)
        return False
    if not row:
        return False
    engagement_id, email, name, company, state = row
    # e.id comes back as a Python UUID; downstream (_send_postmark filename)
    # slices with [:8] which fails on UUID. Cast to str at the boundary.
    engagement_id = str(engagement_id)
    # Only regenerate for engagements that are already Editable (i.e. have
    # a report of record). Draft never got past first generation. Locked /
    # Expired are terminal.
    if state != "Editable":
        return False

    _log_event(cursor, {
        "engagement_id": engagement_id,
        "to": email,
        "status": "queued_regeneration",
        "respondent_id": respondent_id,
    })
    # Bug fixed 2026-07-15 — UUID subscript in _send_postmark filename.
    # Flip back to daemon thread so edits feel snappy again.
    thread = threading.Thread(
        target=_worker,
        args=(engagement_id, email, name, company),
        daemon=True,
        name=f"report-regen-{engagement_id[:8]}",
    )
    thread.start()
    return True


def on_respondent_complete(cursor, respondent_id: str) -> bool:
    """Call when the respondent has no next question. Returns True if this
    call triggered generation+delivery, False if it was already done.

    Runs on the request's cursor for the completed_at stamp (fast), then
    hands the slow work (report + email) to a daemon thread.
    """
    try:
        info = _mark_complete(cursor, respondent_id)
    except Exception:  # noqa: BLE001
        logger.exception("auto_delivery: completion stamp failed for %s",
                         respondent_id)
        return False
    if info is None:
        return False
    engagement_id, email, name, company = info
    _log_event(cursor, {
        "engagement_id": engagement_id,
        "to": email,
        "status": "queued",
        "respondent_id": respondent_id,
    })
    thread = threading.Thread(
        target=_worker,
        args=(engagement_id, email, name, company),
        daemon=True,
        name=f"report-delivery-{engagement_id[:8]}",
    )
    thread.start()
    return True
