# 2026-07-07 — runs-status-check-mislabel

**Severity:** high
**Area:** infra (schema) + observability
**Status:** fixed
**Keywords:** redesign_runs, status, check-constraint, 23514, zombie-sweep, completed_with_warnings, persisted, false-failure, monitoring

## Symptom

The `redesign_runs` dashboard / daily digest showed the pipeline "failing"
(status `failed`, note "pipeline crashed before final status write") on ~37% of
days (14 of 38 runs). Every category-shortfall day appeared as a crash, which
made it look like shortfalls were caused by crashes. But the GitHub Actions
"Daily pipeline" job **succeeded** on all those days, content **was** persisted
(8–9 stories) and **deployed** to prod. Six of the 14 "failed" runs even had the
full 9 stories — no shortfall at all.

## Root cause

`redesign_runs.status` had a CHECK constraint allowing only
`{running, completed, failed}`:

```
CHECK (status = ANY (ARRAY['running','completed','failed']))
```

But `pipeline/full_round.py` writes a wider set:
- `persisted` (intermediate, lines 1235 / 1642)
- `completed_with_warnings` when `telemetry["warnings"]` is non-empty (line 1275)
- `deploy_failed` on upload failure (line 1282)

On any run with a warning (a short category, or a "reasoner repaired N times"
note, etc.), the terminal `update_run(status='completed_with_warnings')` was
**rejected by the constraint** (Postgres 23514). `update_run` logs the error and
returns falsy, but the pipeline had already deployed and exited 0, so the GH job
was green. The run row was never moved off `running`, and the hourly zombie
sweep (`20260503_zombie_runs_sweep.sql`) then relabeled it `failed` with
"crashed before final status write".

Nothing caught it because: the failing write is non-fatal (only logged), the job
exits 0, and the zombie sweep's note actively *asserts* a crash — so the false
signal was self-confirming. The zombie-sweep migration author diagnosed these as
`RuntimeError in batch_vet` / `SystemExit in pack_and_upload` crashes; the logs
show no such crash, only the 23514 rejection.

## Fix

PR: fix/runs-status-check-widen.

- `supabase/migrations/20260707_widen_runs_status_check.sql` — drop + re-add the
  constraint allowing the full set the code writes
  (`running, persisted, completed, completed_with_warnings, deploy_failed,
  failed`). Widening an allowlist can't violate existing rows, so it validates
  instantly.
- Data correction (one-off): the 14 mislabeled rows (all zombie-swept, all with
  8–9 stories persisted that day) were re-set from `failed` to
  `completed_with_warnings`, with a `[corrected …]` note appended so the history
  reads true.

After this, warning days record `completed_with_warnings` (not a false
`failed`), and the zombie sweep only fires on genuine stuck-`running` crashes —
so a real future crash actually stands out.

## Invariant

The `redesign_runs.status` CHECK constraint MUST be a superset of every status
literal written by `pipeline/full_round.py` / `pipeline/main.py`. If a future
change introduces a new status value, extend the constraint in the same PR.
Grep for `"status":` writes to `redesign_runs` before editing this constraint.

## Pinning test

`update redesign_runs set status='completed_with_warnings' where id=<any>`
succeeds (it did, during the history relabel — that write would have failed
23514 before this migration). Longer-term: no run should sit at `running` after
the daily job finishes unless the process genuinely died.

## Related

- `docs/bugs/2026-07-07-pbs-waf-bot-challenge.md` — the actual News-supply cause
  this mislabel was masking.
- `supabase/migrations/20260503_zombie_runs_sweep.sql` — the sweep whose note
  ("crashed before final status write") was the misleading signal.
