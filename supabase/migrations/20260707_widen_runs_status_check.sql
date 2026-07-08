-- Widen redesign_runs.status CHECK to match the values the pipeline writes.
--
-- Bug (docs/bugs/2026-07-07-runs-status-check-mislabel.md):
--   full_round.py writes status in
--     {running, persisted, completed, completed_with_warnings, deploy_failed, failed}
--   but the original constraint only allowed {running, completed, failed}.
--   So every 'persisted' (intermediate) write and — on ANY warning day — the
--   terminal 'completed_with_warnings' write was rejected (SQLSTATE 23514).
--   The row was therefore never updated off 'running', and the hourly
--   zombie-sweep (20260503_zombie_runs_sweep.sql) then flipped the SUCCESSFUL,
--   already-deployed run to 'failed' with the misleading note
--   "pipeline crashed before final status write". Every warning day looked like
--   a crash; run monitoring was untrustworthy.
--
-- Fix: allow the full set the code actually writes. Widening an allowlist
-- CHECK cannot violate existing rows (all are completed/failed/running), so the
-- ALTER validates instantly and is non-blocking on this small table.

ALTER TABLE public.redesign_runs
  DROP CONSTRAINT IF EXISTS redesign_runs_status_check;

ALTER TABLE public.redesign_runs
  ADD CONSTRAINT redesign_runs_status_check
  CHECK (status = ANY (ARRAY[
    'running',
    'persisted',
    'completed',
    'completed_with_warnings',
    'deploy_failed',
    'failed'
  ]::text[]));
