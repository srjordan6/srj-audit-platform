"""Django management command: generate_report.

Manually triggers report generation for a given engagement. Owner password
is read from OS env var PDF_OWNER_PASSWORD.

Usage:
    python manage.py generate_report <engagement_id> <buyer_email>
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from reports import services


class Command(BaseCommand):
    help = "Generate a locked report for a given engagement (Draft→Editable transition)."

    def add_arguments(self, parser):
        parser.add_argument("engagement_id", type=str)
        parser.add_argument("buyer_email", type=str)

    def handle(self, *args, **options):
        engagement_id = options["engagement_id"]
        buyer_email = options["buyer_email"]
        owner_password = os.environ.get("PDF_OWNER_PASSWORD")
        if not owner_password:
            raise CommandError(
                "PDF_OWNER_PASSWORD env var not set. Set it before running."
            )

        with transaction.atomic():
            with connection.cursor() as cursor:
                report_id, pdf_bytes, pdf_hash = services.generate_and_lock(
                    cursor,
                    engagement_id=engagement_id,
                    buyer_email=buyer_email,
                    owner_password=owner_password,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Generated report {report_id} — {len(pdf_bytes)} bytes, hash {pdf_hash[:16]}..."
            )
        )
