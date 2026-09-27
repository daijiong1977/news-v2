# Email and magic-link security rollout

The live `kidsnews.21mins.com` client still calls `issue_magic_link` from an
anonymous browser session and receives the raw token. It also posts arbitrary
recipient/HTML to `send-email-v2`, deployed with `verify_jwt=false`. The
`send-digest` worker is publicly triggerable while holding a service-role
key. These are real security issues, not a news-quality preference.

## Completed code in PR #35

- `request-magic-link` issues the token server-side and sends a fixed email.
  The response never contains the token. A link may target only the two
  production origins; a supplied evil `Origin` cannot redirect the token.
- `send-recovery-code` validates the parent's Supabase Auth JWT, checks that
  the requested kid belongs to that parent, runs the existing recovery RPC as
  the caller, then sends to the authenticated email. Recipient and HTML cannot
  be chosen by the browser.
- The anonymous parent-dashboard "email this device's full report to any
  address" button is removed per owner choice. Scheduled digest remains.
- `send-digest` requires `x-internal-secret`; `send-email-v2` accepts that
  header or a service-role bearer. The new header is backed by one
  64-character random `SEND_EMAIL_SECRET` in Supabase and GitHub Actions.
  Quality digest, parent digest, and pipeline watchdog supply this header.
  The relay also accepts the existing Supabase service-role bearer from the
  AI News and podcast **server** jobs; those credentials are already secret,
  and this avoids breaking their notifications. Anonymous/publishable-key
  browser calls remain forbidden.
- After the new site is live, a database migration revokes `issue_magic_link`
  from PUBLIC, anon and authenticated. Only service_role may receive a raw
  token. The migration must not run before the site changes.

## Production rollout — order matters

1. Store the *same* new `SEND_EMAIL_SECRET` in the Supabase project and in
   the `daijiong1977/news-v2` GitHub Actions secrets. Never put it in the
   repository or browser bundle.
2. Deploy `request-magic-link` with `--no-verify-jwt` (kids have no Supabase
   Auth session) and `send-recovery-code` with JWT verification enabled.
   Leave the old relay untouched. Smoke-test a test sign-in email and ensure
   the response contains no token; reject invalid recovery requests.
3. Merge PR #35. `website/**` triggers the republish/sync/Vercel workflow.
   Verify the fresh public `kidsync.js` no longer mentions `issue_magic_link`
   or `send-email-v2`, and the parent page no longer posts to the relay.
   Verify a sign-in email and authenticated recovery email end-to-end.
4. Deploy the revised `send-digest` with `--no-verify-jwt`; its own secret
   gate is mandatory. Check unauthenticated calls return 403 and the parent
   digest GitHub workflow passes the secret. Confirm quality digest and
   watchdog callers have their GitHub secret available.
5. Apply `20260927_restrict_magic_link_issuance.sql`. Confirm anonymous
   `issue_magic_link` calls are denied while server-side sign-in still works.
6. **Last**, deploy the hardened `send-email-v2` with `--no-verify-jwt`.
   Confirm no-secret requests return 403, a fixed-content sign-in email is
   delivered, and scheduled/admin mail still works. Do not publish the
   shared secret or test it in a browser.

Do not merge first and wait to deploy the additive functions: the website
automatically republishes from `main`, so login would break during that gap.
Do not deploy the relay gate before the website and server callers have moved.

## Validation and limitations

Run `deno test supabase/functions/_shared/email_security_test.ts`, `deno
check` on the four edge functions, the relevant Python digest tests, and a
browser syntax check before rollout. The public magic-link request remains
anonymous by necessity; the existing RPC limits five unconsumed links per
email in 30 minutes. Because a malicious caller could still request fixed
sign-in emails to many addresses, monitor volume and add a stronger global
abuse control if observed. No child-safety or article-selection threshold is
changed by this security work.
