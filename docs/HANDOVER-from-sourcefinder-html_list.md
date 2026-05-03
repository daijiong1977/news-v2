# Handover from sourcefinder → news-v2: support `html_list` feed kind

**From:** `~/myprojects/sourcefinder` (mining-only project)
**To:**   `~/myprojects/news-v2` (production pipeline that fetches & serves)
**Date:** 2026-05-03
**Driver:** sourcefinder is about to promote 4 sources, **3 of which are
`html_list` not RSS**. news-v2's current daily pipeline only knows RSS —
these will fail at fetch time if promoted as-is.

## TL;DR

1. Add `feed_kind` + `feed_config` columns to `redesign_source_configs`.
2. Port `sourcefinder/scraper.py` into news-v2 (or copy it inline).
3. At the daily pipeline's RSS-fetch step, dispatch by `feed_kind`.
4. **Do NOT modify `pipeline/cleaner.py`** — it stays as-is. Body
   extraction is already feed-kind-agnostic (it operates on whatever
   HTML is fetched).

## Why this is needed (context)

`sourcefinder` mines candidate publishers via 3 feed shapes:

- `rss` — XML RSS/Atom feed (the historical case news-v2 already handles)
- `sitemap` — `sitemap.xml` (sitemapindex → sub-sitemap → urlset)
- `html_list` — HTML listing page where article links are extracted via a
  CSS selector

Round-1 + round-2 brainstorms surfaced ~40% non-RSS sources. The 4 sources
ready to promote on 2026-05-03:

| id | name | feed_kind | URL |
|---|---|---|---|
| 15 | Smithsonian Smart News | `rss` | https://www.smithsonianmag.com/rss/smart-news/ |
| 24 | DOGOnews | `html_list` | https://www.dogonews.com/ |
| 25 | Live Science | `rss` | https://www.livescience.com/feeds/all |
| 35 | NG Kids — Space | `html_list` | https://kids.nationalgeographic.com/space/ |

Only #15 and #25 work in the current pipeline. #24 and #35 need this work.

Going forward sourcefinder will keep promoting more `html_list` sources —
some of the strongest candidates are explicitly built for kids and don't
publish RSS (NG Kids family, kid-magazine sites, etc.).

## What changes

### 1. Schema — add 2 columns to `redesign_source_configs`

```sql
ALTER TABLE redesign_source_configs
    ADD COLUMN feed_kind TEXT NOT NULL DEFAULT 'rss';

ALTER TABLE redesign_source_configs
    ADD COLUMN feed_config TEXT;  -- JSON; nullable for feed_kind='rss'
```

Existing rows default to `feed_kind='rss'` — backward-compatible.

The `redesign_source_candidates` table can stay as-is (passive; sourcefinder
uses local SQLite for in-flight candidates).

### 2. Code — port the scraper module

The canonical implementation lives at `~/myprojects/sourcefinder/sourcefinder/scraper.py`.
It's ~250 lines, pure-Python (urllib + bs4 + xml.etree). Recommended:
**copy it into news-v2 as `pipeline/scraper.py`** — duplicate code beats
cross-repo Python imports.

Key entry point:

```python
from pipeline.scraper import discover_article_urls

# `source` is a dict-like row from redesign_source_configs with at minimum:
#   rss_url, feed_kind, feed_config (JSON string or None)
items = discover_article_urls(source, top_n=5)
# Returns: [{"url": str, "title": str, "description": str, ...}, ...]
```

Behavior by `feed_kind`:

```
feed_kind='rss'        — uses rss_url as RSS/Atom feed URL
feed_kind='sitemap'    — uses rss_url as sitemap.xml URL
                         feed_config: {"subsitemap_filter": "...",
                                       "url_filter": "...",
                                       "max_items": 200}
feed_kind='html_list'  — uses rss_url as HTML listing page URL
                         feed_config: {"article_selector": "css selector",
                                       "exclude_pattern": "regex",
                                       "title_selector": "css selector"}
```

The scraper has built-in retry policy (3 UAs cycled, ~60s budget) for
publisher anti-bot resilience. Keep that — it's already saved us on Live
Science (transient WAF block).

### 3. Daily pipeline integration

Wherever news-v2's daily pipeline currently does:

```python
# Conceptual current path
for source in active_sources:
    items = fetch_rss(source.rss_url)        # ← only handles RSS
    for item in items[:N]:
        article_html = fetch(item.link)
        body = extract_article_from_html(item.link, article_html)  # cleaner.py
        ...
```

Change to:

```python
from pipeline.scraper import discover_article_urls

for source in active_sources:
    items = discover_article_urls(source, top_n=N)  # ← all 3 feed_kinds
    for item in items[:N]:
        article_html = fetch(item["url"])
        body = extract_article_from_html(item["url"], article_html)  # unchanged
        ...
```

