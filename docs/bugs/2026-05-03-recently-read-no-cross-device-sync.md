# 2026-05-03 — recently-read-no-cross-device-sync

**Severity:** medium (UX regression for multi-device kids)
**Area:** website + edge-fn (RPC)
**Status:** fixed
**Keywords:** recent_reads, RecentReadsPopover, fetchHistory, redesign_reading_events, articleProgress, snapshot, cross-device, kidsync

## Symptom

Same kid account, two devices (home computer + school computer). Reads
4 articles on Device A. Opens the site on Device B (same email signed
in via magic link). Clicks the "Recently read" / streak popover.

**Bug:** popover shows 0 entries, OR shows fewer than the kid actually
read. The "You haven't read anything yet today" empty state appears
even though the cloud has the events.

User's exact words (chat 2026-05-03):

> 同一个账号，在不同的这个一个是我家里的电脑，一个是学校电脑上面，
> 就是 recent read 没有同步过去

(Same account, different devices — home and school computers — recent
reads didn't sync across.)

Earlier the same day the user also reported: "Recently read is always
zero even I completed 4 yesterday." That was the same root cause
showing up after the user came back on a fresh-cache device.

Reproduction:
1. Device A: complete 4 articles. Verify popover shows 4 entries.
2. Sign out / clear localStorage / move to Device B.
3. Sign in on Device B via the same magic-link email.
4. cloud bootstrap fires, `fetchHistory()` returns the events.
5. Open the popover → 0 entries (or only entries that are coincidentally
   still in today's `ARTICLES` listing on this device).

## Root cause

`RecentReadsPopover` (`website/home.jsx:1989-2050`) renders an entry
in two ways:

1. `ARTICLES.find(x => x.id === id)` — finds the article in the
   currently-loaded bundle (today's, or the active archive day's).
2. Fallback to `articleProgress[id]` snapshot (the dict of cached
   per-article metadata: title, category, imageURL, archiveDate, etc.).

For cross-device reads:
- (1) misses because Device B's `ARTICLES` is today's bundle, while
  the read happened on a past day. The id like `2026-05-02-fun-2-middle`
  isn't in today's listing.
- (2) misses because the cloud merge path in `index.html:442-451`
  built `articleProgress[id]` entries with ONLY `steps` /
  `lastTab` / `lastTouchedAt` — no `title`, no `category`, no
  `imageURL`. The popover's check `if (snap && typeof snap === 'object' && snap.title)`
  silently dropped every cloud-rebuilt entry because `snap.title`
  was empty.

Trace:
- `redesign_reading_events` table had no `title` or `image_url`
  columns (`information_schema.columns` showed: id, client_id,
  story_id, category, level, language, step, minutes_added,
  duration_ms, occurred_at, day_key — that's it).
- `record_reading_event` RPC accepted only category + level +
  language + minutes — no title.
- `get_reading_history` RPC returned the same 6 fields. The client
  had no source of truth for the title field of a past-day article.

So the popover's snapshot fallback worked great on the SAME device
(article.jsx's bumpStep wrote `articleProgress[id].title = article.title`
locally), but the cloud round-trip lost it.

This was a "field names lie" pattern: the events table had `category`
+ `level` (snapshot-ish fields) but not `title` + `image_url`,
making it look like enough of the snapshot was preserved when actually
the gating field for the renderer was missing.

## Fix

Migration `supabase/migrations/20260504_reading_events_title.sql`:
- ALTER TABLE redesign_reading_events ADD COLUMN title TEXT, image_url TEXT
- DROP + CREATE both RPCs (return-type / signature changes can't use
  CREATE OR REPLACE):
  - `record_reading_event` accepts new `p_title` + `p_image_url`
    params (default NULL — backwards compat for any client still on
    the old shape)
  - `get_reading_history` returns title + image_url alongside the
    existing fields

Frontend:
- `website/kidsync.js:128-145` — `recordReadingEvent(storyId, step, opts)`
  now passes `opts.title` and `opts.imageURL` into the RPC.
- `website/article.jsx:213-235` — bumpStep packages title + imageURL
  into the event metadata, used by both the per-step write AND the
  `'finish'` event.
- `website/index.html:442-505` — cloud merge populates `fromCloud[id]`
  with title / category / level / imageURL / archiveDate from the event
  row. The merge with local `articleProgress[id]` prefers local for
  the snapshot fields when both are present, but falls back to cloud
  when local is absent or empty (the cross-device scenario).

The `lvlSuffix` heuristic stays — events store level=`'Tree'`/`'Sprout'`
and the frontend appends `-easy`/`-middle` to match the listing id.
There's a known mismatch case (kid switches level between read +
return) but that's pre-existing and beyond the scope of this fix.

## Invariant

**Every reading event written to the cloud MUST carry enough metadata
for the popover to render the entry without consulting any other
source.** Specifically: `title`, `category`, `level`, `image_url`
(nullable but populated in the happy path) — the article.jsx writer
must include them, the RPC must store them, and the cloud-merge in
index.html must propagate them into `articleProgress[id]`.

Future edits that add new event types or new clients MUST continue
to populate these snapshot fields. If a new event source can't (e.g.,
a server-side write triggered by a different system), the renderer
must NOT rely on the new event being renderable on its own — gate
the rendering on `snap.title` truthiness like today.

## Pinning test

MANUAL (no SPA login automation in this repo):

1. Sign in on Browser A. Read 1 article fully (all 4 stages). Verify
   popover shows 1 entry with title + category + image.
2. In Browser A devtools: `localStorage.clear()`, reload. Verify the
   popover still shows the entry (cloud bootstrap reconstructs it).
3. Sign in on Browser B (different browser / incognito) via the same
   magic-link email. Wait for cloud bootstrap to complete (no spinner).
4. Open the popover. Verify the entry from step 1 is visible with
   title + category + image.
5. Check that the rendered entry's title matches what was on Device A.

A regression appears as: step 4 shows "You haven't read anything yet
today" even though `redesign_reading_events` has rows.

DB sanity-check (run any time):

```sql
SELECT story_id, title, image_url, occurred_at
FROM redesign_reading_events
WHERE client_id = '<kid-uuid>'
  AND step IN ('discuss', 'finish')
ORDER BY occurred_at DESC
LIMIT 5;
```

Expected: the title column is non-NULL on rows written by clients
that have the post-2026-05-04 frontend. Older rows written before
this fix are kept (NULL title) and the popover gracefully drops
them — they re-appear if the kid re-reads the article.

## Related

- Universal-patterns: "Field names lie" — the events table had
  category + level (snapshot-ish), making it look like enough of
  the snapshot was preserved. The gating field for the renderer
  (title) was missing.
- `2026-05-03-magic-link-onboarding-flash.md` — the sibling
  cross-device sign-in flow bug shipped in the same PR.
- `website/home.jsx:1989-2050` — RecentReadsPopover render path
  (unchanged by this fix; relies on snap.title being populated).
- `2026-04-26-kid-identity.sql` — the original magic-link / kid
  profile RPC migration that created the events table.
