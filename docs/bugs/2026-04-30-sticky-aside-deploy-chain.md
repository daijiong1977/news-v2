# 2026-04-30 — sticky-aside-deploy-chain

**Severity:** medium (low for the layout itself, medium for the deploy-chain mis-design that compounded it)
**Area:** website + infra
**Status:** fixed
**Keywords:** article, layout, sticky, aside, read-and-words, deploy-chain, vercel, kidsnews-v2, multi-repo, position-sticky, latest.zip

## Symptom

User feedback (issue #6, feedback row 11, user level Tree, en) on
2026-04-30:

> the story left side is too long comparing to right side. Maybe we
> can use scroll or adjust the left right ratio to make it more
> balance and easy to read.

The reporting user was on iPhone Safari at ~390px portrait. On the
article view's default Read & Words tab, the body column scrolls
naturally with the page, and the right `<aside>` (Word Treasure
keyword cards + optional "Why it matters" panel) was scrolling
out of view as the user read down. Visually the page felt
unbalanced because the body got tall while the keyword glossary
disappeared.

## Root cause

**Two independent failures compounded** and made today's diagnosis
harder than it needed to be:

### Failure 1 — the actual layout bug

`website/article.jsx:561` — the right `<aside>` had no `position:
sticky` so its grid item stretched to row height (`align-self:
stretch` is the grid default) and scrolled with the body. The
keyword glossary was referenced from the highlighted words in the
body, so once the user scrolled mid-paragraph the glossary was
no longer visible.

A nearly identical sticky pattern was already used in `article.jsx`
at line 990 (the quiz tab's "Look back at the story" panel) so the
solution was a known good fit — just hadn't been applied to the
Read & Words aside.

### Failure 2 — the deploy chain was silently broken

`daijiong1977/news-v2` is the source repo. Vercel watches a
*different* repo, `daijiong1977/kidsnews-v2`, which has a sync
workflow that downloads `latest.zip` from Supabase Storage and
replaces its `site/` directory. Pushes to news-v2/main do NOT
trigger that sync — only the daily-pipeline cron's
`pack_and_upload` step refreshed the `latest.zip` (which holds
both daily content AND the website source), and that ran once a
day.

So three earlier same-day attempts to fix the layout shipped
**zero effect**:

- **PR #8** — applied the correct sticky-aside change. Merged
  17:51 UTC. Admin reported "looks the same as before fix";
  reverted at 19:14 UTC. **The CSS was correct;** it never
  reached production.
- **PR #9** — pivoted to `useIsNarrow` grid collapse on mobile
  (a different angle). Closed without merge during the retry
  cycle, same root cause.
- **PR #10** — `useIsNarrow` again, this time with Chrome
  DevTools MCP screenshots embedded as visual verification.
  Merged 20:31 UTC. Admin still didn't see effect on the live
  site (because deploy chain still broken); rolled back via
  `pr-rollback.yml` workflow.

We finally noticed when the admin pointed out that yet again
"nothing changed on the live site" and we traced
`kidsnews-v2/site/article.jsx`'s blob hash — it was identical to
the original pre-PR-#8 hash, confirming none of the source-side
PRs had ever reached production.

## Fix

Two-part fix landed in two commits on main:

**Part 1 — wire the deploy chain (commit `8d166cb`):**

- `.github/workflows/deploy-on-push.yml` — fires on push to main
  with path filter `['website/**', '.github/workflows/deploy-on-push.yml']`.
  Steps: `PACK_REPUBLISH_ONLY=1 pack_and_upload` (pulls today's
  article content from existing `latest.zip` on Supabase, repacks
  with fresh website source, uploads new `latest.zip`) →
  `repository_dispatch` to `kidsnews-v2` `news-v2-uploaded` event
  → `kidsnews-v2`'s `sync-from-supabase.yml` downloads the new
  `latest.zip`, replaces `site/`, commits, pushes → Vercel
  auto-deploys from `kidsnews-v2/main`.
- End-to-end measured ~47s from news-v2 push to news.6ray.com
  serving the new bundle.

**Part 2 — apply the sticky-aside CSS (commit `293f78d`):**

- `website/article.jsx:561` — added `position:'sticky', top:90,
  alignSelf:'start', maxHeight:'calc(100vh - 110px)',
  overflow:'auto'` to the Read & Words `<aside>` style. Same
  code as the reverted PR #8.
- `alignSelf:'start'` is required so the grid item stays
  content-sized rather than stretched; otherwise sticky never
  activates because the cell already fills the row. `top:90`
  matches the existing pattern at `article.jsx:990`.

**Note on commit hygiene:** Part 2 was originally pushed as
`chore(test): re-apply PR #8 sticky-aside to demo deploy chain
end-to-end` because it doubled as the deploy-chain smoke test.
Per the new shipped-project policy
(`~/myprojects/lessons/universal-patterns.md` § 15) that change
should have been a `fix(article):` PR with this bug record. This
record is the retroactive correction.

## Invariant

In `ReadAndWordsTab` (`website/article.jsx:561`), the right
`<aside>` MUST keep `position: sticky` with `top: 90`,
`alignSelf: 'start'`, `maxHeight: 'calc(100vh - 110px)'`, and
`overflow: 'auto'`. Removing any of these breaks the sticky
behaviour — `alignSelf: 'start'` is the subtle one (without it
the grid item stretches and sticky binds to a non-scrollable
cell).

`.github/workflows/deploy-on-push.yml` MUST stay in place. If it
is deleted or its `paths:` filter is widened/removed, future
website changes will silently fail to deploy (the daily-pipeline
cron will eventually pick them up at next run, but admins who
expect "merge → live in 90s" will be misled).

The pattern at `article.jsx:990` and `article.jsx:561` has
duplicated literal values (`top:90`, `maxHeight:'calc(100vh -
110px)'`). Copilot's PR review on PR #8 flagged this as a DRY
violation; deferred for a future cleanup pass — when fixing
either, also fix the other and consider extracting shared
constants.

## Pinning test

MANUAL (60s click-through):

1. Open any article on news.6ray.com / kidsnews.21mins.com at
   desktop width — Read & Words tab should show body left,
   Word Treasure right, in a 1.6fr/1fr grid. Scroll the page;
   Word Treasure must remain pinned at top of viewport (~90px
   from top) while the body scrolls past.

2. Resize the browser to ~390px wide (or open Chrome DevTools
   device toolbar at iPhone 12). Same behaviour: Word Treasure
   sticky at top, body scrolls. (We did NOT add a mobile
   stacked-column collapse — kept the two-column sticky
   approach because admin preferred this pattern.)

3. From a fresh main checkout, change the `<aside>` style at
   `article.jsx:561` to remove `alignSelf:'start'` and redeploy.
   Word Treasure should immediately revert to scrolling-with-body
   behaviour, confirming alignSelf is the required piece.

## Related

- **Issue #6** — the originating user feedback. Auto-closed by
  PR #10's "Closes #6" body when PR #10 merged; stayed closed
  after PR #10's revert because the issue resolution-state and
  the code-state are decoupled.
- **PR #8 (reverted)** — `27a2f28` — same fix code; reverted
  because nothing reached prod (deploy chain).
- **PR #9 (closed)** — different angle (useIsNarrow); closed
  during retry cycle, never tested either.
- **PR #10 (reverted)** — same useIsNarrow approach as PR #9
  with Chrome MCP screenshots embedded; merged + rolled back
  for same deploy-chain reason.
- **`.github/workflows/pr-rollback.yml`** — exists from the
  earlier autofix-loop work; lets admin click [Rollback] in
  digest emails to revert a merged PR via `git revert + push`
  on main, triggering a fresh Vercel redeploy.
- **`.github/workflows/deploy-on-push.yml`** — the new
  source-repo-push → Vercel chain. Built today as part of this
  fix.
- **`~/myprojects/lessons/vendor-gotchas.md` Vercel § Multi-repo
  deploy chains** — generalised lesson for other projects.
- **`~/.claude/projects/-Users-jiong/memory/project_news_v2_deploy_chain.md`**
  — project memory with full chain diagram + verification queries.
- **`~/.claude/projects/-Users-jiong/memory/feedback_verify_deploy_claims.md`**
  — generalised "don't claim auto-deploy without checking" rule.
- **`~/.claude/projects/-Users-jiong/memory/feedback_pr_for_code_direct_for_knobs.md`**
  — the shipped-project PR-vs-direct-push policy this record
  retroactively complies with.