`extract_article_from_html` (the production cleaner) is **untouched**. It
already operates on any HTML regardless of how the URL was discovered.

### 4. Reddit-specific outbound link follow

If news-v2 ever ingests Reddit RSS feeds (sourcefinder rejected them all but
some may still be in `redesign_source_configs` from earlier), the
description's `[link]` anchor needs to be followed before passing to the
cleaner. See `bin/daily_verify.py:extract_outbound_from_reddit_desc` in
sourcefinder for the helper. Optional — only relevant if you keep any
`reddit.com` sources active.

## Test cases (validate before promote)

After the migration + code change, validate with these 3 `html_list`
candidates that sourcefinder is about to promote. They should fetch
articles + extract bodies cleanly via the existing `extract_article_from_html`:

```sql
INSERT INTO redesign_source_configs
    (category, name, rss_url, feed_kind, feed_config, state)
VALUES
    ('Fun', 'DOGOnews',
     'https://www.dogonews.com/',
     'html_list',
     '{"article_selector": "article a[href*=\"/2026\"], article a[href*=\"/2025\"]", "exclude_pattern": "#comment"}',
     'live'),

    ('Fun', 'NG Kids — Space',
     'https://kids.nationalgeographic.com/space/',
     'html_list',
     '{"article_selector": "a[href*=\"/space/\"][href*=\"/article/\"]"}',
     'live'),

    ('Fun', 'NG Kids — Geography',
     'https://kids.nationalgeographic.com/geography/',
     'html_list',
     '{"article_selector": "a[href*=\"/geography/\"]", "exclude_pattern": "/games/|/videos/"}',
     'live');
```

Expected behavior at next pipeline run:

- DOGOnews: 3 articles, ~334 wc avg, all with og:image
- NG Kids — Space: 3 articles, ~247 wc avg, all with og:image (some shorter)
- NG Kids — Geography: 3 articles, ~682 wc avg, all with og:image

If any source returns 0 articles → the selector needs adjustment OR the
site changed. Sourcefinder's daily verify catches this and notifies.

## Image fallback (optional but recommended)

If `extract_article_from_html` returns `og_image=None`, news-v2 may want to
fall back to a body `<img>` tag — same logic sourcefinder uses for NASA
APOD-style pages. Reference implementation:
`~/myprojects/sourcefinder/bin/daily_verify.py::_fallback_body_image`.

About 30 lines, optional. Without it, sources whose pages don't have
`<meta og:image>` will surface without hero images in news-v2 output.

## What sourcefinder commits to do once news-v2 is ready

`bin/promote.py` in sourcefinder currently strips `feed_kind` and
`feed_config` before INSERT (left over from before this work). Once
news-v2 supports the new columns, ping sourcefinder and we update
`bin/promote.py:to_remote_payload()` to pass them through.

Until then: only RSS sources are promotable to production. Sourcefinder
will hold `html_list` candidates in `state='good'` (ready, but waiting
on news-v2).

## Coordination protocol

1. news-v2 maintainer applies migration + code change
2. news-v2 maintainer runs the 3 test INSERTs above on a staging branch
3. Verify next pipeline run picks up all 3 `html_list` sources successfully
4. Merge to production
5. Ping sourcefinder; we update `bin/promote.py` to send `feed_kind` +
   `feed_config` going forward
6. From that point on, sourcefinder can promote `html_list` sources directly
   via `python -m bin.promote --id N`

## Reference: full scraper.py contents

For convenience (since cross-repo imports are fragile), the canonical
scraper module is at:

  `/Users/jiong/myprojects/sourcefinder/sourcefinder/scraper.py`

~250 lines, dependencies: `bs4`, `lxml`, stdlib. Already in news-v2's
requirements (used by cleaner.py). Just copy the file.

If you'd rather not duplicate, you can `pip install -e
~/myprojects/sourcefinder` and import — but that creates a runtime
dependency that's annoying to track. **Recommend copy.**

## Out of scope

- **No changes to cleaner.py** — body extraction logic stays canonical.
- **No changes to image scoring or kid-safety logic** — that's all in
  sourcefinder, doesn't affect production.
- **No changes to news-v2's read path** — the daily pipeline change is
  isolated to the fetch/discover step.

## Questions / blockers

If anything's unclear about the scraper behavior or the schema migration,
the sourcefinder repo has empirical results from running this in
production for 3+ days against ~50 candidate sources — see
`~/myprojects/sourcefinder/docs/scheduled-tasks-howto.md` (the
context-exhaustion section especially) and
`~/myprojects/sourcefinder/out/daily-verify-2026-05-*.json` for real
sample data showing what each `feed_kind` produces.
