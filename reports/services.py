"""Report generation orchestrator (Sprint E option B).

Ties together:
- responses fetch (for content rendering)
- reports.generator.generate_locked_report (WeasyPrint + pypdf pipeline)
- reports table INSERT (persistence metadata)
- engagements.lifecycle.build_first_generation_update (Draft→Editable) or
  regeneration (Editable stays Editable, generation_count++)

Content HTML is a minimal placeholder for MVP — real Tier 1 report templates
per Part A §5 land in Sprint F. Sufficient for smoke testing the state
transition + PDF pipeline end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from engagements import lifecycle
from reports import generator


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
    """Minimal report content — real templates arrive in Sprint F."""
    return (
        f"<h1>AI Audit Snapshot</h1>"
        f"<p>Engagement ID: {engagement_id}</p>"
        f"<p>Responses recorded: {response_count}</p>"
        f"<p>This is a placeholder Tier 1 snapshot. Full framework findings "
        f"and prioritized actions land in Sprint F.</p>"
    )


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

    response_count = _count_responses(cursor, engagement_id)
    content_html = _render_placeholder_content(engagement_id, response_count)

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

    if state == lifecycle.DRAFT:
        _apply_first_generation(cursor, engagement_id, state, report_id, pdf_hash, now)
    elif state == lifecycle.EDITABLE:
        _apply_regeneration(cursor, engagement_id, report_id, pdf_hash)

    return report_id, pdf_bytes, pdf_hash
