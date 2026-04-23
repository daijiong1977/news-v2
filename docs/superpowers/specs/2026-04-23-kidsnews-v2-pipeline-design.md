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
   b. Vet Stage 1 on title+snippet (Step 2) — reject obvious unsafe BEFORE fetching full text
   c. Read full content (Step 3) — only for SAFE/CAUTION survivors
   d. Rewrite into 3 variants (Step 4) — stops once 3 publishable collected
   e. Store finals (Step 5)
3. Export zip (Step 6)
4. Push zip to kidsnews-v2 (Step 7)
5. kidsnews-v2 unpack workflow auto-fires (Step 8)
6. Mark `redesign_runs.status='completed'`

### Future iterations (deferred, not in v1 of pipeline)
- **Vet Stage 3 (post-rewrite gatekeeper)**: after rewrite produces easy_en / middle_en / zh variants, run a final DeepSeek check on the kid-facing output. Adds protection against rewriter leaking source-level issues. Deferred because: (a) rewriter is instructed to write at 5th grade level, usually softens automatically; (b) Stage 1 catches most bad source material; (c) if Stage 3 is needed empirically, plug it in between Step 4 and Step 5 without changing other steps.
- **Full-text re-vet before rewrite (Stage 2)**: only if Stage 3 reject rate exceeds ~15% in practice.
- **Pillow-based image dimension check**: currently we trust URL heuristics + HEAD `Content-Length`. Upgrade if too many low-quality images slip through.

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

## Step 2: VET (Stage 1 — title + snippet) ✅

### Purpose
Filter out candidates whose titles/snippets alone reveal kid-inappropriate content. Runs before fetching full text so REJECTs don't waste Jina fetches. Single-stage for v1 of the pipeline; Stage 3 (post-rewrite gatekeeper) deferred to a later iteration.

### Input
`redesign_candidates` rows from Step 1 for current run+category. Each row has:
- `title` (always present)
- `snippet` (always present, 100-300 chars from Tavily or RSS)

### APIs used
- `POST https://api.deepseek.com/chat/completions`
- Model: `deepseek-chat` (V3)
- `temperature: 0.1` (deterministic scoring)
- `max_tokens: 400`
- Prompt adapted from the existing vetter prompt in `vetter-comparison-test.mjs`, trimmed for title+snippet context.

### Prompt skeleton

```
SYSTEM:
You are a content safety reviewer for a kids news site (ages 8-13, grades 3-8).
You are judging based ONLY on the title and a short snippet (100-300 chars).
Err on the side of SAFE when the snippet is neutral. Reject only when the title
or snippet clearly signals violence, sexual content, substance use, explicit
distress, or topics that would upset or confuse a child of this age.

Rate on each dimension (0=none, 1=minimal, 2=mild, 3=moderate, 4=significant, 5=severe):
violence, sexual, substance, language, fear, adult_themes, distress, bias

Return ONLY valid JSON (no markdown):
{
  "scores": {...},
  "total": 0,
  "verdict": "SAFE|CAUTION|REJECT",
  "flags": ["..."],
  "rewrite_notes": "..."
}

USER:
Title: <title>
Snippet: <snippet>
```

### Scoring thresholds
- 0-4 total → **SAFE**
- 5-12 total → **CAUTION** (continue, apply `rewrite_notes` at Rewrite step)
- 13+ total → **REJECT** (drop, pipeline fetches backfill from same lane)

