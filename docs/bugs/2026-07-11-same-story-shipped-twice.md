# 2026-07-11 — same story shipped twice (NYT Air Force One subpoena, PBS + NPR)

**Severity:** high
**Area:** pipeline (mega curator dedup)
**Status:** fixed
**Keywords:** cluster_id, duplicate story, dedup, _dedupe_ranked_stories, titles_same_story, spare promotion, subject cap, source diversity

## Symptom

Live News (2026-07-11) shipped two cards about the SAME event — NYT
reporters subpoenaed over Air Force One reporting — slot 2 from PBS,
slot 3 from NPR. Owner: "还是重复，和源不够".

## Root cause

Checkpoint (stage2_picks, News) shows the curator did its tagging job:

| rank | src | subject | cluster_id |
|---|---|---|---|
| 2 | PBS | New York Times | `nyt_subpoena_af1` |
| 4 | NPR | New York Times | `nyt_subpoena_af1` |

Both picks share cluster_id AND subject — but both shipped:
1. **cluster_id was never enforced deterministically.** The prompt says
   "at most one per cluster" (soft); nothing dropped the second.
2. **The #43 subject-cap only guards the top 3.** The dup sat at rank 4;
   rank 3 (FIFA) was dropped downstream and rank 4 was promoted into the
   shipped 3 → two NYT stories.

Enabler: only 4 News sources, so on a big-story day multiple sources
carry the same wire story ("源不够").

## Fix

PR: fix/same-story-dedup.

1. `_dedupe_ranked_stories` (mega_curator.py) — deterministic, runs
   before the diversity passes over the WHOLE ranked list: drops a pick
   whose cluster_id repeats, whose title is near-identical
   (`titles_same_story`, overlap-coefficient ≥0.7), or (News) whose
   non-empty subject repeats. Survivors re-ranked 1..N. Freed slots
   refill from deep backfill / carry-over (#41/#42) with different
   stories.
2. `titles_same_story` — shared title-overlap predicate.
3. Stage-3 promotion guard — `promote_spare_and_rewrite` takes
   `used_titles` and skips a probe-pool spare (no cluster_id) whose title
   matches an already-shipping pick, so promotion can't reintroduce the
   removed dup from a third source.

## Invariant

- No two shipped stories in a category describe the same event
  (cluster_id / near-title). News additionally ships ≤1 per subject.
- Dedup runs before diversity/promotion and the promotion path re-checks
  titles — a duplicate can't slip back in via spare promotion.

## Pinning test

`python -m pipeline.test_story_dedup` — esp.
`test_same_cluster_id_dropped_and_reranked` (replays the 07-11 picks),
`test_near_duplicate_title_dropped_even_with_diff_cluster`.

## Related

- `docs/bugs/2026-07-08-news-subject-cap.md` — the subject tag this reuses.
- Durable fix for "源不够": more kid-oriented News sources (sourcefinder).
