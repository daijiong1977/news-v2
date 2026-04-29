# 2026-04-28 — news-source-diversity

**Severity:** high
**Area:** pipeline
**Status:** fixed
**Keywords:** spare-promotion, diversity, validator, used-source-names, Stage 3, NPR

## Symptom

The day's News bundle had two NPR articles (rank-1 and rank-3) and
zero PBS articles. Diversity policy is "3 different sources per
category", explicitly stated in the curator config.

## Root cause

The diversity validator ran ONCE post-Stage-2 curator and produced
a diverse top-3 (NPR / PBS / AJ). Then Stage 3 safety rejected the
PBS pick. `promote_spare_and_rewrite()` blindly took rank_4 — also
NPR — without re-checking diversity. The validator wasn't re-run
after spare promotion because it lived only in the curator stage.

The validator's input was `top_3`; the spare promoter's input was
`spares` ordered by rank. They didn't share state about which
sources had already been used in the surviving picks.

## Fix

- `pipeline/full_round.py` — `promote_spare_and_rewrite()` now
  takes `used_source_names: set[str]` and runs two-pass selection:
    - Pass 1: prefer spares whose source is NOT in `used_source_names`
    - Pass 2: fall back to any spare if no diverse option exists
- The Stage 3 loop recomputes `used_names` from `survived_winners`
  on every iteration so each promotion respects the latest set:

```python
used_names = {w["source"].name for w in survived_winners if w.get("source")}
```

## Invariant

After Stage 3 spare promotion, the final top-3 within each category
MUST come from at least 3 distinct source names whenever 3+ distinct
sources are available in the spare pool. Any future change to
spare-promotion MUST pass `used_source_names` through and prefer
diverse sources unless the pool has none.

If the spare pool genuinely doesn't contain 3 distinct sources, the
fallback to a duplicate is allowed but should log a warning so we
notice when the source pool is too narrow.

## Pinning test

Pipeline-level smoke (run after each pipeline cycle):
- After full_round completes, read the day's `articles_news_*.json`
  and assert the three `source` fields contain ≥ 3 distinct names.
- Failure path: log + alert; do NOT silently publish a duplicated
  source bundle.

Manual: read latest `news.6ray.com` News column — confirm three
different sources by sight.

## Related

- The keyword-stem fix (`2026-04-28-keyword-stem-mismatch.md`)
  shipped in the same pipeline cycle and is independent.
- The source-pool-too-narrow case (currently logs nothing) is a
  followup gotcha worth recording in `docs/gotchas.md` if it ever
  fires in production.
