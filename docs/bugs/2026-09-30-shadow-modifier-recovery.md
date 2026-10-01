# 2026-09-30 — News hybrid draft recovery

**Severity:** high
**Area:** shadow pipeline
**Status:** fixed (offline; VM validation pending)
**Keywords:** DeepSeek, invalid JSON, AnswerRejected, modifier, facts_supported

## Symptom

news-hybrid-1 stopped at rewrite-News-c041: malformed JSON was repaired once, then middle had 281 words, outside 300–410. Only one News had passed and five had factual rejections. The accepted English draft contained Chinese characters.

## Root cause

One global correction budget conflated syntax repair with content repair. AnswerRejected declared by both __main__ execution and pipeline.agent_shadow import produced distinct classes, so the editor did not catch real CLI failures. In-process mocks missed this. Reviewer-only handling discarded fixable attribution/quote/qualifier defects; English lacked a language guard. HTTP usage overwrote prior attempts.

## Fix

PR #86; runtime PR #1. agent_shadow_errors.py provides the shared exception. Only news-deepseek gets one format + one content repair, with prior answer and per-attempt usage. agent_shadow_modifier.py edits from evidence and judges the final corrected draft; editor validates/saves it or replaces a failed draft. New runs skip the old audit; legacy factual rejects get one modification opportunity. Corrected English rejects Chinese contamination. No production change, third audit, real model call, DB write or deployment.

## Invariant

- At most three HTTP attempts: initial, one formatting repair, one content repair.
- Exhausted draft/invalid modifier is article-level fallback, also through python -m.
- Scores/facts/event judgments refer to corrected text. No invented evidence; safety/history/word gates retained.
- Modifier self-check is not an independent audit of its own edits.
- Existing deadline/call budgets and completed-answer hashes remain enforced.

## Pinning test

pipeline/test_agent_shadow_repair.py covers real CLI exception fallback, mixed format/word errors, repeated failure budgets, modifier fix vs replace, invalid modifier, no third audit, corrected English/word limits. Python3.10 relevant suite: 157 passed; no real model or production test.

## Related

docs/KIDSNEWS-NEWS-HYBRID-TEST.md has resume instructions and the unchanged one-hour deadline caveat. Native token/quota and repaired quality remain VM-test pending.
