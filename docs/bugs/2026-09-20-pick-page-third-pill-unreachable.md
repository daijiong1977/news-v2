# 2026-09-20 — pick page's third category pill unreachable on a phone

**Severity:** medium
**Area:** website
**Status:** fixed
**Keywords:** pick page, PickFlow, tracker pills, minWidth, flex, overflow, News Science Fun, 390px, iPhone

## Symptom

On an iPhone (390 CSS px) the "Pick your story" flow shows three tracker
pills — News / Science / Fun — that double as navigation back to a category
already visited. The Fun pill was cut off at the right edge of the screen and
could not be scrolled to or tapped. A reader who wanted to change their Fun
pick had to restart the flow.

Reported as "这个 pickup 页面好像对手机也非常的不友好，选起来挺麻烦的".

## Root cause

`website/home.jsx`, the tracker row inside `PickFlow`:

    <div style={{display:'flex', gap:8}}>
      ... three <button> each with minWidth:130

Three pills at 130px plus two 8px gaps is 406px. A 390px viewport minus the
page gutter leaves about 366px. The row had no `flexWrap`, no `overflowX`,
and the pills had no `flexShrink`, so the third one simply rendered past the
right edge — and after the responsive pass added `overflow-x: hidden` to the
body on phones, it was clipped rather than reachable by sideways scrolling.

The invariant: a horizontal strip whose items have a fixed minimum width must
declare what happens when they do not fit. Three ways out — wrap, scroll, or
shrink — and this row declared none, so the browser picked the one that loses
content.

Nothing caught it because the whole site was built and reviewed at laptop
width, where 406px is comfortable.

## Fix

Branch `pick-page-mobile`. The strip gets `overflowX:'auto'` with
`WebkitOverflowScrolling:'touch'` and a hidden scrollbar, and the pills get
`flexShrink:0` plus `minWidth: narrow ? 104 : 130` so all three fit a 390px
screen without scrolling at all. Verified in-browser: the Fun pill's right
edge is inside the viewport at 390px.

## Prevention

When a row of fixed-width items can exceed the viewport, say which of wrap /
scroll / shrink applies. Checking layouts at 390px — the narrowest phone in
common use — catches this class before it ships.
