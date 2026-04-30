# 2026-04-30 — mobile-responsive-grid-collapse

**Severity:** medium
**Area:** website
**Status:** fixed
**Keywords:** article, layout, responsive, mobile, grid, matchmedia, useIsNarrow, read-and-words, story-page

## Symptom

User feedback (issue #6, feedback row 11, user level Tree, en, page
URL `https://kidsnews.21mins.com/`) on 2026-04-30:

> the story left side is too long comparing to right side. Maybe we
> can use scroll or adjust the left right ratio to make it more
> balance and easy to read.

The reporting user was on mobile (iPhone Safari, ~375px viewport —
visible from the admin's screenshot of the same view). On the
article view's default Read & Words tab, the layout still rendered
its desktop two-column grid on a phone, so the body got ~225px of
horizontal space and the aside got ~140px. The body became a tall,
skinny column of broken-up paragraphs while the aside stayed short
— exactly the "left too long compared to right" imbalance.

## Root cause

`website/article.jsx:561` (post-fix line; was `:530` pre-fix) declared
`gridTemplateColumns: '1.6fr 1fr'` with no media query and no
responsive collapse. The codebase has zero existing matchMedia /
@media / breakpoint usage anywhere — every grid is laid out with
fixed `fr` ratios regardless of viewport. So on mobile, the desktop
1.6fr/1fr ratio is preserved unchanged, which divides a 375px
viewport into two cramped columns.

The previous attempt (PR #8, reverted) added `position: sticky` to
the right `<aside>`. That didn't address the cramped two-column
problem at all — sticky just keeps the aside in view while you
scroll, but the columns are still side-by-side and still cramped on
a phone. Wrong axis of fix entirely.

## Fix

PR: opened against `main` from branch
`fix/issue-6-mobile-responsive-grid`. Closes #6.

- `website/article.jsx:9-27` — added `useIsNarrow(maxWidth)` hook.
  Reads `window.matchMedia(...).matches` for initial state and
  subscribes to `change` events for live updates (so the layout
  reflows if the user rotates the device or resizes the browser).
  Falls back to the deprecated `addListener` API for Safari < 14.
  Returns false in non-browser environments so SSR / build-time
  evaluation never crashes.
- `website/article.jsx:559` — `ReadAndWordsTab` calls
  `useIsNarrow(768)` and switches `gridTemplateColumns` between
  `'1fr'` (single column, stacked) when narrow and `'1.6fr 1fr'`
  (the original two-column layout) when wide. The 768px breakpoint
  is the conventional tablet/mobile boundary; below it the body
  card and the aside (Word Treasure + optional "Why it matters")
  each get full viewport width and stack vertically.

The change is scoped intentionally to `ReadAndWordsTab` only. Other
tabs (`BackgroundTab`, `QuizTab`, `MyTakeTab`) and the search/home
views also use rigid `fr` grids and likely have similar mobile
cramping, but those are separate fixes — see Related.

## Invariant

`ReadAndWordsTab`'s grid MUST collapse to a single column on
viewports ≤768px. Future edits to the grid-template at
`article.jsx:561` MUST keep the `isNarrow ? '1fr' : ...'` ternary
(or an equivalent media query) — replacing it with a fixed
multi-column ratio re-introduces the cramped mobile layout that
issue #6 reported.

`useIsNarrow` MUST remain defined before any function that calls it
in render (currently only `ReadAndWordsTab`). It is a normal hook
and must not be called conditionally.

## Pinning test

MANUAL (30s click-through):
1. Open any article in a browser at desktop width — the Read &
   Words tab should still render two columns (story on left, Word
   Treasure on right) at the existing 1.6fr/1fr ratio.
2. Resize the browser narrower than 768px (or open Chrome DevTools
   device-toolbar at iPhone 12, 390x844). The two columns must
   reflow into a single stacked column: story body full-width on
   top, Word Treasure (and "Why it matters" if present) full-width
   below.
3. Resize back wider than 768px without reloading — the layout
   must reflow back to two columns. (This proves the matchMedia
   `change` listener is wired up; if it stays single-column even
   at desktop width after a resize, the listener regressed.)

## Related

- PR #8 (reverted on 2026-04-30) — the previous, wrong-angle attempt
  at this issue. Added `position: sticky` to the aside; the admin
  rolled it back. Don't revisit that approach without first stacking
  on mobile.
- `website/article.jsx:840`, `:1008`, `:1262` (approximate; was
  `:820 / :988 / :1242` pre-fix, lines shift with the new hook block)
  — `BackgroundTab`, `QuizTab`, `MyTakeTab` use the same fixed-fr
  grid pattern and likely cramp on mobile in the same way. Out of
  scope for this PR; can reuse `useIsNarrow` when each is fixed.
- `website/home.jsx`, `website/parent.jsx` — also have rigid grids
  with no responsive collapse.
- `~/myprojects/lessons/universal-patterns.md` — the
  "responsive-collapse-on-mobile" pattern would belong here once a
  second project hits the same trap.
