OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/jiong/myprojects/news-v2
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 019dc1e5-5c73-7033-a86d-202f503430d8
--------
user
# Code review brief — News Oh, Ye! v2 (news.6ray.com)

## Project context

**Goal.** Bilingual kids news site (English easy / middle + 中文 summary).
Fully autonomous pipeline runs daily on GitHub Actions, produces 9 stories
(3 News / 3 Science / 3 Fun) plus per-story detail enrichment, ships to
Supabase Storage, and auto-deploys to Vercel at news.6ray.com.

**Three-repo architecture.**
- `news-v2` (this repo): Python pipeline + React prototype source. Runs the
  daily-pipeline workflow. Goes private eventually.
- `kidsnews-v2` (separate repo): tiny deploy shell. A sync workflow pulls
  `latest.zip` from Supabase Storage, unzips into `site/`, commits, Vercel
  auto-deploys.
- `kidsnews` (legacy, v1 reference at kidsnews.6ray.com): not relevant.

## Flow

```
GitHub Action (news-v2 · daily 06:20 UTC)
  └── python -m pipeline.full_round
        ├── RSS mine (3 sources × 3 categories, per-weekday rotation)
        ├── Phase A per source: vet 10 briefs, return top-4 verified candidates
        ├── past-dedup (3-day lookback, title ≥80% similar → drop)
        ├── cross-source dedup (promote next candidate on dup)
        ├── tri-variant rewrite (easy_en / middle_en / zh) via DeepSeek chat
        ├── detail enrich (keywords / questions / background / mind-tree /
        │     why_it_matters / perspectives) via DeepSeek reasoner
        │     — retries 3× on JSON parse; falls back to split 3-slot batches
        ├── image optimize (Pillow decode + libwebp cwebp/dwebp CLI)
        │     → Supabase Storage redesign-article-images bucket
        ├── persist runs + stories to Supabase tables
        └── pack_and_upload
              ├── validate_bundle (9 listings · 18 details · all images)
              ├── check_not_overwriting_newer (aborts if remote is fresher)
              ├── zip website/ → Supabase redesign-daily-content:latest.zip
              │     + <YYYY-MM-DD>.zip
              ├── latest-manifest.json + <YYYY-MM-DD>-manifest.json
              ├── per-day flat files under <YYYY-MM-DD>/ prefix (new)
              ├── backfill_missing_archive_dirs (extracts past zips if the
              │     flat dir is missing — runs only once per past date)
              ├── update archive-index.json (list of available dates)
              └── retention sweep (keep 30 days)

GitHub Action (kidsnews-v2 · cron :15 every 2h, or dispatch on pipeline success)
  └── downloads latest.zip → unzips into site/ → commits if changed → push

Vercel (on push to kidsnews-v2)
  └── deploys site/ to news.6ray.com
```

## Key files (by importance)

### Pipeline (Python 3.11)
- `pipeline/full_round.py` — orchestrator. Aggregate → dedup → images →
  rewrite+enrich → persist → pack_and_upload.
- `pipeline/news_rss_core.py` — shared utilities. DeepSeek call wrappers
  with retry, vet/rewriter/enricher prompts, RSS fetch, duplicate checker.
- `pipeline/pack_and_upload.py` — validation + zip + manifest + per-day
  flat upload + archive-index + retention.
- `pipeline/image_optimize.py` — webp optimizer with shutil.which() for
  cross-platform CLI path.
- `pipeline/news_sources.py` / `science_sources.py` / `fun_sources.py` —
  RSS source registries (per-weekday rotation for Science/Fun).
- `pipeline/news_aggregate.py` / `science_aggregate.py` / `fun_aggregate.py`
  — per-category aggregators (mostly wrappers around `run_source_with_backups`).
- `pipeline/supabase_io.py` — DB insert/update helpers.
- `pipeline/rewrite_from_db.py` — resume pipeline from DB state (skip
  mining + image ops). Used for debug / partial-category re-runs.

### Frontend (React 18 + Babel-standalone, in-browser JSX transpile)
- `website/index.html` — app shell. Loads data.jsx / components.jsx /
  home.jsx / article.jsx / user-panel.jsx. Owns top-level state (route,
  level, cat, archiveDay, progress, tweaks).
- `website/data.jsx` — payload loader. Fetches today's listings from
  `/payloads/*.json` (local). For archive mode, fetches from Supabase
  Storage `<date>/payloads/*.json`. Exposes window.loadArchive(date).
- `website/home.jsx` — listing page with feature + normal card variants,
  DatePopover for "View old news", footer generation timestamp.
- `website/article.jsx` — detail page: Read & Words / Background / Quiz
  / Think & Share tabs. Supports mind-tree Article_Structure for Tree
  level, 5W boxes for Sprout.
- `website/components.jsx` — shared UI bits (CatChip, XpBadge, etc.).
- `website/user-panel.jsx` — profile drawer (name / avatar / theme / level).

### CI/CD
- `.github/workflows/daily-pipeline.yml` — news-v2 daily cron (pipeline).
- (kidsnews-v2 repo) `.github/workflows/sync-from-supabase.yml` — pulls
  latest.zip + commits.
