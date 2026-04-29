# 2026-04-28 — archive-slow-load

**Severity:** medium
**Area:** website
**Status:** fixed
**Keywords:** sequential-fetch, parallelize, Promise.all, cache, loadPayloads, archive

## Symptom

Switching to an archive date took ~5 seconds before the listing
rendered. The user could see a blank list / spinner during that
window, which made the rapid-archive-switch UX feel broken.

## Root cause

`loadPayloads(archiveDate)` in `website/data.jsx` used to fetch the
9 payloads (3 categories × 3 levels) sequentially:

```js
for (const cat of cats) {
  for (const lvl of levels) {
    const r = await fetch(`${base}/articles_${cat}_${lvl}.json`);
    // ...
  }
}
```

Each Supabase Storage round-trip is ~500ms; 9 × ~500ms ≈ 5s. Worse,
re-visiting the same archive day re-fetched everything because there
was no cache.

## Fix

- `website/data.jsx:171-209` — switch to `Promise.all` + per-day
  cache (`_archiveCache: Map`). All 9 fetches now run in parallel
  (~one round-trip's worth, ~500ms cold) and cached lookups return
  synchronously for the rest of the session.

## Invariant

`loadPayloads` MUST kick off all category × level fetches in
parallel and return after the slowest, not the sum. The cache MUST
be keyed by archiveDate (with `__today__` as the null sentinel).
Future additions to the listing matrix (more cats / levels) MUST
preserve this — never await inside the inner loop.

If `_archiveExtras` is consulted (search-result synthetic merge), it
MUST be re-merged on cache hits too — the cache stores the bare
list, the merge layer wraps the return.

## Pinning test

MANUAL (15s):
1. Open the site, open DevTools → Network → throttle "Fast 3G".
2. Click a date in the archive picker.
3. Total time-to-listing-rendered should be < 1s on the cold load,
   < 100ms on the second visit (cached).

## Related

- `2026-04-28-archive-click-race.md` — the await pattern there only
  feels good because this fix made `loadArchive` ~500ms instead of
  ~5s. If a future change makes loadArchive slow again, the race
  fix's await turns into a 5s click freeze.
