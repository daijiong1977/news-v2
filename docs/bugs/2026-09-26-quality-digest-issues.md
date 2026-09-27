# Quality digest: long/short bodies and 2/3 sources (2026-09-26)

## Evidence

The owner's digest reported seven middle-body length defects and two
source-diversity defects across September 24–26. Public Storage payloads
still show the seven bodies out of the digest's 300–410 ±15% band.

- September 25 News: BBC, PBS, BBC. Run 36106439452 rejected three initial
  News rewrites on child-safety grounds and promoted two spares. The final
  selection did not re-optimize for three distinct sources.
- September 25 Fun: Live Science, Live Science, NG Kids — Space. The same
  run probed 19 viable items across several feeds, but the curator's top
  five had only two sources. It logged that no third-source spare existed
  *inside that five*; Stage 3 did not try the wider spare pool because the
  story count was already three.
- The September 25 run repeatedly logged word-count repair output still
  outside 300–410 (for example 203→283, 246→260 and 534→534). The old
  repair kept the original and Stage 3 merely logged a flag, then published.
  Run 36282782318 on September 26 also logged 503→501 for a Science body.
- The digest inspected three days, but the auto-fix workflow scanned one
  day only. Additionally, its body handler accepted a rewrite even if it
  remained outside the QA band and uploaded it without a new independent
  full-text child-safety review.

## Fix

1. Carry the source article into short-body repair (the previously open
   PR #47 fix), and accept a repaired body only when it clears the *same*
   ±15% QA tolerance used by the digest. An article still outside that
   tolerance is not publishable; Stage 3 can use an independently vetted
   spare. No mechanical truncation or unsourced padding is used.
2. Re-order already-vetted Stage-3 survivors to use three sources when
   possible. If three stories survive but only two sources remain, try a
   different-source spare through the normal body, category and child-safety
   gates. If none passes, publish the safer two-source set and log an
   explicit degradation; source diversity does not override child safety.
3. Auto-fix scans the same *number* of archived days as the digest lookback,
   never today's static website bundle. It accepts a replacement only if
   length and keywords pass, the forbidden-term backstop is clear, and an
   independent reviewer scores the complete easy+middle text as safe.
   Missing source text (for expansion), missing counterpart, or reviewer
   failure escalates without overwriting the published payload.
4. The digest email no longer claims adding a feed or rerunning alone will
   necessarily solve source diversity, nor promises that any rewrite will
   be applied regardless of its checks.

## Verification and operational follow-up

- Offline regression suite: 189 passed (excluding feed/live-provider suites
  that require external credentials or have pre-existing collection issues).
- A live full pipeline run has **not** yet used this branch. Do not infer
  production success from unit tests.
- Historical payloads are unchanged by the code PR. After review/merge,
  let the archive auto-fix scan the affected dates and inspect the resulting
  queue, digest and public Storage payloads. The regular site serves today's
  static bundle; archived dates read directly from Storage.
- The in-progress old-code digest run 36283016740 was cancelled before its
  unsafe auto-fix step. The next scheduled digest should not run the old
  handler before this PR is merged or the workflow is otherwise guarded.

## Tuning points

- `news_rss_core.WC_BANDS` and `quality_digest.BODY_TARGETS` define ideal
  lengths; `WC_QA_SLACK` and `WC_SLACK` must stay equal.
- `mega_curator._enforce_top3_source_diversity` handles initial picks;
  `full_round._prefer_final_source_diversity` and the Stage-3 new-source
  spare attempt handle post-vet changes. Jev's `FLOOR` and
  `CATEGORY_FIT_MIN` still protect editorial relevance.
- The archive auto-fix lookback is controlled by `QUALITY_DIGEST_DAYS` in
  `.github/workflows/quality-digest.yml`.
