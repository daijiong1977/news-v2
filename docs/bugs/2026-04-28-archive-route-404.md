# 2026-04-28 — archive-route-404

**Severity:** high
**Area:** website
**Status:** fixed
**Keywords:** vercel, cleanUrls, rewrite, SPA, routing, archive

## Symptom

`/archive/<date>` returned 404 on Vercel for every date — the archive
feature was unreachable from any URL after a Vercel rewrite tweak.
Refreshing the page on a working in-app archive view also 404'd.

## Root cause

`vercel.json` rewrite was set to:

```json
{ "rewrites": [{ "source": "/archive/:path*", "destination": "/index.html" }] }
```

But the project also had `cleanUrls: true`, which strips `.html`
extensions from URLs. With `cleanUrls`, Vercel rewrote
`/archive/<date>` → `/index.html` → and then cleanUrls "cleaned" the
destination to `/index`, which is not a real file → 404.

This is a Vercel-specific interaction: `cleanUrls` runs AFTER
rewrites and applies to the rewritten destination, not just the
incoming URL.

## Fix

- `website/vercel.json` — change destination to `/`:

```json
{ "rewrites": [{ "source": "/archive/:path*", "destination": "/" }] }
```

Vercel internally serves `/` as the SPA index without going through
cleanUrls' `.html` strip. Verified against production after deploy.
Same change copied into `kidsnews-v2/site/vercel.json` because that
repo's project is configured with `outputDirectory: "site"`.

## Invariant

Any SPA rewrite destination on a Vercel project with `cleanUrls:
true` MUST point at `/`, never at `/index.html`. If you need a
specific HTML entry point, disable cleanUrls for that route or use a
separate project.

## Pinning test

MANUAL: `curl -sI https://news.6ray.com/archive/2026-04-25 | head -1`
should return `HTTP/2 200`, not 404. After any vercel.json edit,
re-curl every documented archive URL form.

## Related

- `docs/bugs/2026-04-28-archive-click-race.md` — discovered while
  fixing this; once routing worked, the in-app click revealed the
  separate race-condition bug.
