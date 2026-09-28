# News/Fun whole-catalog selection experiment — 2026-09-28

## Scope

Keep the existing JEV screening, routing, same-event checks and full candidate
catalog. News already sends up to 29 JEV-qualified candidates to one DeepSeek
numeric-only comparison, then offers six to the main curator. This change
extends that optional comparison to **Fun only** when there are more than
seven candidates above Fun's JEV quality floor (0.50). Science is unchanged.

Fun's DeepSeek answer is a complete permutation of local numbers; no returned
title or other model-authored article data is trusted. The full catalog stays
available for Stage-3 backfill. A malformed answer or API failure preserves
JEV's order and send flags. An underfilled Fun pool skips the extra call.
The existing curator, rewrite, seven-day history guard and independent
full-text child-safety review still decide what can publish. No new DeepSeek
final-three call was added: the curator already compares the shortlisted
items; a second model call would not fix a thin source pool.

## Read-only checkpoint replay

| Date | Fun JEV catalog | At/above 0.50 | Extra Fun DeepSeek call with new gate |
| --- | ---: | ---: | --- |
| 2026-09-26 | 10 | 5 | skipped |
| 2026-09-27 | 13 | 4 | skipped |
| 2026-09-28 | 14 | 4 | skipped |

The 2026-09-28 local exploratory replay *without* the gate made two real
DeepSeek comparisons of the saved 14-title Fun catalog. One only swapped
the order of the top two already-JEV-qualified candidates; the other placed
a consumer-earbud product story third. That is not a case for relaxing the
JEV floor. The gated production code would make **zero** extra model calls
for that checkpoint and would retain the original four-item shortlist.

The user's historical JEV dashboard figure of about $0.005/day is a reason
to retain the existing JEV editorial checks. The anomalous ~$0.04 day had
two complete pipeline runs and a 503/60-second JEV prefilter timeout; Actions
logs do not disclose itemized JEV charges. This PR does not claim to reduce
JEV cost. See `docs/bugs/2026-09-28-jev-spend-and-offpeak-schedule.md` in
the separate schedule PR for the run-by-run audit.

## Verification and risk

- Unit tests cover full permutation validation, 29-item cap, preserved deep
  spares, malformed-response fallback, thin-pool no-call, and curator input.
- The September 26–28 checkpoints exercise the no-call path. A richer Fun
  day with >7 qualified candidates is still needed to verify model impact in
  production; until then this is a conditional feature, not a demonstrated
  improvement in published article quality.
- News and Science selection, JEV call counts, and independent safety
  thresholds are unchanged.
