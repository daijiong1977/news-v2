# KidsNews v2 — Phase 1: Static UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the `news_v2/newdesign/` React prototype into the kidsnews repo under `/v2/`, wire it to real JSON payload files, and ship it to Vercel at `https://news.6ray.com/v2/` without touching v1.

**Architecture:** Prototype already runs React+Babel-standalone in the browser — treat it as static HTML. Replace the mock `ARTICLES` array (in `data.jsx`) with an async loader that fetches `/v2/payloads/<date>/manifest.json` + per-category JSON at page load.

**Axes are independent:**
- **Level toggle** (English only): Sprout → `easy_en`, Tree → `middle_en`
- **Language toggle**: EN / ZH. ZH shows `zh` summary cards (level toggle hidden); click routes to the `middle_en` detail for the same story (since there is no Chinese detail page).

Each article carries both `level` ∈ {Sprout, Tree} and `language` ∈ {en, zh}. Home page filters by both axes.

**Tech Stack:** Static HTML, React 18 (UMD), Babel standalone, Google Fonts (Fraunces + Nunito), Vercel. No npm, no build step.

**Working branch:** `redesign` in `/Users/jiong/myprojects/kidsnews` (already checked out).

**Out of scope for Phase 1:** pipeline code, zip export, Supabase writes. This phase ships a UI that loads from a static `/v2/payloads/` directory checked into git with hand-crafted sample data.

---

## File Structure

```
kidsnews/
├── v2/                          # NEW — everything under this folder is v2
│   ├── index.html               # entry point (ports News Oh,Ye! prototype.html)
│   ├── article.html             # identical to index.html; routed via ?page=article
│   ├── home.jsx                 # copied from news_v2/newdesign/home.jsx
│   ├── article.jsx              # copied from news_v2/newdesign/article.jsx
│   ├── components.jsx           # copied from news_v2/newdesign/components.jsx
│   ├── user-panel.jsx           # copied from news_v2/newdesign/user-panel.jsx
│   ├── data.jsx                 # REWRITTEN — async loader, not mock array
│   └── payloads/
│       └── 2026-04-23/          # seed sample, hand-crafted
│           ├── manifest.json    # { "date": "...", "categories": ["News","Science","Fun"] }
│           ├── news.json        # { "stories": [ {slot:1,...}, {slot:2,...}, {slot:3,...} ] }
│           ├── science.json
│           └── fun.json
└── vercel.json                  # ADD cache header rule for /v2/payloads/
```

**Why one entry HTML for both home + article?** The prototype's single-page React app handles routing internally via `localStorage` + `route` state. No need to split into multiple HTMLs.

**Payload shape** (per `redesign_published_variants_v` view, projected to flat JSON):

```json
{
  "date": "2026-04-23",
  "category": "News",
  "stories": [
    {
      "id": "2026-04-23-news-1",
      "slot": 1,
      "image_url": "https://...",
      "image_credit": "apple.com",
      "source_url": "https://apple.com/...",
      "vetter_verdict": "SAFE",
      "variants": {
        "easy_en":   { "headline": "...", "body": "...", "why_it_matters": "...", "keywords": [...], "quiz": [...], "discussion": [...] },
        "middle_en": { "headline": "...", "body": "...", "why_it_matters": "...", "keywords": [...], "quiz": [...], "discussion": [...] },
        "zh":        { "headline": "...", "summary": "...", "why_it_matters": "..." }
      }
    }
  ]
}
```

Note: `zh` variant has only `headline`, `summary`, `why_it_matters` — no `body`/`keywords`/`quiz`/`discussion`. Chinese is summary-only per redesign contract.

---

## Task 1: Scaffold `v2/` directory and copy static prototype assets

