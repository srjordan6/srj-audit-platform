"""Django management command: sweep_locked_snapshots.

Runs the Editable → Locked sweep. Schedule via cron or RQ background job.
Idempotent — safe to run every minute.

Usage:
    python manage.py sweep_locked_snapshots
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from engagements import sweeps


class Command(BaseCommand):
    help = "Transition Editable engagements past window_end to Locked."

    def handle(self, *args, **options):
        with transaction.atomic():
            with connection.cursor() as cursor:
                count = sweeps.sweep_editable_to_locked(cursor)
        self.stdout.write(
            self.style.SUCCESS(f"Locked {count} engagement(s).")
        )
