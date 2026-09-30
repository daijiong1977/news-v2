# News-only DeepSeek/Bot experiment — 2026-09-30

Opt-in local shadow test. Production and the previous full autonomous run are unchanged.

| Work | Owner |
| --- | --- |
| Feed collection, original fetch, counts, cache, pack | Python |
| News plan: three winners plus up to three reserves, history and importance | Bot |
| EN easy/middle + Chinese rewrite | DeepSeek HTTP |
| Independent full-text facts/safety/neutrality review | Bot in a new session/sub-Agent |
| Details generation and per-field/per-question review | DeepSeek HTTP, separate requests |
| Original-source images | Existing bounded download/decode; no Bot visual task |

Science/Fun are empty and not fetched/generated/reviewed. Catalog validator rejects selections in inactive sections. Publication is forbidden for this partial experiment. Images are **not visually approved**; technical checks do not prove relevance, neutrality or child safety. Default full autonomous visual review stays enabled.

Provider boundary: `config/shadow-news-deepseek.json`, environment reference `DEEPSEEK_API_KEY`. `.env` is loaded on every profile command, not just prepare, without overriding exported variables. Never read/print/commit it. HTTP invalid answer gets one model correction, then existing rewrite-invalid/omit-details handling. Uncertain network outcomes do not auto-retry. Native body review remains mandatory.

## VM test

Use a new run directory; do not reuse `autonomous-1`. First pull with fast-forward only on `codex/stepwise-full-shadow`. The existing registry date must match 2026-09-30 and include News history. It contains source/history configuration, **not a frozen feed snapshot**, so live feed changes affect comparison.

```sh
cd /workspace/kidsnews-shadow
git pull --ff-only origin codex/stepwise-full-shadow
.venv/bin/python -m pipeline.agent_shadow prepare --run-dir work/2026-09-30/news-hybrid-1 --date 2026-09-30 --editor-mode autonomous --test-profile news-deepseek --registry work/2026-09-30/registry.json
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/2026-09-30/news-hybrid-1
```

Repeat the last command according to the JSON result: exit 0 next step; exit 2 read **only** the indicated native request and write its envelope answer; exit 1 stop/report; exit 3 already done. Every body review must be a fresh session/sub-Agent without reading the writer's answer file. Do not write HTTP answers yourself, change code, deploy, write Supabase or send mail. No routine progress messages; one final report or blocking error.

On pack completion stop. Inspect `done.json`, `review-results.json`, `metrics.json`, `provider-audit.json`, `steps.jsonl`, `reader/`, `site/`. News should have 3 accepted drafts (or explain candidate exhaustion), one important qualified story and publisher/topic diversity. Check details accuracy and source-image suitability manually. Preserve warnings.

## Baseline and measurement

Previous full native run: 51m11s, 56 AI tasks, 18 body fetches, 9 final stories; observed user quota 7% weekly (not measured model tokens). Three News stories were all PBS; five drafts were rejected for unsupported facts; three images were removed when reviewers could not view pixels. Avoid fabricating a 7%→3% linear estimate.

This experiment targets only News, normally one native planning task + three independent body reviews, plus rejected-story/discovery/correction tasks if needed. DeepSeek normally performs nine requests: three rewrites, three details, three detail reviews. Actual usage and per-call seconds are recorded in provider-audit; native tokens are unavailable, so user console must measure quota. Compare News-specific quality and costs, not this three-story cost against the previous nine-story total. Record start/end ET, full wall time (including Bot handoffs), body fetches, native/HTTP calls, tokens, retries, rejection reasons, source mix, importance and manual assessment. Do not claim the under-3% target achieved before console evidence.