**Files:**
- Create: `kidsnews/v2/index.html`
- Create: `kidsnews/v2/home.jsx` (copy from news_v2/newdesign/home.jsx)
- Create: `kidsnews/v2/article.jsx` (copy from news_v2/newdesign/article.jsx)
- Create: `kidsnews/v2/components.jsx` (copy from news_v2/newdesign/components.jsx)
- Create: `kidsnews/v2/user-panel.jsx` (copy from news_v2/newdesign/user-panel.jsx)

- [ ] **Step 1: Create `kidsnews/v2/index.html` from the prototype template**

Copy `/Users/jiong/myprojects/news_v2/newdesign/News Oh,Ye! prototype.html` to `/Users/jiong/myprojects/kidsnews/v2/index.html` exactly — no modifications yet. The script src paths (`data.jsx`, `components.jsx`, etc.) are relative so they resolve inside `/v2/`.

- [ ] **Step 2: Copy the five JSX files** (including `data.jsx` — it will be replaced in Task 3, but the prototype needs it to render for the Task 1 smoke test)

```bash
cp /Users/jiong/myprojects/news_v2/newdesign/data.jsx \
   /Users/jiong/myprojects/news_v2/newdesign/home.jsx \
   /Users/jiong/myprojects/news_v2/newdesign/article.jsx \
   /Users/jiong/myprojects/news_v2/newdesign/components.jsx \
   /Users/jiong/myprojects/news_v2/newdesign/user-panel.jsx \
   /Users/jiong/myprojects/kidsnews/v2/
```

- [ ] **Step 3: Start a local server and verify the prototype renders untouched**

```bash
cd /Users/jiong/myprojects/kidsnews && python3 -m http.server 8000
```

Open `http://localhost:8000/v2/` in a browser. Expected: the prototype home page loads with mock data, category tabs work, article page opens.

If the page is blank or shows a React error, fix path issues before proceeding. `data.jsx` is still the mock file at this point — that's fine, we replace it in Task 3.

- [ ] **Step 4: Commit**

```bash
cd /Users/jiong/myprojects/kidsnews
git add v2/index.html v2/home.jsx v2/article.jsx v2/components.jsx v2/user-panel.jsx v2/data.jsx
git commit -m "feat(v2): import redesign prototype under /v2/"
```

Do NOT `git add v2/` with a trailing slash — we'll add payloads in Task 2 as a separate commit.

---

## Task 2: Seed a sample payload directory

**Files:**
- Create: `kidsnews/v2/payloads/2026-04-23/manifest.json`
- Create: `kidsnews/v2/payloads/2026-04-23/news.json`
- Create: `kidsnews/v2/payloads/2026-04-23/science.json`
- Create: `kidsnews/v2/payloads/2026-04-23/fun.json`

- [ ] **Step 1: Write `manifest.json`**

```json
{
  "date": "2026-04-23",
  "generated_at": "2026-04-23T12:00:00Z",
  "categories": ["News", "Science", "Fun"]
}
```

- [ ] **Step 2: Write `news.json` with 3 stories, all three variants each**

Pull from the mock `ARTICLES` array in `news_v2/newdesign/data.jsx` — use the first 3 News items (Apple CEO, Earth Day, etc.) as source content. Each story must include `easy_en`, `middle_en`, `zh` variants. For `zh`, translate the summary only; no body.

Shape (full example):

