# 21mins · Brand Handoff

A complete brand kit for **21mins** (parent) and **kidsnews · 21mins** (kids vertical).
Drop the `assets/` folder into your codebase and use the tokens in `tokens.css` / `tokens.json`.

> **For Claude Code:** open `CLAUDE_CODE_PROMPT.md` for a step-by-step prompt that wires this kit into the kidsnews-v2 codebase. Open `audit/index.html` in a browser to see the BEFORE/AFTER spec for every screen.

---

## 1 · The system at a glance

**21mins** is a family of daily learning rituals. One subject, one finite session, one habit.
The first vertical is **kidsnews** — a daily news-literacy practice for kids 8–13.
Future verticals planned: **ai**, **finance**, **tech** (each gets its own accent color, same skeleton).

**Voice:** energetic, optimistic, daily-ritual. The sun is the metaphor — it rises every day, the magic compounds.

---

## 2 · Logos

### Parent · `21mins`
A stacked geometric mark: **"21"** in Fraunces light, three accent bars in one row (long · long · short) tucked under, **"MINS"** tracked beneath.
The bar rhythm is the brand's signature — it appears in every vertical.

- `assets/21mins-mark.svg` — light (ink on cream)
- `assets/21mins-mark-dark.svg` — dark (white on ink)
- `assets/favicon-21mins.svg` — favicon-tuned (32px)

**Slogans**
- Short form: **"Little Daily, Vast Magic."** (use everywhere except hero)
- Long form: **"21 minutes. Every day. _The magic compounds._"** (hero / about)

### Kidsnews · `kidsnews · 21mins`
A sun-faced mark built from the parent's DNA:
- **Roman II + I** as the eyes (II open, I winking) — the "21" reframed for kids
- **"MINS"** as the nose — same Nunito caps as the parent
- **Smile arc** with the parent's long-long-short rhythm baked into the dasharray
- **12 rays** radiating outward — kid energy + the daily-sunshine metaphor

- `assets/kidsnews-mark.svg` — light (ink on cream, gold disc)
- `assets/kidsnews-mark-dark.svg` — dark (white rays + ink face on gold disc)
- `assets/favicon-kidsnews.svg` — favicon-tuned (32px)

**Slogan**
- Hero: **"Little Daily, Big Magic!"** (the kid voice — "Big" not "Vast")

---

## 3 · Color tokens

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#1b1230` | Primary text, mark ink |
| `--cream` | `#fff9ef` | Page background |
| `--paper` | `#fffaf0` | Card surfaces |
| `--border` | `#ece2d0` | Hairline dividers, card borders |
| `--muted` | `#9a8d7a` | Secondary text, captions |
| `--gold` | `#ffc83d` | Sun accent — primary brand color |
| `--coral` | `#ff6b5b` | "news" highlight in kidsnews wordmark |

Per-vertical accent (replace `--gold` for siblings):
- `kidsnews` → `#ffc83d` (sun-gold)
- `ai` → `#5bb4ff` (sky-blue)
- `finance` → `#7cbf5a` (forest-green)
- `tech` → `#a78bfa` (slate-violet)

See `tokens.css` and `tokens.json`.

---

## 4 · Typography

| Role | Family | Weight | Notes |
|---|---|---|---|
| Display / serif | **Fraunces** | 500 (parent), 600 (kids II/I) | Variable axis: `opsz 144` for display, `opsz 9` for the kids eyes |
| Sans / UI | **Nunito** | 400 / 600 / 700 / 800 / 900 | "MINS" caps tracked at `0.34em` |

Google Fonts import (already in `fonts.css`):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700;9..144,800;9..144,900&family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
```

---

## 5 · React components

`react/Big21.jsx` and `react/SunFace21.jsx` are the canonical implementations. They scale off a single `size` prop and accept `ink`, `accent` (and `ray` for the sun-face).

```jsx
import { Big21 } from './react/Big21.jsx';
import { SunFace21 } from './react/SunFace21.jsx';

<Big21 size={120} />                                 // parent, default colors
<Big21 size={64} ink="#fff" accent="#ffc83d" />      // on dark

<SunFace21 size={200} />                             // kidsnews hero
<SunFace21 size={32} ray="#1b1230" />                // favicon — black rays for contrast
```

---

## 6 · Archived explorations

`assets/archive/` holds four earlier marks we explored before locking the final two. Kept for future reference if a vertical needs a different metaphor.

- `archive/clock-arc.svg` — clock dial with a "21-minute" sweep
- `archive/loop.svg` — geometric 2+1 forming a closed loop
- `archive/sunrise.svg` — half-disc sun rising over a horizon (the parent's earlier draft)
- `archive/dot-grid.svg` — 21 dots in a 3×7 grid (the daily tracker)

---

## 7 · Don't

- ❌ Don't recolor the parent mark with vertical accents — the parent stays sun-gold; verticals layer their accent **alongside** the parent.
- ❌ Don't use the kidsnews sun-face mark for the parent or other verticals — it's kid-specific.
- ❌ Don't change the long-long-short bar rhythm. It's the brand's signature.
- ❌ Don't substitute fonts. Fraunces + Nunito are load-bearing.
- ❌ Don't stretch or recolor the SVGs in CSS. Pass `ink` / `accent` / `ray` props (React) or edit the `<svg>` directly.

---

## 8 · File map

```
21mins-brand/
├── README.md                     ← this file
├── tokens.css                    ← CSS custom properties
├── tokens.json                   ← same tokens, JSON for build tools
├── fonts.css                     ← Google Fonts <link> + @font-face hints
├── assets/
│   ├── 21mins-mark.svg
│   ├── 21mins-mark-dark.svg
│   ├── favicon-21mins.svg
│   ├── kidsnews-mark.svg
│   ├── kidsnews-mark-dark.svg
│   ├── favicon-kidsnews.svg
│   └── archive/
│       ├── clock-arc.svg
│       ├── loop.svg
│       ├── sunrise.svg
│       └── dot-grid.svg
└── react/
    ├── Big21.jsx
    └── SunFace21.jsx
```
