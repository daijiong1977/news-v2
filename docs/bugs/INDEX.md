# Bug Records — Index

> 📖 **First time here?** Read [HOW-TO-USE.md](HOW-TO-USE.md) (in
> Chinese) for the workflow: how feedback enters the system, how to
> triage it, how to write a record, and how the commit-msg hook
> behaves.

One entry per fixed bug. Newest first. Grep this file (and the linked
records) BEFORE designing a fix in any of these areas — chances are
the same trap has bitten before and the record names the invariant
you must not break.

**Format:** `YYYY-MM-DD | severity | area | slug | one-line symptom | keywords`

---

| Date | Sev | Area | Record | Symptom | Keywords |
|---|---|---|---|---|---|
| 2026-04-29 | medium | infra | [autofix-token-starvation](2026-04-29-autofix-token-starvation.md) | Autofix daemon's back-to-back claude -p calls starved the user's IDE of API quota for ~2 min | claude, headless, daemon, rate-limit, concurrency, autofix |
| 2026-04-29 | high | website | [search-click-wrong-article](2026-04-29-search-click-wrong-article.md) | Clicking a search hit always opened today's first article instead of the searched one | search, archive, ARTICLES.find, listing-overwrite, synthetic-merge |
| 2026-04-28 | high | website | [archive-route-404](2026-04-28-archive-route-404.md) | `/archive/<date>` returned 404 across every date after a Vercel rewrite tweak | vercel, cleanUrls, rewrite, SPA, routing |
| 2026-04-28 | high | website | [archive-click-race](2026-04-28-archive-click-race.md) | Clicking an archive date opened the wrong article (today's, not the past day's) | useEffect, race, archiveDay, ARTICLES, async |
| 2026-04-28 | medium | website | [archive-slow-load](2026-04-28-archive-slow-load.md) | Switching to an archive date took ~5 seconds to render | sequential-fetch, parallelize, Promise.all, cache |
| 2026-04-28 | high | pipeline | [news-source-diversity](2026-04-28-news-source-diversity.md) | News bundle had two NPR articles instead of three diverse sources | spare-promotion, diversity, validator, used-source-names |
| 2026-04-28 | medium | pipeline | [keyword-stem-mismatch](2026-04-28-keyword-stem-mismatch.md) | Keywords like "negotiation" weren't matching body forms like "negotiating" → false-positive filter rejections | filter_keywords, stemmer, suffix-rewrite, inflection |

---

## How to use this index

- **Before fixing a bug**: grep for keywords related to the area you're
  about to touch. If a record names an Invariant in the file you're
  editing, your fix MUST preserve it.
- **After fixing a bug**: copy `_template.md`, fill it in, append a row
  here, and reference the path in your commit's `Bug-Record:` trailer
  (the commit-msg hook will reject `fix(...)` commits without one).

## How to use this with cross-referenced docs

- `docs/gotchas.md` — subtle traps still worth a cold-read even when
  no specific bug exists yet (silent edge cases, coupling pitfalls).
  When a bug record names a gotcha as related, link both ways.
- `docs/superpowers/specs/` — design docs for the feature the bug
  lives in. The spec tells you the *intended* shape; the bug record
  tells you *where reality diverged and what saved us*.
