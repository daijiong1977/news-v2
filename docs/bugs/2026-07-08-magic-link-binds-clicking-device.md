# 2026-07-08 — magic-link-binds-clicking-device

**Severity:** high
**Area:** website + edge-fn (auth / magic-link)
**Status:** fixed (core); several UX/security follow-ups documented
**Keywords:** magic-link, issue_magic_link, consume_magic_link, client_id, cross-device, binding, requester, kidsync, sign-in, streak, onboarding

## Symptom

The owner: "the login email process still feels wrong but I cannot identify."
A cross-device code + data review pinned it: the magic link bound the email
to the device that **clicked** the link, not the device that **requested**
it (and holds the reading history).

Everyday household path — type email on the **laptop** (where the streak
lives), open the email on the **phone**, tap the link — the phone is a fresh,
empty browser with a different `ohye_client_id`, so `consume_magic_link`
bound the email to the phone's empty id and stranded the laptop's
profile/streak. The phone landed back on OnboardingScreen with no error
(mimicking the already-"fixed" 2026-05-03 flash bug). Intermittent (only the
first bind per email), silent, and impossible to reproduce in the dev loop
(request + click in the same browser) — exactly a "wrongness you feel but
can't catch."

## Root cause

`issue_magic_link(p_email)` never recorded WHICH device requested the link.
So `consume_magic_link` had nothing to bind a never-seen email to except
`p_local_client_id` — the clicking device
(`supabase/migrations/20260426_email_magic_link.sql:120-126`,
`website/kidsync.js:371`). The 2026-05-03 flash-gate comment claimed the
pre-upload closed this race; it doesn't — `fetchProfile` on the clicking
device queries the clicking cid, never the requester's.

## Fix

PR: fix/login-magic-link-binding.

- `supabase/migrations/20260708_magic_link_bind_requester.sql` — add a
  `client_id` column to `redesign_email_magic_links`; `issue_magic_link`
  gains `p_client_id uuid default null` and stores the requester's id on the
  token; `consume_magic_link` binds a never-seen email to
  `coalesce(requester, clicking)` — i.e. the requesting device when known.
  The `default null` + `coalesce` keep an old cached client (mid-deploy)
  working with the previous behavior. **Applied to prod and verified live:**
  issue as device A → consume as device B → email binds to **A** (the
  history device), consume returns A, B adopts it. Test rows cleaned up.
- `website/kidsync.js` — `requestMagicLink` passes `p_client_id: clientId()`.
- `website/index.html` — strip `?magic=` from the URL BEFORE awaiting the
  consume RPC (was in a `finally` after), so a refresh mid-consume can't
  re-attempt an already-spent single-use token and lose the sign-in; hash
  preserved (finding 8).

## Invariant

A magic link binds an email to the device that REQUESTED it (recorded on the
token), not the device that clicks it. `issue_magic_link` must always be
called with the requesting device's `client_id`, and `consume_magic_link`
must prefer the token's stored `client_id` over the clicking device's.

## Pinning test

Live RPC test (run 2026-07-08): `issue_magic_link(email, A)` →
`consume_magic_link(token, B)` returns A and
`redesign_kid_email_links.client_id = A`. Re-runnable with any two distinct
UUIDs; delete the test email's rows after.

## Related / deferred (from the same review, NOT in this PR)

- **[HIGH security] Token returned to any anon caller + `send-email-v2` open
  relay** — `issue_magic_link` hands the raw token to the browser, and
  `send-email-v2` runs `verify_jwt=false`, so anyone can mint+consume a link
  for any email without inbox access, and send mail from the domain. Fix:
  move token generation + send into ONE edge function that never returns the
  token. (Owner is reviewing the Supabase edge functions — address there.)
- [MED] onboarding "link sent ✓" is unreachable (persistProfile unmounts the
  screen mid-send); permanent 3s `waitForSession` wait for magic/anon users;
  error/success have no App-level toast; sign-out doesn't mint a fresh cid;
  no cloud-history re-parenting on identity swap; non-UUID cids throw a raw
  cast error; no resend cooldown. See the review notes.
- `docs/bugs/2026-05-03-magic-link-onboarding-flash.md` — the flash-gate that
  masked this.
