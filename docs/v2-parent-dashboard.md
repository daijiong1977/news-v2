# v2 Parent Dashboard — Design

**Status.** Live at `kidsnews.21mins.com/parent.html` since 2026-04-26.

**Goal.** Let parents see what their kid is reading on kidsnews — recent articles,
quiz performance, written discussion drafts, reactions — without forcing them to
sign up for anything. Optional Google sign-in unlocks cross-device history +
weekly/daily email digest.

---

## Architecture at a glance

```
                   ┌─────────────────── kid device ───────────────────┐
                   │                                                  │
                   │ index.html → home.jsx ─┬─→ article.jsx           │
                   │                        │                         │
                   │                        ▼                         │
                   │  KidStats helper (article.jsx)                   │
                   │     localStorage:                                │
                   │        ohye_quiz_log_v1                          │
                   │        ohye_reactions_v1                         │
                   │        ohye_article_time_v1                      │
                   │        ohye_response_*  (discussion drafts)      │
                   │        ohye_progress / ohye_tweaks               │
                   │                        │                         │
                   │  kidsync.js  ──── fire-and-forget ──┐            │
                   │     window.kidsync.{                │            │
                   │       upsertKidProfile,             ▼            │
                   │       recordReadingEvent,    Supabase RPCs       │
                   │       recordQuizAttempt,     (anon, security     │
                   │       recordArticleReaction,  definer)            │
                   │       upsertDiscussion,                          │
                   │       generatePairingCode  }                     │
                   └──────────────────────────────────────────────────┘
                                              │
                                              ▼
                            ┌─────────── Supabase ────────────┐
                            │  redesign_kid_profiles          │
                            │  redesign_reading_events        │
                            │  redesign_quiz_attempts         │
                            │  redesign_article_reactions     │
                            │  redesign_discussion_responses  │
                            │  redesign_parent_users          │
                            │  redesign_kid_pairing_codes     │
                            │                                  │
                            │  RLS: parents see only their own │
                            │  kids' rows (via _parent_user_id │
                            │  helper + SECURITY DEFINER fns). │
                            └─────────────────────────────────┘
                                              │
                                              ▼
                            ┌──── parent.html (Google sign-in) ────┐
                            │  Local-mode: read kid's localStorage │
                            │     on this device (no auth).        │
                            │  Cloud-mode: query Supabase (RLS-    │
                            │     gated) for the selected kid.     │
                            │  Source toggle = "📱 This device"    │
                            │     vs. "☁️ Cloud · <kid>".          │
                            │                                      │
                            │  Email digest:                       │
                            │    daily-pipeline @ 10am UTC ─→      │
                            │    send-digest edge fn ─→            │
                            │    send-email-v2 (Gmail SMTP)        │
                            └──────────────────────────────────────┘
```

---

## Two modes

### Local (default — no setup)

Parent opens `kidsnews.21mins.com/parent.html` on the kid's device. Dashboard
reads `localStorage` directly: `ohye_progress`, `ohye_tweaks`,
`ohye_quiz_log_v1`, `ohye_reactions_v1`, `ohye_article_time_v1`, and the
`ohye_response_*` keys for discussion drafts. No accounts, no DB calls.
Everything is computed in-browser by `collectStats()` in `parent.jsx`.

Limit: only data from THIS device. If parent uses multiple devices, each
shows its own slice.

### Cloud (Google sign-in)

Parent clicks "Sign in with Google". `useAuth` subscribes to Supabase Auth.
On first session, `useKids.refresh()`:

1. Calls `upsert_parent_self()` RPC — creates the `redesign_parent_users` row
   if missing, otherwise stamps `last_login_at`.
2. Reads `ohye_client_id` from localStorage. If present, calls
   `claim_kid_for_caller(p_client_id)` to link THIS device's kid to the
   parent (same-device auto-claim).
3. SELECTs the parent's `redesign_kid_profiles` rows (RLS-gated to their
   own kids) — populates the kid switcher chips.

After auth, the source toggle defaults to "☁️ Cloud" and the dashboard
queries `cloudCollectStats(client_id, dayFilter)` which fetches:

