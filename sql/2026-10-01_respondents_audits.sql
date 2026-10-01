-- OD-19 Tier 2 routing (2026-10-01): which audit(s) a respondent was invited to
-- on a combined engagement. NULL = the engagement's instrument.
BEGIN;
ALTER TABLE respondents ADD COLUMN IF NOT EXISTS audits text
    CHECK (audits IS NULL OR audits IN ('tier_1', 'aiitsa', 'combined'));
COMMENT ON COLUMN respondents.audits IS 'OD-19 Tier 2 routing: tier_1 | aiitsa | combined; NULL = engagement instrument';
COMMIT;
