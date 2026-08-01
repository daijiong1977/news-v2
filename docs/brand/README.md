# 21mins brand system

The brand kit for **21mins** (parent brand) and **kidsnews · 21mins** (first vertical).

**Committed here 2026-07-31 to stop it being a single uncommitted copy.** Until then these files sat
untracked in `~/myprojects/kidsnews-v2-snapshot/` — a scratch directory — and existed **nowhere else on
disk and in no repo**. Only the *applied output* (4 SVG marks + `website/tokens.css`) had ever made it
into git; the system that produced them had not.

## Provenance

Authored **2026-04-25 on claude.ai** (web), not in Claude Code — the companion iOS spec states its
source as *"chat handoff from claude.ai/design"*. **That session is not recoverable**: the earliest
Claude session transcript on this Mac starts 2026-06, and a full search of local transcripts for these
filenames returns nothing. The files are the only record of that work.

## What's here

| Path | What |
|---|---|
| `kit/README.md` | the brand book — logos, slogans, color, type, voice |
| `kit/CLAUDE_CODE_PROMPT.md` | step-by-step prompt to wire the kit into the kidsnews-v2 codebase |
| `kit/tokens.css` · `kit/tokens.json` | design tokens |
| `kit/fonts.css` | type stack (Fraunces + Nunito) |
| `kit/assets/` | logo SVGs — 21mins mark, kidsnews sun mark, favicons, light + dark |
| `kit/audit/index.html` | BEFORE/AFTER spec for every screen |
| `kit/preview.html` | the kit rendered on one page |
| `iOS-DESIGN-BRIEF.md` | one-page brief for a designer/non-technical reader |
| `PROJECT-SUMMARY.md` | the deeper technical companion |

## The system

**21mins** is a family of daily learning rituals — one subject, one finite session, one habit. Slogan
*"Little Daily, Vast Magic."*; long form *"21 minutes. Every day. The magic compounds."* The sun is the
metaphor. **kidsnews** is the first vertical (news literacy, ages 8–13); **ai / finance / tech** are
planned verticals sharing the skeleton with their own accent colour.

The kidsnews mark reuses the parent's DNA: Roman **II + I** as eyes (the "21" reframed for kids), MINS
as the nose, a smile arc carrying the parent's long-long-short bar rhythm, 12 rays.

## Status — the brand DID ship

Live at [kidsnews.21mins.com](https://kidsnews.21mins.com) and [news.6ray.com](https://news.6ray.com),
titled *"kidsnews · today's 21 minutes"*. In this repo: `website/tokens.css` and the four marks under
`website/assets/`.

What has **not** shipped is the rest of the system — the full brand book, the screen-by-screen audit,
and the planned ai/finance/tech verticals. That is what this folder preserves.

## Related

- **iOS app:** `~/myprojects/21mins-ios/` — a real SwiftUI Xcode project (10 commits, 128 files) built
  from `iOS-DESIGN-BRIEF.md` on 2026-04-26. ⚠️ It has **no git remote**; archived to
  `~/archives/repos/21mins-ios.bundle` on 2026-07-31.
- Vault note: `brain/wiki/topics/news-ohye.md`.
