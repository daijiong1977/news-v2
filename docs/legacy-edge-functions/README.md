# Legacy edge-function archive (2026-07-08)

These are verbatim source backups of **v1 (old-version) Supabase edge functions
that were DELETED** from project `lfknsvavhiqrsasdfyrs` on 2026-07-08, to reduce
the public attack surface (all were `verify_jwt=false`).

Why they were safe to delete:
- The v1 schema they operated on is gone (`public.articles` no longer exists).
- Zero references from any current code (news-v2 / kidsnews-v2) — confirmed by grep.
- The v1 site is retired; the live site (kidsnews.21mins.com) runs on v2.

Notably removed: `cleanup-old-data` (an unauthenticated, service-role data-wipe
endpoint — `retention_days:0` would have deleted every article) and `send-email`
(v1, superseded by `send-email-v2`).

KEPT (non-public, `verify_jwt=true`, may be reused by other projects): bootstrap,
bootstrap-legacy, auth-register, ai-key, storage-api, test-auth. `health` also kept.

To restore any of these: `supabase functions deploy <slug>` with the archived source.