- `redesign_reading_events`        (events log for time/step computation)
- `redesign_quiz_attempts`         (per-attempt picks + correct/total)
- `redesign_article_reactions`     (one reaction per kid+story+level)
- `redesign_discussion_responses`  (rounds JSON + saved_final)
- `redesign_kid_profiles`          (the selected kid's identity)

Cross-device pairing for parents on a different device than the kid:
parent clicks "Add a kid by code: [______] Link" → calls
`consume_pairing_code(p_code)`. The code is generated on the kid's
device by tapping "Pair with parent on another device" in user-panel
(generates via `generate_pairing_code(client_id)`, 10-min TTL,
single-use, displayed with a live countdown).

---

## Email digest

User-toggleable cadence: `off | daily | weekly`, persisted as
`redesign_parent_users.digest_cadence` via the `set_digest_cadence(text)`
RPC. The dashboard's `DigestCadenceToggle` component writes this.

**Cron path.** `.github/workflows/parent-digest.yml` runs daily at 10:00
UTC, POSTs to the `send-digest` edge function. The function:

1. SELECTs parents with `digest_cadence != 'off'`.
2. Filters to those due (no `digest_last_sent_at`, or older than the cadence
   window minus 1h tolerance).
3. For each due parent: gathers their kids' `redesign_*` rows for the
   cadence window (1d / 7d), builds an HTML email with per-kid sections
   (minutes read, articles finished, quiz averages, recent finishes,
   recent quiz misses, saved discussion answers).
4. POSTs to the existing `send-email-v2` edge function (Gmail SMTP via
   denomailer; uses `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` from
   `public.secrets`).
5. Stamps `digest_last_sent_at` on success.

**On-demand path.** The "📤 Email me the full report" button in the
dashboard builds a self-contained digest in-browser from the currently-
viewed `stats` (local OR cloud, whichever the source toggle is showing)
and POSTs directly to `send-email-v2`. Mirrors the dashboard's full
content so the parent reads it without clicking back.

`send-digest` env vars:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — provided by the platform.
- `PARENT_DASHBOARD_URL` — defaults to `https://kidsnews.21mins.com/parent.html`.

`send-email-v2` env / secrets:
- Reads `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` from `public.secrets` via
  `get_secret(secret_name)` SECURITY DEFINER RPC.

---

## Schema (full migration: `supabase/migrations/20260425_parent_dashboard.sql`)

| Table | Key columns | Notes |
|---|---|---|
| `redesign_parent_users` | id, email (unique), name, digest_cadence, digest_last_sent_at, last_login_at | one row per Google account; never an unauthenticated parent |
| `redesign_kid_profiles` | client_id (PK = ohye_client_id), parent_user_id, display_name, avatar, level, language, theme, daily_goal | parent_user_id NULL until claim/consume RPC links |
| `redesign_reading_events` | bigserial, client_id, story_id, category, level, language, step, minutes_added, duration_ms, occurred_at, day_key | append-only; powers daily/weekly aggregation |
| `redesign_quiz_attempts` | bigserial, client_id, story_id, level, picks (jsonb), correct, total, duration_ms, attempted_at, day_key | one row per quiz finish; replays show retry pattern |
| `redesign_article_reactions` | (client_id, story_id, level) PK, reaction enum, reacted_at | upsert, one reaction per article-level |
| `redesign_discussion_responses` | bigserial, (client_id, story_id, level) UNIQUE, rounds (jsonb), saved_final, updated_at | mirrors localStorage `ohye_response_*` |
| `redesign_kid_pairing_codes` | code (PK, 6-digit), client_id, expires_at, consumed_at, consumer_email | 10-min TTL; single-use |

**RLS.** Anon can SELECT nothing. Authenticated parents SELECT only rows
linked to their own `parent_user_id` (via `_parent_user_id()` helper).
All writes from kid clients go through SECURITY DEFINER RPCs so we
never grant table-level INSERT to anon.

**RPCs:**
- Anon (kid side): `upsert_kid_profile`, `record_reading_event`,
  `record_quiz_attempt`, `record_article_reaction`,
  `upsert_discussion_response`, `generate_pairing_code`.
- Auth (parent side): `upsert_parent_self`, `claim_kid_for_caller`,
  `consume_pairing_code`, `unlink_kid`, `set_digest_cadence`.
- Helpers: `_parent_user_id()` (SECURITY DEFINER, used by RLS policies).

---

## Files added/changed

| File | Role |
|---|---|
| `website/parent.html` | dashboard chrome (loads React, Supabase JS, data.jsx, parent.jsx) |
| `website/parent.jsx` | dashboard logic — `collectStats`, `cloudCollectStats`, `useAuth`, `useKids`, `Dashboard`, `CloudBanner`, `DigestCadenceToggle`, `PairingCodeInput`, `buildDigestHtml` |
| `website/kidsync.js` | vanilla-JS bridge — lazy Supabase client + `window.kidsync.*` methods, fire-and-forget |
| `website/article.jsx` | `KidStats` helpers; `bumpStep` mirrors via `kidsync.recordReadingEvent`; QuizTab persists attempts; DiscussTab adds reaction picker |
| `website/user-panel.jsx` | "Parent / teacher → Parent dashboard" link + `PairingExpander` for cross-device flow |
| `website/index.html` | loads `kidsync.js`; mirrors tweaks via `kidsync.upsertKidProfile`; passes `updateTweak` to ArticlePage |
| `supabase/migrations/20260425_parent_dashboard.sql` | full schema + RPCs + RLS |
| `supabase/functions/send-digest/index.ts` | edge function — aggregates per-parent + sends via `send-email-v2` |
| `.github/workflows/parent-digest.yml` | daily 10:00 UTC cron POST |

---

## Pipeline / deploy chain (for context, not parent-dashboard-specific)

The kid app + parent dashboard ship as static assets through a two-repo chain:

```
news-v2 repo  →  pipeline.full_round  →  pack_and_upload
                                              │
                                              ▼
                                  Supabase Storage:
                                    redesign-daily-content/latest.zip
                                              │
                                              ▼ repository_dispatch (PAT)
                                  kidsnews-v2 repo
                                  sync-from-supabase.yml:
                                    download zip → unzip → commit → push
                                              │
                                              ▼
                                  Vercel auto-deploy → kidsnews.21mins.com
```

Two modes for `pack_and_upload`:
- **Full pipeline** — INCLUDE_FILES (shell) + INCLUDE_DIRS (content) all from
  the news-v2 git checkout. Validates today's bundle. Used by `daily-pipeline.yml`.
- **Republish** (`PACK_REPUBLISH_ONLY=1`) — SHELL from git checkout,
  CONTENT extracted from the existing `latest.zip` on Supabase. Used by
  `republish-bundle.yml`. Lets you ship dashboard/JSX changes without
  burning LLM credits AND without clobbering today's mined articles.
- **Restore** (`PACK_RESTORE_FROM_DATE=YYYY-MM-DD`) — copy `<date>.zip` →
  `latest.zip`. One-shot recovery if a botched republish leaves
  latest.zip pointing at stale content.

Both `daily-pipeline.yml` and `republish-bundle.yml` end with a
**verify-sync** step: stamp dispatch timestamp, then poll kidsnews-v2's
latest commit for one authored AFTER dispatch by the sync bot. Fails
the workflow if no fresh sync commit lands within 90s. This catches
silent failures (PAT scope drift, no-content-change skip, sync-workflow
errors) at deploy time instead of letting kidsnews.21mins.com serve
stale articles unnoticed.

---

## Open follow-ups

- **Article-content dedup** against the last 7 days of `redesign_stories`
  by `source_url` — currently science/fun categories repeat yesterday's
  stories when the source RSS still serves them. News doesn't repeat
  because the high-volume feeds cycle out fast.
- **Python keyword backfill** — when LLM keyword output is empty (or all
  filtered by the body-match scrub), call `keyword_extractor.extract_keywords`
  in `pack_and_upload` to inject deterministic body-grounded vocab so
  readers always see something highlighted.
- **Apple SSO / magic-link fallback** — parents without Gmail accounts
  are currently locked out of cloud mode. Defer until a real user asks.
- **Multi-kid summary view** — current cloud-mode shows ONE kid at a time
  (kid switcher). Add an "All kids" overview for families.
- **`kidsnews-v2` retirement** — the two-repo deploy chain (Supabase zip
  → kidsnews-v2 sync) made sense when kidsnews-v2 was a thin static
  shell. If we collapse to a single Vercel project with news-v2's
  `website/` as root, every deploy step disappears (no PAT, no sync
  workflow, no verify step needed).
