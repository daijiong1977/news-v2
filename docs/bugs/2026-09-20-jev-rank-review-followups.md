# 2026-09-20 — jev_rank review follow-ups

**Severity:** medium
**Area:** pipeline
**Status:** fixed
**Keywords:** jev_rank, mega_curator, exactly 5, MIN_SEND, already_published, _jev_pick, cache, skip reason, checkpoint scratch state

## Symptom

None observed in production — found reviewing #48/#49/#51 the same day they
merged, before the first scheduled run used them. Four defects, all in code
that was already on `main`:

1. On 2026-09-20 the curator was handed **4** News briefs while its prompt
   demanded "exactly 5 ranked picks per category". It returned 4 (graceful),
   but nothing guaranteed that.
2. The run log reported 17 "pair checks" for 58 briefs; some of those were the
   same question asked two or three times.
3. A brief skipped in a fill pass was logged under the rule that deferred it,
   not the rule that actually blocked it.
4. Injecting an exception into `_select` left `_jev_pick` on every brief, and
   the caller checkpoints those briefs.

## Root cause

**1 — unsatisfiable output contract.** `MEGA_CURATOR_SYSTEM_PROMPT` was written
when the probe always handed the curator 10 candidates per category, so "rank
5" was always possible. #51 made the count variable (`MIN_SEND=4` ..
`TO_CURATOR=6`) without touching the prompt, which still read "OUTPUT CONTRACT
(strict): exactly 5 ranked picks per category" and "~36 candidates from 9 RSS
feeds". To comply from a pool of 4 the model must repeat a candidate id or
invent one. `mega_curate` drops both (`cid in seen_ids -> continue`; unknown id
-> warn + skip), so the category silently loses a rank and `reasoning` is
written against a rule that could not be followed. The invariant: a prompt that
states a fixed output count must be regenerated, or relaxed, whenever the input
count becomes variable.

**2 — half-cached pair questions.** `_Pairs.relation` memoises on
`(id(a), id(b), subject)`; `_Pairs.already_published`, added later for the
cross-category repeat check, did not. `_select` asks `hard_reason` up to three
times per brief — main pass, cap fill, below-floor fill — and each ask re-walked
every recent title and re-issued the Jev calls. Beyond the waste this is a
correctness hazard: `already_published` returns early once
`time.monotonic() > self.deadline`, so the *same* brief can answer "repeat of a
published story" in the main pass and "not a repeat" in a later one.

**3 — stale deferral reasons.** The fill passes tested `hard_reason(b)` but, on
a hit, left the brief in `capped`/`low` carrying the soft reason it was
originally deferred with. `chosen` grows between passes, so a brief deferred as
"already 2 from this source" can genuinely become "same story as a
higher-ranked pick" — and the run log, the only record of why a story did not
ship, named the wrong rule.

**4 — scratch state cleaned on one path.** `_jev_pick` is written onto every
brief so `_select` can sort and compare without carrying the scores dict. It
was popped inside the per-category loop and again after it, both on the success
path only. `rank_briefs` catches every exception and returns `(None, report)`,
so a failure mid-selection returns normally with the key still attached; the
caller then checkpoints those briefs.

## Fix

Branch `review-fixes`.

- `pipeline/mega_curator.py`: prompt states "rank EVERY candidate a category
  gives you, up to 5", forbids repeating or inventing an id, and the
  per-category header carries the count.
- `pipeline/jev_rank.py`: `already_published` memoises per brief, with
  `forget_published` clearing the entry when a call fails so a retry is still
  possible; the three fill passes share one `_fill` helper that moves a
  re-blocked brief into `hard` with the real reason; `_jev_pick` cleanup moved
  into the `finally`.
- `pipeline/test_jev_rank.py`: three regression tests — the already-published
  question is asked once per brief, scratch state never survives (including
  after an injected exception), and a fill pass reports the blocking reason.

Left alone and documented in the module: `cap_may_yield` weighs alternatives
that a hard rule may later reject, so it can decline to yield in favour of a
brief that can never be chosen. The fill passes recover the deferred brief, so
the cost is ordering only.

## Prevention

Two patterns worth carrying forward:

- **A prompt is an interface.** When a stage changes how many items it hands an
  LLM, grep the prompt for the old count. "Exactly N" outlives the code that
  guaranteed N.
- **If one lookup in a class is cached, the next one added must be too.** The
  asymmetry is invisible at the call site — both look like plain method calls —
  and here it turned a deadline into a source of inconsistent answers.
