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
- Watch the next daily runs for `wc-repair` log lines and a drop in
  `word-count flag` warnings / digest body_too_long tickets.

## Lessons

- A prompt instruction is a request, not an invariant. Any spec the
  product depends on (length bands, required fields) needs a
  deterministic check + repair at generation time; log-and-ship means
  kids see the defect for a full day.
- Model swaps (even silent vendor-side ones) change instruction-
  following behavior; guards must be model-independent.
