# Shadow HTTP recovery, budgets and native fallback

Severity: high. Status: fixed on feature branches only; VM quality unverified.
PRs: news-v2 #86 and grokbot-kidsnews #1. Production paths remain unchanged.

## Root causes

Every HTTP exception left an attempting sentinel that permanently blocked same-directory
recovery, including explicit HTTP errors. Answer and complete state were separate commits.
A one-hour wall clock blocked resumable tasks. News importance/Science publisher quotas
could chase unavailable candidates and starve other sections through one shared fetch budget.
Batch priority treated an omitted top-importance source as an invalid whole group.
CLI recovery named the wrong interpreter; status competed for locks and threw hash failures.

## Fix / invariants

Classify transport failure conservatively; cap retries/Retry-After and keep cost reservations.
Use matching atomic answer.json as commit record, preserve first answer and rebuild audit.
Uncertain transport never automatically resends HTTP. Explicit frozen native fallback preserves
request ID, writes four batch drafts and reports same-model self-check/mixed provenance.
Two consecutive fallback runs trip a runtime circuit breaker; budgets survive all restarts.
After 24 hours require explicit confirmation and fresh same-category seven-day history recheck,
without changing publication date. Fetch caps are 12 per section; only attempt quota improvements
when untried qualified candidates exist. Logs are best-effort; evidence and fetch audit atomic.
Safe status is lock-free and reports answer_integrity; rerun uses sys.executable.

## Red -> green evidence

Initial new review suite: 12 failed/1 passed before B1/B2/B3/S7/B5/B6 fixes.
B4/B7/logging subset: 4 failed before fixes. Stale/audit/provenance subset: 3 failed.
Per-category exhausted refill and malformed HTTP envelope probes each failed before correction.
Python 3.10.20 final relevant suite: 219 passed (29 new tests/probes); two known dependency/runpy
warnings, no failures. Real CLI test proves single-line JSON and exits 2 -> 0 -> 1.
No real model calls, DB writes, deployment, email, production edits or merge were performed.
P1–P5 remain production blockers and require a separate task after VM shadow validation.

Tests: pipeline/test_agent_shadow_resume.py. Detailed item mapping: review document.
