# News-only DeepSeek/Bot experiment — 2026-09-30

Opt-in local shadow test. Production and the previous full autonomous run are unchanged.

| Work | Owner |
| --- | --- |
| Feed collection, original fetch, counts, cache, pack | Python |
| News plan: three winners plus up to three reserves, history and importance | Bot |
| EN easy/middle + Chinese rewrite | DeepSeek HTTP |
| Source-grounded modification + final facts/safety/neutrality judgment | Bot in a fresh session/sub-Agent; no third AI audit |
| Details generation and per-field/per-question review | DeepSeek HTTP, separate requests |
| Original-source images | Existing bounded download/decode; no Bot visual task |

Science/Fun are empty and not fetched/generated/reviewed. Catalog validator rejects selections in inactive sections. Publication is forbidden for this partial experiment. Images are **not visually approved**; technical checks do not prove relevance, neutrality or child safety. Default full autonomous visual review stays enabled.

Provider boundary: `config/shadow-news-deepseek.json`, environment reference `DEEPSEEK_API_KEY`. `.env` is loaded on every profile command, not just prepare, without overriding exported variables. Never read/print/commit it. Only this profile allows one formatting repair AND one content/word-count repair (at most three HTTP attempts including initial output). Corrections include the previous answer, not a blind regeneration. Exhausted invalid drafts are skipped, invalid details omitted. Uncertain network outcomes do not auto-retry. Each HTTP attempt records usage separately; old overwritten usage cannot be reconstructed.

The second model directly fixes attribution, quotes, qualifiers, neutrality and mixed-language text from the source, then scores its FINAL corrected draft. Code validates corrected fields, word limits, English language, eight safety scores, facts_supported and same-category event_clear. A failed final judgment replaces the draft. This is second-model editing/self-check, NOT an independent audit of the modifier's own edits. Serious politics/war/death remain allowed without graphic violence. No additional pre-audit pass or third model call.

### Resume the failed hybrid run

Pull and repeat `step` on `work/2026-09-30/news-hybrid-1`; do not remove cached answers or accepted drafts. Legacy factual rejections get one modifier opportunity; the accepted mixed-language draft is reopened for modification. Completed answer hashes remain immutable. The real CLI uses a shared AnswerRejected class so an exhausted article correction is caught even with `python -m`.

The existing one-hour run deadline and call budgets remain enforced. If the interrupted run has already exceeded that deadline, it cannot be resumed by silently resetting its audit; stop/report and explicitly start a new run directory. No real resume result is claimed by offline tests.

## VM test

Use a new run directory; do not reuse `autonomous-1`. First pull with fast-forward only on `codex/stepwise-full-shadow`. The existing registry date must match 2026-09-30 and include News history. It contains source/history configuration, **not a frozen feed snapshot**, so live feed changes affect comparison.

```sh
cd /workspace/kidsnews-shadow
git pull --ff-only origin codex/stepwise-full-shadow
.venv/bin/python -m pipeline.agent_shadow prepare --run-dir work/2026-09-30/news-hybrid-1 --date 2026-09-30 --editor-mode autonomous --test-profile news-deepseek --registry work/2026-09-30/registry.json
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/2026-09-30/news-hybrid-1
```

Repeat the last command according to the JSON result: exit 0 next step; exit 2 read **only** the indicated native request and write its envelope answer; exit 1 stop/report; exit 3 already done. Every body modifier must be a fresh session/sub-Agent without reading the writer's answer file, and return corrected_article plus scores and factual/event judgments on that corrected article. Do not write HTTP answers yourself, change code, deploy, write Supabase or send mail. No routine progress messages; one final report or blocking error.

On pack completion stop. Inspect `done.json`, `review-results.json`, `metrics.json`, `provider-audit.json`, `steps.jsonl`, `reader/`, `site/`. News should have 3 accepted drafts (or explain candidate exhaustion), one important qualified story and publisher/topic diversity. Check details accuracy and source-image suitability manually. Preserve warnings.

## Baseline and measurement

Previous full native run: 51m11s, 56 AI tasks, 18 body fetches, 9 final stories; observed user quota 7% weekly (not measured model tokens). Three News stories were all PBS; five drafts were rejected for unsupported facts; three images were removed when reviewers could not view pixels. Avoid fabricating a 7%→3% linear estimate.

This experiment targets only News, normally one native planning task + three independent body reviews, plus rejected-story/discovery/correction tasks if needed. DeepSeek normally performs nine requests: three rewrites, three details, three detail reviews. Actual usage and per-call seconds are recorded in provider-audit; native tokens are unavailable, so user console must measure quota. Compare News-specific quality and costs, not this three-story cost against the previous nine-story total. Record start/end ET, full wall time (including Bot handoffs), body fetches, native/HTTP calls, tokens, retries, rejection reasons, source mix, importance and manual assessment. Do not claim the under-3% target achieved before console evidence.
