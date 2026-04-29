# <YYYY-MM-DD> — <short slug>

> Copy this file to `docs/bugs/YYYY-MM-DD-<slug>.md` for a new bug record.
> Add a one-line entry to `docs/bugs/INDEX.md`. Reference the file path
> from your fix commit using a `Bug-Record:` trailer.

**Severity:** low | medium | high | critical
**Area:** pipeline | website | edge-fn | infra | …
**Status:** open | fixed | wontfix
**Keywords:** <comma, separated, terms, you'd, grep, for>

## Symptom

What the user (or monitor) saw. Quote their exact words / screenshot
filename if you have it. Include the exact URL, level, language, and
date the bug surfaced. Reproduction steps go here, not in Fix.

## Root cause

WHY this bug exists, written so a future session with no memory of
this one can understand it from a cold read. Name the subtle
invariant that was violated. Trace through the code path: file:line
references, what state was wrong at what moment, and why nothing
caught it earlier (no test, race window, etc.).

## Fix

Link to the PR / commit SHA. Then the *minimal* description of what
changed — file:line for each non-obvious touch. Anyone reviewing
this fix six months from now should be able to use this section as a
diff index.

- `path/to/file.ext:NNN` — what + why
- `path/to/other.ext:NNN-MMM` — what + why

## Invariant

The promise the fix makes. Future edits to this code path MUST NOT
violate this. State it as a rule, e.g.:

- "X must complete before Y is rendered"
- "Function F must accept Z=null without falling through to default"
- "Listing payload upload must precede search-index upsert"

If a later fix breaks this invariant, it is a regression — open a new
bug record that links back to this one.

## Pinning test

The smallest mechanism that makes a regression LOUD. One of:
- A unit/integration test (with file path and command to run it)
- A smoke-test script saved under `tests/smoke/` or `scripts/smoke/`
- A reproduction URL or admin tool path that visibly fails when
  the regression is back

If none, write "MANUAL: <30-second click-through that proves it works>".

## Related

- Other bug records this depends on or interacts with
- Linked design doc under `docs/superpowers/specs/`
- Linked gotcha entry in `docs/gotchas.md` (cross-reference the entry)
