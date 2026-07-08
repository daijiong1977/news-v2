-- Security: enable Row Level Security on the 6 RLS-disabled tables that carry
-- NO anon-client access, closing the `rls_disabled` advisor for them with zero
-- website impact. See docs/bugs/2026-07-07-rls-disabled-advisory.md.
--
-- Why these are safe with RLS on and NO policy (= anon/authenticated get zero
-- access; the service role, which the pipeline + edge functions use, bypasses
-- RLS and is unaffected):
--   * engine_prompts / engine_subbuckets / engine_source_daily_stats /
--     engine_source_candidates — sourcefinder engine internals; written only by
--     the pipeline/sourcefinder via SUPABASE_SERVICE_KEY (service role).
--   * redesign_source_candidates — passive audit/seed store; service role only.
--   * redesign_search_index — read ONLY by the archive-search edge function,
--     which uses SUPABASE_SERVICE_ROLE_KEY; the reader site never queries it
--     directly (it hits the edge function). Search is unaffected.
--
-- NOT included (deferred): engine_config, engine_source_reports,
-- engine_mining_runs — these ARE read by website/admin.html (authenticated
-- Google-SSO session), so they need an admins-only SELECT policy first. See the
-- proposed policy in the bug record; do not enable RLS on them without it.

ALTER TABLE public.engine_prompts             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engine_subbuckets          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engine_source_daily_stats  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engine_source_candidates   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.redesign_source_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.redesign_search_index      ENABLE ROW LEVEL SECURITY;
