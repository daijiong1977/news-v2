# News/Fun whole-catalog selection experiment — 2026-09-28

## Scope

Keep the existing JEV screening, routing, same-event checks and full candidate
catalog. News already sends up to 30 JEV-qualified candidates to one DeepSeek
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

- Unit tests cover full permutation validation, 30-item cap, preserved deep
  spares, malformed-response fallback, thin-pool no-call, and curator input.
- The September 26–28 checkpoints exercise the no-call path. A richer Fun
  day with >7 qualified candidates is still needed to verify model impact in
  production; until then this is a conditional feature, not a demonstrated
  improvement in published article quality.
- Science selection, JEV call counts, and independent safety thresholds are
  unchanged. News comparison gains one candidate at the former 29-item edge.

## First-cut tuning in this PR

JEV remains the first content-aware screen: it rejects only the calibrated
clear-cut headline classes, then the body probe and JEV editorial score create
the de-duplicated candidate catalog. News and Fun each offer at most the first
**30** JEV-ranked candidates to the numeric DeepSeek comparison; this is **per
section**, not 30 shared across sections. Any deeper catalog entry remains
available to safe Stage-3 refill. On the September 28 checkpoint, News had 32
unique JEV catalog entries, while Fun had only 14; the cap affects only News
there, and Fun's >7-qualified gate still skips the extra model call.

The JEV editorial pass formerly requested a five-level `want` answer for every
brief, then never read it for ranking, selection, routing or refill. Removing
that question preserves every decision rule while reducing the answer work per
scored brief. The optional prefilter previously waited up to 60 seconds before
failing open on a degraded JEV service; its budget is now 15 seconds. On a
timeout it keeps all candidates (other than the local live-blog regex), and
the downstream independent full-text safety review remains mandatory.

This is a bounded latency and unused-question cleanup, **not** a measured
reduction of the anomalous $0.04 JEV charge. The normal prefilter finished in
about 3–4 seconds in the observed runs; billing needs a later dashboard check
after one natural run. DeepSeek's marginal cost for the 30th News item is
small but nonzero. No production rerun or content replacement was performed.
