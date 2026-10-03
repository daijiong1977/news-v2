# 2026-10-03 — Relative event recency at final editing

Severity: medium; Area: three-stage source-first editor; Status: fixed on feature branch.

## Gap

The Python source gate recognizes publication dates and explicit dated lead events, but not reliably indirect phrases such as “three weeks ago.” A newly posted page about an old event could reach the fixed five and be rewritten as a current Fun or News story.

## Change

New source journals freeze `semantic_event_recency: true`. The existing one-article Codex final-edit call must examine the **main** event relative to the run date: News at most three America/New_York calendar days, Fun at most seven. It may return a short stale-event rejection instead of rewriting. Python persists that rejection, tries the next candidate from the same fixed five, and stops publication if fewer than three acceptable stories remain. The first group ordering also prefers current events. Science remains exempt. Existing journals without the new flag keep their original request/answer contract on resume. No extra model call is introduced for a valid article.

This is a model judgment, not a guarantee of accurate temporal interpretation. The explicit-date Python gate remains the deterministic first line of defense. The reviewer must not treat a historical background date as the main event or recast an old event as current.

## Verification

`pipeline/test_source_first_review_finish.py` covers relative-date rejection, missing freshness verdict, and an older checkpoint. `pipeline/test_kidsnews_python.py` covers reserve promotion after a semantic stale rejection. Python 3.10 tests are offline; no model, site, or database was called.
