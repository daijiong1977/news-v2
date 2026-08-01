# Email security hardening — send-email-v2 open relay + magic-link token exposure

**Status:** code drafted, NOT deployed — awaiting owner review.
**Owner constraint:** the live site must not be affected. This spec's rollout
order guarantees zero downtime for login and digests.

## The two holes

1. **`send-email-v2` is an open relay.** `verify_jwt=false`, no secret check.
   Anyone can POST `{to_email, subject, html, from_name}` and send arbitrary
   mail from the project's Gmail, with a spoofable sender display name →
   phishing/spam from your domain, Gmail suspension, reputation loss.
2. **Magic-link token handed to the browser.** `kidsync.js` called
   `issue_magic_link` and got the raw token client-side, then emailed it via
   the open relay. So anyone can mint + consume a link for any email without
   inbox access.

The client uses `send-email-v2` for THREE email types today (all let the
browser control recipient + HTML + sender):
- `kidsync.js` — kid magic-link sign-in.
- `parent.jsx:588` — parent "email me the reading report".
- `parent.jsx:1005` — parent "email the kid's recovery code".

## Principle

The browser must never control `to_email` + `html` + `from_name`. Each email
type gets a purpose-built server function that composes the body server-side;
`send-email-v2` becomes an internal, secret-gated SMTP relay.

## Pieces (in this PR)

- `supabase/functions/request-magic-link/index.ts` — NEW. Takes `{email,
  client_id}`, issues the token server-side (never returns it), composes the
  sign-in email, forwards to send-email-v2 with the secret. Replaces the
  kid magic-link path.
- `supabase/functions/send-email-v2/index.ts` — hardened: requires
  `x-internal-secret == SEND_EMAIL_SECRET`, else 403. (This repo now holds the
  source; previously it lived only on Supabase.)

## Pieces (follow-up, described here — build when rolling out)

- `send-recovery-code` edge fn (verify_jwt=true): takes `{kid_client_id}`,
  reads the caller's email from the JWT, composes + sends. Replaces
  `parent.jsx:1005`.
- `send-parent-digest` edge fn (verify_jwt=true): composes the digest
  server-side from the caller's kid data, sends to the JWT email. Replaces
  `parent.jsx:588` (recipient stops being client-controlled).
- Client edits: `kidsync.js` → call `request-magic-link`; `parent.jsx` → call
  the two new functions. Remove all direct `send-email-v2` fetches.
- Server callers add the secret header: `pipeline/quality_digest.py`,
  `supabase/functions/send-digest/index.ts`, `.github/workflows/pipeline-watchdog.yml`.

## Zero-downtime rollout order (CRITICAL)

send-email-v2's lockdown is deployed LAST, only after every caller passes the
secret — so there is never a window where a legit caller is rejected.

1. Create the secret: `SEND_EMAIL_SECRET` (Supabase project secret) — a random
   32+ char string. Set it on the project so all edge fns + the GH secret.
2. Deploy `request-magic-link` (+ the two parent functions). Additive — nothing
   else changes yet. send-email-v2 still open, so they work.
3. Ship the client (kidsync.js + parent.jsx) pointing at the new functions.
   Site deploy. Now no browser calls send-email-v2 directly.
4. Update the 3 server callers to send `x-internal-secret`. Deploy them.
   (Harmless extra header while send-email-v2 is still open.)
5. Deploy the hardened `send-email-v2` (requires the secret). Now every caller
   passes it → relay closed, zero breakage.

## Verification per phase

- After 2: `curl request-magic-link` with a test email → 200 + email arrives;
  token never in the response.
- After 3: real kid + parent sign-in still work (magic link, recovery, digest).
- After 5: `curl send-email-v2` WITHOUT the secret → 403; WITH → 200. Digests
  + login still work end-to-end.

## Notes

- Magic-link *binding* (requester vs clicker device) is already fixed and live
  (PR #33 / `2026-07-08-magic-link-binds-clicking-device.md`).
- `request-magic-link` stays verify_jwt=false (kids are anonymous); abuse is
  capped by issue_magic_link's 5-active-links-per-email limit. Consider adding
  a per-IP rate limit at rollout.
