# 2026-07-08 — news-image-drop-starves-supply

**Severity:** high
**Area:** pipeline (source supply)
**Status:** fixed
**Keywords:** verify_article_content, generic-social-image, og:image, news-shortfall, bundle-validation, NPR, pack_and_upload

## Symptom

The manually-triggered full run on 2026-07-08 (05:44 UTC, mega) FAILED: bundle
validation refused to publish because News had only **1 story** (need ≥2), so
`pack_and_upload` aborted (SystemExit 1) and nothing deployed. The live site
correctly kept the previous day's content (safeguard working).

## Root cause

News candidate flow that run: 16 briefs → curator ranked 5 (rank1/4/5 = NPR
World, rank2 = BBC, rank3 = PBS). Body-verify dropped **all three NPR ranks**
on `generic social image` (NPR's `facebook-default-wide` og:image). That left
2 verified (BBC + PBS). Stage 3's independent safety vet then correctly rejected
1 (a News story scoring dim≥3), leaving **1**. No spare could be promoted (the
NPR spares had also failed on the image).

So `verify_article_content` DROPPING an otherwise-good, kid-safe article merely
because its og:image is a generic social default starved a thin category (News
has 4 sources). NPR very frequently serves the facebook-default image, so this
recurs. The new independent vet (correct, conservative) removed the slack that
previously let News scrape by at 2.

## Fix

PR: fix/news-keep-generic-image. `pipeline/news_rss_core.py::verify_article_content`
no longer rejects on a generic social image — it keeps the article (the image
is ugly but VALID and renderable; the card still shows something). A missing
image (`not og_image`) is still rejected, which avoids sending a null image
into the download path. Test updated: `test_generic_image_now_kept`.

This recovers the NPR candidates → News has enough to survive the safety vet's
1-per-category rejection.

## Invariant

Image quality is nice-to-have, never a reason to DROP a kid-safe article with a
good body. Only a genuinely missing image is rejected (to avoid a null-image
download path). The frontend degrades a missing/blank image to a category-colour
card (`home.jsx`: `s.image ? url(...) : c.color`), so image-less cards are safe.

## Pinning test

`python -m pipeline.test_filter_polish::test_generic_image_now_kept` — generic
image → kept; `test_missing_image_reported_honestly` — missing → rejected.
End-to-end: a re-triggered run should ship News ≥ 2 and publish.

## Related

- `docs/bugs/2026-07-07-pbs-waf-bot-challenge.md` — the PBS fix (confirmed
  working this run: PBS rank3 verified 707w).
- `docs/bugs/2026-07-08-safety-quality.md` — the independent vet that removed
  the slack.
- Follow-up: nicer per-category placeholder image instead of shipping NPR's
  generic default (cosmetic).
