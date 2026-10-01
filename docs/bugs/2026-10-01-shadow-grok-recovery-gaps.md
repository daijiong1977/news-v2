# 2026-10-01 — shadow Grok recovery gaps

**Severity:** high
**Area:** shadow pipeline
**Status:** fixed offline
**Keywords:** fallback_pending, native provenance, four drafts, discovered history, cached refill

## Symptom

Grok review of 6d9d2d3 identified recovery gaps; four classes were independently
reproduced offline. Legacy fallback_native plus an older revision HTTP answer
returned that same content with native provenance. Five fallback drafts passed.
Stale history review omitted discover IDs. Fetch cap stopped before cached evidence.

## Root cause

The fallback sentinel was saved before old-answer quarantine, but resumption
treated the sentinel as proof of a native answer. Four-draft constraints were
instructions only. Stale review read initial input rather than current catalog,
and used a different archive field than prepare. A fetch cap used break/early
return, conflating inability to download with inability to use existing evidence.

## Fix

Feature PR https://github.com/daijiong1977/news-v2/pull/86; runtime PR #1.

- agent_shadow_providers.native_fallback: pending sentinel, repeatable quarantine,
  no relabelled old HTTP answer, and explicit visible four-draft override.
- agent_shadow.ask: enforce native fallback four-draft cap without changing ID.
- registry_history/check_stale: merge current discover IDs/final routing and share
  archived/is_archived exclusion; frozen publication-date exclusion remains.
- AutonomousEditor.pool/extend and BatchEditor.extend: cached unconsumed eligible
  originals remain usable after cap, with no further fetch or counter reset.

## Invariant

- A fallback marker is not proof of a newly written native answer.
- The request ID remains frozen; five HTTP drafts remain valid, native at most four.
- Every discover candidate participates in stale history recheck in its final section.
- A download cap does not invalidate already cached eligible evidence.
- Settled drafts/categories and persistent budgets are preserved; production untouched.

## Pinning test

pipeline/test_agent_shadow_grok_fixes.py: 8 instances all failed before the patch,
then passed; Python3.10 related suite 227 passed. Includes quarantine write-failure
injection, legacy/pending recovery, actual native five-to-four correction handoff,
discover/archive/frozen-date history, and cached originals/refill at the cap.
No real model, DB write, deployment or mail.

## Related

- docs/KIDSNEWS-GROK-FOLLOWUP-2026-10-01.md
- docs/KIDSNEWS-HYBRID-RESUME-REVIEW-2026-09-30.md
- docs/bugs/2026-10-01-shadow-http-resume.md
