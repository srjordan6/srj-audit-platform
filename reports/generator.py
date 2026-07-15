"""OD-18 report generation pipeline: HTML → PDF → AES-256 lockdown → hash.

Watermark model (OD-18 §7.2): diagonal low-opacity text carrying buyer
email + snapshot ID + generation timestamp on every page.

Encryption (OD-18 §7.1): 256-bit AES, owner password from settings, no
user password, permissions_flag=0 (no copy/print/edit/annotate/extract).

WeasyPrint and pypdf are lazy-imported inside their consumers so tests
can mock the module-level functions without needing the libraries
installed in the test environment.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime


def build_watermarked_html(
    content_html: str,
    buyer_email: str,
    snapshot_id: str,
    generated_at_iso: str,
) -> str:
    """Wrap report content in an HTML document with diagonal watermark.

    Watermark spec (OD-18 §7.2): position:fixed + rotate(-30deg) + opacity 0.08.
    """
    watermark = f"{buyer_email} \u00b7 {snapshot_id} \u00b7 {generated_at_iso}"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 2cm; }}
  body {{ font-family: sans-serif; position: relative; }}
  .srj-watermark {{
    position: fixed;
    top: 40%;
    left: 0;
    right: 0;
    transform: rotate(-30deg);
    opacity: 0.08;
    font-size: 24pt;
    text-align: center;
    color: #000;
    pointer-events: none;
    z-index: 1000;
  }}
</style>
</head>
<body>
<div class="srj-watermark">{watermark}</div>
{content_html}
</body>
</html>"""


def html_to_pdf_bytes(html: str) -> bytes:
    """Convert HTML string to PDF bytes via WeasyPrint (lazy import)."""
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


def encrypt_pdf(
    pdf_bytes: bytes,
    owner_password: str,
    buyer_email: str = "",
    snapshot_id: str = "",
    generated_at_iso: str = "",
) -> bytes:
    """Apply AES-256 encryption + zero-permissions flags + attribution metadata.

    User password None (opens without prompt). Owner password gates
    permission changes. permissions_flag=0 blocks copy/print/edit/annotate.

    Buyer attribution moved to PDF /Info metadata (Author/Subject/Keywords)
    2026-07-15 so the visible watermark can be brand-only while any leaked
    copy remains traceable via `pdfinfo` or similar readers.
    """
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    # Embed attribution in PDF metadata (Info dictionary). These fields
    # are readable by any PDF tool and survive re-encryption; a leaked
    # copy still points back to the buyer.
    metadata = {
        "/Title": f"SRJ AI Audit Snapshot Report - {snapshot_id or 'confidential'}",
        "/Author": "SRJ Consulting & Services LLC",
        "/Subject": f"Confidential audit report issued to {buyer_email or 'the named buyer'}",
        "/Producer": "SRJ AI Audit Platform (aiauditforcompanies.com)",
        "/Creator": "SRJ Consulting & Services LLC",
        "/Keywords": (
            f"confidential;not-for-redistribution;buyer={buyer_email};"
            f"snapshot_id={snapshot_id};generated_at={generated_at_iso}"
        ),
    }
    writer.add_metadata(metadata)

    writer.encrypt(
        user_password="",
        owner_password=owner_password,
        algorithm="AES-256",
        permissions_flag=0,
    )
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def compute_pdf_hash(pdf_bytes: bytes) -> str:
    """SHA-256 hex digest for report_of_record_pdf_hash column."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def generate_locked_report(
    content_html: str,
    buyer_email: str,
    snapshot_id: str,
    generated_at: datetime,
    owner_password: str,
) -> tuple[bytes, str]:
    """Full OD-18 pipeline: watermark → PDF → encrypt → hash.

    Returns (encrypted_pdf_bytes, sha256_hex_hash). The hash is stored to
    engagements.report_of_record_pdf_hash at Editable→Locked transition.
    """
    watermarked = build_watermarked_html(
        content_html,
        buyer_email,
        snapshot_id,
        generated_at.isoformat(),
    )
    pdf = html_to_pdf_bytes(watermarked)
    encrypted = encrypt_pdf(
        pdf,
        owner_password,
        buyer_email=buyer_email,
        snapshot_id=snapshot_id,
        generated_at_iso=generated_at.isoformat(),
    )
    return encrypted, compute_pdf_hash(encrypted)
