# Hand-applied SQL

The `scores`, `responses`, `engagements`, `reports` and `events` tables are
hand-managed. The Django models that mirror them are `managed = False`, so
`manage.py migrate` does **not** create or alter them — migrations in
`*/migrations/` exist only to keep Django's model state quiet.

Schema changes therefore live here as dated, idempotent SQL files and are
applied manually, in order, as the table owner.

## Applying

The MCP writer role is not the table owner, so DDL must run as `postgres`:

```powershell
psql -U postgres -d srj_audit -f "C:\SRJ AI Audit Platform\clean-clone\sql\<file>.sql"
```

Every file is wrapped in a transaction and uses `IF NOT EXISTS`, so
re-running one is safe.

## Applied

| File | Applied | What |
|---|---|---|
| `2026-09-05_scores_report_id.sql` | 2026-09-05 | `scores.report_id` FK to `reports`, two indexes, INSERT grant to `srj_audit_app`. Enables append-per-generation score history (Tier 4 trend lines). |

## Conventions

- Name files `YYYY-MM-DD_short_description.sql`.
- Wrap in `BEGIN; … COMMIT;`.
- Use `IF NOT EXISTS` / `IF EXISTS` so the file is idempotent.
- Grant explicitly to `srj_audit_app` — the app role is deliberately
  `NOSUPERUSER` so that RLS `tenant_isolation` policies apply to it.
- Add a row to the table above when the file is applied to production.
