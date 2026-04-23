# News Oh,Ye! — Pipeline Implementation Guide

> **For:** Codex / Claude Code / developer implementing the automated pipeline
> **Site:** kidsnews.6ray.com
> **Stack:** Node.js (ESM) + Tavily + Jina Reader + DeepSeek + Supabase
> **Goal:** Automated bilingual kids news, 2x daily, fully API-driven (no browser)

---

## Architecture Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│ 1. DISCOVER  │───▶│  2. READ     │───▶│  3. VET      │───▶│ 4. REWRITE   │───▶│ 5. STORE │
│  Tavily API  │    │ Tavily+Jina  │    │  DeepSeek    │    │  DeepSeek    │    │ Supabase │
│  (search)    │    │ (full text)  │    │  (safety)    │    │ (kids+中文)   │    │  (DB)    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘
                                                                                     │
                                                                              ┌──────▼──────┐
                                                                              │ 6. PUBLISH  │
                                                                              │  Vercel ISR │
                                                                              └─────────────┘
```

---

## Environment Variables

```bash
# Required
TAVILY_API_KEY=<required>
DEEPSEEK_API_KEY=<required>
SUPABASE_URL=<required>
SUPABASE_SERVICE_KEY=<required>

# Optional (for vetter comparison tests)
ANTHROPIC_API_KEY=<your Claude API key>
JINA_API_KEY=<optional, free tier works without key>
EXA_API_KEY=<optional, for cross-verification>
```

---

## Step 1: DISCOVER — Find candidate articles

### Tool: Tavily Search API

**Endpoint:** `POST https://api.tavily.com/search`

**What it does:** Searches the web and returns article URLs, titles, snippets, full content, and images — all in one call.

### Input
```javascript
// Each category runs its own 10-candidate funnel.
// The new-discovery lane contributes 6 candidates per category.
const categories = [
  { query: "top US news today", category: "News" },
  { query: "science discovery news this week", category: "Science" },
  { query: "kids fun news this week sports games competitions", category: "Fun" },
];
```

### API Call
```javascript
async function discoverArticles(query) {
  const response = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: process.env.TAVILY_API_KEY,
      query: query,
      search_depth: "advanced",      // better results, costs ~$0.01
      include_raw_content: true,     // full article text (saves Step 2 for most)
      include_images: true,          // returns image URLs from the article
      max_results: 5
    })
  });
  return await response.json();
}
```

### Output Shape (Tavily response)
```javascript
{
  "results": [
    {
      "title": "Article Title",
      "url": "https://source.com/article",
      "content": "Short snippet/summary (300-500 chars)",
      "raw_content": "Full article text (5,000-25,000 chars) or null",
      "score": 0.95  // relevance score
    }
  ],
  "images": [
    "https://cdn.source.com/photo1.jpg",
    "https://cdn.source.com/photo2.jpg"
  ]
}
```

### Processing Logic
```javascript
async function discover() {
  const categories = [
    { query: "top US news today", category: "News" },
    { query: "science discovery news this week", category: "Science" },
    { query: "kids fun news this week sports games competitions", category: "Fun" }
  ];

  const allCandidates = [];

  for (const cat of categories) {
    const result = await discoverArticles(cat.query);
    for (const article of result.results) {
      allCandidates.push({
        title: article.title,
        url: article.url,
        snippet: article.content,
        raw_content: article.raw_content || null,  // may be null for some
        images: result.images || [],                // images from this search
        category: cat.category,
        source: 'tavily',
        tavily_score: article.score
      });
    }
  }

  // Deduplicate by URL (same article from multiple searches = higher impact)
  const deduped = deduplicateByUrl(allCandidates);

  // Sort by impact: articles found in multiple searches rank higher
  deduped.sort((a, b) => b.searchHits - a.searchHits);

  return deduped; // new-discovery candidates for a single category lane
}

function deduplicateByUrl(candidates) {
  const map = new Map();
  for (const c of candidates) {
    const key = new URL(c.url).pathname; // normalize
    if (map.has(key)) {
      map.get(key).searchHits++;
    } else {
      c.searchHits = 1;
      map.set(key, c);
    }
  }
  return Array.from(map.values());
}
```

---

## Step 2: READ — Get full article content + images

