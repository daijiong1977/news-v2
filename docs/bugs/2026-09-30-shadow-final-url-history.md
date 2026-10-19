# 2026-09-30 — shadow-final-url-history

**Severity:** medium
**Area:** shadow pipeline
**Status:** fixed (feature branch only, not production)
**Keywords:** autonomous, redirect, final-url, history, dedup

## Symptom

Offline review found a candidate's initial URL could be new while its HTTPS redirect
resolved to an article already in the same category's seven-day history. The autonomous
body pool admitted it when the Agent supplied history_status=clear. No live publication
or real model was involved in reproduction.

## Root cause

AutonomousEditor.pool compared the initial feed/discovery URL before fetching. After
the fetch it recorded evidence_url and publisher host but did not repeat the mechanical
history check against that final URL. Semantic event review should not be the only
defense against an exact source-URL duplicate.

## Fix

PR: https://github.com/daijiong1977/news-v2/pull/86

- pipeline/agent_shadow_autonomous.py, AutonomousEditor.pool: canonicalize final evidence
  URL, block same-category historical and current pool URLs, record url_exclusions, and
  emit final evidence_url as the article's source link.
- pipeline/test_agent_shadow_autonomous.py: reproduce the redirect with a fake fetch.
- docs/KIDSNEWS-AUTONOMOUS-SHADOW.md: document final-URL gate and test count.

## Invariant

Every fetched final source URL must be checked mechanically against its final category's
history and the current original pool, even when the initial URL was clear. Redirects
must not bypass seven-day history. Final text/event/safety review remains mandatory.
This change does not alter production full_round/news_rss_core.

## Pinning test

`test_redirected_original_url_cannot_bypass_same_category_history` first failed on the
new autonomous implementation, then passed after the final-URL gate. Python3.10.20:
132 offline tests pass across shadow and related regressions; new autonomous suite23.

```sh
python -m pytest -q -p no:cacheprovider pipeline/test_agent_shadow_autonomous.py
```

## Related

- ../KIDSNEWS-AUTONOMOUS-SHADOW.md
- 2026-09-27-storm-repeat-history-gate.md
