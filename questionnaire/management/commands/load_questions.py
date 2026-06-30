"""
load_questions — Django management command that synchronizes the `questions`
table with the canonical question_bank.py source-of-truth.

USAGE
-----
    # Preview changes without writing (DEFAULT before any sync)
    python manage.py load_questions --dry-run

    # Apply changes (inserts + updates; orphans in DB left alone)
    python manage.py load_questions

    # Apply AND mark DB rows missing from question_bank.py as
    # is_active=False (does NOT delete; preserves response history)
    python manage.py load_questions --deactivate-orphans

    # Limit to a specific tier
    python manage.py load_questions --tier tier_1

    # Print field-level diffs for every updated row
    python manage.py load_questions --verbose-diff

CONTRACT
--------
`audit_platform/questionnaire/question_bank.py` is the source of truth.
The `questions` table is reconciled in the direction of the file. Direct
DDL writes to the table via SRJ MCP are tolerated only as production
hotfixes that must be back-ported to question_bank.py within the same
week (see operator runbook).

The command does NOT delete rows. Deactivation (is_active=False) is the
strongest action available; existing response records that reference a
deactivated question continue to resolve via FK.

DESIGN
------
Uses raw SQL via `django.db.connection` rather than the Django ORM. The
`questions` table is `managed=False` in this project (provisioned by the
srj-mcp bootstrap migration), so the ORM path would require either a
Question model with hand-maintained Meta.db_table or a from_db_value
serialization layer for JSONB. Raw SQL with psycopg's Json adapter
sidesteps both and matches the pattern used elsewhere in this codebase
(direct SQL via SRJ MCP for hotfixes).

The 19 columns are pinned in COLUMNS below. If a new column is added to
the schema, both COLUMNS and the question_bank.py dicts need to be
updated together; the command's planning loop will silently drop any
column not in COLUMNS, and the apply loop will refuse to write a row
that includes an unrecognized key.

SAFETY
------
- Single transaction. Any error rolls back all changes.
- Dry-run shows the plan without writing. Default to --dry-run in CI and
  before any production sync.
- Validates ID uniqueness in question_bank.py before touching the DB.
- Logs the per-row plan (insert / update / unchanged / orphan) before
  committing, so /admin audit logs can reconstruct what changed.

TIER 1 / PRODUCTION STATE NOTE
------------------------------
As of 2026-06-30, production and question_bank.py hold the same 136
Tier 1 IDs. A dry-run from this state will show zero inserts and zero
orphans. Updates will fire only if a column value has drifted between
the bank and the DB (e.g., wording tweak, options edit). Run
`--dry-run --verbose-diff` first to confirm what (if anything) the
sync would touch.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from questionnaire.question_bank import QUESTIONS


# ----------------------------------------------------------------------------
# Schema pinning
# ----------------------------------------------------------------------------
# The 19 columns of public.questions, in the order used for INSERT.
# Order is significant: SQL placeholders and value tuples are built from
# this list in lockstep.

COLUMNS: tuple[str, ...] = (
    "id",
    "tier",
    "section",
    "subsection",
    "sequence_number",
    "question_text",
    "question_type",
    "options",
    "matrix_rows",
    "matrix_columns",
    "skip_logic",
    "role_visibility",
    "required",
    "scoring_weight",
    "framework_mappings",
    "notes",
    "is_active",
    "scoring_overrides",
    "extended_metadata",
)

# Columns that participate in the comparison between bank and DB.
# id is excluded because it's the join key, not a comparable field.
COMPARABLE_COLUMNS: tuple[str, ...] = tuple(c for c in COLUMNS if c != "id")


# ----------------------------------------------------------------------------
# Value normalization
# ----------------------------------------------------------------------------

def _bank_value(q: dict, column: str) -> Any:
    """Pull a column value out of a bank dict, normalizing for compare.

    Bank dicts may omit nullable columns entirely (e.g., `subsection`);
    treat missing keys as None.
    """
    value = q.get(column)
    if column == "scoring_weight" and value is not None:
        return Decimal(value).quantize(Decimal("0.01"))
    return value


def _db_value(row: dict, column: str) -> Any:
    """Pull a column value off a DB row dict, normalizing for compare."""
    value = row.get(column)
    if column == "scoring_weight" and value is not None:
        return Decimal(value).quantize(Decimal("0.01"))
    return value


def _diff_columns(bank_q: dict, db_row: dict) -> list[tuple[str, Any, Any]]:
    """Return [(column, bank_value, db_value), ...] for columns that differ."""
    differences: list[tuple[str, Any, Any]] = []
    for c in COMPARABLE_COLUMNS:
        b = _bank_value(bank_q, c)
        d = _db_value(db_row, c)
        if b != d:
            differences.append((c, b, d))
    return differences


def _format_value_short(v: Any, max_len: int = 60) -> str:
    """Compact string form of a value for diff output."""
    s = repr(v)
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def _to_sql_value(value: Any, column: str) -> Any:
    """Pass a Python value through to psycopg3.

    psycopg3 auto-adapts dict/list to JSONB and Decimal to NUMERIC; no
    manual encoding needed. This function is kept as the indirection
    point so a future driver switch (e.g., back to psycopg2) only
    requires changes here, not at every call site.

    Assumption: JSONB column values are JSON-serializable Python
    (dict/list of str/int/float/bool/None). Decimal inside JSONB would
    require a custom adapter — flag and add if a future question_bank
    ever embeds Decimal in framework_mappings / scoring_overrides /
    extended_metadata.
    """
    return value


# ----------------------------------------------------------------------------
# Bank-side validation
# ----------------------------------------------------------------------------

def _assert_unique_bank_ids(bank_questions: list[dict]) -> None:
    """Raise CommandError if question_bank.py has duplicate IDs."""
    seen: set[str] = set()
    dupes: list[str] = []
    for q in bank_questions:
        qid = q.get("id")
        if not qid:
            raise CommandError(
                f"question_bank.py contains a question with no 'id' field: {q!r}"
            )
        if qid in seen:
            dupes.append(qid)
        seen.add(qid)
    if dupes:
        raise CommandError(
            f"question_bank.py contains duplicate IDs: {sorted(set(dupes))!r}"
        )


def _assert_known_columns_only(bank_questions: list[dict]) -> None:
    """Raise CommandError if any bank dict has keys not in COLUMNS.

    This catches schema drift in either direction — a column added to
    the bank without the schema, or a typo in the bank — before any
    write touches Postgres.
    """
    known = set(COLUMNS)
    for q in bank_questions:
        unknown = set(q.keys()) - known
        if unknown:
            raise CommandError(
                f"question_bank.py question {q.get('id')!r} has unrecognized "
                f"keys (not in schema): {sorted(unknown)!r}. "
                f"Update COLUMNS in load_questions.py or fix the bank."
            )


# ----------------------------------------------------------------------------
# DB-side fetch
# ----------------------------------------------------------------------------

def _fetch_db_rows(tier_filter: str | None) -> dict[str, dict]:
    """Return {id: row_as_dict} for every row in public.questions.

    Optionally filters by tier. JSONB columns are returned by psycopg as
    already-decoded Python objects (dict/list/None), so no manual
    decoding is needed here.
    """
    cols_sql = ", ".join(COLUMNS)
    if tier_filter:
        sql = f"SELECT {cols_sql} FROM public.questions WHERE tier = %s"
        params: tuple[Any, ...] = (tier_filter,)
    else:
        sql = f"SELECT {cols_sql} FROM public.questions"
        params = ()

    rows_by_id: dict[str, dict] = {}
    with connection.cursor() as cur:
        cur.execute(sql, params)
        for db_tuple in cur.fetchall():
            row = dict(zip(COLUMNS, db_tuple))
            rows_by_id[row["id"]] = row
    return rows_by_id


# ----------------------------------------------------------------------------
# Plan structure
# ----------------------------------------------------------------------------

class SyncPlan:
    """Computed diff between question_bank.py and public.questions."""

    def __init__(self) -> None:
        self.to_insert: list[dict] = []
        self.to_update: list[tuple[dict, dict, list[tuple[str, Any, Any]]]] = []
        self.unchanged: list[str] = []
        self.orphans_in_db: list[dict] = []

    @property
    def has_changes(self) -> bool:
        return bool(self.to_insert or self.to_update)

    def summary_lines(self) -> list[str]:
        return [
            f"  to insert      : {len(self.to_insert)}",
            f"  to update      : {len(self.to_update)}",
            f"  unchanged      : {len(self.unchanged)}",
            f"  orphans in DB  : {len(self.orphans_in_db)}  (not in question_bank.py)",
        ]


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
                "question_bank.py. Does NOT delete. Safe to use only after "
                "any production-only questions have been back-ported into "
                "question_bank.py."
            ),
        )
        parser.add_argument(
            "--verbose-diff",
            action="store_true",
            help="Print column-level diffs for every updated row.",
        )

    # ---- entry point ----------------------------------------------------

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        tier_filter: str | None = options["tier"]
        deactivate_orphans: bool = options["deactivate_orphans"]
        verbose_diff: bool = options["verbose_diff"]

        # ---- 1. Validate bank --------------------------------------------
        bank_questions = [
            q for q in QUESTIONS
            if tier_filter is None or q.get("tier") == tier_filter
        ]
        _assert_unique_bank_ids(bank_questions)
        _assert_known_columns_only(bank_questions)

        self.stdout.write(
            f"Loaded {len(bank_questions)} questions from question_bank.py"
            + (f" (tier={tier_filter})" if tier_filter else "")
        )

        # ---- 2. Fetch DB and compute plan --------------------------------
        db_rows_by_id = _fetch_db_rows(tier_filter)
        self.stdout.write(
            f"Loaded {len(db_rows_by_id)} rows from public.questions"
            + (f" (tier={tier_filter})" if tier_filter else "")
        )

        plan = self._compute_plan(bank_questions, db_rows_by_id)

        self.stdout.write("")
        self.stdout.write("Sync plan:")
        for line in plan.summary_lines():
            self.stdout.write(line)
        self.stdout.write("")

        if verbose_diff and plan.to_update:
            self.stdout.write("Column-level diffs for updates:")
            for bank_q, _db_row, diffs in plan.to_update:
                self.stdout.write(f"  {bank_q['id']}:")
                for column, b, d in diffs:
                    self.stdout.write(
                        f"    {column}: db={_format_value_short(d)} "
                        f"-> bank={_format_value_short(b)}"
                    )
            self.stdout.write("")

        if not plan.has_changes:
            self.stdout.write(self.style.SUCCESS("No additions or updates needed."))

        if plan.orphans_in_db:
            self.stdout.write("Orphans in DB (present in DB but not in question_bank.py):")
            for row in plan.orphans_in_db:
                marker = "  (will deactivate)" if deactivate_orphans else "  (left alone)"
                self.stdout.write(f"  {row['id']}{marker}")
            self.stdout.write("")

        # ---- 3. Apply (or skip on dry-run) -------------------------------
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
        bank_questions: list[dict],
        db_rows_by_id: dict[str, dict],
    ) -> SyncPlan:
        plan = SyncPlan()
        bank_ids: set[str] = {q["id"] for q in bank_questions}

        for q in bank_questions:
            qid = q["id"]
            if qid not in db_rows_by_id:
                plan.to_insert.append(q)
                continue
            db_row = db_rows_by_id[qid]
            diffs = _diff_columns(q, db_row)
            if diffs:
                plan.to_update.append((q, db_row, diffs))
            else:
                plan.unchanged.append(qid)

        for db_id, db_row in db_rows_by_id.items():
            if db_id not in bank_ids:
                plan.orphans_in_db.append(db_row)

        return plan

    # ---- application ----------------------------------------------------

    @transaction.atomic
    def _apply_plan(self, plan: SyncPlan, deactivate_orphans: bool) -> None:
        if plan.to_insert:
            self._do_inserts(plan.to_insert)
            self.stdout.write(f"Inserted {len(plan.to_insert)} rows.")

        if plan.to_update:
            for bank_q, _db_row, _diffs in plan.to_update:
                self._do_update(bank_q)
            self.stdout.write(f"Updated {len(plan.to_update)} rows.")

        if deactivate_orphans and plan.orphans_in_db:
            ids = [row["id"] for row in plan.orphans_in_db]
            count = self._do_deactivate(ids)
            self.stdout.write(f"Deactivated {count} orphan rows (is_active=False).")

    def _do_inserts(self, bank_questions: list[dict]) -> None:
        cols_sql = ", ".join(COLUMNS)
        placeholders = ", ".join(["%s"] * len(COLUMNS))
        sql = f"INSERT INTO public.questions ({cols_sql}) VALUES ({placeholders})"

        with connection.cursor() as cur:
            for q in bank_questions:
                params = tuple(
                    _to_sql_value(_bank_value(q, c), c) for c in COLUMNS
                )
                cur.execute(sql, params)

    def _do_update(self, bank_q: dict) -> None:
        # UPDATE every comparable column. Cheaper than per-column diffing
        # at write time and safe because the comparable set excludes id.
        set_clause = ", ".join(f"{c} = %s" for c in COMPARABLE_COLUMNS)
        sql = f"UPDATE public.questions SET {set_clause} WHERE id = %s"
        params = tuple(
            _to_sql_value(_bank_value(bank_q, c), c) for c in COMPARABLE_COLUMNS
        ) + (bank_q["id"],)
        with connection.cursor() as cur:
            cur.execute(sql, params)

    def _do_deactivate(self, ids: list[str]) -> int:
        sql = "UPDATE public.questions SET is_active = FALSE WHERE id = ANY(%s)"
        with connection.cursor() as cur:
            cur.execute(sql, (list(ids),))
            return cur.rowcount
