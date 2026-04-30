# 2026-04-30 — supabase-edge-fn-html-blocked

**Severity:** medium
**Area:** infra
**Status:** worked-around
**Keywords:** supabase, edge-function, content-type, csp, sandbox, nosniff, html, browser-rendering

## Symptom

Built a Supabase Edge Function (`autofix-review`) that returns
HTML — verified locally rendering, set
`Content-Type: text/html; charset=utf-8`, added `<meta charset>`,
double-checked UTF-8 bytes via curl. But every browser (Chrome,
Safari, both with and without cache) rendered the response as
plain text — HTML markup visible as visible characters, no styling
applied, all emoji shown as latin-1 garbage.

## Root cause

Supabase Edge Functions inject three response headers automatically
that override anything the function sets:

```
content-type: text/plain
content-security-policy: default-src 'none'; sandbox
x-content-type-options: nosniff
```

This is an **anti-phishing default** baked into Supabase's edge
runtime — they don't want their domain (`*.supabase.co`) to be a
phishing host. Combined:

- `nosniff` forces browser to honor Content-Type literally → no
  HTML detection from body
- `text/plain` overrides our `text/html` → browser renders as text
- `default-src 'none'; sandbox` would block scripts/styles even if
  HTML rendered

Confirmed via `curl -D -` showing the headers despite our code
explicitly setting `Content-Type: text/html`. Tested with both
plain-object headers and `new Headers()` — both got sanitized.

JSON responses (`Content-Type: application/json`) are NOT affected
— Supabase only forces text/plain on what it considers
"presentation content."

## Fix

Move HTML rendering off Supabase Edge Functions entirely. Static
HTML page hosted on Vercel (the project's existing
`news.6ray.com` deployment) at `/autofix.html`. Page uses JS to
fetch + write `redesign_autofix_queue` via Supabase REST API with
the anon key (after adding anon SELECT + restricted anon UPDATE
RLS policies for that table).

- `website/autofix.html` — static panel
- `pipeline/pack_and_upload.py` — added autofix.html to SHELL_FILES
- `pipeline/quality_digest.py` — button URL → news.6ray.com/autofix
- Supabase migration `redesign_autofix_queue_anon_rls`

## Invariant

**Supabase Edge Functions can return JSON, redirects, plain text,
and binary blobs — but NOT browser-renderable HTML.** Any feature
that needs to render HTML to a browser MUST be hosted on a real web
host (Vercel, Netlify, GitHub Pages, etc.) where you control all
response headers. Edge functions can still serve as data APIs
(JSON) that the static HTML page consumes via fetch().

If a future change tries to revive HTML edge functions, this gotcha
returns within minutes.

## Pinning test

Curl any Supabase edge function that tries to return HTML:

```bash
curl -sI https://<ref>.supabase.co/functions/v1/<fn-name>
# If response includes:
#   content-type: text/plain
#   content-security-policy: default-src 'none'; sandbox
# …the function is hitting Supabase's anti-phishing override.
```

When that happens, do not iterate on the function — move to a
proper web host.

## Related

- `docs/bugs/2026-04-29-autofix-token-starvation.md` — same project
  (autofix subsystem), different problem.
- `docs/superpowers/specs/2026-04-29-quality-digest-email.md` —
  the original quality digest design that originally targeted edge
  functions for the panel.
