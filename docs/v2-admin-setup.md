# v2 Admin — One-Time Setup Steps

The code shipped tonight covers schema + admin page + workflow polling.
A few things still need a click in a dashboard before the page works
end-to-end.

## 1. Supabase — enable Google OAuth provider

Required for the SSO step once any admin row exists.

1. Open your Supabase project → **Authentication** → **Providers** → **Google**
2. Toggle **Enabled**.
3. Create OAuth credentials in Google Cloud:
   - **Console** → **APIs & Services** → **Credentials** → **Create OAuth client ID**
   - Application type: **Web application**
   - Authorized redirect URI: copy from the Supabase Google panel (looks like
     `https://lfknsvavhiqrsasdfyrs.supabase.co/auth/v1/callback`).
   - **Authorized JavaScript origins**: add `https://news.6ray.com`
     (and `http://localhost:18100` if you want local testing).
4. Paste the **Client ID** and **Client Secret** back into the Supabase Google
   provider panel and **Save**.

Test by visiting `https://news.6ray.com/admin` — first load should show the
Bootstrap Wizard (no admins). If you don't see "Sign in with Google" button
working when you have admins, this step is the cause.

## 2. First admin (Bootstrap)

Once OAuth is wired:

1. Visit `https://news.6ray.com/admin` — the page opens un-gated because
   `redesign_admin_users` is empty.
2. **Optional:** click **Sign in with Google** so the wizard auto-fills your
   email. Otherwise type it in.
3. Click **Make me admin**. The row inserts via the RLS bootstrap policy.
4. Reload — the page now requires SSO. Sign in. You're in.

From then on, `/admin` always requires Google SSO and only emails on the
list can access. You can add more admins from the **👥 Admins** tab.

## 3. Cron schedule editing

Schedule lives in `redesign_cron_config` (one row, name `daily-pipeline`).
Edit on the **🔧 Pipeline** tab.

Mechanics:
- The GitHub Actions workflow polls every 30 minutes.
- On each poll it reads the row, calculates the closest cron-expression
  fire time, and proceeds only if `now` is within ±15 min.
- This means changes take effect on the next 30-min poll boundary.

Cron field: standard 5-field format, **UTC**. Examples:
- `20 6 * * *`  → 06:20 UTC daily (current default)
- `0 14 * * *`  → 14:00 UTC daily
- `0 6 * * 1-5` → 06:00 UTC weekdays

## 4. AI provider rotation (PHASED)

The **🤖 AI Providers** tab is wired for CRUD on the `redesign_ai_providers`
table. **Pipeline-side reading from this table is the next phase** — for now
the code in `pipeline/news_rss_core.py` still uses hardcoded DeepSeek
constants. UI changes are tracked but not yet honored. Phase 2 of this admin
project will refactor `deepseek_*_call()` to look up the active provider per
role from `redesign_ai_providers`.

(Same caveat applies to the **🏷️ Categories** tab — pipeline still uses
hardcoded News/Science/Fun. Phase 2 will rewire that lookup.)

## 5. Story archive — current scope

Archive on the **📰 Stories** tab flips `redesign_stories.archived = true`.
This is captured in DB immediately. Effect on the live site:

- **Today's content** (currently in `latest.zip`): the archived flag has
  **no immediate effect** — the bundle was assembled before the archive.
  To remove the bad story from the live site right now, manually trigger
  a fresh pipeline run from the **🔧 Pipeline** tab info area
  (`gh workflow run …`).
- **Tomorrow's run**: the next pipeline cycle generates fresh content and
  doesn't include yesterday's stories anyway, so archived rows naturally
  disappear from the live site.

A future enhancement (instant archive → instant live-site removal without
a full re-run) is the right next step but is outside tonight's scope.

## 6. Cleaning up

Once you're sure the admin works end-to-end, the v1 KidsNews decommission
checklist in `docs/cleanup-v1-inventory.md` becomes safe to execute.
