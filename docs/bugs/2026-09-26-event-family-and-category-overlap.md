# 2026-09-26 — Event-family duplicates and Fun/Science overlap

**Severity:** high
**Area:** pipeline
**Status:** fixed
**Keywords:** event-family, duplicate, spare-promotion, Trump-Xi, category-fit, Fun, Science, source-registry

## Symptom

The 2026-09-25 edition shipped three News cards about different stages or
angles of the same Trump–Xi White House visit. The same edition's three Fun
cards were a dinosaur discovery, an interstellar comet, and Jupiter facts —
all Science stories.

## Root cause

The curator had cluster and News-subject instructions, but event identity did
not survive every pipeline stage. After Stage 3 rejected two News rewrites,
`promote_spare_and_rewrite` checked reserve candidates only with a 70% lexical
headline-overlap predicate. Differently worded stages of one event therefore
returned through the spare path without a shared cluster id.

Separately, the live source registry classified `Live Science`, `NG Kids —
Space`, `MIT News`, and `Popular Mechanics` as Fun. The ranking stage measured
general kid appeal but had no hard per-article section-fit gate, so surprising
science routinely beat entertainment, sport, arts, and human-interest stories.

## Fix

Implemented in the commit carrying this bug-record trailer.

- `pipeline/mega_curator.py` — detect event families using headline actors,
  event language, title/summary context, and stable `_event_group` ids.
- `pipeline/jev_rank.py` — group duplicate event stages before the curator and
  hard-block candidates whose `category_fit` is below 0.60.
- `pipeline/full_round.py` — preserve event metadata through reserve promotion;
  reject same-event and wrong-category spares.
- `supabase/migrations/20260926_reclassify_fun_science_sources.sql` — move four
  science/technology sources out of Fun; the equivalent live DB update was
  applied and verified on 2026-09-26.

## Invariant

- One daily edition may publish at most one article from an event family,
  including after safety rejection, reserve promotion, or deep backfill.
- A candidate below the category-fit threshold may neither reach the curator
  nor re-enter through the reserve pool.
- Sources whose primary editorial identity is science must be registered under
  Science, even when their articles are entertaining.

## Pinning test

- `pipeline/test_story_dedup.py::test_event_family_dropped_even_when_titles_are_worded_differently`
- `pipeline/test_jev_rank.py::test_news_event_family_is_grouped_before_curator`
- `pipeline/test_jev_rank.py::test_wrong_section_story_is_hard_blocked_and_not_a_spare`
- Run: `.venv/bin/python -m pytest -q pipeline/test_story_dedup.py pipeline/test_jev_rank.py`

## Related

- [2026-07-08 — News subject cap](2026-07-08-news-subject-cap.md)
- [2026-07-11 — Same story shipped twice](2026-07-11-same-story-shipped-twice.md)
- [2026-04-28 — News source diversity](2026-04-28-news-source-diversity.md)
