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
| 2026-05-02 | high   | pipeline | [pipeline-enrich-truncation](2026-05-02-pipeline-enrich-truncation.md) | Phase D enrich split-batch hit max_tokens=12000 truncation on News middle (3 long stories + reasoner CoT). Bundle missed required fields, pack_and_upload refused upload, no Vercel redeploy. | detail_enrich, deepseek_reasoner, max_tokens, truncation, pack_and_upload, bundle-validation |
| 2026-05-01 | medium | infra | [quality-digest-schedule-wait-crash](2026-05-01-quality-digest-schedule-wait-crash.md) | Quality-digest backup cron crashed at wait step — `github.event.schedule` is the cron STRING not a timestamp, fromisoformat blew up. All downstream steps (autofix + send) skipped. | github-actions, quality-digest, schedule, fromisoformat, cron-string, workflow_run |
| 2026-05-01 | medium | pipeline | [rss-freshness-no-filter](2026-05-01-rss-freshness-no-filter.md) | RSS-feed intake had no freshness filter — a 17-day-old article slipped into today's bundle. Add max_age_days=5 cap (admin choice) at fetch_rss_entries; sourcefinder verification mirrors with same default. | rss, freshness, fetch_rss_entries, evergreen, age-filter |
| 2026-04-30 | medium | website + infra | [sticky-aside-deploy-chain](2026-04-30-sticky-aside-deploy-chain.md) | Article Read & Words right aside scrolled away with body on phone — and three same-day fix attempts (PR #8/#9/#10) silently never reached production because news-v2 → Vercel deploy chain wasn't wired (Vercel watches kidsnews-v2). | article, layout, sticky, aside, deploy-chain, vercel, kidsnews-v2, multi-repo, position-sticky |
| 2026-04-30 | medium | infra | [search-level-filter-loses-cross-level-matches](2026-04-30-search-level-filter-loses-cross-level-matches.md) | Search at user level (Tree → middle) returned 0 hits for words like "ocean" / "math" because easy/middle versions of same story use different vocabulary; level filter at SQL excluded the matching row | search, archive-search, tsvector, level-filter, cross-level
| 2026-04-30 | medium | infra | [supabase-edge-fn-html-blocked](2026-04-30-supabase-edge-fn-html-blocked.md) | Supabase Edge Functions silently override Content-Type to text/plain + add sandbox CSP, breaking HTML rendering in browsers | supabase, edge-function, content-type, csp, sandbox, html |
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
