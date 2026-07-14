"""Issue a promotional / tester access code.

Usage (from Render Shell or local):

    python manage.py issue_access_code \
        --code AIAUDIT100 \
        --label "LinkedIn campaign 2026-07" \
        --max-uses 100 \
        --expires-days 30

    # If --code is omitted, an 8-char random uppercase code is generated.
    # If --expires-days is omitted, defaults to 30 days from now.

Prints the code + the pre-filled marketing URL:

    https://aiauditforcompanies.com/startaiaudit?code=AIAUDIT100
"""

from __future__ import annotations

import secrets
import string
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


ALLOWED_CODE_CHARS = string.ascii_uppercase + string.digits


def _random_code(length: int = 8) -> str:
    return "".join(secrets.choice(ALLOWED_CODE_CHARS) for _ in range(length))


class Command(BaseCommand):
    help = "Issue a promotional access code that comps the $399 Tier 1 fee."

    def add_arguments(self, parser):
        parser.add_argument(
            "--code",
            help="Explicit code string (uppercase alphanumeric). "
                 "If omitted, an 8-char random code is generated.",
        )
        parser.add_argument(
            "--label", required=True,
            help="Short human label, e.g., 'LinkedIn campaign 2026-07'.",
        )
        parser.add_argument(
            "--max-uses", type=int, default=1,
            help="Maximum number of redemptions before the code stops working "
                 "(default: 1).",
        )
        parser.add_argument(
            "--expires-days", type=int, default=30,
            help="Days from now until the code expires (default: 30).",
        )
        parser.add_argument(
            "--kind", default="tester_full_comp",
            help="Code kind label stored on the row "
                 "(default: tester_full_comp).",
        )
        parser.add_argument(
            "--percentage", type=float, default=100.0,
            help="Discount percentage 0-100 (default: 100 = full comp). "
                 "The current start-form flow treats any code as full comp; "
                 "sub-100 percentages are stored for future partial-discount use.",
        )
        parser.add_argument(
            "--created-by", default="operator",
            help="Free-form audit trail for who issued the code.",
        )
        parser.add_argument(
            "--notes",
            help="Free-form notes (context, campaign details, etc.).",
        )

    def handle(self, *args, **opts):
        code = (opts["code"] or _random_code()).upper().strip()

        if not code or any(c not in ALLOWED_CODE_CHARS for c in code):
            raise CommandError(
                "code must be uppercase A-Z / 0-9 only."
            )

        if opts["max_uses"] < 1:
            raise CommandError("--max-uses must be at least 1.")
        if opts["expires_days"] < 1:
            raise CommandError("--expires-days must be at least 1.")
        if not (0 <= opts["percentage"] <= 100):
            raise CommandError("--percentage must be 0-100.")

        expires_at = timezone.now() + timedelta(days=opts["expires_days"])

        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO access_codes
                        (code, kind, percentage, label, notes, max_uses,
                         expires_at, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        code,
                        opts["kind"],
                        opts["percentage"],
                        opts["label"],
                        opts.get("notes"),
                        opts["max_uses"],
                        expires_at,
                        opts["created_by"],
                    ),
                )
            except Exception as exc:
                raise CommandError(
                    f"Insert failed (code already exists?): {exc}"
                )

            code_id = cursor.fetchone()[0]

        base = "https://aiauditforcompanies.com/startaiaudit"
        pre_filled = f"{base}?code={code}"

        self.stdout.write(self.style.SUCCESS(
            "\nAccess code issued.\n"
            f"  id           : {code_id}\n"
            f"  code         : {code}\n"
            f"  label        : {opts['label']}\n"
            f"  kind         : {opts['kind']}\n"
            f"  percentage   : {opts['percentage']}\n"
            f"  max_uses     : {opts['max_uses']}\n"
            f"  expires_at   : {expires_at.isoformat()}\n"
            f"  created_by   : {opts['created_by']}\n"
            "\nShare either:\n"
            f"  Code only      : {code}\n"
            f"  Pre-filled URL : {pre_filled}\n"
        ))
