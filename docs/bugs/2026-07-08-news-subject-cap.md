# 2026-07-08 — cap one subject per News top 3 (3 Trump stories shipped)

**Severity:** medium
**Area:** pipeline (mega curator diversity)
**Status:** fixed
**Keywords:** subject, cluster_id, topic diversity, curator, _enforce_top3_subject_diversity, News, entity cap

## Symptom

Owner: yesterday all 3 News stories were Trump-related. The curator's
within-cat "prefer different clusters" is soft, and cluster_id groups by
*story* (a summit, an election ruling, a tariff = 3 clusters) not by
*person*, so three Trump stories passed as "diverse".

## Fix

PR: feat/news-subject-cap.

1. Curator now tags each pick with a `subject` = the dominant named
   person/org ("" if none) — coarser than cluster_id. Prompt gains a
   HARD RULE: a non-empty subject may appear only ONCE in the News top 3
   ("don't ship three Trump stories"), fill the rest with different
   subjects.
2. `_enforce_top3_subject_diversity` (mega_curator.py) — deterministic
   backstop mirroring `_enforce_top3_source_diversity`, scoped to News:
   swaps a repeated-subject pick out of the top 3 for a rank-4/5 spare
   with a different subject, preferring one that also keeps 3 distinct
   sources; falls back to any different-subject spare (subject cap wins
   over source diversity on conflict). Empty subject never collides.
   Degrades cleanly + warns when the pool truly has no other subject;
   deep backfill / carry-over (#41/#42) then fill from other sources.

## Invariant

- News ships at most one story per non-empty subject in its top 3.
  Scope is News-only by owner choice; extend cap_categories to widen.

## Pinning test

`python -m pipeline.test_subject_cap` — esp.
`test_caps_repeated_subject_and_fills_from_spares`,
`test_empty_subject_never_counts_as_duplicate`.

## Related

- `pipeline/mega_curator.py::_enforce_top3_source_diversity` — the
  source-diversity backstop this mirrors and runs after.
