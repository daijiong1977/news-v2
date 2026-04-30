# 2026-04-29 — autofix-token-starvation

**Severity:** medium
**Area:** infra
**Status:** fixed
**Keywords:** claude, headless, daemon, rate-limit, concurrency, autofix, launchd

## Symptom

Owner's Claude Code IDE suddenly couldn't connect after the autofix
launchd daemon's first tick fired. Stopping the daemon process and
waiting ~2 min restored the IDE connection.

## Root cause

`scripts/autofix-daemon.sh` invoked `python -m pipeline.autofix_consumer`
without the `--once` flag, so the consumer's `run_one_tick()` loop
drained the entire 4-item queue back-to-back. Each item spawned a
fresh `claude -p` subprocess, and each subprocess used the **same
account token** as the user's interactive IDE.

Three sequential `claude -p` runs across ~6 minutes (each ~2 min)
saturated the account's concurrency / quota window for the Pro tier.
While the daemon was active, IDE requests were either throttled or
rejected. Cooldown ≈ 2 min after the daemon stopped → IDE recovered.

The Invariant we accidentally violated: **a background headless agent
running on the user's account must not monopolize their token.**

## Fix

Commit: `<pending>` after this record.

`scripts/autofix-daemon.sh` now passes `--once` to the consumer so
each launchd tick processes exactly one queued item. Combined with
the existing `StartInterval=28800` (8h ticks), the daemon spends
~3 min on Claude per 8h window — ≈0.6% duty cycle. Plenty of
headroom for interactive IDE work.

Tradeoff: a queue of N items takes 8N hours to fully drain. For our
scale (≈0-2 new quality issues per pipeline day) that's fine. If a
backlog ever builds up (e.g. several days of pipeline failures), the
owner can manually drain by running
`python -m pipeline.autofix_consumer` (no `--once`) during a window
when they're not using Claude IDE.

## Invariant

Any background process that spawns `claude -p` (or any other CLI that
shares the user's Anthropic account token) MUST:

1. Process at most ONE agent invocation per tick.
2. Schedule ticks far enough apart (≥ ~30 min) that the cumulative
   duty cycle stays below ~5% of the user's interactive session
   budget.
3. Or: use a SEPARATE Anthropic API key (not the IDE's account
   token) for the headless work, so the two pools don't collide.

If a future change adds another launchd / cron consumer that calls
`claude -p`, this invariant must be re-verified — the cumulative
duty cycle is the property that matters, not any one consumer's
local scheduling.

## Pinning test

Manual: with the daemon installed, observe the IDE remains usable
during a daemon tick. If a regression breaks that, the symptom is
"IDE drops connection for 1-3 min when daemon ticks" — log into the
IDE, check `~/Library/Logs/kidsnews-autofix/$(date -u +%Y-%m-%d).log`
for back-to-back `spawning claude` lines without `--once` in the
invocation.

## Related

- `docs/superpowers/specs/2026-04-29-quality-digest-email.md` — the
  Plan C autofix architecture this constrains.
- `feedback#10` / `gh-issue#5` — the original feature request that
  introduced the daemon.
