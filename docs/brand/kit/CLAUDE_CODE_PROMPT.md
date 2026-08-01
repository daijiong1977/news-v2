# Claude Code prompt — kidsnews v2 brand alignment

Copy everything below the divider and paste it into Claude Code from the **root of the kidsnews-v2 repo**. The audit document and brand kit will be provided alongside in a `21mins-brand/` folder; if you placed them elsewhere, adjust the paths in step 0.

---

## ROLE

You are a frontend engineer working on **kidsnews v2**. A brand audit has identified concrete misalignments between the live build and the locked **21mins** parent brand. Your job is to apply those changes — faithfully, completely, and without inventing new design directions.

## INPUTS YOU HAVE

- The kidsnews-v2 codebase (this repo).
- A folder `21mins-brand/` at the repo root containing:
  - `README.md` — full brand documentation (read this first)
  - `tokens.css` / `tokens.json` — color + spacing tokens
  - `fonts.css` — Fraunces + Nunito imports
  - `assets/kidsnews-mark.svg`, `kidsnews-mark-dark.svg`, `favicon-kidsnews.svg` — locked kids marks
  - `assets/21mins-mark.svg`, `21mins-mark-dark.svg` — parent endorsement mark
  - `react/SunFace21.jsx`, `Big21.jsx` — canonical React mark components
- An audit document `audit/index.html` (open it in a browser) showing every BEFORE/AFTER pair and a proposed home flow.

## STEP 0 · Orient

1. Open `21mins-brand/README.md` and read sections 1–4 (system, logos, colors, type).
2. Open `audit/index.html` in a browser. Skim every section top-to-bottom. Pay attention to the **AFTER** artboards and the annotation notes — those are the spec.
3. List the kidsnews-v2 files you'll need to touch. At minimum:
   - The component that renders the current placeholder logo (`OhYeLogo` or similar)
   - Header / top-nav component
   - Home page / hero component
   - Article reader header + time pill
   - User panel / profile drawer
   - `index.html` `<head>` (favicon, OG tags, document title)
   - Global CSS / token file
4. **Confirm with me** before making changes. Show me the file list and your plan. Wait for go-ahead.

## STEP 1 · Install brand assets

1. Copy `21mins-brand/tokens.css` and `21mins-brand/fonts.css` into the repo's global CSS location. Import them at the app root.
2. Copy the SVG assets from `21mins-brand/assets/` into the repo's public/static asset directory.
3. Copy `21mins-brand/react/SunFace21.jsx` and `Big21.jsx` into the components directory. Adjust import paths if needed but **do not modify the SVG geometry** of either component.
4. Replace any existing color values in the global stylesheet that match the old palette with the `var(--ink)` / `var(--gold)` / `var(--coral)` / etc. tokens from `tokens.css`. Do NOT re-tune the colors.

## STEP 2 · Logo + wordmark

Delete the current `OhYeLogo` placeholder component and any references to "News Oh,Ye!" wordmark.

Replace with the **kidsnews lockup** as documented in `21mins-brand/README.md` §2 and shown in audit section 1:

- Mark: `<SunFace21 size={...}/>` from the brand kit
- Wordmark: "kids" in `var(--ink)` + "news" in `var(--coral)`, Fraunces 700, letter-spacing `-0.02em`
- Endorsement line below wordmark: small `<Big21 size={11} ink="var(--muted)" accent="var(--muted)"/>` followed by the text "a 21mins channel" — Nunito 800, 9.5–10px, `letter-spacing: 0.18em`, uppercase, `var(--muted)`

Apply this lockup **everywhere** the old logo appeared:
- Global header (full size, ~44px mark)
- Article reader top bar (compact, ~32px mark)
- User panel hero (if logo was there)
- Any modal/drawer headers
- Footer / about pages

## STEP 3 · The "21 minutes" promise

This is the highest-priority brand fix. The current build shows **15 minutes** in the home hero. **Change it to 21 everywhere.**

In the home hero (audit section 2a):
- Headline: "Today's **21 minutes**" (the "21 minutes" word group sits in a gold pill, rotated -2deg, per the AFTER mock)
- Tagline directly below the headline, italic Fraunces 600, ~22px, color `#c14e2a`: **"Little daily, big magic."**
- Body copy: "Three smart stories. Read, think, and earn your streak."
- The sub-progress line should read e.g. "12/21 min today" (not 8/15)

Update the Daily-3 stack:
- Header reads "⚡ Today's 3 · 7 min each" (the per-story estimate is now 7, so 3×7 = 21)
- Each story's `mins` field in mock/seed data should be **7** (or 6/7/8 with the total summing to 21)
- Add a green check ✓ on completed stories (audit shows the first story in the demo as done)

Search the codebase for the literal string `15` / `15 min` / `15 minutes` in the context of the daily goal and replace with `21`. Same for the daily-goal selector in the user panel — current options `[5, 10, 15, 20, 30]` become `[15, 21, 30, 45]`, default selected = **21** (audit section 3).

