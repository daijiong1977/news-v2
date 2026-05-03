-- supabase/migrations/20260504_cadence_aware_sources.sql
ALTER TABLE redesign_source_configs
  ADD COLUMN IF NOT EXISTS cadence_days INTEGER NOT NULL DEFAULT 1
    CHECK (cadence_days BETWEEN 1 AND 60),
  ADD COLUMN IF NOT EXISTS next_pickup_at DATE;

CREATE INDEX IF NOT EXISTS redesign_source_configs_pickup_eligible_idx
  ON redesign_source_configs (category, next_pickup_at NULLS FIRST)
  WHERE enabled = true;

-- Add UNIQUE(name) so the seed in Task 2 can use ON CONFLICT (name).
-- Guarded so the migration is replay-safe (CI re-runs, staging refreshes,
-- partial-failure recovery): pre-check for duplicates and skip if the
-- constraint already exists.
DO $$
DECLARE dup_count int;
BEGIN
  SELECT count(*) INTO dup_count FROM (
    SELECT name FROM redesign_source_configs
    GROUP BY name HAVING count(*) > 1
  ) d;
  IF dup_count > 0 THEN
    RAISE EXCEPTION 'Cannot add UNIQUE(name): % duplicate name(s) found', dup_count;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'redesign_source_configs_name_unique'
  ) THEN
    ALTER TABLE redesign_source_configs
      ADD CONSTRAINT redesign_source_configs_name_unique UNIQUE (name);
  END IF;
END$$;
