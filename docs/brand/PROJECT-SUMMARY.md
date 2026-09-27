# 21 minutes every day — Kids News (kidsnews vertical)

> **Snapshot date:** 2026-04-25
> **Live URL today:** https://news.6ray.com (Vercel deploy of this repo)
> **Live URL going forward:** https://kidsnews.21mins.com (in migration; same bundle, same code, new domain)
> **Source repo for the bundle that lives here:** https://github.com/daijiong1977/news-v2 (Python pipeline + the JSX you see in `site/`)

This file is the **single hand-off doc** for design improvement passes
(Claude, human designer, or any other vertical-agnostic reviewer).
It also doubles as the seed for **future verticals** at the same brand
parent — `ai.21mins.com`, `finance.21mins.com`, `tech.21mins.com`, etc.
— which will reuse the same shell with different content + a different
`SITE_CONFIG`.

---

## 1. The product in one paragraph

A daily kid-news habit. Three stories per day (News / Science / Fun),
each in two reading levels (Sprout = 4th-grade, Tree = 7th-grade) plus
a Chinese summary. Each story has four learning steps — Read & Words,
Background, Quiz, Think — together totaling **7 minutes** of focused
work. Three stories × 7 = **21 minutes a day**, the brand promise.
Reader earns +2 / +1 / +2 / +2 minutes toward the day's 21-minute
goal as each step is finished. A 21-day streak is the long-term game.

---

## 2. Audience + positioning

- **Primary reader:** kids age 8–13 (own Sprout/Tree paths inside
  the same daily 3 stories).
- **Secondary reader:** the parent who hands the device over and
  expects *no* dark patterns, no infinite scroll, no ads, no
  comments/social. The 21-minute boundary is the point.
- **Tone:** warm-cartoon — emojis used as functional accents (📰 🔬 🎉
  📖 🔍 🎯 💭), Fraunces serif for moments-of-pride headings, Nunito
  sans for body. Color is muted-warm (`#fff9ef` ground, `#1b1230`
  ink, `#ffc83d` gold accent).
- **Voice:** writes as a thoughtful older friend, not a teacher. No
  baby talk, no exclamation-mark spam.

The "21 minutes every day" wordmark deliberately puts the *behavior*
on top, not a brand persona — so the same page works for
`ai.21mins.com` (adult, daily AI digest, same 21-min model) without
re-skinning the shell.

---

## 3. Visual + UI design system

### Palette
| Role | Token | Notes |
|---|---|---|
| Page bg | `#fff9ef` (sunny variant default) | also: sky `#eef6ff`, candy `#fff0f6`, forest `#f3f8ec` — picked in user panel |
| Primary text | `#1b1230` | navy-violet, deep enough for kid eyes |
| Accent | `#ffc83d` | sunny gold; bg-rotate-2deg pattern for hero highlight |
| Category — News | `#ff6b5b` over `#ffece8` | warm coral |
| Category — Science | `#17b3a6` over `#e0f6f3` | cool teal |
| Category — Fun | `#9061f9` over `#eee5ff` | playful violet |
| Success / streak | `#0e8d82` over `#e0f6f3` | |
| Warning / stale | `#c14e2a` over `#fff0e8` | |

### Typography
- Display: **Fraunces** (variable weight, 800/900) — headings, hero,
  story titles.
- UI / body: **Nunito** (500/700/800) — buttons, cards, copy.
- Mono: system mono (`ui-monospace, SFMono-Regular, Menlo`) — `pre`
  bits in admin only.

### Spacing + radii
- Cards: `border-radius: 14–16px`, soft shadows
  (`0 2px 0 rgba(27,18,48,0.05)`), 1.5px warm-beige border (`#f0e8d8`).
- Buttons: `border-radius: 16px` for hero CTAs, `10–12px` for
  utility. Active state lowers a 3-px shadow → 1-px shadow + 2px
  translateY for a satisfying press feel.
- Pills: `border-radius: 999px` everywhere status appears.

