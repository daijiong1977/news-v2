# 2026-05-01 — quality-digest-schedule-wait-crash

**Severity:** medium
**Area:** infra (CI workflow)
**Status:** fixed
**Keywords:** github-actions, quality-digest, workflow_run, schedule, github.event.schedule, fromisoformat, cron-string, backup-cron

## Symptom

Today's quality-digest run via the backup cron (`30 5 * * *`,
fired at 2026-05-01 06:28 UTC) failed at the *Wait until 92 min
after pipeline TRIGGER time* step. Result:

- The wait step itself returned non-zero exit.
- All subsequent steps (autofix scan, autofix apply, send digest,
  cron-sync) were SKIPPED by GitHub Actions' default failure
  behaviour.
- No digest email sent that morning.

The normal `workflow_run` path (fired ~92 min after `Daily
pipeline` finishes) still works — only the schedule-backup path
broke.

## Root cause

`.github/workflows/quality-digest.yml` had this env binding on the
wait step:

```yaml
env:
  TRIGGER_TIME: ${{ github.event.workflow_run.run_started_at || github.event.schedule || '' }}
```

The intent was: "use the upstream pipeline's start time when
fired by `workflow_run`; fall back to schedule for backup runs".
But for `schedule` events, **`github.event.schedule` is the cron
expression STRING** (e.g. `"30 5 * * *"`), not a timestamp. So
the next line:

```bash
TRIGGER_EPOCH=$(python3 -c "from datetime import datetime; print(int(datetime.fromisoformat('$TRIGGER_TIME'.replace('Z','+00:00')).timestamp()))")
```

executed as `datetime.fromisoformat("30 5 * * *")` → ValueError →
`set -e` → step exits non-zero → cascade-skip downstream.

The `[ -z "$TRIGGER_TIME" ]` empty-string guard didn't catch this
because the cron string isn't empty. The bug only surfaces on the
backup cron path; `workflow_run` path always populates with a
proper ISO timestamp.

## Fix

`.github/workflows/quality-digest.yml` — narrow the wait step's
`if:` condition to only fire on `workflow_run` events:

```yaml
if: ${{ steps.guard.outputs.should_run != 'false'
        && inputs.skip_sleep != true
        && github.event_name == 'workflow_run' }}
```

For the schedule path (backup): the wait is unnecessary anyway —
the schedule cron is the *fallback* that fires regardless of
upstream pipeline state, so it should send the digest immediately
without a 92-min anchor. With the new condition, the wait step
is silently skipped on schedule events, downstream steps run
immediately.

Also simplified `TRIGGER_TIME` to drop the now-pointless schedule
fallback expression: `${{ github.event.workflow_run.run_started_at }}`.

## Invariant

Any future "wait N minutes after upstream" logic in CI yaml MUST
gate on `github.event_name == 'workflow_run'`. The
`github.event.schedule` field is a STRING (the cron expression),
not a timestamp — never feed it directly to a datetime parser.

If a similar pattern appears elsewhere (e.g., a future "wait for X
to finish" step), apply the same gating.

## Pinning test

After deploy, manually dispatch the digest with `skip_sleep=false`
under the schedule path is hard to simulate, but the next backup
cron firing (any morning the upstream pipeline didn't fire on
schedule) will exercise the path. The wait step should appear as
"skipped" in that run's step list, with downstream steps showing
"success".

The normal workflow_run path (the daily 17:20 UTC pipeline → ~92
min wait → digest send around 18:50 UTC) MUST stay green; this
fix doesn't change that path.

## Related

- `.github/workflows/quality-digest.yml:111` — the wait step.
- `.github/workflows/quality-digest.yml:24-30` — the three trigger
  types (`workflow_run`, `schedule`, `workflow_dispatch`).
- `.github/workflows/daily-pipeline.yml:27` — the upstream pipeline
  cron `20 17 * * *`. When pipeline runs successfully, `workflow_run`
  fires the digest ~immediately, the wait step delays it to the
  92-min anchor.
- 2026-04-30 commit `f01be1f` `chore(digest): anchor sleep on
  pipeline trigger+92min for predictable email timing` — original
  introduction of the 92-min anchor logic. The schedule-fallback
  expression was added defensively but the cron-string-vs-timestamp
  semantic difference was missed at the time.
