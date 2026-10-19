# 2026-10-02 — shadow candidate quality

**Severity:** high
**Area:** shadow
**Status:** fixed on feature branches; not merged or deployed
**Keywords:** Pokemon, same-event, advertorial, affiliate, Time for Kids, related articles

## Symptom

The Fun 25-summary experiment selected two Pokemon stories covering the same World Championships, and retained a best-cat-trackers shopping comparison as reserve eight. TFK originals included unrelated related-card summaries, inflating the original word count.

## Root cause

Shortlist dedup trusted only model event keys; tournament and anniversary wrappers received different keys. Shopping/affiliate signals lacked a deterministic gate. Shadow generic extraction searched beyond the TFK main body into related cards, and the collection counted that text before photo qualification.

## Fix

PR: https://github.com/daijiong1977/news-v2/pull/86; Bot snapshot https://github.com/daijiong1977/grokbot-kidsnews/pull/1.

- `agent_shadow_candidate_quality.py`: commercial signals, DOM contamination check, and ranked named-event/content-overlap filtering.
- source-first collection/editor: reject metadata ads before body, body disclosures/contamination before photo, and cached unsuitable originals before ranking.
- shortlist: preserve higher ranking and promote reserves; audit dropped ID and retained ID without rewriting model answers.
- rank prompt: overlapping championship coverage is not distinct because its wrapper changes; ads are not reserves.

## Invariant

Do not count contaminated TFK extraction or advertising as mechanical passes. Do not ban a whole publisher or franchise. Same named event/year retains one higher-ranked representative; different years/events survive. Related-card references must not turn an unrelated author interview into a duplicate. Only shadow paths change; production cleaner and pipeline stay untouched.

## Pinning test

`pipeline/test_agent_shadow_candidate_quality.py`: 14 new regressions first reproduced failures, then passed. Full relevant Python 3.10 suite: 317 passed, two existing warnings. Real cached Pokemon replay removes the lower-ranked anniversary wrapper but preserves the author reserve; two public TFK pages fail the pollution gate. No real model call or publication for this fix.

## Related

[Full rules and limitations](../KIDSNEWS-CANDIDATE-QUALITY-2026-10-02.md).
