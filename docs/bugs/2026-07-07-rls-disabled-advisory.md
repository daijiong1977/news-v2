# 2026-07-07 — rls-disabled-advisory

**Severity:** high (security)
**Area:** infra (Supabase RLS)
**Status:** partially fixed (6/9 done; 3 admin tables have a proposed policy)
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

**Phase 2 — proposed, NOT yet applied:** `engine_config, engine_source_reports,
engine_mining_runs` are read (and, for `engine_config`, likely written) by
`website/admin.html`, which runs as an authenticated Google-SSO session. They
need an admins-only policy before RLS is turned on, or the admin panel breaks:

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
