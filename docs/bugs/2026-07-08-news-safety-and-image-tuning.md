# 2026-07-08 — news-safety-and-image-tuning

**Severity:** medium
**Area:** pipeline (safety policy + image handling)
**Status:** fixed
**Keywords:** evaluate_rewriter_safety, per-dimension, threshold, violence, adult_themes, verify_article_content, og_image, generic-social-image, NPR, placeholder, category-colour-card

## Symptom

After the first successful full run (2026-07-08), two owner observations:

1. **PBS (and other hard-news) getting over-filtered.** PBS NewsHour fetched +
   verified fine (Googlebot fix working), but its serious world-news stories
   ("US strikes on Iran", "NATO summit") were rejected by Stage 3 safety
   (`any_dim ≥ 3`, e.g. violence/fear = 3). For a kids NEWS site, moderate
   war/politics/conflict coverage IS appropriate — over-filtering it starves
   News and drops legitimate world news.
2. **NPR photos "both wrong".** The prior fix kept NPR articles that carry the
   generic `facebook-default` og:image — so two NPR cards showed NPR's branding
   logo instead of a real photo.

## Fix

PR: fix/news-safety-image-tuning.

### 1. Per-dimension Stage-3 safety thresholds
`pipeline/news_rss_core.py::evaluate_rewriter_safety` — replaced the single
`any_dim ≥ 3 → REJECT` with two tiers (admin choice):
- **Strict (>= 3 rejects):** `sexual`, `substance`, `language` — never
  appropriate for kids regardless of news value.
- **News-inherent (>= 4 rejects):** `violence`, `fear`, `distress`,
  `adult_themes`, `bias` — kids on a news site should read age-appropriate hard
  news, so a MODERATE level (3) passes; only SEVERE (4-5, e.g. graphic gore)
  rejects.

So "US strikes on Iran" (violence/fear = 3) now PASSES; sexual/drug/profanity
content at 3, or graphic violence at 4-5, still REJECTS.

### 2. Image is optional; never ship a generic image
`pipeline/news_rss_core.py::verify_article_content` — a missing OR generic
social image is now **cleared** (`og_image = None`) and the article is KEPT.
The frontend renders a clean category-colour card (`home.jsx:
s.image ? url(...) : c.color`), and `process_images()` skips a null og_image
(`full_round.py: if not og: continue`). Supersedes the earlier "keep the
generic image" fix (which shipped NPR's ugly logo). Never drop a kid-safe
article for its image; never ship the generic branding image.

## Invariant

- Safety reject is per-dimension: strict dims (sexual/substance/language) at
  ≥3, news-inherent dims at ≥4. Changing the split is an admin policy decision —
  keep the strict trio strict.
- A kid-safe article is never dropped for image reasons; a missing/generic
  image is cleared to None (colour card), never shipped as the photo.

## Pinning test

`python -m pipeline.test_safety_quality` — `test_moderate_news_dims_pass`,
`test_severe_news_dim_rejected`, `test_strict_dims_still_reject_at_3`.
`python -m pipeline.test_filter_polish` — `test_generic_image_cleared_not_shipped`,
`test_missing_image_kept_and_cleared`, `test_real_image_kept`.

## Related

- `docs/bugs/2026-07-08-news-image-drop-starves-supply.md` — the earlier
  keep-generic-image step this supersedes.
- `docs/bugs/2026-07-08-safety-quality.md` — the independent vet whose scores
  these thresholds are applied to.
- Follow-up: real per-category placeholder art (nicer than a plain colour card);
  extracting a real in-body image for NPR instead of clearing.

## Update (same day) — image policy reverted to REJECT

Owner decision: image quality matters more than article count — if the image
is wrong/missing, REJECT the article rather than ship a blank category-colour
card. `verify_article_content` is back to rejecting on missing/generic image.
This is affordable because the per-dimension safety loosening (kept) lets
real-image hard-news sources (PBS/BBC/Al Jazeera) through, so News fills from
good-image articles. Residual thin-News risk remains → durable fix is more
News sources and/or extracting a real in-body image for NPR.
Tests: test_missing_image_rejected, test_generic_image_rejected, test_real_image_kept.
