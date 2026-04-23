# KidsNews v2 — Pipeline Design

**Date:** 2026-04-23
**Status:** Under design — sections marked ✅ are approved; others are drafting/pending.
**Supersedes:** `PIPELINE-IMPLEMENTATION.md` (draft, earlier assumptions)

---

## Overview ✅

### Runtime
- **Language:** Python 3.11+
- **Host:** GitHub Actions cron in the **public `daijiong1977/kidsnews-v2`** repo (unlimited free minutes)
- **Schedule:** `7 13 * * *` UTC (9:07am ET — non-`:00` to avoid fleet collision)
- **Cross-repo code access:** workflow clones `daijiong1977/news-v2` (private) via PAT stored as secret `NEWS_V2_PAT` (classic PAT, `repo` scope, read-only)
- **Local dev note:** developer's Mac is NOT involved in production. Pipeline code lives in news-v2; production execution happens entirely on GitHub Actions.

### Storage (single source of truth)
- Supabase project: `lfknsvavhiqrsasdfyrs.supabase.co` (same as v1)
- Tables: `redesign_runs`, `redesign_candidates`, `redesign_stories`, `redesign_story_variants`, `redesign_story_sources` (per `supabase/migrations/20260423_redesign_parallel_schema.sql`)
- **Supabase Storage bucket**: `redesign-article-images` (NEW, separate from any v1 bucket). Public read access. Files: `article_<story_id>_<hash>.webp`.

### Secrets (in kidsnews-v2 repo settings)
- `TAVILY_API_KEY`
- `DEEPSEEK_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` (bypasses RLS)
- `JINA_API_KEY` (optional)
- `NEWS_V2_PAT` (read access to private news-v2)

### Per-run control flow
1. Create `redesign_runs` row (status='running')
2. For each category in [News, Science, Fun]:
   a. Discover candidates (Step 1)
   b. Read full content (Step 2)
   c. Vet (Step 3)
   d. Rewrite (Step 4) — stops once 3 publishable collected
   e. Store finals (Step 5)
3. Export zip (Step 6)
4. Push zip to kidsnews-v2 (Step 7)
5. kidsnews-v2 unpack workflow auto-fires (Step 8)
6. Mark `redesign_runs.status='completed'`

### Failure semantics ✅
- Categories run independently. News can publish even if Science mid-run fails.
- Any per-category exception → log to `redesign_runs.notes`, continue to next category
- Entire-run fatal (Supabase connection lost, etc.) → `status='failed'`, workflow exits non-zero, GH Actions default email alert fires
- No automatic retry. Manual re-run via `workflow_dispatch`.

---

## Step 1: DISCOVER ✅

### Purpose
Produce **6 candidates per category** (News/Science/Fun), dedup'd against last 10 days, with verified decent imagery. Prefer a mix of web-search and RSS lanes, flex between them as availability allows.

### Sources per category

| Category | Tavily lane | RSS lane |
|---|---|---|
| News | 3 results via date-less query (current events change daily) | PBS NewsHour, pull 3 latest |
| Science | 3 results, query = topic-of-the-day | Science Daily, pull 3 latest |
| Fun | 3 results, query = topic-of-the-day | BBC Tennis, pull 2 latest (low-freq feed) |

### Daily topic rotation (Science + Fun)

Rotation avoids "every day's pipeline searches the same phrase and surfaces the same stories all week." Look up `date.weekday()` in UTC and build the Tavily query from the cell below. RSS lane does **not** filter by daily topic — it just pulls latest N entries regardless.

**Science**
| Day | Topic | Tavily query |
|---|---|---|
| Mon | AI / auto | `kids AI robots automation news this week` |
| Tue | Biology / Medicine / Health | `kids biology medicine health news this week` |
| Wed | Space / Astronomy | `kids space astronomy planets news this week` |
| Thu | Chemistry / Physics | `kids chemistry physics experiment news this week` |
| Fri | Environment / Climate | `kids environment climate nature news this week` |
| Sat | Technology / Engineering | `kids technology engineering invention news this week` |
| Sun | Nature / Geometry | `kids nature geometry patterns news this week` |

**Fun**
| Day | Topic | Tavily query |
|---|---|---|
| Mon | Music | `kids music news concerts instruments this week` |
| Tue | Swimming / Water sports | `kids swimming water sports news this week` |
| Wed | Movies / TV | `kids movies tv shows news this week` |
| Thu | Team sports | `kids soccer basketball football team sports news this week` |
| Fri | Arts / Crafts | `kids arts crafts creativity news this week` |
| Sat | Animals / Famous person / History | `kids animals famous people history news this week` |
| Sun | Video games / Esports | `kids video games esports news this week` |

