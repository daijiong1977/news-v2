-- Per-source probe health counters and auto-pause signal.
--
-- Backs `pipeline/full_round.py:_stage1_5_runner`'s phase_a_probe
-- bookkeeping: every body-fetch attempt is attributed to its source,
-- thin/long drops increment the counters, and any source whose
-- drop_rate >= 60% AND attempts >= 10 is auto-paused (state='paused',
-- paused_reason='high_probe_drop_rate'). `db_config.load_sources`
-- excludes paused rows from the candidate pool until admin sets state
-- back to 'live'.
--
-- Counters are CUMULATIVE all-time. Manual unpause resets them
-- implicitly via setting state='live' (the next run's increment
-- starts from whatever cumulative number is there — operator can
-- zero them in the same UPDATE if they want a clean slate).
--
-- All four columns default to 0 / NULL so existing rows are
-- backfill-safe. probe_errors (transport / fetch exceptions, NOT
-- content-thin/long) is tracked separately so flaky network does
-- not cause auto-pause.

ALTER TABLE redesign_source_configs
  ADD COLUMN IF NOT EXISTS probe_attempts   INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS probe_drops_thin INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS probe_drops_long INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS probe_errors     INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS paused_at        TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS paused_reason    TEXT;

COMMENT ON COLUMN redesign_source_configs.probe_attempts IS
  'Cumulative count of articles probed (full_round phase_a_probe). Drop-rate denominator.';
COMMENT ON COLUMN redesign_source_configs.probe_drops_thin IS
  'Cumulative drops where body word_count < PROBE_MIN_WORDS. Counted toward auto-pause.';
COMMENT ON COLUMN redesign_source_configs.probe_drops_long IS
  'Cumulative drops where body word_count > PROBE_MAX_WORDS. Counted toward auto-pause.';
COMMENT ON COLUMN redesign_source_configs.probe_errors IS
  'Cumulative probe-fetch exceptions (network / 5xx / parser). NOT counted toward auto-pause — transient blips should not pause sources.';
COMMENT ON COLUMN redesign_source_configs.paused_at IS
  'When the source entered state=paused. NULL if currently live.';
COMMENT ON COLUMN redesign_source_configs.paused_reason IS
  'Reason for pause (auto-pause sets ''high_probe_drop_rate''; manual pauses can use other strings). NULL when state=live.';