### Tools: Tavily raw_content (primary) + Jina Reader (fallback)

Most articles will already have `raw_content` from Step 1. For those that don't, use Jina Reader.

### Jina Reader API Call
```javascript
async function readWithJina(url) {
  const response = await fetch(`https://r.jina.ai/${url}`, {
    headers: {
      'Accept': 'text/plain',
      // Optional: 'Authorization': `Bearer ${process.env.JINA_API_KEY}`
    }
  });

  if (!response.ok) {
    throw new Error(`Jina returned ${response.status} for ${url}`);
  }

  const markdown = await response.text();
  return markdown;
  // Returns markdown with:
  // - Title: ...
  // - URL Source: ...
  // - Published Time: ...
  // - Markdown Content: full article
  // - Image URLs embedded as ![alt](url) in the markdown
}
```

### Image Extraction from Jina Markdown
```javascript
function extractImagesFromMarkdown(markdown) {
  const regex = /!\[([^\]]*)\]\((https?:\/\/[^\)]+)\)/g;
  const images = [];
  let match;
  while ((match = regex.exec(markdown)) !== null) {
    images.push({ alt: match[1], url: match[2] });
  }
  return images;
}
```

### Combined Read Logic
```javascript
async function readArticle(candidate) {
  let fullText = candidate.raw_content;
  let images = candidate.images || [];
  let readMethod = 'tavily';

  // If Tavily didn't return full content, use Jina
  if (!fullText || fullText.length < 1200) {
    try {
      const jinaMarkdown = await readWithJina(candidate.url);
      fullText = jinaMarkdown;
      readMethod = 'jina';

      // Extract additional images from Jina markdown
      const jinaImages = extractImagesFromMarkdown(jinaMarkdown);
      images = [...images, ...jinaImages.map(i => i.url)];
    } catch (e) {
      console.warn(`Jina failed for ${candidate.url}: ${e.message}`);
      // Use snippet as last resort
      fullText = candidate.snippet;
      readMethod = 'snippet_only';
    }
  }

  return {
    ...candidate,
    fullText,
    images: [...new Set(images)], // deduplicate image URLs
    readMethod
  };
}
```

### Tested Reliability (April 2026)

| Source Domain | Jina Reader | Tavily raw_content |
|---|---|---|
| mediaoffice.ae | ✅ 9.6KB | not tested |
| nme.com | ✅ 16.6KB | not tested |
| swimswam.com | ❌ 451 rate limited | not tested |
| usmagazine.com | not tested | ✅ 24KB |
| goodhousekeeping.com | not tested | ✅ 15.7KB |
| earth.com | not tested | ✅ worked |
| atptour.com | not tested | ✅ worked |

**Key:** Tavily `raw_content` is more reliable overall. Jina is free and good as backup but some domains block it.

---

## Step 3: VET — Check if kid-appropriate

### Tool: DeepSeek V3 API (OpenAI-compatible)

**Endpoint:** `POST https://api.deepseek.com/chat/completions`
**Model:** `deepseek-chat` (V3)
**Cost:** ~$0.27/M input tokens, ~$1.10/M output tokens

### System Prompt (Vetter)
```
You are a content safety reviewer for a kids news site (ages 8-13, grades 3-8).

Rate this article on each dimension (0=none, 1=minimal, 2=mild, 3=moderate, 4=significant, 5=severe):
- Violence/Conflict
- Sexual Content
- Substance Use
- Profanity/Language
- Fear/Horror
- Complex Adult Themes
- Emotional Distress
- Bias/Stereotypes

Return ONLY valid JSON (no markdown, no code blocks, no explanation):
{
  "scores": { "violence": 0, "sexual": 0, "substance": 0, "language": 0, "fear": 0, "adult_themes": 0, "distress": 0, "bias": 0 },
  "total": 0,
  "verdict": "SAFE|CAUTION|REJECT",
  "flags": ["any specific concerns"],
  "rewrite_notes": "suggestions if CAUTION"
}
```

### Scoring Rules
- **SAFE** (0-8): Auto-proceed to rewrite
- **CAUTION** (9-20): Proceed but apply rewrite_notes during rewrite
- **REJECT** (21-40): Skip this article entirely

