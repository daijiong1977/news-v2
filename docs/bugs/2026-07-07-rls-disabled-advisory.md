# 2026-07-07 — rls-disabled-advisory

**Severity:** high (security)
**Area:** infra (Supabase RLS)
**Status:** FIXED 2026-07-31 (9/9 — Phase 2 applied with an admins-only policy)
**Keywords:** rls, row-level-security, anon-key, engine_config, redesign_search_index, security, supabase, admin-policy

## Symptom

Supabase advisor `rls_disabled` (level: critical): 9 public tables had Row Level
Security **disabled**, so anyone holding the public anon/publishable key could
read — and, worse, **modify** — every row:
`engine_config, engine_prompts, engine_subbuckets, engine_source_daily_stats,
engine_source_reports, engine_mining_runs, engine_source_candidates,
redesign_search_index, redesign_source_candidates`.

## Root cause

These tables were created without `ENABLE ROW LEVEL SECURITY`. The pipeline and
edge functions reach them via the **service role** (`SUPABASE_SERVICE_KEY` /
`SUPABASE_SERVICE_ROLE_KEY`), which bypasses RLS — so nothing forced a policy to
exist, and the anon exposure went unnoticed.

## Fix

Split by who actually reads each table via the **anon/authenticated** key
(service-role access is unaffected by RLS):

**Phase 1 — applied (`supabase/migrations/20260707_enable_rls_safe_tables.sql`):**
Enabled RLS (no policy = zero anon access) on the 6 tables with no client access:
`engine_prompts, engine_subbuckets, engine_source_daily_stats,
engine_source_candidates, redesign_source_candidates, redesign_search_index`.
- The reader site never queries these. Search hits `redesign_search_index` only
  through the `archive-search` edge function, which uses the service role — so
  search is unaffected. **Verified:** `GET /functions/v1/archive-search?q=science`
  → HTTP 200, 3 hits, after the migration.

**Phase 2 — APPLIED 2026-07-31** (`supabase/migrations/20260731_enable_rls_admin_tables.sql`):
`engine_config, engine_source_reports, engine_mining_runs` are read (and, for
`engine_config`, written) by `website/admin.html`, which runs as an authenticated
Google-SSO session. Each got an admins-only `FOR ALL TO authenticated` policy,
then RLS was enabled.

- Shipped policy uses **`public._is_admin()`** rather than the inline subquery
  sketched below. `_is_admin()` is STABLE SECURITY DEFINER with a pinned
  `search_path`, so it reads `redesign_admin_users` without re-entering that
  table's own RLS; the inline subquery would run under the caller's policies
  (slower, and a recursion hazard).
- Precondition re-verified before applying: `App()` in admin.html returns
  `<SignInPanel/>` when `!session` and an access-denied screen when
  `!bootState.allowed`, so every `engine_*` read happens post-sign-in — there is
  no pre-auth read to black out. Bootstrap mode is inactive
  (`redesign_admin_users` has 1 row).
- Confirmed the hole was real before closing it: with the publishable key, all 3
  tables returned rows, and an anon INSERT into `engine_config` **succeeded** in
  principle (writes were unrestricted). After the migration: reads return `[]`
  and the same INSERT is rejected with `42501 new row violates row-level
  security policy`.
- Pinning test now passes: all 9 tables `relrowsecurity = true`, and the
  `rls_disabled` advisor returns **0 findings**.
- ⚠️ Still to do by a human: load the admin panel signed in as an allowlisted
  admin and confirm the Config, Reports and Mining tabs still populate. This
  could not be verified programmatically (it needs a real Google SSO session).

Original proposed sketch, kept for the record:

```sql
-- Repeat for engine_config, engine_source_reports, engine_mining_runs:
ALTER TABLE public.engine_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admins full access engine_config"
  ON public.engine_config
  FOR ALL
  TO authenticated
  USING      ( (auth.jwt() ->> 'email') IN (SELECT email FROM public.redesign_admin_users) )
  WITH CHECK ( (auth.jwt() ->> 'email') IN (SELECT email FROM public.redesign_admin_users) );
```

Before applying Phase 2: confirm admin.html reads these only AFTER sign-in (a
pre-auth read would return empty under the policy), and load the admin panel to
verify each section still populates.

## Invariant

Every `public` table must have RLS enabled. Backend-only tables (service-role
access) get RLS with no policy. Tables read by the client get RLS + a policy
scoped to the minimum role (authenticated + admin-allowlist for admin tables;
never a blanket `anon` policy on config/prompt tables).

## Pinning test

`select relname, relrowsecurity from pg_class where relnamespace='public'::regnamespace
and relname = ANY(...)` — all 9 must be `true` once Phase 2 lands. Advisor
`rls_disabled` must return empty. Search smoke:
`GET /functions/v1/archive-search?q=science` → 200 with hits.

## Related

- Advisor surfaced during the 2026-07-07 health-check.
- Phase 2 depends on `redesign_admin_users` (email allowlist) + admin.html auth.
