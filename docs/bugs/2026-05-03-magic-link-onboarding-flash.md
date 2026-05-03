# 2026-05-03 — magic-link-onboarding-flash

**Severity:** medium (bad UX, not data loss)
**Area:** website
**Status:** fixed
**Keywords:** magic_link, consumeMagicLink, OnboardingScreen, sign-in, race, kidsync, fetchProfile, useEffect, hydration

## Symptom

User clicks the magic-link in their email. They expect to land on the
home page already signed in. Instead they land on the OnboardingScreen
that asks them to type their name + send a magic link AGAIN. The user
can hit "skip" / fill in the form once more and eventually log in,
but the loop is confusing and looks like the magic link didn't work.

User's exact words (from chat 2026-05-03):

> when I use magic link email click that link. it will redirect me
> to the initiate page which ask send magic link again. although I
> can skip and then login but that loop is not good.

Reproduction:
1. On Device A, type your email and click "Send magic link" on the
   onboarding screen, OR clear localStorage and request a fresh link.
2. Open the email on Device A (same browser). Click the link.
3. Page loads at `/?magic=<TOKEN>`.
4. Within the first ~1-2 seconds of page load, the OnboardingScreen
   is visible — same form that asks for name + email + send link.

The bug is most painful on a fresh device or after `localStorage`
was cleared, because in those cases the cloud profile fetch can
return null (brand-new email never had a `display_name` synced) and
OnboardingScreen sticks around indefinitely.

## Root cause

`website/index.html`'s App component decides what to render based on
a synchronous read of `tweaks` from `localStorage` on first paint.
`website/home.jsx:1123` then gates rendering with:

```js
const needsOnboarding = !isArchive && (!tweaks?.userName || tweaks.userName.trim() === '');
if (needsOnboarding) return <OnboardingScreen .../>;
```

Magic-link consumption happens AFTER first paint, inside the cloud
bootstrap useEffect (`website/index.html:259-429`). That async chain
runs:

1. `consumeMagicLink(token)` — RPC writes canonical client_id +
   email to localStorage.
2. `linkCurrentSession()` — idempotent identity link.
3. `fetchProfile()` — pulls `display_name` / `avatar` / `theme` /
   `level` / `daily_goal` from `kid_profiles` and merges into
   `tweaks` via `setTweaks`.
4. `fetchHistory(100)` — backfills readHistory + articleProgress.

Until step 3 resolves, `tweaks.userName` is whatever was already in
localStorage (usually empty for a returning user on a different
browser). `needsOnboarding` is `true`, so OnboardingScreen wins the
first ~1-2 paints.

The OnboardingScreen has the magic-link UI baked in (`home.jsx:374-413`),
so the user sees the SAME "send magic link" form they just used.
They reasonably conclude the link didn't work and re-submit.

The ?magic= token is being consumed correctly behind the scenes —
the RPC works, the email and client_id are persisted. The UI just
doesn't know to wait, and the OnboardingScreen doesn't know that
sign-in is already in progress.

There was no test (UI race window). The only signal a developer
would have is opening the production site with a magic-link URL,
which doesn't happen in normal dev.

## Fix

PR https://github.com/daijiong1977/news-v2/pull/<TBD>.

Add a `magicConsuming` boolean state in `App` (`website/index.html`),
true on initial render iff URL has `?magic=`. The cloud bootstrap
useEffect resolves it to false in a `finally` block once
`consumeMagicLink` settles (success OR failure — we don't want to
hang the UI on a bad token).

Pass `magicConsuming` down to `HomePage` as a prop. In `HomePage`,
short-circuit BEFORE the `needsOnboarding` check:

```js
if (magicConsuming) {
  return <SigningInScreen theme={theme} />;
}
```

`SigningInScreen` is a tiny new component (~30 lines) that shows a
spinner + "Signing you in…" copy, themed to match the brand colors.

If the token turns out to be invalid (RPC returns
`{ ok: false, error: ... }`), `magicConsuming` flips to false and
the OnboardingScreen renders normally — with a hint banner so the
user knows the link was bad.

Files touched:
- `website/index.html:188` — new `magicConsuming` useState
- `website/index.html:259-429` — bootstrap useEffect's
  `consumeMagicLink` block wraps in try/finally to flip the flag
- `website/index.html:608-625` — pass `magicConsuming` prop to HomePage
- `website/home.jsx:974` — HomePage signature accepts `magicConsuming`
- `website/home.jsx:1119-1135` — early-return SigningInScreen
- `website/home.jsx:<new>` — `SigningInScreen` component
- `website/home.jsx:<new>` — `magicLinkError` state surfaced as a
  banner in OnboardingScreen when consumption failed

No backend / RPC changes — `consume_magic_link` already returns
`{ ok, error }` correctly, the bug was purely in the render path.

## Invariant

**A page-load that carries `?magic=<token>` MUST NOT render the
OnboardingScreen until the magic-link consumption attempt has
settled (resolved or rejected).**

Future edits to the cloud bootstrap useEffect MUST NOT remove the
`finally` that sets `magicConsuming=false`. If a new async step is
added between consumeMagicLink and fetchProfile, evaluate whether
its resolution should also gate the spinner — the current contract
is "spinner until consumeMagicLink finishes," not "spinner until
fetchProfile finishes."

If the magic-link UI moves out of OnboardingScreen into a separate
sign-in route, the same `magicConsuming` gate applies there.

## Pinning test

MANUAL (no automation infra for SPA login flows in this repo):

1. Open chrome devtools.
2. `localStorage.clear()` on `news.6ray.com`. Reload — should land
   on OnboardingScreen.
3. Type a name + email, click "Send magic link". Verify email arrives.
4. Click the link in the email. URL transitions to `?magic=<TOKEN>`.
5. **Expected behavior:** the screen briefly shows "Signing you in…"
   (NOT the OnboardingScreen with magic-link form). Within ~1-2s,
   transitions to the home page (signed in).
6. **Bug behavior:** OnboardingScreen with the magic-link form is
   visible during the consumption window. User can resend the
   magic link, which is the loop.

If step 5 ever shows the OnboardingScreen during the brief
post-click moment, the regression is back. This is enforced by the
`if (magicConsuming) return <SigningInScreen .../>;` early-return —
remove it and the bug returns immediately.

## Related

- `2026-04-26-kid-identity.sql` — original magic-link RPC migration.
- `website/kidsync.js:392-417` — `consumeMagicLink` RPC wrapper
  (correct, not changed in this fix).
- `website/index.html:259-429` — cloud bootstrap useEffect (extended
  to gate the spinner).
- Universal-patterns lesson (cross-project): "State + async: await
  before setState" — the bootstrap effect was relying on multiple
  awaited steps to populate state, and the render path didn't know
  which step was the gate. The fix uses an explicit "in-flight"
  flag rather than implicit "wait for all data".