## STEP 4 · Article reader (audit 2c)

- Replace top-bar wordmark with the compact kidsnews lockup
- The time-to-read meta line currently shows "⏱ 7 min · Tree level". Reframe as a pill: `7 min · 1 of your 21` so each story positions itself within the 21-minute budget
- Keep the stage stepper (Read · Background · Quiz · Think) exactly as it is — that pattern is good

## STEP 5 · User panel (audit section 3)

- Add a faint sun-rays watermark in the hero gradient header (12 rays, opacity `.18`, ink color, lower-right). Match the SVG pattern in the AFTER mock.
- Streak chip: change from generic white pill to `var(--ink)` background + `var(--gold)` text — same color pair as the parent badge.
- Daily goal options retuned (see step 3).

## STEP 6 · Net-new surfaces (audit section 4)

These do not exist in v2. Add them:

### 6a · Favicon + document head

In `index.html`:
```html
<link rel="icon" type="image/svg+xml" href="/assets/favicon-kidsnews.svg">
<title>kidsnews · today's 21 minutes</title>
<meta name="description" content="Three smart stories every day for curious kids 8–13. Little daily, big magic.">
```

### 6b · Open Graph share card

Add OG/Twitter meta tags pointing to a share image. For the share image, you have two options:
- **Quick:** screenshot the OG artboard from `audit/index.html` at 1200×630 and use as `og-image.png`
- **Proper:** build a route that renders the OG card component server-side / via puppeteer — match the design in audit section 4

```html
<meta property="og:title" content="kidsnews · little daily, big magic">
<meta property="og:description" content="The daily news habit for curious kids 8–13. Three stories, 21 minutes, read · think · learn.">
<meta property="og:image" content="/assets/og-image.png">
<meta name="twitter:card" content="summary_large_image">
```

### 6c · First-run onboarding

Currently there is none. Build the onboarding splash shown in audit section 4. It's a single-screen, two-column layout — sun-mark on the left, brand intro + 3 category teasers + "Pick my animal →" CTA on the right. Component skeleton:

```jsx
<OnboardingSplash onContinue={() => setStep('animal-picker')} />
```

Show on first session only (gate via localStorage `kidsnews:onboarded`).

## STEP 7 · OPTIONAL — proposed pick-3 home flow (audit section 5)

The audit proposes reframing the home page as a **pick → today → read** ritual instead of "Daily-3 + browsable feed at the same time". This is a larger UX change.

**Do NOT ship this without my explicit go-ahead.** Confirm with me whether to:
- (A) Skip it for now and keep the current home, just brand-corrected (steps 1–6)
- (B) Implement the pick flow as documented in audit section 5 — with `Pick`, `Today`, `Read` as the new home routes
- (C) Implement (B) behind a feature flag so we can A/B it

If (B) or (C): the AFTER artboards in audit section 5 are the spec. Stories are picked from a daily pool of 9, kid taps to select 3, hits "Start" — the existing reader stays intact.

## STEP 8 · QA pass

Before declaring done:
1. Open every page that displays the logo/wordmark. Confirm it's the new kidsnews lockup, no exceptions.
2. Search the codebase for `OhYe`, `Oh,Ye`, `15 minutes`, `15 min` (in daily-goal contexts), `News Oh` — should return zero results.
3. Confirm tokens are imported and the page renders with the correct cream/ink/gold palette.
4. Confirm Fraunces (Fraunces, not a fallback) and Nunito are loading — open devtools network tab, look for the Google Fonts request.
5. Tab title shows "kidsnews · today's 21 minutes". Favicon shows the sun-face.
6. Take screenshots of: header, home, article reader, user panel. Compare side-by-side with the AFTER artboards in `audit/index.html`. Pixel-perfect not required, but composition + colors + wording must match.

## CONSTRAINTS

- Do NOT re-color the locked marks. Pass props.
- Do NOT substitute fonts. Fraunces + Nunito are load-bearing.
- Do NOT change the "long-long-short" bar rhythm in any 21mins-related artwork — it's the brand signature.
- Do NOT redesign the feed grid (audit 2b) — it's already on-brand.
- Do NOT add new copy or sections that weren't in the audit. If you think something's missing, ask first.
- If a screen exists in the live app but isn't covered in the audit (e.g. quiz UI, settings deep pages), apply the same logo/wordmark/token rules consistently and flag for review.

## DELIVERABLE

A pull request with:
- Title: `feat: align kidsnews v2 with locked 21mins brand`
- A description that lists which audit sections were addressed and which (if any) were deferred
- Screenshots of the four key surfaces (header, home, article, user panel)
- A note on whether step 7 (pick-3 flow) was implemented, deferred, or flagged

When in doubt, the audit document is the source of truth. The brand kit README is the second source of truth. If the two disagree, the brand kit wins.
