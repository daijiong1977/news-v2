# 2026-04-29 — search-click-wrong-article

**Severity:** high
**Area:** website
**Status:** fixed
**Keywords:** search, archive, ARTICLES.find, listing-overwrite, synthetic-merge, redesign_search_index

## Symptom

User clicked any result on the new search page and the wrong article opened
— always the FIRST article on that day's bundle, regardless of which
result the user picked. Reproducible against `news.6ray.com`. URL DID
flip to `/archive/<correct-date>` so the day-load was happening; only
the article identity was wrong.

## Root cause

The `redesign_search_index` table can hold rows whose `story_id` is no
longer in the day's listing JSON. This happens when the daily pipeline
runs TWICE on the same date — each run overwrites
`<date>/payloads/articles_<cat>_<lvl>.json` with the latest top-3,
while `<date>/article_payloads/payload_<sid>/...` keeps growing
(orphan stories survive on storage). So the search-index row points
at a real on-storage payload but a story_id the listing no longer
declares.

`website/article.jsx:62` does:

```js
const baseArticle = ARTICLES.find(a => a.id === articleId) || ARTICLES[0];
```

When the click handler awaited `loadArchive(published_date)` and then
routed to `<story_id>-<level>`, `ARTICLES.find` missed (story_id not
in listing) and silently fell back to `ARTICLES[0]` — i.e. the first
article of that day's bundle. The detail-fetch then loaded THAT
article's payload, not the one the user clicked.

## Fix

Commit: `abb13bb` — pushed to `main` 2026-04-29.

Synthesize a listing entry from the search row before routing, and
inject it into the per-day bundle so `ARTICLES.find` succeeds.

- `website/data.jsx:170-208` — new `_archiveExtras` map +
  `_mergeExtras()` that unions synthetic entries into the cached and
  freshly-fetched bundles. `synthesizeArticleFromSearchRow(r)`
  reuses `listingToArticle()` to keep the synthetic shape identical
  to a real listing entry.
- `website/data.jsx:248-261` — `stashSearchExtra(r)` exposed on
  `window`. Called BEFORE `loadArchive` so the merge applies to both
  the awaited fetch and the secondary `archiveDay` useEffect re-fetch.
- `website/index.html:524-552` — `onOpenSearchResult(r)` does
  `stashSearchExtra → await loadArchive → setArchiveDay → setRoute`,
  with a zh→English-twin redirect for `noDetail` Chinese hits (same
  pattern as the streak-popover `onOpen()` at index.html:505-515).
- `website/home.jsx:1614-1622` — `searchResultImageUrl()` always
  routes through `<ARCHIVE_BASE>/<published_date>/...`. Search rows
  are only indexed AFTER pack_and_upload mirrors images to storage,
  so this is reachable for every indexed row.

## Invariant

When a search row is opened, the article eventually rendered MUST
match the row's `story_id` and `level`. ArticlePage's
`ARTICLES.find` MUST NOT fall back to `ARTICLES[0]` for a search
result's id — if the id can't be found after `loadArchive`, the
caller's responsibility is to pre-stash a synthetic so the find
succeeds. Any change to the article-resolution flow must preserve
this. If the synthetic merge logic is removed, the orphan-storyId
class of bugs returns immediately.

A second invariant: the `archiveDay` useEffect's re-fetch of
`loadArchive` MUST honor `_archiveExtras`. If a future refactor
clears the cache or skips `_mergeExtras` on the cache-hit path, the
synthetic gets dropped between the click handler's await and the
useEffect's load.

## Pinning test

MANUAL smoke (90s):
1. Visit `https://news.6ray.com/`
2. Click 🔍 in the header → search page opens
3. Type a word that appears in a NON-today article (e.g. "mines")
4. Click any non-top result
5. Verify the article that opens has the title shown in the result
   card, NOT the date's first article.

Automated: `/tmp/smoke-search2.js` (kept locally, browser-driven via
chrome-devtools-mcp). Update its hardcoded query and expected title
when content rotates out.

Future improvement: cron job to invalidate
`redesign_search_index` rows whose `story_id` is no longer in the
day's listing — would let us drop the synthetic-merge fallback. See
followups in the search redesign cross-check.

## Related

- `docs/superpowers/specs/` — no formal spec for search; design
  lived in commit messages and `/tmp/search-design.md` (the brief
  sent to Copilot for cross-check).
- Adjacent: archive-click-race fix (`2026-04-28-archive-click-race.md`)
  — same class of "ARTICLES not loaded yet when route changes".