### API Call
```javascript
async function vetArticle(articleText) {
  const response = await fetch('https://api.deepseek.com/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`
    },
    body: JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        { role: 'system', content: VETTER_SYSTEM_PROMPT },
        { role: 'user', content: `Article to review:\n\n${articleText}` }
      ],
      temperature: 0.1,   // low temp for consistent scoring
      max_tokens: 500
    })
  });

  const data = await response.json();
  const content = data.choices[0].message.content;

  // Parse JSON (strip markdown code fences if DeepSeek adds them)
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  return JSON.parse(cleaned);
}
```

### Input
```javascript
{
  articleText: "Full article text from Step 2 (string, 1000-20000 chars)"
}
```

### Output
```javascript
{
  "scores": {
    "violence": 0,
    "sexual": 0,
    "substance": 0,
    "language": 0,
    "fear": 1,
    "adult_themes": 1,
    "distress": 0,
    "bias": 0
  },
  "total": 2,
  "verdict": "SAFE",
  "flags": ["mentions microplastics in human bodies — mild fear factor"],
  "rewrite_notes": ""
}
```

---

## Step 4: REWRITE — Kid-friendly English + Chinese translation

### Tool: DeepSeek V3 API

Same endpoint as vetting, different system prompt.

### System Prompt (Rewriter)
```
You are a news writer for "News Oh,Ye!" — a bilingual kids news site for ages 8-13.

RULES:
1. ACCURACY IS #1 — never add facts not in the source article. Every claim must be traceable to the source.
2. Write at a 5th grade reading level (short sentences, simple words)
3. Keep it engaging — use active voice, rhetorical questions, fun comparisons
4. Include specific dates, numbers, and names from the source
5. English body: 200-350 words. Chinese body: 200-350 characters equivalent.
6. Add a "Why It Matters" section explaining significance for kids
7. Suggest a fun, curiosity-driven headline in both languages
8. If vetter flagged any concerns, apply the rewrite_notes to soften those areas

Return ONLY valid JSON (no markdown, no code blocks):
{
  "headline_en": "Fun engaging headline in English",
  "headline_zh": "有趣的中文标题",
  "body_en": "Full article body in English (markdown OK)",
  "body_zh": "完整的中文文章正文",
  "why_it_matters_en": "1-2 sentences on why kids should care",
  "why_it_matters_zh": "为什么这对孩子们很重要",
  "category": "News|Science|Fun",
  "article_date": "2026-04-21"
}
```

### API Call
```javascript
async function rewriteArticle(articleText, vetterResult, sourceUrls, sourceNames) {
  const userMessage = `Source article:\n\n${articleText}\n\n` +
    `Vetter result: ${JSON.stringify(vetterResult)}\n\n` +
    `Sources: ${sourceUrls.join(', ')}\n` +
    `Source names: ${sourceNames.join(', ')}`;

  const response = await fetch('https://api.deepseek.com/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`
    },
    body: JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        { role: 'system', content: REWRITER_SYSTEM_PROMPT },
        { role: 'user', content: userMessage }
      ],
      temperature: 0.3,   // slightly creative for engaging writing
      max_tokens: 2000
    })
  });

  const data = await response.json();
  const content = data.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  return JSON.parse(cleaned);
}
```

### Input
```javascript
{
  articleText: "Full source article text",
  vetterResult: { /* output from Step 3 */ },
  sourceUrls: ["https://npr.org/...", "https://cnn.com/..."],
  sourceNames: ["NPR", "CNN"]
}
```

### Output
```javascript
{
  "headline_en": "Apple Gets a New Boss! Tim Cook Steps Down After 15 Years",
  "headline_zh": "苹果换新掌门人啦！蒂姆·库克卸任15年CEO",
  "body_en": "Big news from one of the world's most famous companies!...",
  "body_zh": "来自全球最著名科技公司的大新闻！...",
  "why_it_matters_en": "Apple makes products that billions of people use...",
  "why_it_matters_zh": "苹果的产品被全球数十亿人使用...",
  "category": "tech",
  "article_date": "2026-04-21"
}
```

---

## Step 5: STORE — Save to Supabase

### Supabase Setup

Write the redesign pipeline into a new parallel table family first.

Do not write the redesign pipeline into the existing `articles` table during validation.

Apply the baseline SQL in:

- `supabase/migrations/20260423_redesign_parallel_schema.sql`

### Table Family
```sql
-- Created by supabase/migrations/20260423_redesign_parallel_schema.sql
-- Main tables:
--   redesign_runs
--   redesign_candidates
--   redesign_stories
--   redesign_story_variants
--   redesign_story_sources
```

### Insert Pattern
```javascript
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

