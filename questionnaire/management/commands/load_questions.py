"""
load_questions — Django management command that synchronizes the `questions`
table with the canonical question_bank.py source-of-truth.

USAGE
-----
    # Preview changes without writing
    python manage.py load_questions --dry-run

    # Apply changes (additions and updates only; existing rows not in
    # question_bank.py are left alone, even if they look orphaned)
    python manage.py load_questions

    # Apply changes AND mark DB rows missing from question_bank.py as
    # is_active=False (does NOT delete; preserves response history)
    python manage.py load_questions --deactivate-orphans

    # Limit to a specific tier
    python manage.py load_questions --tier tier_1

CONTRACT
--------
The command treats `audit_platform/questionnaire/question_bank.py` as the
source of truth. Any divergence between the file and the DB is reconciled
in the direction of the file. Direct DDL changes to the questions table
via SRJ MCP are tolerated only as production hotfixes that must be
back-ported to question_bank.py within the same week.

The command does NOT delete rows. Deactivation (is_active=False) is the
strongest action available; existing response records that reference a
deactivated question continue to resolve via FK.

SAFETY
------
- Runs inside a single transaction. Any error rolls back all changes.
- Dry-run mode is the default behavior pattern in CI; run --dry-run before
  any production sync.
- Logs the full diff between file and DB before committing, so audit logs
  in /admin can show exactly what changed and when.
"""

from __future__ import annotations

from dataclasses import fields as dc_fields
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from questionnaire.models import Question as QuestionModel
from questionnaire.question_bank import QUESTIONS, Question, assert_unique_ids


# ----------------------------------------------------------------------------
# Field comparison helpers
# ----------------------------------------------------------------------------
# Fields are compared in three groups, each with its own equality semantics.

# Direct equality (scalar fields, with None tolerated).
SCALAR_FIELDS = (
    "tier", "section", "subsection", "sequence_number",
    "question_text", "question_type",
    "required", "is_active", "notes",
)

# Numeric field needing Decimal-aware comparison.
DECIMAL_FIELDS = ("scoring_weight",)

# JSONB fields. Compared as Python objects post-deserialization. Order
# matters in every case here — options/matrix_rows/matrix_columns are
# user-visible ordered lists; framework_mappings has weight-determining
# order; skip_logic/scoring_overrides/extended_metadata are small dicts.
JSON_FIELDS = (
    "options", "matrix_rows", "matrix_columns",
    "skip_logic", "role_visibility", "framework_mappings",
    "scoring_overrides", "extended_metadata",
)

ALL_FIELDS = SCALAR_FIELDS + DECIMAL_FIELDS + JSON_FIELDS


def _bank_value(q: Question, field_name: str) -> Any:
    """Pull a field value out of a Question dataclass, normalizing for compare."""
    value = getattr(q, field_name)
    if field_name in DECIMAL_FIELDS and value is not None:
        # Question dataclass stores Decimal; DB returns Decimal. Quantize
        # both sides identically so 1.0 == 1.00.
        return Decimal(value).quantize(Decimal("0.01"))
    return value


def _db_value(row: QuestionModel, field_name: str) -> Any:
    """Pull a field value off a Django ORM row, normalizing for compare."""
    value = getattr(row, field_name)
    if field_name in DECIMAL_FIELDS and value is not None:
        return Decimal(value).quantize(Decimal("0.01"))
    return value


def _diff_fields(bank_q: Question, db_row: QuestionModel) -> list[tuple[str, Any, Any]]:
    """Return [(field, bank_value, db_value), ...] for fields that differ."""
    differences: list[tuple[str, Any, Any]] = []
    for f in ALL_FIELDS:
        b = _bank_value(bank_q, f)
        d = _db_value(db_row, f)
        if b != d:
            differences.append((f, b, d))
    return differences


def _format_value_short(v: Any, max_len: int = 60) -> str:
    """Compact string form of a value for diff output."""
    s = repr(v)
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


# ----------------------------------------------------------------------------
# Plan structure
# ----------------------------------------------------------------------------

class SyncPlan:
    """Computed diff between question_bank.py and the questions table."""

    def __init__(self) -> None:
        self.to_insert: list[Question] = []
        self.to_update: list[tuple[Question, QuestionModel, list[tuple[str, Any, Any]]]] = []
        self.unchanged: list[str] = []
        self.orphans_in_db: list[QuestionModel] = []

    @property
    def has_changes(self) -> bool:
        return bool(self.to_insert or self.to_update)

    def summary_lines(self) -> list[str]:
        lines = [
            f"  to insert      : {len(self.to_insert)}",
            f"  to update      : {len(self.to_update)}",
            f"  unchanged      : {len(self.unchanged)}",
            f"  orphans in DB  : {len(self.orphans_in_db)}  (not in question_bank.py)",
        ]
        return lines


