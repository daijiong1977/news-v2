-- Security: Phase 2 of the rls_disabled advisory — the last 3 public tables
-- still running with Row Level Security OFF. See
-- docs/bugs/2026-07-07-rls-disabled-advisory.md (Phase 1 = 20260707_enable_rls_safe_tables.sql).
--
-- These 3 could not go in Phase 1 because website/admin.html reads them from the
-- BROWSER with the anon/publishable key, as an authenticated Google-SSO user:
--   * engine_config          — read + written by the admin Config tab
--   * engine_source_reports  — read by the admin Reports tab
--   * engine_mining_runs     — read by the admin Mining tab
-- RLS with no policy would black out those tabs, so each gets an admins-only
-- policy instead. The pipeline/sourcefinder use SUPABASE_SERVICE_KEY (service
-- role), which bypasses RLS entirely and is unaffected either way.
--
-- Verified before applying (2026-07-31):
--   * admin.html gates on auth before rendering ANY tab: App() returns
--     <SignInPanel/> when !session and an access screen when !bootState.allowed,
--     so every engine_* read happens post-sign-in. No pre-auth read to break.
--   * redesign_admin_users currently has 1 row, so bootstrap mode (adminCount
--     === 0, which renders BootstrapWizard instead of the tabs) is not active.
--   * Anon COULD read all 3 tables before this migration (confirmed by a live
--     REST call with the publishable key). Contents were operational only —
--     tuning thresholds, run logs, source reports — no credentials, no PII.
--
-- Uses public._is_admin() rather than the inline
-- `(auth.jwt()->>'email') IN (SELECT email FROM redesign_admin_users)` sketched
-- in the bug record: _is_admin() is STABLE SECURITY DEFINER with a pinned
-- search_path, so it reads redesign_admin_users WITHOUT re-entering that table's
-- own RLS. The inline subquery would be evaluated under the caller's policies,
-- which is both slower and a recursion hazard.

ALTER TABLE public.engine_config         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engine_source_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engine_mining_runs    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "admins full access engine_config"         ON public.engine_config;
DROP POLICY IF EXISTS "admins full access engine_source_reports" ON public.engine_source_reports;
DROP POLICY IF EXISTS "admins full access engine_mining_runs"    ON public.engine_mining_runs;

CREATE POLICY "admins full access engine_config"
  ON public.engine_config          FOR ALL TO authenticated
  USING ( public._is_admin() ) WITH CHECK ( public._is_admin() );

CREATE POLICY "admins full access engine_source_reports"
  ON public.engine_source_reports  FOR ALL TO authenticated
  USING ( public._is_admin() ) WITH CHECK ( public._is_admin() );

CREATE POLICY "admins full access engine_mining_runs"
  ON public.engine_mining_runs     FOR ALL TO authenticated
  USING ( public._is_admin() ) WITH CHECK ( public._is_admin() );
