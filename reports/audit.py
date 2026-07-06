"""Report download event audit logging (OD-18 §7.5).

Enables leak-source identification when combined with the per-copy watermark.
"""

from __future__ import annotations

import json
from typing import Optional


def log_report_download(
    cursor,
    engagement_id: str,
    actor_user_id: str,
    ip_address: str,
    user_agent: str,
    report_framework: Optional[str] = None,
) -> None:
    """Insert a report.downloaded event into the events table."""
    cursor.execute(
        """
        INSERT INTO events
        (event_type, actor_user_id, engagement_id, payload, ip_address, user_agent)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
        """,
        (
            "report.downloaded",
            actor_user_id,
            engagement_id,
            json.dumps({"report_framework": report_framework}),
            ip_address,
            user_agent,
        ),
    )
