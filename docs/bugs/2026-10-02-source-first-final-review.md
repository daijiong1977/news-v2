# 2026-10-02 — source-first final review

**Severity:** high
**Area:** shadow pipeline / website release
**Status:** fixed
**Keywords:** source-first, resume, immutable-body, detail-status, manifest, history

## Symptom / Root cause

Final Spec/code review reproduced interrupted prepare reading a missing connector snapshot, detail-only repair replacing good bodies, and the official reader mapper discarding the omitted-details marker. Incremental selection lost ready-article context and final-category history metadata. Release recovery froze ZIP but not manifest; packaging checked body evidence but skipped title/card fields.

## Fix

Feature PR86, exported to Bot PR1. Full issue/location/test matrix:
[Final review](../KIDSNEWS-SOURCE-FIRST-FINAL-REVIEW-2026-10-02.md).
No production main merge, real model, database write or deployment.

## Invariants

- Frozen prepare context and original start time survive interruption.
- Feed and redirected URLs both participate in final-section history checks; retired catalog entries retain routing.
- Detail repair never changes a passing body/self-check or another passing detail level.
- Public reader availability uses the fetched detail_status, not an unpopulated state field.
- Resume and rollback identify both ZIP and manifest; quote mismatch remains warning, numeric evidence remains hard.

## Pinning tests

pipeline/test_source_first_review_collection.py (6), test_source_first_review_finish.py (5), test_source_first_review_publish.py (6 instances).
Python3.10 related full suite:235 passed, two pre-existing warnings. Runtime export reruns the same suite.
