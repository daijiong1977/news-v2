-- Hourly sweep for zombie redesign_runs rows.
--
-- Problem: when the pipeline crashes via uncaught exception (RuntimeError
-- in batch_vet) or SystemExit (pack_and_upload abort), the final
-- "status='failed'" PATCH never runs. The row stays with status='running'
-- and finished_at=NULL forever, polluting the dashboard.
--
-- Fix: sweep every hour. Anything still 'running' more than 90 minutes
-- after started_at is dead — the pipeline timeout is 90 min, so a row
-- past that window with no finished_at must have crashed.
--
-- Safe by construction: if a healthy run finishes in <90 min the row is
-- already status='completed' before the sweep can touch it.

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Idempotent: drop any prior version of this job, then re-add.
DO $$
DECLARE
    j_id bigint;
BEGIN
    SELECT jobid INTO j_id FROM cron.job WHERE jobname = 'cleanup-zombie-runs';
    IF j_id IS NOT NULL THEN
        PERFORM cron.unschedule(j_id);
    END IF;
END$$;

SELECT cron.schedule(
    'cleanup-zombie-runs',
    '0 * * * *',  -- every hour, on the hour
    $sweep$
        UPDATE redesign_runs
        SET status = 'failed',
            finished_at = NOW(),
            notes = COALESCE(notes, '') ||
                    ' (zombie sweep: pipeline crashed before final status write)'
        WHERE status = 'running'
          AND started_at < NOW() - INTERVAL '90 minutes'
          AND finished_at IS NULL;
    $sweep$
);
