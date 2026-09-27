# 2026-09-22 — new website page merged but 404 on the live site

**Severity:** low
**Area:** pipeline (pack) · website
**Status:** fixed
**Keywords:** 404, podcast.html, SHELL_FILES, pack_and_upload, allowlist, deploy-on-push, new page, cleanUrls

## Symptom

`website/podcast.html` was merged to main (#62), `Deploy website on push` ran green, yet
`https://kidsnews.21mins.com/podcast` returned Vercel's `404 NOT_FOUND` (Jiong's phone
screenshot, 2026-09-22 21:14). `podcast.html` was also absent from the kidsnews-v2 repo
that Vercel builds from.

## Root cause

The site bundle is not "everything under website/". `pipeline/pack_and_upload.py:49`
builds the shell from an explicit allowlist, `SHELL_FILES` (index.html, article.jsx, …,
autofix.html) plus `SHELL_DIRS` (assets, components). A brand-new top-level page is
silently skipped: the pack step succeeds, the dispatch to kidsnews-v2 succeeds, the sync
finds nothing new, and the workflow reports success with the page never leaving the repo.
Nothing in CI compares `website/*.html` against the allowlist, so the omission was
invisible until a person loaded the URL.

## Fix

`fix(pack): ship website/podcast.html (SHELL_FILES allowlist)`

- `pipeline/pack_and_upload.py:52` — `"podcast.html"` added to `SHELL_FILES`.

## Invariant

**A new top-level file under `website/` is not live until it is named in
`pack_and_upload.SHELL_FILES` (or lives in a `SHELL_DIRS` directory).** Adding a page =
adding the file *and* the allowlist entry in the same PR. If this bites again, the right
next step is a CI check that fails when `website/*.html` contains a file the allowlist
does not.

## Notes

`terms-of-use.html` is in the same situation (present in the repo, not in the allowlist);
left as is because nothing links to it yet.
