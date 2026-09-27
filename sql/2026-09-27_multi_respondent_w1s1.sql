-- W1 Sprint 1: multi-respondent engagements (Part B-1 S.3, S.4).
-- Applied to production 2026-09-27. Run as postgres:
--   psql -U postgres -d srj_audit -f "<repo>\sql\2026-09-27_multi_respondent_w1s1.sql"
--
-- The respondents/engagements tables already carried the multi-respondent
-- columns from Part A (engagement_id, role, invitation_token, status,
-- completion_percentage, reminder_count, coverage_met_at, extension_count).
-- This adds only what the buyer-driven flow needs, plus the instrument
-- column that W2 (AIITSA) will key on so the engine is instrument-agnostic
-- from the start.

BEGIN;

-- Buyer-triggered reminder rate limit (one per 24h, B-1 S.4.3).
ALTER TABLE respondents
    ADD COLUMN IF NOT EXISTS last_nudged_at timestamptz;

-- Buyers can silence automatic reminders for a respondent they are
-- chasing personally (B-1 S.4.3).
ALTER TABLE respondents
    ADD COLUMN IF NOT EXISTS reminders_disabled boolean NOT NULL DEFAULT false;

-- W2 preparation: which question bank a question belongs to. Every
-- existing row is Pillar I Tier 1.
ALTER TABLE questions
    ADD COLUMN IF NOT EXISTS instrument text NOT NULL DEFAULT 'tier_1';
CREATE INDEX IF NOT EXISTS idx_questions_instrument ON questions (instrument);

-- Buyer dashboard and coverage check read these per engagement.
CREATE INDEX IF NOT EXISTS idx_respondents_engagement_status
    ON respondents (engagement_id, status);

GRANT SELECT, INSERT, UPDATE ON respondents TO srj_audit_app;
GRANT SELECT ON questions TO srj_audit_app;

COMMIT;