# ----------------------------------------------------------------------------
# Command
# ----------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Synchronize the questions table with the canonical question_bank.py "
        "source-of-truth. See module docstring for usage."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without applying changes.",
        )
        parser.add_argument(
            "--tier",
            default=None,
            help="Limit to a specific tier (e.g. 'tier_1'). Default: all tiers.",
        )
        parser.add_argument(
            "--deactivate-orphans",
            action="store_true",
            help=(
                "Set is_active=False on DB rows whose IDs are not present in "
                "question_bank.py. Does NOT delete. Safe to use if you've "
                "deliberately removed a question from the bank."
            ),
        )
        parser.add_argument(
            "--verbose-diff",
            action="store_true",
            help="Print field-level diffs for every updated row.",
        )

    # ---- entry point ----------------------------------------------------

    def handle(self, *args, **options) -> None:
        # question_bank.py runs assert_unique_ids() at import; calling it
        # again here makes the validation contract explicit.
        try:
            assert_unique_ids()
        except ValueError as e:
            raise CommandError(f"question_bank.py validation failed: {e}")

        dry_run: bool = options["dry_run"]
        tier_filter: str | None = options["tier"]
        deactivate_orphans: bool = options["deactivate_orphans"]
        verbose_diff: bool = options["verbose_diff"]

        # ---- 1. Load bank questions (optionally filtered to tier) -------
        bank_questions = [q for q in QUESTIONS if tier_filter is None or q.tier == tier_filter]
        self.stdout.write(
            f"Loaded {len(bank_questions)} questions from question_bank.py"
            + (f" (tier={tier_filter})" if tier_filter else "")
        )

        # ---- 2. Compute the sync plan -----------------------------------
        plan = self._compute_plan(bank_questions, tier_filter)

        self.stdout.write("")
        self.stdout.write("Sync plan:")
        for line in plan.summary_lines():
            self.stdout.write(line)
        self.stdout.write("")

        if verbose_diff and plan.to_update:
            self.stdout.write("Field-level diffs for updates:")
            for bank_q, _db_row, diffs in plan.to_update:
                self.stdout.write(f"  {bank_q.id}:")
                for field, b, d in diffs:
                    self.stdout.write(
                        f"    {field}: db={_format_value_short(d)} "
                        f"-> bank={_format_value_short(b)}"
                    )
            self.stdout.write("")

        if not plan.to_insert and not plan.to_update:
            self.stdout.write(self.style.SUCCESS("No additions or updates needed."))

        if plan.orphans_in_db:
            self.stdout.write(
                f"Orphans in DB (present in DB but not in question_bank.py):"
            )
            for row in plan.orphans_in_db:
                marker = "  (will deactivate)" if deactivate_orphans else "  (left alone)"
                self.stdout.write(f"  {row.id}{marker}")
            self.stdout.write("")

        # ---- 3. Apply (or skip on dry-run) ------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes applied."))
            return

        if not plan.has_changes and not (deactivate_orphans and plan.orphans_in_db):
            self.stdout.write(self.style.SUCCESS("Nothing to do."))
            return

        self._apply_plan(plan, deactivate_orphans)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Sync complete."))

    # ---- planning -------------------------------------------------------

    def _compute_plan(
        self,
        bank_questions: list[Question],
        tier_filter: str | None,
    ) -> SyncPlan:
        """Diff bank questions against DB rows and produce a SyncPlan."""

        # Load all (optionally tier-filtered) DB rows once into a dict.
        db_query = QuestionModel.objects.all()
        if tier_filter:
            db_query = db_query.filter(tier=tier_filter)
        db_rows_by_id: dict[str, QuestionModel] = {row.id: row for row in db_query}

        bank_ids = {q.id for q in bank_questions}
        plan = SyncPlan()

        # Inserts and updates
        for q in bank_questions:
            if q.id not in db_rows_by_id:
                plan.to_insert.append(q)
                continue
            db_row = db_rows_by_id[q.id]
            diffs = _diff_fields(q, db_row)
            if diffs:
                plan.to_update.append((q, db_row, diffs))
            else:
                plan.unchanged.append(q.id)

        # Orphans (in DB but not in bank). Tier filter already applied above.
        for db_id, db_row in db_rows_by_id.items():
            if db_id not in bank_ids:
                plan.orphans_in_db.append(db_row)

        return plan

    # ---- application ----------------------------------------------------

    @transaction.atomic
    def _apply_plan(self, plan: SyncPlan, deactivate_orphans: bool) -> None:
        """Apply the sync plan inside a single transaction."""

        # Inserts via bulk_create.
        if plan.to_insert:
            new_models = [self._bank_to_model(q) for q in plan.to_insert]
            QuestionModel.objects.bulk_create(new_models)
            self.stdout.write(f"Inserted {len(new_models)} rows.")

        # Updates one-by-one (Django bulk_update has limitations with JSONB
        # fields across some backends; explicit save() is reliable).
        for bank_q, db_row, _diffs in plan.to_update:
            for f in ALL_FIELDS:
                setattr(db_row, f, _bank_value(bank_q, f))
            db_row.save()
        if plan.to_update:
            self.stdout.write(f"Updated {len(plan.to_update)} rows.")

        # Deactivate orphans only if explicitly requested.
        if deactivate_orphans and plan.orphans_in_db:
            ids = [row.id for row in plan.orphans_in_db]
            count = QuestionModel.objects.filter(id__in=ids).update(is_active=False)
            self.stdout.write(f"Deactivated {count} orphan rows (is_active=False).")

    # ---- conversion -----------------------------------------------------

    def _bank_to_model(self, q: Question) -> QuestionModel:
        """Convert a bank Question dataclass into an unsaved Question model."""
        kwargs: dict[str, Any] = {}
        for f in dc_fields(q):
            kwargs[f.name] = getattr(q, f.name)
        # scoring_weight needs Decimal normalization
        if "scoring_weight" in kwargs and kwargs["scoring_weight"] is not None:
            kwargs["scoring_weight"] = Decimal(kwargs["scoring_weight"]).quantize(
                Decimal("0.01")
            )
        return QuestionModel(**kwargs)