async function storeStory(runId, story, candidate, variantPayloads) {
  const { data: storyRows, error: storyError } = await supabase
    .from('redesign_stories')
    .insert({
      run_id: runId,
      candidate_id: candidate.id,
      published_date: story.article_date,
      category: story.category,
      story_slot: story.story_slot,
      canonical_title: story.headline_en,
      canonical_source_url: candidate.url,
      primary_image_url: candidate.images?.[0] || null,
      primary_image_credit: extractDomain(candidate.images?.[0] || ''),
      vetter_score: story.vetterResult.total,
      vetter_verdict: story.vetterResult.verdict,
      publish_status: 'published'
    })
    .select();

  if (storyError) throw storyError;

  const storyId = storyRows[0].id;

  const { error: variantError } = await supabase
    .from('redesign_story_variants')
    .insert(variantPayloads.map((variant) => ({
      story_id: storyId,
      ...variant,
    })));

  if (variantError) throw variantError;

  return storyRows[0];
}

function extractDomain(url) {
  try { return new URL(url).hostname.replace('www.', ''); }
  catch { return ''; }
}
```

---

## Full Pipeline Orchestration

```javascript
// pipeline.mjs — main entry point
import 'dotenv/config';

async function runPipeline() {
  const runId = crypto.randomUUID();
  const log = [];
  const startTime = Date.now();

  console.log(`\n[${runId}] Pipeline starting...`);

  // ── Step 1: Discover ──
  console.log('[1/5] Discovering articles...');
  const candidates = await discover();
  console.log(`  Found ${candidates.length} candidates`);
  log.push({ step: 'discover', count: candidates.length });

  // ── Step 2: Read full content ──
  console.log('[2/5] Reading full articles...');
  const articles = [];
  for (const c of candidates) {
    try {
      const article = await readArticle(c);
      if (article.fullText && article.fullText.length >= 500) {
        articles.push(article);
      }
    } catch (e) {
      console.warn(`  Skip ${c.url}: ${e.message}`);
    }
  }
  console.log(`  ${articles.length} articles with full content`);
  log.push({ step: 'read', count: articles.length });

  // ── Step 3: Vet for kid safety ──
  console.log('[3/5] Vetting articles...');
  const vetted = [];
  for (const article of articles) {
    try {
      const result = await vetArticle(article.fullText);
      console.log(`  ${article.title.substring(0, 40)}... → ${result.verdict} (${result.total}/40)`);

      if (result.verdict === 'REJECT') {
        log.push({ step: 'vet', title: article.title, verdict: 'REJECT', score: result.total });
        continue; // skip rejected articles
      }

      vetted.push({ article, vetterResult: result });
    } catch (e) {
      console.warn(`  Vet failed for ${article.title}: ${e.message}`);
    }
  }
  console.log(`  ${vetted.length} articles passed vetting`);
  log.push({ step: 'vet', passed: vetted.length });

  // ── Pick top articles for first-pass detail generation ──
  const TARGET_COUNT = parseInt(process.env.DETAIL_CANDIDATE_COUNT || '5');
  const topArticles = vetted
    .sort((a, b) => a.vetterResult.total - b.vetterResult.total) // safest first
    .slice(0, TARGET_COUNT);

  // ── Step 4: Rewrite for kids + translate ──
  console.log('[4/5] Rewriting articles...');
  const rewritten = [];
  for (const { article, vetterResult } of topArticles) {
    try {
      const result = await rewriteArticle(
        article.fullText,
        vetterResult,
        [article.url],
        [extractDomain(article.url)]
      );

      // Validate output has required fields
      if (!result.headline_en || !result.body_en || !result.body_zh) {
        throw new Error('Missing required fields in rewrite output');
      }

      rewritten.push({ article, vetterResult, rewriteResult: result });
      console.log(`  ✅ ${result.headline_en.substring(0, 50)}...`);
    } catch (e) {
      console.warn(`  Rewrite failed: ${e.message}`);
    }
  }
  log.push({ step: 'rewrite', count: rewritten.length });

  // ── Step 5: Store in Supabase ──
  console.log('[5/5] Storing articles...');
  const stored = [];
  for (const { article, vetterResult, rewriteResult } of rewritten) {
    try {
      const row = await storeArticle(rewriteResult, vetterResult, article);
      stored.push(row);
      console.log(`  💾 Stored: ${row.id}`);
    } catch (e) {
      console.warn(`  Store failed: ${e.message}`);
    }
  }
  log.push({ step: 'store', count: stored.length });

  // ── Summary ──
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`\n[${runId}] Pipeline complete in ${elapsed}s`);
  console.log(`  Discovered: ${candidates.length}`);
  console.log(`  Read: ${articles.length}`);
  console.log(`  Vetted (passed): ${vetted.length}`);
  console.log(`  Rewritten: ${rewritten.length}`);
  console.log(`  Stored: ${stored.length}`);

  return { runId, log, stored };
}

