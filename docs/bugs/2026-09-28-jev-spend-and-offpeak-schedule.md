# 2026-09-28: JEV spend investigation and Eastern off-peak schedule

## Decision

Schedule the daily production run at **06:10 America/New_York**, including
daylight-saving changes. DeepSeek's published weekday peak ends at 06:00 EDT
or 05:00 EST, so a promptly started run is off-peak. GitHub Actions supports
an IANA `timezone` on `on.schedule`; scheduled runs may still be delayed, so
this is a target time, not an SLA. The workflow file is now the schedule's
source of truth. Schedule changes require a PR; the old UTC cron bot may not
push directly to `main`. The admin page retains the enable and variant controls
but no longer edits a misleading UTC cron value.

Official references: <https://api-docs.deepseek.com/quick_start/pricing/> and
<https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule>.

## What the runs actually sent to JEV

| Run | Type | Prefilter | After body probe / rank | Pair checks | Observed failures |
| --- | --- | ---: | ---: | ---: | --- |
| [2026-09-24 scheduled](https://github.com/daijiong1977/news-v2/actions/runs/35968254822) | baseline | 92/92 in 3.8s; 9 dropped | 72/72 in 5.7s | 18 | none in logged summary |
| [2026-09-27 scheduled](https://github.com/daijiong1977/news-v2/actions/runs/36302246549) | comparison | 90/90 in 3.5s; 10 dropped | 64/64 in 5.7s | 26 | none in logged summary |
| [2026-09-28 scheduled](https://github.com/daijiong1977/news-v2/actions/runs/36391689636) | first run that day | 95/95 in 3.7s; 10 dropped | 66/66 in 13.6s | 75 | one DeepSeek retry, not a JEV error |
| [2026-09-28 manual](https://github.com/daijiong1977/news-v2/actions/runs/36427645986) | second full run | 104 submitted; 60s budget exceeded; pass ignored, zero dropped | 81/81 in 92.7s | 17 | JEV 503/connect timeouts in prefilter and two topic labels |

The 9/28 manual run also routed all 81 viable briefs by section and attempted
topic labels on the ranked catalog. The labels reported News 28 tagged / 4
uncertain, Science 16 tagged / 1 failed, and Fun 12 tagged / 1 failed. This
is substantial additional JEV work beyond the prefilter/rank numbers in the
table. Previous runs also had routing and topic calls, but fewer labels were
needed in the older, shorter candidate catalog.

The manual run's prefilter was **fail-open**: after its 503/time-budget issue,
all 104 briefs continued. This preserved editorial coverage but spent time
and may have caused billable attempted work before later JEV stages ran.

The user's dashboard observations were about $0.005/day last week and $0.04
today. Logs do **not** contain itemized JEV charges or a billing timezone.
Two full runs, a larger candidate catalog, more topic labels, and failed
requests/retries are plausible contributors. They do not prove which stage
accounts for the eightfold dollar difference. Do not infer dollars per call
from elapsed seconds or treat JEV and DeepSeek charges as one bill.

## Cost reduction experiment (not enabled yet)

Candidate idea: one DeepSeek *numbered-list* pre-pick on the post-probe catalog,
followed by JEV ranking only the top ~30 **per category or a globally balanced
quota**. The prompt would return indices only, retain a reserve catalog, and
be evaluated against previous published picks before production use. A hard
top-30 globally could starve Science/Fun or remove the US-child-impact News
story; it is not safe to deploy solely from one day of samples. Another
option is a short JEV health probe before fanning out ~100 prefilter calls,
but skipping JEV on a transient error may worsen categorization. Neither
option touches the independent full-text child-safety review.

Before selecting an optimization, collect per-stage request counts, failures,
token/charge detail from the JEV billing dashboard if available, and compare
one scheduled run with one scheduled run. Avoid manual reruns in the daily
cost baseline; their incremental cost is real.

## Verification after merge

Confirm the first natural scheduled run starts near 06:10 Eastern (GitHub can
delay cron), uses the intended `main` commit, finishes all three stages, and
syncs the website. Inspect the JEV bill for that *single* run/day before
changing the selection algorithm.
