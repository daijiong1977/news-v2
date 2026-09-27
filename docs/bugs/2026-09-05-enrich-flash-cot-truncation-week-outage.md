# 2026-09-05 — Enrich truncation at 20k on V4 Flash failed every daily run 08-29 → 09-05

## Symptom

Every Daily pipeline run from 2026-08-29 through 2026-09-05 (both
scheduled and manual retries, ~14 runs) failed at the PACK + UPLOAD
stage with `Bundle validation FAILED — refusing to pack/upload`:
slots missing `questions` (need ≥3), `background_read` (need ≥1),
`Article_Structure` (need ≥3). No articles published for a week.
Run summaries showed `reasoner_truncated: 1..4` and
`partial enrich (N/6)` warnings.

## Root Cause

Same disease as docs/bugs/2026-08-25-mega-curator-flash-cot-truncation.md,
different call site. `detail_enrich()` in `pipeline/news_rss_core.py`
calls the reasoner per level with `max_tokens=20000`, sized for the
pre-Flash provider. DeepSeek V4 Flash (sole enabled provider since
2026-08-23) spends its chain-of-thought from the same `max_tokens`
budget, so on long-article days the 3-slot enrich calls truncate.
`detail_enrich` swallows the RuntimeError and keeps the other level's
slots — but bundle validation (correctly) refuses to ship articles
with empty questions, so ONE truncated call sinks the entire publish.
2026-09-03: 1/7 truncated → Science 3/6 → dead. 2026-09-05: 4/7
truncated → Fun 0/6 → dead.

The 2026-08-25 fix bumped only the mega-curator call site; the enrich
(20k), vet (12k), and default (16k) budgets were left under-sized.

## Fix

`pipeline/news_rss_core.py`, three numeric knob bumps to 65536:
- `detail_enrich` per-level call: 20000 → 65536 (the failing site)
- curator vet batch call: 12000 → 65536 (no fallback — truncation
  there crashes the run outright)
- `deepseek_reasoner_call` default: 16000 → 65536

API ceiling 131072 verified live for `deepseek-v4-flash`; billing is
per generated token, so unused headroom is free.

## Verification

- 2026-09-05 and 2026-09-03 failed-run logs show the truncation →
  partial-enrich → bundle-validation chain.
- Post-fix `workflow_dispatch` run completed with
  `reasoner_truncated: 0` and published the bundle.

## Lessons

- When a token-budget disease is diagnosed at one call site, grep for
  ALL sibling call sites in the same commit. The 08-25 fix treated one
  symptom and left three identical time bombs; the enrich one detonated
  four days later and cost a week of publishes.
- A stage that "degrades gracefully" (partial enrich) feeding a stage
  that hard-fails on partials (bundle validation) is not graceful — it
  just moves the crash later and makes the log harder to read. The
  failure surfaced 17 min into each run instead of at the truncation.
- Nobody noticed for a week: the watchdog/digest emails either didn't
  fire or weren't read. Worth checking why the failure wasn't surfaced
  on day 1.
