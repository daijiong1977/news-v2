# KidsNews v2 — Architecture

**Date:** 2026-04-23
**Status:** Locked. Phase 1 current setup deviates intentionally; Phase 3 restores this architecture.

## Three repos

| Repo | Role | Vercel connected? | Live URL |
|---|---|---|---|
| `daijiong1977/kidsnews` | v1 deployment (reference only, do not touch) | ✅ | kidsnews.6ray.com |
| `daijiong1977/news-v2` | v2 **pipeline + source code** | ❌ (Phase 3 disconnects any temp connection) | — |
| `daijiong1977/kidsnews-v2` (future, not yet created) | v2 **deployment target** | ✅ | news.6ray.com |

## Daily production flow

```
┌─────────────────────────────┐
│  news-v2 repo               │
│  (pipeline + UI source)     │
│                             │
│  Daily cron:                │
│  Discover → Read → Vet      │
│  → Rewrite → Store          │
│  (Supabase redesign_*)      │
│                             │
│  Export: website-v2-        │
│  YYYY-MM-DD.zip             │
│  {payloads, article_payloads,│
│   article_images, manifest, │
│   UI static files*}         │
└──────────────┬──────────────┘
               │ push zip
               ▼
┌─────────────────────────────┐
│  kidsnews-v2 repo           │
│  (deployment target)        │
│                             │
│  .github/workflows/         │
│  unpack-website.yml:        │
│    detect zip → unzip into  │
│    root → commit [skip ci]  │
└──────────────┬──────────────┘
               │ Vercel git integration
               ▼
┌─────────────────────────────┐
│  Vercel project kidsnews-v2 │
│  → news.6ray.com            │
└─────────────────────────────┘
```

*UI static files in zip = option A: every daily zip includes the current UI source (index.html + .jsx). Ensures kidsnews-v2 never drifts from news-v2. Alternative (option B): manual sync on UI changes only. **Decision deferred to Phase 3.**

## Per-repo responsibilities

**news-v2** (this repo) contains:
- `pipeline/` — Node.js pipeline code (Phase 2)
- `website/` — UI source (HTML + JSX) — the source of truth
- `docs/superpowers/` — specs + plans
- `supabase/migrations/` — schema for `redesign_*` tables
- `scripts/export-zip.mjs` — builds the daily zip (Phase 2)
- `scripts/push-to-kidsnews-v2.sh` — pushes zip to kidsnews-v2 repo (Phase 3)

**kidsnews-v2** (future repo) contains:
- `index.html`, `*.jsx`, `components.jsx`, `user-panel.jsx`, `data.jsx` — UI static (daily-refreshed if option A, else committed manually)
- `payloads/` — daily-replaced by unpack workflow
- `article_payloads/` — daily-replaced
- `article_images/` — daily-replaced
- `.github/workflows/unpack-website.yml` — the unpack automation
- `vercel.json` — cache headers + cleanUrls, etc.

## Phase plan

- **Phase 1 (current): UI only.**
  - news-v2/website/ has UI + local copy of v1 payloads for development.
  - Temporary Vercel deploy from news-v2/website/ → news-v2-phi.vercel.app for mobile preview during dev. **This will be torn down in Phase 3.**
  - No pipeline, no kidsnews-v2 repo yet.
- **Phase 2: Pipeline.** Implement discover/read/vet/rewrite/store/export in news-v2/pipeline/. Output zip locally, inspect, iterate. Still no push to Vercel or kidsnews-v2.
- **Phase 3: Deployment wiring.**
  1. Delete temp Vercel project `news-v2`
  2. Remove `.vercel/` from news-v2/website/
  3. Create `daijiong1977/kidsnews-v2` GitHub repo
  4. Seed with UI source + `unpack-website.yml` workflow
  5. Create Vercel project `kidsnews-v2`, connect GitHub, bind `news.6ray.com`
  6. Add push-to-kidsnews-v2 step to pipeline
  7. First end-to-end dry run
- **Phase 4: Production.** Schedule cron, monitor, iterate.

## Supersedes

Prior draft `docs/superpowers/plans/2026-04-23-kidsnews-v2-phase1-ui.md` — that plan assumed v2 lived inside the kidsnews repo under `/v2/`. Now obsolete.
