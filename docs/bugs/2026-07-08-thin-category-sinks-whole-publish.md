# 2026-07-08 — thin category sinks whole publish; backfill pool too shallow

**Severity:** high
**Area:** pipeline (Stage-3 backfill + pack gating)
**Status:** fixed
**Keywords:** backfill, spare pool, probe briefs, degraded publish, merge mode, SystemExit, deploy_failed, one-category failure

## Symptom

2026-07-08 06:06 run: News survived Stage 3 with only 1 story → pack
validation SystemExit → **nothing** published (Science/Fun were perfectly
fine) → run marked deploy_failed → full re-run needed (double LLM cost).
Owner: "有一些文章没有,就导致整个 reject,我觉得这不好。4 个源,
不管怎么样也找得到 3 篇合格的文章…不应该 crash 整个 pipeline 重新跑。"

## Root cause (two stacked problems)

1. **Backfill pool too shallow.** Probe keeps 10 briefs/cat, but the
   curator ranks only 5, and Stage-3 spare promotion could only draw from
   the curator's leftover ranks (usually 1 spare). The other ~5 probed
   briefs — bodies already fetched — were silently discarded. After
   verify/safety attrition there was often nothing left to promote.
2. **All-or-nothing pack.** `validate_bundle` (≥2/cat) aborted the WHOLE
   upload on one thin category, discarding the other categories' fresh
   content and blocking any publish.

## Fix

PR: fix/deep-backfill-degraded-publish.

1. **Deep backfill** — `_unpicked_probe_spares` (full_round.py): every
   probed-but-unranked brief becomes an unverified Stage-3 spare
   (source-interleaved, cached `_probe_art` reused). Promotion still runs
   body/image verify + the full safety vet per spare — deeper pool, same
   gates.
2. **Per-category degraded publish** — `_split_publishable` + pack merge
   mode (reuses PR #40 machinery): fresh categories publish; a still-thin
   category keeps its current live content from latest.zip; loud warning
   in telemetry/digest. Only all-categories-thin refuses to publish.
   Degraded publishes don't stamp thin cats' sources as shipped.

## Invariant

- A single category's failure must never block publishing the others,
  and must never require a full re-run.
- Deepening the backfill pool must not bypass verify/safety gates.

## Pinning test

`python -m pipeline.test_backfill_degrade` —
`test_unpicked_probe_spares_excludes_ranked_and_interleaves`,
`test_split_publishable_mixed`.

## Related

- `docs/bugs/2026-07-08-probe-cap-starves-low-priority-sources.md` — the
  probe interleave these spares inherit.
- PR #40 partial-category run — the merge machinery reused here.

## Follow-up (same day) — pack-time carry-over top-up

Owner refinement: a category should ALWAYS ship 3 — after cross-source
backfill, borrow from the previous live bundle. `_topup_thin_categories`
(pack_and_upload.py) appends previous-bundle stories (listings + payloads
+ images + PDFs, id-deduped) to any 1-2-story category until 3; a 0-story
category still keeps old content wholesale; only all-0 refuses to publish.
main_mega threshold moved to min_per_cat=1. Pure file ops, no LLM, gates
unchanged. Tests: pipeline/test_pack_topup.py.
