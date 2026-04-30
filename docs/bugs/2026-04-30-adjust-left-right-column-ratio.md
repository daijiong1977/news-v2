# 2026-04-30 — adjust-left-right-column-ratio

**Severity:** low
**Area:** website
**Status:** fixed
**Keywords:** article, layout, sticky, aside, read-and-words, story-page, scroll, balance

## Symptom

User feedback (issue #6, feedback row 11, user level Tree, en) on
2026-04-30:

> the story left side is too long comparing to right side. Maybe we
> can use scroll or adjust the left right ratio to make it more
> balance and easy to read.

The Read & Words tab of the article view (`ReadAndWordsTab`) renders
the article body in a left column ("The Story", 250-340 words) next
to a right `<aside>` containing 3-5 keyword cards plus an optional
"Why it matters" panel. At desktop widths the body column is 4-6×
taller than the aside, so once the user scrolls into the body the
keyword glossary scrolls off-screen and they lose the in-context
hint cards the design depended on.

## Root cause

`website/article.jsx:530` lays the tab out as
`gridTemplateColumns: '1.6fr 1fr'`. The right `<aside>` had no
`position: sticky`, so by default its grid item stretched to the
row height (`align-self: stretch`) and scrolled with the body.
Functionally correct but visually unbalanced; the keyword glossary
is referenced from the highlighted words in the body, but once the
user is mid-paragraph the glossary is no longer visible.

A nearly identical sticky pattern was already used elsewhere in
`article.jsx` (line 990, the quiz tab's "Look back at the story"
panel uses `position:'sticky', top:90, maxHeight:'calc(100vh - 110px)', overflow:'auto'`),
so the pattern was a known good fit — just hadn't been applied to
the Read & Words aside.

## Fix

PR: opened against `main` from branch `fix/issue-6-sticky-aside`.

- `website/article.jsx:561` — added `position:'sticky', top:90, alignSelf:'start', maxHeight:'calc(100vh - 110px)', overflow:'auto'` to the `<aside>` style. `alignSelf:'start'` is required so the grid item is content-height (not stretched), otherwise sticky just sits at the top of a full-height cell and never sticks. `top:90` matches the sticky header offset already used at line 990.

## Invariant

In `ReadAndWordsTab`, the right aside MUST stay in view while the
user scrolls the long body. If a future edit introduces a parent
container with `overflow: hidden | auto | scroll` between the
sticky aside and the page viewport, sticky will silently break.
The aside's grid item must remain content-sized (`align-self: start`
or equivalent) — switching it back to stretched will also break
sticky.

## Pinning test

MANUAL: open any article, stay on the default Read & Words tab,
scroll the page down. The Word Treasure / Why it matters panel
on the right must remain visible at the top of the viewport while
the story scrolls. If the right column scrolls away with the body,
the sticky pattern has regressed.

## Related

- `website/article.jsx:990` — pre-existing sticky pattern (quiz
  tab's "Look back at the story") that this fix mirrors.