Note: thresholds are tighter than the full-text vetter in PIPELINE-IMPLEMENTATION.md (there: SAFE 0-8, CAUTION 9-20, REJECT 21-40). Because title+snippet has less information, we need to treat borderline hits as SAFE-but-watch (catch in rewriter's softening), not reject aggressively. Tune based on run data.

### Processing
```python
for candidate in candidates_for_this_category:
    response = deepseek_chat(
        system=STAGE1_VETTER_PROMPT,
        user=f"Title: {candidate.title}\nSnippet: {candidate.snippet}",
        temperature=0.1,
        max_tokens=400,
    )
    # Response: {scores, total, verdict, flags, rewrite_notes}
    UPDATE redesign_candidates
       SET vetter_score = $response.total,
           vetter_verdict = $response.verdict,
           vetter_flags = $response.flags,
           vetter_payload = $response,
           vetted_rank = (rank within category by score ascending)
     WHERE id = $candidate.id

# After all vetted, drop REJECTs:
candidates_passed = [c for c in candidates if c.vetter_verdict != 'REJECT']
if len(candidates_passed) < 3:
    # not enough to reach 3 published stories — trigger backfill discovery for this category
    ...
```

### Output
Updates to same `redesign_candidates` rows:
- `vetter_score` (int, 0-40)
- `vetter_verdict` (text, SAFE|CAUTION|REJECT)
- `vetter_flags` (jsonb, array of concern strings)
- `vetter_payload` (jsonb, full DeepSeek response for audit)
- `vetted_rank` (int, rank within category by score asc — safest first)

### Verification
- Assert: all candidates in run have `vetter_verdict IS NOT NULL`
- Log: verdict distribution per category (too many REJECTs → tune query or thresholds)
- If fewer than 3 SAFE+CAUTION per category → trigger backfill discovery (up to 2 extra discover rounds); if still under 3, publish what we have, log warning

### Failure modes + handling
- DeepSeek API error → retry once with exponential backoff; second failure marks candidate `vetter_verdict='ERROR'` and treats as REJECT (conservative)
- JSON parse error (DeepSeek returned malformed JSON) → retry once; second failure → REJECT
- All candidates REJECT'd → trigger backfill; if 2 backfill rounds also fail → skip this category for today

---

## Step 3: READ (full article text — survivors only) ✅

### Purpose
Get full article text for candidates that passed Stage 1 vet (SAFE or CAUTION). Skipped for REJECTs. Reduces Jina fetches by ~30-50% compared to reading everyone.

### Input
- `redesign_candidates` rows where `vetter_verdict IN ('SAFE', 'CAUTION')` for current run+category
- Each row has:
  - `source_url` (always)
  - `raw_content` (Tavily lane may have it, RSS lane doesn't)
  - `snippet` (fallback)

### Processing
```python
survivors = SELECT FROM redesign_candidates
    WHERE run_id = $run_id
      AND category = $category
      AND vetter_verdict IN ('SAFE', 'CAUTION')

for candidate in survivors:
    text = candidate.raw_content
    method = 'tavily'
    images = candidate.image_urls or []

    needs_fetch = (
        candidate.discovery_lane == 'rss'
        or not text
        or len(text) < 1200
    )

    if needs_fetch:
        try:
            markdown = fetch_jina(candidate.source_url, timeout=30s)
            text = markdown
            method = 'jina'
            images = dedup(images + extract_markdown_images(markdown))
        except (HTTPError, Timeout) as e:
            log.warning(f"Jina failed {candidate.source_url}: {e}")
            text = candidate.snippet
            method = 'snippet_only'

    UPDATE redesign_candidates
       SET raw_content = $text,
           read_method = $method,
           image_urls = $images
     WHERE id = $candidate.id
```

### APIs used
- **Primary (reused)**: Tavily `raw_content` from Step 1 if adequate
- **Fallback**: `GET https://r.jina.ai/<url>` with `Accept: text/plain`, 30s timeout
- **Supabase UPDATE** via `supabase-py`

### Output
Same `redesign_candidates` rows, updated:
- `raw_content` — full text (2000-15000 chars typical)
- `read_method` ∈ {`tavily`, `jina`, `snippet_only`}
- `image_urls` — dedup'd union

### Verification
- Assert: all survivors have `raw_content IS NOT NULL`
- Warn: if > 1 `snippet_only` per category, quality of rewrite will suffer

### Failure modes + handling
- Jina 451 (rate-limited) → `snippet_only`
- Jina 404 → `snippet_only`
- Timeout → `snippet_only`
- All-candidates-snippet-only in a category → continue but log in `redesign_runs.notes` for manual review

---

## Step 4: REWRITE (pending)

## Step 5: STORE (pending)

## Step 6: EXPORT zip (pending)

## Step 7: PUSH to kidsnews-v2 (pending)

## Step 8: UNPACK (kidsnews-v2 workflow) (pending)

## Error handling & observability (pending)
