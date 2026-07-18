"""Report generation orchestrator.

Ties together:
- reports.report_render (scoring contexts -> real tier1 snapshot HTML)
- reports.generator.generate_locked_report (WeasyPrint + pypdf pipeline)
- reports table INSERT (persistence metadata)
- engagements.lifecycle.build_first_generation_update (Draft->Editable) or
  regeneration (Editable stays Editable, generation_count++)

Sprint R: content_html now comes from the scoring-driven template renderer.
The old placeholder is retained only as a logged fallback if rendering fails.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from engagements import lifecycle
from reports import generator

logger = logging.getLogger(__name__)


def _get_engagement(cursor, engagement_id: str) -> tuple[str, str, int]:
    """Return (snapshot_state, company_id, generation_count) or raise."""
    cursor.execute(
        "SELECT snapshot_state, company_id, generation_count "
        "FROM engagements WHERE id = %s",
        (engagement_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"engagement {engagement_id} not found")
    return row[0], str(row[1]), int(row[2] or 0)


def _count_responses(cursor, engagement_id: str) -> int:
    cursor.execute(
        "SELECT COUNT(*) FROM responses r "
        "JOIN respondents rs ON r.respondent_id = rs.id "
        "WHERE rs.engagement_id = %s",
        (engagement_id,),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def _render_placeholder_content(engagement_id: str, response_count: int) -> str:
    """Fallback content if the real renderer fails."""
    return (
        f"<h1>AI Audit Snapshot</h1>"
        f"<p>Engagement ID: {engagement_id}</p>"
        f"<p>Responses recorded: {response_count}</p>"
        f"<p>Report rendering encountered an error; this is a fallback "
        f"document. Contact support@aiauditforcompanies.com.</p>"
    )


def _render_content(cursor, engagement_id: str) -> str:
    """Real snapshot content via scoring engine; placeholder on failure."""
    try:
        from reports.report_render import render_tier1_snapshot_html
        return render_tier1_snapshot_html(engagement_id)
    except Exception:
        logger.exception("tier1 snapshot render failed; using placeholder")
        response_count = _count_responses(cursor, engagement_id)
        return _render_placeholder_content(engagement_id, response_count)


def _insert_report(
    cursor,
    company_id: str,
    engagement_id: str,
    framework: str,
    pdf_bytes: bytes,
    buyer_email: str,
    generated_at: datetime,
) -> str:
    cursor.execute(
        "INSERT INTO reports "
        "(company_id, engagement_id, framework, report_type, file_path, "
        " file_size_bytes, generated_at, delivered_to_email, download_count) "
        "VALUES (%s, %s, %s, 'tier_1_snapshot', %s, %s, %s, %s, 0) "
        "RETURNING id",
        (
            company_id,
            engagement_id,
            framework,
            f"inline://{engagement_id}",
            len(pdf_bytes),
            generated_at,
            buyer_email,
        ),
    )
    return str(cursor.fetchone()[0])


def _apply_first_generation(
    cursor,
    engagement_id: str,
    state: str,
    report_id: str,
    pdf_hash: str,
    now: datetime,
) -> None:
    update = lifecycle.build_first_generation_update(state, now=now)
    cursor.execute(
        "UPDATE engagements SET "
        "snapshot_state = %s, "
        "first_generation_timestamp = %s, "
        "window_end_timestamp = %s, "
        "generation_count = %s, "
        "report_of_record_id = %s, "
        "report_of_record_pdf_hash = %s "
        "WHERE id = %s",
        (
            update["snapshot_state"],
            update["first_generation_timestamp"],
            update["window_end_timestamp"],
            update["generation_count"],
            report_id,
            pdf_hash,
            engagement_id,
        ),
    )


def _apply_regeneration(
    cursor,
    engagement_id: str,
    report_id: str,
    pdf_hash: str,
) -> None:
    cursor.execute(
        "UPDATE engagements SET "
        "generation_count = generation_count + 1, "
        "report_of_record_id = %s, "
        "report_of_record_pdf_hash = %s "
        "WHERE id = %s",
        (report_id, pdf_hash, engagement_id),
    )


def generate_and_lock(
    cursor,
    engagement_id: str,
    buyer_email: str,
    owner_password: str,
    framework: str = "tier_1",
    now: Optional[datetime] = None,
) -> tuple[str, bytes, str]:
    """Generate PDF report + apply lifecycle transition.

    Draft: transitions to Editable, sets first_generation_timestamp and
    window_end_timestamp, generation_count=1.

    Editable: increments generation_count, updates report_of_record.

    Locked/Expired: raises ValueError.

    Returns (report_id, pdf_bytes, sha256_hash).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    state, company_id, _gen_count = _get_engagement(cursor, engagement_id)
    if state in (lifecycle.LOCKED, lifecycle.EXPIRED):
        raise ValueError(
            f"cannot generate report in state {state} — snapshot is terminal"
        )

    content_html = _render_content(cursor, engagement_id)

    pdf_bytes, pdf_hash = generator.generate_locked_report(
        content_html=content_html,
        buyer_email=buyer_email,
        snapshot_id=engagement_id,
        generated_at=now,
        owner_password=owner_password,
    )

    report_id = _insert_report(
        cursor, company_id, engagement_id, framework, pdf_bytes, buyer_email, now
    )

    # Phase 2e: persist the PDF to Cloudflare R2 (non-fatal). Replace the
    # inline:// placeholder with the real object key so the report can be
    # re-downloaded later. If R2 is down/unset, generation still succeeds.
    try:
        from reports import storage
        _r2_key = storage.upload_report_pdf(engagement_id, report_id, pdf_bytes)
        if _r2_key:
            cursor.execute(
                "UPDATE reports SET file_path = %s WHERE id = %s",
                (f"r2://{_r2_key}", report_id),
            )
    except Exception:  # noqa: BLE001
        logger.exception("r2 persist failed for report %s (non-fatal)", report_id)

    if state == lifecycle.DRAFT:
        _apply_first_generation(cursor, engagement_id, state, report_id, pdf_hash, now)
    elif state == lifecycle.EDITABLE:
        _apply_regeneration(cursor, engagement_id, report_id, pdf_hash)

    return report_id, pdf_bytes, pdf_hash