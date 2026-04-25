# v2 Admin — Implementation Plan

**Scope:** Build a production-grade admin page at `news.6ray.com/admin` for
managing the v2 KidsNews pipeline. Google SSO auth (no self-registration);
first admin email seeded in migration; subsequent admins added by an
existing admin from the page itself.

**Date:** 2026-04-25

## Schema additions

All tables prefixed `redesign_*` for clean namespacing. RLS enabled with
admin-only policies driven by the `redesign_admin_users` table.

### `redesign_categories`
| col | type | notes |
|---|---|---|
| id | uuid PK | gen_random_uuid() |
| slug | text UNIQUE | `news` / `science` / `fun` |
| name | text | "News" / "Science" / "Fun" |
| emoji | text | "📰" / "🔬" / "🎉" |
| color | text | hex e.g. "#1f6bbf" |
| display_order | int | sort index |
| active | bool | filter inactive without dropping |
| created_at | timestamptz | |

Seed: 3 rows for the existing categories. Pipeline reads `WHERE active = true ORDER BY display_order`.

### `redesign_ai_providers`
| col | type | notes |
|---|---|---|
| id | uuid PK | |
| name | text | display name e.g. "DeepSeek V4" |
| base_url | text | API base URL |
| model_id | text | model identifier passed in payload |
| api_key_secret | text | name of the env var / Vault entry holding the key |
| role | text | enum: `curator` / `rewriter` / `enricher` / `any` |
| enabled | bool | |
| priority | int | lower = preferred when multiple match a role |
| max_tokens_default | int | optional override |
| temperature_default | numeric | optional override |
| created_at | timestamptz | |

Seed: 1 DeepSeek row, role=`any`, priority=1. Pipeline `select_provider(role)` picks lowest priority enabled match.

### `redesign_admin_users`
| col | type | notes |
|---|---|---|
| id | uuid PK | |
| email | text UNIQUE | matched against Google OAuth `user.email` |
| name | text | optional display name |
| added_by | uuid | FK to redesign_admin_users.id (null for the seed) |
| created_at | timestamptz | |
| last_login_at | timestamptz | bumped on each successful auth |

**Empty by design.** Frontend logic: if `COUNT(*) = 0`, page opens
without auth gate and shows a "Setup Admin" tab where the user enters
their first Google email. After ≥1 row exists, the page enforces
Google SSO; only emails in the table can access.

### `redesign_cron_config`
| col | type | notes |
|---|---|---|
| id | uuid PK | |
| name | text UNIQUE | "daily-pipeline" |
| cron_expression | text | standard 5-field, UTC e.g. "20 6 * * *" |
| pipeline_variant | text | `current` / `mega` |
| enabled | bool | |
| last_fired_at | timestamptz | |
| updated_at | timestamptz | |

Seed: 1 row, expression "20 6 * * *", variant "current", enabled true.
Will use `pg_cron` to call a SQL function that POSTs to GitHub
`/repos/.../dispatches`. When admin edits the schedule, the function
drops+recreates the matching pg_cron job.

### `redesign_stories` — ALTER

Add `archived` BOOLEAN DEFAULT false. Lets admins soft-delete bad
stories without losing audit trail. Bundle generation skips
`archived=true` rows.

## Pipeline changes

### `pipeline/full_round.py`
- Add `_load_categories()` that fetches `redesign_categories` rows.
- Replace hardcoded `("News", news_sources())` etc. with iteration over
  the loaded categories. Source mapping by category slug.

### `pipeline/news_rss_core.py`
- Add `_select_provider(role)` that fetches from `redesign_ai_providers`.
- Refactor `deepseek_call` / `deepseek_reasoner_call` to accept the
  provider config (URL, model, key env var name) instead of hardcoded
  `DEEPSEEK_API_*` constants. Provider config injected per call site.

### `pipeline/pack_and_upload.py`
- Filter out `archived=true` stories during bundle build.

## Admin page (`website/admin.html`)

Standalone React + Babel-standalone (matches existing pattern). Single
file, ~600 lines. Sections:

- **Auth gate**: on load, check Supabase Auth session. If signed in,
  query `redesign_admin_users` for the email. If matched, render admin.
  If not signed in or not whitelisted, show "Sign in with Google" button.
- **Tab nav** (8 tabs): Sources / Categories / AI Providers / Admin
  Users / Stories / Feedback / Runs / Pipeline.
- **Each CRUD tab**: list + add form + edit/delete actions per row.
  Confirmations on delete.
- **Stories**: filter by date + category. Archive button per story.
- **Feedback**: read-only list, with optional "respond" placeholder
  (for the user-feedback-loop flow already wired to `feedback-rewrite`
  edge function).
- **Runs**: tail of `redesign_runs`, telemetry expanded inline.
- **Pipeline**:
  - "Trigger now" button (POSTs `workflow_dispatch` to GH API; uses
    a PAT stored in `redesign_admin_users.github_dispatch_token` for
    the calling admin — or a single shared secret stored in Vault).
  - Cron schedule editor (writes to `redesign_cron_config`; pg_cron
    job rebuilds itself via trigger).
  - Variant picker (current / mega).

## Google SSO

Frontend uses `@supabase/supabase-js`'s `signInWithOAuth({ provider: 'google' })`.

User-side setup (one-time):
1. In Supabase dashboard → Authentication → Providers → Google → enable.
2. Create OAuth client in Google Cloud Console; redirect URI from
   Supabase. Paste client ID + secret.
3. Confirm `redesign_admin_users` has the user's email seeded.

After that, every visit to `/admin` checks the session, validates the
email against the whitelist, and grants access.

## DB-driven schedule (GH Actions polling pattern)

To avoid pg_cron + Vault setup, the workflow polls the DB:

1. `.github/workflows/daily-pipeline.yml` cron set to fire every 30 min.
2. New first step reads `redesign_cron_config`, derives the intended
   "next-fire" time. If `now` is NOT within ±15 min of the intended
   time, exit 0 immediately (no-op). Else proceed with the run.
3. Admin edits `cron_expression` from the UI → effective on the next
   30-min poll.

Trade-off: up to 30-min jitter on actual fire vs. configured time.
Acceptable for a daily news site. pg_cron upgrade left as a follow-up.

## Routing — `/admin` vs `/admin.html`

Default Vercel behavior serves `/admin.html` directly. To get clean
`/admin` URL, add `vercel.json` rewrite in kidsnews-v2:
```json
{ "rewrites": [ { "source": "/admin", "destination": "/admin.html" } ] }
```

I'll add this to the news-v2 bundle so it ships with the next sync.

## Bootstrap order

1. Apply schema migrations (tables, alters, seeds).
2. Add the cleanup-v1 inventory note pointing here.
3. Build admin.html with Google SSO + 8 tabs.
4. Wire pipeline to read from new tables (categories, providers).
5. Wire pack_and_upload to skip `archived=true`.
6. Set up pg_cron + GitHub-dispatch SQL function.
7. Add Vercel rewrite + commit / push.
8. User runs through the SSO flow once on the live site after deploy.

## Risks / things to validate after deploy

- Google OAuth redirect must include the production hostname
  (`news.6ray.com`) AND localhost for testing.
- RLS policies must allow signed-in admins to write all the
  `redesign_*` tables they manage. Wrong policy = silent insert
  failure.
- pg_cron jobs use GMT — schedule expressions must be in UTC.
- Bundle doesn't include `archived=true` stories, but the
  `redesign_stories` rows stay in DB (for audit). Confirm
  `pack_and_upload` filter is applied at all 3 read sites.
