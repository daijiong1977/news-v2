# v1 KidsNews — Decommission Inventory

**Status:** PENDING (delete deferred a few days for safety review)
**Compiled:** 2026-04-25
**Analyst:** Claude Opus 4.7

This document captures everything tied to the **original KidsNews (v1)** that
would be removed when we decommission it. The v2 site at news.6ray.com
(`daijiong1977/kidsnews-v2` deploy + `daijiong1977/news-v2` pipeline) is
unaffected — every "delete" entry below has been cross-referenced against
v2's actual code paths.

The Supabase project `lfknsvavhiqrsasdfyrs` is shared between v1, v2,
and at least one other app family (vocab / portfolio). The project itself
**must not be deleted** — only specific tables / buckets / functions.

---

## Vercel

| Action | Project | Linked repo | Domain | Notes |
|---|---|---|---|---|
| **DROP** | `news-ohye` | `daijiong1977/kidsnews` | kidsnews.6ray.com | id `prj_MY40MNZvi6Nbsv49vaqpNt6E8eof` |
| keep | `kidsnews-v2` | `daijiong1977/kidsnews-v2` | news.6ray.com | current site |
| keep | `news-v2` | `daijiong1977/news-v2` | news-v2-phi.vercel.app | pipeline preview deploys |

After dropping the project, the `kidsnews.6ray.com` subdomain CNAME / alias
will need to be removed from the 6ray.com DNS too (Vercel doesn't free the
record automatically because the apex domain stays attached to other projects).

## GitHub

| Action | Repo | Created | Notes |
|---|---|---|---|
| **ARCHIVE** | `daijiong1977/kidsnews` | 2025-11-11 | v1 frontend; homepage `news-ohye.vercel.app`; references `articles`, `categories`, `feeds`, `cron_jobs`, `user_profiles` etc. |
| **CONFIRM** | `daijiong1977/news` | 2025-10-20 | older repo, no homepage, last touched 2025-10-31. May be earlier v1 prototype — verify before deleting. |
| keep | `daijiong1977/news-v2` | — | current pipeline |
| keep | `daijiong1977/kidsnews-v2` | — | current deploy |

Recommendation: **archive** rather than delete the v1 repo (preserves
source code for future archaeology) unless storage is at a premium.

## Supabase — `lfknsvavhiqrsasdfyrs.supabase.co`

### Tables to drop (v1-only)

Cross-checked against `admin.html`, `user_manager/`, `index.html` in the
`kidsnews` repo. None of these are written or read by `news-v2/pipeline/*`.

**Content**
- `articles` (943 rows)
- `article_images` (943 rows)
- `article_summaries`
- `article_analysis`
- `background_read`
- `keywords`
- `questions`
- `choices`
- `comments`
- `response` (910 rows)

**Source registry (v1)** — note v2 uses `redesign_source_configs` instead
- `categories` (7)
- `feeds` (10)
- `difficulty_levels` (3)

**v1 users / auth** — v2 has no auth yet; `redesign_user_responses` uses
anonymous client_id from localStorage
- `users` (0; commented "Legacy user system (deprecated)")
- `user_difficulty_levels`
- `user_categories`
- `user_preferences`
- `user_awards`
- `user_subscriptions`
- `user_stats_sync`
- `user_stats` (1)
- `user_profiles` (2)
- `magic_links` (5)
- `demo_users` (5)

**v1 admin / infra** — v2 cron lives in GitHub Actions, secrets in repo secrets
- `cron_jobs` (4)
- `apikey`
- `api_keys` (7)
- `ai_providers` (2)
- `secrets` (6)
- `client_devices` (1)
- `feedback`

### Tables to KEEP

**v2 pipeline (current):**
- `redesign_runs` (19) — pipeline execution log
- `redesign_stories` (18) — published story metadata
- `redesign_source_configs` (39) — RSS source registry
- `redesign_user_responses` (3) — kid feedback

**Vocab apps (VocabPalace / SatSpell / WordScholar):**
- `words` (100), `word_lists` (2), `word_list_items` (100), `word_ai_content` (50), `user_progress` (40)

**Confirm before keeping (likely portfolio, NOT v1 KidsNews):**
- `posts` (52), `about` (1), `projects` (16)

### Storage buckets

| Action | Bucket | Objects | Size | Top-level dirs |
|---|---|---|---|---|
| **DROP** | `shared-storage` | 5382 | 122 MB | `website/` (3501), `image/` (969), `json/` (912) — all v1 |
| keep | `redesign-daily-content` | 144 | 8.2 MB | v2 daily zips + flat files |
| keep | `redesign-article-images` | 72 | 4.2 MB | v2 webp images, dated paths |
| confirm | `about-photos` | 0 | — | empty; almost certainly portfolio (not v1) |

### Edge Functions

The v2 pipeline runs from GitHub Actions, not from edge functions.
Every function below was created Nov 10–22, 2025 (v1 era).

**DROP — v1 pipeline & website generation:**
- `payload-generator`
- `generate-website`
- `test-generate`
- `generate-and-store-website`
- `process-images`
- `daily-pipeline`
- `zip-to-git`
- `cleanup-old-data`
- `cleanup-json`

**DROP — v1 auth & admin:**
- `bootstrap`
- `bootstrap-legacy`
- `ai-key`
- `auth-register`
- `test-auth`

**KEEP** (used by other apps or v2):
- `health`
- `send-email`, `send-email-v2`
- `storage-api`
- `feedback-rewrite` (v2 reader feedback flow → `redesign_user_responses`)

## Render

**Unknown** — no API access from this session. User to confirm which
services exist on render.com (if any) and identify v1-related ones.

Likely candidates if v1 had any Render usage:
- A Node/Python pipeline service (cron-based article generation)
- A staging API
- A scheduled cleanup worker

If nothing on Render is tied to v1, no action needed.

---

## Recommended deletion order

To minimize risk of orphaned writes leaving stale state behind:

1. **Vercel project `news-ohye`** — stops the live v1 site immediately.
   DNS alias for `kidsnews.6ray.com` cleared from 6ray.com config.
2. **Render services** (if any) — stops v1 background work.
3. **Supabase Edge Functions** — listed above; stops any orphaned writers.
4. **Supabase tables** — listed above. Snapshot `articles`, `article_images`,
   `response` to a JSON dump before drop, in case anything's worth keeping.
5. **Supabase storage bucket `shared-storage`** — once table refs gone.
6. **GitHub repos** — archive (not delete) `kidsnews` and (if v1) `news`.

## Pre-flight backup

Before step 4, capture a one-shot JSON dump:

```bash
# inside news-v2 repo, with SUPABASE_URL + SUPABASE_SERVICE_KEY in env
mkdir -p backups/v1-2026-04-25
for t in articles article_images response user_profiles; do
  curl -fsS "${SUPABASE_URL}/rest/v1/${t}?select=*" \
    -H "apikey: ${SUPABASE_SERVICE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
    > "backups/v1-2026-04-25/${t}.json"
done
```

Stash that backup somewhere outside the repo (cloud drive) and *then*
proceed with drops.

## Open questions for the user

1. Is `daijiong1977/news` repo v1-related, or unrelated?
2. Are `posts` / `about` / `projects` tables portfolio-related (not v1)?
3. What services exist on Render, and which are v1?

Resume the cleanup once these are answered and the backup is taken.