- `requirements.txt` — Python deps.
- `pipeline/backfill_card_summaries.py`, `pipeline/augment_mined_at.py` —
  one-shots used historically.

## What to evaluate

Focus where you'd expect bugs or future pain:

1. **Correctness.**
   - `dedup_winners` → `pick_winners_with_dedup` refactor. Two overlapping
     ScienceDaily feeds produced the same article; fix was to return up
     to 4 candidates and promote next on dup. Check edge cases: all
     sources returning candidates that are all pairwise dupes; candidate
     exhaustion mid-loop.
   - `filter_past_duplicates` title-similarity at 0.80 — are there
     obvious false positives / negatives? (titles can differ
     significantly while being the same story; or be identical but
     different stories.)
   - `deepseek_*_call` retry logic — does it handle rate-limit
     (429) differently from JSON parse errors?
   - `detail_enrich` split-batch fallback — what if BOTH easy and
     middle sub-calls fail? Currently continues with partial details;
     downstream validator will catch.

2. **Security.**
   - Supabase service key lives in a committed .env loader (module
     top-level), overridden by GitHub Actions secret at job start.
     Any path where the key could end up in a log?
   - Vercel.json Cache-Control of 5min for user-visible assets — any
     risk of serving private data?
   - DeepSeek API key is only used server-side; confirm no frontend
     references.
   - Any HTML injection paths in the rewriter output? UI highlights
     keywords by matching with user-content strings.

3. **Failure modes.**
   - Pipeline partial failure (category rewrite succeeds but enrich
     fails): is there a state where a partial bundle gets uploaded?
     (We added `check_not_overwriting_newer` and `validate_bundle`.)
   - Supabase Storage quota exhaustion mid-upload.
   - Vercel build fails after kidsnews-v2 commit — the pipeline
     doesn't know; only manual intervention.
   - Browser with localStorage full / disabled.

4. **Maintainability.**
   - `pipeline/news_rss_core.py` is ~1200 lines. Should it split?
   - `full_round.py` grew fast — orchestration, dedup, image-process
     helpers, persistence, emit — all in one file.
   - React app has no build step (Babel-standalone). Fine for a
     prototype; risky long-term. Recommendation?
   - Hardcoded `/Users/jiong/...` paths were a CI bug source today;
     are there others lurking?

5. **Architecture.**
   - Three-repo split: authoring / deploy / legacy. Any cleaner alt?
   - The zip-over-Storage indirection vs directly pushing
     generated artifacts to the deploy repo.
   - Per-day flat files coexist with zips — redundant, or
     justified?
   - "CI-only, never run locally" guard (`check_not_overwriting_newer`)
     — robust enough? Any evasion paths?

6. **Prompt engineering.**
   - Rewriter prompt vs enricher prompt — any accuracy-vs-creativity
     trade-offs worth flagging?
   - `card_summary` ≤ 120 words — is the prompt actually enforceable?
     (We also post-trim with a word cap.)
   - Past-dedup threshold of 0.80 title similarity — when would you
     lower or raise it?

## Format of your review

For each finding, use:

- **Severity**: `Critical` / `Important` / `Minor` / `Info`
- **File:line** (or "cross-cutting")
- **What**: one-sentence description
- **Why it matters** (1-2 sentences)
- **Suggested fix** (concrete, if you have one)

Then at the end: 3-5 line assessment summary + top 3 things to fix first.

Do not nitpick style unless it materially affects clarity. Do not
suggest broad refactors without a specific incident that justifies
them. Trust that the design decisions (RSS-only, three-repo split,
zip-via-Supabase, React-without-build) are intentional unless you spot
evidence they're causing real problems.
2026-04-24T23:48:47.880837Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
2026-04-24T23:48:47.918536Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
2026-04-24T23:48:48.406156Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
2026-04-24T23:48:49.038412Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
ERROR: Reconnecting... 2/5
2026-04-24T23:48:51.088768Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
ERROR: Reconnecting... 3/5
2026-04-24T23:48:52.597193Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
ERROR: Reconnecting... 4/5
2026-04-24T23:48:54.697794Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
ERROR: Reconnecting... 5/5
2026-04-24T23:48:58.396067Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses
ERROR: Reconnecting... 1/5
ERROR: Reconnecting... 2/5
ERROR: Reconnecting... 3/5
ERROR: Reconnecting... 4/5
ERROR: Reconnecting... 5/5
ERROR: unexpected status 401 Unauthorized: Missing bearer or basic authentication in header, url: https://api.openai.com/v1/responses, cf-ray: 9f1900a92c89b3e9-MIA, request id: req_74fe63aeb0914657a97cd4bc4a09263d
codex
Review was interrupted. Please re-run /review and wait for it to complete.
2026-04-24T23:49:06.149922Z ERROR codex_core::session: failed to record rollout items: thread 019dc1e5-5c9c-7763-bc64-2a141a96b2a3 not found
ERROR: unexpected status 401 Unauthorized: Missing bearer or basic authentication in header, url: https://api.openai.com/v1/responses, cf-ray: 9f1900a92c89b3e9-MIA, request id: req_74fe63aeb0914657a97cd4bc4a09263d
2026-04-24T23:49:06.195604Z ERROR codex_core::session: failed to record rollout items: thread 019dc1e5-5c73-7033-a86d-202f503430d8 not found
