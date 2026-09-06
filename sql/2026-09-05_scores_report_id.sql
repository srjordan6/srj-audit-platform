-- scores: append-per-generation history, keyed to the report of record.
-- Locked with Stephen 2026-09-05. Applied to production 2026-09-05.
--
-- The MCP writer role is not the table owner, so this cannot be applied
-- through execute_write. Run as postgres:
--   psql -U postgres -d srj_audit -f "<repo>\sql\2026-09-05_scores_report_id.sql"
--
-- Rationale: `scores` had existed since the initial schema and was never
-- written to (0 rows) -- scoring ran in memory at render time and was
-- discarded. reports.services.generate_and_lock now appends a row set per
-- generation, so `report_id` is what makes the history queryable:
-- "what did the report of record say, and how has it moved since".
--
-- Verify:
--   psql -U postgres -d srj_audit -c "\d scores"
--   select framework, dimension, score from scores where report_id = '<id>';

BEGIN;

ALTER TABLE scores
    ADD COLUMN IF NOT EXISTS report_id uuid
        REFERENCES reports(id) ON DELETE CASCADE;

-- Trend queries: one engagement's scores over time, per framework.
CREATE INDEX IF NOT EXISTS idx_scores_engagement_framework_time
    ON scores (engagement_id, framework, calculated_at DESC);

-- Pull the full score set for a given report of record.
CREATE INDEX IF NOT EXISTS idx_scores_report
    ON scores (report_id);

-- The app role writes these rows. It is deliberately NOSUPERUSER so that
-- the tenant_isolation RLS policy applies to it.
GRANT SELECT, INSERT ON scores TO srj_audit_app;

COMMIT;
