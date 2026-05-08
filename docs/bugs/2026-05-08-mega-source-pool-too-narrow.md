# 2026-05-08 — mega-source-pool-too-narrow

**Severity:** high
**Area:** pipeline
**Status:** fixed
**Keywords:** load_sources, mega, phase_a_light, phase_a_probe, source-diversity, cadence, fallback, auto-pause, probe_drops_thin

## Symptom

Daily quality digest flagged Fun category for two days running:
```
2026-05-08 · FUN: only 1/3 distinct sources. Fix: add more sources …
2026-05-07 · FUN: only 2/3 distinct sources. Fix: add more sources …
```

Today (2026-05-08) all 3 ranked Fun stories came from IndieWire. Yesterday
2 of 3 came from Kotaku. Fix-suggestion text in the digest told the
operator to "add more sources" — but `redesign_source_configs` already
held **21 enabled live sources** for Fun, so the suggestion was wrong
and never would have helped.

## Root cause

Two parallel pipelines coexist in `pipeline/full_round.py`:

- **Legacy `aggregate_category` path** (line 1109-1129) loaded
  `db_config.load_sources(cat, n=POOL_DEPTH=12)` and ran a runtime
  source-by-source backfill until 3 distinct sources contributed
  candidates.
- **Mega path `phase_a_light`** (line 1367) called
  `db_config.load_sources(cat_name)` with no `n` — which meant **the
  default `n=3` from `db_config.py:123` was used**. Only 3 sources per
  category entered the pipeline.

Production runs only the mega path (telemetry rows since 2026-05-04 only
contain `phase_a_light` / `phase_a_probe` / `stage2_curator` —
`aggregate` block is absent). So what looked like a 21-source rotation
was actually a 3-source rotation, with no diversity backstop.

When 1-2 of those 3 sources lost most of their articles in
`phase_a_probe` (body too thin / too long for `[350, 1200]` words),
**the surviving pool collapsed onto whichever single source had healthy
articles**. Telemetry on 2026-05-08 for Fun:

```
phase_a_light:  Fun=8 briefs from 3 sources (some had < 4 entries past freshness)
phase_a_probe:  Fun=3 kept (6 dropped thin, 1 long)
stage2_curator: Fun=3 picks  ← curator only had 3 to pick from
```

The cadence-aware `load_sources` already had a sleeping-source fallback
(`picked = eligible[:n] + sleeping[:n - len(picked)]`), but with `n=3`
and 3 eligible sources every day, the fallback path was dead code.

There was also no signal to the operator that a particular source was
chronically failing the probe gate — every day the same domains tripped
the thin-body filter, and there was no mechanism to cool them off
automatically.

## Fix

PR #24 — three coordinated changes:

1. **`pipeline/db_config.py:121-200`** — replaced `n: int = 3` with
   `min_pool=6, max_pool=None`. New semantics: return ALL eligible
   sources (capped at `max_pool` if set). If eligible count < `min_pool`,
   top up with sleeping sources (closest-to-expiring first) to reach
   `min_pool`, no further. Sleeping sources keep their cadence rest
   unless eligible can't carry the run.

2. **`pipeline/full_round.py:1366-1383`** — wired the mega
   `_phase_a_runner` to call `load_sources(cat_name, today=today_d_mega)`
   with the new defaults (no `n`, no cap → all eligible + needed
   sleeping). Legacy `aggregate_category` callers now pass
   `max_pool=POOL_DEPTH` explicitly to preserve their hard cap of 12.

3. **`pipeline/full_round.py:1404-1531`** — per-source probe drop
   counters in `_stage1_5_runner`. Each probe attempt is attributed to
   `brief["_source_name"]`; thin/long drops increment per-source counts.
   After the run, `_stamp_probe_health` UPSERTs cumulative counters
   (`probe_attempts`, `probe_drops_thin`, `probe_drops_long`) on
   `redesign_source_configs` and auto-pauses any source where
   `drops/attempts >= 0.6 AND attempts >= 10` by setting
   `state='paused'`, `paused_at=now()`, `paused_reason='high_probe_drop_rate'`.
   `load_sources` filters out paused rows so they never re-enter a pool
   until admin manually unpauses (sets `state='live'`).

Migration `add_source_probe_health_counters` adds the four new
columns to `redesign_source_configs` (defaulted to 0 / NULL).

## Invariant

**The mega path's `phase_a_light` MUST be called on a pool that contains
either all eligible sources for the day OR enough fallback sleeping
sources to absorb downstream probe drops.**

Concretely:
- `load_sources(cat)` with default args returns the pool that the mega
  pipeline trusts. Never call it with a hard cap < 6 from the mega path.
- `min_pool` is the floor that triggers sleeping fallback. Never lower
  it without checking that probe drop rate × pool size keeps the
  curator's input at or above the diversity target (3 distinct sources).
- Sleeping sources are tapped only when eligible can't carry the run.
  Don't pre-populate sleeping into the pool "just in case" — that
  consumes their cadence rest unnecessarily.
- Auto-paused sources with `state='paused'` MUST be invisible to
  `load_sources`. The candidate filter in `db_config.py:163-167`
  enforces this; do not add new code paths that bypass it.

## Pinning test

`pipeline/test_load_sources.py` — 12 tests covering:
- `test_eligible_first_skips_sleeping_when_enough` — 7 eligible, 2
  sleeping, `min_pool=6` → all 7 eligible returned, neither sleeping
  source picked.
- `test_sleeping_fills_only_shortfall` — 2 eligible, 5 sleeping,
  `min_pool=6` → 2 eligible + first 4 sleeping (closest to expiring).
- `test_paused_excluded` — `state='paused'` row never appears in the
  pool even when eligible by date.
- `test_max_pool_caps_eligible` — 15 eligible, `max_pool=5` → exactly 5
  returned (preserves legacy `aggregate_category` ceiling).
- All previously-passing tests retained (parameter renamed `n` →
  `max_pool` per call site).

Run: `python -m pipeline.test_load_sources` from repo root with venv
activated. Expect: `All 12 tests passed.`

For the autopause logic, the path is exercised end-to-end on the next
3 AM EDT cron — telemetry will surface `per_source: {<name>: {attempts,
thin, long}}` blocks under `phase_a_probe`, and any source that
crosses the 60% / 10-attempts threshold will appear paused on the next
fire (visible in admin → Sources, with `paused_reason` populated).
