# Admin cross-check — 2026-04-25

Reviewed against `docs/v2-admin-plan.md`, `docs/v2-admin-setup.md`, `website/admin.html`, `.github/workflows/daily-pipeline.yml`, and `pipeline/pack_and_upload.py` at commit `561fb57`.

> Note: the actual `v2_admin_schema` / `v2_admin_rls` SQL files are **not** in this repo, so policy findings below are based on the documented migration design plus Supabase/Postgres RLS semantics.

## Findings

### [high] Scheduled “skip” currently fails the workflow

In `.github/workflows/daily-pipeline.yml:67-84`, the cron-check step uses `sys.exit(78)` for “neutral skip.” In a normal GitHub Actions `run:` step, any nonzero exit code is a **failure**, not a skip/neutral result. That means most 30-minute polls will show as red failed runs, and later default `if: success()` steps will be skipped for the wrong reason. `if: always()` steps still run.

### [high] Bootstrap path intentionally allows anonymous first-admin insert

`website/admin.html:150-157` inserts into `redesign_admin_users` from the browser with the publishable key, and the wizard is shown whenever `adminCount === 0` (`admin.html:827-833`). If the documented `admin_users_insert_bootstrap_or_admin` policy is implemented as “table empty OR `_is_admin()`,” then an unauthenticated caller **is allowed** to insert while the table is empty. That matches the intended bootstrap UX, but it means whoever reaches `/admin` first can claim the first admin row.

### [medium] Bootstrap race can create two admins

`App.recheck()` (`admin.html:804-817`) and the wizard render are client-side only; there is no server-side serialization. Two visitors who both observe `count = 0` can both submit different emails before either insert becomes visible to the other transaction, producing two admins. This is probably acceptable for a single-operator site, but it is real.

### [medium] `redesign_admin_users` SELECT policy likely leaks admin emails

The brief says the SELECT policy is `USING (true)` so anon callers can do the bootstrap count. That also makes the whole table readable to any visitor who can hit the Supabase REST endpoint with the embedded publishable key. The count query in `admin.html:805` only needs row visibility, not public disclosure of admin emails. If this is acceptable, document it explicitly; otherwise prefer a count-only RPC/view for bootstrap detection.

### [medium] Invalid cron text will break scheduled runs until fixed

The Pipeline tab saves `cron_expression` as free text (`admin.html:703-705`, `683-690`). The workflow then passes it straight to `croniter(expr, now)` (`daily-pipeline.yml:74-81`) with no `try/except`. An invalid expression will raise and fail every scheduled run until someone corrects the row. Client-side validation is worth adding.

### [low] `parseInt(e.target.value || 0)` can send `NaN`

This pattern appears in Sources and AI Providers (`admin.html:267,290,437,458`). For pasted junk like `"abc"`, `parseInt("abc" || 0)` yields `NaN`. Supabase will surface a DB error if the target column is non-nullable; otherwise JSON serialization turns `NaN` into `null`. This is not silent in the strict-schema case, but the input handling is still brittle.

### [low] Sources tab category mismatch is not a current production risk

The add-source UI uses a `<select>` populated from `redesign_categories.name` (`admin.html:258-262`), so normal entry stays case-consistent. More importantly, this repo’s pipeline still treats Python source lists as canonical: `pipeline/seed_source_configs.py:1-6` says DB source configs are only seeded for now. So a bad `category` value in `redesign_source_configs` does not currently drive bundle generation.

## Confirmations

### [info] Recheck auto-elevates a user who already signed in during bootstrap

After first-admin insert, `onDone` calls `recheck()` (`admin.html:157`, `832`). If the user already has a Google session, `recheck()` looks up `session.user.email` in `redesign_admin_users` (`admin.html:807-813`) and immediately flips `allowed` true. No second sign-in is needed.

### [info] `_is_admin()` as `STABLE SECURITY DEFINER` is the right shape

Given the described design, `SECURITY DEFINER` is the correct way to avoid recursive RLS evaluation when policies query `redesign_admin_users` itself. Service-role pipeline writes also still bypass RLS by design, so existing `redesign_stories` upserts should not be blocked by admin-only policies.

### [info] Cron boundary logic includes the ±15 minute edge

For a configured cron like `15 6 * * *`, the current `delta > 15 * 60` test correctly allows the 06:00 and 06:30 polls, and also exact 06:15. The boundary behavior is fine; the problem is the nonzero “skip” exit code.

### [info] Story restore should return on the next bundle build

`StoriesTab` toggles `archived` directly (`admin.html:546-549`). `pack_and_upload.py` now ships `admin.html`, and the review brief says bundle generation skips `archived=true` stories. Restoring a story should therefore make it eligible again on the next pipeline run, not instantly on the current live bundle.

### [info] Static serving smoke check passed

`python3 -m http.server 18101` served `http://localhost:18101/admin.html` with HTTP 200. I did not run a browser-based console inspection or real OAuth flow.
