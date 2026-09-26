# 2026-09-15 — Middle body shipped at 724w (vs 300-410 band); add generation-time repair

## Symptom

2026-09-14's News #1 (PBS, EPA climate-rule story) shipped with a
middle_en body of 724 words — nearly double the 300-410 band — shown to
kids as a "7 min" read. Stage 3 logged the flag
(`word-count flag source_id=0 · middle: 724w outside 300-410`) but
flags are advisory: the article ships anyway and quality_digest only
tickets it the next morning. Word-count flags per run rose from 2
(Sep 8) to 5 (Sep 14) after DeepSeek silently replaced V4 Flash with
V4.1-Flash on Sep 10.

## Root Cause

The tri-variant rewriter prompt's word caps ("HARD MAXIMUM 400 words.
STRICT — count silently before returning") are advisory to the model.
V4.1-Flash ignores them more often than its predecessor. There was no
deterministic enforcement between generation and publish — only the
warning log and a next-day digest ticket.

## Fix

New `repair_wordcounts()` in `pipeline/news_rss_core.py`, called at the
top of `filter_safe_rewrites` (before the independent safety vet, so
the vet scores the text that ships):

- measures each easy/middle body against `WC_BANDS`;
- for each out-of-band body, makes ONE targeted `deepseek_call` asking
  to compress/expand that single body into the band (repair targets
  210-300 / 320-380 leave margin inside the 200-320 / 300-410 bands);
- accepts the repair only if the result is inside the band; otherwise
  keeps the original (degrades to the previous flag-and-ship behavior);
- one attempt per variant, honoring the one-regen-per-body project
  policy; call failures are caught and logged.

Tests: `pipeline/test_wc_repair.py` (repair applied, out-of-band repair
rejected, call failure keeps original, in-band bodies make no calls,
short body expanded).

## Verification

- `pytest pipeline/test_wc_repair.py pipeline/test_safety_quality.py`
  → 13 passed (new pass + existing Stage 3 suite unaffected).
- First real run (34927289853, 2026-09-15): pass fired 10 times,
  repaired only **2**. Run succeeded and published; 7 of 18 published
  variants were still out of band. See follow-up below.

## Follow-up — v1 could not expand (fixed same day)

The v1 repair prompt told the model to expand a too-short body "with
details already present in the text", and the repair call never
received the source article. With no material to add, the model
returned the input verbatim — 5 of the 7 misses came back at exactly
their original length (192→192, 254→254, 257→257, 265→265, 462→462).
Today's dominant failure mode was too SHORT (5 of 7), not too long.

v2 changes:
- `_wc_repair_user_msg()` splits SHORTEN and EXPAND into separate
  framings, and states "returning it unchanged is a failure".
- `repair_wordcounts(rewrite_result, sources_by_id)` — the EXPAND path
  now receives the original source article (1200-word excerpt) so
  added details are real and sourced; `filter_safe_rewrites` threads it
  from `_winners` (mega path) and from `art` (spare-promotion path).
- Tests: 3 more cases (expand carries SOURCE ARTICLE, shrink does not,
  missing source doesn't crash) → 21 passed across the touched suites.
  The 1 pre-existing failure (`test_cadence_calibrate`) and 3 `test_feed`
  collection errors are present on clean main too.

## Lessons

- A prompt instruction is a request, not an invariant. Any spec the
  product depends on (length bands, required fields) needs a
  deterministic check + repair at generation time; log-and-ship means
  kids see the defect for a full day.
- Model swaps (even silent vendor-side ones) change instruction-
  following behavior; guards must be model-independent.
