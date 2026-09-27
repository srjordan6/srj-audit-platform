"""Cloudflare R2 object storage for generated report PDFs (Phase 2e).

R2 is S3-compatible; we use boto3 (already a dependency) pointed at the R2
endpoint. Every function is NON-FATAL: on any failure it logs and returns
None/False so report generation and email delivery still succeed.

Environment variables (set in Render):
  R2_ACCOUNT_ID          Cloudflare account id (prefix of the S3 endpoint)
  R2_ACCESS_KEY_ID       R2 API token access key id
  R2_SECRET_ACCESS_KEY   R2 API token secret
  R2_BUCKET              bucket name (srj-audit-reports)

Key layout (Part A 2.7, adapted to R2):
  reports/tier_1/{engagement_id}/{report_id}.pdf
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _client():
    account = os.environ.get("R2_ACCOUNT_ID")
    key = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not (account and key and secret):
        logger.info("r2: credentials not set; storage disabled")
        return None
    try:
        import boto3
        from botocore.config import Config
        return boto3.client(
            "s3",
            endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
            aws_access_key_id=key,
            aws_secret_access_key=secret,
            region_name="auto",
            config=Config(signature_version="s3v4",
                          retries={"max_attempts": 3, "mode": "standard"}),
        )
    except Exception:  # noqa: BLE001
        logger.exception("r2: client init failed")
        return None


def _bucket() -> str:
    return os.environ.get("R2_BUCKET", "srj-audit-reports")


def report_key(engagement_id: str, report_id: str, tier: str = "tier_1") -> str:
    """Key scheme from the 2026-07-17 R2 architecture record:
    reports/tier_1/..., reports/tier_2/..., reports/tier_3/..."""
    tier = tier if tier in ("tier_1", "tier_2", "tier_3") else "tier_1"
    return f"reports/{tier}/{engagement_id}/{report_id}.pdf"


def upload_report_pdf(engagement_id: str, report_id: str, pdf_bytes: bytes, tier: str = "tier_1"):
    """Upload the PDF to R2. Returns the object key on success, else None."""
    client = _client()
    if client is None:
        return None
    key = report_key(engagement_id, report_id, tier)
    try:
        client.put_object(
            Bucket=_bucket(),
            Key=key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        logger.info("r2: stored %s (%d bytes)", key, len(pdf_bytes))
        return key
    except Exception:  # noqa: BLE001
        logger.exception("r2: upload failed for %s", key)
        return None


def fetch_report_pdf(key: str):
    """Return the PDF bytes for an R2 key, or None on any failure."""
    client = _client()
    if client is None:
        return None
    try:
        obj = client.get_object(Bucket=_bucket(), Key=key)
        return obj["Body"].read()
    except Exception:  # noqa: BLE001
        logger.exception("r2: fetch failed for %s", key)
        return None
