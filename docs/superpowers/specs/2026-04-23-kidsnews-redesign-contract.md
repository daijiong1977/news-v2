# KidsNews redesign contract

**Date:** 2026-04-23
**Status:** Locked product direction for the redesign baseline
**Purpose:** Replace the conflicting assumptions spread across the older prototype docs and the current pipeline guide before implementation work starts.

## 1. Core decisions

- The redesign keeps three user-facing categories: `News`, `Science`, and `Fun`.
- `Fun` includes sports stories. Sports is not a separate publishing lane in the redesign.
- Each final story must ship in three outputs:
  - `easy English`
  - `middle English`
  - `Chinese`
- The current visual baseline still includes all four prototype surfaces:
  - home page
  - article detail page
  - archive/day picker
  - user panel/profile drawer
- No page is currently treated as missing or needing re-download.
- Publishable outcomes are `SAFE` and `CAUTION`. Only rejected stories are blocked.

## 2. Daily content contract

The new pipeline runs per category, not as one shared daily pool.

For each of `News`, `Science`, and `Fun`:

1. Discover `10` candidates.
2. The candidate mix is:
   - `6` from the new discovery pipeline
   - `4` from RSS / curated feed intake
3. Vet and rank all `10` candidates.
4. Send the top `5` ranked candidates into full detail generation first.
5. Stop the category run as soon as `3` publishable stories exist.
6. If the first `5` detailed candidates do not produce `3` publishable stories, continue through the remaining vetted candidates in order.
7. If all `10` vetted candidates are exhausted and the category still has fewer than `3` publishable stories, repeat discovery for that category until the quota is filled.

This makes the daily publishing target:

- `3` final stories per category
- `9` final stories per day across all categories
- `27` output payloads per day if each story produces easy, middle, and Chinese variants

## 3. Safety and publishing contract

The content policy remains authoritative in:

- `docs/superpowers/specs/2026-04-20-kidsnews-content-policy.md`

Operational rule for the redesign:

- `SAFE` publishes.
- `CAUTION` publishes after the required rewrite / softening pass.
- `REJECT` does not publish.

This means manual draft review is not the default path for `CAUTION`. The system should transform and publish unless a future spec adds an explicit review gate.

## 4. Schema rollout contract

The redesign does **not** cut over the old Supabase schema immediately.

The rollout model is:

- keep the old schema and old project running as-is
- create a parallel redesign table set first
- have the new pipeline write only into the redesign tables during validation
- compare old and new outputs while both systems run in parallel
- cut reads and writes over only after the redesign tables and pipeline are proven stable

The first redesign table family is:

- `redesign_runs`
- `redesign_candidates`
- `redesign_stories`
- `redesign_story_variants`
- `redesign_story_sources`

This table family is intentionally separate from the current `articles` and related child tables.

For the redesign baseline:

- the old schema remains the live production path
- the new schema is the validation path
- no destructive migration against the old schema is part of the baseline
- cutover happens later as an explicit migration step, not as part of initial redesign implementation

The parallel-schema baseline SQL lives in:

- `supabase/migrations/20260423_redesign_parallel_schema.sql`

## 5. UI contract

The redesign UI work should preserve the current prototype structure while aligning it to the new content model.

### Keep

- The current home page composition and daily reading framing
- The current article learning flow
- The archive/day browsing model
- The user drawer/settings model

### Align

- The category model must read as `News / Science / Fun` everywhere
- Internal mock data should stop presenting sports as a separate top-level lane
- Placeholder controls can stay placeholder during baseline import, but they are not evidence of broken screens

## 6. Mapping to current naming

The redesign currently uses `Sprout` and `Tree` in the UI.

For pipeline and payload planning, the baseline mapping is:

- `Sprout` -> `easy English`
- `Tree` -> `middle English`
- `Chinese` remains its own localized output

If the UI keeps `Sprout` and `Tree`, the backend and docs should still map cleanly to easy/middle outputs.

## 7. Required deltas against current docs

### `PIPELINE-IMPLEMENTATION.md`

Replace these assumptions:

- hard-coded secrets in the environment section
- category examples such as `sports` and `entertainment` as separate top-level lanes
- six-article cost/test framing
- single-pass story selection assumptions
- incomplete output contract for easy/middle/Chinese
- outdated publish logic that does not match `SAFE and CAUTION both publish`

Update this guide to model:

- per-category `6 + 4 -> 10 -> 5 -> 3` funnel
- `News / Science / Fun` category surface
- sports folded into `Fun`
- three outputs per final story
- parallel redesign tables as the first write target
- repeat-discovery behavior after a category exhausts all `10` candidates without producing `3` publishable stories

### `docs/superpowers/specs/2026-04-21-kidsnews-agent-design.md`

Keep it as a historical prototype reference, but do not treat it as the redesign target.

Its outdated assumptions are:

- `4` web + `2` PBS
- one `News` lane only
- middle English only
- English only
- six final HTML articles as the success target

### `docs/superpowers/specs/2026-04-20-kidsnews-claude-agent-prototype-design.md`

Keep the reusable ideas:

- content policy artifact
- selection workflow concept

Do not keep these runtime assumptions as redesign truth:

- local-only news prototype as the target product shape
- news-only scope
- middle-only scope
- no Chinese output

### `newdesign/data.jsx`

Treat this as a follow-up alignment task.

Current prototype data still contains stale `Sports` labeling inside stories that now belong under `Fun`.

## 8. Immediate implementation implications

Before shipping redesign code, the baseline must support:

- a parallel table set in Supabase for side-by-side runs
- a per-category pipeline loop
- three final stories per category
- three output variants per story
- category and mock-data cleanup in the prototype UI
- secret removal from docs and helper scripts before any push

## 9. Superseded assumptions

The redesign should no longer assume any of the following as product truth:

- `4 web + 2 PBS`
- `6 total stories is enough`
- `News only`
- `middle only`
- `English only`
- `sports as a separate top-level category`
- `SAFE publish, CAUTION draft`

This file is the working contract for the new redesign baseline until a newer dated spec replaces it.