# DeepSeek + Retry Implementation Flow

Focused brief for the second review pass — what I want feedback on is
specifically the LLM-call side: how prompts are constructed, when calls
fire, retry policy, fallback paths, and the surrounding orchestration.

## Daily run timeline (per category × 3 — News / Science / Fun)

```
PHASE A — per source × 3 sources                          # 3 × deepseek-reasoner
  1. fetch RSS, vet 10 briefs (1 reasoner call per source)
  2. ranked picks: choice_1, choice_2, alternate_0, alternate_1
  3. fetch HTML body + og:image for each ranked candidate
     until up to 4 verified candidates per source

PAST-DEDUP                                                # 0 LLM calls
  query redesign_stories (last 3 days, this category) →
  drop candidates whose normalized title ≥0.80 SequenceMatcher
  similarity to any past title

CROSS-SOURCE DEDUP + PROMOTE-NEXT                         # 1 deepseek_call (chat)
  check_duplicates() across the 3 current picks
  on dup: drop weaker source's pick → bump pointer → next candidate
  loops until no dup OR all candidates exhausted (max 8 rounds)

REWRITE                                                   # 1 deepseek_call (chat)
  tri_variant_rewrite: input = surviving 1-3 winners' bodies (≤2500w each)
  output = JSON {articles: [{source_id, easy_en{headline, card_summary, body},
                             middle_en{...}, zh{headline, summary}}, ...]}
  prompt: TRI_VARIANT_REWRITER_PROMPT (system) + parameterized N input

ENRICH                                                    # 1-3 reasoner calls
  detail_enrich:
    1st try: ONE call returning all 2N slots
    on JSON parse / network failure after 3 retries → split into TWO calls:
      easy-only (N slots) + middle-only (N slots)
    if both halves succeed → continue with full 2N detail set
    if one half fails → continue with partial; validator catches at pack time

VALIDATE BUNDLE
  9 listings × 2-3 articles · 2N detail payloads · per-story image present
  if shape wrong → SystemExit(1) before zip upload

PACK + UPLOAD
  zip → Supabase + dated archive
  per-day flat files → Supabase <date>/payloads/...
  archive-index.json updated (today added ONLY after flat upload succeeds)
  retention sweep deletes >30 day old dated artifacts

UPDATE_RUN
  redesign_runs.status: persisted → completed (or deploy_failed on upload error)
```

Total LLM cost per run: ~12 reasoner + ~3 chat = ~15 DeepSeek calls;
~$0.20-0.30 per day at current usage.

## Key files

- `pipeline/news_rss_core.py:240-353` — `_retry_sleep_for`,
  `_deepseek_post`, `deepseek_call`, `deepseek_reasoner_call`
- `pipeline/news_rss_core.py:498-528` — TRI_VARIANT_REWRITER_PROMPT +
  `tri_variant_rewriter_input` (parameterized by N)
- `pipeline/news_rss_core.py:530-636` — DETAIL_ENRICH_PROMPT +
  `detail_enrich_input` (parameterized by N)
- `pipeline/news_rss_core.py:701-759` — `_detail_enrich_input_single_level`,
  `detail_enrich` (with split-batch fallback)
- `pipeline/news_rss_core.py:761-880` — vet curator prompt + `run_source_phase_a`
- `pipeline/news_rss_core.py:880-960` — `check_duplicates` (cross-source dup)
- `pipeline/full_round.py:55-180` — `dedup_winners` →
  `pick_winners_with_dedup` (promote-next-candidate logic),
  `filter_past_duplicates` (3-day, 0.80 threshold, SequenceMatcher)
- `pipeline/full_round.py:415-500` — `main()` orchestration with the
  status-truthfulness fix

## Retry policy table (just landed)

| Failure | First retry | Second | Third |
|---|---|---|---|
| HTTP 429 | `Retry-After` (capped 120s, default 30×attempt) | same | same |
| HTTP 5xx | 4s | 8s | 16s |
| Network (Connection/Timeout) | 4s | 8s | 16s |
| JSONDecodeError | 1s | 2s | 3s |
| Other 4xx | 2s | 4s | 6s |

After 3 attempts, raises `RuntimeError` from chained `last_err`.
For enrichment, the caller catches and falls back to split-batch.

## What I want feedback on

1. **Should retry budget be model-class-dependent?** Reasoner calls
   already cost more thinking tokens; failing one is more expensive
   than failing a chat call. Should reasoner get more or fewer retries?

2. **Idempotence + visible state during retries.** Currently the entire
   `deepseek_call` is treated as one atomic unit. If a retry happens
   silently in CI logs, an operator looking at the run only sees
   "took 30s" not "retried twice for 429". Worth surfacing retry count
   in the run status / logs more explicitly?

3. **JSON repair as a separate strategy from re-roll.** Right now if
   reasoner emits malformed JSON, we just re-roll the whole call. If
   the JSON is truncated (`max_tokens` cliff) re-rolling helps; if
   it's a single comma drop in a 24KB output, a JSON-repair pass on
   the existing string would be cheaper. Worth adding?

4. **Past-dedup hostname / entity overlap.** Title-only at 0.80
   misses same-story rewrites with different headlines. Worth
   adding domain-of-source URL match as a second signal? (e.g.
   if the new candidate's source URL host matches a past story's
   AND any 5-gram of the lead overlaps, flag as dup.)

5. **Prompt parameterization by N.** Now we tell the model
   "N=2" or "N=1" explicitly in the user message. But the system
   prompt still describes the field set as if N=3 is canonical.
   Worth restructuring the system prompt to be N-agnostic from the
   top, or is the user-message override sufficient?

6. **Response-format JSON mode.** DeepSeek supports
   `response_format: {type: "json_object"}` which forces JSON-shaped
   output. We don't use it. Would adding it eliminate the malformed
   JSON failure class? (Reasoner is the offender; rewrite_chat is
   reliable.)

7. **Run-status state machine.** Currently:
   `running → persisted → {completed | deploy_failed}`.
   Anything else worth tracking — partial enrichment, partial dedup
   exhaustion, or per-category status?

Format: per-finding Severity / File:line / What / Why / Fix.
End with assessment + top-3 to fix first. Don't re-cover ground from
the previous review (`docs/reviews/2026-04-24-copilot-review.md`).
Trust that those issues are fixed (commit `d200b94`).
