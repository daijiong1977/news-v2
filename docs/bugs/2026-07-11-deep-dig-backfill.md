# 2026-07-11 — short category should dig deeper into today's feeds

**Severity:** medium
**Area:** pipeline (Stage-3 backfill)
**Status:** fixed
**Keywords:** deep-dig, backfill, phase_a_light, max_per_source, fetch_source_entries, carry-over, source diversity, thin category

## Symptom / owner ask

When a category ends short (1-2 stories after dedup/safety/image), the
pipeline jumped straight to borrowing yesterday's content. Owner: dig
DEEPER into the same day's other sources first — "另外两个源可以再往
深度挖一下，看看有没有合适的文章再补进去".

## Root cause

`phase_a_light` only fetched `max_per_source=4` briefs/source, though
each feed carries up to 25 items (`MAX_RSS_DEFAULT`). So the entire
funnel only ever saw the top ~4 stories per source; the backfill spares
were just the leftovers of those same 4×sources. Items 5..25 of each
feed were never fetched.

## Fix

PR: feat/deep-dig-backfill.

`_deep_dig_spares` (full_round.py): reactive — only when a category is
short after promoting the shallow probe spares. Fetches deeper feed items
(items 5..15/source via `fetch_source_entries(max_entries=15)`), drops
already-considered links, interleaves across sources, and wraps each as
an unverified Stage-3 spare. Promotion runs the SAME gates (body/image
verify + safety vet + title-dedup vs shipped). Wired into `_safety_runner`
between the shallow-spare drain and the pack-time carry-over.

Fill priority is now: shallow probe spares → **deep-dig today's feeds** →
yesterday's carry-over (#42) → keep-old/degrade. Fresh same-day content
is always preferred over yesterday's; carry-over is the safety net.

## Invariant

- Deep-dig is reactive (cost only when short) and never lowers a gate —
  it only widens the candidate net with fresh same-day stories.

## Pinning test

`python -m pipeline.test_deep_dig` — `test_excludes_seen_links_and_interleaves`,
`test_dedups_same_link_across_sources`, `test_fetch_failure_is_non_fatal`.

## Related

- `docs/bugs/2026-07-08-thin-category-sinks-whole-publish.md` — the deep
  backfill + carry-over this slots in front of.
- Durable fix for chronic thin supply: more News sources (sourcefinder).
