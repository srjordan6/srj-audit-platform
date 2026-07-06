"""Django management command: load_framework_mappings.

Reads a CSV of framework mappings, validates against the registry, and
applies to questions.framework_mappings via mapping_loader.

Usage:
    python manage.py load_framework_mappings path/to/mappings.csv
    python manage.py load_framework_mappings path/to/mappings.csv --replace
    python manage.py load_framework_mappings path/to/mappings.csv --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from scoring import csv_parser, mapping_loader


class Command(BaseCommand):
    help = "Load question→framework mappings from CSV into questions.framework_mappings."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to mappings CSV.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Overwrite entire framework_mappings array (default: merge, preserve internal aggregators).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse + validate but do not write.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        mode = "replace" if options["replace"] else "merge"
        dry_run = options["dry_run"]

        try:
            with open(csv_path, "r", encoding="utf-8") as fh:
                mappings = csv_parser.parse_mapping_csv(fh)
        except FileNotFoundError:
            raise CommandError(f"CSV not found: {csv_path}")
        except ValueError as e:
            raise CommandError(str(e))

        errors = mapping_loader.validate_mappings(mappings)
        if errors:
            for qid, err_list in errors.items():
                for err in err_list:
                    self.stdout.write(self.style.ERROR(f"{qid}: {err}"))
            raise CommandError(f"{len(errors)} question(s) have invalid mappings.")

        self.stdout.write(
            f"Parsed {len(mappings)} question(s) with valid mappings. "
            f"Mode: {mode}. Dry-run: {dry_run}."
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes applied."))
            return

        with transaction.atomic():
            with connection.cursor() as cursor:
                count = mapping_loader.apply_framework_mappings(
                    cursor, mappings, mode=mode
                )

        self.stdout.write(
            self.style.SUCCESS(f"Applied mappings to {count} question(s).")
        )
