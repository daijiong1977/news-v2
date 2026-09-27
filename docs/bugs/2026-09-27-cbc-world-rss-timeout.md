# 2026-09-27 — CBC World RSS stalls in direct feedparser fetch

**Severity:** medium  
**Area:** pipeline / source registry  
**Status:** proposed  
**Keywords:** CBC, News, RSS, feedparser, timeout, source diversity

## Symptom and root cause

The owner requested CBC World as another News source. Its public RSS and
article pages returned normally under an explicit RSS-reader request, but
the existing `feedparser.parse(url)` pipeline path stalled for more than
eight seconds in a read-only test. That call owns its network operation and
does not use the pipeline's HTTP timeout. A stalled feed can delay all of
Phase A. A generic browser UA is not a safe replacement: it made PBS serve
a challenge page with zero feed entries. An explicit RSS-reader UA returned
normal feeds from both PBS and CBC in repeated read-only checks.

The source registry currently has four enabled News publishers. CBC is a
fifth independent publisher, not a replacement for Al Jazeera. Jev scoring
of one small CBC snapshot found five of ten length-valid items above the
News pick and category-fit floors. That does not establish full-text child
safety or predict the final daily edition.

## Fix and invariant

- `pipeline/news_rss_core.py`: fetch RSS bytes with a 15-second bounded HTTP
  request and an RSS-reader UA, then parse bytes; HTTP errors and timeouts
  yield an empty source while the rest of the pipeline continues. Freshness
  behavior is unchanged. Do not reuse the HTML-page browser headers here.
- `supabase/migrations/20260927_add_cbc_world_news.sql`: add CBC World to
  `redesign_source_configs` as the fifth News publisher. Apply only after
  the code is deployed. The row can first be staged disabled in production
  for field verification; it must not be enabled while old fetch code runs.

Existing seven-day cross-category duplicate checks, Jev editorial/category
gates, body/image checks and independent full-text child-safety review must
continue to apply to CBC. More candidate supply is not permission to bypass
those gates or to force 3/3 distinct sources.

## Verification and rollout

- Regression tests: `pipeline/test_rss_fetch_timeout.py`.
- Before enabling CBC, verify its RSS freshness, article word counts and
  `og:image` through the new code. After enabling, compare Phase-A/probe/Jev
  candidates, source diversity, safety rejections and elapsed time for several
  scheduled runs.
- Rollback: disable only the `CBC World` row (do not delete history). The
  bounded RSS reader remains useful for the other sources.
