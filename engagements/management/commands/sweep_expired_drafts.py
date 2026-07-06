"""Django management command: sweep_expired_drafts.

Runs the Draft → Expired sweep at the 180-day outer cap per OD-18 §4.
Schedule daily or hourly. Idempotent.

Usage:
    python manage.py sweep_expired_drafts
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from engagements import sweeps


class Command(BaseCommand):
    help = "Transition Draft engagements past 180-day cap to Expired."

    def handle(self, *args, **options):
        with transaction.atomic():
            with connection.cursor() as cursor:
                count = sweeps.sweep_draft_to_expired(cursor)
        self.stdout.write(
            self.style.SUCCESS(f"Expired {count} engagement(s).")
        )
