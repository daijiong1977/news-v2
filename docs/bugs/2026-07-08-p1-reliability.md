# 2026-07-08 — p1-reliability

**Severity:** high
**Area:** pipeline (recovery + persistence + rotation)
**Status:** fixed
**Keywords:** RESUME_FROM, checkpoints, jsonb, int-keys, quiz, correct_answer, fuzzy-match, insert_run, retry, orphan-slots, same-day-rerun, stamp_shipped_sources, deploy_failed

## Symptom

Five reliability defects from the 2026-07-07 code sweep (P1 tier), each
verified in code:

1. **RESUME_FROM=enrich/persist could never succeed** — `final_variants[cat] =
   {i: art}` (int keys) is checkpointed to JSONB, which stringifies keys;
   `_walk_from_jsonable` never coerced them back, so
   `final_variants_by_cat[cat][i]` raised KeyError on resume — the exact
   recovery path used after a `deploy_failed`.
2. **Unanswerable quizzes could ship** — when the LLM's `correct_answer`
   didn't match an option verbatim, quiz_shuffle logged and left the question
   as-is; the frontend (`article.jsx` `Math.max(0, idx)`) silently mapped it
   to option A.
3. **One startup blip disabled a whole day's persistence** — `insert_run` had
   no retry; on failure `run_id=None`, every persist is gated `if run_id:`,
   yet the site still deployed → zero `redesign_stories` rows, blind digest.
4. **Same-day re-runs left orphan slot rows** — `insert_story` upserts on
   (published_date, category, story_slot); a re-run shipping 2/3 overwrote
   slots 1–2 but left the prior attempt's slot-3 live under today's date.
5. **Sources were rotation-stamped before deploy success** — persist stamped
   `last_used_at`/`next_pickup_at`, so on `deploy_failed` a fresh re-run saw
   today's sources as ineligible and mined a different, weaker bundle.

## Root cause

Individually small omissions sharing one theme: the failure/recovery paths
were never exercised, so their bugs survived — resume was broken precisely at
the stages you'd resume into, and "run row insert fails" / "second run same
day" / "deploy fails after persist" are all rare-day paths.

## Fix

PR: fix/p1-reliability.

- `pipeline/checkpoints.py::_walk_from_jsonable` — pure-digit dict keys are
  coerced back to int on load (slot keys like `"0_easy"` unaffected).
- `pipeline/quiz_shuffle.py` — near-miss `correct_answer` (casefold /
  whitespace / trailing period) is rewritten to the option's exact text on a
  unique fuzzy match; otherwise the question is **dropped**. Behavior change
  from "leave untouched" (2026-07-07); test updated accordingly.
- `pipeline/supabase_io.py::insert_run` — 3 attempts with backoff + loud
  give-up log.
- `pipeline/full_round.py::persist_to_supabase` — after upserting each
  category, deletes today's rows with `story_slot > len(stories)`.
- `pipeline/full_round.py::stamp_shipped_sources` — extracted from
  persist_to_supabase; called in BOTH terminal blocks (legacy + mega) only
  under `upload_ok`, so rotation only advances for deployed bundles.

## Invariant

1. Checkpoint save→load must round-trip dict key types for every stage
   payload; consumers may index with int.
2. A quiz question whose `correct_answer` cannot be resolved to an option
   must not reach a payload.
3. `redesign_stories` for (today, category) must contain exactly the slots
   the latest attempt shipped — nothing above `len(stories)`.
4. Source rotation stamps (`last_used_at`/`next_pickup_at` cadence stamp)
   happen only after `upload_ok` — an undeployed bundle doesn't consume a
   source's cadence slot. (Probe stamping for unshipped sources is separate
   and pre-deploy by design.)

## Pinning test

`python -m pipeline.test_p1_reliability` (5 tests: checkpoint round-trip,
quiz fuzzy-rewrite, quiz drop, insert_run retry, stamp extraction/no-op).
`test_quiz_shuffle.py::test_malformed_questions_dropped_not_shipped` pins the
new drop behavior.

## Related

- `docs/bugs/2026-07-08-mega-path-regressions.md` — same review sweep (P0).
- `docs/bugs/2026-07-07-quiz-answer-position-bias.md` — the fuzzy/drop was
  its declared follow-up.
- Deferred from this tier: checkpoint run-id stamping (mixed-attempt chain
  detection) — key coercion removes the known breakage; chain identity is a
  hardening follow-up.
