# 2026-09-20 — past-dedup self-poisons same-day re-runs

**Severity:** medium
**Area:** pipeline
**Status:** fixed
**Keywords:** filter_past_duplicate_briefs, past-dup, rerun, re-run, published_date, phase_a, brief drop, thin pool, low pick scores, duplicate

## Symptom

Two full pipeline runs were done back-to-back on 2026-09-20 while testing the
Jev ranking stage. The first produced a good News set (Congo Ebola
vaccinations / White House press ban / Ed Sheeran apology). The **second run,
from the same code, produced a visibly worse one**: a Premier League match
*preview* ("Fulham vs Manchester United – prediction, teams, lineups") and an
adult-politics arrest story ("Russian election observer loses consciousness
during arrest"), neither appropriate for the audience.

The Jev ranker's own scores showed it knew: the bottom of what it sent to the
curator scored `pick=0.33`, versus 0.67/0.55/0.48 on the first run. It was not
choosing badly — it had nothing left to choose from.

    run 1: 62 briefs after the forbidden filter → 44 ranked
    run 2: 51 briefs after the forbidden filter → 35 ranked

## Root cause

`filter_past_duplicate_briefs` (pipeline/full_round.py) drops briefs whose
title ≥80% matches a story the same category published in the last `days`
days:

    start = (date.today() - timedelta(days=days)).isoformat()
    ... .gte("published_date", start).execute()

There is **no upper bound**, so the window is `[today-3, ∞)` — it includes
**today**. On a same-day re-run the pipeline therefore treats *its own
previous attempt's output* as "already published" and drops exactly the
stories it just decided were the best ones.

The invariant that was violated: past-duplicate suppression must compare
against what the reader has *already seen on a previous day*, never against
rows this run is about to replace. A full re-run replaces every row for the
date; a partial re-run (`PIPELINE_CATEGORIES=News`) replaces every row for
that category — and this filter compares within a category, so in both cases
the rows it matched against were rows on their way out.

Nothing caught it earlier because production runs once a day from cron, so the
window's upper end never mattered. It only surfaces when a human re-runs a
day, which is exactly what testing a new stage requires — and then it looks
like a quality regression in the new stage rather than a dedup bug.

Note the related-but-correct code: `_recent_published_titles` (added the same
day for the Jev ranker) already excludes today with `.lt("published_date",
today)`. This fix brings the older filter in line.

## Fix

Commit on branch `jev-rank`. One-line change in
`filter_past_duplicate_briefs`: bound the window with
`.lt("published_date", today)` and pass the run's date in, rather than
recomputing `date.today()` inside the helper (a run that crosses UTC midnight
would otherwise compare against a different day than it publishes to).

`pipeline/test_filter_polish.py` gains a case asserting that a brief matching
a story published *today* survives, while one matching *yesterday* is dropped.

## Prevention

When a filter asks "has this been published before", the window needs both
ends. "Before" means strictly before the current run's date — the run's own
output is not history. Any query used to suppress candidates should be read
with the question "could this ever match a row this run wrote?".