```json
{
  "date": "2026-04-23",
  "category": "News",
  "stories": [
    {
      "id": "2026-04-23-news-1",
      "slot": 1,
      "image_url": "https://img.odcdn.com.br/wp-content/uploads/2026/01/Destaque-John-Ternus-e-Tim-Cook-1920x1080.jpg",
      "image_credit": "odcdn.com.br",
      "source_url": "https://apple.com/newsroom/...",
      "source_name": "Apple Newsroom",
      "vetter_verdict": "SAFE",
      "variants": {
        "easy_en": {
          "headline": "Apple Gets a New Boss! Tim Cook Steps Down After 15 Years",
          "body": "Big news from Apple! ...",
          "why_it_matters": "Apple makes things billions of kids and grownups use every day.",
          "keywords": [
            {"term": "CEO", "def": "Chief Executive Officer — the top boss who runs a company."}
          ],
          "quiz": [
            {"q": "When will John Ternus become Apple's new CEO?", "options": ["August 31","September 1","April 20","January 1"], "a": 1}
          ],
          "discussion": ["If you ran a giant company, what new invention would you ask your team to build first?"]
        },
        "middle_en": { "headline": "...", "body": "...", "why_it_matters": "...", "keywords": [...], "quiz": [...], "discussion": [...] },
        "zh": { "headline": "苹果换新掌门人啦！", "summary": "苹果宣布蒂姆·库克将于8月31日卸任CEO...", "why_it_matters": "苹果的产品被全球数十亿人使用。" }
      }
    },
    { "id": "2026-04-23-news-2", "slot": 2, "...": "..." },
    { "id": "2026-04-23-news-3", "slot": 3, "...": "..." }
  ]
}
```

Repeat the same 3-story structure for `science.json` and `fun.json`, pulling content from the corresponding mock articles.

- [ ] **Step 3: Validate JSON files parse**

```bash
for f in v2/payloads/2026-04-23/*.json; do python3 -c "import json; json.load(open('$f'))" && echo "$f OK"; done
```

Expected: all 4 files print `OK`.

- [ ] **Step 4: Commit**

```bash
git add v2/payloads/
git commit -m "feat(v2): seed sample payload for 2026-04-23"
```

---

## Task 3: Rewrite `data.jsx` as an async payload loader

**Files:**
- Create: `kidsnews/v2/data.jsx`

- [ ] **Step 1: Write `data.jsx` that fetches payloads, then populates the same globals the prototype expects**