### Components (in `components.jsx` + inline)
- `OhYeLogo` — placeholder mark; **logo refresh pending** for the
  21-minutes brand.
- `StreakRing` — animated SVG ring around 🔥 emoji and the streak
  count.
- `BigButton` — hero CTA with press animation.
- `CatChip`, `LevelChip`, `XpBadge` — small inline status pills.
- `StarMeter` — quiz progress.
- `ProgressBadge` — homepage's per-card progress ring (auto-hides
  for 0%, becomes ✓ at 100).

### Layout
- Single-column on mobile (no design rows below 480px assumed yet).
- Desktop: max-width 1180px gutter, generous whitespace.
- Hero on home: 2-up — copy left, today's-3 stack right.
- Article page: top stepper bar, then four tabs (Read, Background,
  Quiz, Think), each rendered in-place as the user advances.

### Interaction language
- Cards "press" not "tap" — physical 2-3px shadow + translateY.
- Confetti spritz on quiz-complete (deliberately small, not
  Duolingo-loud).
- No infinite scroll. No "next article" until daily 3 done.
- Star meter for the quiz, not points-flying.

---

## 4. Information architecture

```
Home  /
   ├─ Hero (today's 21 min)
   ├─ Today's 3 (swappable picks per category)
   ├─ Category tabs  (News / Science / Fun)
   ├─ Articles grid for the active category
   └─ Footer
Article  /article/:id
   ├─ Header (back · brand · stepper)
   ├─ Tab 1: Read & Words   (body, keyword reveal)
   ├─ Tab 2: Background     (named-entity intros, 5W structure)
   ├─ Tab 3: Quiz           (6 MCQs, immediate feedback)
   └─ Tab 4: Think          (Discussion prompts, response capture)
Archive  (calendar popover from home)
   └─ Past N days served from a dated Supabase Storage prefix.
Admin  /admin    (separate page, Google SSO, allowlist)
   └─ See repo `news-v2/website/admin.html` for the 8-tab admin.
```

---

## 5. Key UX flows

1. **First-time reader** opens kidsnews.21mins.com → sees brand,
   hero "Today's 21 minutes", "0 / 21 min today" pill, three
   category cards on the right. Picks one or hits the "Start
   today's read" hero CTA.
2. **Inside an article**, the stepper across the top acts as both a
   wayfinding and a reward bar. Each tab's "Next" button is the
   single primary action; *no tab is forcibly locked*, but the
   stepper visually emphasizes the next undone tab.
3. **Day rollover:** at local midnight the counter resets. Detected
   on tab visibility-change so a tab left open across midnight
   doesn't double-count yesterday's leftover.
4. **Resume:** reopening a story lands on the last tab the reader
   was on (`articleProgress[id].lastTab`).
5. **Streak:** earned by hitting the daily 21 — visible in the
   streak ring on the home hero (and the user panel).

---

## 6. Tech stack

- **Frontend:** plain HTML + Babel-standalone in the browser. No
  build step. JSX files are loaded directly. Trade-off: simple
  authoring, slightly slower first paint.
  - `index.html` — App shell + auth/state/routing
  - `home.jsx` — Home page
  - `article.jsx` — Article detail page
  - `components.jsx` — Shared components
  - `data.jsx` — `SITE_CONFIG`, payload loader, helpers
  - `user-panel.jsx` — Settings drawer
  - `admin.html` — Standalone admin page (kid-facing site never
    routes here)
- **Storage:** all reader state in localStorage (`ohye_progress`,
  `ohye_tweaks`, `ohye_route`, `ohye_archive_day`,
  `ohye_daily_picks_v3`). Anonymous client-id assigned for feedback
  stitching but no auth required for reading.
