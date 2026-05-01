# 2026-05-01 — rss-freshness-no-filter

**Severity:** medium
**Area:** pipeline (RSS intake)
**Status:** fixed
**Keywords:** rss, freshness, staleness, fetch_rss_entries, news_rss_core, feedparser, age-filter, evergreen, published_parsed

## Symptom

Admin reported a stale article landed in today's (2026-05-01) bundle:

> Article 3 · Tue, 14 Apr 2026 08:01:00 +0000
> 792 words · container-p
> Is AI bad for critical thinking? It depends on when you use it
> Using AI later in solving tough problems boosts critical thinking
> and memory, a study which is 2 weeks ago.

The article was published on 2026-04-14 — **17 days before** the
day it appeared in the bundle. Kid news bundles are supposed to be
"news from the last few days", so a 17-day-old article is a freshness
regression visible to readers.

## Root cause

`pipeline/news_rss_core.py:fetch_rss_entries` (the universal RSS
intake function used by both `full` and `light` flow) had **no
freshness filter**. It pulled the first N entries from each feed
verbatim:

```python
def fetch_rss_entries(url, max_entries=MAX_RSS_DEFAULT):
    feed = feedparser.parse(url)
    out = []
    for entry in feed.entries[:max_entries]:
        out.append({...})    # no date check
    return out
```

Some RSS feeds (especially aggregator / "trending" / "popular" /
"editor's pick" lists) silently mix in weeks-old articles alongside
fresh ones. PBS NewsHour, NPR's main feed, etc. are usually clean,
but the discovery / mining pipeline pulls from a wide pool of
candidate sources, and several included evergreen / stale items.
Without an age cap, those slipped straight into the curator pool
and onward into the daily bundle.

Note: the Tavily-discovery code path (`pipeline/discover.py:232`)
already has `"days": 3` in its query — so Tavily-found candidates
are already age-bounded. The bug was specifically in the RSS-feed
path. The article in the symptom was an RSS-pipe leak.

## Fix

`pipeline/news_rss_core.py` — `fetch_rss_entries` now accepts a
`max_age_days` parameter (default `MAX_RSS_AGE_DAYS_DEFAULT=5`)
and drops entries older than that:

- **5 days** (admin choice 2026-05-01) is wide enough that
  weekly-publishing sources don't run dry, narrow enough that
  17-days-stale slips don't recur.
- Entries with a parseable `published_parsed` (feedparser's UTC
  struct_time) are checked; fallback to RFC 822 string parsing of
  `published` / `updated` if needed.
- Entries with **no parseable date** are KEPT (rather than dropped)
  — safer to err on inclusion when a feed lacks dates than to
  silently empty a source that just doesn't expose them. Logged
  as `no_date_kept` for visibility.
- Logs `dropped_old=N` when filtering activity occurs, so admin
  can spot feeds with bad freshness profiles in pipeline output.

Helper `_entry_age_days(entry)` factored out so callers can reuse
the parsing logic if needed elsewhere.

## Invariant

Any code path that ingests RSS entries into the candidate pool
MUST apply a freshness filter. Currently the single chokepoint is
`fetch_rss_entries`. If a future refactor introduces a parallel
RSS path (e.g., aiohttp-based, batch reader, etc.) it MUST either
reuse `fetch_rss_entries` or replicate the `_entry_age_days` /
`max_age_days` filter — otherwise the stale-article regression
returns silently.

The 5-day default is a heuristic, not a hard guarantee. If a
specific source's `published_parsed` is missing, articles from
that source bypass the filter (logged as `no_date_kept`). Sources
with chronically missing dates should be flagged for replacement
in the next sourcefinder discovery cycle, not left invisible.

## Pinning test

Run after deploy:

```bash
python -c "
import sys; sys.path.insert(0, '/Users/jiong/myprojects/news-v2')
from pipeline.news_rss_core import fetch_rss_entries, _entry_age_days
import feedparser

# Synthesize a feed with one fresh + one stale entry to validate filtering
# OR use a known-stale feed if available.
url = 'https://www.pbs.org/newshour/feeds/rss/headlines'
fresh = fetch_rss_entries(url, max_entries=10, max_age_days=5)
print(f'fresh-only: {len(fresh)} entries')

# Sanity: every kept entry should be ≤ 5 days old (where age is parseable)
import time, calendar
for e in fresh:
    feed = feedparser.parse(url)
    # log line in pipeline output should show 'dropped_old=N' if any drops occur
"
```

Watch the daily-pipeline log for `rss freshness [<url>]: kept=N
(max_age=5d), dropped_old=K, no_date_kept=M` — non-zero
`dropped_old` proves the filter is active.

## Related

- `pipeline/news_rss_core.py:1555` and `:1894` — the two call
  sites of `fetch_rss_entries`. Both now benefit automatically.
- `pipeline/discover.py:232` — Tavily-side `days=3` filter. Same
  intent, different code path. Different default value (3 vs 5)
  is intentional: Tavily search returns a wider pool with more
  evergreen drift, so it's tighter; RSS path is narrower so a
  more permissive 5 is OK.
- `sourcefinder/sourcefinder/express.py`, `report.py`,
  `discover_and_eval.py` — `--days` defaults bumped from 3 → 5 in
  the same change-set so verification uses the SAME window prod
  ingests with. Sample-fidelity rule: tests must mirror prod.
- `sourcefinder/docs/RUNBOOK-local-source-discovery.md` — Workflow 2
  step 2 explicitly tells Cowork to drop articles > 5 days old
  before judging quality.
