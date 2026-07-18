"""Report download (Phase 2e).

/reports/mine/download/ streams the respondent's most recent persisted
report PDF from Cloudflare R2. Access is scoped to the session respondent's
own engagement, so a respondent can only ever fetch their own report.
"""

from __future__ import annotations

import logging

from django.db import connection
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

_PROCESSING_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Report generating</title>
<style>body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;
background:#F4F3FA;color:#201868;text-align:center;padding:80px 20px}
.card{max-width:520px;margin:0 auto;background:#fff;border-radius:10px;
padding:32px;box-shadow:0 1px 4px rgba(32,24,104,.15)}
a{color:#F07800;font-weight:600;text-decoration:none}</style></head>
<body><div class="card">
<h2>Your report is still generating</h2>
<p>Your AI Audit Snapshot is being prepared and emailed to you now &mdash;
this usually takes a minute or two. Refresh this page shortly, or check your
inbox for the PDF.</p>
<p><a href="javascript:location.reload()">&#8635; Refresh</a></p>
</div></body></html>"""


def _session_respondent_id(request):
    return request.session.get("respondent_id") or request.GET.get("respondent_id")


@require_http_methods(["GET"])
def download_my_report(request):
    rid = _session_respondent_id(request)
    if not rid:
        return HttpResponseNotFound("respondent_id required")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rp.id, rp.file_path, rp.engagement_id "
            "FROM reports rp "
            "JOIN respondents rs ON rs.engagement_id = rp.engagement_id "
            "WHERE rs.id = %s "
            "ORDER BY rp.generated_at DESC LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if row is None:
            return HttpResponse(_PROCESSING_HTML, status=200)

        report_id, file_path, engagement_id = str(row[0]), row[1], str(row[2])
        if not file_path or not file_path.startswith("r2://"):
            # Not yet persisted to R2 (still generating, or R2 was unset when
            # this report was made). Tell the user it's on the way by email.
            return HttpResponse(_PROCESSING_HTML, status=200)

        key = file_path[len("r2://"):]
        from reports import storage
        pdf = storage.fetch_report_pdf(key)
        if pdf is None:
            return HttpResponse(_PROCESSING_HTML, status=200)

        cursor.execute(
            "UPDATE reports SET download_count = COALESCE(download_count, 0) + 1, "
            "last_downloaded_at = NOW() WHERE id = %s",
            (report_id,),
        )

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        f'attachment; filename="AI_Audit_Snapshot_{engagement_id[:8]}.pdf"'
    )
    return resp
