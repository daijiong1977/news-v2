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
| 2026-07-08 | high | pipeline | [p1-reliability](2026-07-08-p1-reliability.md) | Five rare-path reliability defects: RESUME_FROM=enrich/persist broken by JSONB int→str keys; unanswerable quizzes shipped (frontend mapped to A); insert_run had no retry (one blip = zero persistence, site still deploys); same-day re-runs left orphan slot rows; sources rotation-stamped before deploy success. | RESUME_FROM, checkpoints, jsonb, quiz, fuzzy-match, insert_run, retry, orphan-slots, stamp_shipped_sources |
| 2026-07-08 | high | pipeline + infra | [mega-path-regressions](2026-07-08-mega-path-regressions.md) | Mega cutover (~07-02) silently dropped legacy safeguards: phase_a_light bypassed fetch_source_entries (freshness filter dead, html_list sources produced 0 briefs), only 3 sources/cat with no backfill, no past-run dedup, watchdog retried on the LEGACY variant; plus picked-but-failed sources hogged rotation slots forever (probe_* columns unused). Fixed as one batch. | mega, phase_a_light, freshness, html_list, backfill, dedup, probe_attempts, next_pickup_at, watchdog, pipeline_variant |
| 2026-07-07 | high | infra | [rls-disabled-advisory](2026-07-07-rls-disabled-advisory.md) | Supabase advisor: RLS disabled on 9 public tables → anon key could read/modify every row. Phase 1: enabled RLS on the 6 backend-only tables (zero website impact; search verified). Phase 2 (proposed): admins-only policy for engine_config/engine_source_reports/engine_mining_runs read by admin.html. | rls, row-level-security, anon-key, engine_config, redesign_search_index, security, supabase, admin-policy |
| 2026-07-07 | high | infra | [runs-status-check-mislabel](2026-07-07-runs-status-check-mislabel.md) | 14/38 runs showed false "failed / crashed" — redesign_runs status CHECK allowed only running/completed/failed, so the code's 'completed_with_warnings' + 'persisted' writes were rejected (23514), the row stuck at 'running', and the zombie sweep mislabeled a successful+deployed run as a crash. Fix: widen the constraint + relabel history. | redesign_runs, status, check-constraint, 23514, zombie-sweep, completed_with_warnings, false-failure, monitoring |
| 2026-07-07 | high | pipeline | [pbs-waf-bot-challenge](2026-07-07-pbs-waf-bot-challenge.md) | PBS put articles behind AWS WAF (JS challenge); plain fetch got a 2KB stub → 0-word body → every PBS article dropped → PBS shipped 0 stories/30d → News dipped to 2. Fix: detect the WAF stub and refetch as Googlebot (which the WAF allowlists). 0/6 → 6/6 kept. | pbs, fetch_html, aws-waf, bot-challenge, googlebot, user-agent, news-shortfall, extraction |
| 2026-07-07 | medium | pipeline | [quiz-answer-position-bias](2026-07-07-quiz-answer-position-bias.md) | Quiz correct answers almost always "B" (live 2026-07-07: A6/B71/C22/D0%). LLM parks the right MCQ option in a fixed slot and nothing reorders options before publish, so a kid scores 100% by always tapping B. | quiz, correct_answer, options, shuffle, detail_enrich, positional-bias, all-B, MCQ |
| 2026-05-03 | medium | website + edge-fn | [recently-read-no-cross-device-sync](2026-05-03-recently-read-no-cross-device-sync.md) | "Recently read" popover showed 0 entries on Device B for reads done on Device A — events table lacked title/image_url, so the cross-device cloud merge produced articleProgress entries with no rendering metadata and the popover silently dropped them. | recent_reads, RecentReadsPopover, fetchHistory, redesign_reading_events, articleProgress, snapshot, cross-device, kidsync |
| 2026-05-03 | medium | website  | [magic-link-onboarding-flash](2026-05-03-magic-link-onboarding-flash.md) | Clicking the magic-link in email lands on OnboardingScreen which shows the magic-link form again — race between cloud-bootstrap consumeMagicLink/fetchProfile and the synchronous render path. User loops back to "send magic link". | magic_link, consumeMagicLink, OnboardingScreen, sign-in, race, kidsync, fetchProfile, useEffect, hydration |
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
