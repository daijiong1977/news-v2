# 2026-08-25 — Mega-curator CoT truncation at 20k on V4 Flash killed the daily run

## Symptom

Daily pipeline failed twice on 2026-08-25 (scheduled run 32878436351 at
17:32 UTC, manual retry 32878884182 at 17:36 UTC), both ~4 min in, with:

```
RuntimeError: reasoner output truncated (max_tokens=20000 hit);
split-batch fallback in caller will shrink the payload
```

raised from `pipeline/news_rss_core.py:1492` via
`pipeline/mega_curator.py:165` (stage2_picks). No articles published.
DeepSeek dashboard showed only ~$0.02 usage — the run died at stage 2,
so almost nothing downstream ran.

## Root Cause

DeepSeek V4 Flash (the only enabled provider since V4 Pro was disabled
in `redesign_ai_providers` on 2026-08-23) is a thinking model whose
`reasoning_content` counts against `max_tokens`. With 30 candidates,
today's news mix drove the chain-of-thought past the 20k budget before
the JSON answer finished — same failure family as the 6k→12k→20k bumps
(runs 24921275967, 24997954155). CoT length is content-dependent:
yesterday's run passed with the same model and the same candidate count.

Aggravating factor: the error message promises a "split-batch fallback
in caller", but `mega_curate()` has no such fallback — truncation
crashes the entire run.

## Fix

Single-line knob bump in `pipeline/mega_curator.py`: `max_tokens`
20000 → 65536. Verified `api.deepseek.com` accepts `max_tokens` up to
131072 for `deepseek-v4-flash`, and billing is per generated token, so
the headroom costs nothing unless used.

## Verification

- Tiny live API probes confirmed: (a) `reasoning_content` consumes the
  `max_tokens` budget (10-token probe returned empty content,
  `finish_reason: length`); (b) 131072 and 65536 are accepted.
- Pipeline re-run via `workflow_dispatch` after the fix completed
  stage2_picks without truncation.

## Lessons

- Third truncation bump on this same call site. If it truncates again
  even at 64k, stop bumping — implement the caller-side split-batch
  (per-category calls) that the error message already advertises, or
  disable thinking for this call.
- A thinking model's reasoning budget shares `max_tokens` with output;
  sizing `max_tokens` to the output schema alone is always wrong for
  `"thinking": {"type": "enabled"}` providers.
- Provider changes in `redesign_ai_providers` (V4 Pro disabled
  2026-08-23) shift CoT length characteristics; token budgets sized for
  one model silently under-fit another.
