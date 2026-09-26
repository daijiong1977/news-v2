# 2026-09-26 — Deep-dig section fit and final safety audit

**Severity:** medium
**Area:** pipeline
**Status:** fixed
**Keywords:** deep-dig, category-fit, Fun, Science, safety, redesign_stories, independent-vet

## Symptom

Review of the 2026-09-26 full mega run found two unguarded paths. A short
category's deep-dig RSS items had no Jev section-fit score, so a science item
from a mixed Fun feed could be promoted. All nine published story rows had
`safety_total` and `safety_verdict` null despite Stage 3 having scored the
rewritten articles.

## Root cause

`_deep_dig_spares` creates briefs after the first-round Jev rank stage. The
spare promotion gate defaulted missing `_jev_category_fit` to 1.0, which is
appropriate for older legacy spares but silently allowed unscored deep-dig
items. Separately, `persist_to_supabase` read `_vet_info` from the original
source article; mega Stage 3 stores its independent safety scores and final
decision on the rewritten variant, not the source article.

## Fix

- `pipeline/jev_rank.py` — score deep-dig briefs with the existing Jev section
  question and threshold. Unscored backfill is skipped; the established
  previous-day carry-over remains available.
- `pipeline/full_round.py` — gate deep-dig spares before promotion and persist
  final rewritten-body safety scores and verdict when present. Legacy runs
  continue using their original vet fields.

## Invariant

- No newly fetched deep-dig brief may be promoted without a passing section-fit
  score. A Jev outage may reduce fresh backfill, but must not relabel Science
  as Fun.
- A published `redesign_stories` safety row describes the final child-facing
  rewrite and Stage-3 decision when those results exist.

## Pinning test

`python -m pytest -q pipeline/test_deep_dig.py pipeline/test_jev_rank.py pipeline/test_persist_safety.py`

## Related

- `docs/bugs/2026-09-26-event-family-and-category-overlap.md`
- `docs/bugs/2026-07-11-deep-dig-backfill.md`
- `docs/bugs/2026-07-08-safety-quality.md`