runPipeline().catch(console.error);
```

---

## Image Handling — Detailed Flow

Images come from two sources, used in priority order:

### Priority 1: Tavily `include_images`
When Tavily searches, `include_images: true` returns an `images[]` array of URLs found on the results pages. These are typically article hero images.

### Priority 2: Jina Reader markdown
When Jina reads an article, the markdown includes `![alt](url)` image tags. Parse them with:
```javascript
const images = extractImagesFromMarkdown(jinaMarkdown);
```

### Priority 3: Tavily image search (dedicated)
If neither source has a good image, run a separate Tavily search specifically for images:
```javascript
const imgResult = await fetch('https://api.tavily.com/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    api_key: process.env.TAVILY_API_KEY,
    query: `${articleTitle} photo`,
    search_depth: 'basic',
    include_images: true,
    max_results: 1
  })
});
const imgData = await imgResult.json();
const imageUrl = imgData.images?.[0] || null;
```

### Image Selection Logic
```javascript
function selectBestImage(candidate) {
  const images = candidate.images || [];
  if (images.length === 0) return { url: null, credit: '' };

  // Filter out tiny icons, logos, tracking pixels
  const good = images.filter(url => {
    const lower = url.toLowerCase();
    return !lower.includes('logo') &&
           !lower.includes('icon') &&
           !lower.includes('avatar') &&
           !lower.includes('tracking') &&
           !lower.includes('1x1') &&
           !lower.includes('pixel');
  });

  const best = good[0] || images[0];
  return {
    url: best,
    credit: extractDomain(best)
  };
}
```

---

## API Reference Summary

| API | Endpoint | Auth | Key Params |
|---|---|---|---|
| **Tavily Search** | `POST https://api.tavily.com/search` | `api_key` in body | `query`, `search_depth`, `include_raw_content`, `include_images`, `max_results` |
| **Jina Reader** | `GET https://r.jina.ai/{url}` | `Authorization: Bearer` header (optional) | URL path param |
| **DeepSeek Chat** | `POST https://api.deepseek.com/chat/completions` | `Authorization: Bearer` header | `model: "deepseek-chat"`, `messages[]`, `temperature`, `max_tokens` |
| **Supabase** | `POST https://{project}.supabase.co/rest/v1/redesign_*` | `apikey` + `Authorization` headers | Parallel redesign tables |

---

## Cost Estimate (per category run: 10 vetted candidates, 5 detailed candidates, target 3 published stories)

| Service | Usage | Cost |
|---|---|---|
| Tavily Search | enough searches to produce 6 new-pipeline candidates | ~$0.04-$0.06 |
| RSS intake | 4 curated candidates | $0.00 |
| Jina Reader | fallback reads for missing raw content | $0.00 (free tier) |
| DeepSeek (vet) | 10 candidates × ~3K tokens each | ~$0.01 |
| DeepSeek (rewrite) | up to 5 detail candidates × ~5K tokens each | ~$0.01 |
| Supabase | inserts into redesign tables | $0.00 (free tier) |
| **Total per category run** | | **~$0.07-$0.09** |
| **Daily across 3 categories** | | **~$0.21-$0.27** |

---

## Testing Plan

