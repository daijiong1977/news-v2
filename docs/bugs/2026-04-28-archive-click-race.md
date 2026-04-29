# 2026-04-28 — archive-click-race

**Severity:** high
**Area:** website
**Status:** fixed
**Keywords:** useEffect, race, archiveDay, ARTICLES, async, archive, click

## Symptom

User clicked a date in the archive picker; the URL changed to
`/archive/<picked-date>` but the article tiles rendered were still
TODAY's articles, not the picked day's. Clicking any tile opened a
preview-style stub.

## Root cause

`onOpenArchive` (in `website/index.html`) used to be:

```js
onOpenArchive={(d) => {
  setArchiveDay(d);
  setCat('All');
  window.scrollTo({top:0});
}}
```

`setArchiveDay(d)` triggered a re-render BEFORE the `archiveDay`
useEffect fired its async `loadArchive(d)` call. The re-render saw
the stale `window.ARTICLES` (today's bundle), so the listing
`useMemo` produced today's tiles. Subsequent clicks routed against
today's ARTICLES too — the article reader opened the wrong story.

The async useEffect did eventually swap ARTICLES, but only AFTER the
user had already clicked an outdated tile.

## Fix

`website/index.html:525-540` — pre-load ARTICLES INSIDE the click
handler (await `window.loadArchive(d)` BEFORE `setArchiveDay`):

```js
onOpenArchive={async (d) => {
  try {
    if (typeof window.loadArchive === 'function') {
      await window.loadArchive(d || null);
    }
  } catch (e) { /* fall through; useEffect will retry */ }
  setArchiveDay(d);
  setCat('All');
  window.scrollTo({ top: 0 });
}}
```

Same pattern applied to `onResume` (resume-from-history) at
`website/index.html:541-557` and to `onOpenSearchResult` at
`:524-552` for the same reason.

## Invariant

`window.ARTICLES` MUST contain the listing for `archiveDay` BEFORE
React re-renders the listing. Any handler that flips `archiveDay`
MUST `await window.loadArchive(date)` before calling
`setArchiveDay`. The `archiveDay` useEffect's own loadArchive call
is a SAFETY-NET, not a primary loader — relying on it for the first
render is the bug.

## Pinning test

MANUAL (60s):
1. Open `https://news.6ray.com/`
2. Click the calendar pill in the header → pick yesterday
3. Verify tile titles change to yesterday's stories within ~500ms
4. Click any tile → verify article matches the tile's title.

## Related

- `2026-04-29-search-click-wrong-article.md` — same class
  ("ARTICLES not loaded yet when route changes"), different trigger
  (search) and an additional layer (orphan story_ids).
- `2026-04-28-archive-slow-load.md` — the parallelize+cache fix
  reduced the await window from ~5s to ~0.5s, making the race fix's
  user-visible cost negligible.