The prototype reads `window.ARTICLES`, `window.CATEGORIES`, `window.LEVELS`, `window.MOCK_USER`. Keep `CATEGORIES`, `LEVELS`, `MOCK_USER` as-is (they're static). Replace `ARTICLES` construction with a loader.

```jsx
// v2/data.jsx — async payload loader
// Populates window.ARTICLES from /v2/payloads/<date>/<category>.json
// Preserves the same object shape the prototype's home.jsx/article.jsx expect.

const CATEGORIES = [
  { id: "news",    label: "News",    emoji: "📰", color: "#ff6b5b", bg: "#ffece8" },
  { id: "science", label: "Science", emoji: "🔬", color: "#17b3a6", bg: "#e0f6f3" },
  { id: "fun",     label: "Fun",     emoji: "🎈", color: "#9061f9", bg: "#eee5ff" },
];

const LEVELS = [
  { id: "Sprout", emoji: "🌱", label: "Sprout", sub: "Easy English" },
  { id: "Tree",   emoji: "🌳", label: "Tree",   sub: "Middle English" },
];

const MOCK_USER = {
  name: "Mia", streak: 7, minutesToday: 6, dailyGoal: 15,
  totalXp: 1240, weekXp: 310, badges: ["🦉","🔭","🌱"], readToday: [],
};

// --- Payload → prototype article shape ---
function variantToSproutArticle(story, variant, category) {
  return {
    id: story.id + "-sprout",
    day: 0,
    storyId: story.id,
    title: variant.headline,
    summary: variant.body.split("\n\n")[0] || variant.body.slice(0, 280),
    body: variant.body,
    image: story.image_url,
    category: category,
    source: story.source_name || "",
    time: story.date || "",
    readMins: Math.max(3, Math.round((variant.body.length || 600) / 200)),
    level: "Sprout",
    language: "en",
    xp: 30,
    keywords: variant.keywords || [],
    quiz: (variant.quiz || []).map(q => ({ q: q.q, options: q.options, a: q.a })),
    discussion: variant.discussion || [],
    whyItMatters: variant.why_it_matters || "",
  };
}

function variantToTreeArticle(story, variant, category) {
  return { ...variantToSproutArticle(story, variant, category),
    id: story.id + "-tree", level: "Tree", xp: 45, readMins: Math.max(4, Math.round((variant.body.length || 900) / 200)) };
}

function variantToZhCard(story, variant, category) {
  return {
    id: story.id + "-zh",
    day: 0,
    storyId: story.id,             // pairs with -sprout / -tree twins
    title: variant.headline,
    summary: variant.summary || "",
    body: "",                      // intentionally empty — Chinese has no detail page
    image: story.image_url,
    category: category,
    source: story.source_name || "",
    time: story.date || "",
    readMins: 2,
    level: null,                   // language axis only — level toggle is hidden in ZH mode
    xp: 15,
    keywords: [],
    quiz: [],
    discussion: [],
    whyItMatters: variant.why_it_matters || "",
    language: "zh",
    noDetail: true,                // consumed by onOpen router
  };
}

async function loadPayloads() {
  const manifest = await fetch("payloads/2026-04-23/manifest.json").then(r => r.json());
  const articles = [];

  for (const category of manifest.categories) {
    const slug = category.toLowerCase();
    const payload = await fetch(`payloads/${manifest.date}/${slug}.json`).then(r => r.json());
    for (const story of payload.stories) {
      if (story.variants.easy_en)   articles.push(variantToSproutArticle(story, story.variants.easy_en, category));
      if (story.variants.middle_en) articles.push(variantToTreeArticle(story, story.variants.middle_en, category));
      if (story.variants.zh)        articles.push(variantToZhCard(story, story.variants.zh, category));
    }
  }
  return articles;
}

window.CATEGORIES = CATEGORIES;
window.LEVELS = LEVELS;
window.MOCK_USER = MOCK_USER;
window.ARTICLES = [];
window.__payloadsLoaded = loadPayloads().then(list => { window.ARTICLES = list; });
```

- [ ] **Step 2: Gate the React mount on `window.__payloadsLoaded`**

Edit `v2/index.html`, find the `mount()` function near the bottom (around line 241 in the prototype). Change:

```js
function mount() {
  if (!window.HomePage || !window.ArticlePage || !window.UserPanel) { setTimeout(mount, 50); return; }
  ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
}
setTimeout(mount, 0);
```

to:

```js
function mount() {
  if (!window.HomePage || !window.ArticlePage || !window.UserPanel) { setTimeout(mount, 50); return; }
  if (!window.__payloadsLoaded) { setTimeout(mount, 50); return; }
  window.__payloadsLoaded.then(() => {
    ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
  });
}
setTimeout(mount, 0);
```

- [ ] **Step 3: Manually verify in browser**

```bash
cd /Users/jiong/myprojects/kidsnews && python3 -m http.server 8000
```

Open `http://localhost:8000/v2/`. Expected: loading indicator briefly, then home page with **9 articles** (3 per category, Sprout level) visible when "🌱 Sprout" is selected. Toggle to "🌳 Tree" → see 3 Tree articles per category. Toggle language to Chinese → see 3 Chinese summary cards under Tree tab. Click any article → detail page opens.

- [ ] **Step 4: Commit**

```bash
git add v2/data.jsx v2/index.html
git commit -m "feat(v2): replace mock ARTICLES with async payload loader"
```

---

## Task 4a: Teach home.jsx to filter by language (Chinese is language, not level)

**Files:**
- Modify: `kidsnews/v2/home.jsx`

**Context:** The prototype was written assuming all articles are English and `tweaks.language === 'zh'` only changes UI labels/routing. With real payloads, English and Chinese cards coexist in `window.ARTICLES`. Home must:

- `language === 'en'` → filter `a.language === 'en' && a.category === cat && a.level === level`
- `language === 'zh'` → filter `a.language === 'zh' && a.category === cat` (ignore level; hide level toggle)

- [ ] **Step 1: Find the article filter in `home.jsx`**

```bash
grep -n "ARTICLES" /Users/jiong/myprojects/kidsnews/v2/home.jsx | head -10
```

Locate the line(s) that build the visible article list (something like `const visible = ARTICLES.filter(...)`). Note the exact pattern — the surrounding code determines how to inject the language check.

- [ ] **Step 2: Add language filter**

Pattern: whatever the current `.filter(...)` is, wrap/extend it so the predicate also checks `a.language === (tweaks.language || 'en')`. In Chinese mode, drop the `a.level === level` check.

Rough shape:

```js
const lang = tweaks?.language || 'en';
const visible = ARTICLES.filter(a => {
  if (a.category !== cat) return false;
  if (lang === 'zh') return a.language === 'zh';
  return a.language === 'en' && a.level === level;
});
```

- [ ] **Step 3: Hide the level toggle when language is Chinese**

Find the Level toggle render in `home.jsx` (Sprout/Tree buttons) and wrap in `{lang !== 'zh' && (...)}` or add `display: 'none'` when `lang === 'zh'`. The prototype already hides it in CN mode for the old mock data — confirm the existing hide-logic works with the new filter.

- [ ] **Step 4: Verify in browser**

Toggle EN + Sprout → 3 Sprout cards per category. EN + Tree → 3 Tree cards. ZH → 3 Chinese summary cards per category, no level toggle visible.

- [ ] **Step 5: Commit**

```bash
git add v2/home.jsx
git commit -m "feat(v2): filter articles by language axis (zh separate from level)"
```

---

## Task 4: Route Chinese clicks to middle_en (Tree) detail

**Files:**
- Modify: `kidsnews/v2/index.html` (the `onOpen` function, around line 132)

- [ ] **Step 1: Replace the `onOpen` function**

The prototype currently routes Chinese clicks to Sprout. Change it to the Tree (middle_en) twin using `storyId`:

```js
const onOpen = (id) => {
  // Chinese cards have no detail page — route to the middle_en (Tree) twin of the same story.
  const target = ARTICLES.find(a => a.id === id);
  if (target && target.noDetail && target.language === 'zh') {
    const twin = ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en' && a.level === 'Tree');
    if (twin) id = twin.id;
  }
  setRoute({ page:'article', articleId:id });
};
```

- [ ] **Step 2: Manually verify**

In browser: toggle language to Chinese, click a Chinese summary card. Expected: Tree-level English article detail page opens (not Sprout).

- [ ] **Step 3: Commit**

```bash
git add v2/index.html
git commit -m "feat(v2): route Chinese clicks to Tree-level English detail"
```

---

## Task 5: Vercel config — cache headers for payload files

**Files:**
- Modify: `kidsnews/vercel.json`

- [ ] **Step 1: Read current `vercel.json`**

```bash
cat vercel.json
```

- [ ] **Step 2: Add a cache rule for `/v2/payloads/*`**

Add to the `headers` array:

```json
{
  "source": "/v2/payloads/(.*)",
  "headers": [
    { "key": "Cache-Control", "value": "public, max-age=300, s-maxage=600, stale-while-revalidate=86400" }
  ]
}
```

Same rule as v1 `/payloads/` — 5 min browser, 10 min edge. Keeps v1 rule untouched.

- [ ] **Step 3: Validate JSON**

```bash
python3 -c "import json; json.load(open('vercel.json'))" && echo OK
```

- [ ] **Step 4: Commit**

```bash
git add vercel.json
git commit -m "chore(v2): cache headers for /v2/payloads"
```

---

## Task 6: Data alignment — scrub "Sports" residue, align Level copy

**Files:**
- Modify: `kidsnews/v2/payloads/2026-04-23/fun.json`

- [ ] **Step 1: Audit `fun.json` for "Sports" category tags**

```bash
grep -n -i "sport" v2/payloads/2026-04-23/fun.json
```

Per redesign contract §2: sports belongs under `Fun`, not a separate lane. Any story tagged `category: "Sports"` must be rewritten to `category: "Fun"`. The `tag` field (free-form) CAN still say "Sports" — that's just a descriptor.

- [ ] **Step 2: Fix any `"category": "Sports"` → `"category": "Fun"`**

Use Edit tool on each offending line.

- [ ] **Step 3: Validate**

```bash
grep -n '"category": "Sports"' v2/payloads/2026-04-23/*.json
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add v2/payloads/
git commit -m "chore(v2): fold Sports stories under Fun category"
```

---

## Task 7: End-to-end smoke test — deploy to Vercel preview

**Files:** none modified.

- [ ] **Step 1: Push branch**

```bash
git push -u origin redesign
```

- [ ] **Step 2: Open the Vercel preview URL**

Vercel auto-builds on push. In the GitHub PR, click the Vercel preview bot's URL (or check https://vercel.com/daijiong1977/kidsnews/deployments). Append `/v2/` to the preview URL.

- [ ] **Step 3: Manual test matrix** (in the deployed preview, NOT localhost)

| Scenario | Expected |
|---|---|
| Hit `/v2/` | Home loads with 9 Sprout articles (3 News, 3 Science, 3 Fun) |
| Click "🌳 Tree" | 9 Tree-level articles shown |
| Click language toggle → CN | 9 Chinese summary cards under Tree tab |
| Click Chinese card | Opens Tree-level English detail |
| Click Sprout article | Opens Sprout-level English detail with keywords, quiz, discussion |
| Hit `/v2/payloads/2026-04-23/news.json` directly | Raw JSON served with `Cache-Control: public, max-age=300...` |
| Hit `/` (v1) | Existing v1 site unchanged |

- [ ] **Step 4: If all scenarios pass, merge to main**

```bash
gh pr create --base main --head redesign --title "v2 static UI phase 1" --body "Phase 1 per docs/superpowers/plans/2026-04-23-kidsnews-v2-phase1-ui.md"
```

Do NOT merge until user approves.

---

## Open questions / follow-ups (not blocking Phase 1)

1. **Image hosting**: Sample payloads use remote image URLs (CDN links from source articles). For production, Phase 2 pipeline should either download images into `/v2/article_images/` (v1 pattern) or keep remote URLs. Decide in Phase 2.
2. **Font loading**: prototype uses Google Fonts CDN. v1 kidsnews self-hosts Newsreader. Acceptable to differ? (Prototype's Fraunces + Nunito is the design.) Assuming yes.
3. **localStorage namespace collision**: prototype uses keys like `ohye_level`, `ohye_cat`. v1 uses different keys. No conflict since they're on different paths, but worth noting.
4. **Legacy `Seedling` migration**: prototype code migrates `Seedling` → `Sprout` in localStorage. Keep it — harmless.

---

## Self-review checklist

- [x] **Spec coverage:** Contract §1 categories, §2 daily funnel (payload shape matches), §5 UI keep list (home/article/archive/user-panel all wired), §6 Sprout↔easy_en / Tree↔middle_en / Chinese mapping — all covered.
- [x] **Placeholder scan:** no TBD/TODO; every step has literal code or exact command.
- [x] **Type consistency:** `variantToSproutArticle` / `variantToTreeArticle` / `variantToZhCard` return the same shape consumed by existing `home.jsx` / `article.jsx` (id, title, summary, body, image, category, source, time, readMins, level, xp, keywords[], quiz[], discussion[]).

---

## Phase 2 + 3 preview (separate plans)

- **Phase 2 plan** (to write next): Node.js pipeline in `news_v2/` — implements Discover/Read/Vet/Rewrite/Store per `PIPELINE-IMPLEMENTATION.md` + §2 funnel. Writes to `redesign_*` tables.
- **Phase 3 plan** (after Phase 2): reads `redesign_published_variants_v`, emits the same JSON shape used in Task 2, packs into `website-v2-YYYY-MM-DD.zip`, pushes to kidsnews repo. New GitHub Action unpacks into `v2/payloads/`.

Together: Phase 1 proves the UI contract, Phase 2+3 replace hand-crafted payloads with automated ones.