**News** uses a day-less query: `top kids-appropriate news stories today`.

### Funnel logic

```
target_total = 6
default split = (tavily=3, rss=3) for News/Science; (tavily=3, rss=2) for Fun*

collect tavily_hits via Tavily API with category's query
collect rss_hits via feedparser from category's RSS URL (latest N)
dedup_and_filter(tavily_hits + rss_hits)

if len(filtered) < 6:
    top_up_lane = whichever lane has more remaining candidates available
    request N more from top_up_lane
    re-run dedup_and_filter

if len(filtered) < 6 after one top-up retry:
    log WARNING, proceed with what we have (minimum 3 to continue; else fail category)

select final 6 (or fewer)
```

*Fun targets 5 (3+2) instead of 6 because BBC Tennis doesn't update fast enough to consistently hit 3. Pipeline flexes Fun to 6 when Tavily has extras.

### Dedup (against last 10 days)

Two checks, both cheap, both zero-API-cost:
1. **Exact URL match**: `SELECT 1 FROM redesign_candidates WHERE source_url = $1 AND created_at > now() - interval '10 days'`. If match → skip.
2. **Title normalized substring match**: lowercase + strip punct, tokenize; if ≥70% word overlap with any recent title → skip.

If both checks pass → candidate is fresh. If dedup'd → log reason in `redesign_candidates.dedup_check`, candidate not stored but attempted replacement fetched from same lane.

### Image quality filter

For each surviving candidate, HEAD-check its primary image URL:
- Reject if URL substring matches: `logo`, `icon`, `avatar`, `tracking`, `1x1`, `pixel`, `spacer`
- Reject if extension is `.svg` or `.gif`
- Reject if HEAD returns 4xx/5xx OR times out in 3s OR `Content-Length < 20000` (20KB)
- If rejected → candidate dropped, pipeline fetches 1 replacement from same lane

Pipeline does not currently verify image dimensions via full download — URL substring + byte size is cheap and catches most low-quality images. If still too lossy in practice, upgrade to download + Pillow dimension check in a later iteration.

### Hot-topic boost

After 6 (or fewer) candidates are collected per category:
- Pairwise compare titles cross-lane (Tavily×RSS)
- Similarity via the same normalized-substring check used in dedup
- If ≥70% word overlap → both candidates get `hotness_score = true`
- In Step 4 (Rewrite), hot candidates get priority ordering

Mostly helps News (world events often surface in both lanes). Science/Fun rarely hot due to day-topic rotation.

### Schema additions required

Add to `redesign_candidates`:
- `hotness_score boolean DEFAULT false`
- `image_filter_passed boolean DEFAULT false`
- `dedup_check text` (nullable; stores reason if skipped)

(Will include in a follow-up Supabase migration.)

### Output

`redesign_candidates` rows: up to 6 per category per run, with:
- `run_id`, `category`, `discovery_lane` (`new_pipeline` | `rss`)
- `source_name`, `source_domain`, `source_url`, `title`, `snippet`
- `raw_content` (nullable until Step 2), `image_urls` (jsonb)
- `discovered_rank` (int, 1-N within category)
- `hotness_score`, `image_filter_passed`, `dedup_check`

### APIs used
- `POST https://api.tavily.com/search` — search, auth via `api_key` in body
- `feedparser` Python library — RSS parsing, no API key needed
- `HEAD <image_url>` via `requests` — image quality check
- Supabase INSERT via `supabase-py` — persist candidates

### Verification
- Assert: 3-6 candidates per category per run (min 3 for category to continue; <3 fails the category)
- Assert: all stored candidates have `image_filter_passed = true`
- Assert: no stored candidate's URL matches last 10 days
- Log warning: if final lane ratio is very skewed (>5:1) — signals one source is underperforming

---

## Step 2: READ (pending design — next up)

## Step 3: VET (pending)

## Step 4: REWRITE (pending)

## Step 5: STORE (pending)

## Step 6: EXPORT zip (pending)

## Step 7: PUSH to kidsnews-v2 (pending)

## Step 8: UNPACK (kidsnews-v2 workflow) (pending)

## Error handling & observability (pending)
