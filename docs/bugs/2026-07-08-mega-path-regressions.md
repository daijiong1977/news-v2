# 2026-07-08 — mega-path-regressions

**Severity:** high
**Area:** pipeline + infra (workflows)
**Status:** fixed
**Keywords:** mega, phase_a_light, feedparser, freshness, html_list, feed_kind, backfill, n=3, dedup, probe_attempts, probe_errors, next_pickup_at, slot-hog, watchdog, pipeline_variant, auto

## Symptom

Four regressions introduced by the ~2026-07-02 cutover to the mega pipeline
variant, found by a systematic code review (three parallel reviewers), each
verified in code and/or live data:

1. **Freshness filter dead** — `phase_a_light` called `feedparser.parse`
   directly and took `entries[:4]`, bypassing `fetch_rss_entries`'
   5-day `max_age_days` guard. Bug 2026-05-01-rss-freshness-no-filter had
   silently regressed. It also bypassed past-run dedup (`filter_past_duplicates`
   is legacy-path-only), so a sticky top-of-feed story could republish on
   consecutive days.
2. **html_list sources dead** — the same bypass skipped `fetch_source_entries`'
   feed_kind dispatch, so the 3 html_list sources (DOGOnews, NG Kids Space /
   Geography) produced 0 briefs. Live data: all three last shipped exactly
   2026-07-02 (the cutover day).
3. **3-source ceiling, no backfill** — mega picked `load_sources(cat)` with the
   default `n=3` and the runtime backfill (POOL_DEPTH=12) exists only in legacy
   `main()`; one bad feed day collapsed a category to 2/3 (Fun 2026-06-12/13).
4. **Watchdog retried the wrong pipeline** — pipeline-watchdog.yml hardcoded
   `-f pipeline_variant=current` and daily-pipeline.yml defaulted `'current'`
   in three places, so a failed mega run was retried on the LEGACY pipeline
   (ignores mega checkpoints, double LLM cost, upserts over mega's rows).

Related standing defect fixed in the same batch: sources that are picked but
ship nothing are never re-stamped, so their stale `next_pickup_at` sorts
most-overdue forever and hogs 1 of the pickup slots daily (the PBS failure
mode; NPR Health was doing it live at 2026-06-01). The `probe_*` columns
existed but were written by nothing.

## Root cause

`main_mega()` was built as a light-weight parallel path and reimplemented
Phase A ad hoc (`feedparser.parse` inline) instead of reusing the
feed-kind-aware, freshness-filtered `fetch_source_entries`; the legacy path's
supply-resilience helpers (backfill, dedup) were never ported; and the
workflow defaults were written when `current` was production and never
updated after the cutover. The rotation only ever learned from success
(shipping stamps `next_pickup_at`); failure taught it nothing.

## Fix

PR: fix/mega-p0-regressions.

- `pipeline/full_round.py::phase_a_light` — now routes through
  `fetch_source_entries` (freshness + feed_kind restored). Verified live:
  html_list sources 0 → 6 briefs.
- `pipeline/full_round.py::filter_past_duplicate_briefs` (+ pure
  `_drop_dup_briefs`) — 3-day title-similarity dedup for mega briefs,
  called in `_phase_a_runner`; fail-open on DB errors.
- `pipeline/full_round.py::main_mega` — `load_sources(cat, n=8)` (was 3):
  briefs are metadata-only so the wider pool is ~free and one dead feed no
  longer collapses a category; checkpoint source-lookup now loads `n=999`
  so hydration covers any source a prior attempt picked.
- `pipeline/full_round.py::stamp_probe_outcomes` (+ pure `_probe_bump`) —
  after persist, every picked-but-unshipped source gets `probe_attempts+1`
  (`probe_errors+1` when it produced zero briefs) and, when its
  `next_pickup_at` is unset/overdue, a bump to tomorrow — a failing source
  now degrades gracefully instead of monopolizing the most-overdue slot.
  Skipped on RESUME runs (picked set unknown).
- `.github/workflows/daily-pipeline.yml` — `pipeline_variant` input gains
  `auto` (new default); `cron_check` runs on every trigger and is the single
  variant resolver: explicit input > `redesign_cron_config` > `'mega'`
  fallback (was `'current'` in all three fallbacks). The admin `enabled`
  flag still gates only scheduled runs.
- `.github/workflows/pipeline-watchdog.yml` — retry dispatches
  `pipeline_variant=auto` (was hardcoded `current`).

## Invariant

1. Mega Phase A MUST fetch through `fetch_source_entries` — never raw
   feedparser — so freshness and feed_kind dispatch cannot silently diverge
   between pipeline variants.
2. Every picked source gets an outcome stamp each run: shipped → cadence
   stamp (persist path), unshipped → probe counters + overdue-bump. No
   source may retain a stale most-overdue `next_pickup_at` across a run it
   was picked for.
3. Exactly one place resolves the effective pipeline variant (daily-pipeline
   `cron_check`); no workflow may hardcode a variant in a retry/dispatch.

## Pinning test

`python -m pipeline.test_mega_pickup_fixes` (6 tests: dispatcher routing +
bad-source resilience, brief dedup, probe-bump rule). Live check: DOGOnews /
NG Kids produce briefs via `phase_a_light`; `redesign_source_configs.probe_*`
columns start moving after the next short day.

## Related

- `docs/bugs/2026-07-07-pbs-waf-bot-challenge.md` — the slot-hog mechanism
  this batch closes generically.
- `docs/bugs/2026-05-01-rss-freshness-no-filter.md` — the regressed-and-now-
  restored freshness guard.
- Follow-up (not in this PR): DOGOnews html_list briefs arrive with empty
  titles (scraper extraction gap) — they flow through but rank poorly with
  the curator, which scores on title+summary. Fix in `pipeline/scraper.py`.
- Follow-up: remaining P1 review findings (RESUME int-key break, self-graded
  safety, insert_run silent-skip, same-day orphan slots).
