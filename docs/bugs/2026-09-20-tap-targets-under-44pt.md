# 2026-09-20 — interactive controls smaller than a fingertip

**Severity:** low
**Area:** website
**Status:** fixed
**Keywords:** tap target, touch target, 44pt, accessibility, mis-tap, dismiss button, close button, back button, phone

## Symptom

Found by a scripted sweep of every main surface at 390px and 440px, not by a
report. Three controls a reader taps are smaller than Apple's 44×44pt minimum:

    ×  dismiss on the streak banner   23 × 26
    ×  close on the feedback modal    22px glyph, no padding
    ←  back on the search page        32 × 30

The dismiss button is the one that matters: it sits immediately beside the
"Sign in →" button, so a finger aimed at ✕ that lands 10px left starts a
Google sign-in the reader did not want. The audience is children, whose aim is
less precise than the adult hands this was built and reviewed with.

## Root cause

Every one of these is an icon-only button styled with a font size and a few
pixels of padding — `padding:'4px 6px', fontSize:18`. That sizes the *glyph*,
and the button's box is whatever the glyph plus padding comes to. On a mouse
that is fine; a cursor is a single pixel. A fingertip needs roughly 44pt, and
nothing in the codebase stated that minimum, so each icon button was sized by
eye at desktop width.

Not a regression — these were always this size. It surfaced now because the
sweep added a rule for it.

## Fix

Branch `tap-targets`. Each control gets `minWidth:44, minHeight:44` with
`display:'inline-flex'` and centred content, and its padding drops to 0. The
glyph renders at exactly the same size; only the area that accepts a finger
grows. The footer's legal links (63×16, 47×16) get `lineHeight:1.9` for the
same reason.

## Prevention

Icon-only buttons need a stated minimum box, not just a font size. The sweep
in this session checks for buttons under 32px in either dimension and is worth
re-running after layout work — its other rules are this week's two bugs turned
into detectors (a `grid-column: span 2` child inside a single-column grid, and
a text node under 60px wide in a tall box).
