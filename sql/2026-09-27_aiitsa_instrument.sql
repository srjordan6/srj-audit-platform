-- W2 AIITSA Sprint A: which question bank an engagement walks.
-- tier_1 = Pillar I (default, every existing row); aiitsa = AI IT Security Audit(TM);
-- combined = both, Pillar I first. questions.instrument (2026-09-27 W1S1 SQL) tags the
-- questions themselves; this tags the engagement. Run as postgres against srj_platform.
BEGIN;
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS instrument text NOT NULL DEFAULT 'tier_1';
ALTER TABLE engagements DROP CONSTRAINT IF EXISTS engagements_instrument_check;
ALTER TABLE engagements ADD CONSTRAINT engagements_instrument_check
    CHECK (instrument IN ('tier_1', 'aiitsa', 'combined'));
CREATE INDEX IF NOT EXISTS idx_engagements_instrument ON engagements (instrument);
COMMIT;