- **Backend (in the news-v2 repo, not this one):**
  - Supabase Postgres + Storage + Auth + Edge Functions.
  - Daily Python pipeline (`pipeline/full_round.py`): mines RSS,
    cleans + safety-filters, calls a configurable LLM provider
    (currently DeepSeek V4 Flash), persists 9 stories, packs zip,
    pushes to Supabase Storage, dispatches the kidsnews-v2 sync.
  - Admin-editable categories / sources / providers / cron-config /
    admin-allowlist tables (`redesign_*`).
  - Checkpoint resume across pipeline stages.
- **Deploy:** GitHub Action in `news-v2` builds a daily zip; a
  scheduled+dispatched Action in `kidsnews-v2` (this repo) pulls
  it, rewrites `site/`, commits, and Vercel auto-deploys on push.

---

## 7. Per-vertical configuration

`site/data.jsx` exposes a single `SITE_CONFIG`:

```js
const SITE_CONFIG = {
  brand:        "21 minutes every day",
  audience:     "Kids age 8-13",
  domain:       "kidsnews.21mins.com",
  vertical:     "kidsnews",

  dailyGoalMinutes: 21,
  storiesPerDay:    3,
  perArticleMinutes: 7,             // = sum(stepWeights)
  stepWeights: { read:2, analyze:1, quiz:2, discuss:2 },
};
```

**Invariant:** `storiesPerDay × Σ(stepWeights) === dailyGoalMinutes`.

For each new vertical, fork the deploy and override:
- `vertical` → folder name in storage
- `audience` → "Adults curious about AI / finance / tech / …"
- `stepWeights` → e.g. AI vertical may want `{read:3, analyze:2, quiz:1, discuss:1}` if
  source articles are denser
- `domain` → matching subdomain on 21mins.com
- The DB tables (`redesign_categories`, `redesign_source_configs`)
  stay multi-tenant via a `vertical` column when the time comes.

Brand display surfaces (header logo text, footer, browser title in
JSX-rendered places) read `window.SITE_CONFIG.brand` at runtime —
literal "21 minutes every day" only appears in the static `<title>`
tags of `index.html` + `admin.html`.

---

## 8. What works — strengths to preserve

- **Frictionless first read.** No login wall, no "create account"
  wedge. The bootstrap admin path is the only auth flow, and even
  that's quiet (one-time setup).
- **The 21-minute boundary** is the actual product, not a marketing
  line. The counter only goes up by stepping through the four tabs;
  scrolling without engaging doesn't tick.
- **Resume + day-rollover.** Two often-broken UX details that work
  here: a returning reader lands on the right tab; a midnight
  visitor sees a clean 0/21 not yesterday's leftover.
- **Single-source-of-truth `SITE_CONFIG`.** Every vertical can
  reskin without touching JSX logic.

---

## 9. Known issues + improvement opportunities

### Pixel-level visual polish
- **Logo placeholder.** `OhYeLogo` is a temporary mark. Wordmark for
  "21 minutes every day" is unwritten. Designer brief: a logomark
  small enough to live at 32×32 in the article header AND 72×72
  in the hero — probably abstracts the "21" as a closed loop or
  a clock-arc.
- **Hero composition.** The "Today's <21> minutes" hero has the
  right energy on desktop but compresses awkwardly at < 768px;
  the stack reorder loses the rotated-pill emphasis.
- **Streak ring size.** 72px on hero, 40px in header — both look
  cramped next to Fraunces 30/52pt headings.
- **Empty + error states.** Functional but undesigned (e.g.
  "No stories here · 🌱"). Mostly placeholders.

### Information design
- **Stepper UX.** Currently the four tabs are clickable in any
  order, but the visual stepper is stronger as a sequence — a kid
  can skip Background and just answer Quiz. Consider gating
  forward only when prior tab has been "next-clicked" at least
  once.
- **Word-aloud button** lives inside the keyword card and is easy to
  miss. Could surface as a tap-zone wrapping the term itself.
- **Archive day picker.** Calendar popover works but feels
  "official" — kids would respond to a friendlier visual.
- **Streak rewards.** No visible reward beyond the number. Even
  small things — confetti at 21 days, a weekly stamp — would help
  the streak feel worth chasing.

