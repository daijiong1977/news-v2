# 2026-07-08 — safety-quality

**Severity:** high (safety) / medium (quality)
**Area:** pipeline (prompts + Stage 3 gate)
**Status:** fixed
**Keywords:** independent-vet, self-grading, safety, filter_safe_rewrites, is_forbidden, self-harm, word-count, body_too_short, 170-210, WC_BANDS, keyword-bar, background_read, audience-anchor

## Symptom

From the 2026-07-07 prompt review (P1/P2 tier):

1. **The final safety gate was self-graded** — the rewriter scored its own
   output's 8 safety dims in the same LLM call, and no independent reviewer
   ever saw the full rewritten text. Self-evaluation leniency is a
   well-documented LLM failure mode; "Score CONSERVATIVELY" does not
   counteract it.
2. **Body-only self-harm mentions passed every gate** — the forbidden regex
   (which covers suicide/self-harm) screened only RSS title+summary, never
   the fetched or rewritten body.
3. **The pipeline manufactured its own body_too_short tickets (66 all-time)**
   — the rewrite prompt demanded easy bodies of 170-210 words (STRICT) while
   quality_digest gates 200-320: any obedient 170-199-word body became a
   next-morning ticket. Nothing measured word counts at generation time.
4. Prompt hygiene: overlapping vet-rubric branches (dim=4 with total=4 was
   simultaneously REJECT and SAFE), inconsistent audience anchors ("age 12"
   vs "ages 8-13"), incoherent keyword grade-bars (both set BELOW the
   reader's grade), and background_read soliciting hallucination-prone
   specifics (years, tenures) with no guard.

## Root cause

Generation and judgment were fused: the same call that wrote the text was
the only scorer of that text, and every numeric contract in the prompts
(word bands, answer-matching, difficulty bars) lacked a matching measurement
at generation time — so violations surfaced (if at all) a day later in QA.

## Fix

PR: fix/p2-safety-quality. All in `pipeline/news_rss_core.py` unless noted.

- **`independent_safety_vet(articles)` + `SAFETY_VET_PROMPT`** — one extra
  chat call per rewrite batch scores the rewritten middle_en on 8 dims and
  re-scores fear/distress against easy_en imagined for a 9-year-old (max of
  the two readings — "easy is safe by construction" was false for
  age-relative dims). `filter_safe_rewrites` overwrites the self-scores with
  the independent ones (self kept as `safety_self` for telemetry) and falls
  back to self-scores on any vet failure — a vet outage degrades to the old
  behavior, never to reject-all. Verified live: real DeepSeek call returned
  full dims; benign story all-0, storm story fear=2/distress=2.
- **Deterministic forbidden backstop** — `is_forbidden()` now runs over the
  rewritten middle_en + easy_en bodies inside `filter_safe_rewrites`;
  a hit REJECTs regardless of scores.
- **Word bands aligned + measured** — easy band 170-210 → **210-300**
  (inside the digest gate 200-320); `WC_BANDS` + `_wordcount_flags` annotate
  `_wc_flags` and warn at generation time (kept in sync with
  quality_digest.BODY_TARGETS by comment).
- **Prompt hygiene** — vet rubric rewritten as ordered rules (REJECT →
  CAUTION → SAFE, first match wins); unified audience anchor ("ages 8-13,
  grades 3-8; safety to the youngest reader, interest to a 12-year-old");
  keyword difficulty bars replaced with the single operational test ("would
  a typical 10/13-year-old NOT know it"); background_read ACCURACY guard
  forbids specific years/figures not present in the body.

Cost: +1 chat call per category per run (3/day) — negligible next to the
reasoner calls.

## Invariant

1. The model that wrote a body is never the only safety gate on that body:
   `filter_safe_rewrites` must consult an independent scorer (or its
   documented fallback) before the threshold check.
2. `is_forbidden()` runs on the REWRITTEN text that ships, not only on feed
   metadata.
3. Any numeric band stated in a generation prompt must have a matching
   Python-side measurement at generation time (WC_BANDS mirrors
   quality_digest.BODY_TARGETS — change them together).

## Pinning test

`python -m pipeline.test_safety_quality` (5 tests: independent-override,
fallback-on-failure, forbidden-body reject, wc flags, band alignment).
Live smoke: `independent_safety_vet` on 2 fixture articles returns complete
dims (run 2026-07-08).

## Related

- `docs/bugs/2026-07-08-p1-reliability.md` — same sweep, mechanical tier.
- `docs/bugs/2026-05-02-pipeline-enrich-truncation.md` — same detail_enrich
  path (truncation risk unchanged by this fix).
- Deferred: automated re-ask on word-band violation (flags-only for now);
  card_summary triple-cap consolidation (LOW); curator candidate-order
  shuffle (LOW).
