# 2026-05-02 — pipeline-enrich-truncation

**Severity:** high (blocks the daily upload — no new bundle = stale prod)
**Area:** pipeline (Phase D enrich)
**Status:** fixed
**Keywords:** detail_enrich, deepseek_reasoner, max_tokens, truncation, split-batch, News middle, bundle-validation, pack_and_upload

## Symptom

Today's (2026-05-02) daily-pipeline run via the 17:35 UTC schedule
cron failed at the *Run full_round* step. Cascade:

```
=== MEGA Phase D — enrich 9 survivors only ===
INFO  split-batch easy: 3 slots OK
ERROR split-batch middle failed after retries:
      reasoner output truncated (max_tokens=12000 hit);
      split-batch fallback in caller will shrink the payload
WARNING [News] enrich returned 3 slots, expected 6
...
=== PACK + UPLOAD ZIP ===
ERROR Bundle validation FAILED — refusing to pack/upload:
   · 2026-05-02-news-1/middle: questions has 0 (need ≥3)
   · 2026-05-02-news-1/middle: background_read has 0 (need ≥1)
   · 2026-05-02-news-1/middle: Article_Structure has 0 (need ≥3)
   ... (same for news-2 and news-3, all middle level)
ERROR pack_and_upload aborted (SystemExit 1)
##[error]Process completed with exit code 2.
```

End result: no bundle uploaded → no kidsnews-v2 sync → no Vercel
redeploy. news.6ray.com kept yesterday's content.

The pipeline-watchdog auto-retry kicked in (workflow_dispatch run
25258536681, fired ~37s after failure), but it's running the same
deterministic code path — without a fix it would have hit the same
truncation.

## Root cause

`pipeline/news_rss_core.py:detail_enrich` (called per category in
Phase D) uses split-batch by default: 1 reasoner call per
(category, level) pair, 3 slots per call. The call set
`max_tokens=12000`. For News middle with 3 long articles
(today's articles included a 600+ word piece on Iran sanctions
and an article on Spirit Airlines closure), the combined output
of:

- V4 Pro reasoner thinking-mode CoT (consumes output budget)
- 3× structured JSON enrichments containing:
  - questions[] (≥3 quiz questions per article, with options +
    correct_answer)
  - background_read[] (≥1 background paragraph per article)
  - Article_Structure[] (≥3 structural breakdown elements)

exceeded 12000 tokens, finishing with `finish_reason=length`.

The split-batch is already as-narrow-as-it-gets (1 level × 3 slots);
the inner `_reasoner_call_with_model` raises immediately on
`length` truncation without retrying because the comment says
"caller will shrink the payload" — but in this case the caller IS
the split-batch (no further shrinking available). So `detail_enrich`
caught the RuntimeError, logged "split-batch middle failed after
retries", and returned with only the easy slots populated. News
middle was empty.

`pack_and_upload` then refused to ship a bundle missing required
fields (correct: shipping a partial bundle would put broken
articles on prod).

The pre-existing reasoner default is `max_tokens=16000` — the
12000 here was an under-budget pin from when this code was
written, when News articles were typically shorter.

## Fix

`pipeline/news_rss_core.py:detail_enrich` — bump
`max_tokens=12000` → `max_tokens=16000` in the split-batch reasoner
call. This matches the function's default and gives a 33% headroom
over today's truncation point. The previous "12k is generous"
comment was based on an outdated read of typical article length.

Single-line change. The split-batch retry semantics are unchanged.

## Invariant

Whenever `detail_enrich`'s per-level reasoner call truncates
(`finish_reason=length`), the bundle for that category is
partial and `pack_and_upload` will refuse it. There is currently
**no further fallback** below split-batch — if 16000 starts
failing too, the path forward is one of:

1. Bump max_tokens further (model limit is 128K total
   context; we can go higher if needed).
2. Implement a true "1 slot at a time" fallback below split-batch.
3. Tighten the enrichment prompt (shorter background_read /
   fewer / shorter Article_Structure entries).

If this happens again, prefer (1) first — it's a single-line
config change with no behavioural drift. Option (2) is the
correct architectural answer if (1) keeps drifting upward.

## Pinning test

After deploy + manual re-dispatch:

```bash
gh run list -R daijiong1977/news-v2 --workflow daily-pipeline.yml --limit 1
# expect: status=completed, conclusion=success
gh run view <id> -R daijiong1977/news-v2 --log | grep -E "split-batch|truncated|enrich returned"
# expect: 6 "split-batch X: 3 slots OK" lines (3 categories × 2 levels),
# zero "truncated" lines, zero "enrich returned N slots, expected 6" warnings
```

Watch for the run to complete *Run full_round* successfully and
proceed through *Refresh search index* / *Trigger kidsnews-v2 sync* /
*Verify kidsnews-v2 sync*.

## Related

- `pipeline/news_rss_core.py:1318` —
  `def deepseek_reasoner_call(..., max_tokens: int = 16000, ...)`.
  Default. Now matches `detail_enrich`'s usage.
- `pipeline/full_round.py:1147-1219` — caller of `detail_enrich`
  has a partial-recovery path that ships the easy half if middle
  fails (see "split-batch fallback used" comment). Today that
  partial-recovery happened, but `pack_and_upload` correctly
  refused the partial bundle since news_*/middle was missing
  required fields. No code change needed there.
- `pipeline/full_round.py:391` — outer (non-enrich) reasoner call
  uses `max_tokens=8000` for the curator step; that's fine since
  it returns picks not enrichment.
- Secondary observation, NOT fixed in this commit:
  `redesign_runs.status` CHECK constraint rejects `'persisted'`
  and `'deploy_failed'` writes the pipeline now produces, surfacing
  as HTTP 400 errors in the log. Telemetry-only (doesn't block
  the pipeline). Follow-up: a separate migration to broaden the
  status enum.