### Content layout
- **Quiz feedback** currently flashes confetti and moves on.
  Designer + behavioral question: should incorrect answers say
  *why* the right one is right, or trust the body to have explained
  it? Currently neither.
- **Background tab structure** is lots of paragraph + a 5W table.
  At Tree level it's a lot of text — consider a vertical accordion
  per W.
- **Article body.** No images inside the body — the og:image is
  shown once at the top. Designer should consider whether
  illustration / pull-quote / "did-you-know" interleave fits the
  brand.

### Cross-vertical extensibility
- `SITE_CONFIG` covers behavior + counters but **not visuals.**
  When the AI vertical wants its own palette + logo, today that
  means JSX edits. Plan: extend `SITE_CONFIG` to carry a `theme`
  object that components.jsx reads from.
- The category list is hardcoded as 3 (`News`, `Science`, `Fun`)
  in some places (homepage layout assumes 3 cards). Future
  verticals may want 2 (AI: News + Deep dive) or 4 (Finance:
  Markets + Macro + Companies + Crypto).

### Accessibility
- Keyboard navigation is present but minimal — tab focus indicators
  default browser styling.
- Color-only state indicators (active vs disabled chips). Consider
  adding text or icon supplements.

---

## 10. What this snapshot contains

```
kidsnews-v2-snapshot/
├── README.md             — repo's own auto-generated note
├── vercel.json           — cleanUrls + cache-control headers
└── site/
    ├── index.html        — App shell, routing, state, auth
    ├── home.jsx
    ├── article.jsx
    ├── components.jsx
    ├── data.jsx          — SITE_CONFIG + payload loader
    ├── user-panel.jsx
    ├── article_images/   — today's 9 webps (cropped to ~1024×768)
    ├── article_payloads/ — per-story keywords / questions / etc
    ├── article_pdfs/     — printable PDFs per (story × level)
    └── payloads/         — per-(category × level) listing JSONs
```

The Python pipeline + admin live in the **sibling repo `news-v2`**
(at `~/myprojects/news-v2/` for daijiong1977). Design feedback
about the daily content pipeline, the admin page, or the source
extraction lives there, not here.

---

## 11. Asks for the design pass

If this summary is being read by a designer or a critique-bot:

1. **Logo + wordmark for "21 minutes every day."** Versatile across
   verticals (kidsnews / ai / finance / …). The "21" or the "minutes"
   should carry, not the persona.
2. **Hero composition** that works mobile-first.
3. **Stepper reward language** — small visual changes that make the
   four tabs feel like a journey, not a checklist.
4. **Empty states + first-time-visitor onboarding** (single screen,
   no signup).
5. **Archive day-picker** that fits the brand.
6. **A theme extension to `SITE_CONFIG`** so each future vertical
   can reskin without editing JSX.

---

## 12. Pointers for future verticals

When you spin up `ai.21mins.com` or similar, the absolute minimum
fork is:

- New Vercel project pointed at a sibling repo (e.g. `ainews-21mins`).
- That repo's `site/` is bundled by a vertical-specific pipeline
  in something like `ai-news-v2`.
- The bundled `data.jsx` overrides `SITE_CONFIG`:
  ```js
  const SITE_CONFIG = {
    brand: "21 minutes every day",   // same brand, same wordmark
    audience: "AI-curious adults",
    domain: "ai.21mins.com",
    vertical: "ai",
    dailyGoalMinutes: 21,
    storiesPerDay: 3,
    perArticleMinutes: 7,
    stepWeights: { read: 3, analyze: 1, quiz: 2, discuss: 1 },
    // future: theme: { ... }
  };
  ```
- Categories per vertical are admin-editable in the shared Supabase
  (`redesign_categories` table), so adding "Models / Apps / Policy"
  for the AI vertical doesn't require code.

The `21mins.com` parent could host a tiny landing — *"Pick your
21 minutes"* — that links to the verticals.