### Test 1: Discovery only
```bash
TAVILY_API_KEY=... node -e "
  // paste discover() function
  // verify: returns 15-20 candidates with titles, URLs, snippets
"
```
**Expected:** 15-20 unique article URLs with titles.

### Test 2: Read one article
```bash
# Test Tavily raw_content
node -e "/* call discoverArticles('Apple CEO') with include_raw_content:true, check raw_content length */"

# Test Jina Reader fallback
node -e "/* call readWithJina('https://news.vt.edu/articles/2026/01/science-murder-muppet.html') */"
```
**Expected:** Full article text > 1200 chars.

### Test 3: Vet comparison (DeepSeek vs Claude)
```bash
# Use the comparison script we already built:
node ~/.claude/vetter-comparison-test.mjs
# Or with Claude:
ANTHROPIC_API_KEY=... node ~/.claude/vetter-comparison-test.mjs
```
**Expected:** Both models agree on SAFE/CAUTION/REJECT for the sample articles.

### Test 4: Rewrite quality
```bash
node -e "/* call rewriteArticle() with one article, inspect:
  - headline_en is engaging, kid-friendly
  - body_en is 200-350 words, 5th grade level
  - body_zh is natural Chinese (not robotic translation)
  - no facts added beyond source
*/"
```

### Test 5: Full pipeline dry run
```bash
TAVILY_API_KEY=... DEEPSEEK_API_KEY=... node pipeline.mjs
```
**Expected:**
- Discovers enough candidates for one category funnel
- Reads full content for 80%+
- Vets 10 candidates for the category lane
- Rewrites up to 5 detailed candidates
- Publishes 3 final stories when enough publishable candidates exist
- Writes into `redesign_*` tables, not the old `articles` table

### Golden Test Fixtures

Create these JSON files for regression testing:

1. `fixtures/safe_article.json` — Earth Day article → expected SAFE (0-3)
2. `fixtures/caution_article.json` — article with mild war references → expected CAUTION (9-15)
3. `fixtures/reject_article.json` — shooting/violence article → expected REJECT (21+)
4. `fixtures/rewrite_output.json` — expected shape of rewrite output

---

## Project Structure

```
news-pipeline/
├── .env                          # API keys (gitignored)
├── .env.example                  # template
├── package.json
├── pipeline.mjs                  # main orchestrator
├── src/
│   ├── discover.mjs              # Step 1: Tavily search
│   ├── read.mjs                  # Step 2: Tavily + Jina reader
│   ├── vet.mjs                   # Step 3: DeepSeek vetter
│   ├── rewrite.mjs               # Step 4: DeepSeek rewriter
│   ├── store.mjs                 # Step 5: Supabase insert
│   ├── images.mjs                # Image selection logic
│   └── prompts/
│       ├── vetter.txt             # Vetter system prompt
│       └── rewriter.txt           # Rewriter system prompt
├── fixtures/
│   ├── safe_article.json
│   ├── caution_article.json
│   ├── reject_article.json
│   └── rewrite_output.json
├── test/
│   ├── discover.test.mjs
│   ├── vet.test.mjs
│   ├── rewrite.test.mjs
│   └── vetter-comparison.test.mjs
└── README.md
```

---

## Key Design Decisions

1. **DeepSeek over Claude for vetting+rewriting:** 10-20x cheaper ($3.50/mo vs $60/mo). DeepSeek is strong at Chinese translation (native bilingual model). If safety vetting accuracy is a concern, can add Claude as a secondary vetter for borderline CAUTION scores only.

2. **Tavily as primary search+reader:** One API call gets search results + full article text + images. Eliminates need for separate scraping.

3. **Jina Reader as fallback only:** Free tier (10M tokens), but some domains block it. Used only when Tavily `raw_content` is null.

4. **Exa.ai for cross-verification (optional):** Can add later to verify stories are real and widely reported. Free tier: 1,000 searches. Paid: $40/mo.

5. **Temperature settings:** Vetter uses 0.1 (consistent scores), Rewriter uses 0.3 (engaging but controlled writing).

6. **Parallel rollout first:** redesign writes to `redesign_*` tables while the old project keeps using the current schema.
7. **Articles as published:** SAFE and CAUTION both publish after rewrite; only REJECT is blocked.
