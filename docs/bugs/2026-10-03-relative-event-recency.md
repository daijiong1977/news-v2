# 2026-10-03 — Relative event recency at final editing

Severity: medium; Area: three-stage source-first editor; Status: fixed on feature branch.

## Gap

The Python source gate recognizes publication dates and explicit dated lead events, but not reliably indirect phrases such as “three weeks ago.” A newly posted page about an old event could reach the fixed five and be rewritten as a current Fun or News story.

## Change

New source journals freeze `semantic_event_recency: true`. The existing one-article Codex final-edit call examines the **main** event relative to the run date: News at most three America/New_York calendar days, Fun at most seven. It returns a complete, accurately historical article even when stale. Python defers it while trying fresh candidates from the same fixed five. If the fresh pool is short, a safety/quality-qualified historical article can fill a slot with an explicit `ready_stale_fallback` warning for editorial follow-up. The first group ordering also prefers current events. Science remains exempt. Existing journals without the new flag keep their original request/answer contract on resume. No extra model call is introduced for a valid article. The release still cannot fabricate a third article if all five fail safety, factual, or structural gates.

This is a model judgment, not a guarantee of accurate temporal interpretation. The explicit-date Python gate remains the deterministic first line of defense. The reviewer must not treat a historical background date as the main event or recast an old event as current.

## Verification

`pipeline/test_source_first_review_finish.py` covers historical marking, missing freshness verdict, and an older checkpoint. `pipeline/test_kidsnews_python.py` covers fresh-first reserve promotion and explicit historical fallback when fewer than three current candidates pass. Python 3.10 tests are offline; no model, site, or database was called.
