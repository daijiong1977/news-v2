# 2026-09-26 — Seven-day cross-category event dedup

**Severity:** medium
**Area:** pipeline
**Status:** fixed
**Keywords:** cross-category, event, duplicate, Fat Bear Week, Jev, seven-day

## Symptom

Fat Bear Week shipped as News on 2026-09-19 and Fun on 2026-09-26.
The two source headlines differ, but Jev's existing same-single-event
question scored them 0.68 in the 2026-09-26 candidate replay.

## Root cause

The cheap past-run title filter looked only within each category and three
prior days. The Jev event comparison did cross categories, but also looked
back only three days. Correcting the section alone could not prevent a
seven-day repeat.

## Fix

- Both past-run lookups now use the half-open seven-day window
  `[run_date-7, run_date)` across all categories and non-archived rows.
- Near-identical headlines are removed by code before body fetching. Jev
  receives only plausible reworded pairs sharing at least two content words.
- Jev ranking telemetry records the historical event-check call count and
  input/output tokens separately from other pair calls.

## Invariants

- A same-day rerun must not compare with its own earlier attempt.
- Topic diversity is a soft selection preference; same-event dedup is a
  separate hard gate across categories.
- The independent full-text child-safety review remains unchanged.

## Cost check

Using the 2026-09-26 probe checkpoint (67 candidates), title preselection
yielded 8 possible Jev pairs at three days and 19 at seven days (17 unique
title pairs). A four-worker live Jev replay of the 17 unique pairs took
0.85 seconds wall time. One response reported 331 input and 21 output
tokens; the sample is not a substitute for measured production usage.

## Pinning tests

`python -m pytest -q pipeline/test_filter_polish.py pipeline/test_jev_rank.py`

## Related

- `docs/bugs/2026-09-20-past-dedup-self-poisons-reruns.md`
- `docs/bugs/2026-09-26-event-family-and-category-overlap.md`
