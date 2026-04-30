# 2026-04-30 — mobile-responsive-grid-collapse

**Severity:** medium
**Area:** website
**Status:** fixed
**Keywords:** article, layout, responsive, mobile, grid, matchmedia, useIsNarrow, read-and-words, story-page, issue-6

## Symptom

User feedback (issue #6, feedback row 11, user level Tree, en, page
URL `https://kidsnews.21mins.com/`) on 2026-04-30:

> the story left side is too long comparing to right side. Maybe we
> can use scroll or adjust the left right ratio to make it more
> balance and easy to read.

The reporter is on iPhone Safari (~375-390px viewport, evident from
the admin's screenshot). On the article view's default Read & Words
tab, the layout still rendered its desktop two-column grid on a
phone, dividing a 375-500px viewport into a cramped body column
(~225-300px) and an even narrower aside (~140-180px). Visible on
the 500x844 BEFORE screenshot at `/tmp/before-mobile-article-fold.png`
captured during this fix: the headline wraps onto seven lines, the
Story body is a tall narrow column, and the Word Treasure aside is
clipped past the right edge. That is the imbalance the user
described.

## Root cause

`website/article.jsx` `ReadAndWordsTab` declared
`gridTemplateColumns: '1.6fr 1fr'` with no media query and no
responsive collapse. The codebase has zero existing matchMedia /
@media / breakpoint usage anywhere — every grid is laid out with
fixed `fr` ratios regardless of viewport. So on mobile, the desktop
1.6fr/1fr ratio is preserved unchanged, dividing whatever pixels are
available into two cramped columns.

The first attempt (PR #8, reverted) added `position: sticky` to the
right `<aside>`. That doesn't address column width at all — sticky
keeps the aside in view while you scroll, but the columns are still
side-by-side on a phone and still cramped. Wrong axis of fix.

The second attempt (PR #9, closed without merge) introduced
`useIsNarrow(768)` and the grid-collapse pattern below — the right
angle, but the PR was opened without rendering the page on a mobile
viewport, so the admin couldn't trust the fix worked. That is what
this third attempt corrects: same code shape, plus actual visual
verification at 390px and 1280px viewports captured to `/tmp` before
opening the PR.

## Fix

PR: opened against `main` from branch `fix/issue-6-mobile-grid-collapse-v2`. Closes #6.

- `website/article.jsx:4-26` — adds `useIsNarrow(maxWidth)` hook.
  Reads `window.matchMedia(query).matches` for initial state and
  subscribes to `change` events so the layout reflows on rotate /
  resize without reload. Falls back to deprecated `addListener` for
  Safari < 14. Returns false in non-browser environments so SSR /
  build-time evaluation does not crash. The codebase had zero
  existing matchMedia callers, so this is net-new helper, scoped
  to `article.jsx` until a second caller appears (then move to
  `website/components.jsx`).
- `website/article.jsx:558-560` — `ReadAndWordsTab` calls
  `useIsNarrow(768)` and switches `gridTemplateColumns` between
  `'1fr'` (single stacked column) when narrow and `'1.6fr 1fr'`
  (the original two-column desktop layout) when wide. 768px is the
  conventional tablet/mobile breakpoint.

Scoped intentionally to `ReadAndWordsTab` only. Other tabs
(`BackgroundTab`, `QuizTab`, `MyTakeTab`) and the home / search
views also use rigid `fr` grids and likely have similar mobile
cramping — out of scope here, called out below.

## Invariant

`ReadAndWordsTab`'s grid MUST collapse to a single column on
viewports ≤768px. Future edits to the grid-template at
`article.jsx:560` MUST keep the `isNarrow ? '1fr' : ...'` ternary
(or an equivalent media query) — replacing it with a fixed
multi-column ratio re-introduces the cramped mobile layout that
issue #6 reported and that PRs #8 and #9 failed to address.

`useIsNarrow` MUST remain defined before any function that calls it
in render. It is a normal hook and must not be called conditionally.

## Pinning test

MANUAL (60s click-through, captured during this fix):

1. `cd website && python3 -m http.server 8765` (or a Vercel preview).
2. Resize browser to 390x844 (iPhone-ish portrait). Open any article
   on the Read & Words tab. The grid MUST stack to a single column
   — Story full-width on top, Word Treasure full-width below. The
   headline must NOT wrap into seven lines, and the Word Treasure
   keyword cards must be fully visible (not clipped past the right
   edge).
3. Resize to 1280x800 desktop. The same view MUST reflow back to
   the original two-column 1.6fr/1fr layout (Story left, aside
   right) without a page reload — proves the matchMedia `change`
   listener is wired up.

Reference screenshots captured against this fix and embedded in the
PR description: `before-mobile-article-fold.png` (broken, prod
without fix) vs `after-mobile-article-fold.png` (fixed, this branch
served locally).

## Related

- PR #8 (`fix(article): make Read & Words right aside sticky`) —
  reverted by `3970994`. Wrong axis of fix; sticky keeps the aside
  in view while scrolling but does not reflow column widths on a
  phone.
- PR #9 (`fix(article): collapse Read & Words grid to single
  column on mobile`) — closed without merge. Same code shape as
  this PR but skipped visual verification, which the admin could
  not trust. The kidsnews-bugfix skill was updated (commit `a4e3c8e`
  on the self-skills repo) to mandate Chrome DevTools MCP screenshots
  at mobile + desktop widths BEFORE opening any layout PR.
- Other tabs in `article.jsx` (`BackgroundTab` ~line 820, `QuizTab`
  ~line 988, `MyTakeTab` ~line 1242) and `home.jsx`'s search /
  archive grids all use rigid `fr` ratios and likely show the same
  cramping on mobile. Each is its own separate fix; the
  `useIsNarrow` helper here is the building block they should reuse,
  and once a second caller lands the helper should move to
  `website/components.jsx`.
