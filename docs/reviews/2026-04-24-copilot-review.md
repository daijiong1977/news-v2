# 🤖 Copilot CLI Session

> [!NOTE]
> - **Session ID:** `eab251e0-5b22-49cc-9fc7-56aa22e4b4ee`  
> - **Started:** 4/24/2026, 7:50:49 PM  
> - **Duration:** 6m 36s  
> - **Exported:** 4/24/2026, 7:57:25 PM  

---

<sub>⏱️ 1s</sub>

### 👤 User

Read docs/reviews/2026-04-24-review-brief.md carefully. It lists files + evaluation dimensions for the project at /Users/jiong/myprojects/news-v2 (News Oh,Ye! kids news site — Python pipeline + React prototype + GitHub Actions + Supabase + Vercel).

Review the codebase — pipeline/*.py, website/*.jsx, website/index.html, .github/workflows/daily-pipeline.yml. Use the format specified in the brief (Severity / File:line / What / Why / Fix). Cover correctness, security, failure modes, maintainability, architecture, and prompt engineering. Be specific — cite file:line for every finding.

End with a 3-5 line assessment + top-3 things to fix first.

Write the entire review (no preamble, no session markers) to stdout.

---

<sub>⏱️ 10s</sub>

### ✅ `skill`

**using-superpowers**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "using-superpowers"
}
```

</details>

```
Skill "using-superpowers" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>⏱️ 20s</sub>

### ✅ `skill`

**dispatching-parallel-agents**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "dispatching-parallel-agents"
}
```

</details>

```
Skill "dispatching-parallel-agents" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>⏱️ 31s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md.**

/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md

<details>
<summary>178 lines</summary>

````
1. # Code review brief — News Oh, Ye! v2 (news.6ray.com)
2. 
3. ## Project context
4. 
5. **Goal.** Bilingual kids news site (English easy / middle + 中文 summary).
6. Fully autonomous pipeline runs daily on GitHub Actions, produces 9 stories
7. (3 News / 3 Science / 3 Fun) plus per-story detail enrichment, ships to
8. Supabase Storage, and auto-deploys to Vercel at news.6ray.com.
9. 
10. **Three-repo architecture.**
11. - `news-v2` (this repo): Python pipeline + React prototype source. Runs the
12.   daily-pipeline workflow. Goes private eventually.
13. - `kidsnews-v2` (separate repo): tiny deploy shell. A sync workflow pulls
14.   `latest.zip` from Supabase Storage, unzips into `site/`, commits, Vercel
15.   auto-deploys.
16. - `kidsnews` (legacy, v1 reference at kidsnews.6ray.com): not relevant.
17. 
18. ## Flow
19. 
20. ```
21. GitHub Action (news-v2 · daily 06:20 UTC)
22.   └── python -m pipeline.full_round
23.         ├── RSS mine (3 sources × 3 categories, per-weekday rotation)
24.         ├── Phase A per source: vet 10 briefs, return top-4 verified candidates
25.         ├── past-dedup (3-day lookback, title ≥80% similar → drop)
26.         ├── cross-source dedup (promote next candidate on dup)
27.         ├── tri-variant rewrite (easy_en / middle_en / zh) via DeepSeek chat
28.         ├── detail enrich (keywords / questions / background / mind-tree /
29.         │     why_it_matters / perspectives) via DeepSeek reasoner
30.         │     — retries 3× on JSON parse; falls back to split 3-slot batches
31.         ├── image optimize (Pillow decode + libwebp cwebp/dwebp CLI)
32.         │     → Supabase Storage redesign-article-images bucket
33.         ├── persist runs + stories to Supabase tables
34.         └── pack_and_upload
35.               ├── validate_bundle (9 listings · 18 details · all images)
36.               ├── check_not_overwriting_newer (aborts if remote is fresher)
37.               ├── zip website/ → Supabase redesign-daily-content:latest.zip
38.               │     + <YYYY-MM-DD>.zip
39.               ├── latest-manifest.json + <YYYY-MM-DD>-manifest.json
40.               ├── per-day flat files under <YYYY-MM-DD>/ prefix (new)
41.               ├── backfill_missing_archive_dirs (extracts past zips if the
42.               │     flat dir is missing — runs only once per past date)
43.               ├── update archive-index.json (list of available dates)
44.               └── retention sweep (keep 30 days)
45. 
46. GitHub Action (kidsnews-v2 · cron :15 every 2h, or dispatch on pipeline success)
47.   └── downloads latest.zip → unzips into site/ → commits if changed → push
48. 
49. Vercel (on push to kidsnews-v2)
50.   └── deploys site/ to news.6ray.com
51. ```
52. 
53. ## Key files (by importance)
54. 
55. ### Pipeline (Python 3.11)
56. - `pipeline/full_round.py` — orchestrator. Aggregate → dedup → images →
57.   rewrite+enrich → persist → pack_and_upload.
58. - `pipeline/news_rss_core.py` — shared utilities. DeepSeek call wrappers
59.   with retry, vet/rewriter/enricher prompts, RSS fetch, duplicate checker.
60. - `pipeline/pack_and_upload.py` — validation + zip + manifest + per-day
61.   flat upload + archive-index + retention.
62. - `pipeline/image_optimize.py` — webp optimizer with shutil.which() for
63.   cross-platform CLI path.
64. - `pipeline/news_sources.py` / `science_sources.py` / `fun_sources.py` —
65.   RSS source registries (per-weekday rotation for Science/Fun).
66. - `pipeline/news_aggregate.py` / `science_aggregate.py` / `fun_aggregate.py`
67.   — per-category aggregators (mostly wrappers around `run_source_with_backups`).
68. - `pipeline/supabase_io.py` — DB insert/update helpers.
69. - `pipeline/rewrite_from_db.py` — resume pipeline from DB state (skip
70.   mining + image ops). Used for debug / partial-category re-runs.
71. 
72. ### Frontend (React 18 + Babel-standalone, in-browser JSX transpile)
73. - `website/index.html` — app shell. Loads data.jsx / components.jsx /
74.   home.jsx / article.jsx / user-panel.jsx. Owns top-level state (route,
75.   level, cat, archiveDay, progress, tweaks).
76. - `website/data.jsx` — payload loader. Fetches today's listings from
77.   `/payloads/*.json` (local). For archive mode, fetches from Supabase
78.   Storage `<date>/payloads/*.json`. Exposes window.loadArchive(date).
79. - `website/home.jsx` — listing page with feature + normal card variants,
80.   DatePopover for "View old news", footer generation timestamp.
81. - `website/article.jsx` — detail page: Read & Words / Background / Quiz
82.   / Think & Share tabs. Supports mind-tree Article_Structure for Tree
83.   level, 5W boxes for Sprout.
84. - `website/components.jsx` — shared UI bits (CatChip, XpBadge, etc.).
85. - `website/user-panel.jsx` — profile drawer (name / avatar / theme / level).
86. 
87. ### CI/CD
88. - `.github/workflows/daily-pipeline.yml` — news-v2 daily cron (pipeline).
89. - (kidsnews-v2 repo) `.github/workflows/sync-from-supabase.yml` — pulls
90.   latest.zip + commits.
91. - `requirements.txt` — Python deps.
92. - `pipeline/backfill_card_summaries.py`, `pipeline/augment_mined_at.py` —
93.   one-shots used historically.
94. 
95. ## What to evaluate
96. 
97. Focus where you'd expect bugs or future pain:
98. 
99. 1. **Correctness.**
100.    - `dedup_winners` → `pick_winners_with_dedup` refactor. Two overlapping
101.      ScienceDaily feeds produced the same article; fix was to return up
102.      to 4 candidates and promote next on dup. Check edge cases: all
103.      sources returning candidates that are all pairwise dupes; candidate
104.      exhaustion mid-loop.
105.    - `filter_past_duplicates` title-similarity at 0.80 — are there
106.      obvious false positives / negatives? (titles can differ
107.      significantly while being the same story; or be identical but
108.      different stories.)
109.    - `deepseek_*_call` retry logic — does it handle rate-limit
110.      (429) differently from JSON parse errors?
111.    - `detail_enrich` split-batch fallback — what if BOTH easy and
112.      middle sub-calls fail? Currently continues with partial details;
113.      downstream validator will catch.
114. 
115. 2. **Security.**
116.    - Supabase service key lives in a committed .env loader (module
117.      top-level), overridden by GitHub Actions secret at job start.
118.      Any path where the key could end up in a log?
119.    - Vercel.json Cache-Control of 5min for user-visible assets — any
120.      risk of serving private data?
121.    - DeepSeek API key is only used server-side; confirm no frontend
122.      references.
123.    - Any HTML injection paths in the rewriter output? UI highlights
124.      keywords by matching with user-content strings.
125. 
126. 3. **Failure modes.**
127.    - Pipeline partial failure (category rewrite succeeds but enrich
128.      fails): is there a state where a partial bundle gets uploaded?
129.      (We added `check_not_overwriting_newer` and `validate_bundle`.)
130.    - Supabase Storage quota exhaustion mid-upload.
131.    - Vercel build fails after kidsnews-v2 commit — the pipeline
132.      doesn't know; only manual intervention.
133.    - Browser with localStorage full / disabled.
134. 
135. 4. **Maintainability.**
136.    - `pipeline/news_rss_core.py` is ~1200 lines. Should it split?
137.    - `full_round.py` grew fast — orchestration, dedup, image-process
138.      helpers, persistence, emit — all in one file.
139.    - React app has no build step (Babel-standalone). Fine for a
140.      prototype; risky long-term. Recommendation?
141.    - Hardcoded `/Users/jiong/...` paths were a CI bug source today;
142.      are there others lurking?
143. 
144. 5. **Architecture.**
145.    - Three-repo split: authoring / deploy / legacy. Any cleaner alt?
146.    - The zip-over-Storage indirection vs directly pushing
147.      generated artifacts to the deploy repo.
148.    - Per-day flat files coexist with zips — redundant, or
149.      justified?
150.    - "CI-only, never run locally" guard (`check_not_overwriting_newer`)
151.      — robust enough? Any evasion paths?
152. 
153. 6. **Prompt engineering.**
154.    - Rewriter prompt vs enricher prompt — any accuracy-vs-creativity
155.      trade-offs worth flagging?
156.    - `card_summary` ≤ 120 words — is the prompt actually enforceable?
157.      (We also post-trim with a word cap.)
158.    - Past-dedup threshold of 0.80 title similarity — when would you
159.      lower or raise it?
160. 
161. ## Format of your review
162. 
163. For each finding, use:
164. 
165. - **Severity**: `Critical` / `Important` / `Minor` / `Info`
166. - **File:line** (or "cross-cutting")
167. - **What**: one-sentence description
168. - **Why it matters** (1-2 sentences)
169. - **Suggested fix** (concrete, if you have one)
170. 
171. Then at the end: 3-5 line assessment summary + top 3 things to fix first.
172. 
173. Do not nitpick style unless it materially affects clarity. Do not
174. suggest broad refactors without a specific incident that justifies
175. them. Trust that the design decisions (RSS-only, three-repo split,
176. zip-via-Supabase, React-without-build) are intentional unless you spot
177. evidence they're causing real problems.
178.
````

</details>


---

<sub>⏱️ 31s</sub>

### ✅ `glob`

**pipeline/*.py**

"pipeline/*.py"

<details>
<summary>42 matches</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/test_replacement_feeds.py
/Users/jiong/myprojects/news-v2/pipeline/news_guardian_full.py
/Users/jiong/myprojects/news-v2/pipeline/news_exa_list.py
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py
/Users/jiong/myprojects/news-v2/pipeline/config.py
/Users/jiong/myprojects/news-v2/pipeline/news_aj_full.py
/Users/jiong/myprojects/news-v2/pipeline/seed_source_configs.py
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py
/Users/jiong/myprojects/news-v2/pipeline/tune_query.py
/Users/jiong/myprojects/news-v2/pipeline/news_bbc_full.py
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py
/Users/jiong/myprojects/news-v2/pipeline/full_round.py
/Users/jiong/myprojects/news-v2/pipeline/discover.py
/Users/jiong/myprojects/news-v2/pipeline/image_optimize.py
/Users/jiong/myprojects/news-v2/pipeline/science_sources.py
/Users/jiong/myprojects/news-v2/pipeline/test_fun_feeds.py
/Users/jiong/myprojects/news-v2/pipeline/augment_mined_at.py
/Users/jiong/myprojects/news-v2/pipeline/vet.py
/Users/jiong/myprojects/news-v2/pipeline/tune_news.py
/Users/jiong/myprojects/news-v2/pipeline/__init__.py
/Users/jiong/myprojects/news-v2/pipeline/news_npr_full.py
/Users/jiong/myprojects/news-v2/pipeline/news_raw_list.py
/Users/jiong/myprojects/news-v2/pipeline/cleaner.py
/Users/jiong/myprojects/news-v2/pipeline/news_exa_pipeline.py
/Users/jiong/myprojects/news-v2/pipeline/enrich_existing.py
/Users/jiong/myprojects/news-v2/pipeline/news_aj_rss.py
/Users/jiong/myprojects/news-v2/pipeline/test_sciencedaily_topics.py
/Users/jiong/myprojects/news-v2/pipeline/science_aggregate.py
/Users/jiong/myprojects/news-v2/pipeline/fun_aggregate.py
/Users/jiong/myprojects/news-v2/pipeline/news_sources.py
/Users/jiong/myprojects/news-v2/pipeline/test_science_feeds.py
/Users/jiong/myprojects/news-v2/pipeline/news_aggregate.py
/Users/jiong/myprojects/news-v2/pipeline/news_pbs_full.py
/Users/jiong/myprojects/news-v2/pipeline/main.py
/Users/jiong/myprojects/news-v2/pipeline/fun_sources.py
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_enrich.py
/Users/jiong/myprojects/news-v2/pipeline/read.py
/Users/jiong/myprojects/news-v2/pipeline/output.py
/Users/jiong/myprojects/news-v2/pipeline/curator.py
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_rewrite.py
/Users/jiong/myprojects/news-v2/pipeline/backfill_card_summaries.py
```

</details>


---

<sub>⏱️ 31s</sub>

### ✅ `glob`

**website/*.jsx**

"website/*.jsx"

```
/Users/jiong/myprojects/news-v2/website/home.jsx
/Users/jiong/myprojects/news-v2/website/user-panel.jsx
/Users/jiong/myprojects/news-v2/website/article.jsx
/Users/jiong/myprojects/news-v2/website/data.jsx
/Users/jiong/myprojects/news-v2/website/components.jsx
```


---

<sub>⏱️ 31s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml.**

/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml (lines 1-250)

<details>
<summary>62 lines</summary>

```
1. name: Daily pipeline
2. 
3. on:
4.   workflow_dispatch: {}
5.   schedule:
6.     # 06:20 UTC daily ≈ 23:20 PT / 02:20 ET. Pick any time; kidsnews-v2 cron
7.     # then pulls latest.zip on its next `:15` of an even hour (≤2h lag).
8.     - cron: "20 6 * * *"
9. 
10. permissions:
11.   contents: read
12. 
13. jobs:
14.   run:
15.     runs-on: ubuntu-latest
16.     timeout-minutes: 30
17.     env:
18.       DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
19.       SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
20.       SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
21.     steps:
22.       - name: Checkout
23.         uses: actions/checkout@v4
24. 
25.       - name: Install libwebp (cwebp / dwebp)
26.         run: |
27.           sudo apt-get update -q
28.           sudo apt-get install -y -q webp
29. 
30.       - name: Set up Python
31.         uses: actions/setup-python@v5
32.         with:
33.           python-version: "3.11"
34.           cache: "pip"
35. 
36.       - name: Install Python deps
37.         run: |
38.           python -m pip install -U pip
39.           pip install -r requirements.txt
40. 
41.       - name: Write .env for modules that read it directly
42.         run: |
43.           umask 077
44.           cat > .env <<EOF
45.           DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
46.           SUPABASE_URL=${SUPABASE_URL}
47.           SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
48.           EOF
49. 
50.       - name: Run full_round
51.         run: python -m pipeline.full_round
52. 
53.       - name: Upload payloads artifact (debug)
54.         if: always()
55.         uses: actions/upload-artifact@v4
56.         with:
57.           name: website-payloads-${{ github.run_id }}
58.           path: |
59.             website/payloads/
60.             website/article_payloads/
61.           retention-days: 7
62.
```

</details>


---

<sub>⏱️ 31s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/index.html.**

/Users/jiong/myprojects/news-v2/website/index.html (lines 1-250)

<details>
<summary>250 lines</summary>

```
1. <!doctype html>
2. <html lang="en">
3. <head>
4. <meta charset="utf-8"/>
5. <meta name="viewport" content="width=device-width,initial-scale=1"/>
6. <title>News Oh,Ye! — Kids News Prototype</title>
7. <link rel="preconnect" href="https://fonts.googleapis.com">
8. <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
9. <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700;9..144,800;9..144,900&family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
10. <style>
11.   html, body { margin:0; padding:0; font-family: 'Nunito', sans-serif; background:#fff9ef; color:#1b1230; }
12.   * { box-sizing: border-box; -webkit-font-smoothing: antialiased; }
13.   button { font-family: 'Nunito', sans-serif; }
14.   ::selection { background:#ffc83d; color:#1b1230; }
15.   /* Scrollbar - subtle */
16.   ::-webkit-scrollbar { width:10px; height:10px; }
17.   ::-webkit-scrollbar-track { background:#fff9ef; }
18.   ::-webkit-scrollbar-thumb { background:#e8dcc6; border-radius:10px; }
19. </style>
20. <script src="https://unpkg.com/react@18.3.1/umd/react.development.js" integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L" crossorigin="anonymous"></script>
21. <script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm" crossorigin="anonymous"></script>
22. <script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y" crossorigin="anonymous"></script>
23. </head>
24. <body>
25. <div id="root"></div>
26. 
27. <script type="text/babel" src="data.jsx?v=20260424e"></script>
28. <script type="text/babel" src="components.jsx"></script>
29. <script type="text/babel" src="home.jsx?v=20260424e"></script>
30. <script type="text/babel" src="article.jsx?v=20260424e"></script>
31. <script type="text/babel" src="user-panel.jsx"></script>
32. 
33. <script type="text/babel">
34. const { useState, useEffect } = React;
35. 
36. const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
37.   "theme": "sunny",
38.   "showConfetti": true,
39.   "heroVariant": "daily15",
40.   "userName": "",
41.   "avatar": "panda",
42.   "language": "en",
43.   "dailyGoal": 15,
44.   "level": "Sprout",
45.   "streakDays": 0,
46.   "xp": 0
47. }/*EDITMODE-END*/;
48. 
49. function App() {
50.   // restore from localStorage; if saved articleId no longer exists (payloads changed), fall back to home
51.   const [route, setRoute] = useState(() => {
52.     try {
53.       const saved = JSON.parse(localStorage.getItem('ohye_route') || 'null');
54.       if (!saved) return { page:'home', articleId:null };
55.       if (saved.page === 'article' && !ARTICLES.some(a => a.id === saved.articleId)) {
56.         return { page:'home', articleId:null };
57.       }
58.       return saved;
59.     } catch { return { page:'home', articleId:null }; }
60.   });
61.   const [level, setLevel] = useState(() => {
62.     const v = localStorage.getItem('ohye_level') || 'Sprout';
63.     // Retire Seedling — migrate legacy profiles
64.     return v === 'Seedling' ? 'Sprout' : v;
65.   });
66.   const [cat, setCat] = useState(() => {
67.     const v = localStorage.getItem('ohye_cat') || 'News';
68.     return (v === 'Today' || v === 'Archive' || v === 'All') ? 'News' : v;
69.   });
70.   const [archiveDay, setArchiveDay] = useState(() => {
71.     // archiveDay is now "YYYY-MM-DD" (string) or null for today.
72.     // Migration: any legacy numeric value in localStorage is cleared.
73.     const v = localStorage.getItem('ohye_archive_day');
74.     if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
75.     if (v) localStorage.removeItem('ohye_archive_day');
76.     return null;
77.   });
78.   const [progress, setProgress] = useState(() => {
79.     try {
80.       const saved = JSON.parse(localStorage.getItem('ohye_progress') || 'null');
81.       const base = { readToday: MOCK_USER.readToday, minutesToday: MOCK_USER.minutesToday, articleProgress: {} };
82.       if (!saved) return base;
83.       return { articleProgress: {}, ...saved, articleProgress: saved.articleProgress || {} };
84.     } catch { return { readToday: MOCK_USER.readToday, minutesToday: MOCK_USER.minutesToday, articleProgress: {} }; }
85.   });
86. 
87.   // Tweaks / User Panel — persisted to localStorage so name/avatar/theme/etc.
88.   // survive reloads. Defaults fill in any missing keys (forward-compat when
89.   // we add new tweak fields later).
90.   const [tweaks, setTweaks] = useState(() => {
91.     try {
92.       const saved = JSON.parse(localStorage.getItem('ohye_tweaks') || 'null');
93.       return saved ? { ...TWEAK_DEFAULTS, ...saved } : TWEAK_DEFAULTS;
94.     } catch { return TWEAK_DEFAULTS; }
95.   });
96.   const [userPanelOpen, setUserPanelOpen] = useState(false);
97. 
98.   useEffect(() => { localStorage.setItem('ohye_route', JSON.stringify(route)); }, [route]);
99.   useEffect(() => { localStorage.setItem('ohye_level', level); }, [level]);
100.   useEffect(() => { localStorage.setItem('ohye_cat', cat); }, [cat]);
101.   useEffect(() => {
102.     if (archiveDay) localStorage.setItem('ohye_archive_day', String(archiveDay));
103.     else localStorage.removeItem('ohye_archive_day');
104.     // Whenever archiveDay changes, re-load ARTICLES from the matching bundle
105.     // (today's local files, or a past day's Supabase prefix).
106.     if (typeof window.loadArchive === 'function') {
107.       window.loadArchive(archiveDay).then(() => {
108.         // Force a re-render by bumping a dummy state; route stays put.
109.         setRoute(r => ({ ...r }));
110.       });
111.     }
112.   }, [archiveDay]);
113.   useEffect(() => { localStorage.setItem('ohye_progress', JSON.stringify(progress)); }, [progress]);
114.   useEffect(() => { localStorage.setItem('ohye_tweaks', JSON.stringify(tweaks)); }, [tweaks]);
115. 
116.   // Edit-mode wiring
117.   useEffect(() => {
118.     const handler = (e) => {
119.       if (!e.data) return;
120.       if (e.data.type === '__activate_edit_mode') setUserPanelOpen(true);
121.       if (e.data.type === '__deactivate_edit_mode') setUserPanelOpen(false);
122.     };
123.     window.addEventListener('message', handler);
124.     // Announce AFTER listener
125.     try { window.parent.postMessage({ type:'__edit_mode_available' }, '*'); } catch {}
126.     return () => window.removeEventListener('message', handler);
127.   }, []);
128. 
129.   const updateTweak = (key, val) => {
130.     const edits = { [key]: val };
131.     setTweaks(t => ({...t, ...edits}));
132.     try { window.parent.postMessage({ type:'__edit_mode_set_keys', edits }, '*'); } catch {}
133.   };
134. 
135.   // Apply theme to root
136.   const themeVars = {
137.     sunny: { bg:'#fff9ef', accent:'#ffc83d', hero1:'#ffe2a8', hero2:'#ffc0a8', border:'#ffb98a', heroTextAccent:'#c14e2a', card:'#fff', chip:'#f0e8d8' },
138.     sky:   { bg:'#eef6ff', accent:'#5bb4ff', hero1:'#cfe6ff', hero2:'#bfd9ff', border:'#8ec2ff', heroTextAccent:'#1f6bbf', card:'#fff', chip:'#dce8f5' },
139.     candy: { bg:'#fff0f6', accent:'#ff6ba0', hero1:'#ffd0e2', hero2:'#e0cbff', border:'#ffa0c5', heroTextAccent:'#b73a79', card:'#fff', chip:'#f5dce8' },
140.     forest:{ bg:'#f3f8ec', accent:'#7cbf5a', hero1:'#d9ecc0', hero2:'#f2e1a6', border:'#a7d685', heroTextAccent:'#4a7a2a', card:'#fff', chip:'#e0e8cf' },
141.   };
142.   const theme = themeVars[tweaks.theme] || themeVars.sunny;
143. 
144.   useEffect(() => {
145.     document.body.style.background = theme.bg;
146.     const root = document.documentElement;
147.     root.style.setProperty('--theme-bg', theme.bg);
148.     root.style.setProperty('--theme-accent', theme.accent);
149.     root.style.setProperty('--theme-hero1', theme.hero1);
150.     root.style.setProperty('--theme-hero2', theme.hero2);
151.     root.style.setProperty('--theme-border', theme.border);
152.     root.style.setProperty('--theme-hero-text', theme.heroTextAccent);
153.     root.style.setProperty('--theme-chip', theme.chip);
154.   }, [tweaks.theme]);
155. 
156.   const onOpen = (id) => {
157.     // Chinese summary cards have no detail page — route to the English twin
158.     // (Tree-level / middle) via storyId. If no Tree twin exists, fall back to
159.     // any English variant of the same story.
160.     const target = ARTICLES.find(a => a.id === id);
161.     if (target && target.noDetail && target.language === 'zh') {
162.       const tree = ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en' && a.level === 'Tree');
163.       const any = tree || ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en');
164.       if (any) id = any.id;
165.     }
166.     setRoute({ page:'article', articleId:id });
167.   };
168.   const onBack = () => setRoute({ page:'home', articleId:null });
169.   const onComplete = () => setRoute({ page:'home', articleId:null });
170. 
171.   return (
172.     <div data-screen-label={route.page==='home' ? '01 Home' : '02 Article'} style={{minHeight:'100vh', background: theme.bg}}>
173.       {route.page === 'home' ? (
174.         <HomePage
175.           onOpen={onOpen}
176.           onOpenArchive={(d)=>{ setArchiveDay(d); setCat('All'); window.scrollTo({top:0}); }}
177.           archiveDay={archiveDay}
178.           level={level} setLevel={setLevel}
179.           cat={cat} setCat={setCat}
180.           progress={progress}
181.           theme={theme}
182.           heroVariant={tweaks.heroVariant}
183.           tweaks={tweaks}
184.           onOpenUserPanel={()=>setUserPanelOpen(true)}
185.         />
186.       ) : (
187.         <ArticlePage
188.           articleId={route.articleId}
189.           onBack={onBack}
190.           onComplete={onComplete}
191.           progress={progress}
192.           setProgress={setProgress}
193.         />
194.       )}
195. 
196.       {userPanelOpen && (
197.         <UserPanel
198.           tweaks={tweaks}
199.           updateTweak={updateTweak}
200.           level={level}
201.           setLevel={setLevel}
202.           onClose={()=>setUserPanelOpen(false)}
203.         />
204.       )}
205.     </div>
206.   );
207. }
208. 
209. function TweaksPanel({ tweaks, updateTweak, setTweaksVisible }) {
210.   return (
211.     <div style={{
212.       position:'fixed', bottom:20, right:20, width:280, background:'#fff',
213.       borderRadius:18, border:'2px solid #1b1230', padding:'16px 18px',
214.       boxShadow:'0 10px 0 rgba(27,18,48,0.18)', zIndex:100,
215.       fontFamily:'Nunito, sans-serif',
216.     }}>
217.       <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
218.         <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>🎨 Tweaks</div>
219.         <button onClick={()=>setTweaksVisible(false)} style={{background:'none', border:'none', fontSize:18, cursor:'pointer', color:'#9a8d7a'}}>×</button>
220.       </div>
221. 
222.       <TwkRow label="Color theme">
223.         <select value={tweaks.theme} onChange={e=>updateTweak('theme', e.target.value)} style={twkInput}>
224.           <option value="sunny">☀️ Sunny</option>
225.           <option value="sky">🌊 Sky</option>
226.           <option value="candy">🍬 Candy</option>
227.           <option value="forest">🌳 Forest</option>
228.         </select>
229.       </TwkRow>
230. 
231.       <TwkRow label="Hero style">
232.         <select value={tweaks.heroVariant} onChange={e=>updateTweak('heroVariant', e.target.value)} style={twkInput}>
233.           <option value="daily15">Daily 15 banner</option>
234.           <option value="streak">Streak-focused</option>
235.         </select>
236.       </TwkRow>
237. 
238.       <TwkRow label="Quiz confetti">
239.         <label style={{display:'flex', alignItems:'center', gap:8, fontSize:13, fontWeight:700, cursor:'pointer'}}>
240.           <input type="checkbox" checked={tweaks.showConfetti} onChange={e=>updateTweak('showConfetti', e.target.checked)}/>
241.           {tweaks.showConfetti ? 'On' : 'Off'}
242.         </label>
243.       </TwkRow>
244. 
245.       <div style={{fontSize:11, color:'#9a8d7a', marginTop:10, borderTop:'1px dashed #eee', paddingTop:10}}>
246.         Toggle Tweaks from the toolbar to customize.
247.       </div>
248.     </div>
249.   );
250. }
```

</details>


---

<sub>⏱️ 51s</sub>

### 📦 task (Completed)

### 💬 Copilot

I'll review the pipeline code focusing on the specific edge cases mentioned in the brief. Let me start by reading the context document and then inspecting the critical files.

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/docs/reviews.**

/Users/jiong/myprojects/news-v2/docs/reviews

```
2026-04-24-codex-review.md
2026-04-24-copilot-review-raw.md
2026-04-24-copilot-review.md
2026-04-24-review-brief.md
```


### ✅ `bash`

**Find review docs**

$ find /Users/jiong/myprojects/news-v2/docs/reviews -type f -name "*.md" | head -20

```
/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md
/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-copilot-review-raw.md
/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-copilot-review.md
/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-codex-review.md
<exited with exit code 0>
```


### 💬 Copilot

Now let me read the review brief for context:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md.**

/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md

<details>
<summary>178 lines</summary>

````
1. # Code review brief — News Oh, Ye! v2 (news.6ray.com)
2. 
3. ## Project context
4. 
5. **Goal.** Bilingual kids news site (English easy / middle + 中文 summary).
6. Fully autonomous pipeline runs daily on GitHub Actions, produces 9 stories
7. (3 News / 3 Science / 3 Fun) plus per-story detail enrichment, ships to
8. Supabase Storage, and auto-deploys to Vercel at news.6ray.com.
9. 
10. **Three-repo architecture.**
11. - `news-v2` (this repo): Python pipeline + React prototype source. Runs the
12.   daily-pipeline workflow. Goes private eventually.
13. - `kidsnews-v2` (separate repo): tiny deploy shell. A sync workflow pulls
14.   `latest.zip` from Supabase Storage, unzips into `site/`, commits, Vercel
15.   auto-deploys.
16. - `kidsnews` (legacy, v1 reference at kidsnews.6ray.com): not relevant.
17. 
18. ## Flow
19. 
20. ```
21. GitHub Action (news-v2 · daily 06:20 UTC)
22.   └── python -m pipeline.full_round
23.         ├── RSS mine (3 sources × 3 categories, per-weekday rotation)
24.         ├── Phase A per source: vet 10 briefs, return top-4 verified candidates
25.         ├── past-dedup (3-day lookback, title ≥80% similar → drop)
26.         ├── cross-source dedup (promote next candidate on dup)
27.         ├── tri-variant rewrite (easy_en / middle_en / zh) via DeepSeek chat
28.         ├── detail enrich (keywords / questions / background / mind-tree /
29.         │     why_it_matters / perspectives) via DeepSeek reasoner
30.         │     — retries 3× on JSON parse; falls back to split 3-slot batches
31.         ├── image optimize (Pillow decode + libwebp cwebp/dwebp CLI)
32.         │     → Supabase Storage redesign-article-images bucket
33.         ├── persist runs + stories to Supabase tables
34.         └── pack_and_upload
35.               ├── validate_bundle (9 listings · 18 details · all images)
36.               ├── check_not_overwriting_newer (aborts if remote is fresher)
37.               ├── zip website/ → Supabase redesign-daily-content:latest.zip
38.               │     + <YYYY-MM-DD>.zip
39.               ├── latest-manifest.json + <YYYY-MM-DD>-manifest.json
40.               ├── per-day flat files under <YYYY-MM-DD>/ prefix (new)
41.               ├── backfill_missing_archive_dirs (extracts past zips if the
42.               │     flat dir is missing — runs only once per past date)
43.               ├── update archive-index.json (list of available dates)
44.               └── retention sweep (keep 30 days)
45. 
46. GitHub Action (kidsnews-v2 · cron :15 every 2h, or dispatch on pipeline success)
47.   └── downloads latest.zip → unzips into site/ → commits if changed → push
48. 
49. Vercel (on push to kidsnews-v2)
50.   └── deploys site/ to news.6ray.com
51. ```
52. 
53. ## Key files (by importance)
54. 
55. ### Pipeline (Python 3.11)
56. - `pipeline/full_round.py` — orchestrator. Aggregate → dedup → images →
57.   rewrite+enrich → persist → pack_and_upload.
58. - `pipeline/news_rss_core.py` — shared utilities. DeepSeek call wrappers
59.   with retry, vet/rewriter/enricher prompts, RSS fetch, duplicate checker.
60. - `pipeline/pack_and_upload.py` — validation + zip + manifest + per-day
61.   flat upload + archive-index + retention.
62. - `pipeline/image_optimize.py` — webp optimizer with shutil.which() for
63.   cross-platform CLI path.
64. - `pipeline/news_sources.py` / `science_sources.py` / `fun_sources.py` —
65.   RSS source registries (per-weekday rotation for Science/Fun).
66. - `pipeline/news_aggregate.py` / `science_aggregate.py` / `fun_aggregate.py`
67.   — per-category aggregators (mostly wrappers around `run_source_with_backups`).
68. - `pipeline/supabase_io.py` — DB insert/update helpers.
69. - `pipeline/rewrite_from_db.py` — resume pipeline from DB state (skip
70.   mining + image ops). Used for debug / partial-category re-runs.
71. 
72. ### Frontend (React 18 + Babel-standalone, in-browser JSX transpile)
73. - `website/index.html` — app shell. Loads data.jsx / components.jsx /
74.   home.jsx / article.jsx / user-panel.jsx. Owns top-level state (route,
75.   level, cat, archiveDay, progress, tweaks).
76. - `website/data.jsx` — payload loader. Fetches today's listings from
77.   `/payloads/*.json` (local). For archive mode, fetches from Supabase
78.   Storage `<date>/payloads/*.json`. Exposes window.loadArchive(date).
79. - `website/home.jsx` — listing page with feature + normal card variants,
80.   DatePopover for "View old news", footer generation timestamp.
81. - `website/article.jsx` — detail page: Read & Words / Background / Quiz
82.   / Think & Share tabs. Supports mind-tree Article_Structure for Tree
83.   level, 5W boxes for Sprout.
84. - `website/components.jsx` — shared UI bits (CatChip, XpBadge, etc.).
85. - `website/user-panel.jsx` — profile drawer (name / avatar / theme / level).
86. 
87. ### CI/CD
88. - `.github/workflows/daily-pipeline.yml` — news-v2 daily cron (pipeline).
89. - (kidsnews-v2 repo) `.github/workflows/sync-from-supabase.yml` — pulls
90.   latest.zip + commits.
91. - `requirements.txt` — Python deps.
92. - `pipeline/backfill_card_summaries.py`, `pipeline/augment_mined_at.py` —
93.   one-shots used historically.
94. 
95. ## What to evaluate
96. 
97. Focus where you'd expect bugs or future pain:
98. 
99. 1. **Correctness.**
100.    - `dedup_winners` → `pick_winners_with_dedup` refactor. Two overlapping
101.      ScienceDaily feeds produced the same article; fix was to return up
102.      to 4 candidates and promote next on dup. Check edge cases: all
103.      sources returning candidates that are all pairwise dupes; candidate
104.      exhaustion mid-loop.
105.    - `filter_past_duplicates` title-similarity at 0.80 — are there
106.      obvious false positives / negatives? (titles can differ
107.      significantly while being the same story; or be identical but
108.      different stories.)
109.    - `deepseek_*_call` retry logic — does it handle rate-limit
110.      (429) differently from JSON parse errors?
111.    - `detail_enrich` split-batch fallback — what if BOTH easy and
112.      middle sub-calls fail? Currently continues with partial details;
113.      downstream validator will catch.
114. 
115. 2. **Security.**
116.    - Supabase service key lives in a committed .env loader (module
117.      top-level), overridden by GitHub Actions secret at job start.
118.      Any path where the key could end up in a log?
119.    - Vercel.json Cache-Control of 5min for user-visible assets — any
120.      risk of serving private data?
121.    - DeepSeek API key is only used server-side; confirm no frontend
122.      references.
123.    - Any HTML injection paths in the rewriter output? UI highlights
124.      keywords by matching with user-content strings.
125. 
126. 3. **Failure modes.**
127.    - Pipeline partial failure (category rewrite succeeds but enrich
128.      fails): is there a state where a partial bundle gets uploaded?
129.      (We added `check_not_overwriting_newer` and `validate_bundle`.)
130.    - Supabase Storage quota exhaustion mid-upload.
131.    - Vercel build fails after kidsnews-v2 commit — the pipeline
132.      doesn't know; only manual intervention.
133.    - Browser with localStorage full / disabled.
134. 
135. 4. **Maintainability.**
136.    - `pipeline/news_rss_core.py` is ~1200 lines. Should it split?
137.    - `full_round.py` grew fast — orchestration, dedup, image-process
138.      helpers, persistence, emit — all in one file.
139.    - React app has no build step (Babel-standalone). Fine for a
140.      prototype; risky long-term. Recommendation?
141.    - Hardcoded `/Users/jiong/...` paths were a CI bug source today;
142.      are there others lurking?
143. 
144. 5. **Architecture.**
145.    - Three-repo split: authoring / deploy / legacy. Any cleaner alt?
146.    - The zip-over-Storage indirection vs directly pushing
147.      generated artifacts to the deploy repo.
148.    - Per-day flat files coexist with zips — redundant, or
149.      justified?
150.    - "CI-only, never run locally" guard (`check_not_overwriting_newer`)
151.      — robust enough? Any evasion paths?
152. 
153. 6. **Prompt engineering.**
154.    - Rewriter prompt vs enricher prompt — any accuracy-vs-creativity
155.      trade-offs worth flagging?
156.    - `card_summary` ≤ 120 words — is the prompt actually enforceable?
157.      (We also post-trim with a word cap.)
158.    - Past-dedup threshold of 0.80 title similarity — when would you
159.      lower or raise it?
160. 
161. ## Format of your review
162. 
163. For each finding, use:
164. 
165. - **Severity**: `Critical` / `Important` / `Minor` / `Info`
166. - **File:line** (or "cross-cutting")
167. - **What**: one-sentence description
168. - **Why it matters** (1-2 sentences)
169. - **Suggested fix** (concrete, if you have one)
170. 
171. Then at the end: 3-5 line assessment summary + top 3 things to fix first.
172. 
173. Do not nitpick style unless it materially affects clarity. Do not
174. suggest broad refactors without a specific incident that justifies
175. them. Trust that the design decisions (RSS-only, three-repo split,
176. zip-via-Supabase, React-without-build) are intentional unless you spot
177. evidence they're causing real problems.
178.
````

</details>


### 💬 Copilot

Now let me read the key pipeline files, starting with full_round.py and the files it depends on:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline.**

/Users/jiong/myprojects/news-v2/pipeline

<details>
<summary>44 lines</summary>

```
__init__.py
__pycache__
augment_mined_at.py
backfill_card_summaries.py
cleaner.py
config.py
curator.py
discover.py
enrich_existing.py
full_round.py
fun_aggregate.py
fun_sources.py
image_optimize.py
main.py
news_aggregate.py
news_aj_full.py
news_aj_rss.py
news_bbc_full.py
news_exa_list.py
news_exa_pipeline.py
news_guardian_full.py
news_npr_full.py
news_pbs_full.py
news_raw_list.py
news_rss_core.py
news_sources.py
output.py
pack_and_upload.py
read.py
requirements.txt
rewrite_from_db.py
science_aggregate.py
science_sources.py
seed_source_configs.py
supabase_io.py
test_fun_feeds.py
test_replacement_feeds.py
test_science_feeds.py
test_sciencedaily_topics.py
test_thinking_enrich.py
test_thinking_rewrite.py
tune_news.py
tune_query.py
vet.py
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py

```
File too large to read at once (23.3 KB). Consider using the grep tool to search within the file, or view with view_range to read specific sections.
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 1-100)

<details>
<summary>100 lines</summary>

```
1. """Shared core for RSS → filter → batched vet+cluster → batched rewrite.
2. 
3. Used by news_aj_full.py and news_pbs_full.py. Parameterized by:
4.   - RSS URL
5.   - source label (for HTML title)
6.   - MAX_KEPT (cap on articles sent to vetter)
7.   - PICK_COUNT (how many the curator picks)
8.   - TARGET_WORDS (kids article length)
9.   - output filenames
10. 
11. Vet thresholds (locked 2026-04-23):
12.   - REJECT if any dim >= 4 OR total > 6
13.   - CAUTION if total 5-6 AND every dim <= 3
14.   - SAFE if total 0-4 AND every dim <= 3
15. """
16. from __future__ import annotations
17. 
18. import html
19. import json
20. import logging
21. import os
22. import re
23. import time
24. from datetime import datetime, timezone
25. from pathlib import Path
26. from urllib.parse import urlparse
27. 
28. import feedparser
29. import requests
30. 
31. from .cleaner import extract_article_from_html
32. 
33. log = logging.getLogger("rss-core")
34. 
35. # Load .env once on module import
36. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
37. for _line in (_envp.open() if _envp.exists() else []):
38.     if "=" in _line and not _line.startswith("#"):
39.         _k, _v = _line.strip().split("=", 1)
40.         os.environ[_k] = _v
41. 
42. DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
43. DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
44. 
45. MIN_WORDS_DEFAULT = 500
46. MAX_RSS_DEFAULT = 25
47. VIDEO_PATH_RE = re.compile(r"/video/", re.I)
48. HTML_FETCH_TIMEOUT = 15
49. HTML_FETCH_HEADERS = {
50.     # Real browser UA — NPR and some others block bot-flavored UAs.
51.     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
52.                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
53.     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
54.     "Accept-Language": "en-US,en;q=0.9",
55. }
56. 
57. SAFETY_DIMS = ["violence", "sexual", "substance", "language", "fear",
58.                "adult_themes", "distress", "bias"]
59. SAFETY_SHORT = ["Viol", "Sex", "Subst", "Lang", "Fear", "Adult", "Distr", "Bias"]
60. 
61. # Generic social-share default images (usually a site logo or blank template,
62. # not a real article image). Detected by URL substring.
63. BAD_IMAGE_PATTERNS = (
64.     "facebook-default",
65.     "twitter-default",
66.     "og-default",
67.     "share-default",
68.     "default-share",
69.     "default-og",
70.     "default-social",
71. )
72. 
73. MIN_PICK_BODY_WORDS = 250   # fall back to alternate if pick's body is thinner than this
74. 
75. 
76. def is_generic_social_image(url: str | None) -> bool:
77.     if not url:
78.         return True
79.     u = url.lower()
80.     return any(p in u for p in BAD_IMAGE_PATTERNS)
81. 
82. 
83. # ---------------------------------------------------------------------------
84. # Vet threshold evaluator (Python-side, authoritative)
85. # ---------------------------------------------------------------------------
86. 
87. def apply_vet_thresholds(safety: dict) -> str:
88.     """Authoritative verdict from safety scores.
89. 
90.     REJECT if any dim >= 4 OR total > 6.
91.     CAUTION if total 5-6 AND every dim <= 3.
92.     SAFE if total 0-4 AND every dim <= 3.
93.     """
94.     dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
95.     total = safety.get("total")
96.     if total is None:
97.         total = sum(dims)
98.     max_dim = max(dims) if dims else 0
99.     if max_dim >= 4 or total > 6:
100.         return "REJECT"
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 100-300)

<details>
<summary>201 lines</summary>

````
100.         return "REJECT"
101.     if 5 <= total <= 6:
102.         return "CAUTION"
103.     return "SAFE"
104. 
105. 
106. # ---------------------------------------------------------------------------
107. # Step 1+2: RSS + HTML scrape + filter
108. # ---------------------------------------------------------------------------
109. 
110. def fetch_rss_entries(url: str, max_entries: int = MAX_RSS_DEFAULT) -> list[dict]:
111.     feed = feedparser.parse(url)
112.     out = []
113.     for entry in feed.entries[:max_entries]:
114.         out.append({
115.             "title": getattr(entry, "title", ""),
116.             "link": getattr(entry, "link", ""),
117.             "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
118.             "summary": getattr(entry, "summary", ""),
119.         })
120.     return out
121. 
122. 
123. def fetch_html(url: str) -> str | None:
124.     try:
125.         r = requests.get(url, timeout=HTML_FETCH_TIMEOUT, headers=HTML_FETCH_HEADERS,
126.                          allow_redirects=True)
127.         if r.status_code >= 400:
128.             return None
129.         return r.text
130.     except requests.RequestException:
131.         return None
132. 
133. 
134. def process_entry(entry: dict, min_words: int = MIN_WORDS_DEFAULT) -> dict:
135.     url = entry["link"]
136.     if VIDEO_PATH_RE.search(url):
137.         return {**entry, "og_image": None, "body": "", "word_count": 0,
138.                 "skip_reason": "video URL", "highlights": [], "paragraphs": []}
139.     html_text = fetch_html(url)
140.     if not html_text:
141.         return {**entry, "og_image": None, "body": "", "word_count": 0,
142.                 "skip_reason": "html fetch failed", "highlights": [], "paragraphs": []}
143.     extracted = extract_article_from_html(url, html_text)
144.     body = extracted.get("cleaned_body") or ""
145.     paragraphs = extracted.get("paragraphs") or []
146.     og_image = extracted.get("og_image")
147.     wc = len(body.split()) if body else 0
148.     skip_reason = None
149.     if wc < min_words:
150.         skip_reason = f"{wc}w < {min_words}w"
151.     elif not og_image:
152.         skip_reason = "no og:image"
153.     hls = [p for p in paragraphs if len(p.split()) >= 12][:3]
154.     return {
155.         **entry,
156.         "og_image": og_image,
157.         "body": body,
158.         "word_count": wc,
159.         "paragraphs": paragraphs,
160.         "highlights": hls,
161.         "skip_reason": skip_reason,
162.     }
163. 
164. 
165. # ---------------------------------------------------------------------------
166. # Step 3: BATCHED vet+cluster+curate (1 DeepSeek call)
167. # ---------------------------------------------------------------------------
168. 
169. def build_vet_prompt(pick_count: int) -> str:
170.     return f"""You are a content reviewer + curator for a kids news site (readers age 12).
171. 
172. You will receive a numbered list of news articles (id 0..N-1), each with title + first paragraphs.
173. 
174. TASK 1 — Vet every article on 8 safety dimensions and 3 interest dimensions.
175. 
176.   Safety (score each 0-5, where 0=none, 5=severe):
177.     violence, sexual, substance, language, fear, adult_themes, distress, bias
178.     Compute total = sum of 8 dims.
179.     Initial safety_verdict (we will re-apply strict thresholds downstream):
180.       any_dim >= 4 or total > 6  -> REJECT
181.       total 5-6 (and all dims <= 3) -> CAUTION
182.       total 0-4 -> SAFE
183. 
184.   Interest (score each 0-5):
185.     importance  — how globally significant
186.     fun_factor  — how delightful / surprising / fun
187.     kid_appeal  — how likely a 12-year-old would want to read this
188.     interest_peak = max(importance, fun_factor, kid_appeal)
189.     interest_verdict:
190.       peak >= 3 -> ENGAGING
191.       peak == 2 -> MEH
192.       peak <= 1 -> BORING
193. 
194. TASK 2 — Detect topic clusters.
195.   A cluster = 2+ articles on the SAME real-world story/topic.
196.   Give each cluster a short id and theme. Size-3+ clusters are HOT.
197. 
198. TASK 3 — Pick exactly {pick_count} stories for publishing.
199.   Rules:
200.     R1: NEVER pick a REJECT (any_dim >= 4 or total > 6).
201.     R2: Prefer HOT cluster members at SAFE level. CAUTION is acceptable only
202.         if no SAFE hot-cluster member exists.
203.     R3: Prefer interest_verdict=ENGAGING. Never pick BORING unless no alternative.
204.     R4: Diversify — picks should come from DIFFERENT clusters if possible.
205.     R5: Avoid gossip, obituaries, dry business jargon, sports-results-only.
206. 
207. TASK 4 — List 3-4 RANKED alternates (next-best IDs) in case a pick fails the
208.   later content-quality check (thin body, missing real image, etc.).
209.   Do not repeat picks in alternates.
210. 
211. Return ONLY valid JSON (no markdown fences):
212. {{
213.   "vet": [
214.     {{
215.       "id": 0,
216.       "safety": {{"violence": 0, "sexual": 0, "substance": 0, "language": 0,
217.                   "fear": 0, "adult_themes": 0, "distress": 0, "bias": 0,
218.                   "total": 0, "verdict": "SAFE"}},
219.       "interest": {{"importance": 0, "fun_factor": 0, "kid_appeal": 0,
220.                     "peak": 0, "verdict": "ENGAGING"}},
221.       "cluster_id": "cluster_x",
222.       "flags": ["..."]
223.     }},
224.     ... one per input ...
225.   ],
226.   "clusters": [
227.     {{"id": "cluster_x", "theme": "...", "members": [0,1], "size": 2, "is_hot": false}}
228.   ],
229.   "picks": [
230.     {{"id": 0, "reason": "must cite safety verdict, interest peak, and cluster status"}},
231.     ... {pick_count} total ...
232.   ],
233.   "alternates": [
234.     {{"id": 7, "reason": "..."}},
235.     {{"id": 12, "reason": "..."}},
236.     {{"id": 3, "reason": "..."}}
237.   ]
238. }}"""
239. 
240. 
241. def deepseek_call(system: str, user: str, max_tokens: int, temperature: float = 0.2,
242.                   max_attempts: int = 3) -> dict:
243.     """Call deepseek-chat with JSON output. Retries on JSON parse failure
244.     (model occasionally emits malformed JSON) and transient HTTP errors."""
245.     last_err: Exception | None = None
246.     for attempt in range(1, max_attempts + 1):
247.         try:
248.             r = requests.post(DEEPSEEK_ENDPOINT,
249.                 json={
250.                     "model": "deepseek-chat",
251.                     "messages": [{"role": "system", "content": system},
252.                                  {"role": "user", "content": user}],
253.                     "temperature": temperature,
254.                     "max_tokens": max_tokens,
255.                 },
256.                 headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
257.                 timeout=120)
258.             r.raise_for_status()
259.             content = r.json()["choices"][0]["message"]["content"]
260.             content = re.sub(r"^```json\s*", "", content.strip())
261.             content = re.sub(r"\s*```\s*$", "", content)
262.             return json.loads(content)
263.         except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
264.                 requests.Timeout) as e:
265.             last_err = e
266.             log.warning("chat attempt %d/%d failed: %s",
267.                         attempt, max_attempts, str(e)[:200])
268.             if attempt < max_attempts:
269.                 time.sleep(2 * attempt)
270.     raise RuntimeError(f"deepseek_call exhausted {max_attempts} attempts") from last_err
271. 
272. 
273. def vet_curator_input(briefs: list[dict], pick_count: int) -> str:
274.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.",
275.              f"Articles to vet + cluster + pick {pick_count}:", ""]
276.     for i, b in enumerate(briefs):
277.         hls = b.get("highlights") or []
278.         hls_text = " ".join(hls)[:400] if hls else (b.get("summary", "") or "")[:400]
279.         lines.append(f"[id: {i}] {b.get('title','')}")
280.         lines.append(f"  first paragraphs: {hls_text}")
281.         lines.append("")
282.     return "\n".join(lines)
283. 
284. 
285. def vet_and_curate(briefs: list[dict], pick_count: int) -> dict:
286.     result = deepseek_call(build_vet_prompt(pick_count), vet_curator_input(briefs, pick_count),
287.                            max_tokens=3500, temperature=0.2)
288.     # Re-apply thresholds authoritatively on Python side
289.     for v in result.get("vet") or []:
290.         safety = v.get("safety") or {}
291.         # Recompute total from dims (trust dim scores, not model's stated total)
292.         dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
293.         safety["total"] = sum(dims)
294.         safety["verdict"] = apply_vet_thresholds(safety)
295.     # Filter out any picks that are REJECT under the new rule
296.     vet_by_id = {v["id"]: v for v in result.get("vet") or []}
297.     filtered_picks = []
298.     for p in result.get("picks") or []:
299.         pid = p.get("id")
300.         v = vet_by_id.get(pid)
````

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 300-500)

<details>
<summary>201 lines</summary>

```
300.         v = vet_by_id.get(pid)
301.         if v and v.get("safety", {}).get("verdict") == "REJECT":
302.             log.warning("  dropping picked id=%s — REJECT on strict thresholds", pid)
303.             continue
304.         filtered_picks.append(p)
305.     result["picks"] = filtered_picks
306.     return result
307. 
308. 
309. # ---------------------------------------------------------------------------
310. # Step 4: BATCHED rewrite (1 DeepSeek call)
311. # ---------------------------------------------------------------------------
312. 
313. def build_rewriter_prompt(pick_count: int, target_words: int) -> str:
314.     return f"""You are a news writer for "News Oh, Ye!", a news site for 12-year-old readers.
315. 
316. You will receive {pick_count} source articles (with title + full body). Rewrite EACH as a
317. kid-friendly news story at a 12-year-old / 7th-grade reading level.
318. 
319. WORD COUNT — STRICT:
320.   Each article's `body` MUST be {target_words - 20}-{target_words + 20} words.
321.   Count silently before returning; if under, add a concrete example or vivid detail.
322. 
323. READING LEVEL:
324.   Aim for 12 years old (7th grade). That means:
325.   · Use real, interesting vocabulary — not baby talk. Words like
326.     "crucial", "controversial", "ambitious", "negotiation", "historic",
327.     "escalate", "diplomat", "coalition", "sanction", "evacuate",
328.     "unprecedented", "stabilize", "devastation" are fair game.
329.   · The FIRST time you use any specialized term, EXPLAIN it inline in
330.     plain English:
331.     "a ceasefire (when both sides agree to stop fighting for a while)"
332.     "sanctions — rules that block trade and money between countries"
333.   · Mix sentence lengths: some short and punchy, some longer with clauses.
334. 
335. TONE & STRUCTURE (every article):
336.   Para 1 — HOOK (surprising detail, vivid scene, or question) + the
337.            essential WHO, WHAT, WHERE, WHEN in 2-4 sentences.
338.   Para 2-3 — EXPLAIN the background a 12-year-old needs to understand why.
339.   Para 4 — PERSPECTIVES: what do different sides think?
340.   Para 5 — "WHY IT MATTERS": 1-2 sentences connecting to the reader's world.
341. 
342. ACCURACY:
343.   Every fact MUST come from the source. Don't invent names, dates, numbers.
344. 
345. HEADLINE:
346.   A NEW kid-friendly headline — different wording from the source.
347. 
348. OUTPUT — valid JSON only (no markdown fences):
349. {{
350.   "articles": [
351.     {{
352.       "source_id": <int>,
353.       "headline": "...",
354.       "body": "paragraph 1\\n\\nparagraph 2\\n\\n...",
355.       "why_it_matters": "..."
356.     }},
357.     ... one per input ...
358.   ]
359. }}"""
360. 
361. 
362. def rewriter_input(articles_with_ids: list[tuple[int, dict]], target_words: int) -> str:
363.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
364.     for src_id, art in articles_with_ids:
365.         host = urlparse(art.get("link") or "").netloc.replace("www.", "")
366.         body = art.get("body") or ""
367.         words = body.split()
368.         body_trimmed = " ".join(words[:2500])
369.         lines.append(f"=== SOURCE [id: {src_id}] ===")
370.         lines.append(f"Title: {art.get('title','')}")
371.         lines.append(f"Host: {host}")
372.         lines.append(f"Date: {art.get('published','')}")
373.         lines.append("")
374.         lines.append("Full body:")
375.         lines.append(body_trimmed)
376.         lines.append("")
377.     lines.append(f"Write {len(articles_with_ids)} kids articles. Each body: "
378.                  f"{target_words - 20}-{target_words + 20} words.")
379.     return "\n".join(lines)
380. 
381. 
382. def rewrite_batch(articles_with_ids: list[tuple[int, dict]], target_words: int) -> dict:
383.     return deepseek_call(build_rewriter_prompt(len(articles_with_ids), target_words),
384.                          rewriter_input(articles_with_ids, target_words),
385.                          max_tokens=3000, temperature=0.5)
386. 
387. 
388. # ---------------------------------------------------------------------------
389. # Tri-variant rewriter (easy_en + middle_en + zh-summary)
390. # ---------------------------------------------------------------------------
391. 
392. TRI_VARIANT_REWRITER_PROMPT = """You are a 小记者 (junior reporter) at "News Oh, Ye!" — YOU
393. are a kid yourself, writing for OTHER kids. Your voice is curious, excited, and
394. engaging — like a smart older sibling who just found a cool story and can't wait
395. to tell their friends. Don't sound like a grown-up news anchor. NEVER be boring.
396. 
397. What real kid reporters do:
398.   · Start with a HOOK — a surprising detail, a vivid scene, or a direct
399.     question to the reader. NEVER open with a dry "who did what" summary.
400.   · Use "you" to pull the reader in ("Have you ever wondered…?", "Imagine…")
401.   · Find the WEIRD, COOL, or SURPRISING part of the story and lead with it
402.   · Use specific details (real numbers, names, places) — concrete beats vague
403.   · Compare new concepts to things kids already know
404.     ("about the size of a school bus", "as tall as a 10-story building",
405.      "that's like filling 50 swimming pools with…")
406.   · Mix sentence lengths. Short ones for impact. Longer ones for explaining.
407.   · Show enthusiasm — let the "wow, did you know?!" energy come through
408. 
409. You will receive N source articles. For EACH, produce THREE variants:
410. 
411. 1. easy_en — English. READER IS A 10-YEAR-OLD (grade 4).
412.    · body: 170-210 words (STRICT — count before returning)
413.    · Simple but not baby-talk; explain any hard word inline in plain English:
414.      "a ceasefire (when both sides agree to stop fighting for a while)"
415.    · Short, punchy sentences; lead with a hook — not a summary
416.    · card_summary: 6-9 sentences, MAX 120 words. Shown on the home-page card.
417.      Opens with a hook, then covers the WHO / WHAT / WHERE / WHY in plain
418.      words — enough that a kid understands the story without clicking. Uses
419.      one or two concrete details (names, numbers, places). NOT a restatement
420.      of the headline. Ends with punctuation.
421. 
422. 2. middle_en — English. READER IS A MIDDLE SCHOOLER (grade 7-8, age 12-14).
423.    · body: 320-350 words (STRICT — if under 320, add MORE vivid details,
424.      specific names or numbers, or a direct quote from the source; never invent)
425.    · Richer vocabulary ("crucial", "unprecedented", "diplomat", "negotiation",
426.      "escalate", "sanction", "controversial", "coalition"); explain inline
427.      the first time you use a specialized term
428.    · Mix short impact sentences with longer, complex ones
429.    · card_summary: 6-9 sentences, MAX 120 words. Shown on the home-page card.
430.      Opens with a hook, covers the WHO / WHAT / WHERE / WHY plus one line on
431.      the tension or stakes. Include 2-3 concrete details (names, numbers,
432.      places, quotes) so a middle-schooler can grasp the story without
433.      clicking. NOT a restatement of the headline. Ends with punctuation.
434. 
435. 3. zh — 简体中文. 摘要卡片 only (no body, no quiz, no keywords).
436.    · headline: 有意思的中文标题 (可保留 CEO / iPhone / iPad 等专有名词为英文)
437.    · summary: 260-300 汉字 (STRICT — count silently, must not exceed 300)
438.      保持小记者的口吻 — 好奇、生动、抓住读者注意。
439.      不要写成干巴巴的新闻摘要。用具体细节、用比喻、用提问。
440. 
441. RULES (all variants):
442.   · ACCURACY — every fact must come from the source. No invented names, dates,
443.     numbers, or quotes.
444.   · NEW HEADLINE per variant — don't copy the source headline verbatim.
445.   · NO dry summary tone — you're a kid reporter excited about a story,
446.     not a wire-service editor.
447. 
448. OUTPUT — valid JSON only (no markdown fences):
449. {
450.   "articles": [
451.     {
452.       "source_id": <int>,
453.       "easy_en":   {"headline": "...", "card_summary": "...", "body": "..."},
454.       "middle_en": {"headline": "...", "card_summary": "...", "body": "..."},
455.       "zh":        {"headline": "...", "summary": "..."}
456.     },
457.     ... one entry per input article ...
458.   ]
459. }"""
460. 
461. 
462. def tri_variant_rewriter_input(articles_with_ids: list[tuple[int, dict]]) -> str:
463.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
464.     for src_id, art in articles_with_ids:
465.         host = urlparse(art.get("link") or "").netloc.replace("www.", "")
466.         body = art.get("body") or ""
467.         body_trimmed = " ".join(body.split()[:2500])
468.         lines.append(f"=== SOURCE [id: {src_id}] ===")
469.         lines.append(f"Title: {art.get('title','')}")
470.         lines.append(f"Host: {host}")
471.         lines.append(f"Date: {art.get('published','')}")
472.         lines.append("")
473.         lines.append("Full body:")
474.         lines.append(body_trimmed)
475.         lines.append("")
476.     lines.append("Write 3 tri-variant entries (easy_en + middle_en + zh) per the rules.")
477.     return "\n".join(lines)
478. 
479. 
480. def tri_variant_rewrite(articles_with_ids: list[tuple[int, dict]]) -> dict:
481.     return deepseek_call(TRI_VARIANT_REWRITER_PROMPT,
482.                          tri_variant_rewriter_input(articles_with_ids),
483.                          max_tokens=5000, temperature=0.5)
484. 
485. 
486. # ---------------------------------------------------------------------------
487. # Detail enrichment — 1 call per category, 6 items (3 articles × 2 EN variants)
488. # References bodies by id instead of re-returning them (saves tokens).
489. # ---------------------------------------------------------------------------
490. 
491. DETAIL_ENRICH_PROMPT = """You are enriching kids-news articles with DEPTH beyond the body text.
492. Use careful reasoning. The reader already has the body; you're adding what the
493. body alone doesn't provide — historical context, real-world pattern, nuance.
494. 
495. You will receive 3 articles. Each has two rewritten English bodies:
496.   easy_en  — grade 4 / 10-year-old reader (~200 words)
497.   middle_en — grade 7-8 / 12-14 year old reader (~320 words)
498. 
499. For each of the 6 slots (3 articles × {easy,middle}) produce:
500.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 500-700)

<details>
<summary>201 lines</summary>

````
500. 
501.   [common to both easy and middle]
502.   · keywords: 6 {term, explanation} pairs. EVERY term MUST literally appear (or
503.     appear as a common inflection — "banned" for "ban", "fined" for "fine")
504.     in the corresponding body. Do NOT invent concepts that aren't in the text.
505.   · questions: 6 MCQ questions, each {question, options:[4], correct_answer}.
506.     correct_answer MUST match one option character-for-character.
507. 
508.   ———— easy slot (10-year-old reader) ————
509.   · background_read: array of 2-3 SIMPLE sentences giving RELATED real-world
510.     context. Add historical facts, related events, or concepts the kid might
511.     not know. Avoid generic filler about the news source itself.
512.   · Article_Structure: array of 4 strings: WHO / WHAT / WHERE / WHY
513.     (format: "WHO: ...", "WHAT: ...", etc.) — specific answers drawn from the
514.     body, not a template.
515.   · why_it_matters: 1 sentence connecting the story to a 10-year-old's life
516.     (school / family / community / future).
517.   · perspectives: 2-3 {perspective, description} POV pairs covering clear
518.     different stances (positive / critical / neutral).
519. 
520.   ———— middle slot (12-14 year old reader) ————
521.   · background_read: array of 3-5 richer sentences (150-250 words total).
522.     REQUIRE real historical facts, prior events, or named organizations a
523.     12-year-old may not know. Define new terms briefly when used. No generic
524.     statements about "this news source" or "how journalists work".
525.   · Article_Structure: MIND-TREE showing how THIS article is constructed.
526.     Array of strings, each a tree node. Use tree characters └─ ├─ and leading
527.     spaces for hierarchy. Example:
528.       [
529.         "LEAD: <hook>",
530.         "  └─ specific: '<quote/detail>'",
531.         "KEY EVENT: <what happened>",
532.         "  ├─ WHO: <specific names>",
533.         "  ├─ WHEN: <timeline>",
534.         "  └─ AMOUNT: <numbers>",
535.         "TENSION / VIEWPOINTS",
536.         "  ├─ ONE SIDE: <viewpoint A>",
537.         "  └─ OTHER SIDE: <viewpoint B>",
538.         "EVIDENCE: <support>",
539.         "OPEN QUESTION: <unresolved>"
540.       ]
541.     Reflect the article's ACTUAL structure — don't force a template.
542.   · why_it_matters: 1-2 sentences on the stakes for a 12-14 year-old — broader
543.     societal / systemic / future implications, not just personal relevance.
544.   · perspectives: 4 {perspective, description} pairs, each a DISTINCT angle:
545.       - Positive (who benefits, what's gained)
546.       - Negative / critical (who's harmed, what's concerning)
547.       - Neutral / analytical (systemic or historical pattern)
548.       - Forward-looking (what next, what could/should change)
549.     Each description 2-3 sentences exploring tension or nuance.
550. 
551. ACCURACY: facts in background_read must be real-world accurate. If unsure,
552. prefer pattern statements over specific claims.
553. 
554. REFERENCE, don't re-return: use keys "0_easy", "0_middle", "1_easy", "1_middle",
555. "2_easy", "2_middle". Do NOT echo the body text back.
556. 
557. Return ONLY valid JSON (no markdown fences):
558. {
559.   "details": {
560.     "0_easy":   {"keywords":[...], "questions":[...], "background_read":[...], "Article_Structure":[...], "why_it_matters":"...", "perspectives":[...]},
561.     "0_middle": {...},
562.     "1_easy":   {...},
563.     "1_middle": {...},
564.     "2_easy":   {...},
565.     "2_middle": {...}
566.   }
567. }"""
568. 
569. 
570. def detail_enrich_input(rewrite_result: dict) -> str:
571.     """Build the user message for detail enrichment from the tri-variant rewrite result."""
572.     lines = ["3 articles below. For each, generate detail fields for easy and middle levels.", ""]
573.     for i, art in enumerate(rewrite_result.get("articles") or []):
574.         easy = art.get("easy_en") or {}
575.         middle = art.get("middle_en") or {}
576.         lines.append(f"=== Article [id: {i}] ===")
577.         lines.append(f"easy_en headline: {easy.get('headline','')}")
578.         lines.append(f"easy_en body ({len((easy.get('body') or '').split())} words):")
579.         lines.append((easy.get("body") or ""))
580.         lines.append("")
581.         lines.append(f"middle_en headline: {middle.get('headline','')}")
582.         lines.append(f"middle_en body ({len((middle.get('body') or '').split())} words):")
583.         lines.append((middle.get("body") or ""))
584.         lines.append("")
585.     lines.append("Return the JSON with the 6 slots keyed as 0_easy, 0_middle, 1_easy, 1_middle, 2_easy, 2_middle.")
586.     return "\n".join(lines)
587. 
588. 
589. KEYWORD_SUFFIX_RE = r"(?:s|es|ed|d|ing|ning|ned|ting|ted|er|ers|ion|ions|ensions|ensión|ly)?"
590. 
591. 
592. def keyword_in_body(term: str, body: str) -> bool:
593.     """Same suffix-aware match the UI uses — term or inflected form present?"""
594.     import re
595.     if not term or not body:
596.         return False
597.     escaped = re.escape(term)
598.     pattern = rf"\b{escaped}{KEYWORD_SUFFIX_RE}\b"
599.     return bool(re.search(pattern, body, flags=re.IGNORECASE))
600. 
601. 
602. def filter_keywords(details: dict, rewrite_result: dict) -> dict:
603.     """Drop keywords that don't appear in the corresponding body. Logs drops."""
604.     articles_by_id = {a["source_id"]: a for a in rewrite_result.get("articles") or []}
605.     for slot_key, det in details.items():
606.         kws = det.get("keywords") or []
607.         if not kws:
608.             continue
609.         try:
610.             aid_str, lvl = slot_key.rsplit("_", 1)
611.             aid = int(aid_str)
612.         except (ValueError, TypeError):
613.             continue
614.         art = articles_by_id.get(aid, {})
615.         variant = art.get(f"{lvl}_en" if lvl in ("easy", "middle") else lvl) or {}
616.         body = variant.get("body") or ""
617.         kept = []
618.         dropped = []
619.         for k in kws:
620.             if keyword_in_body(k.get("term", ""), body):
621.                 kept.append(k)
622.             else:
623.                 dropped.append(k.get("term"))
624.         det["keywords"] = kept
625.         if dropped:
626.             log.info("  [%s] dropped hallucinated keywords: %s", slot_key, dropped)
627.     return details
628. 
629. 
630. def deepseek_reasoner_call(system: str, user: str, max_tokens: int = 16000,
631.                            max_attempts: int = 3) -> dict:
632.     """Call deepseek-reasoner (thinking mode). Returns parsed JSON from final
633.     content. Retries on JSON parse failure (model occasionally drops a comma
634.     in large payloads) and on transient HTTP/network errors."""
635.     last_err: Exception | None = None
636.     for attempt in range(1, max_attempts + 1):
637.         try:
638.             r = requests.post(
639.                 DEEPSEEK_ENDPOINT,
640.                 json={
641.                     "model": "deepseek-reasoner",
642.                     "messages": [{"role": "system", "content": system},
643.                                  {"role": "user", "content": user}],
644.                     "max_tokens": max_tokens,
645.                 },
646.                 headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
647.                 timeout=300,
648.             )
649.             r.raise_for_status()
650.             content = r.json()["choices"][0]["message"]["content"]
651.             content = re.sub(r"^```json\s*", "", content.strip())
652.             content = re.sub(r"\s*```\s*$", "", content)
653.             return json.loads(content)
654.         except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
655.                 requests.Timeout) as e:
656.             last_err = e
657.             log.warning("reasoner attempt %d/%d failed: %s",
658.                         attempt, max_attempts, str(e)[:200])
659.             if attempt < max_attempts:
660.                 time.sleep(2 * attempt)  # 2s, 4s
661.     raise RuntimeError(f"deepseek_reasoner_call exhausted {max_attempts} attempts") from last_err
662. 
663. 
664. def _detail_enrich_input_single_level(rewrite_result: dict, level: str) -> str:
665.     """Build an input covering only easy OR only middle slots (3 slots total).
666.     Smaller payload → less chance of malformed JSON under reasoner load."""
667.     assert level in ("easy", "middle")
668.     lines = [f"3 articles below. For EACH, generate detail fields ONLY for the "
669.              f"{level} level.", ""]
670.     for i, art in enumerate(rewrite_result.get("articles") or []):
671.         v = art.get(f"{level}_en") or {}
672.         lines.append(f"=== Article [id: {i}] ===")
673.         lines.append(f"{level}_en headline: {v.get('headline','')}")
674.         lines.append(f"{level}_en body ({len((v.get('body') or '').split())} words):")
675.         lines.append((v.get("body") or ""))
676.         lines.append("")
677.     lines.append(f"Return JSON with 3 slots keyed as 0_{level}, 1_{level}, 2_{level}.")
678.     return "\n".join(lines)
679. 
680. 
681. def detail_enrich(rewrite_result: dict) -> dict:
682.     """Detail enrichment with two-stage fallback:
683.       1. Single 6-slot call (fast, cheaper).
684.       2. If that fails JSON parse even after retries, split into TWO 3-slot
685.          calls (easy-only + middle-only). Smaller prompts → higher chance of
686.          well-formed JSON per call, and if one half still fails the other is
687.          salvageable.
688.     Post-filter hallucinated keywords at the end."""
689.     try:
690.         res = deepseek_reasoner_call(DETAIL_ENRICH_PROMPT,
691.                                      detail_enrich_input(rewrite_result),
692.                                      max_tokens=16000)
693.         details = res.get("details") or {}
694.         # Accept even partial success here (all 6 slots expected; caller checks).
695.     except RuntimeError as e:
696.         log.warning("detail_enrich 6-slot call failed after retries (%s) — "
697.                     "falling back to split 3-slot batches", e)
698.         details = {}
699.         for level in ("easy", "middle"):
700.             try:
````

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 700-900)

<details>
<summary>201 lines</summary>

```
700.             try:
701.                 res = deepseek_reasoner_call(
702.                     DETAIL_ENRICH_PROMPT,
703.                     _detail_enrich_input_single_level(rewrite_result, level),
704.                     max_tokens=12000,
705.                 )
706.                 for k, v in (res.get("details") or {}).items():
707.                     details[k] = v
708.                 log.info("split-batch %s: %d slots OK", level,
709.                          len(res.get("details") or {}))
710.             except RuntimeError as e2:
711.                 log.error("split-batch %s failed: %s", level, e2)
712.                 # Continue — the other level may still succeed.
713. 
714.     filter_keywords(details, rewrite_result)
715.     return {"details": details}
716. 
717. 
718. # ---------------------------------------------------------------------------
719. # Cross-source duplicate check
720. # ---------------------------------------------------------------------------
721. 
722. DUP_CHECK_PROMPT = """You are checking a small set of kids news article briefs for
723. cross-source DUPLICATES.
724. 
725. A "duplicate" = two briefs covering the SAME news event (e.g. "Pope on Iran peace"
726. appears in both PBS and AJ). Different angles on the same event still count as
727. duplicates. Different stories that merely share a topic (both about science, etc.)
728. are NOT duplicates.
729. 
730. Input: N briefs. Each has an id, title, source, and a short excerpt.
731. 
732. Return ONLY valid JSON:
733. {
734.   "verdict": "OK" | "DUP_FOUND",
735.   "duplicate_pairs": [
736.     {"ids": [i, j], "reason": "why these two cover the same event"}
737.   ],
738.   "drop_suggestion": <id of the brief to drop if DUP_FOUND, else null>
739. }
740. 
741. If verdict is OK, duplicate_pairs should be [] and drop_suggestion null.
742. If DUP_FOUND, prefer to drop the one with lower priority source (if given) or
743. the less-engaging one. Only suggest dropping ONE brief even if multiple pairs exist
744. (we handle one substitution per cycle)."""
745. 
746. 
747. def dup_check_input(briefs: list[dict]) -> str:
748.     """briefs: [{id, title, source_name, source_priority, snippet_or_excerpt}]"""
749.     lines = ["Check the following briefs for cross-source duplicates:", ""]
750.     for b in briefs:
751.         lines.append(f"[id: {b['id']}] {b.get('title', '')}")
752.         lines.append(f"  source: {b.get('source_name', '')} (priority {b.get('source_priority', '?')})")
753.         lines.append(f"  excerpt: {(b.get('excerpt') or '')[:400]}")
754.         lines.append("")
755.     return "\n".join(lines)
756. 
757. 
758. def check_duplicates(briefs: list[dict]) -> dict:
759.     return deepseek_call(DUP_CHECK_PROMPT, dup_check_input(briefs),
760.                          max_tokens=500, temperature=0.1)
761. 
762. 
763. # ---------------------------------------------------------------------------
764. # Phase A — per-source mining (unified full+light)
765. # ---------------------------------------------------------------------------
766. 
767. MAX_PICK_BODY_WORDS = 5000   # reject picks with suspiciously long body (probably aggregate page)
768. 
769. 
770. def verify_article_content(art: dict) -> tuple[bool, str | None]:
771.     """Check body words + image quality. Returns (ok, reject_reason)."""
772.     wc = art.get("word_count", 0)
773.     if wc < MIN_PICK_BODY_WORDS:
774.         return False, f"body {wc}w < {MIN_PICK_BODY_WORDS}w"
775.     if wc > MAX_PICK_BODY_WORDS:
776.         return False, f"body {wc}w > {MAX_PICK_BODY_WORDS}w (suspect aggregate page)"
777.     if is_generic_social_image(art.get("og_image")):
778.         return False, f"generic social image: {art.get('og_image')}"
779.     if not art.get("og_image"):
780.         return False, "no og:image"
781.     return True, None
782. 
783. 
784. def _fetch_and_enrich(entry: dict) -> dict:
785.     """Fetch HTML, extract body+og:image, populate word_count."""
786.     from .cleaner import extract_article_from_html
787.     url = entry.get("link") or ""
788.     html_text = fetch_html(url)
789.     if not html_text:
790.         entry["body"] = ""
791.         entry["paragraphs"] = []
792.         entry["og_image"] = None
793.         entry["word_count"] = 0
794.         return entry
795.     extracted = extract_article_from_html(url, html_text)
796.     entry["body"] = extracted.get("cleaned_body") or ""
797.     entry["paragraphs"] = extracted.get("paragraphs") or []
798.     entry["og_image"] = extracted.get("og_image")
799.     entry["word_count"] = len(entry["body"].split()) if entry["body"] else 0
800.     return entry
801. 
802. 
803. def run_source_phase_a(source, html_tag_stripper=None) -> dict | None:
804.     """Run Phase A for one source. Returns a dict like:
805.         {
806.           "source": source,
807.           "winner": <art dict with body+og_image+word_count populated>,
808.           "winner_pick_slot": "choice_1" | "choice_2" | "alternate_0" | ...,
809.           "batch_vet": <raw vet response>,
810.           "kept_briefs": <list of briefs sent to vet>,
811.           "attempts": [{pick_slot, id, reject_reason or None}],
812.         }
813.     or None if no viable winner after trying choice_1, choice_2, then alternates.
814. 
815.     `source` must have attributes: name, rss_url, flow, max_to_vet, min_body_words.
816.     """
817.     from .cleaner import extract_article_from_html
818.     import re as _re
819. 
820.     log.info("[%s] Phase A: flow=%s", source.name, source.flow)
821.     rss_entries = fetch_rss_entries(source.rss_url, max_entries=25)
822.     log.info("[%s]  RSS entries: %d", source.name, len(rss_entries))
823. 
824.     if source.flow == "full":
825.         processed = [process_entry(e, min_words=source.min_body_words) for e in rss_entries]
826.         kept = [p for p in processed if not p.get("skip_reason")]
827.         if source.max_to_vet and len(kept) > source.max_to_vet:
828.             kept = kept[: source.max_to_vet]
829.         if len(kept) < 2:
830.             log.warning("[%s]  only %d kept — insufficient for choice_1+choice_2", source.name, len(kept))
831.             return None
832.         briefs = kept
833.     else:
834.         # Light flow: skip video URLs, strip HTML from descriptions
835.         video_re = _re.compile(r"/(?:videos?|watch|live|podcast)/", _re.I)
836.         html_tag_re = _re.compile(r"<[^>]+>")
837.         briefs = []
838.         for e in rss_entries:
839.             url = e.get("link") or ""
840.             if video_re.search(url):
841.                 continue
842.             desc_clean = html_tag_re.sub("", e.get("summary") or "").strip()
843.             briefs.append({**e, "summary": desc_clean, "highlights": [desc_clean[:400]] if desc_clean else []})
844.             if len(briefs) >= source.max_to_vet:
845.                 break
846. 
847.         if len(briefs) < 2:
848.             log.warning("[%s]  only %d briefs — insufficient", source.name, len(briefs))
849.             return None
850. 
851.     log.info("[%s]  vetter input: %d briefs (reasoner)", source.name, len(briefs))
852.     batch_vet = deepseek_reasoner_call(build_vet_prompt(2),
853.                                         vet_curator_input(briefs, 2),
854.                                         max_tokens=8000)
855. 
856.     # Re-apply strict thresholds authoritatively
857.     for v in batch_vet.get("vet") or []:
858.         safety = v.get("safety") or {}
859.         dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
860.         safety["total"] = sum(dims)
861.         safety["verdict"] = apply_vet_thresholds(safety)
862.     # Drop picks that became REJECT
863.     vet_by_id = {v["id"]: v for v in batch_vet.get("vet") or []}
864.     picks = [p for p in (batch_vet.get("picks") or [])
865.              if not (vet_by_id.get(p.get("id"), {}).get("safety", {}).get("verdict") == "REJECT")]
866.     alternates = [a for a in (batch_vet.get("alternates") or [])
867.                   if not (vet_by_id.get(a.get("id"), {}).get("safety", {}).get("verdict") == "REJECT")]
868. 
869.     # Build candidate order: choice_1, choice_2, alternate_0, alternate_1, ...
870.     candidate_ids: list[tuple[str, int]] = []
871.     for i, p in enumerate(picks[:2]):
872.         candidate_ids.append((f"choice_{i+1}", p.get("id")))
873.     for i, a in enumerate(alternates):
874.         candidate_ids.append((f"alternate_{i}", a.get("id")))
875. 
876.     # Verify up to MAX_CANDIDATES_PER_SOURCE candidates — each must pass body
877.     # + image checks. Downstream (past-dedup + cross-source-dedup) picks the
878.     # best surviving candidate per source instead of cheaply taking choice_1.
879.     MAX_CANDIDATES_PER_SOURCE = 4
880.     candidates: list[dict] = []
881.     attempts: list[dict] = []
882.     for slot, cid in candidate_ids:
883.         if len(candidates) >= MAX_CANDIDATES_PER_SOURCE:
884.             break
885.         if cid is None or cid >= len(briefs):
886.             continue
887.         art = dict(briefs[cid])
888.         if source.flow == "light" or not art.get("body"):
889.             log.info("[%s]  fetching [%s id=%d] %s", source.name, slot, cid,
890.                      art.get("link", "")[:80])
891.             art = _fetch_and_enrich(art)
892.         ok, reason = verify_article_content(art)
893.         attempts.append({"slot": slot, "id": cid, "title": art.get("title"),
894.                          "word_count": art.get("word_count"), "ok": ok, "reason": reason})
895.         if ok:
896.             art["_vet_info"] = vet_by_id.get(cid)
897.             candidates.append({"winner": art, "slot": slot})
898.             log.info("[%s]  ✓ [%s id=%d] %dw", source.name, slot, cid,
899.                      art.get("word_count", 0))
900.         else:
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 900-1100)

<details>
<summary>201 lines</summary>

```
900.         else:
901.             log.info("[%s]  ✗ [%s id=%d] %s — %s", source.name, slot, cid,
902.                      art.get("title", "")[:40], reason)
903. 
904.     if not candidates:
905.         log.warning("[%s]  no viable candidate after %d attempts", source.name,
906.                     len(attempts))
907.         return None
908. 
909.     log.info("[%s]  → %d candidates ready", source.name, len(candidates))
910. 
911.     # Back-compat fields for callers that still read .winner / .winner_slot.
912.     top = candidates[0]
913.     return {
914.         "source": source,
915.         "candidates": candidates,       # NEW: ranked list (up to 4)
916.         "winner": top["winner"],        # legacy: first candidate
917.         "winner_slot": top["slot"],     # legacy: first candidate's slot
918.         "batch_vet": batch_vet,
919.         "kept_briefs": briefs,
920.         "attempts": attempts,
921.     }
922. 
923. 
924. # ---------------------------------------------------------------------------
925. # HTML render
926. # ---------------------------------------------------------------------------
927. 
928. def verdict_class(v: str, kind: str = "safety") -> str:
929.     if kind == "safety":
930.         return {"SAFE": "v-safe", "CAUTION": "v-caution", "REJECT": "v-reject"}.get(v, "")
931.     return {"ENGAGING": "v-engaging", "MEH": "v-meh", "BORING": "v-boring"}.get(v, "")
932. 
933. 
934. def render_html(source_label: str, rss_url: str,
935.                 all_entries: list[dict], kept: list[dict], rejected: list[dict],
936.                 batch_vet: dict, kids_articles_by_id: dict, target_words: int,
937.                 min_words: int) -> str:
938.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
939. 
940.     def esc(s):
941.         return html.escape(str(s) if s is not None else "")
942. 
943.     vet_list = batch_vet.get("vet") or []
944.     clusters = batch_vet.get("clusters") or []
945.     picks = batch_vet.get("picks") or []
946.     picked_ids = {p.get("id") for p in picks}
947.     cluster_by_id = {c.get("id"): c for c in clusters}
948.     article_to_cluster = {v.get("id"): v.get("cluster_id") for v in vet_list}
949. 
950.     parts = [f"""<!doctype html>
951. <html lang="en">
952. <head>
953. <meta charset="utf-8"/>
954. <meta name="viewport" content="width=device-width,initial-scale=1"/>
955. <title>{esc(source_label)} → 12yo — {today}</title>
956. <style>
957.   body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1100px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
958.   h1{{font-size:24px;margin:8px 0;}}
959.   h2{{font-size:17px;margin:28px 0 10px;border-bottom:2px solid #eee;padding-bottom:6px;color:#444;}}
960.   .meta{{color:#777;font-size:13px;margin-bottom:18px;}}
961.   .stats{{background:#f6f6f6;border-radius:6px;padding:10px 14px;margin:12px 0;font-size:13px;color:#555;}}
962.   .stats b{{color:#222;}}
963.   table{{width:100%;border-collapse:collapse;margin-bottom:18px;font-size:12.5px;}}
964.   th,td{{padding:5px 7px;text-align:left;border-bottom:1px solid #eee;vertical-align:top;}}
965.   th{{background:#f0f0f0;font-weight:600;font-size:11.5px;}}
966.   td.n{{text-align:right;font-variant-numeric:tabular-nums;width:28px;}}
967.   td.tot{{text-align:right;font-weight:700;width:36px;}}
968.   .pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10.5px;font-weight:700;white-space:nowrap;}}
969.   .v-safe{{background:#d8f3e0;color:#266;}}
970.   .v-caution{{background:#fff2c4;color:#955;}}
971.   .v-reject{{background:#f9d6d6;color:#933;}}
972.   .v-engaging{{background:#d9e8ff;color:#245;}}
973.   .v-meh{{background:#eee;color:#666;}}
974.   .v-boring{{background:#f9d6d6;color:#933;}}
975.   .hot{{background:#ffe5cc;color:#c35;padding:2px 6px;border-radius:4px;font-size:10.5px;font-weight:700;margin-left:4px;}}
976.   .pick{{background:#fffbea;}}
977.   .pick td:first-child::before{{content:"★ "; color:#d8a300;}}
978.   .cluster-box{{background:#fff6ed;border-left:4px solid #f0903e;padding:10px 14px;margin:8px 0;border-radius:4px;}}
979.   .reason{{background:#eef6ff;border-left:3px solid #4a90e2;padding:8px 12px;margin:8px 0;font-size:13px;}}
980.   .kids-article{{background:#fff9ef;border:2px solid #ffc83d;border-radius:10px;padding:22px 26px;margin:24px 0;box-shadow:0 2px 6px rgba(0,0,0,.06);}}
981.   .kids-article .kheadline{{font-size:24px;font-weight:800;color:#1b1230;margin:0 0 6px;font-family:Georgia,serif;line-height:1.2;}}
982.   .kids-article .ksrc{{font-size:12px;color:#8a6d00;margin-bottom:10px;}}
983.   .kids-article img{{max-width:100%;border-radius:6px;margin:10px 0;}}
984.   .kids-article .kbody{{font-size:16px;line-height:1.65;color:#221a10;}}
985.   .kids-article .kbody p{{margin:0 0 14px;}}
986.   .kids-article .kwim{{background:#fff3c4;border-left:4px solid #e0a800;padding:10px 14px;margin-top:14px;border-radius:4px;font-style:italic;}}
987.   details{{margin:8px 0;}}
988.   details summary{{cursor:pointer;color:#07c;font-size:13px;}}
989.   details pre{{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;background:#fafafa;padding:10px;border-radius:6px;max-height:400px;overflow-y:auto;margin-top:6px;}}
990.   a{{color:#07c;text-decoration:none;}}
991.   a:hover{{text-decoration:underline;}}
992.   .flags{{font-size:11px;color:#933;margin-top:3px;}}
993.   .threshold{{background:#ffede6;border-left:4px solid #d04030;padding:8px 12px;margin:12px 0;border-radius:4px;font-size:13px;}}
994. </style>
995. </head>
996. <body>
997. <h1>{esc(source_label)} → 12-year-old kids news — {today}</h1>
998. <div class="meta">
999.   RSS: <a href="{esc(rss_url)}" target="_blank">{esc(rss_url)}</a> · Filter: body ≥ {min_words}w + image + not /video/ · 2 DeepSeek calls total.
1000. </div>
1001. 
1002. <div class="threshold">
1003.   <b>Vet thresholds (locked 2026-04-23):</b>
1004.   <b class="v-reject pill">REJECT</b> if any dim ≥ 4 or total > 6 ·
1005.   <b class="v-caution pill">CAUTION</b> if total 5-6 (all dims ≤ 3) ·
1006.   <b class="v-safe pill">SAFE</b> if total 0-4 (all dims ≤ 3)
1007. </div>
1008. 
1009. <div class="stats">
1010.   <b>RSS entries:</b> {len(all_entries)} ·
1011.   <b>Kept (to vetter):</b> {len(kept)} ·
1012.   <b>Rejected at filter:</b> {len(rejected)} ·
1013.   <b>Clusters:</b> {len(clusters)} (HOT: {sum(1 for c in clusters if c.get("is_hot"))}) ·
1014.   <b>Picks:</b> {len(picks)} ·
1015.   <b>Kids articles:</b> {len(kids_articles_by_id)}
1016. </div>
1017. 
1018. <h2>Topic clusters</h2>"""]
1019. 
1020.     hot_clusters = [c for c in clusters if c.get("is_hot")]
1021.     other_clusters = [c for c in clusters if not c.get("is_hot")]
1022.     for c in hot_clusters + other_clusters:
1023.         badge = '<span class="hot">🔥 HOT</span>' if c.get("is_hot") else ""
1024.         member_titles = []
1025.         for mid in c.get("members", []):
1026.             if mid < len(kept):
1027.                 member_titles.append(f"[{mid}] {kept[mid].get('title','')[:70]}")
1028.         members_list = "<br>".join(esc(t) for t in member_titles[:10])
1029.         parts.append(f"""
1030. <div class="cluster-box">
1031.   <b>{esc(c.get('theme','?'))}</b> {badge} — <b>{c.get('size', 0)}</b> articles
1032.   <div style="font-size:12px;color:#555;margin-top:6px;">{members_list}</div>
1033. </div>""")
1034. 
1035.     # SAFETY TABLE
1036.     parts.append("""
1037. <h2>Vetter Safety Report · 安全审核报告</h2>
1038. <table>
1039. <thead><tr>
1040.   <th>#</th><th>Title</th>""")
1041.     for short in SAFETY_SHORT:
1042.         parts.append(f"<th>{short}</th>")
1043.     parts.append("""<th>Total</th><th>Verdict</th><th>Cluster</th>
1044. </tr></thead><tbody>""")
1045. 
1046.     for v in vet_list:
1047.         aid = v.get("id")
1048.         if aid >= len(kept):
1049.             continue
1050.         art = kept[aid]
1051.         safety = v.get("safety") or {}
1052.         cluster_id = v.get("cluster_id") or ""
1053.         cluster_size = cluster_by_id.get(cluster_id, {}).get("size", 0)
1054.         cluster_badge = f"🔥{cluster_size}" if cluster_size >= 3 else (str(cluster_size) if cluster_size > 1 else "")
1055.         is_pick = aid in picked_ids
1056.         row_cls = ' class="pick"' if is_pick else ""
1057.         title = art.get("title") or ""
1058.         flags = safety.get("flags") or v.get("flags") or []
1059.         flags_html = f'<div class="flags">flags: {esc(", ".join(flags))}</div>' if flags else ""
1060. 
1061.         parts.append(f"""<tr{row_cls}>
1062.   <td class="n">{aid}</td>
1063.   <td><a href="{esc(art.get('link',''))}" target="_blank">{esc(title[:70])}</a>{flags_html}</td>""")
1064.         for dim in SAFETY_DIMS:
1065.             parts.append(f'<td class="n">{safety.get(dim, "?")}</td>')
1066.         parts.append(f"""<td class="tot">{safety.get("total", "?")}</td>
1067.   <td><span class="pill {verdict_class(safety.get('verdict',''), 'safety')}">{esc(safety.get('verdict',''))}</span></td>
1068.   <td>{esc(cluster_id)} {cluster_badge}</td>
1069. </tr>""")
1070.     parts.append("""</tbody></table>""")
1071. 
1072.     # INTEREST TABLE
1073.     parts.append("""
1074. <h2>Interest Report · 兴趣评分</h2>
1075. <table>
1076. <thead><tr>
1077.   <th>#</th><th>Title</th><th>Import.</th><th>Fun</th><th>KidAppeal</th><th>Peak</th><th>Verdict</th>
1078. </tr></thead><tbody>""")
1079.     for v in vet_list:
1080.         aid = v.get("id")
1081.         if aid >= len(kept):
1082.             continue
1083.         art = kept[aid]
1084.         interest = v.get("interest") or {}
1085.         is_pick = aid in picked_ids
1086.         row_cls = ' class="pick"' if is_pick else ""
1087.         title = art.get("title") or ""
1088.         parts.append(f"""<tr{row_cls}>
1089.   <td class="n">{aid}</td>
1090.   <td>{esc(title[:90])}</td>
1091.   <td class="n">{interest.get("importance", "?")}</td>
1092.   <td class="n">{interest.get("fun_factor", "?")}</td>
1093.   <td class="n">{interest.get("kid_appeal", "?")}</td>
1094.   <td class="tot">{interest.get("peak", "?")}</td>
1095.   <td><span class="pill {verdict_class(interest.get('verdict',''), 'interest')}">{esc(interest.get('verdict',''))}</span></td>
1096. </tr>""")
1097.     parts.append("""</tbody></table>""")
1098. 
1099.     # PICKS
1100.     parts.append("""
```

</details>


### 💬 Copilot

Now let me continue reading full_round.py to check the critical edge cases:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 1-100)

<details>
<summary>100 lines</summary>

```
1. """Full round — news + science + fun aggregators → optimize images → upload to
2. Storage → write redesign_runs + redesign_stories → emit v1-shape payload files
3. for the new v2 UI.
4. 
5. Run:  python -m pipeline.full_round
6. View: http://localhost:18100/  (UI loads from website/payloads/ + article_payloads/ + article_images/)
7. """
8. from __future__ import annotations
9. 
10. import hashlib
11. import json
12. import logging
13. from datetime import datetime, timezone
14. from pathlib import Path
15. from urllib.parse import urlparse
16. 
17. from .news_rss_core import (check_duplicates, detail_enrich,
18.                               run_source_phase_a, tri_variant_rewrite)
19. from .fun_sources import todays_enabled_sources as fun_sources
20. from .fun_sources import todays_topic as fun_topic
21. from .science_sources import todays_enabled_sources as science_sources
22. from .science_sources import todays_topic as science_topic
23. from .image_optimize import fetch_and_optimize
24. from .supabase_io import insert_run, insert_story, update_run, upload_image
25. from .news_sources import enabled_sources as news_sources
26. from .news_aggregate import run_source_with_backups as run_news
27. from .science_aggregate import run_source_with_backups as run_sci
28. from .fun_aggregate import run_source_with_backups as run_fun
29. from .news_sources import backup_sources as news_backups
30. from .science_sources import todays_backup_sources as sci_backups
31. from .fun_sources import todays_backup_sources as fun_backups
32. 
33. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
34. log = logging.getLogger("full-round")
35. 
36. 
37. # -------------------------------------------------------------------
38. # 1) Aggregate 3 categories
39. # -------------------------------------------------------------------
40. 
41. def aggregate_category(label: str, enabled: list, backups: list, runner) -> dict[str, dict]:
42.     """Run Phase A for each source; return `{source_name: {source, candidates}}`.
43.     Each source contributes up to 4 ranked candidates (choice_1…). If the
44.     primary source yields 0 candidates, rotates to a backup source (handled
45.     inside `runner`)."""
46.     log.info("[%s] aggregating from %d sources", label, len(enabled))
47.     used_backups: set[str] = set()
48.     by_source: dict[str, dict] = {}
49.     for source in enabled:
50.         avail = [b for b in backups if b.name not in used_backups]
51.         res = runner(source, avail)
52.         if not res:
53.             continue
54.         # Supports both the new multi-candidate Phase A return shape and the
55.         # legacy single-winner shape (some aggregator paths still produce
56.         # the latter, e.g. after backup rotation).
57.         cands = res.get("candidates")
58.         if not cands and res.get("winner"):
59.             cands = [{"winner": res["winner"], "slot": res.get("winner_slot") or "choice_1"}]
60.         if not cands:
61.             continue
62.         src_obj = res["source"]
63.         by_source[src_obj.name] = {"source": src_obj, "candidates": cands}
64.         if res.get("used_backup"):
65.             used_backups.add(src_obj.name)
66.     return by_source
67. 
68. 
69. def _normalize_title(t: str) -> str:
70.     """lowercase + strip punctuation + collapse whitespace for similarity match."""
71.     import re as _re
72.     s = (t or "").lower()
73.     s = _re.sub(r"[^\w\s]", " ", s)
74.     s = _re.sub(r"\s+", " ", s).strip()
75.     return s
76. 
77. 
78. def _title_similarity(a: str, b: str) -> float:
79.     from difflib import SequenceMatcher
80.     return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()
81. 
82. 
83. # Shape used by filter_past_duplicates + pick_winners_with_dedup:
84. #   by_source = {
85. #     <source_name>: {"source": <SourceObj>, "candidates": [{"winner": art, "slot": "choice_1"}, ...]},
86. #     ...
87. #   }
88. 
89. 
90. def filter_past_duplicates(category: str, by_source: dict[str, dict],
91.                            days: int = 3, threshold: float = 0.80) -> dict[str, dict]:
92.     """Drop candidates whose title ≥threshold-matches any story this category
93.     published in the last `days` days. Cheap — SequenceMatcher on a few
94.     dozen title pairs is microseconds."""
95.     from datetime import date, timedelta
96.     from .supabase_io import client
97.     try:
98.         sb = client()
99.     except Exception as e:
100.         log.warning("past-dedup skipped — Supabase unreachable: %s", e)
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 100-250)

<details>
<summary>151 lines</summary>

```
100.         log.warning("past-dedup skipped — Supabase unreachable: %s", e)
101.         return by_source
102.     start = (date.today() - timedelta(days=days)).isoformat()
103.     try:
104.         r = sb.table("redesign_stories").select(
105.             "source_title, category, published_date"
106.         ).eq("category", category).gte("published_date", start).execute()
107.         past_titles = [row.get("source_title") or "" for row in (r.data or [])]
108.     except Exception as e:
109.         log.warning("past-dedup query failed — skipping: %s", e)
110.         return by_source
111. 
112.     if not past_titles:
113.         log.info("  [%s] past-dedup: no prior stories in last %d days", category, days)
114.         return by_source
115. 
116.     result: dict[str, dict] = {}
117.     for name, bundle in by_source.items():
118.         kept: list[dict] = []
119.         for c in bundle["candidates"]:
120.             t = (c["winner"].get("title") or "")
121.             best = max((_title_similarity(t, pt) for pt in past_titles), default=0.0)
122.             if best >= threshold:
123.                 log.info("  [%s/%s] past-dup drop %s (sim=%.2f) — %s",
124.                          category, name, c.get("slot"), best, t[:60])
125.             else:
126.                 kept.append(c)
127.         result[name] = {"source": bundle["source"], "candidates": kept}
128.     return result
129. 
130. 
131. def pick_winners_with_dedup(by_source: dict[str, dict]) -> list[dict]:
132.     """Pick the highest-ranked surviving candidate per source, then
133.     cross-source dedup. When a pair of today's picks duplicates, drop the
134.     weaker source's current pick and promote its NEXT candidate (no extra
135.     DeepSeek-and-RSS round-trip — we already mined up to 4 per source)."""
136.     ptrs: dict[str, int] = {name: 0 for name in by_source}
137.     exhausted: set[str] = set()
138. 
139.     def current_for(name: str) -> dict | None:
140.         idx = ptrs.get(name, 0)
141.         cands = by_source[name].get("candidates") or []
142.         return cands[idx] if idx < len(cands) else None
143. 
144.     for _round in range(8):
145.         picks: list[tuple[str, dict]] = []
146.         for name in by_source:
147.             if name in exhausted:
148.                 continue
149.             c = current_for(name)
150.             if c:
151.                 picks.append((name, c))
152.         if len(picks) < 2:
153.             break
154.         briefs = [
155.             {"id": i, "title": c["winner"].get("title"),
156.              "source_name": name,
157.              "source_priority": getattr(by_source[name]["source"], "priority", 9),
158.              "excerpt": (c["winner"].get("body") or "")[:400]}
159.             for i, (name, c) in enumerate(picks)
160.         ]
161.         dup = check_duplicates(briefs)
162.         if dup.get("verdict") != "DUP_FOUND":
163.             break
164.         drop_id = dup.get("drop_suggestion")
165.         if drop_id is None and dup.get("duplicate_pairs"):
166.             pair = dup["duplicate_pairs"][0]["ids"]
167.             drop_id = max(pair, key=lambda i: briefs[i]["source_priority"])
168.         if drop_id is None or drop_id >= len(picks):
169.             break
170.         drop_name, drop_cand = picks[drop_id]
171.         log.info("  cross-source dup — promoting next candidate for [%s] "
172.                  "(was %s: %s)",
173.                  drop_name, drop_cand["slot"],
174.                  (drop_cand["winner"].get("title") or "")[:50])
175.         ptrs[drop_name] += 1
176.         if ptrs[drop_name] >= len(by_source[drop_name].get("candidates") or []):
177.             log.warning("  [%s] exhausted all candidates — skipping", drop_name)
178.             exhausted.add(drop_name)
179. 
180.     final: list[dict] = []
181.     for name, bundle in by_source.items():
182.         if name in exhausted:
183.             continue
184.         c = current_for(name)
185.         if c:
186.             final.append({
187.                 "source": bundle["source"],
188.                 "winner": c["winner"],
189.                 "winner_slot": c["slot"],
190.             })
191.     return final
192. 
193. 
194. # -------------------------------------------------------------------
195. # 2) Optimize + upload images
196. # -------------------------------------------------------------------
197. 
198. def _short_hash(s: str) -> str:
199.     return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
200. 
201. 
202. def process_images(stories: list[dict], today: str, website_dir: Path) -> None:
203.     """For each story winner, download + optimize og:image → local cache + Supabase Storage.
204.     Annotates each story dict with _image_local, _image_storage_url.
205.     """
206.     images_dir = website_dir / "article_images"
207.     images_dir.mkdir(parents=True, exist_ok=True)
208.     for s in stories:
209.         art = s["winner"]
210.         og = art.get("og_image")
211.         if not og:
212.             log.warning("[%s] no og:image", art.get("title", "")[:60])
213.             continue
214.         img_id = _short_hash(art.get("link") or og)
215.         filename = f"article_{img_id}.webp"
216.         local_path = images_dir / filename
217.         info = fetch_and_optimize(og, local_path)
218.         if not info:
219.             log.warning("  skip image for %s", art.get("title", "")[:60])
220.             continue
221.         s["_image_id"] = img_id
222.         s["_image_local"] = f"article_images/{filename}"
223.         s["_image_info"] = info
224.         # Upload to Supabase Storage (public)
225.         storage_name = f"{today}/{filename}"
226.         storage_url = upload_image(local_path, storage_name)
227.         if storage_url:
228.             s["_image_storage_url"] = storage_url
229.         log.info("  ✓ image %s (%.1f KB, q=%d)  %s",
230.                  filename, info["final_bytes"] / 1024, info["final_quality"],
231.                  "+ uploaded" if storage_url else "local-only")
232. 
233. 
234. # -------------------------------------------------------------------
235. # 3) Rewrite (tri-variant) — batched per category
236. # -------------------------------------------------------------------
237. 
238. def rewrite_for_category(stories: list[dict]) -> tuple[dict[int, dict], dict]:
239.     """Tri-variant rewrite, then detail enrichment. Returns
240.     (variants_by_src_id, details_by_slot). Raises if either step ultimately
241.     fails — callers decide whether that's fatal for the whole run."""
242.     if not stories:
243.         return {}, {}
244.     articles_for_rewrite = [(i, s["winner"]) for i, s in enumerate(stories)]
245.     rewrite_res = tri_variant_rewrite(articles_for_rewrite)
246.     variants = {a.get("source_id"): a for a in rewrite_res.get("articles") or []}
247.     if len(variants) < len(stories):
248.         raise RuntimeError(
249.             f"rewrite returned {len(variants)} variants for {len(stories)} stories"
250.         )
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 250-400)

<details>
<summary>151 lines</summary>

```
250.         )
251. 
252.     # Phase D — detail enrichment (1 extra call per category)
253.     enrich = detail_enrich(rewrite_res)
254.     details_by_slot = enrich.get("details") or {}
255.     expected_slots = len(stories) * 2  # easy + middle per story
256.     if len(details_by_slot) < expected_slots:
257.         raise RuntimeError(
258.             f"detail_enrich returned {len(details_by_slot)} slots, "
259.             f"expected {expected_slots}"
260.         )
261.     return variants, details_by_slot
262. 
263. 
264. # -------------------------------------------------------------------
265. # 4) Emit v1-shape payload files (what the existing v2 UI reads)
266. # -------------------------------------------------------------------
267. 
268. def make_story_id(date: str, category: str, slot: int) -> str:
269.     return f"{date}-{category.lower()}-{slot}"
270. 
271. 
272. def card_summary(variant: dict, max_words: int = 120) -> str:
273.     """Short blurb for the home-page card. Prefer `card_summary` from the
274.     rewriter; fall back to the first few sentences of `body` capped at
275.     `max_words`. Strip to whole sentence so it never ends mid-word."""
276.     cs = (variant.get("card_summary") or "").strip()
277.     if cs:
278.         words = cs.split()
279.         if len(words) <= max_words:
280.             return cs
281.         return " ".join(words[:max_words]).rstrip(",;:") + "…"
282.     body = (variant.get("body") or "").strip()
283.     if not body:
284.         return ""
285.     import re
286.     sentences = re.split(r'(?<=[.!?])\s+', body)
287.     out, count = [], 0
288.     for s in sentences:
289.         n = len(s.split())
290.         if count + n > max_words and out:
291.             break
292.         out.append(s)
293.         count += n
294.         if count >= max_words * 0.6:  # stop once we have a reasonable blurb
295.             break
296.     return " ".join(out).strip()
297. 
298. 
299. def emit_v1_shape(stories_by_cat: dict[str, list[dict]],
300.                   variants_by_cat: dict[str, dict[int, dict]],
301.                   details_by_cat: dict[str, dict[str, dict]],
302.                   today: str,
303.                   website_dir: Path) -> None:
304.     """Write v1-compatible payload files the prototype UI already reads:
305.       payloads/articles_<cat>_<level>.json  (listings)
306.       article_payloads/payload_<id>/<level>.json  (detail)
307.     """
308.     payloads_dir = website_dir / "payloads"
309.     details_dir = website_dir / "article_payloads"
310.     payloads_dir.mkdir(parents=True, exist_ok=True)
311.     details_dir.mkdir(parents=True, exist_ok=True)
312. 
313.     mined_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
314. 
315.     for category in ("News", "Science", "Fun"):
316.         stories = stories_by_cat.get(category, [])
317.         variants = variants_by_cat.get(category, {})
318.         details = details_by_cat.get(category, {})
319.         # Build one listing file per level (easy / middle / cn) per category
320.         per_level_articles = {"easy": [], "middle": [], "cn": []}
321.         for slot, s in enumerate(stories, start=1):
322.             art = s["winner"]
323.             var = variants.get(slot - 1) or {}
324.             story_id = s.get("_story_id") or make_story_id(today, category, slot)
325.             s["_story_id"] = story_id
326.             img_local = s.get("_image_local") or ""
327.             src_name = s["source"].name
328.             src_url = art.get("link") or ""
329.             time_ago = art.get("published") or ""
330. 
331.             easy = var.get("easy_en") or {}
332.             middle = var.get("middle_en") or {}
333.             zh = var.get("zh") or {}
334. 
335.             # Listings (flat, v1-shape) — summary is short card blurb (≤120 words)
336.             common_listing = {
337.                 "id": story_id,
338.                 "source": src_name,
339.                 "time_ago": time_ago,
340.                 "mined_at": mined_at,                  # when this pipeline run captured the story
341.                 "source_published_at": art.get("published") or "",
342.                 "image_url": f"/{img_local}" if img_local else "",
343.                 "category": category,
344.             }
345.             per_level_articles["easy"].append({**common_listing,
346.                 "title": easy.get("headline") or art.get("title") or "",
347.                 "summary": card_summary(easy),
348.             })
349.             per_level_articles["middle"].append({**common_listing,
350.                 "title": middle.get("headline") or art.get("title") or "",
351.                 "summary": card_summary(middle),
352.             })
353.             per_level_articles["cn"].append({**common_listing,
354.                 "title": zh.get("headline") or "",
355.                 "summary": zh.get("summary") or "",
356.             })
357. 
358.             # Detail payloads (per-story, per-level). Chinese is summary-only → no detail.
359.             story_detail_dir = details_dir / f"payload_{story_id}"
360.             story_detail_dir.mkdir(parents=True, exist_ok=True)
361.             # slot-based lookup into details_by_slot: "<article_index>_<level>"
362.             for lvl_key, var_obj in (("easy", easy), ("middle", middle)):
363.                 slot_key = f"{slot - 1}_{lvl_key}"
364.                 det = details.get(slot_key) or {}
365.                 bg = det.get("background_read") or []
366.                 if isinstance(bg, str):
367.                     bg = [bg]
368.                 detail = {
369.                     "title": var_obj.get("headline") or art.get("title") or "",
370.                     "summary": var_obj.get("body") or "",      # full body (v1 pattern)
371.                     "why_it_matters": det.get("why_it_matters", ""),
372.                     "image_url": f"/{img_local}" if img_local else "",
373.                     "keywords": det.get("keywords") or [],
374.                     "questions": det.get("questions") or [],
375.                     "background_read": bg,
376.                     "Article_Structure": det.get("Article_Structure") or [],
377.                     "perspectives": det.get("perspectives") or [],
378.                     "mined_at": mined_at,
379.                     "source_published_at": art.get("published") or "",
380.                     "source_name": src_name,
381.                     "source_url": src_url,
382.                 }
383.                 (story_detail_dir / f"{lvl_key}.json").write_text(
384.                     json.dumps(detail, ensure_ascii=False, indent=2)
385.                 )
386. 
387.         # Write 3 listing files per category (easy / middle / cn)
388.         cat_slug = category.lower()
389.         for lvl_key, items in per_level_articles.items():
390.             out = payloads_dir / f"articles_{cat_slug}_{lvl_key}.json"
391.             out.write_text(json.dumps({"articles": items},
392.                                        ensure_ascii=False, indent=2))
393. 
394. 
395. # -------------------------------------------------------------------
396. # 5) Persist to Supabase (runs + stories rows)
397. # -------------------------------------------------------------------
398. 
399. def persist_to_supabase(stories_by_cat, variants_by_cat, today: str, run_id: str) -> int:
400.     """Insert stories rows; return count inserted."""
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 400-550)

<details>
<summary>144 lines</summary>

```
400.     """Insert stories rows; return count inserted."""
401.     count = 0
402.     for category, stories in stories_by_cat.items():
403.         variants = variants_by_cat.get(category, {})
404.         for slot, s in enumerate(stories, start=1):
405.             art = s["winner"]
406.             story_id = s.get("_story_id") or make_story_id(today, category, slot)
407.             vet = art.get("_vet_info") or {}
408.             safety = vet.get("safety") or {}
409.             interest = vet.get("interest") or {}
410.             src_host = urlparse(art.get("link") or "").netloc.replace("www.", "")
411.             row = {
412.                 "run_id": run_id,
413.                 "category": category,
414.                 "story_slot": slot,
415.                 "published_date": today,
416.                 "source_name": s["source"].name,
417.                 "source_url": art.get("link") or "",
418.                 "source_title": art.get("title") or "",
419.                 "source_published_at": None,   # skip for now
420.                 "winner_slot": s.get("winner_slot"),
421.                 "used_backup": bool(s.get("used_backup")),
422.                 "backup_for_source": s.get("primary_source_name"),
423.                 "safety_violence":   safety.get("violence"),
424.                 "safety_sexual":     safety.get("sexual"),
425.                 "safety_substance":  safety.get("substance"),
426.                 "safety_language":   safety.get("language"),
427.                 "safety_fear":       safety.get("fear"),
428.                 "safety_adult_themes": safety.get("adult_themes"),
429.                 "safety_distress":   safety.get("distress"),
430.                 "safety_bias":       safety.get("bias"),
431.                 "safety_total":      safety.get("total"),
432.                 "safety_verdict":    safety.get("verdict"),
433.                 "interest_importance": interest.get("importance"),
434.                 "interest_fun_factor": interest.get("fun_factor"),
435.                 "interest_kid_appeal": interest.get("kid_appeal"),
436.                 "interest_peak":       interest.get("peak"),
437.                 "interest_verdict":    interest.get("verdict"),
438.                 "vet_flags": safety.get("flags") or vet.get("flags") or [],
439.                 "primary_image_url": s.get("_image_storage_url") or art.get("og_image"),
440.                 "primary_image_local": s.get("_image_local"),
441.                 "primary_image_credit": src_host,
442.                 "payload_path": f"payloads/articles_{category.lower()}_easy.json",
443.                 "payload_story_id": story_id,
444.             }
445.             sid = insert_story(row)
446.             if sid:
447.                 count += 1
448.                 log.info("  → redesign_stories id=%s · %s #%d %s",
449.                          sid[:8], category, slot, art.get("title", "")[:50])
450.             else:
451.                 log.warning("  insert failed: %s", art.get("title", "")[:60])
452.     return count
453. 
454. 
455. # -------------------------------------------------------------------
456. # Orchestrator
457. # -------------------------------------------------------------------
458. 
459. def main() -> None:
460.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
461.     website_dir = Path(__file__).resolve().parent.parent / "website"
462. 
463.     # Start run record
464.     run_id = insert_run({"run_date": today, "status": "running"})
465.     if not run_id:
466.         log.warning("insert_run failed — continuing without DB persistence")
467. 
468.     log.info("=== AGGREGATE (up to 4 candidates per source) ===")
469.     news_bs = aggregate_category("News", news_sources(), news_backups(), run_news)
470.     science_bs = aggregate_category("Science", science_sources(), sci_backups(), run_sci)
471.     fun_bs = aggregate_category("Fun", fun_sources(), fun_backups(), run_fun)
472. 
473.     log.info("=== PAST-DEDUP (3-day lookback · title ≥80%% similar = dup) ===")
474.     news_bs = filter_past_duplicates("News", news_bs, days=3)
475.     science_bs = filter_past_duplicates("Science", science_bs, days=3)
476.     fun_bs = filter_past_duplicates("Fun", fun_bs, days=3)
477. 
478.     log.info("=== PICK + CROSS-SOURCE DEDUP (promote next candidate on dup) ===")
479.     news = pick_winners_with_dedup(news_bs)
480.     science = pick_winners_with_dedup(science_bs)
481.     fun = pick_winners_with_dedup(fun_bs)
482.     stories_by_cat = {"News": news, "Science": science, "Fun": fun}
483.     for cat, ws in stories_by_cat.items():
484.         log.info("  %s: %d winners", cat, len(ws))
485. 
486.     log.info("=== IMAGES (optimize + upload) ===")
487.     for cat, ws in stories_by_cat.items():
488.         log.info("[%s] processing %d images", cat, len(ws))
489.         process_images(ws, today, website_dir)
490. 
491.     log.info("=== REWRITE (tri-variant + detail enrich, 2 calls per category) ===")
492.     variants_by_cat: dict[str, dict] = {}
493.     details_by_cat: dict[str, dict] = {}
494.     failures: list[str] = []
495.     for cat, ws in stories_by_cat.items():
496.         try:
497.             v, d = rewrite_for_category(ws)
498.             variants_by_cat[cat] = v
499.             details_by_cat[cat] = d
500.             log.info("  [%s] rewrite: %d variants · detail slots: %d",
501.                      cat, len(v), len(d))
502.         except Exception as e:  # noqa: BLE001
503.             log.error("  [%s] rewrite/enrich FAILED: %s", cat, e)
504.             failures.append(f"{cat}: {e}")
505. 
506.     if failures:
507.         # Mark run as failed (if DB tracking on), don't upload a partial zip.
508.         msg = f"{len(failures)} category failures: " + " | ".join(failures)
509.         if run_id:
510.             update_run(run_id, {"status": "failed",
511.                                 "finished_at": datetime.now(timezone.utc).isoformat(),
512.                                 "notes": msg})
513.         log.error("Aborting — %s", msg)
514.         raise SystemExit(1)
515. 
516.     log.info("=== EMIT v1-shape payload files ===")
517.     emit_v1_shape(stories_by_cat, variants_by_cat, details_by_cat, today, website_dir)
518. 
519.     log.info("=== PERSIST TO SUPABASE ===")
520.     count = 0
521.     if run_id:
522.         count = persist_to_supabase(stories_by_cat, variants_by_cat, today, run_id)
523.         update_run(run_id, {"status": "completed",
524.                             "finished_at": datetime.now(timezone.utc).isoformat(),
525.                             "notes": f"stories persisted: {count}"})
526. 
527.     log.info("=== PACK + UPLOAD ZIP (deploy trigger) ===")
528.     try:
529.         from .pack_and_upload import main as _pack_upload
530.         _pack_upload()
531.     except Exception as e:  # noqa: BLE001
532.         log.warning("pack_and_upload failed — site will lag until next run: %s", e)
533. 
534.     log.info("=== DONE ===")
535.     total_stories = sum(len(ws) for ws in stories_by_cat.values())
536.     log.info("Run: %s · Stories: %d · DB persisted: %d", run_id or "(no DB)",
537.              total_stories, count)
538.     log.info("View: http://localhost:18100/")
539. 
540. 
541. if __name__ == "__main__":
542.     main()
543.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py (lines 1-100)

<details>
<summary>100 lines</summary>

```
1. """Pack `website/` into a zip and upload it to Supabase Storage as both
2. `<YYYY-MM-DD>.zip` (immutable archive) and `latest.zip` (what the deploy repo's
3. GitHub Action fetches). Also writes a `latest-manifest.json` (+ dated copy)
4. with the version + content hash + story IDs so anyone inspecting the bucket
5. knows what's inside without downloading.
6. 
7. Validates today's content bundle BEFORE packing. If any listing or detail file
8. is missing or incomplete, refuses to upload — the live site keeps yesterday's
9. zip until the pipeline produces a fully-formed bundle.
10. 
11. After a successful upload, runs retention: keeps `latest.*` + the last
12. `RETENTION_DAYS` dated archives; deletes older dated zips + manifests."""
13. from __future__ import annotations
14. 
15. import hashlib
16. import json
17. import logging
18. import os
19. import re
20. import sys
21. import zipfile
22. from datetime import datetime, timezone
23. from io import BytesIO
24. from pathlib import Path
25. 
26. from supabase import create_client
27. 
28. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
29. log = logging.getLogger("pack")
30. 
31. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
32. for _line in (_envp.open() if _envp.exists() else []):
33.     if "=" in _line and not _line.startswith("#"):
34.         k, v = _line.strip().split("=", 1)
35.         os.environ[k] = v
36. 
37. ROOT = Path(__file__).resolve().parent.parent
38. WEB = ROOT / "website"
39. BUCKET = "redesign-daily-content"
40. RETENTION_DAYS = 30  # dated archives older than this get deleted
41. 
42. # Allowlist of top-level files/dirs that ship to production.
43. INCLUDE_FILES = {"index.html", "article.jsx", "home.jsx", "components.jsx",
44.                  "data.jsx", "user-panel.jsx"}
45. INCLUDE_DIRS = {"payloads", "article_payloads", "article_images", "assets"}
46. 
47. 
48. def collect_files() -> list[tuple[Path, str]]:
49.     out: list[tuple[Path, str]] = []
50.     for name in INCLUDE_FILES:
51.         p = WEB / name
52.         if p.is_file():
53.             out.append((p, name))
54.     for d in INCLUDE_DIRS:
55.         base = WEB / d
56.         if not base.is_dir():
57.             continue
58.         for p in base.rglob("*"):
59.             if p.is_file() and not p.name.startswith("."):
60.                 out.append((p, str(p.relative_to(WEB))))
61.     return out
62. 
63. 
64. CATS = ("news", "science", "fun")
65. # (field, min_count) — what a detail payload MUST contain to count as complete.
66. DETAIL_MIN = [
67.     ("keywords", 3),
68.     ("questions", 3),
69.     ("background_read", 1),
70.     ("Article_Structure", 3),
71. ]
72. 
73. 
74. def validate_bundle(today: str) -> None:
75.     """Fail (SystemExit 1) if today's bundle is incomplete. Check:
76.       · 9 listing files (3 cats × easy/middle/cn), each with exactly 3 articles
77.       · 18 detail payloads (9 stories × easy/middle), each with non-empty
78.         keywords/questions/background_read/Article_Structure
79.       · 9 article images on disk (one per story id)
80.     """
81.     errs: list[str] = []
82. 
83.     # Listing files — 2 or 3 per cat/lvl acceptable (ideal=3; 2 after
84.     # cross-source dup drops when all backups are exhausted). <2 is fatal.
85.     payloads = WEB / "payloads"
86.     short_cats: set[str] = set()  # cats that shipped <3
87.     for cat in CATS:
88.         for lvl in ("easy", "middle", "cn"):
89.             p = payloads / f"articles_{cat}_{lvl}.json"
90.             if not p.is_file():
91.                 errs.append(f"missing listing: {p.name}")
92.                 continue
93.             try:
94.                 doc = json.loads(p.read_text())
95.                 arts = doc.get("articles") or []
96.                 if len(arts) < 2:
97.                     errs.append(f"{p.name}: {len(arts)} articles (need ≥2)")
98.                 elif len(arts) < 3:
99.                     short_cats.add(f"{cat}/{lvl}")
100.                 for a in arts:
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py (lines 100-250)

<details>
<summary>151 lines</summary>

```
100.                 for a in arts:
101.                     if not (a.get("title") and a.get("summary") and a.get("id")):
102.                         errs.append(f"{p.name}: article {a.get('id','?')} missing title/summary/id")
103.             except Exception as e:  # noqa: BLE001
104.                 errs.append(f"{p.name}: parse error {e}")
105.     if short_cats:
106.         log.warning("Shipping with <3 articles in: %s", sorted(short_cats))
107. 
108.     # Detail payloads (easy + middle only; cn has no detail page) — iterate
109.     # actual story IDs from the middle listing so 2-article cats validate
110.     # cleanly.
111.     details = WEB / "article_payloads"
112.     all_story_ids: list[str] = []
113.     for cat in CATS:
114.         p = payloads / f"articles_{cat}_middle.json"
115.         if p.is_file():
116.             try:
117.                 arts = json.loads(p.read_text()).get("articles") or []
118.                 all_story_ids.extend(a.get("id") for a in arts if a.get("id"))
119.             except Exception:
120.                 pass
121.     for story_id in all_story_ids:
122.         story_dir = details / f"payload_{story_id}"
123.         if not story_dir.is_dir():
124.             errs.append(f"missing detail dir: payload_{story_id}")
125.             continue
126.         for lvl in ("easy", "middle"):
127.             p = story_dir / f"{lvl}.json"
128.             if not p.is_file():
129.                 errs.append(f"missing detail: {story_id}/{lvl}.json")
130.                 continue
131.             try:
132.                 d = json.loads(p.read_text())
133.                 if not (d.get("summary") and len((d.get("summary") or "").split()) >= 50):
134.                     errs.append(f"{story_id}/{lvl}: summary missing or <50 words")
135.                 for field, min_n in DETAIL_MIN:
136.                     if len(d.get(field) or []) < min_n:
137.                         errs.append(
138.                             f"{story_id}/{lvl}: {field} has "
139.                             f"{len(d.get(field) or [])} (need ≥{min_n})"
140.                         )
141.             except Exception as e:  # noqa: BLE001
142.                 errs.append(f"{story_id}/{lvl}: parse error {e}")
143. 
144.     # Per-story images (same image used across easy/middle for a story)
145.     images_dir = WEB / "article_images"
146.     needed_images: set[str] = set()
147.     for cat in CATS:
148.         # Pull image_urls from today's listings — whichever level works
149.         for lvl in ("middle", "easy"):
150.             p = payloads / f"articles_{cat}_{lvl}.json"
151.             if not p.is_file():
152.                 continue
153.             try:
154.                 doc = json.loads(p.read_text())
155.                 for a in doc.get("articles") or []:
156.                     url = a.get("image_url") or ""
157.                     if url:
158.                         needed_images.add(Path(url).name)
159.                 break
160.             except Exception:
161.                 continue
162.     for name in needed_images:
163.         if not (images_dir / name).is_file():
164.             errs.append(f"missing image: article_images/{name}")
165. 
166.     if errs:
167.         log.error("Bundle validation FAILED — refusing to pack/upload:")
168.         for e in errs:
169.             log.error("  · %s", e)
170.         raise SystemExit(1)
171.     log.info("Bundle validation OK: 9 listings · 18 details · %d images",
172.              len(needed_images))
173. 
174. 
175. def build_zip() -> bytes:
176.     buf = BytesIO()
177.     files = collect_files()
178.     with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
179.         for p, arc in files:
180.             zf.write(p, arcname=arc)
181.     log.info("Packed %d files (%d bytes)", len(files), buf.tell())
182.     return buf.getvalue()
183. 
184. 
185. def build_manifest(today: str, body: bytes) -> dict:
186.     """Summarize what this zip contains — version + content hash + story IDs.
187.     Consumers can compare manifest sha256 without downloading the zip."""
188.     stories: list[dict] = []
189.     for cat in CATS:
190.         p = WEB / "payloads" / f"articles_{cat}_middle.json"
191.         if not p.is_file():
192.             continue
193.         try:
194.             for a in (json.loads(p.read_text()).get("articles") or []):
195.                 stories.append({
196.                     "id": a.get("id"),
197.                     "category": a.get("category"),
198.                     "title": a.get("title"),
199.                     "mined_at": a.get("mined_at"),
200.                     "source": a.get("source"),
201.                     "source_published_at": a.get("source_published_at"),
202.                 })
203.         except Exception:
204.             pass
205.     return {
206.         "version": today,
207.         "packed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
208.         "git_sha": os.environ.get("GITHUB_SHA") or "",
209.         "zip_bytes": len(body),
210.         "zip_sha256": hashlib.sha256(body).hexdigest(),
211.         "story_count": len(stories),
212.         "stories": stories,
213.     }
214. 
215. 
216. DATED_ZIP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.zip$")
217. DATED_MANIFEST_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-manifest\.json$")
218. DATED_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
219. 
220. 
221. def upload_dated_flat_files(sb, date_str: str, bundle: bytes | None = None) -> int:
222.     """Upload each file under the website bundle to `<date>/<relpath>` in the
223.     bucket so the UI can fetch past days' content directly (no zip parsing
224.     in the browser). `bundle` is an optional zip body — if given, files are
225.     extracted from it; otherwise read from local disk. Returns file count."""
226.     uploaded = 0
227.     if bundle is not None:
228.         zf = zipfile.ZipFile(BytesIO(bundle))
229.         members = [n for n in zf.namelist()
230.                    if n.endswith(".json") or n.endswith(".webp")]
231.         for name in members:
232.             body = zf.read(name)
233.             ctype = "application/json" if name.endswith(".json") else "image/webp"
234.             sb.storage.from_(BUCKET).upload(
235.                 path=f"{date_str}/{name}",
236.                 file=body,
237.                 file_options={"content-type": ctype, "upsert": "true"},
238.             )
239.             uploaded += 1
240.     else:
241.         for p, arc in collect_files():
242.             if not (arc.endswith(".json") or arc.endswith(".webp")):
243.                 continue  # skip HTML/JSX shell from dated flat copy
244.             ctype = "application/json" if arc.endswith(".json") else "image/webp"
245.             sb.storage.from_(BUCKET).upload(
246.                 path=f"{date_str}/{arc}",
247.                 file=p.read_bytes(),
248.                 file_options={"content-type": ctype, "upsert": "true"},
249.             )
250.             uploaded += 1
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py (lines 250-400)

<details>
<summary>151 lines</summary>

```
250.             uploaded += 1
251.     log.info("dated-flat: uploaded %d files under %s/", uploaded, date_str)
252.     return uploaded
253. 
254. 
255. def update_archive_index(sb, dates: list[str]) -> None:
256.     """Merge `dates` into `archive-index.json` (descending, deduped, cap 30)."""
257.     try:
258.         body = sb.storage.from_(BUCKET).download("archive-index.json")
259.         idx = json.loads(body.decode() if isinstance(body, bytes) else body)
260.     except Exception:
261.         idx = {"dates": []}
262.     existing = set(idx.get("dates") or [])
263.     existing.update(dates)
264.     all_dates = sorted(existing, reverse=True)[:RETENTION_DAYS]
265.     idx = {"dates": all_dates,
266.            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
267.     sb.storage.from_(BUCKET).upload(
268.         path="archive-index.json",
269.         file=json.dumps(idx, ensure_ascii=False, indent=2).encode(),
270.         file_options={"content-type": "application/json", "upsert": "true"},
271.     )
272.     log.info("archive-index updated: %d dates (newest=%s)",
273.              len(all_dates), all_dates[0] if all_dates else "-")
274. 
275. 
276. def backfill_missing_archive_dirs(sb, current_index: list[str]) -> list[str]:
277.     """For any YYYY-MM-DD.zip in the bucket whose date isn't in the archive
278.     index AND doesn't yet have its flat dir, extract the zip and upload
279.     flat files. Returns list of backfilled dates."""
280.     current_set = set(current_index)
281.     objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
282.     candidates = []
283.     for o in objs or []:
284.         m = DATED_ZIP_RE.match(o.get("name") or "")
285.         if m and m.group(1) not in current_set:
286.             candidates.append(m.group(1))
287.     backfilled: list[str] = []
288.     for d in sorted(candidates):
289.         try:
290.             body = sb.storage.from_(BUCKET).download(f"{d}.zip")
291.             body = bytes(body) if not isinstance(body, bytes) else body
292.             upload_dated_flat_files(sb, d, bundle=body)
293.             backfilled.append(d)
294.         except Exception as e:  # noqa: BLE001
295.             log.warning("backfill %s failed: %s", d, e)
296.     return backfilled
297. 
298. 
299. def cleanup_retention(sb, keep_days: int) -> None:
300.     """Delete dated archives older than `keep_days`. Keeps `latest.*` always.
301.     Also removes all files under `<date>/` prefix for expired dates."""
302.     from datetime import date, timedelta
303.     cutoff = date.today() - timedelta(days=keep_days)
304.     expired: set[str] = set()
305.     objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
306.     to_delete: list[str] = []
307.     for o in objs or []:
308.         name = o.get("name") or ""
309.         for rx in (DATED_ZIP_RE, DATED_MANIFEST_RE, DATED_DIR_RE):
310.             m = rx.match(name)
311.             if not m:
312.                 continue
313.             try:
314.                 day = datetime.strptime(m.group(1), "%Y-%m-%d").date()
315.             except ValueError:
316.                 continue
317.             if day < cutoff:
318.                 if rx is DATED_DIR_RE:
319.                     expired.add(name)
320.                 else:
321.                     to_delete.append(name)
322.     # For each expired dir, list its files + delete them
323.     for d in expired:
324.         try:
325.             subs = sb.storage.from_(BUCKET).list(d, {"limit": 1000})
326.             for s in subs or []:
327.                 to_delete.append(f"{d}/{s.get('name')}")
328.         except Exception as e:  # noqa: BLE001
329.             log.warning("retention: listing %s/ failed: %s", d, e)
330.     if not to_delete:
331.         log.info("retention: 0 old files (keep %d days)", keep_days)
332.         return
333.     # Supabase remove() takes a list of paths.
334.     sb.storage.from_(BUCKET).remove(to_delete)
335.     log.info("retention: deleted %d files older than %s",
336.              len(to_delete), cutoff.isoformat())
337. 
338. 
339. def local_freshest_mined_at() -> str | None:
340.     """ISO-8601 of the most recent mined_at across all today's listings."""
341.     stamps: list[str] = []
342.     for cat in CATS:
343.         p = WEB / "payloads" / f"articles_{cat}_middle.json"
344.         if not p.is_file():
345.             continue
346.         try:
347.             for a in json.loads(p.read_text()).get("articles") or []:
348.                 if a.get("mined_at"):
349.                     stamps.append(a["mined_at"])
350.         except Exception:
351.             continue
352.     return max(stamps) if stamps else None
353. 
354. 
355. def check_not_overwriting_newer(sb) -> None:
356.     """Refuse to upload if the bucket already has a manifest whose packed_at
357.     (or freshest story mined_at) is newer than our local content. Prevents a
358.     local `pack_and_upload` from silently replacing CI-generated output."""
359.     try:
360.         body = sb.storage.from_(BUCKET).download("latest-manifest.json")
361.         remote = json.loads(body.decode() if isinstance(body, bytes) else body)
362.     except Exception:
363.         return  # nothing remote yet — safe to upload
364.     remote_stamps = [s.get("mined_at") for s in (remote.get("stories") or [])
365.                      if s.get("mined_at")]
366.     remote_freshest = max(remote_stamps) if remote_stamps else remote.get("packed_at")
367.     local_freshest = local_freshest_mined_at()
368.     if not (remote_freshest and local_freshest):
369.         return
370.     if local_freshest < remote_freshest:
371.         msg = (f"REFUSE: remote manifest is newer than local. "
372.                f"remote freshest={remote_freshest} · local freshest={local_freshest}. "
373.                "If you really want to overwrite, set ALLOW_STALE_UPLOAD=1.")
374.         if os.environ.get("ALLOW_STALE_UPLOAD") != "1":
375.             log.error(msg)
376.             raise SystemExit(1)
377.         log.warning("ALLOW_STALE_UPLOAD=1 set — proceeding despite: %s", msg)
378. 
379. 
380. def main() -> None:
381.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
382.     validate_bundle(today)
383.     body = build_zip()
384.     manifest = build_manifest(today, body)
385.     manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
386.     sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
387.     check_not_overwriting_newer(sb)
388. 
389.     # Write zip in two locations: dated archive (immutable history) + latest.
390.     for key in (f"{today}.zip", "latest.zip"):
391.         sb.storage.from_(BUCKET).upload(
392.             path=key,
393.             file=body,
394.             file_options={"content-type": "application/zip", "upsert": "true"},
395.         )
396.         log.info("uploaded %s", key)
397. 
398.     # Same for the manifest — dated archive + latest pointer.
399.     for key in (f"{today}-manifest.json", "latest-manifest.json"):
400.         sb.storage.from_(BUCKET).upload(
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/image_optimize.py.**

/Users/jiong/myprojects/news-v2/pipeline/image_optimize.py

<details>
<summary>139 lines</summary>

```
1. """Image optimize — v1-style unified WebP (1024×768, <60 KB).
2. 
3. Uses Pillow for decode+resize; libwebp's `cwebp` CLI for WebP encoding
4. (Pillow's WebP is unavailable on Python 3.14 on this machine).
5. libwebp's `dwebp` decodes source WebPs (Pillow also lacks WebP decode here).
6. """
7. from __future__ import annotations
8. 
9. import io
10. import logging
11. import shutil
12. import subprocess
13. import tempfile
14. from pathlib import Path
15. 
16. import requests
17. from PIL import Image
18. 
19. log = logging.getLogger("image")
20. 
21. MAX_DIMS = (1024, 768)
22. TARGET_BYTES = 60_000
23. DOWNLOAD_TIMEOUT = 15
24. # PATH first (Linux CI / apt install), Homebrew fallback (local macOS).
25. CWEBP = shutil.which("cwebp") or "/opt/homebrew/bin/cwebp"
26. DWEBP = shutil.which("dwebp") or "/opt/homebrew/bin/dwebp"
27. HEADERS = {
28.     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
29.                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
30. }
31. 
32. 
33. def download_image(url: str) -> bytes | None:
34.     try:
35.         r = requests.get(url, timeout=DOWNLOAD_TIMEOUT, headers=HEADERS, allow_redirects=True)
36.         if r.status_code >= 400:
37.             log.warning("image download %s -> %d", url, r.status_code)
38.             return None
39.         ct = r.headers.get("Content-Type", "").lower()
40.         if not (ct.startswith("image/") or ct == ""):
41.             log.warning("image download %s -> non-image content-type: %s", url, ct)
42.             return None
43.         return r.content
44.     except requests.RequestException as e:
45.         log.warning("image download failed %s: %s", url, e)
46.         return None
47. 
48. 
49. def fit_within(img: Image.Image, max_dims: tuple[int, int]) -> Image.Image:
50.     w, h = img.size
51.     scale = min(max_dims[0] / w, max_dims[1] / h, 1.0)
52.     if scale < 1.0:
53.         new_w = int(w * scale)
54.         new_h = int(h * scale)
55.         return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
56.     return img
57. 
58. 
59. def _decode_webp_bytes(raw: bytes) -> Image.Image:
60.     """Convert WebP bytes → PNG via dwebp → Pillow Image (PNG decode supported)."""
61.     with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as fin, \
62.          tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fout:
63.         fin.write(raw)
64.         fin.flush()
65.         subprocess.run([DWEBP, fin.name, "-o", fout.name],
66.                        check=True, capture_output=True)
67.         return Image.open(fout.name).copy()
68. 
69. 
70. def _open_image(raw: bytes) -> Image.Image:
71.     """Open any supported image format into a Pillow Image."""
72.     try:
73.         return Image.open(io.BytesIO(raw))
74.     except Exception:
75.         # Fallback: maybe WebP (Pillow can't decode) — try dwebp
76.         return _decode_webp_bytes(raw)
77. 
78. 
79. def _encode_webp_via_cli(img: Image.Image, target_bytes: int) -> tuple[bytes, int]:
80.     """Save image as temp PNG, call cwebp with -size target, return (bytes, quality_used)."""
81.     with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_in, \
82.          tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp_out:
83.         img.save(tmp_in.name, format="PNG")
84.         # cwebp -size target in bytes; -m 6 = slower, better compression
85.         result = subprocess.run(
86.             [CWEBP, "-quiet", "-m", "6", "-size", str(target_bytes),
87.              tmp_in.name, "-o", tmp_out.name],
88.             capture_output=True
89.         )
90.         if result.returncode != 0:
91.             raise RuntimeError(f"cwebp failed: {result.stderr.decode()[:200]}")
92.         out_bytes = Path(tmp_out.name).read_bytes()
93.     return out_bytes, 85   # cwebp -size picks quality internally; we log 85 as sentinel
94. 
95. 
96. def optimize_bytes(raw: bytes,
97.                    max_dims: tuple[int, int] = MAX_DIMS,
98.                    target_bytes: int = TARGET_BYTES) -> tuple[bytes, dict]:
99.     """Return (webp_bytes, info) or raise."""
100.     img = _open_image(raw)
101.     # Flatten transparency to white
102.     if img.mode in ("RGBA", "LA", "P"):
103.         rgb = Image.new("RGB", img.size, (255, 255, 255))
104.         rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
105.         img = rgb
106.     elif img.mode != "RGB":
107.         img = img.convert("RGB")
108. 
109.     img = fit_within(img, max_dims)
110.     final_w, final_h = img.size
111. 
112.     webp_bytes, quality = _encode_webp_via_cli(img, target_bytes)
113. 
114.     info = {
115.         "final_bytes": len(webp_bytes),
116.         "final_quality": quality,
117.         "dims": (final_w, final_h),
118.         "hit_target": len(webp_bytes) <= target_bytes,
119.     }
120.     return webp_bytes, info
121. 
122. 
123. def fetch_and_optimize(source_url: str, out_path: Path) -> dict | None:
124.     """Download + optimize → save to out_path. Returns info dict or None on failure."""
125.     raw = download_image(source_url)
126.     if not raw:
127.         return None
128.     try:
129.         webp_bytes, info = optimize_bytes(raw)
130.     except Exception as e:
131.         log.warning("optimize failed for %s: %s", source_url, e)
132.         return None
133.     out_path.parent.mkdir(parents=True, exist_ok=True)
134.     out_path.write_bytes(webp_bytes)
135.     info["source_url"] = source_url
136.     info["original_bytes"] = len(raw)
137.     info["local_path"] = str(out_path)
138.     return info
139.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/supabase_io.py.**

/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py (lines 1-150)

<details>
<summary>84 lines</summary>

```
1. """Supabase helpers — Storage uploads + DB inserts for the v2 redesign schema."""
2. from __future__ import annotations
3. 
4. import logging
5. import os
6. from pathlib import Path
7. from typing import Any
8. 
9. from supabase import Client, create_client
10. 
11. log = logging.getLogger("supa")
12. 
13. # Load .env once
14. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
15. for _line in (_envp.open() if _envp.exists() else []):
16.     if "=" in _line and not _line.startswith("#"):
17.         _k, _v = _line.strip().split("=", 1)
18.         os.environ[_k] = _v
19. 
20. SUPABASE_URL = os.environ.get("SUPABASE_URL")
21. SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
22. STORAGE_BUCKET = "redesign-article-images"
23. 
24. 
25. def client() -> Client:
26.     if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
27.         raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY must be set in .env")
28.     return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
29. 
30. 
31. def upload_image(local_path: Path, remote_name: str) -> str | None:
32.     """Upload a local file to the storage bucket. Returns public URL or None."""
33.     try:
34.         sb = client()
35.         data = local_path.read_bytes()
36.         sb.storage.from_(STORAGE_BUCKET).upload(
37.             remote_name,
38.             data,
39.             file_options={
40.                 "content-type": "image/webp",
41.                 "upsert": "true",           # string, not bool — Supabase quirk
42.             },
43.         )
44.         public_url = sb.storage.from_(STORAGE_BUCKET).get_public_url(remote_name)
45.         # Supabase appends "?" sometimes — strip
46.         return public_url.rstrip("?")
47.     except Exception as e:
48.         log.warning("upload_image failed %s: %s", remote_name, e)
49.         return None
50. 
51. 
52. def insert_run(row: dict[str, Any]) -> str | None:
53.     """Insert a redesign_runs row, return generated id."""
54.     try:
55.         sb = client()
56.         res = sb.table("redesign_runs").insert(row).execute()
57.         return res.data[0]["id"] if res.data else None
58.     except Exception as e:
59.         log.error("insert_run failed: %s", e)
60.         return None
61. 
62. 
63. def update_run(run_id: str, fields: dict[str, Any]) -> bool:
64.     try:
65.         sb = client()
66.         sb.table("redesign_runs").update(fields).eq("id", run_id).execute()
67.         return True
68.     except Exception as e:
69.         log.error("update_run failed: %s", e)
70.         return False
71. 
72. 
73. def insert_story(row: dict[str, Any]) -> str | None:
74.     """Insert a redesign_stories row. Upsert on (published_date, category, story_slot)."""
75.     try:
76.         sb = client()
77.         res = sb.table("redesign_stories").upsert(
78.             row, on_conflict="published_date,category,story_slot"
79.         ).execute()
80.         return res.data[0]["id"] if res.data else None
81.     except Exception as e:
82.         log.error("insert_story failed: %s", e)
83.         return None
84.
```

</details>


### 💬 Copilot

Now let me check the other source/aggregate files and look for specific issues:

### ✅ `bash`

**Find all deepseek call definitions**

$ grep -n "def deepseek.*call" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py

```
241:def deepseek_call(system: str, user: str, max_tokens: int, temperature: float = 0.2,
630:def deepseek_reasoner_call(system: str, user: str, max_tokens: int = 16000,
<exited with exit code 0>
```


### ✅ `bash`

**Check for rate-limit/429 handling**

$ grep -n "429\|rate.limit\|retry\|backoff" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py

```

<exited with exit code 1>
```


### ✅ `bash`

**Find hardcoded local paths**

$ grep -rn "/Users/jiong" /Users/jiong/myprojects/news-v2/pipeline/ 2>/dev/null | head -20

<details>
<summary>21 lines</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/news_exa_list.py:178:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output")
/Users/jiong/myprojects/news-v2/pipeline/news_exa_list.py:187:    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-exa.html")
/Users/jiong/myprojects/news-v2/pipeline/news_guardian_full.py:419:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / today
/Users/jiong/myprojects/news-v2/pipeline/news_guardian_full.py:436:    html_path = Path(f"/Users/jiong/myprojects/news-v2/website/{OUTPUT_SLUG}.html")
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:1209:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / \
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:1226:    html_path = Path(f"/Users/jiong/myprojects/news-v2/website/{output_slug}.html")
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:52:WEBSITE_DIR = Path("/Users/jiong/myprojects/news-v2/website")
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/backfill_card_summaries.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/rewrite_from_db.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/news_bbc_full.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/test_fun_feeds.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/news_exa_list.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/news_raw_list.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/augment_mined_at.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/main.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/tune_news.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/news_exa_pipeline.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/test_replacement_feeds.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/news_guardian_full.cpython-314.pyc matches
Binary file /Users/jiong/myprojects/news-v2/pipeline/__pycache__/test_thinking_enrich.cpython-314.pyc matches
<exited with exit code 0>
```

</details>


### 💬 Copilot

Now let me check the rewrite_from_db file and look at specific edge cases mentioned in the brief:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py.**

/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py

<details>
<summary>239 lines</summary>

```
1. """Resume pipeline from DB state — optionally single-category for testing.
2. 
3. Given today's redesign_stories already picked + images already in Storage,
4. this regenerates body + detail payload without re-doing Phase A/B.
5. 
6. Steps (per category):
7.   1. Query redesign_stories for today → source URLs, image paths, story metadata
8.   2. Re-fetch each source URL + extract body via cleaner
9.   3. Tri-variant rewrite (1 call per category)
10.   4. Detail enrich (1 call per category)
11.   5. Emit v1-shape payload files
12. 
13. Run all 3 categories:
14.   python -m pipeline.rewrite_from_db
15. 
16. Run one category only (for testing):
17.   python -m pipeline.rewrite_from_db News
18.   python -m pipeline.rewrite_from_db Science
19.   python -m pipeline.rewrite_from_db Fun
20. """
21. from __future__ import annotations
22. 
23. import json
24. import logging
25. import os
26. from collections import defaultdict
27. from datetime import datetime, timezone
28. from pathlib import Path
29. 
30. import requests
31. from supabase import create_client
32. 
33. from .cleaner import extract_article_from_html
34. from .full_round import card_summary
35. from .news_rss_core import detail_enrich, tri_variant_rewrite
36. 
37. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
38. log = logging.getLogger("resume")
39. 
40. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
41. for _line in (_envp.open() if _envp.exists() else []):
42.     if "=" in _line and not _line.startswith("#"):
43.         _k, _v = _line.strip().split("=", 1)
44.         os.environ[_k] = _v
45. 
46. HEADERS = {
47.     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
48.                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
49.     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
50. }
51. 
52. WEBSITE_DIR = Path("/Users/jiong/myprojects/news-v2/website")
53. 
54. 
55. def fetch_body(url: str) -> tuple[str, list[str]]:
56.     try:
57.         r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
58.         if r.status_code >= 400:
59.             return "", []
60.         ex = extract_article_from_html(url, r.text)
61.         return ex.get("cleaned_body") or "", ex.get("paragraphs") or []
62.     except Exception as e:
63.         log.warning("fetch failed %s: %s", url, e)
64.         return "", []
65. 
66. 
67. def main() -> None:
68.     import sys
69.     only_cat = sys.argv[1] if len(sys.argv) > 1 else None
70. 
71.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
72.     sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
73.     q = sb.table("redesign_stories").select("*").eq("published_date", today)
74.     if only_cat:
75.         q = q.eq("category", only_cat)
76.     res = q.order("category").order("story_slot").execute()
77.     stories = res.data
78.     log.info("Fetched %d stories from DB for %s%s", len(stories), today,
79.              f" (category={only_cat})" if only_cat else "")
80. 
81.     if not stories:
82.         log.error("No stories in DB for today — aborting")
83.         return
84. 
85.     # Group by category
86.     by_cat: dict[str, list[dict]] = defaultdict(list)
87.     for s in stories:
88.         by_cat[s["category"]].append(s)
89. 
90.     # Re-fetch bodies for each story
91.     log.info("=== REFETCH BODIES ===")
92.     for cat, group in by_cat.items():
93.         for s in group:
94.             body, paras = fetch_body(s["source_url"])
95.             s["_body"] = body
96.             s["_paragraphs"] = paras
97.             log.info("  [%s #%d] %dw · %s", cat, s["story_slot"], len(body.split()),
98.                      s["source_title"][:50] if s.get("source_title") else "")
99. 
100.     # Ensure referenced images exist on local disk (CI may have produced them
101.     # without syncing to this workstation). Pull any missing ones from the
102.     # redesign-article-images bucket — dated subfolder first, then flat root.
103.     log.info("=== SYNC IMAGES FROM SUPABASE (missing-only) ===")
104.     images_dir = WEBSITE_DIR / "article_images"
105.     images_dir.mkdir(parents=True, exist_ok=True)
106.     sb_base = os.environ["SUPABASE_URL"].rstrip("/")
107.     for cat, group in by_cat.items():
108.         for s in group:
109.             local = (s.get("primary_image_local") or "").strip()
110.             if not local:
111.                 continue
112.             fname = Path(local).name
113.             dest = images_dir / fname
114.             if dest.is_file():
115.                 continue
116.             for subpath in (f"2026-04-24/{fname}", today + "/" + fname, fname):
117.                 url = f"{sb_base}/storage/v1/object/public/redesign-article-images/{subpath}"
118.                 try:
119.                     r = requests.get(url, timeout=15)
120.                     if r.status_code == 200 and len(r.content) > 1000:
121.                         dest.write_bytes(r.content)
122.                         log.info("  pulled %s (%d bytes)", fname, len(r.content))
123.                         break
124.                 except Exception as e:
125.                     log.warning("  image fetch %s: %s", url, e)
126.             else:
127.                 log.warning("  MISSING image %s — live site will 404 until re-run", fname)
128. 
129.     # Build rewrite input shape
130.     log.info("=== REWRITE + ENRICH (2 calls per category) ===")
131.     details_dir = WEBSITE_DIR / "article_payloads"
132.     payloads_dir = WEBSITE_DIR / "payloads"
133.     details_dir.mkdir(parents=True, exist_ok=True)
134.     payloads_dir.mkdir(parents=True, exist_ok=True)
135. 
136.     per_cat_listings: dict[str, dict[str, list]] = {}
137. 
138.     for cat, group in by_cat.items():
139.         # Build articles_with_ids for tri_variant_rewrite: [(slot, art_dict)]
140.         arts = []
141.         for i, s in enumerate(group):
142.             art = {
143.                 "title": s.get("source_title") or "",
144.                 "link": s.get("source_url") or "",
145.                 "published": "",
146.                 "body": s.get("_body") or "",
147.             }
148.             arts.append((i, art))
149.         if not arts:
150.             continue
151.         log.info("  [%s] %d stories", cat, len(arts))
152. 
153.         rewrite_res = tri_variant_rewrite(arts)
154.         enrich_res = detail_enrich(rewrite_res)
155.         variants = {a["source_id"]: a for a in rewrite_res.get("articles") or []}
156.         details = enrich_res.get("details") or {}
157.         log.info("    rewrite=%d variants · detail=%d slots", len(variants), len(details))
158. 
159.         # Emit listings + details
160.         per_level: dict[str, list] = {"easy": [], "middle": [], "cn": []}
161.         for i, s in enumerate(group):
162.             var = variants.get(i) or {}
163.             easy = var.get("easy_en") or {}
164.             middle = var.get("middle_en") or {}
165.             zh = var.get("zh") or {}
166.             story_id = s.get("payload_story_id") or f"{today}-{cat.lower()}-{s['story_slot']}"
167.             img_local = s.get("primary_image_local") or ""
168.             img_url = f"/{img_local}" if img_local else ""
169. 
170.             # Preserve the original mining timestamp — DB has it as created_at.
171.             mined_at = s.get("created_at") or datetime.now(timezone.utc).isoformat()
172.             source_pub = s.get("source_published_at") or ""
173.             common_listing = {
174.                 "id": story_id,
175.                 "source": s.get("source_name", ""),
176.                 "time_ago": "",
177.                 "mined_at": mined_at,
178.                 "source_published_at": source_pub,
179.                 "image_url": img_url,
180.                 "category": cat,
181.             }
182.             per_level["easy"].append({**common_listing,
183.                 "title": easy.get("headline") or s.get("source_title") or "",
184.                 "summary": card_summary(easy),
185.             })
186.             per_level["middle"].append({**common_listing,
187.                 "title": middle.get("headline") or s.get("source_title") or "",
188.                 "summary": card_summary(middle),
189.             })
190.             per_level["cn"].append({**common_listing,
191.                 "title": zh.get("headline") or "",
192.                 "summary": zh.get("summary") or "",
193.             })
194. 
195.             # Per-story detail files (easy + middle; no cn detail)
196.             story_dir = details_dir / f"payload_{story_id}"
197.             story_dir.mkdir(parents=True, exist_ok=True)
198.             for lvl_key, var_obj in (("easy", easy), ("middle", middle)):
199.                 slot_key = f"{i}_{lvl_key}"
200.                 det = details.get(slot_key) or {}
201.                 bg = det.get("background_read") or []
202.                 if isinstance(bg, str):
203.                     bg = [bg]
204.                 detail = {
205.                     "title": var_obj.get("headline") or s.get("source_title") or "",
206.                     "summary": var_obj.get("body") or "",
207.                     "why_it_matters": det.get("why_it_matters", ""),
208.                     "image_url": img_url,
209.                     "keywords": det.get("keywords") or [],
210.                     "questions": det.get("questions") or [],
211.                     "background_read": bg,
212.                     "Article_Structure": det.get("Article_Structure") or [],
213.                     "perspectives": det.get("perspectives") or [],
214.                     "mined_at": mined_at,
215.                     "source_published_at": source_pub,
216.                     "source_name": s.get("source_name", ""),
217.                     "source_url": s.get("source_url", ""),
218.                 }
219.                 (story_dir / f"{lvl_key}.json").write_text(
220.                     json.dumps(detail, ensure_ascii=False, indent=2)
221.                 )
222. 
223.         per_cat_listings[cat] = per_level
224. 
225.     # Write listing files
226.     log.info("=== EMIT LISTINGS ===")
227.     for cat, per_level in per_cat_listings.items():
228.         cat_slug = cat.lower()
229.         for lvl_key, items in per_level.items():
230.             out = payloads_dir / f"articles_{cat_slug}_{lvl_key}.json"
231.             out.write_text(json.dumps({"articles": items}, ensure_ascii=False, indent=2))
232.             log.info("  %s (%d items)", out.name, len(items))
233. 
234.     log.info("DONE. View: http://localhost:18100/")
235. 
236. 
237. if __name__ == "__main__":
238.     main()
239.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_sources.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_sources.py (lines 1-80)

<details>
<summary>80 lines</summary>

```
1. """News source registry.
2. 
3. Shaped to mirror the future Supabase table `redesign_news_sources`.
4. For now hardcoded here; migrate to Supabase in Phase 3 per
5. docs/superpowers/plans/2026-04-23-news-sources-supabase-migration.md
6. """
7. from __future__ import annotations
8. 
9. from dataclasses import dataclass
10. 
11. 
12. @dataclass
13. class NewsSource:
14.     id: int
15.     name: str
16.     rss_url: str
17.     flow: str                 # "full" | "light"
18.     max_to_vet: int
19.     min_body_words: int
20.     priority: int             # lower = primary
21.     enabled: bool
22.     is_backup: bool
23.     notes: str = ""
24. 
25.     @property
26.     def is_light(self) -> bool:
27.         return self.flow == "light"
28. 
29. 
30. SOURCES: list[NewsSource] = [
31.     NewsSource(
32.         id=2, name="PBS NewsHour",
33.         rss_url="https://www.pbs.org/newshour/feeds/rss/headlines",
34.         flow="full", max_to_vet=6, min_body_words=500,
35.         priority=1, enabled=True, is_backup=False,
36.         notes="cap at 6 to vetter",
37.     ),
38.     NewsSource(
39.         id=3, name="NPR World",
40.         rss_url="https://feeds.npr.org/1003/rss.xml",
41.         flow="light", max_to_vet=10, min_body_words=500,
42.         priority=2, enabled=True, is_backup=False,
43.     ),
44.     NewsSource(
45.         id=1, name="Al Jazeera",
46.         rss_url="https://www.aljazeera.com/xml/rss/all.xml",
47.         flow="full", max_to_vet=10, min_body_words=500,
48.         priority=3, enabled=True, is_backup=False,
49.     ),
50.     # Backups — Guardian World dropped per user (logo overlay on images).
51.     NewsSource(
52.         id=5, name="BBC News",
53.         rss_url="http://feeds.bbci.co.uk/news/rss.xml",
54.         flow="light", max_to_vet=25, min_body_words=500,
55.         priority=4, enabled=False, is_backup=True,
56.     ),
57.     NewsSource(
58.         id=6, name="ScienceDaily Top Technology",
59.         rss_url="https://www.sciencedaily.com/rss/top/technology.xml",
60.         flow="full", max_to_vet=25, min_body_words=500,
61.         priority=5, enabled=False, is_backup=True,
62.         notes="SD tech topic — news backup",
63.     ),
64.     NewsSource(
65.         id=7, name="ScienceDaily Strange & Offbeat",
66.         rss_url="https://www.sciencedaily.com/rss/strange_offbeat.xml",
67.         flow="full", max_to_vet=25, min_body_words=500,
68.         priority=6, enabled=False, is_backup=True,
69.         notes="SD offbeat — kid-wow backup",
70.     ),
71.     NewsSource(
72.         id=8, name="ScienceDaily Most Popular",
73.         rss_url="https://www.sciencedaily.com/rss/most_popular.xml",
74.         flow="full", max_to_vet=25, min_body_words=500,
75.         priority=7, enabled=False, is_backup=True,
76.         notes="SD most-popular — generic backup",
77.     ),
78. ]
79. 
80.
```

</details>


### ✅ `bash`

**Look for pick_winners_with_dedup edge cases**

$ grep -n "exhausted\|break\|len(candidates)" /Users/jiong/myprojects/news-v2/pipeline/full_round.py | head -20

<details>
<summary>11 lines</summary>

```
137:    exhausted: set[str] = set()
147:            if name in exhausted:
153:            break
163:            break
169:            break
177:            log.warning("  [%s] exhausted all candidates — skipping", drop_name)
178:            exhausted.add(drop_name)
182:        if name in exhausted:
291:            break
295:            break
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check pack_and_upload error handling**

$ grep -n "200\|201\|error\|except\|timeout" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py | head -30

<details>
<summary>21 lines</summary>

```
103:            except Exception as e:  # noqa: BLE001
104:                errs.append(f"{p.name}: parse error {e}")
119:            except Exception:
141:            except Exception as e:  # noqa: BLE001
142:                errs.append(f"{story_id}/{lvl}: parse error {e}")
160:            except Exception:
167:        log.error("Bundle validation FAILED — refusing to pack/upload:")
169:            log.error("  · %s", e)
203:        except Exception:
260:    except Exception:
294:        except Exception as e:  # noqa: BLE001
315:            except ValueError:
328:        except Exception as e:  # noqa: BLE001
350:        except Exception:
362:    except Exception:
375:            log.error(msg)
414:    except Exception as e:  # noqa: BLE001
424:    except Exception:
431:    except Exception as e:  # noqa: BLE001
437:    except Exception as e:  # noqa: BLE001
<exited with exit code 0>
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py (lines 400-420)

<details>
<summary>21 lines</summary>

```
400.         sb.storage.from_(BUCKET).upload(
401.             path=key,
402.             file=manifest_bytes,
403.             file_options={"content-type": "application/json", "upsert": "true"},
404.         )
405.         log.info("uploaded %s", key)
406. 
407.     log.info("manifest: version=%s · zip_bytes=%d · zip_sha256=%s · stories=%d",
408.              manifest["version"], manifest["zip_bytes"],
409.              manifest["zip_sha256"][:12], manifest["story_count"])
410. 
411.     # Flat per-day files — the UI fetches these when user picks a past date.
412.     try:
413.         upload_dated_flat_files(sb, today)
414.     except Exception as e:  # noqa: BLE001
415.         log.warning("dated-flat upload failed (non-fatal): %s", e)
416. 
417.     # Read existing archive-index, backfill any dated zip that doesn't yet
418.     # have a flat dir, then update archive-index with both backfilled +
419.     # today's date.
420.     try:
```

</details>


### ✅ `bash`

**Check for secret/key loading**

$ grep -n "os.environ\|\.env\|DEEPSEEK" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py | head -10

<details>
<summary>10 lines</summary>

```
35:# Load .env once on module import
36:_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
40:        os.environ[_k] = _v
42:DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
43:DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
248:            r = requests.post(DEEPSEEK_ENDPOINT,
256:                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
639:                DEEPSEEK_ENDPOINT,
646:                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
<exited with exit code 0>
```

</details>


### 💬 Copilot

Now let me check the news_rss_core.py around line 700 to see the detail_enrich edge case more clearly:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 681-716)

<details>
<summary>36 lines</summary>

```
681. def detail_enrich(rewrite_result: dict) -> dict:
682.     """Detail enrichment with two-stage fallback:
683.       1. Single 6-slot call (fast, cheaper).
684.       2. If that fails JSON parse even after retries, split into TWO 3-slot
685.          calls (easy-only + middle-only). Smaller prompts → higher chance of
686.          well-formed JSON per call, and if one half still fails the other is
687.          salvageable.
688.     Post-filter hallucinated keywords at the end."""
689.     try:
690.         res = deepseek_reasoner_call(DETAIL_ENRICH_PROMPT,
691.                                      detail_enrich_input(rewrite_result),
692.                                      max_tokens=16000)
693.         details = res.get("details") or {}
694.         # Accept even partial success here (all 6 slots expected; caller checks).
695.     except RuntimeError as e:
696.         log.warning("detail_enrich 6-slot call failed after retries (%s) — "
697.                     "falling back to split 3-slot batches", e)
698.         details = {}
699.         for level in ("easy", "middle"):
700.             try:
701.                 res = deepseek_reasoner_call(
702.                     DETAIL_ENRICH_PROMPT,
703.                     _detail_enrich_input_single_level(rewrite_result, level),
704.                     max_tokens=12000,
705.                 )
706.                 for k, v in (res.get("details") or {}).items():
707.                     details[k] = v
708.                 log.info("split-batch %s: %d slots OK", level,
709.                          len(res.get("details") or {}))
710.             except RuntimeError as e2:
711.                 log.error("split-batch %s failed: %s", level, e2)
712.                 # Continue — the other level may still succeed.
713. 
714.     filter_keywords(details, rewrite_result)
715.     return {"details": details}
716.
```

</details>


### ✅ `bash`

**Check HTTP error handling and rate limit detection**

$ grep -n "requests.post\|r.raise_for_status\|status_code\|429\|HTTPError" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py

<details>
<summary>8 lines</summary>

```
127:        if r.status_code >= 400:
248:            r = requests.post(DEEPSEEK_ENDPOINT,
258:            r.raise_for_status()
263:        except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
638:            r = requests.post(
649:            r.raise_for_status()
654:        except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check card_summary enforcement**

$ grep -n "card_summary" /Users/jiong/myprojects/news-v2/pipeline/full_round.py

<details>
<summary>6 lines</summary>

```
272:def card_summary(variant: dict, max_words: int = 120) -> str:
273:    """Short blurb for the home-page card. Prefer `card_summary` from the
276:    cs = (variant.get("card_summary") or "").strip()
347:                "summary": card_summary(easy),
351:                "summary": card_summary(middle),
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check for 429 specific handling**

$ grep -n "if r.status_code\|429\|rate.limit" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py

```
127:        if r.status_code >= 400:
<exited with exit code 0>
```


### ✅ `bash`

**Check file size**

$ wc -l /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py

```
1232 /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py
<exited with exit code 0>
```


### ✅ `bash`

**Find pick_winners_with_dedup**

$ grep -n "def pick_winners_with_dedup" /Users/jiong/myprojects/news-v2/pipeline/full_round.py

```
131:def pick_winners_with_dedup(by_source: dict[str, dict]) -> list[dict]:
<exited with exit code 0>
```


### 💬 Copilot

Now let me look more carefully at the deepseek retry logic to check for 429 handling:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 241-271)

<details>
<summary>31 lines</summary>

````
241. def deepseek_call(system: str, user: str, max_tokens: int, temperature: float = 0.2,
242.                   max_attempts: int = 3) -> dict:
243.     """Call deepseek-chat with JSON output. Retries on JSON parse failure
244.     (model occasionally emits malformed JSON) and transient HTTP errors."""
245.     last_err: Exception | None = None
246.     for attempt in range(1, max_attempts + 1):
247.         try:
248.             r = requests.post(DEEPSEEK_ENDPOINT,
249.                 json={
250.                     "model": "deepseek-chat",
251.                     "messages": [{"role": "system", "content": system},
252.                                  {"role": "user", "content": user}],
253.                     "temperature": temperature,
254.                     "max_tokens": max_tokens,
255.                 },
256.                 headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
257.                 timeout=120)
258.             r.raise_for_status()
259.             content = r.json()["choices"][0]["message"]["content"]
260.             content = re.sub(r"^```json\s*", "", content.strip())
261.             content = re.sub(r"\s*```\s*$", "", content)
262.             return json.loads(content)
263.         except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
264.                 requests.Timeout) as e:
265.             last_err = e
266.             log.warning("chat attempt %d/%d failed: %s",
267.                         attempt, max_attempts, str(e)[:200])
268.             if attempt < max_attempts:
269.                 time.sleep(2 * attempt)
270.     raise RuntimeError(f"deepseek_call exhausted {max_attempts} attempts") from last_err
271.
````

</details>


### ✅ `bash`

**Review pick_winners_with_dedup logic**

$ grep -A 20 "def pick_winners_with_dedup" /Users/jiong/myprojects/news-v2/pipeline/full_round.py | head -30

<details>
<summary>20 lines</summary>

```
def pick_winners_with_dedup(by_source: dict[str, dict]) -> list[dict]:
    """Pick the highest-ranked surviving candidate per source, then
    cross-source dedup. When a pair of today's picks duplicates, drop the
    weaker source's current pick and promote its NEXT candidate (no extra
    DeepSeek-and-RSS round-trip — we already mined up to 4 per source)."""
    ptrs: dict[str, int] = {name: 0 for name in by_source}
    exhausted: set[str] = set()

    def current_for(name: str) -> dict | None:
        idx = ptrs.get(name, 0)
        cands = by_source[name].get("candidates") or []
        return cands[idx] if idx < len(cands) else None

    for _round in range(8):
        picks: list[tuple[str, dict]] = []
        for name in by_source:
            if name in exhausted:
                continue
            c = current_for(name)
            if c:
                picks.append((name, c))
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check exception handling in pack_and_upload**

$ grep -n "class.*Exception\|Exception as\|except" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py | head -20

<details>
<summary>16 lines</summary>

```
103:            except Exception as e:  # noqa: BLE001
119:            except Exception:
141:            except Exception as e:  # noqa: BLE001
160:            except Exception:
203:        except Exception:
260:    except Exception:
294:        except Exception as e:  # noqa: BLE001
315:            except ValueError:
328:        except Exception as e:  # noqa: BLE001
350:        except Exception:
362:    except Exception:
414:    except Exception as e:  # noqa: BLE001
424:    except Exception:
431:    except Exception as e:  # noqa: BLE001
437:    except Exception as e:  # noqa: BLE001
<exited with exit code 0>
```

</details>


### 💬 Copilot

Let me check for the CI-only guard mentioned in the brief:

### ✅ `bash`

**Check for CI guards**

$ grep -n "GITHUB_SHA\|CI\|github\|cicd" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py

```
208:        "git_sha": os.environ.get("GITHUB_SHA") or "",
358:    local `pack_and_upload` from silently replacing CI-generated output."""
<exited with exit code 0>
```


### ✅ `bash`

**Check exit conditions**

$ grep -rn "raise SystemExit\|sys.exit" /Users/jiong/myprojects/news-v2/pipeline/*.py | grep -v test | head -20

<details>
<summary>6 lines</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/full_round.py:514:        raise SystemExit(1)
/Users/jiong/myprojects/news-v2/pipeline/main.py:39:        raise SystemExit(f"Missing required env vars: {missing}")
/Users/jiong/myprojects/news-v2/pipeline/main.py:593:    sys.exit(main())
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:170:        raise SystemExit(1)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:376:            raise SystemExit(1)
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check detail_enrich error handling**

$ grep -n "detail_enrich" /Users/jiong/myprojects/news-v2/pipeline/full_round.py

```
17:from .news_rss_core import (check_duplicates, detail_enrich,
253:    enrich = detail_enrich(rewrite_res)
258:            f"detail_enrich returned {len(details_by_slot)} slots, "
<exited with exit code 0>
```


### 💬 Copilot

Now let me check the full_round.py context around rewrite_for_category to see the error handling:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 491-535)

<details>
<summary>45 lines</summary>

```
491.     log.info("=== REWRITE (tri-variant + detail enrich, 2 calls per category) ===")
492.     variants_by_cat: dict[str, dict] = {}
493.     details_by_cat: dict[str, dict] = {}
494.     failures: list[str] = []
495.     for cat, ws in stories_by_cat.items():
496.         try:
497.             v, d = rewrite_for_category(ws)
498.             variants_by_cat[cat] = v
499.             details_by_cat[cat] = d
500.             log.info("  [%s] rewrite: %d variants · detail slots: %d",
501.                      cat, len(v), len(d))
502.         except Exception as e:  # noqa: BLE001
503.             log.error("  [%s] rewrite/enrich FAILED: %s", cat, e)
504.             failures.append(f"{cat}: {e}")
505. 
506.     if failures:
507.         # Mark run as failed (if DB tracking on), don't upload a partial zip.
508.         msg = f"{len(failures)} category failures: " + " | ".join(failures)
509.         if run_id:
510.             update_run(run_id, {"status": "failed",
511.                                 "finished_at": datetime.now(timezone.utc).isoformat(),
512.                                 "notes": msg})
513.         log.error("Aborting — %s", msg)
514.         raise SystemExit(1)
515. 
516.     log.info("=== EMIT v1-shape payload files ===")
517.     emit_v1_shape(stories_by_cat, variants_by_cat, details_by_cat, today, website_dir)
518. 
519.     log.info("=== PERSIST TO SUPABASE ===")
520.     count = 0
521.     if run_id:
522.         count = persist_to_supabase(stories_by_cat, variants_by_cat, today, run_id)
523.         update_run(run_id, {"status": "completed",
524.                             "finished_at": datetime.now(timezone.utc).isoformat(),
525.                             "notes": f"stories persisted: {count}"})
526. 
527.     log.info("=== PACK + UPLOAD ZIP (deploy trigger) ===")
528.     try:
529.         from .pack_and_upload import main as _pack_upload
530.         _pack_upload()
531.     except Exception as e:  # noqa: BLE001
532.         log.warning("pack_and_upload failed — site will lag until next run: %s", e)
533. 
534.     log.info("=== DONE ===")
535.     total_stories = sum(len(ws) for ws in stories_by_cat.values())
```

</details>


### ✅ `bash`

**Check for quota/storage limits**

$ grep -n "timeout\|upload.*exception\|Supabase.*quota\|storage.*full" /Users/jiong/myprojects/news-v2/pipeline/supabase_io.py

```

<exited with exit code 1>
```


### ✅ `bash`

**Check upload safety mechanisms**

$ grep -n "upload_dated_flat_files\|check_not_overwriting_newer" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py

<details>
<summary>6 lines</summary>

```
221:def upload_dated_flat_files(sb, date_str: str, bundle: bytes | None = None) -> int:
292:            upload_dated_flat_files(sb, d, bundle=body)
355:def check_not_overwriting_newer(sb) -> None:
387:    check_not_overwriting_newer(sb)
413:        upload_dated_flat_files(sb, today)
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check for partial failure conditions**

$ grep -n "partial\|exhausted\|expected" /Users/jiong/myprojects/news-v2/pipeline/full_round.py | head -20

<details>
<summary>10 lines</summary>

```
137:    exhausted: set[str] = set()
147:            if name in exhausted:
177:            log.warning("  [%s] exhausted all candidates — skipping", drop_name)
178:            exhausted.add(drop_name)
182:        if name in exhausted:
255:    expected_slots = len(stories) * 2  # easy + middle per story
256:    if len(details_by_slot) < expected_slots:
259:            f"expected {expected_slots}"
507:        # Mark run as failed (if DB tracking on), don't upload a partial zip.
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check variant validation**

$ grep -n "if len(variants)" /Users/jiong/myprojects/news-v2/pipeline/full_round.py

```
247:    if len(variants) < len(stories):
<exited with exit code 0>
```


### ✅ `bash`

**Check CI workflow**

$ head -50 /Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml 2>/dev/null || echo "not found"

<details>
<summary>43 lines</summary>

```
name: Daily pipeline

on:
  workflow_dispatch: {}
  schedule:
    # 06:20 UTC daily ≈ 23:20 PT / 02:20 ET. Pick any time; kidsnews-v2 cron
    # then pulls latest.zip on its next `:15` of an even hour (≤2h lag).
    - cron: "20 6 * * *"

permissions:
  contents: read

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install libwebp (cwebp / dwebp)
        run: |
          sudo apt-get update -q
          sudo apt-get install -y -q webp

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install Python deps
        run: |
          python -m pip install -U pip
          pip install -r requirements.txt

      - name: Write .env for modules that read it directly
        run: |
          umask 077
          cat > .env <<EOF
          DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
          SUPABASE_URL=${SUPABASE_URL}
          SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
          EOF

      - name: Run full_round
<exited with exit code 0>
```

</details>


### 💬 Copilot

Let me check the exact flow around detail_enrich fallback and check the validation more carefully:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 238-262)

<details>
<summary>25 lines</summary>

```
238. def rewrite_for_category(stories: list[dict]) -> tuple[dict[int, dict], dict]:
239.     """Tri-variant rewrite, then detail enrichment. Returns
240.     (variants_by_src_id, details_by_slot). Raises if either step ultimately
241.     fails — callers decide whether that's fatal for the whole run."""
242.     if not stories:
243.         return {}, {}
244.     articles_for_rewrite = [(i, s["winner"]) for i, s in enumerate(stories)]
245.     rewrite_res = tri_variant_rewrite(articles_for_rewrite)
246.     variants = {a.get("source_id"): a for a in rewrite_res.get("articles") or []}
247.     if len(variants) < len(stories):
248.         raise RuntimeError(
249.             f"rewrite returned {len(variants)} variants for {len(stories)} stories"
250.         )
251. 
252.     # Phase D — detail enrichment (1 extra call per category)
253.     enrich = detail_enrich(rewrite_res)
254.     details_by_slot = enrich.get("details") or {}
255.     expected_slots = len(stories) * 2  # easy + middle per story
256.     if len(details_by_slot) < expected_slots:
257.         raise RuntimeError(
258.             f"detail_enrich returned {len(details_by_slot)} slots, "
259.             f"expected {expected_slots}"
260.         )
261.     return variants, details_by_slot
262.
```

</details>


### ✅ `bash`

**Check brief mentions of partial failures**

$ grep -n "partial\|incomplete\|fallback" /Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md

<details>
<summary>6 lines</summary>

```
70:  mining + image ops). Used for debug / partial-category re-runs.
111:   - `detail_enrich` split-batch fallback — what if BOTH easy and
112:     middle sub-calls fail? Currently continues with partial details;
127:   - Pipeline partial failure (category rewrite succeeds but enrich
128:     fails): is there a state where a partial bundle gets uploaded?
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check detail_enrich fallback continue logic**

$ grep -n "raise\|return\|continue" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py | grep -A 2 -B 2 "710\|711"

```

<exited with exit code 1>
```


### 💬 Copilot

Based on my thorough review of the pipeline code against the brief's key concerns, here are my findings:

## Code Review Findings — Pipeline Domain

---

### **Critical Findings**

**1. CRITICAL: detail_enrich fallback returns partial data without validation**
- **File:line:** `pipeline/news_rss_core.py:681-715`
- **What:** `detail_enrich()` can return incomplete details dict if split-batch calls fail. Falls back gracefully but returns whatever succeeded, violating the contract.
- **Why it matters:** The brief flagged this edge case: "if BOTH easy and middle sub-calls fail? Currently continues with partial details." Then `full_round.py:256` checks `len(details_by_slot) \< expected_slots` and raises. However, if one level (easy) succeeds and middle fails, you get 3 out of 6 slots. This passes validation if a category has only 1.5 stories (edge case but possible after dedup), creating partial detail payloads that emit_v1_shape writes to disk. Later `pack_and_upload.py:135-140` checks `Article_Structure` count but doesn't validate it's populated for ALL slots—only that ≥3 exist, which could be satisfied by just easy_0, easy_1, easy_2 if middle all failed.
- **Suggested fix:** Change line 256 to require EXACT count (not `\<`), and add retry-on-partial fallback: if first batch returns partial, catch it and trigger split-batch immediately rather than only on RuntimeError.

**2. CRITICAL: pick_winners_with_dedup can exhaust all sources and return empty list**
- **File:line:** `pipeline/full_round.py:131-191`
- **What:** The loop can mark all sources as exhausted (line 178) if every dedup round promotes candidates from the same sources until all exhaust. Then line 180-191 filters by `if name in exhausted` and returns 0 picks.
- **Why it matters:** If 3 sources each have 4 candidates and all 9 candidates are pairwise dupes, the loop tries to promote but exhausts all sources, resulting in `[]` return. Then `emit_v1_shape` writes 0 articles and `pack_and_upload.validate_bundle()` sees empty listings (line 96 checks `len(arts) \< 2`), which exits with error. But this is silent in logs—no clear "all candidates exhausted" message.
- **Suggested fix:** Add explicit check after pick loop (line 180-191): if final list is empty, log.error and raise or return sentinel. Also, the loop logic at line 163 breaks if `verdict != DUP_FOUND` but never exhausts a source; only promotion at line 176 does. A source can exit the loop with unconsumed candidates if dedup suddenly returns "OK"—those alternates are lost. Document this or force an exit on first OK to maximize candidates used.

**3. CRITICAL: Hardcoded local paths in pipeline modules bypass CI guards**
- **File:line:** `pipeline/rewrite_from_db.py:52`, `pipeline/news_rss_core.py:1209`, `pipeline/news_guardian_full.py:419`, etc.
- **What:** `WEBSITE_DIR = Path("/Users/jiong/myprojects/news-v2/website")` is hardcoded. These are used by one-shot debug scripts, but if CI ever calls these (e.g., via rewrite_from_db), it writes to `/Users/jiong/...` on CI runners, fails, and silently doesn't update the live site.
- **Why it matters:** The brief flagged "Hardcoded `/Users/jiong/...` paths were a CI bug source today." The guard `check_not_overwriting_newer()` doesn't catch this—it only checks manifest timestamps, not whether files were actually written to the correct location.
- **Suggested fix:** Replace with `Path(__file__).resolve().parent.parent / "website"` in all non-test files. Add a fixture that logs `WEBSITE_DIR` at startup so CI logs show the path for debugging.

---

### **Important Findings**

**4. IMPORTANT: deepseek_call doesn't distinguish 429 (rate limit) from other errors**
- **File:line:** `pipeline/news_rss_core.py:241-270`, `630-661`
- **What:** Both `deepseek_call` and `deepseek_reasoner_call` catch `requests.HTTPError` broadly (line 263, 654). A 429 (rate limit) is wrapped as HTTPError but treated the same as any 4xx/5xx. Retry logic uses fixed `time.sleep(2 * attempt)` backoff, not exponential or rate-limit-aware.
- **Why it matters:** Rate limits should trigger longer backoff or fast-fail to preserve quota for later steps. Current logic sleeps 2s, 4s, then fails—if quota is truly exhausted, 4s won't help. The brief asked "does it handle rate-limit (429) differently from JSON parse errors?"
- **Suggested fix:** Extract status code from HTTPError, check `r.status_code == 429`, and apply exponential backoff (e.g., 10s, 30s, 90s) or fail loudly with a different exception type. For non-429 errors, retry faster.

**5. IMPORTANT: filter_past_duplicates threshold of 0.80 may drop unrelated stories**
- **File:line:** `pipeline/full_round.py:90-128`
- **What:** Title similarity ≥0.80 → drop. The brief notes: "titles can differ significantly while being the same story; or be identical but different stories." At 0.80, "North Korea Missiles Test" ≈ "North Korea Test Missiles" (high sim, same story ✓) but also "Apple Event Announced" ≈ "Apple Pie Recipe Announced" (high sim, different ✗).
- **Why it matters:** False positives (dropping a real new story) are worse than false negatives (running a duplicate, which cross-source dedup may catch). No data on false-positive rate with 0.80 threshold.
- **Suggested fix:** Benchmark threshold against historical runs. Consider lowering to 0.75 and/or adding a secondary check (e.g., same source URL domain, or DeepSeek semantic similarity, not just string similarity).

**6. IMPORTANT: card_summary prompt enforceability unclear**
- **File:line:** `pipeline/news_rss_core.py:416-420`, `full_round.py:272-296`
- **What:** Rewriter prompt says "card_summary: 6-9 sentences, MAX 120 words" (line 419). But the model may ignore this. Fallback logic at `full_round.py:278-281` strips to 120 words post-hoc. However, if the rewriter returns 200-word card_summary and the fallback truncates to 120, we lose semantic coherence.
- **Why it matters:** The brief flagged "is the prompt actually enforceable? (We also post-trim with a word cap.)" The post-trim is reactive—if the model emits 3 huge paragraphs, word-capping mid-sentence is lossy.
- **Suggested fix:** Add a harder constraint: "Return the card_summary field as a single paragraph, MAX 120 words. No newlines. Cut off mid-word if needed." Or, post-processing should trim to last complete sentence before word limit, not arbitrary truncation.

---

### **Important (Continued)**

**7. IMPORTANT: partial upload state if upload fails mid-flight**
- **File:line:** `pipeline/pack_and_upload.py:221-252`, `390-415`
- **What:** `upload_dated_flat_files()` uploads files one by one (line 234, 245). If the loop fails on file 47/100, the bucket has 47 files under the dated prefix. Then `upload_archive_index()` at line 255 adds the date to the index anyway. UI sees the date in archive-index but files are incomplete.
- **Why it matters:** The brief asked "is there a state where a partial bundle gets uploaded?" The validation (line 74-172) checks for completeness on-disk BEFORE packing, but during upload to Supabase, a transient network error leaves the bucket in an inconsistent state.
- **Suggested fix:** Wrap the loop in a try-catch. On exception, fetch the list of files actually uploaded, remove them (sb.storage.remove()), then re-raise. Only update archive-index after successful completion.

**8. IMPORTANT: check_not_overwriting_newer is not a sufficient CI-only guard**
- **File:line:** `pipeline/pack_and_upload.py:355-377`
- **What:** The guard compares `local_freshest_mined_at()` vs `remote_freshest_mined_at()`. If someone runs `pack_and_upload` locally AFTER the CI run finishes (with same day's date), local stories have same or newer mined_at, so the check passes. The env var `ALLOW_STALE_UPLOAD=1` is a backdoor.
- **Why it matters:** The brief asked "any evasion paths?" Yes—local run on same day, or set the env var. The intent is "never overwrite CI from local," but the implementation only checks timestamps, not origin.
- **Suggested fix:** Check `GITHUB_ACTIONS` env var or `GITHUB_RUN_ID`. Only allow pack_and_upload from CI, or require a token signed with a secret. Alternatively, add a "locked" flag in the manifest: if remote is locked (CI-produced), local run should fail unless `FORCE_UNLOCK=1` with a hard-coded safe code.

---

### **Minor Findings**

**9. MINOR: Exception handling swallows critical context in pack_and_upload**
- **File:line:** `pipeline/pack_and_upload.py:412-415`
- **What:** `upload_dated_flat_files` fails (network timeout, quota exceeded, etc.) → logged as "non-fatal" warning. The run completes, zip is uploaded, but users can't fetch past dates because the flat files never landed.
- **Why it matters:** If Supabase quota is hit during flat-file upload, the site works for today but breaks for archive access. No alerting.
- **Suggested fix:** Add post-upload validation: query the bucket to confirm at least N files landed under the date prefix. If count \< expected, fail the whole run and don't mark as complete.

**10. MINOR: .env module-level import in multiple files risks exposed secrets**
- **File:line:** `pipeline/news_rss_core.py:35-40`, `pipeline/supabase_io.py:13-18`, `pipeline/pack_and_upload.py:31-35`, `pipeline/rewrite_from_db.py:40-44`
- **What:** Each module loads .env on import. If a secrets logger or tracer captures module init, the DEEPSEEK_KEY and SUPABASE_SERVICE_KEY are visible. GitHub Actions secrets are injected into env at job start, so the .env file is a fallback. But the pattern is repeated 4+ times, and if a downstream library logs module __dict__, secrets leak.
- **Why it matters:** The brief asked "any path where the key could end up in a log?" Standard logging config doesn't filter env var leaks. The .env fallback is sensible for local dev, but the module-level pattern is risky.
- **Suggested fix:** Load secrets once in a single module (e.g., `config.py`), then import from there. Use logging filters to redact known secret keys from logs. Add a guard: if running in CI and .env exists, error (fail the run) so the git-push trap catches mistakes.

---

## Summary

The pipeline has solid fail-safes (validate_bundle, check_not_overwriting_newer, detail_enrich fallback) but three structural gaps stand out:

1. **detail_enrich partial fallback** accepts incomplete details without downstream visibility.
2. **pick_winners_with_dedup** can silently exhaust all candidates and return zero stories.
3. **Hardcoded local paths** in debug scripts can compromise CI runs if accidentally called in production workflows.

Additionally, **rate-limit handling is conflated with transient errors**, and **upload-time failures can leave the bucket in an inconsistent state**.

**Top 3 to fix:**
1. **detail_enrich:** Require exact match of expected slots, not `\<`. Trigger split-batch fallback immediately on partial results, not just RuntimeError.
2. **pick_winners_with_dedup:** Add explicit exhaustion check + log + raise at end. Force at least 1 OK round to break and finalize picks.
3. **Hardcoded paths:** Replace `/Users/jiong/...` with dynamic `Path(__file__).parent.parent / "website"` in all non-test modules. Log resolved path on startup.


---

<sub>⏱️ 51s</sub>

### 📦 task (Completed)

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/docs/reviews.**

/Users/jiong/myprojects/news-v2/docs/reviews

```
2026-04-24-codex-review.md
2026-04-24-copilot-review-raw.md
2026-04-24-copilot-review.md
2026-04-24-review-brief.md
```


### 💬 Copilot

Let me read the review brief and then examine the frontend files:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md.**

/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md

<details>
<summary>178 lines</summary>

````
1. # Code review brief — News Oh, Ye! v2 (news.6ray.com)
2. 
3. ## Project context
4. 
5. **Goal.** Bilingual kids news site (English easy / middle + 中文 summary).
6. Fully autonomous pipeline runs daily on GitHub Actions, produces 9 stories
7. (3 News / 3 Science / 3 Fun) plus per-story detail enrichment, ships to
8. Supabase Storage, and auto-deploys to Vercel at news.6ray.com.
9. 
10. **Three-repo architecture.**
11. - `news-v2` (this repo): Python pipeline + React prototype source. Runs the
12.   daily-pipeline workflow. Goes private eventually.
13. - `kidsnews-v2` (separate repo): tiny deploy shell. A sync workflow pulls
14.   `latest.zip` from Supabase Storage, unzips into `site/`, commits, Vercel
15.   auto-deploys.
16. - `kidsnews` (legacy, v1 reference at kidsnews.6ray.com): not relevant.
17. 
18. ## Flow
19. 
20. ```
21. GitHub Action (news-v2 · daily 06:20 UTC)
22.   └── python -m pipeline.full_round
23.         ├── RSS mine (3 sources × 3 categories, per-weekday rotation)
24.         ├── Phase A per source: vet 10 briefs, return top-4 verified candidates
25.         ├── past-dedup (3-day lookback, title ≥80% similar → drop)
26.         ├── cross-source dedup (promote next candidate on dup)
27.         ├── tri-variant rewrite (easy_en / middle_en / zh) via DeepSeek chat
28.         ├── detail enrich (keywords / questions / background / mind-tree /
29.         │     why_it_matters / perspectives) via DeepSeek reasoner
30.         │     — retries 3× on JSON parse; falls back to split 3-slot batches
31.         ├── image optimize (Pillow decode + libwebp cwebp/dwebp CLI)
32.         │     → Supabase Storage redesign-article-images bucket
33.         ├── persist runs + stories to Supabase tables
34.         └── pack_and_upload
35.               ├── validate_bundle (9 listings · 18 details · all images)
36.               ├── check_not_overwriting_newer (aborts if remote is fresher)
37.               ├── zip website/ → Supabase redesign-daily-content:latest.zip
38.               │     + <YYYY-MM-DD>.zip
39.               ├── latest-manifest.json + <YYYY-MM-DD>-manifest.json
40.               ├── per-day flat files under <YYYY-MM-DD>/ prefix (new)
41.               ├── backfill_missing_archive_dirs (extracts past zips if the
42.               │     flat dir is missing — runs only once per past date)
43.               ├── update archive-index.json (list of available dates)
44.               └── retention sweep (keep 30 days)
45. 
46. GitHub Action (kidsnews-v2 · cron :15 every 2h, or dispatch on pipeline success)
47.   └── downloads latest.zip → unzips into site/ → commits if changed → push
48. 
49. Vercel (on push to kidsnews-v2)
50.   └── deploys site/ to news.6ray.com
51. ```
52. 
53. ## Key files (by importance)
54. 
55. ### Pipeline (Python 3.11)
56. - `pipeline/full_round.py` — orchestrator. Aggregate → dedup → images →
57.   rewrite+enrich → persist → pack_and_upload.
58. - `pipeline/news_rss_core.py` — shared utilities. DeepSeek call wrappers
59.   with retry, vet/rewriter/enricher prompts, RSS fetch, duplicate checker.
60. - `pipeline/pack_and_upload.py` — validation + zip + manifest + per-day
61.   flat upload + archive-index + retention.
62. - `pipeline/image_optimize.py` — webp optimizer with shutil.which() for
63.   cross-platform CLI path.
64. - `pipeline/news_sources.py` / `science_sources.py` / `fun_sources.py` —
65.   RSS source registries (per-weekday rotation for Science/Fun).
66. - `pipeline/news_aggregate.py` / `science_aggregate.py` / `fun_aggregate.py`
67.   — per-category aggregators (mostly wrappers around `run_source_with_backups`).
68. - `pipeline/supabase_io.py` — DB insert/update helpers.
69. - `pipeline/rewrite_from_db.py` — resume pipeline from DB state (skip
70.   mining + image ops). Used for debug / partial-category re-runs.
71. 
72. ### Frontend (React 18 + Babel-standalone, in-browser JSX transpile)
73. - `website/index.html` — app shell. Loads data.jsx / components.jsx /
74.   home.jsx / article.jsx / user-panel.jsx. Owns top-level state (route,
75.   level, cat, archiveDay, progress, tweaks).
76. - `website/data.jsx` — payload loader. Fetches today's listings from
77.   `/payloads/*.json` (local). For archive mode, fetches from Supabase
78.   Storage `<date>/payloads/*.json`. Exposes window.loadArchive(date).
79. - `website/home.jsx` — listing page with feature + normal card variants,
80.   DatePopover for "View old news", footer generation timestamp.
81. - `website/article.jsx` — detail page: Read & Words / Background / Quiz
82.   / Think & Share tabs. Supports mind-tree Article_Structure for Tree
83.   level, 5W boxes for Sprout.
84. - `website/components.jsx` — shared UI bits (CatChip, XpBadge, etc.).
85. - `website/user-panel.jsx` — profile drawer (name / avatar / theme / level).
86. 
87. ### CI/CD
88. - `.github/workflows/daily-pipeline.yml` — news-v2 daily cron (pipeline).
89. - (kidsnews-v2 repo) `.github/workflows/sync-from-supabase.yml` — pulls
90.   latest.zip + commits.
91. - `requirements.txt` — Python deps.
92. - `pipeline/backfill_card_summaries.py`, `pipeline/augment_mined_at.py` —
93.   one-shots used historically.
94. 
95. ## What to evaluate
96. 
97. Focus where you'd expect bugs or future pain:
98. 
99. 1. **Correctness.**
100.    - `dedup_winners` → `pick_winners_with_dedup` refactor. Two overlapping
101.      ScienceDaily feeds produced the same article; fix was to return up
102.      to 4 candidates and promote next on dup. Check edge cases: all
103.      sources returning candidates that are all pairwise dupes; candidate
104.      exhaustion mid-loop.
105.    - `filter_past_duplicates` title-similarity at 0.80 — are there
106.      obvious false positives / negatives? (titles can differ
107.      significantly while being the same story; or be identical but
108.      different stories.)
109.    - `deepseek_*_call` retry logic — does it handle rate-limit
110.      (429) differently from JSON parse errors?
111.    - `detail_enrich` split-batch fallback — what if BOTH easy and
112.      middle sub-calls fail? Currently continues with partial details;
113.      downstream validator will catch.
114. 
115. 2. **Security.**
116.    - Supabase service key lives in a committed .env loader (module
117.      top-level), overridden by GitHub Actions secret at job start.
118.      Any path where the key could end up in a log?
119.    - Vercel.json Cache-Control of 5min for user-visible assets — any
120.      risk of serving private data?
121.    - DeepSeek API key is only used server-side; confirm no frontend
122.      references.
123.    - Any HTML injection paths in the rewriter output? UI highlights
124.      keywords by matching with user-content strings.
125. 
126. 3. **Failure modes.**
127.    - Pipeline partial failure (category rewrite succeeds but enrich
128.      fails): is there a state where a partial bundle gets uploaded?
129.      (We added `check_not_overwriting_newer` and `validate_bundle`.)
130.    - Supabase Storage quota exhaustion mid-upload.
131.    - Vercel build fails after kidsnews-v2 commit — the pipeline
132.      doesn't know; only manual intervention.
133.    - Browser with localStorage full / disabled.
134. 
135. 4. **Maintainability.**
136.    - `pipeline/news_rss_core.py` is ~1200 lines. Should it split?
137.    - `full_round.py` grew fast — orchestration, dedup, image-process
138.      helpers, persistence, emit — all in one file.
139.    - React app has no build step (Babel-standalone). Fine for a
140.      prototype; risky long-term. Recommendation?
141.    - Hardcoded `/Users/jiong/...` paths were a CI bug source today;
142.      are there others lurking?
143. 
144. 5. **Architecture.**
145.    - Three-repo split: authoring / deploy / legacy. Any cleaner alt?
146.    - The zip-over-Storage indirection vs directly pushing
147.      generated artifacts to the deploy repo.
148.    - Per-day flat files coexist with zips — redundant, or
149.      justified?
150.    - "CI-only, never run locally" guard (`check_not_overwriting_newer`)
151.      — robust enough? Any evasion paths?
152. 
153. 6. **Prompt engineering.**
154.    - Rewriter prompt vs enricher prompt — any accuracy-vs-creativity
155.      trade-offs worth flagging?
156.    - `card_summary` ≤ 120 words — is the prompt actually enforceable?
157.      (We also post-trim with a word cap.)
158.    - Past-dedup threshold of 0.80 title similarity — when would you
159.      lower or raise it?
160. 
161. ## Format of your review
162. 
163. For each finding, use:
164. 
165. - **Severity**: `Critical` / `Important` / `Minor` / `Info`
166. - **File:line** (or "cross-cutting")
167. - **What**: one-sentence description
168. - **Why it matters** (1-2 sentences)
169. - **Suggested fix** (concrete, if you have one)
170. 
171. Then at the end: 3-5 line assessment summary + top 3 things to fix first.
172. 
173. Do not nitpick style unless it materially affects clarity. Do not
174. suggest broad refactors without a specific incident that justifies
175. them. Trust that the design decisions (RSS-only, three-repo split,
176. zip-via-Supabase, React-without-build) are intentional unless you spot
177. evidence they're causing real problems.
178.
````

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/index.html.**

/Users/jiong/myprojects/news-v2/website/index.html

<details>
<summary>276 lines</summary>

```
1. <!doctype html>
2. <html lang="en">
3. <head>
4. <meta charset="utf-8"/>
5. <meta name="viewport" content="width=device-width,initial-scale=1"/>
6. <title>News Oh,Ye! — Kids News Prototype</title>
7. <link rel="preconnect" href="https://fonts.googleapis.com">
8. <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
9. <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700;9..144,800;9..144,900&family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
10. <style>
11.   html, body { margin:0; padding:0; font-family: 'Nunito', sans-serif; background:#fff9ef; color:#1b1230; }
12.   * { box-sizing: border-box; -webkit-font-smoothing: antialiased; }
13.   button { font-family: 'Nunito', sans-serif; }
14.   ::selection { background:#ffc83d; color:#1b1230; }
15.   /* Scrollbar - subtle */
16.   ::-webkit-scrollbar { width:10px; height:10px; }
17.   ::-webkit-scrollbar-track { background:#fff9ef; }
18.   ::-webkit-scrollbar-thumb { background:#e8dcc6; border-radius:10px; }
19. </style>
20. <script src="https://unpkg.com/react@18.3.1/umd/react.development.js" integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L" crossorigin="anonymous"></script>
21. <script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm" crossorigin="anonymous"></script>
22. <script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y" crossorigin="anonymous"></script>
23. </head>
24. <body>
25. <div id="root"></div>
26. 
27. <script type="text/babel" src="data.jsx?v=20260424e"></script>
28. <script type="text/babel" src="components.jsx"></script>
29. <script type="text/babel" src="home.jsx?v=20260424e"></script>
30. <script type="text/babel" src="article.jsx?v=20260424e"></script>
31. <script type="text/babel" src="user-panel.jsx"></script>
32. 
33. <script type="text/babel">
34. const { useState, useEffect } = React;
35. 
36. const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
37.   "theme": "sunny",
38.   "showConfetti": true,
39.   "heroVariant": "daily15",
40.   "userName": "",
41.   "avatar": "panda",
42.   "language": "en",
43.   "dailyGoal": 15,
44.   "level": "Sprout",
45.   "streakDays": 0,
46.   "xp": 0
47. }/*EDITMODE-END*/;
48. 
49. function App() {
50.   // restore from localStorage; if saved articleId no longer exists (payloads changed), fall back to home
51.   const [route, setRoute] = useState(() => {
52.     try {
53.       const saved = JSON.parse(localStorage.getItem('ohye_route') || 'null');
54.       if (!saved) return { page:'home', articleId:null };
55.       if (saved.page === 'article' && !ARTICLES.some(a => a.id === saved.articleId)) {
56.         return { page:'home', articleId:null };
57.       }
58.       return saved;
59.     } catch { return { page:'home', articleId:null }; }
60.   });
61.   const [level, setLevel] = useState(() => {
62.     const v = localStorage.getItem('ohye_level') || 'Sprout';
63.     // Retire Seedling — migrate legacy profiles
64.     return v === 'Seedling' ? 'Sprout' : v;
65.   });
66.   const [cat, setCat] = useState(() => {
67.     const v = localStorage.getItem('ohye_cat') || 'News';
68.     return (v === 'Today' || v === 'Archive' || v === 'All') ? 'News' : v;
69.   });
70.   const [archiveDay, setArchiveDay] = useState(() => {
71.     // archiveDay is now "YYYY-MM-DD" (string) or null for today.
72.     // Migration: any legacy numeric value in localStorage is cleared.
73.     const v = localStorage.getItem('ohye_archive_day');
74.     if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
75.     if (v) localStorage.removeItem('ohye_archive_day');
76.     return null;
77.   });
78.   const [progress, setProgress] = useState(() => {
79.     try {
80.       const saved = JSON.parse(localStorage.getItem('ohye_progress') || 'null');
81.       const base = { readToday: MOCK_USER.readToday, minutesToday: MOCK_USER.minutesToday, articleProgress: {} };
82.       if (!saved) return base;
83.       return { articleProgress: {}, ...saved, articleProgress: saved.articleProgress || {} };
84.     } catch { return { readToday: MOCK_USER.readToday, minutesToday: MOCK_USER.minutesToday, articleProgress: {} }; }
85.   });
86. 
87.   // Tweaks / User Panel — persisted to localStorage so name/avatar/theme/etc.
88.   // survive reloads. Defaults fill in any missing keys (forward-compat when
89.   // we add new tweak fields later).
90.   const [tweaks, setTweaks] = useState(() => {
91.     try {
92.       const saved = JSON.parse(localStorage.getItem('ohye_tweaks') || 'null');
93.       return saved ? { ...TWEAK_DEFAULTS, ...saved } : TWEAK_DEFAULTS;
94.     } catch { return TWEAK_DEFAULTS; }
95.   });
96.   const [userPanelOpen, setUserPanelOpen] = useState(false);
97. 
98.   useEffect(() => { localStorage.setItem('ohye_route', JSON.stringify(route)); }, [route]);
99.   useEffect(() => { localStorage.setItem('ohye_level', level); }, [level]);
100.   useEffect(() => { localStorage.setItem('ohye_cat', cat); }, [cat]);
101.   useEffect(() => {
102.     if (archiveDay) localStorage.setItem('ohye_archive_day', String(archiveDay));
103.     else localStorage.removeItem('ohye_archive_day');
104.     // Whenever archiveDay changes, re-load ARTICLES from the matching bundle
105.     // (today's local files, or a past day's Supabase prefix).
106.     if (typeof window.loadArchive === 'function') {
107.       window.loadArchive(archiveDay).then(() => {
108.         // Force a re-render by bumping a dummy state; route stays put.
109.         setRoute(r => ({ ...r }));
110.       });
111.     }
112.   }, [archiveDay]);
113.   useEffect(() => { localStorage.setItem('ohye_progress', JSON.stringify(progress)); }, [progress]);
114.   useEffect(() => { localStorage.setItem('ohye_tweaks', JSON.stringify(tweaks)); }, [tweaks]);
115. 
116.   // Edit-mode wiring
117.   useEffect(() => {
118.     const handler = (e) => {
119.       if (!e.data) return;
120.       if (e.data.type === '__activate_edit_mode') setUserPanelOpen(true);
121.       if (e.data.type === '__deactivate_edit_mode') setUserPanelOpen(false);
122.     };
123.     window.addEventListener('message', handler);
124.     // Announce AFTER listener
125.     try { window.parent.postMessage({ type:'__edit_mode_available' }, '*'); } catch {}
126.     return () => window.removeEventListener('message', handler);
127.   }, []);
128. 
129.   const updateTweak = (key, val) => {
130.     const edits = { [key]: val };
131.     setTweaks(t => ({...t, ...edits}));
132.     try { window.parent.postMessage({ type:'__edit_mode_set_keys', edits }, '*'); } catch {}
133.   };
134. 
135.   // Apply theme to root
136.   const themeVars = {
137.     sunny: { bg:'#fff9ef', accent:'#ffc83d', hero1:'#ffe2a8', hero2:'#ffc0a8', border:'#ffb98a', heroTextAccent:'#c14e2a', card:'#fff', chip:'#f0e8d8' },
138.     sky:   { bg:'#eef6ff', accent:'#5bb4ff', hero1:'#cfe6ff', hero2:'#bfd9ff', border:'#8ec2ff', heroTextAccent:'#1f6bbf', card:'#fff', chip:'#dce8f5' },
139.     candy: { bg:'#fff0f6', accent:'#ff6ba0', hero1:'#ffd0e2', hero2:'#e0cbff', border:'#ffa0c5', heroTextAccent:'#b73a79', card:'#fff', chip:'#f5dce8' },
140.     forest:{ bg:'#f3f8ec', accent:'#7cbf5a', hero1:'#d9ecc0', hero2:'#f2e1a6', border:'#a7d685', heroTextAccent:'#4a7a2a', card:'#fff', chip:'#e0e8cf' },
141.   };
142.   const theme = themeVars[tweaks.theme] || themeVars.sunny;
143. 
144.   useEffect(() => {
145.     document.body.style.background = theme.bg;
146.     const root = document.documentElement;
147.     root.style.setProperty('--theme-bg', theme.bg);
148.     root.style.setProperty('--theme-accent', theme.accent);
149.     root.style.setProperty('--theme-hero1', theme.hero1);
150.     root.style.setProperty('--theme-hero2', theme.hero2);
151.     root.style.setProperty('--theme-border', theme.border);
152.     root.style.setProperty('--theme-hero-text', theme.heroTextAccent);
153.     root.style.setProperty('--theme-chip', theme.chip);
154.   }, [tweaks.theme]);
155. 
156.   const onOpen = (id) => {
157.     // Chinese summary cards have no detail page — route to the English twin
158.     // (Tree-level / middle) via storyId. If no Tree twin exists, fall back to
159.     // any English variant of the same story.
160.     const target = ARTICLES.find(a => a.id === id);
161.     if (target && target.noDetail && target.language === 'zh') {
162.       const tree = ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en' && a.level === 'Tree');
163.       const any = tree || ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en');
164.       if (any) id = any.id;
165.     }
166.     setRoute({ page:'article', articleId:id });
167.   };
168.   const onBack = () => setRoute({ page:'home', articleId:null });
169.   const onComplete = () => setRoute({ page:'home', articleId:null });
170. 
171.   return (
172.     <div data-screen-label={route.page==='home' ? '01 Home' : '02 Article'} style={{minHeight:'100vh', background: theme.bg}}>
173.       {route.page === 'home' ? (
174.         <HomePage
175.           onOpen={onOpen}
176.           onOpenArchive={(d)=>{ setArchiveDay(d); setCat('All'); window.scrollTo({top:0}); }}
177.           archiveDay={archiveDay}
178.           level={level} setLevel={setLevel}
179.           cat={cat} setCat={setCat}
180.           progress={progress}
181.           theme={theme}
182.           heroVariant={tweaks.heroVariant}
183.           tweaks={tweaks}
184.           onOpenUserPanel={()=>setUserPanelOpen(true)}
185.         />
186.       ) : (
187.         <ArticlePage
188.           articleId={route.articleId}
189.           onBack={onBack}
190.           onComplete={onComplete}
191.           progress={progress}
192.           setProgress={setProgress}
193.         />
194.       )}
195. 
196.       {userPanelOpen && (
197.         <UserPanel
198.           tweaks={tweaks}
199.           updateTweak={updateTweak}
200.           level={level}
201.           setLevel={setLevel}
202.           onClose={()=>setUserPanelOpen(false)}
203.         />
204.       )}
205.     </div>
206.   );
207. }
208. 
209. function TweaksPanel({ tweaks, updateTweak, setTweaksVisible }) {
210.   return (
211.     <div style={{
212.       position:'fixed', bottom:20, right:20, width:280, background:'#fff',
213.       borderRadius:18, border:'2px solid #1b1230', padding:'16px 18px',
214.       boxShadow:'0 10px 0 rgba(27,18,48,0.18)', zIndex:100,
215.       fontFamily:'Nunito, sans-serif',
216.     }}>
217.       <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
218.         <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>🎨 Tweaks</div>
219.         <button onClick={()=>setTweaksVisible(false)} style={{background:'none', border:'none', fontSize:18, cursor:'pointer', color:'#9a8d7a'}}>×</button>
220.       </div>
221. 
222.       <TwkRow label="Color theme">
223.         <select value={tweaks.theme} onChange={e=>updateTweak('theme', e.target.value)} style={twkInput}>
224.           <option value="sunny">☀️ Sunny</option>
225.           <option value="sky">🌊 Sky</option>
226.           <option value="candy">🍬 Candy</option>
227.           <option value="forest">🌳 Forest</option>
228.         </select>
229.       </TwkRow>
230. 
231.       <TwkRow label="Hero style">
232.         <select value={tweaks.heroVariant} onChange={e=>updateTweak('heroVariant', e.target.value)} style={twkInput}>
233.           <option value="daily15">Daily 15 banner</option>
234.           <option value="streak">Streak-focused</option>
235.         </select>
236.       </TwkRow>
237. 
238.       <TwkRow label="Quiz confetti">
239.         <label style={{display:'flex', alignItems:'center', gap:8, fontSize:13, fontWeight:700, cursor:'pointer'}}>
240.           <input type="checkbox" checked={tweaks.showConfetti} onChange={e=>updateTweak('showConfetti', e.target.checked)}/>
241.           {tweaks.showConfetti ? 'On' : 'Off'}
242.         </label>
243.       </TwkRow>
244. 
245.       <div style={{fontSize:11, color:'#9a8d7a', marginTop:10, borderTop:'1px dashed #eee', paddingTop:10}}>
246.         Toggle Tweaks from the toolbar to customize.
247.       </div>
248.     </div>
249.   );
250. }
251. const twkInput = {
252.   width:'100%', padding:'8px 10px', border:'1.5px solid #f0e8d8', borderRadius:10,
253.   fontSize:13, fontWeight:700, fontFamily:'Nunito, sans-serif', background:'#fff9ef', color:'#1b1230',
254. };
255. function TwkRow({ label, children }) {
256.   return (
257.     <div style={{marginBottom:10}}>
258.       <div style={{fontSize:11, fontWeight:800, color:'#6b5c80', letterSpacing:'.06em', textTransform:'uppercase', marginBottom:5}}>{label}</div>
259.       {children}
260.     </div>
261.   );
262. }
263. 
264. // Wait for all babel scripts to load AND for payloads to be fetched.
265. function mount() {
266.   if (!window.HomePage || !window.ArticlePage || !window.UserPanel) { setTimeout(mount, 50); return; }
267.   if (!window.__payloadsLoaded) { setTimeout(mount, 50); return; }
268.   window.__payloadsLoaded.then(() => {
269.     ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
270.   });
271. }
272. setTimeout(mount, 0);
273. </script>
274. </body>
275. </html>
276.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/data.jsx.**

/Users/jiong/myprojects/news-v2/website/data.jsx

<details>
<summary>138 lines</summary>

```
1. // data.jsx — v2 payload loader
2. // Consumes v1 listing payloads and exposes window.ARTICLES, window.CATEGORIES,
3. // window.LEVELS, window.MOCK_USER, window.__payloadsLoaded (promise for
4. // initial today's load), and window.loadArchive(date) to swap in a past day.
5. //
6. // Today's content is served from the Vercel deploy (same origin, flat paths
7. // under /payloads/ and /article_images/). Past days are served directly from
8. // Supabase Storage under /<date>/payloads/... — see ARCHIVE_BASE.
9. //
10. // Contract mapping (v2 UI <-- v1 source):
11. //   Sprout level        <- easy
12. //   Tree level          <- middle
13. //   Chinese summary card<- cn  (no detail page — summary only)
14. 
15. const SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co';
16. const ARCHIVE_BASE = `${SUPABASE_URL}/storage/v1/object/public/redesign-daily-content`;
17. 
18. const CATEGORIES = [
19.   { id: "news",    label: "News",    emoji: "📰", color: "#ff6b5b", bg: "#ffece8" },
20.   { id: "science", label: "Science", emoji: "🔬", color: "#17b3a6", bg: "#e0f6f3" },
21.   { id: "fun",     label: "Fun",     emoji: "🎈", color: "#9061f9", bg: "#eee5ff" },
22. ];
23. 
24. const LEVELS = [
25.   { id: "Sprout", emoji: "🌱", label: "Sprout", sub: "Easy" },
26.   { id: "Tree",   emoji: "🌳", label: "Tree",   sub: "Middle" },
27. ];
28. 
29. const MOCK_USER = {
30.   name: "Mia",
31.   streak: 7,
32.   minutesToday: 6,
33.   dailyGoal: 15,
34.   totalXp: 1240,
35.   weekXp: 310,
36.   badges: ["🦉", "🔭", "🌱"],
37.   readToday: ["a2"],
38. };
39. 
40. // Rewrite /article_images/xxx.webp → full Supabase URL when we're loading an
41. // archived day. For today's content (archiveDate = null), leave as-is.
42. function resolveImageUrl(rawUrl, archiveDate) {
43.   if (!archiveDate || !rawUrl) return rawUrl || "";
44.   if (rawUrl.startsWith('http')) return rawUrl;
45.   const rel = rawUrl.replace(/^\//, '');   // strip leading slash
46.   return `${ARCHIVE_BASE}/${archiveDate}/${rel}`;
47. }
48. 
49. function listingToArticle(entry, cat, lvl, archiveDate) {
50.   const categoryLabel = { news: "News", science: "Science", fun: "Fun" }[cat];
51.   const isZh = lvl === "cn";
52.   const level = isZh ? null : (lvl === "easy" ? "Sprout" : "Tree");
53.   return {
54.     id: entry.id + "-" + lvl,
55.     storyId: entry.id,
56.     archiveDate: archiveDate || null,   // null = today's edition
57.     title: entry.title,
58.     summary: entry.summary,
59.     body: "",
60.     image: resolveImageUrl(entry.image_url, archiveDate),
61.     category: categoryLabel,
62.     source: entry.source || "",
63.     time: entry.time_ago || "",
64.     minedAt: entry.mined_at || "",
65.     sourcePublishedAt: entry.source_published_at || "",
66.     readMins: isZh ? 2 : (lvl === "easy" ? 3 : 5),
67.     level: level,
68.     language: isZh ? "zh" : "en",
69.     xp: isZh ? 15 : (lvl === "easy" ? 30 : 45),
70.     tag: categoryLabel,
71.     keywords: [],
72.     quiz: [],
73.     discussion: [],
74.     noDetail: isZh,
75.   };
76. }
77. 
78. function listingBaseFor(archiveDate) {
79.   return archiveDate ? `${ARCHIVE_BASE}/${archiveDate}/payloads`
80.                      : 'payloads';
81. }
82. 
83. async function loadPayloads(archiveDate = null) {
84.   const cats = ["news", "science", "fun"];
85.   const levels = ["easy", "middle", "cn"];
86.   const base = listingBaseFor(archiveDate);
87.   const all = [];
88.   for (const cat of cats) {
89.     for (const lvl of levels) {
90.       try {
91.         const r = await fetch(`${base}/articles_${cat}_${lvl}.json?t=${Date.now()}`);
92.         if (!r.ok) { console.warn(`[data] missing: ${base}/articles_${cat}_${lvl}.json`); continue; }
93.         const { articles } = await r.json();
94.         const top3 = (articles || []).slice(0, 3);
95.         for (const a of top3) all.push(listingToArticle(a, cat, lvl, archiveDate));
96.       } catch (e) {
97.         console.warn(`[data] fetch failed: ${base}/articles_${cat}_${lvl}.json`, e);
98.       }
99.     }
100.   }
101.   return all;
102. }
103. 
104. // Fetch the list of available archive days from Supabase.
105. // Returns { dates: [...], updated_at } or { dates: [] } on failure.
106. async function loadArchiveIndex() {
107.   try {
108.     const r = await fetch(`${ARCHIVE_BASE}/archive-index.json?t=${Date.now()}`);
109.     if (!r.ok) return { dates: [] };
110.     return await r.json();
111.   } catch (e) {
112.     console.warn('[data] archive-index fetch failed', e);
113.     return { dates: [] };
114.   }
115. }
116. 
117. // Callable from the app: swap window.ARTICLES to point at a past day's
118. // bundle, or back to today when passed null.
119. async function loadArchive(date) {
120.   const list = await loadPayloads(date || null);
121.   window.ARTICLES = list;
122.   window.__archiveDate = date || null;
123.   return list;
124. }
125. 
126. window.CATEGORIES = CATEGORIES;
127. window.LEVELS = LEVELS;
128. window.MOCK_USER = MOCK_USER;
129. window.ARTICLES = [];
130. window.__archiveDate = null;
131. window.ARCHIVE_BASE = ARCHIVE_BASE;
132. window.loadArchive = loadArchive;
133. window.loadArchiveIndex = loadArchiveIndex;
134. window.__payloadsLoaded = loadPayloads().then(list => {
135.   window.ARTICLES = list;
136.   return list;
137. });
138.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx

```
File too large to read at once (36.2 KB). Consider using the grep tool to search within the file, or view with view_range to read specific sections.
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/article.jsx.**

/Users/jiong/myprojects/news-v2/website/article.jsx

```
File too large to read at once (41.5 KB). Consider using the grep tool to search within the file, or view with view_range to read specific sections.
```


### 💬 Copilot

Now let me view the components.jsx and user-panel.jsx:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/components.jsx.**

/Users/jiong/myprojects/news-v2/website/components.jsx (lines 1-100)

<details>
<summary>100 lines</summary>

```
1. // Shared components for News Oh,Ye!
2. const { useState, useEffect, useRef, useMemo } = React;
3. 
4. // ————————————————————————————————————————————————————————————
5. // LOGO — happy newspaper + "Ye!" + broadcast waves (latest news for kids)
6. // ————————————————————————————————————————————————————————————
7. function OhYeLogo({ size = 40 }) {
8.   return (
9.     <svg width={size} height={size} viewBox="0 0 64 64" fill="none" style={{display:'block'}}>
10.       <defs>
11.         <linearGradient id="logoSky" x1="0" x2="0" y1="0" y2="1">
12.           <stop offset="0" stopColor="#ffc83d" />
13.           <stop offset="1" stopColor="#ffa23d" />
14.         </linearGradient>
15.       </defs>
16. 
17.       {/* Broadcast waves — "latest news" signal radiating from top-right */}
18.       <g stroke="#ff6b5b" strokeWidth="1.8" strokeLinecap="round" fill="none" opacity="0.85">
19.         <path d="M54 14 q3 -1 4 -4"/>
20.         <path d="M57 19 q5 -1 7 -6"/>
21.       </g>
22.       {/* little sparkles */}
23.       <g fill="#ffb82e">
24.         <circle cx="6" cy="12" r="1.4"/>
25.         <circle cx="10" cy="8" r="1.1"/>
26.       </g>
27. 
28.       {/* Folded newspaper body — tilted like it's being held */}
29.       <g transform="rotate(-6 32 36)">
30.         {/* Back page (peeking) */}
31.         <rect x="11" y="17" width="42" height="38" rx="4" fill="#fff3d6" stroke="#1b1230" strokeWidth="2"/>
32.         {/* Front page */}
33.         <rect x="8" y="20" width="42" height="38" rx="4" fill="#ffffff" stroke="#1b1230" strokeWidth="2"/>
34.         {/* Masthead bar with "NEWS" */}
35.         <rect x="12" y="24" width="34" height="7" rx="2" fill="url(#logoSky)"/>
36.         <text x="29" y="29.8" textAnchor="middle" fontSize="6" fontWeight="900" fill="#1b1230" fontFamily="Fraunces, serif" letterSpacing="1">NEWS</text>
37.         {/* Headline lines */}
38.         <rect x="12" y="34.5" width="26" height="2.2" rx="1" fill="#d9cdb7"/>
39.         <rect x="12" y="39.2" width="20" height="2.2" rx="1" fill="#d9cdb7"/>
40.         {/* Smiling eyes on the paper (kids touch) */}
41.         <circle cx="19" cy="49" r="2" fill="#1b1230"/>
42.         <circle cx="27" cy="49" r="2" fill="#1b1230"/>
43.         {/* Smile */}
44.         <path d="M17 52.5 q6 4 12 0" stroke="#1b1230" strokeWidth="2" strokeLinecap="round" fill="none"/>
45.         {/* Rosy cheeks */}
46.         <circle cx="15" cy="52" r="1.3" fill="#ff9eb5" opacity="0.85"/>
47.         <circle cx="31" cy="52" r="1.3" fill="#ff9eb5" opacity="0.85"/>
48.       </g>
49. 
50.       {/* Speech bubble "Ye!" popping out (the happy/excited reaction) */}
51.       <g transform="rotate(8 48 16)">
52.         <path d="M38 6 h18 a4 4 0 0 1 4 4 v10 a4 4 0 0 1 -4 4 h-10 l-4 4 -1 -4 h-3 a4 4 0 0 1 -4 -4 v-10 a4 4 0 0 1 4 -4 z"
53.               fill="#ff6b5b" stroke="#1b1230" strokeWidth="2" strokeLinejoin="round"/>
54.         <text x="47" y="20" textAnchor="middle" fontSize="12" fontWeight="900" fill="#fff" fontFamily="Fraunces, serif">Ye!</text>
55.       </g>
56.     </svg>
57.   );
58. }
59. 
60. // ————————————————————————————————————————————————————————————
61. // STREAK RING — circular progress for daily 15-min goal
62. // ————————————————————————————————————————————————————————————
63. function StreakRing({ minutes, goal, streak, size = 72 }) {
64.   const r = size/2 - 6;
65.   const c = 2 * Math.PI * r;
66.   const pct = Math.min(1, minutes/goal);
67.   return (
68.     <div style={{position:'relative', width:size, height:size}}>
69.       <svg width={size} height={size} style={{transform:'rotate(-90deg)'}}>
70.         <circle cx={size/2} cy={size/2} r={r} stroke="#f0ebe3" strokeWidth="6" fill="none"/>
71.         <circle cx={size/2} cy={size/2} r={r} stroke="#ff8a3d" strokeWidth="6" fill="none"
72.           strokeDasharray={c} strokeDashoffset={c*(1-pct)} strokeLinecap="round"
73.           style={{transition:'stroke-dashoffset .6s ease'}}/>
74.       </svg>
75.       <div style={{position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', lineHeight:1}}>
76.         <div style={{fontSize:22}}>🔥</div>
77.         <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:14, color:'#1b1230', marginTop:2}}>{streak}</div>
78.       </div>
79.     </div>
80.   );
81. }
82. 
83. // ————————————————————————————————————————————————————————————
84. // CATEGORY CHIP
85. // ————————————————————————————————————————————————————————————
86. function CatChip({ cat, small }) {
87.   const c = CATEGORIES.find(x => x.label === cat) || CATEGORIES[0];
88.   return (
89.     <span style={{
90.       display:'inline-flex', alignItems:'center', gap:6,
91.       background: c.bg, color: c.color,
92.       padding: small ? '3px 10px' : '5px 12px',
93.       borderRadius: 999, fontWeight:800,
94.       fontSize: small ? 11 : 13,
95.       letterSpacing: '0.02em',
96.     }}>
97.       <span style={{fontSize: small ? 12 : 14}}>{c.emoji}</span>{c.label}
98.     </span>
99.   );
100. }
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/user-panel.jsx.**

/Users/jiong/myprojects/news-v2/website/user-panel.jsx

<details>
<summary>418 lines</summary>

```
1. // User Profile Button + Panel
2. const { useState: useStateU } = React;
3. 
4. const AVATARS = [
5.   { id:'fox', emoji:'🦊', bg:'#ffb27a' },
6.   { id:'panda', emoji:'🐼', bg:'#e8e8e8' },
7.   { id:'octopus', emoji:'🐙', bg:'#ffa5c5' },
8.   { id:'unicorn', emoji:'🦄', bg:'#e0cbff' },
9.   { id:'frog', emoji:'🐸', bg:'#bde8a0' },
10.   { id:'lion', emoji:'🦁', bg:'#ffd98a' },
11.   { id:'penguin', emoji:'🐧', bg:'#bed7ff' },
12.   { id:'tiger', emoji:'🐯', bg:'#ffc48a' },
13.   { id:'cat', emoji:'🐱', bg:'#f5e0b8' },
14.   { id:'rocket', emoji:'🚀', bg:'#c8bfff' },
15.   { id:'turtle', emoji:'🐢', bg:'#a8e6c4' },
16.   { id:'bear', emoji:'🐻', bg:'#e8c8a0' },
17. ];
18. 
19. const LANGS = [
20.   { id:'en', flag:'🇬🇧', label:'English' },
21.   { id:'zh', flag:'🇨🇳', label:'中文' },
22. ];
23. 
24. const LEVEL_OPTIONS = [
25.   { id:'Sprout', emoji:'🌱', sub:'Ages 8–10 · easier reads' },
26.   { id:'Tree', emoji:'🌳', sub:'Ages 11–13 · deeper dives' },
27. ];
28. 
29. const THEMES = [
30.   { id:'sunny',  emoji:'☀️', label:'Sunny',  sw1:'#ffe2a8', sw2:'#ffc0a8' },
31.   { id:'sky',    emoji:'🌊', label:'Sky',    sw1:'#cfe6ff', sw2:'#bfd9ff' },
32.   { id:'candy',  emoji:'🍬', label:'Candy',  sw1:'#ffd0e2', sw2:'#e0cbff' },
33.   { id:'forest', emoji:'🌳', label:'Forest', sw1:'#d9ecc0', sw2:'#f2e1a6' },
34. ];
35. 
36. const GOALS = [5, 10, 15, 20, 30];
37. 
38. // Find avatar object by id
39. function getAvatar(id) {
40.   return AVATARS.find(a => a.id === id) || AVATARS[0];
41. }
42. 
43. // —————————— USER BUTTON (in header) ——————————
44. function UserButton({ tweaks, onClick, streak }) {
45.   const av = getAvatar(tweaks.avatar);
46.   const lvl = LEVEL_OPTIONS.find(l => l.id === tweaks.level) || LEVEL_OPTIONS[1];
47.   return (
48.     <button onClick={onClick} style={{
49.       display:'flex', alignItems:'center', gap:10,
50.       background:'#fff', border:'2px solid #1b1230',
51.       borderRadius:999, padding:'4px 14px 4px 4px',
52.       cursor:'pointer',
53.       boxShadow:'0 3px 0 rgba(27,18,48,0.12)',
54.       fontFamily:'Nunito, sans-serif',
55.       transition:'transform .15s',
56.     }}
57.     onMouseEnter={e=>e.currentTarget.style.transform='translateY(-2px)'}
58.     onMouseLeave={e=>e.currentTarget.style.transform='translateY(0)'}
59.     >
60.       <div style={{
61.         width:38, height:38, borderRadius:999, background:av.bg,
62.         display:'flex', alignItems:'center', justifyContent:'center',
63.         fontSize:22, border:'2px solid #1b1230',
64.       }}>{av.emoji}</div>
65.       <div style={{textAlign:'left', lineHeight:1.1}}>
66.         <div style={{fontWeight:900, fontSize:14, color:'#1b1230'}}>{tweaks.userName || 'Me'}</div>
67.         <div style={{fontSize:11, color:'#6b5c80', fontWeight:700, display:'flex', gap:6, alignItems:'center'}}>
68.           <span>{lvl.emoji} {lvl.id}</span>
69.           <span style={{color:'#d0c4b4'}}>·</span>
70.           <span>🔥 {streak}</span>
71.         </div>
72.       </div>
73.       <span style={{fontSize:12, color:'#9a8d7a', marginLeft:2}}>▾</span>
74.     </button>
75.   );
76. }
77. 
78. // —————————— USER PANEL (slide-in drawer) ——————————
79. function UserPanel({ tweaks, updateTweak, level, setLevel, onClose }) {
80.   const av = getAvatar(tweaks.avatar);
81.   const [tab, setTab] = useStateU('learn'); // learn | look | me
82. 
83.   const setLevelBoth = (lv) => { setLevel(lv); updateTweak('level', lv); };
84. 
85.   return (
86.     <>
87.       {/* backdrop */}
88.       <div onClick={onClose} style={{
89.         position:'fixed', inset:0, background:'rgba(27,18,48,0.35)', zIndex:90,
90.         animation:'fadeIn .2s ease-out',
91.       }}/>
92.       {/* drawer */}
93.       <div style={{
94.         position:'fixed', top:0, right:0, bottom:0, width:420,
95.         background:'#fff9ef', zIndex:100,
96.         boxShadow:'-10px 0 40px rgba(27,18,48,0.2)',
97.         overflowY:'auto',
98.         fontFamily:'Nunito, sans-serif',
99.         animation:'slideIn .25s ease-out',
100.       }}>
101.         <style>{`
102.           @keyframes fadeIn { from{opacity:0} to{opacity:1} }
103.           @keyframes slideIn { from{transform:translateX(100%)} to{transform:translateX(0)} }
104.         `}</style>
105. 
106.         {/* close */}
107.         <button onClick={onClose} style={{
108.           position:'absolute', top:16, right:16, zIndex:2,
109.           width:36, height:36, borderRadius:999, border:'2px solid #1b1230',
110.           background:'#fff', cursor:'pointer', fontSize:16, fontWeight:900, color:'#1b1230',
111.         }}>×</button>
112. 
113.         {/* hero */}
114.         <div style={{
115.           background:`linear-gradient(135deg, ${av.bg} 0%, #ffe8c8 100%)`,
116.           padding:'32px 28px 20px',
117.           borderBottom:'2px solid #f0e8d8',
118.         }}>
119.           <div style={{display:'flex', alignItems:'center', gap:16}}>
120.             <div style={{
121.               width:88, height:88, borderRadius:999, background:'#fff',
122.               display:'flex', alignItems:'center', justifyContent:'center',
123.               fontSize:56, border:'3px solid #1b1230',
124.               boxShadow:'0 4px 0 rgba(27,18,48,0.2)',
125.             }}>{av.emoji}</div>
126.             <div style={{flex:1, minWidth:0}}>
127.               <input
128.                 value={tweaks.userName || ''}
129.                 onChange={e=>updateTweak('userName', e.target.value.slice(0, 18))}
130.                 placeholder="Your name"
131.                 style={{
132.                   fontFamily:'Fraunces, serif', fontWeight:900, fontSize:30,
133.                   color:'#1b1230', letterSpacing:'-0.02em',
134.                   background:'transparent', border:'none', outline:'none',
135.                   width:'100%', padding:0, margin:0,
136.                 }}
137.               />
138.               <div style={{display:'flex', gap:6, marginTop:4, flexWrap:'wrap'}}>
139.                 <MiniStat icon="🔥" val={`${tweaks.streakDays ?? 7} day streak`}/>
140.                 <MiniStat icon="⭐" val={`${tweaks.xp ?? 240} XP`}/>
141.               </div>
142.             </div>
143.           </div>
144.         </div>
145. 
146.         {/* tabs */}
147.         <div style={{display:'flex', gap:4, padding:'14px 20px 0', borderBottom:'2px solid #f0e8d8'}}>
148.           {[
149.             {id:'learn', label:'Learn', emoji:'📚'},
150.             {id:'look', label:'Look', emoji:'🎨'},
151.             {id:'me', label:'Me', emoji:'😊'},
152.           ].map(t => (
153.             <button key={t.id} onClick={()=>setTab(t.id)} style={{
154.               background: tab===t.id ? '#1b1230' : 'transparent',
155.               color: tab===t.id ? '#ffc83d' : '#6b5c80',
156.               border:'none', borderRadius:'12px 12px 0 0',
157.               padding:'10px 16px', cursor:'pointer',
158.               fontWeight:800, fontSize:13, fontFamily:'Nunito, sans-serif',
159.               display:'flex', gap:6, alignItems:'center',
160.             }}>
161.               <span>{t.emoji}</span><span>{t.label}</span>
162.             </button>
163.           ))}
164.         </div>
165. 
166.         <div style={{padding:'20px 24px 40px'}}>
167.           {tab === 'me' && (
168.             <>
169.               <Section label="Pick your animal" sub="This is you around the site">
170.                 <div style={{display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:8}}>
171.                   {AVATARS.map(a => (
172.                     <button key={a.id} onClick={()=>updateTweak('avatar', a.id)} style={{
173.                       aspectRatio:'1', borderRadius:14, background:a.bg,
174.                       border: tweaks.avatar===a.id ? '3px solid #1b1230' : '2px solid transparent',
175.                       cursor:'pointer', fontSize:28, padding:0,
176.                       boxShadow: tweaks.avatar===a.id ? '0 3px 0 rgba(27,18,48,0.2)' : 'none',
177.                       transform: tweaks.avatar===a.id ? 'translateY(-2px)' : 'none',
178.                       transition:'all .15s',
179.                     }}>{a.emoji}</button>
180.                   ))}
181.                 </div>
182.               </Section>
183. 
184.               <Section label="Daily goal" sub="Read 15 minutes a day to build your streak">
185.                 <div style={{
186.                   background:'#fff9ef', border:'2px solid #f0e8d8', borderRadius:14,
187.                   padding:'12px 16px', display:'flex', alignItems:'center', gap:12,
188.                 }}>
189.                   <div style={{
190.                     width:44, height:44, borderRadius:12, background:'#1b1230',
191.                     color:'#ffc83d', display:'flex', alignItems:'center', justifyContent:'center',
192.                     fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20,
193.                   }}>15</div>
194.                   <div>
195.                     <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230', lineHeight:1}}>15 min every day</div>
196.                     <div style={{fontSize:12, color:'#6b5c80', fontWeight:600, marginTop:4}}>One story from each category · just right for a daily habit</div>
197.                   </div>
198.                 </div>
199.               </Section>
200. 
201.               <Section label="Language" sub="What language you want stories in">
202.                 <div style={{display:'grid', gridTemplateColumns:'repeat(2, 1fr)', gap:8}}>
203.                   {LANGS.map(l => (
204.                     <button key={l.id} onClick={()=>{
205.                       updateTweak('language', l.id);
206.                       if (l.id === 'zh') setLevelBoth('Sprout');
207.                     }} style={{
208.                       background: tweaks.language===l.id ? '#1b1230' : '#fff',
209.                       color: tweaks.language===l.id ? '#fff' : '#1b1230',
210.                       border: tweaks.language===l.id ? '2px solid #1b1230' : '2px solid #f0e8d8',
211.                       borderRadius:14, padding:'10px 12px', cursor:'pointer',
212.                       fontWeight:800, fontSize:13, fontFamily:'Nunito, sans-serif',
213.                       display:'flex', gap:8, alignItems:'center', justifyContent:'flex-start',
214.                     }}>
215.                       <span style={{fontSize:20}}>{l.flag}</span>
216.                       <span>{l.label}</span>
217.                     </button>
218.                   ))}
219.                 </div>
220.               </Section>
221.             </>
222.           )}
223. 
224.           {tab === 'look' && (
225.             <>
226.               <Section label="Color theme" sub="Change the vibe of the whole site">
227.                 <div style={{display:'grid', gridTemplateColumns:'repeat(2, 1fr)', gap:10}}>
228.                   {THEMES.map(t => {
229.                     const active = tweaks.theme === t.id;
230.                     return (
231.                       <button key={t.id} onClick={()=>updateTweak('theme', t.id)} style={{
232.                         background:'#fff', padding:12, borderRadius:16,
233.                         border: active ? '3px solid #1b1230' : '2px solid #f0e8d8',
234.                         cursor:'pointer', textAlign:'left', fontFamily:'Nunito, sans-serif',
235.                         boxShadow: active ? '0 3px 0 rgba(27,18,48,0.15)' : 'none',
236.                       }}>
237.                         <div style={{height:38, borderRadius:10, background:`linear-gradient(135deg, ${t.sw1}, ${t.sw2})`, marginBottom:8}}/>
238.                         <div style={{fontWeight:900, fontSize:14, color:'#1b1230'}}>
239.                           {t.emoji} {t.label}
240.                         </div>
241.                       </button>
242.                     );
243.                   })}
244.                 </div>
245.               </Section>
246. 
247.               <Section label="Home page style" sub="What greets you on the homepage">
248.                 <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
249.                   <HeroPick active={tweaks.heroVariant==='daily15'} onClick={()=>updateTweak('heroVariant','daily15')}
250.                     title="Today's 15" sub="Start reading fast"
251.                     preview={
252.                       <div style={{background:'linear-gradient(135deg,#ffe2a8,#ffc0a8)', borderRadius:8, padding:8, height:60}}>
253.                         <div style={{fontSize:9, fontWeight:800, color:'#c14e2a'}}>TODAY</div>
254.                         <div style={{fontSize:14, fontWeight:900, color:'#1b1230', fontFamily:'Fraunces, serif'}}>15 <span style={{background:'#ffc83d', padding:'0 4px', borderRadius:3}}>min</span></div>
255.                       </div>
256.                     }
257.                   />
258.                   <HeroPick active={tweaks.heroVariant==='streak'} onClick={()=>updateTweak('heroVariant','streak')}
259.                     title="Streak mode" sub="See your fire days"
260.                     preview={
261.                       <div style={{background:'linear-gradient(135deg,#ffe2a8,#ffc0a8)', borderRadius:8, padding:8, height:60, display:'flex', alignItems:'center', gap:6}}>
262.                         <div style={{fontSize:20}}>🔥</div>
263.                         <div>
264.                           <div style={{fontSize:14, fontWeight:900, color:'#1b1230', fontFamily:'Fraunces, serif'}}>7 days</div>
265.                           <div style={{display:'flex', gap:2}}>
266.                             {[1,1,1,1,1,1,0].map((d,i)=>(
267.                               <div key={i} style={{width:6, height:8, borderRadius:2, background: d?'#1b1230':'rgba(255,255,255,0.6)'}}/>
268.                             ))}
269.                           </div>
270.                         </div>
271.                       </div>
272.                     }
273.                   />
274.                 </div>
275.               </Section>
276. 
277.               <Section label="Quiz celebration" sub="Confetti when you get things right">
278.                 <label style={{display:'flex', alignItems:'center', gap:10, padding:'10px 14px', background:'#fff', border:'2px solid #f0e8d8', borderRadius:14, cursor:'pointer'}}>
279.                   <input type="checkbox" checked={tweaks.showConfetti} onChange={e=>updateTweak('showConfetti', e.target.checked)} style={{width:18, height:18}}/>
280.                   <span style={{fontWeight:700, fontSize:14, color:'#1b1230'}}>🎉 {tweaks.showConfetti ? 'Confetti on' : 'Confetti off'}</span>
281.                 </label>
282.               </Section>
283.             </>
284.           )}
285. 
286.           {tab === 'learn' && (
287.             <>
288.               <Section label="Reading level" sub={tweaks.language === 'zh' ? 'Chinese stories are only available at Sprout level right now' : 'Harder or easier stories'}>
289.                 <div style={{display:'flex', flexDirection:'column', gap:8}}>
290.                   {LEVEL_OPTIONS.map(l => {
291.                     const active = (level || tweaks.level) === l.id;
292.                     const zhLocked = tweaks.language === 'zh' && l.id !== 'Sprout';
293.                     return (
294.                       <button key={l.id} disabled={zhLocked} onClick={()=>!zhLocked && setLevelBoth(l.id)} style={{
295.                         background: active ? '#1b1230' : '#fff',
296.                         color: active ? '#fff' : '#1b1230',
297.                         border: active ? '2px solid #1b1230' : '2px solid #f0e8d8',
298.                         borderRadius:14, padding:'12px 16px', cursor: zhLocked ? 'not-allowed' : 'pointer',
299.                         fontFamily:'Nunito, sans-serif',
300.                         display:'flex', alignItems:'center', gap:12, textAlign:'left',
301.                         opacity: zhLocked ? 0.45 : 1,
302.                         position:'relative',
303.                       }}>
304.                         <div style={{fontSize:28}}>{l.emoji}</div>
305.                         <div>
306.                           <div style={{fontWeight:900, fontSize:16}}>{l.id}</div>
307.                           <div style={{fontSize:12, opacity:0.75, fontWeight:600}}>{l.sub}</div>
308.                         </div>
309.                         {active && !zhLocked && <div style={{marginLeft:'auto', fontSize:18, color:'#ffc83d'}}>✓</div>}
310.                         {zhLocked && <div style={{marginLeft:'auto', fontSize:11, fontWeight:800, color:'#9a8d7a', background:'#f6efe3', padding:'3px 8px', borderRadius:999}}>🔒 EN only</div>}
311.                       </button>
312.                     );
313.                   })}
314.                 </div>
315.               </Section>
316. 
317.               <Section label="Your progress" sub="">
318.                 <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
319.                   <BigStat icon="🔥" val={`${tweaks.streakDays ?? 7}`} label="Day streak"/>
320.                   <BigStat icon="⭐" val={`${tweaks.xp ?? 240}`} label="XP earned"/>
321.                   <BigStat icon="📖" val="23" label="Stories read"/>
322.                   <BigStat icon="🏆" val="4" label="Badges"/>
323.                 </div>
324.               </Section>
325. 
326.               <Section label="Parent / teacher" sub="">
327.                 <button style={{
328.                   width:'100%', background:'#fff', border:'2px solid #f0e8d8',
329.                   borderRadius:14, padding:'12px 16px', cursor:'pointer',
330.                   fontWeight:800, fontSize:14, color:'#1b1230',
331.                   fontFamily:'Nunito, sans-serif', textAlign:'left',
332.                   display:'flex', alignItems:'center', gap:10,
333.                 }}>
334.                   <span style={{fontSize:20}}>👨‍👩‍👧</span>
335.                   <span style={{flex:1}}>Parent dashboard</span>
336.                   <span style={{color:'#9a8d7a'}}>›</span>
337.                 </button>
338.               </Section>
339.             </>
340.           )}
341. 
342.           <div style={{display:'flex', gap:8, marginTop:12}}>
343.             <button onClick={onClose} style={{
344.               flex:1, background:'#1b1230', color:'#ffc83d', border:'none',
345.               borderRadius:14, padding:'14px', cursor:'pointer',
346.               fontWeight:900, fontSize:15, fontFamily:'Nunito, sans-serif',
347.               boxShadow:'0 3px 0 rgba(0,0,0,0.2)',
348.             }}>Done ✓</button>
349.             <button onClick={()=>{
350.               updateTweak('avatar','fox'); updateTweak('userName','Me');
351.               updateTweak('theme','sunny'); updateTweak('heroVariant','daily15');
352.               updateTweak('language','en'); updateTweak('dailyGoal',15);
353.               setLevelBoth('Sprout');
354.             }} style={{
355.               background:'#fff', color:'#6b5c80', border:'2px solid #f0e8d8',
356.               borderRadius:14, padding:'14px 16px', cursor:'pointer',
357.               fontWeight:800, fontSize:13, fontFamily:'Nunito, sans-serif',
358.             }}>Reset</button>
359.           </div>
360.         </div>
361.       </div>
362.     </>
363.   );
364. }
365. 
366. function MiniStat({ icon, val }) {
367.   return (
368.     <div style={{
369.       display:'inline-flex', alignItems:'center', gap:4,
370.       background:'rgba(255,255,255,0.7)', padding:'3px 10px', borderRadius:999,
371.       fontSize:12, fontWeight:800, color:'#1b1230',
372.     }}>
373.       <span>{icon}</span><span>{val}</span>
374.     </div>
375.   );
376. }
377. 
378. function BigStat({ icon, val, label }) {
379.   return (
380.     <div style={{
381.       background:'#fff', border:'2px solid #f0e8d8', borderRadius:14,
382.       padding:'14px', textAlign:'center',
383.     }}>
384.       <div style={{fontSize:24, marginBottom:2}}>{icon}</div>
385.       <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:26, color:'#1b1230', lineHeight:1}}>{val}</div>
386.       <div style={{fontSize:11, color:'#6b5c80', fontWeight:700, marginTop:4, textTransform:'uppercase', letterSpacing:'.05em'}}>{label}</div>
387.     </div>
388.   );
389. }
390. 
391. function HeroPick({ active, onClick, title, sub, preview }) {
392.   return (
393.     <button onClick={onClick} style={{
394.       background:'#fff', padding:10, borderRadius:16,
395.       border: active ? '3px solid #1b1230' : '2px solid #f0e8d8',
396.       cursor:'pointer', textAlign:'left', fontFamily:'Nunito, sans-serif',
397.       boxShadow: active ? '0 3px 0 rgba(27,18,48,0.15)' : 'none',
398.     }}>
399.       {preview}
400.       <div style={{fontWeight:900, fontSize:13, color:'#1b1230', marginTop:8}}>{title}</div>
401.       <div style={{fontSize:11, color:'#6b5c80', fontWeight:600}}>{sub}</div>
402.     </button>
403.   );
404. }
405. 
406. function Section({ label, sub, children }) {
407.   return (
408.     <div style={{marginBottom:24}}>
409.       <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:16, color:'#1b1230', marginBottom:2}}>{label}</div>
410.       {sub && <div style={{fontSize:12, color:'#6b5c80', fontWeight:600, marginBottom:12}}>{sub}</div>}
411.       {!sub && <div style={{height:10}}/>}
412.       {children}
413.     </div>
414.   );
415. }
416. 
417. Object.assign(window, { UserButton, UserPanel });
418.
```

</details>


### ✅ `bash`

**Get line counts for home.jsx and article.jsx**

$ wc -l /Users/jiong/myprojects/news-v2/website/home.jsx /Users/jiong/myprojects/news-v2/website/article.jsx

```
728 /Users/jiong/myprojects/news-v2/website/home.jsx
     806 /Users/jiong/myprojects/news-v2/website/article.jsx
    1534 total
<exited with exit code 0>
```


### 💬 Copilot

Now let me search for specific security and correctness issues in the large files:

### ❌ `grep`

**dangerouslySetInnerHTML|innerHTML|eval|new Function|setTimeout.*eval|insertAdjacentHTML**

"dangerouslySetInnerHTML|innerHTML|eval|new Function|setTimeout.*eval|insertAdjacentHTML" in jsx files (website)

```
rg: unrecognized file type: jsx
```


### ❌ `grep`

**localStorage|sessionStorage**

"localStorage|sessionStorage" in jsx files (website)

```
rg: unrecognized file type: jsx
```


### ❌ `grep`

**fetch.*ARTICLE|fetch.*archive|loadArchive**

"fetch.*ARTICLE|fetch.*archive|loadArchive" in jsx files (website)

```
rg: unrecognized file type: jsx
```


### ✅ `grep`

**dangerouslySetInnerHTML|innerHTML|eval|new Function**

"dangerouslySetInnerHTML|innerHTML|eval|new Function" in *.jsx (website)

```
No matches found.
```


### ✅ `grep`

**localStorage.getItem|localStorage.setItem**

"localStorage.getItem|localStorage.setItem" in *.jsx (website)

```
/Users/jiong/myprojects/news-v2/website/home.jsx:    try { const s = JSON.parse(localStorage.getItem('ohye_daily_picks_v3') || 'null'); if (s && s.length === 3) return s; } catch {}
/Users/jiong/myprojects/news-v2/website/home.jsx:  useEffectH(() => { localStorage.setItem('ohye_daily_picks_v3', JSON.stringify(activePicks)); }, [activePicks]);
```


### ✅ `grep`

**loadArchive|fetch.*payload**

"loadArchive|fetch.*payload" in *.jsx (website)

<details>
<summary>8 matches</summary>

```
/Users/jiong/myprojects/news-v2/website/home.jsx:  // When archiveDay changes, ARTICLES is swapped wholesale by loadArchive()
/Users/jiong/myprojects/news-v2/website/home.jsx:    window.loadArchiveIndex().then(r => { if (!cancelled) setIndex(r); });
/Users/jiong/myprojects/news-v2/website/article.jsx:  // Lazy-fetch v1 detail payload for this article. Chinese cards (noDetail) are
/Users/jiong/myprojects/news-v2/website/data.jsx:// initial today's load), and window.loadArchive(date) to swap in a past day.
/Users/jiong/myprojects/news-v2/website/data.jsx:async function loadArchiveIndex() {
/Users/jiong/myprojects/news-v2/website/data.jsx:async function loadArchive(date) {
/Users/jiong/myprojects/news-v2/website/data.jsx:window.loadArchive = loadArchive;
/Users/jiong/myprojects/news-v2/website/data.jsx:window.loadArchiveIndex = loadArchiveIndex;
```

</details>


### 💬 Copilot

Now let me examine key sections of home.jsx and article.jsx:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 1-150)

<details>
<summary>150 lines</summary>

```
1. // Home page — News Oh,Ye!
2. const { useState: useStateH, useEffect: useEffectH, useMemo: useMemoH } = React;
3. 
4. function HomePage({ onOpen, onOpenArchive, level, setLevel, cat, setCat, progress, theme, heroVariant, tweaks, onOpenUserPanel, archiveDay }) {
5.   theme = theme || { bg:'#fff9ef', accent:'#ffc83d', hero1:'#ffe2a8', hero2:'#ffc0a8', border:'#ffb98a', heroTextAccent:'#c14e2a', card:'#fff', chip:'#f0e8d8' };
6. 
7.   const isZh = tweaks && tweaks.language === 'zh';
8.   // In zh mode we show the Chinese summary cards (language === 'zh'); otherwise
9.   // we show English cards at the selected level (Sprout => easy, Tree => middle).
10.   const matchesLanguageLevel = (a) => {
11.     if (isZh) return a.language === 'zh';
12.     return a.language === 'en' && a.level === level;
13.   };
14.   // archiveDay is now a date string "YYYY-MM-DD" (or null for today).
15.   const isArchive = typeof archiveDay === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(archiveDay);
16. 
17.   // When archiveDay changes, ARTICLES is swapped wholesale by loadArchive()
18.   // in index.html. Everything below filters the current ARTICLES in-memory.
19.   const filteredRaw = useMemoH(() => {
20.     const matches = ARTICLES.filter(matchesLanguageLevel);
21.     return (cat === 'All' || !cat) ? matches : matches.filter(a => a.category === cat);
22.   }, [isZh, level, cat, archiveDay]);
23.   // Cap today to 3 per category (editorial layout). Archive also 3 since
24.   // each day's bundle only has 3 per category anyway.
25.   const filtered = useMemoH(() => filteredRaw.slice(0, 3), [filteredRaw]);
26. 
27.   const [calendarOpen, setCalendarOpen] = useStateH(false);
28.   const [recentOpen, setRecentOpen] = useStateH(false);
29. 
30.   // Per-category displayable pool — only the first 3 stories of each category (what's shown on pages)
31.   const displayPool = useMemoH(() => {
32.     const out = [];
33.     for (const c of CATEGORIES) {
34.       out.push(...todayArticles.filter(a => a.category === c.label).slice(0, 3));
35.     }
36.     return out;
37.   }, [todayArticles]);
38.   const poolIds = useMemoH(() => new Set(displayPool.map(a => a.id)), [displayPool]);
39. 
40.   // Pick 1 from each category by default, user can swap (only from the 3-per-category pool)
41.   const [dailyPicks, setDailyPicks] = useStateH(() => {
42.     try { const s = JSON.parse(localStorage.getItem('ohye_daily_picks_v3') || 'null'); if (s && s.length === 3) return s; } catch {}
43.     return null;
44.   });
45.   const defaultPicks = useMemoH(() => {
46.     const out = [];
47.     for (const c of CATEGORIES) {
48.       const first = displayPool.find(a => a.category === c.label);
49.       if (first) out.push(first.id);
50.     }
51.     return out.slice(0, 3);
52.   }, [displayPool]);
53.   const activePicks = (dailyPicks && dailyPicks.every(id => poolIds.has(id))) ? dailyPicks : defaultPicks;
54.   useEffectH(() => { localStorage.setItem('ohye_daily_picks_v3', JSON.stringify(activePicks)); }, [activePicks]);
55.   const swapPick = (idx, newId) => {
56.     const next = [...activePicks]; next[idx] = newId; setDailyPicks(next);
57.   };
58.   const daily3 = useMemoH(() => activePicks.map(id => displayPool.find(a => a.id === id)).filter(Boolean), [activePicks, displayPool]);
59.   const [swapOpen, setSwapOpen] = useStateH(null); // index being swapped
60. 
61.   const byCat = useMemoH(() => {
62.     const m = {};
63.     CATEGORIES.forEach(c => { m[c.label] = ARTICLES.filter(a => a.category === c.label); });
64.     return m;
65.   }, []);
66. 
67.   const minutesToday = progress.minutesToday;
68.   const streak = MOCK_USER.streak;
69.   const goal = MOCK_USER.dailyGoal;
70.   const goalPct = Math.min(1, minutesToday / goal);
71.   const readCount = progress.readToday.length;
72. 
73.   return (
74.     <div style={{background: theme.bg, minHeight:'100vh'}}>
75.       {/* ——————————— HEADER ——————————— */}
76.       <Header level={level} setLevel={setLevel} theme={theme} tweaks={tweaks} onOpenUserPanel={onOpenUserPanel} progress={progress} recentOpen={recentOpen} setRecentOpen={setRecentOpen} onOpenArticle={onOpen} />
77. 
78.       {/* ——————————— ARCHIVE BANNER (when viewing an old day) ——————————— */}
79.       {isArchive && (
80.         <section style={{maxWidth:1180, margin:'16px auto 0', padding:'0 28px'}}>
81.           <div style={{
82.             background:'#1b1230', color:'#fff', borderRadius:18,
83.             padding:'14px 20px', display:'flex', alignItems:'center', gap:14, flexWrap:'wrap',
84.           }}>
85.             <div style={{fontSize:26}}>🗂️</div>
86.             <div style={{flex:1, minWidth:200}}>
87.               <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20, lineHeight:1.1}}>
88.                 {archiveDayLabel(archiveDay)}
89.               </div>
90.               <div style={{fontSize:12, color:'#ffc83d', fontWeight:700, letterSpacing:'.06em', textTransform:'uppercase', marginTop:2}}>
91.                 Reading an old edition
92.               </div>
93.             </div>
94.             <button onClick={()=>onOpenArchive(null)} style={{
95.               background:'#ffc83d', color:'#1b1230', border:'none', borderRadius:999,
96.               padding:'10px 18px', fontWeight:900, fontSize:13, cursor:'pointer', fontFamily:'Nunito, sans-serif',
97.             }}>← Return to today</button>
98.           </div>
99.         </section>
100.       )}
101. 
102.       {/* ——————————— TODAY'S 15 HERO (hidden in archive) ——————————— */}
103.       {!isArchive && (
104.       <section style={{maxWidth:1180, margin:'0 auto', padding:'24px 28px 0'}}>
105.         <div style={{
106.           background:`linear-gradient(135deg, ${theme.hero1} 0%, ${theme.hero2} 100%)`,
107.           borderRadius:28,
108.           padding:'28px 32px',
109.           display:'grid',
110.           gridTemplateColumns: heroVariant === 'streak' ? '1fr 1fr' : '1.2fr 1fr',
111.           gap:28,
112.           alignItems:'center',
113.           position:'relative',
114.           overflow:'hidden',
115.           border:`2px solid ${theme.border}`,
116.         }}>
117.           {/* doodles */}
118.           <svg style={{position:'absolute', right:-20, bottom:-30, opacity:.18}} width="240" height="240" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" stroke="#1b1230" strokeWidth="2" fill="none"/><circle cx="50" cy="50" r="28" stroke="#1b1230" strokeWidth="2" fill="none" strokeDasharray="4 6"/></svg>
119. 
120.           <div style={{position:'relative'}}>
121.             <div style={{fontFamily:'Nunito, sans-serif', fontWeight:800, color: theme.heroTextAccent, fontSize:13, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:6}}>
122.               Hi Mia! 👋 &nbsp;·&nbsp; Thursday, Oct 24
123.             </div>
124.             {heroVariant === 'streak' ? (
125.               <>
126.                 <div style={{display:'inline-flex', alignItems:'center', gap:8, background:'#1b1230', color:'#ffc83d', padding:'6px 14px', borderRadius:999, fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:12, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:12}}>
127.                   🔥 Streak mode
128.                 </div>
129.                 <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:64, lineHeight:0.95, color:'#1b1230', margin:'0 0 10px', letterSpacing:'-0.03em'}}>
130.                   {MOCK_USER.streak} days<br/><span style={{color: theme.heroTextAccent, fontStyle:'italic'}}>on fire.</span>
131.                 </h1>
132.                 <p style={{fontSize:17, color:'#3a2a4a', margin:'0 0 14px', lineHeight:1.5, maxWidth:480}}>
133.                   Read today to hit <b>day {MOCK_USER.streak+1}</b>. You've practiced <b>{minutesToday} of {goal} min</b>.
134.                 </p>
135.                 {/* mini calendar of last 7 days */}
136.                 <div style={{display:'flex', gap:6, marginBottom:16}}>
137.                   {Array.from({length:7}).map((_,i)=>{
138.                     const done = i < 6;
139.                     return (
140.                       <div key={i} style={{width:36, height:44, borderRadius:10, background: done ? '#1b1230' : 'rgba(255,255,255,0.65)', color: done ? '#ffc83d' : '#9a8d7a', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:11, border: i===6 ? `2px dashed ${theme.heroTextAccent}` : 'none'}}>
141.                         <div style={{fontSize:9, opacity:0.7}}>{['M','T','W','T','F','S','S'][i]}</div>
142.                         <div style={{fontSize:14}}>{done ? '✓' : '·'}</div>
143.                       </div>
144.                     );
145.                   })}
146.                 </div>
147.               </>
148.             ) : (
149.               <>
150.                 <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:52, lineHeight:1.02, color:'#1b1230', margin:'0 0 12px', letterSpacing:'-0.02em'}}>
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 150-300)

<details>
<summary>151 lines</summary>

```
150.                 <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:52, lineHeight:1.02, color:'#1b1230', margin:'0 0 12px', letterSpacing:'-0.02em'}}>
151.                   Today's <span style={{background: theme.accent, padding:'0 10px', borderRadius:12, display:'inline-block', transform:'rotate(-2deg)'}}>15 minutes</span>
152.                 </h1>
153.                 <p style={{fontSize:17, color:'#3a2a4a', margin:'0 0 18px', lineHeight:1.5, maxWidth:480}}>
154.                   Read 3 smart stories, learn new words, and win your streak. You've read <b>{readCount} of 3</b> today.
155.                 </p>
156.               </>
157.             )}
158.             <div style={{display:'flex', gap:10, alignItems:'center', flexWrap:'wrap'}}>
159.               <BigButton bg="#1b1230" color="#fff" onClick={() => onOpen(daily3.find(a => !progress.readToday.includes(a.id))?.id || daily3[0].id)}>
160.                 ▶ &nbsp;Start today's read
161.               </BigButton>
162.               <div style={{display:'flex', alignItems:'center', gap:8, padding:'10px 14px', background:'rgba(255,255,255,0.65)', borderRadius:14, fontWeight:700, fontSize:14}}>
163.                 <span style={{fontSize:18}}>⏱️</span>
164.                 <span>{minutesToday}/{goal} min today</span>
165.               </div>
166.             </div>
167.           </div>
168. 
169.           {/* Daily 3 stack — swappable picks */}
170.           <div style={{display:'flex', flexDirection:'column', gap:10, position:'relative'}}>
171.             <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
172.               <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:18, color:'#1b1230'}}>⚡ Today's 3 · 5 min</div>
173.               <div style={{fontSize:11, color:'#6b5c80', fontWeight:700}}>Tap ⇆ to swap</div>
174.             </div>
175.             {daily3.map((a, i) => {
176.               const catColor = CATEGORIES.find(c => c.label === a.category)?.color || '#1b1230';
177.               const alternates = displayPool.filter(x => x.category === a.category && !activePicks.includes(x.id));
178.               const canSwap = alternates.length > 0;
179.               const isSwapping = swapOpen === i;
180.               return (
181.                 <div key={a.id} style={{position:'relative'}}>
182.                   {isSwapping ? (
183.                     <div style={{
184.                       background:'#1b1230', borderRadius:16, padding:10,
185.                       boxShadow:'0 4px 0 rgba(27,18,48,0.15)',
186.                     }}>
187.                       <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'2px 6px 8px'}}>
188.                         <div style={{fontSize:10, fontWeight:800, color:'#ffc83d', textTransform:'uppercase', letterSpacing:'.08em'}}>Pick a different {a.category} story</div>
189.                         <button onClick={()=>setSwapOpen(null)} style={{
190.                           background:'transparent', border:'none', color:'#ffc83d', fontWeight:900, cursor:'pointer', fontSize:16, padding:'0 4px',
191.                         }} title="Close">✕</button>
192.                       </div>
193.                       {alternates.map(alt => (
194.                         <button key={alt.id} onClick={()=>{swapPick(i, alt.id); setSwapOpen(null);}} style={{
195.                           display:'flex', alignItems:'center', gap:10, width:'100%', textAlign:'left',
196.                           background:'rgba(255,255,255,0.06)', color:'#fff',
197.                           border:'none', padding:8, borderRadius:10, cursor:'pointer',
198.                           marginBottom:6,
199.                         }} onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.14)'} onMouseLeave={e=>e.currentTarget.style.background='rgba(255,255,255,0.06)'}>
200.                           <div style={{width:44, height:44, borderRadius:10, flexShrink:0, background:`url(${alt.image}) center/cover, ${catColor}`}}/>
201.                           <div style={{flex:1, minWidth:0}}>
202.                             <div style={{fontWeight:800, fontSize:13, lineHeight:1.25}}>{alt.title}</div>
203.                             <div style={{fontSize:10, opacity:0.7, fontWeight:700, marginTop:3}}>{alt.readMins} min · {alt.tag}</div>
204.                           </div>
205.                         </button>
206.                       ))}
207.                       {alternates.length === 0 && (
208.                         <div style={{color:'#fff', opacity:0.6, fontSize:12, padding:10, textAlign:'center'}}>No other {a.category} stories today.</div>
209.                       )}
210.                     </div>
211.                   ) : (
212.                   <div style={{
213.                     background:'#fff', border:'2px solid #fff', borderRadius:16,
214.                     padding:'10px 12px', display:'flex', gap:12, alignItems:'center',
215.                     boxShadow:'0 2px 0 rgba(27,18,48,0.08)',
216.                   }}>
217.                     <div style={{
218.                       width:36, height:36, borderRadius:12, flexShrink:0,
219.                       background: catColor, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center',
220.                       fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18,
221.                     }}>{i+1}</div>
222.                     <div style={{
223.                       width:52, height:52, borderRadius:12, flexShrink:0,
224.                       background:`url(${a.image}) center/cover, ${catColor}`,
225.                       border:`2px solid ${catColor}`,
226.                     }}/>
227.                     <button onClick={()=>onOpen(a.id)} style={{
228.                       flex:1, minWidth:0, background:'transparent', border:'none', textAlign:'left', cursor:'pointer', padding:0,
229.                     }}>
230.                       <div style={{fontWeight:800, fontSize:14, color:'#1b1230', lineHeight:1.25, marginBottom:4, display:'-webkit-box', WebkitBoxOrient:'vertical', WebkitLineClamp:2, overflow:'hidden'}}>
231.                         {a.title}
232.                       </div>
233.                       <div style={{display:'flex', gap:6, alignItems:'center', fontSize:11, color:'#6b5c80'}}>
234.                         <CatChip cat={a.category} small/>
235.                         <span>· {a.readMins} min</span>
236.                       </div>
237.                     </button>
238.                     {(() => {
239.                       const p = (progress.articleProgress||{})[a.id] || 0;
240.                       const done = progress.readToday.includes(a.id);
241.                       if (done) return <span style={{fontSize:22, color:'#17b3a6'}}>✓</span>;
242.                       if (p > 0) return <span style={{fontSize:11, fontWeight:800, color:'#f4a24c', background:'#fff4e0', padding:'3px 8px', borderRadius:999, border:'1.5px solid #f4a24c'}}>{p}%</span>;
243.                       return null;
244.                     })()}
245.                     {canSwap && (
246.                       <button onClick={()=>setSwapOpen(i)} title={`Pick a different ${a.category} story`} style={{
247.                         background:'transparent', color:'#6b5c80',
248.                         border:'2px solid #f0e8d8', borderRadius:10,
249.                         width:32, height:32, cursor:'pointer', fontSize:14, fontWeight:900,
250.                         display:'flex', alignItems:'center', justifyContent:'center',
251.                       }}>⇆</button>
252.                     )}
253.                   </div>
254.                   )}
255.                 </div>
256.               );
257.             })}
258.           </div>
259.         </div>
260.       </section>
261.       )}
262. 
263.       {/* ——————————— CATEGORY TABS ——————————— */}
264.       <section style={{maxWidth:1180, margin: isArchive ? '24px auto 0' : '32px auto 0', padding:'0 28px', position:'relative'}}>
265.         <div style={{display:'flex', gap:12, flexWrap:'wrap', alignItems:'center'}}>
266.           {CATEGORIES.map(c => (
267.             <CatTab key={c.id} label={c.label} emoji={c.emoji} color={c.color} bg={c.bg} active={cat===c.label} onClick={()=>setCat(c.label)} />
268.           ))}
269.           {!isArchive && (
270.             <button onClick={()=>setCalendarOpen(v=>!v)} style={{
271.               background: calendarOpen ? '#1b1230' : '#fff', color: calendarOpen ? '#ffc83d' : '#1b1230',
272.               border: calendarOpen ? '2px solid #1b1230' : '2px dashed #c9b99a',
273.               borderRadius:999, padding:'8px 16px', fontWeight:800, fontSize:13, cursor:'pointer',
274.               display:'inline-flex', alignItems:'center', gap:6, fontFamily:'Nunito, sans-serif',
275.             }}>📅 View old news</button>
276.           )}
277.           <div style={{flex:1}}/>
278.           <span style={{fontSize:13, color:'#7a6b8c', fontWeight:600}}>
279.             {isZh ? (<>Reading in <b style={{color:'#1b1230'}}>中文</b> · summary only</>) : (<>Showing stories at <b style={{color:'#1b1230'}}>{level}</b> level</>)}
280.           </span>
281.         </div>
282.         {calendarOpen && (
283.           <DatePopover onPick={(d)=>{setCalendarOpen(false); onOpenArchive(d);}} onClose={()=>setCalendarOpen(false)} />
284.         )}
285.       </section>
286. 
287.       {/* ——————————— ARTICLES GRID ——————————— */}
288.       <section style={{maxWidth:1180, margin:'20px auto 0', padding:'0 28px 60px'}}>
289.         {filtered.length === 0 ? (
290.           <div style={{textAlign:'center', padding:'40px 20px', color:'#9a8d7a', background:'#fff', borderRadius:16, border:'2px dashed #f0e8d8'}}>
291.             <div style={{fontSize:36, marginBottom:8}}>🌱</div>
292.             <div style={{fontWeight:800, color:'#1b1230', marginBottom:4}}>No stories here</div>
293.             <div style={{fontSize:13}}>Try a different level from your profile, or a different day.</div>
294.           </div>
295.         ) : filtered.length === 3 && !isArchive ? (
296.           /* Editorial layout: big feature on top (photo left, article right) + 2 companions below */
297.           <div style={{display:'flex', flexDirection:'column', gap:20}}>
298.             <ArticleCard article={filtered[0]} onOpen={()=>onOpen(filtered[0].id)} read={progress.readToday.includes(filtered[0].id)} pct={(progress.articleProgress||{})[filtered[0].id]} variant="feature" />
299.             <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
300.               <ArticleCard article={filtered[1]} onOpen={()=>onOpen(filtered[1].id)} read={progress.readToday.includes(filtered[1].id)} pct={(progress.articleProgress||{})[filtered[1].id]} variant="normal" />
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/article.jsx.**

/Users/jiong/myprojects/news-v2/website/article.jsx (lines 1-150)

<details>
<summary>150 lines</summary>

```
1. // Article detail page — News Oh,Ye!
2. const { useState: useStateA, useMemo: useMemoA, useEffect: useEffectA } = React;
3. 
4. // Format an ISO-8601 timestamp as "Apr 24, 2026". Returns "" on bad input
5. // so callers can safely conditionally render.
6. function formatDate(iso) {
7.   if (!iso) return '';
8.   const d = new Date(iso);
9.   if (isNaN(d.getTime())) return '';
10.   return d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
11. }
12. 
13. function ArticlePage({ articleId, onBack, onComplete, progress, setProgress }) {
14.   const baseArticle = ARTICLES.find(a => a.id === articleId) || ARTICLES[0];
15.   const [tab, setTab] = useStateA('read');
16.   const [tabsVisited, setTabsVisited] = useStateA({ read: true });
17.   const [detail, setDetail] = useStateA(null);
18.   const [detailError, setDetailError] = useStateA(null);
19. 
20.   // Lazy-fetch v1 detail payload for this article. Chinese cards (noDetail) are
21.   // routed away before reaching this page, so we only fetch English variants.
22.   useEffectA(() => {
23.     if (!baseArticle || baseArticle.noDetail) { setDetail(null); return; }
24.     let cancelled = false;
25.     setDetail(null);
26.     setDetailError(null);
27.     const payloadLevel = baseArticle.level === 'Sprout' ? 'easy' : 'middle';
28.     // Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
29.     // prefix; today's content stays local.
30.     const detailBase = baseArticle.archiveDate
31.       ? `${window.ARCHIVE_BASE}/${baseArticle.archiveDate}/article_payloads`
32.       : 'article_payloads';
33.     const url = `${detailBase}/payload_${baseArticle.storyId}/${payloadLevel}.json`;
34.     fetch(url)
35.       .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
36.       .then(d => {
37.         if (cancelled) return;
38.         // Map v1 field shapes to the prototype's expected shape.
39.         // v1 detail pattern: full body lives in `summary`; `background_read` is
40.         // supplementary context (for the Analyze tab), not the body.
41.         const bgRead = Array.isArray(d.background_read)
42.           ? d.background_read.join('\n\n')
43.           : (typeof d.background_read === 'string' ? d.background_read : '');
44.         const mapped = {
45.           body: d.summary || '',                        // FULL regenerated article body
46.           summary: d.summary || baseArticle.summary,
47.           backgroundRead: bgRead,                       // shown on Analyze tab
48.           whyItMatters: d.why_it_matters || '',
49.           keywords: (d.keywords || []).map(k => ({ term: k.term, def: k.explanation })),
50.           quiz: (d.questions || []).map(q => {
51.             const idx = q.options.findIndex(opt => opt === q.correct_answer);
52.             return { q: q.question, options: q.options, a: Math.max(0, idx) };
53.           }),
54.           discussion: (d.perspectives || []).map(p => `${p.perspective}: ${p.description}`),
55.           articleStructure: Array.isArray(d.Article_Structure) ? d.Article_Structure : [],
56.         };
57.         setDetail(mapped);
58.       })
59.       .catch(e => { if (!cancelled) { console.warn('[article] detail fetch failed', url, e); setDetailError(e); } });
60.     return () => { cancelled = true; };
61.   }, [articleId]);
62. 
63.   // Merged article object: prefer detail fields when loaded, fall back to the
64.   // listing-level stub so the title block + header render even before detail
65.   // arrives.
66.   const article = useMemoA(() => {
67.     const d = detail || {};
68.     return {
69.       ...baseArticle,
70.       summary: d.summary || baseArticle.summary,
71.       body: d.body || '',
72.       backgroundRead: d.backgroundRead || '',
73.       whyItMatters: d.whyItMatters || '',
74.       keywords: d.keywords || [],
75.       quiz: d.quiz || [],
76.       discussion: d.discussion || [],
77.       articleStructure: d.articleStructure || [],
78.     };
79.   }, [articleId, detail]);
80. 
81.   // Each step completion bumps progress by 25%: read→25, analyze→50, quiz→75, discuss→100
82.   const bumpProgress = (pct) => {
83.     setProgress(p => {
84.       const ap = p.articleProgress || {};
85.       const cur = ap[article.id] || 0;
86.       if (cur >= pct) return p;
87.       const next = { ...p, articleProgress: { ...ap, [article.id]: pct } };
88.       // When reaching 100, mark as fully read + add minutes
89.       if (pct === 100 && !p.readToday.includes(article.id)) {
90.         next.readToday = [...p.readToday, article.id];
91.         next.minutesToday = (p.minutesToday || 0) + article.readMins;
92.       }
93.       return next;
94.     });
95.   };
96.   const [expandedKw, setExpandedKw] = useStateA(null);
97.   const [quizIdx, setQuizIdx] = useStateA(0);
98.   const [quizAns, setQuizAns] = useStateA([]);
99.   const [quizShow, setQuizShow] = useStateA(false);
100.   const [confetti, setConfetti] = useStateA(false);
101. 
102.   const stages = [
103.     { id:'read', label:'Read & Words', emoji:'📖' },
104.     { id:'analyze', label:'Background', emoji:'🔍' },
105.     { id:'quiz', label:'Quiz', emoji:'🎯' },
106.     { id:'discuss', label:'Think', emoji:'💭' },
107.   ];
108. 
109.   const catColor = getCatColor(article.category);
110. 
111.   // Build paragraphs for the Read tab from detail.body (preferred) or a
112.   // sentence-grouped fallback over the summary while detail is loading.
113.   const paragraphs = useMemoA(() => {
114.     const text = article.body || article.summary || '';
115.     if (article.body) {
116.       // Detail body has explicit paragraph breaks ("\n\n") we can honor.
117.       const paras = text.split(/\n\n+/).map(s => s.trim()).filter(Boolean);
118.       if (paras.length > 0) return paras;
119.     }
120.     // Fallback: group sentences into 3-sentence paragraphs (prototype behavior).
121.     const sentences = text.split(/(?<=\.)\s+/);
122.     const groups = [];
123.     for (let i=0; i<sentences.length; i+=3) groups.push(sentences.slice(i, i+3).join(' '));
124.     return groups;
125.   }, [article.id, article.body, article.summary]);
126. 
127.   const switchTab = (id) => {
128.     setTab(id);
129.     setTabsVisited(v => ({...v, [id]: true}));
130.   };
131. 
132.   // Block tabs until detail is loaded. Header/title block still render so the
133.   // user gets feedback while the payload arrives.
134.   const detailReady = !!detail;
135. 
136.   return (
137.     <div style={{background:'#fff9ef', minHeight:'100vh'}}>
138.       {/* ——— Top bar ——— */}
139.       <div style={{background:'#fff9ef', borderBottom:'2px solid #f0e8d8', position:'sticky', top:0, zIndex:30}}>
140.         <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:14}}>
141.           <button onClick={onBack} style={{
142.             background:'#fff', border:'2px solid #f0e8d8', borderRadius:14, padding:'8px 14px',
143.             fontWeight:800, fontSize:14, cursor:'pointer', color:'#1b1230',
144.             display:'inline-flex', alignItems:'center', gap:6,
145.           }}>← Back</button>
146.           <div style={{display:'flex', alignItems:'center', gap:10}}>
147.             <OhYeLogo size={32}/>
148.             <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>News Oh,Ye!</div>
149.           </div>
150.           <div style={{flex:1}}/>
```

</details>


### 💬 Copilot

Let me continue reviewing article.jsx and check for potential issues with URL construction and archive loading:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/article.jsx.**

/Users/jiong/myprojects/news-v2/website/article.jsx (lines 200-350)

<details>
<summary>151 lines</summary>

```
200.           </div>
201.         </div>
202. 
203.         {/* ——— TABS CONTENT ——— */}
204.         {!detailReady && !detailError && (
205.           <div style={{background:'#fff', borderRadius:22, padding:'40px 32px', border:'2px dashed #f0e8d8', textAlign:'center', color:'#6b5c80'}}>
206.             <div style={{fontSize:36, marginBottom:10}}>📡</div>
207.             <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', marginBottom:6}}>Loading the full story…</div>
208.             <div style={{fontSize:13}}>Fetching keywords, quiz, and background.</div>
209.           </div>
210.         )}
211.         {detailError && (
212.           <div style={{background:'#fff', borderRadius:22, padding:'40px 32px', border:'2px solid #ffb98a', textAlign:'center', color:'#6b5c80'}}>
213.             <div style={{fontSize:36, marginBottom:10}}>⚠️</div>
214.             <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', marginBottom:6}}>Couldn't load this story.</div>
215.             <div style={{fontSize:13}}>Try again in a moment.</div>
216.           </div>
217.         )}
218. 
219.         {detailReady && tab === 'read' && (
220.           <ReadAndWordsTab
221.             article={article}
222.             paragraphs={paragraphs}
223.             expanded={expandedKw}
224.             setExpanded={setExpandedKw}
225.             onFinish={() => { bumpProgress(25); switchTab('analyze'); }}
226.           />
227.         )}
228. 
229.         {detailReady && tab === 'analyze' && (
230.           <AnalyzeTab article={article} paragraphs={paragraphs} onNext={()=>{ bumpProgress(50); switchTab('quiz'); }} />
231.         )}
232. 
233.         {detailReady && tab === 'quiz' && (
234.           <QuizTab
235.             article={article} paragraphs={paragraphs}
236.             quizIdx={quizIdx} setQuizIdx={setQuizIdx}
237.             quizAns={quizAns} setQuizAns={setQuizAns}
238.             quizShow={quizShow} setQuizShow={setQuizShow}
239.             onFinish={() => { bumpProgress(75); setConfetti(true); setTimeout(()=>setConfetti(false), 1800); switchTab('discuss'); }}
240.           />
241.         )}
242. 
243.         {detailReady && tab === 'discuss' && (
244.           <DiscussTab article={article} paragraphs={paragraphs} onDone={()=>{ bumpProgress(100); onComplete(); }} />
245.         )}
246.       </div>
247. 
248.       {confetti && <Confetti/>}
249.     </div>
250.   );
251. }
252. 
253. // ——— Highlight keywords in a text string ———
254. // Matches base terms AND common English inflections (ban → banned, fine → fined).
255. // The base term is captured as group 1 so we can look up the definition even
256. // when the matched text is an inflected form like "banned".
257. function highlightText(text, keywords, catColor) {
258.   if (!keywords || !keywords.length) return [text];
259.   const termMap = {};
260.   keywords.forEach(k => { termMap[k.term.toLowerCase()] = k; });
261.   // Sort longer-first so multi-word terms ("prediction market") win over
262.   // single-word subsets ("prediction").
263.   const terms = keywords.map(k => k.term).sort((a, b) => b.length - a.length);
264.   const SUFFIX = '(?:s|es|ed|d|ing|ning|ned|ting|ted|er|ers)?';
265.   const alt = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
266.   const pattern = new RegExp(`\\b(${alt})${SUFFIX}\\b`, 'gi');
267.   const result = [];
268.   let last = 0, m, idx = 0;
269.   while ((m = pattern.exec(text)) !== null) {
270.     if (m.index > last) result.push(text.substring(last, m.index));
271.     const base = (m[1] || '').toLowerCase();   // captured base term
272.     const kw = termMap[base];
273.     result.push(<KwTip key={`kw-${idx++}`} text={m[0]} def={kw?.def || ''} color={catColor}/>);
274.     last = m.index + m[0].length;
275.   }
276.   if (last < text.length) result.push(text.substring(last));
277.   return result;
278. }
279. 
280. function KwTip({ text, def, color }) {
281.   const [show, setShow] = useStateA(false);
282.   return (
283.     <span style={{position:'relative', display:'inline-block'}}
284.           onMouseEnter={()=>setShow(true)} onMouseLeave={()=>setShow(false)}>
285.       <span style={{
286.         color, fontWeight:800, borderBottom:`2px dotted ${color}`,
287.         cursor:'help', padding:'0 1px',
288.       }}>{text}</span>
289.       {show && (
290.         <span style={{
291.           position:'absolute', bottom:'calc(100% + 8px)', left:'50%', transform:'translateX(-50%)',
292.           background:'#1b1230', color:'#fff', padding:'8px 12px', borderRadius:10,
293.           fontSize:12, fontWeight:600, whiteSpace:'normal', minWidth:180, maxWidth:260, zIndex:40,
294.           lineHeight:1.4, pointerEvents:'none',
295.           boxShadow:'0 6px 20px rgba(27,18,48,0.25)',
296.         }}>
297.           <b style={{color:'#ffc83d'}}>{text}:</b> {def}
298.         </span>
299.       )}
300.     </span>
301.   );
302. }
303. 
304. // ——————— READ & WORDS TAB (combined) ———————
305. function ReadAndWordsTab({ article, paragraphs, expanded, setExpanded, onFinish }) {
306.   const catColor = getCatColor(article.category);
307.   const [gameOpen, setGameOpen] = useStateA(false);
308.   return (
309.     <div style={{display:'grid', gridTemplateColumns:'1.6fr 1fr', gap:24}}>
310.       <div style={{background:'#fff', borderRadius:22, padding:'30px 34px', border:'2px solid #f0e8d8'}}>
311.         <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:18, paddingBottom:14, borderBottom:'2px dashed #f0e8d8'}}>
312.           <div style={{fontSize:26}}>📖</div>
313.           <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:22, color:'#1b1230', margin:0}}>The Story</h2>
314.           <div style={{flex:1}}/>
315.           <div style={{fontSize:12, color:'#9a8d7a', fontWeight:700}}>Hover on the colored words!</div>
316.         </div>
317.         {paragraphs.map((p, i) => (
318.           <p key={i} style={{fontSize:18, lineHeight:1.7, color:'#2a1f3d', marginBottom:16, fontFamily:'Nunito, sans-serif'}}>
319.             {i === 0 && <span style={{float:'left', fontSize:48, fontFamily:'Fraunces, serif', fontWeight:900, lineHeight:.9, marginRight:8, marginTop:4, color: catColor}}>{p[0]}</span>}
320.             {highlightText(i === 0 ? p.substring(1) : p, article.keywords, catColor)}
321.           </p>
322.         ))}
323.         <div style={{display:'flex', justifyContent:'center', marginTop:24, paddingTop:20, borderTop:'2px dashed #f0e8d8'}}>
324.           <BigButton onClick={onFinish} bg="#17b3a6" color="#fff">
325.             ✓ I read it! Next: Background →
326.           </BigButton>
327.         </div>
328.       </div>
329. 
330.       <aside style={{display:'flex', flexDirection:'column', gap:14}}>
331.         <div style={{background:'#fff', border:'2px solid #f0e8d8', borderRadius:18, padding:18}}>
332.           <div style={{display:'flex', alignItems:'center', gap:8, marginBottom:12}}>
333.             <div style={{fontSize:22}}>🔑</div>
334.             <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:17, color:'#1b1230'}}>Word Treasure</div>
335.           </div>
336.           <div style={{display:'flex', flexDirection:'column', gap:8}}>
337.             {article.keywords.map((k, i) => (
338.               <KeywordCard key={i} kw={k} idx={i} expanded={expanded===i} onToggle={()=>setExpanded(expanded===i ? null : i)}/>
339.             ))}
340.           </div>
341.           {article.keywords.length >= 2 && (
342.             <button onClick={()=>setGameOpen(true)} style={{
343.               marginTop:12, width:'100%', background:`linear-gradient(135deg, ${catColor}, #1b1230)`,
344.               color:'#fff', border:'none', borderRadius:12, padding:'10px 12px',
345.               fontWeight:800, fontSize:13, cursor:'pointer', fontFamily:'Nunito, sans-serif',
346.               display:'flex', alignItems:'center', justifyContent:'center', gap:8,
347.               boxShadow:'0 2px 0 rgba(27,18,48,0.1)',
348.             }}>🎮 Match the meanings</button>
349.           )}
350.         </div>
```

</details>


### ✅ `grep`

**ARTICLE_STRUCTURE|mind.tree|renderTree**

"ARTICLE_STRUCTURE|mind.tree|renderTree" in *.jsx (website)

```
/Users/jiong/myprojects/news-v2/website/article.jsx:  // Tree level: render Article_Structure as a nested mind-tree preserving
/Users/jiong/myprojects/news-v2/website/article.jsx:      {/* Right: Structure (5W for easy, mind-tree for middle) */}
```


### ✅ `grep`

**window.ARTICLES**

"window.ARTICLES" in *.jsx (website)

```
/Users/jiong/myprojects/news-v2/website/data.jsx:// Consumes v1 listing payloads and exposes window.ARTICLES, window.CATEGORIES,
/Users/jiong/myprojects/news-v2/website/data.jsx:// Callable from the app: swap window.ARTICLES to point at a past day's
/Users/jiong/myprojects/news-v2/website/data.jsx:  window.ARTICLES = list;
/Users/jiong/myprojects/news-v2/website/data.jsx:window.ARTICLES = [];
/Users/jiong/myprojects/news-v2/website/data.jsx:  window.ARTICLES = list;
```


### 💬 Copilot

Let me check for the article structure rendering and potential template-injection risks:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/article.jsx.**

/Users/jiong/myprojects/news-v2/website/article.jsx (lines 400-550)

<details>
<summary>151 lines</summary>

```
400.           {keywords.map((kw, i) => {
401.             const isRight = checked && String(picks[i]) === String(i);
402.             const isWrong = checked && picks[i] !== '' && String(picks[i]) !== String(i);
403.             return (
404.               <div key={i} style={{display:'flex', gap:10, alignItems:'center'}}>
405.                 <div style={{
406.                   flex:'0 0 30%', background: catColor+'22', color: catColor,
407.                   fontWeight:800, padding:'10px 12px', borderRadius:10, fontSize:14, textAlign:'center',
408.                 }}>{kw.term}</div>
409.                 <select value={picks[i]} disabled={checked} onChange={e=>{
410.                   const v = e.target.value;
411.                   setPicks(prev => { const n = [...prev]; n[i] = v; return n; });
412.                 }} style={{
413.                   flex:1, padding:'10px 12px', borderRadius:10, fontSize:13,
414.                   border: `2px solid ${isRight ? '#17b3a6' : isWrong ? '#ff6b5b' : '#f0e8d8'}`,
415.                   background:'#fff9ef', color:'#1b1230', fontFamily:'Nunito, sans-serif', cursor: checked ? 'default' : 'pointer',
416.                 }}>
417.                   <option value="">Pick a meaning…</option>
418.                   {shuffledDefs.map(({ def, idx }) => (
419.                     <option key={idx} value={idx}>{def}</option>
420.                   ))}
421.                 </select>
422.               </div>
423.             );
424.           })}
425.         </div>
426.         {checked ? (
427.           <div style={{marginTop:16, background: correct === total ? '#e0f6f3' : '#fff4c2', borderRadius:14, padding:'14px 16px', textAlign:'center'}}>
428.             <div style={{fontSize:28, marginBottom:4}}>{'⭐'.repeat(stars)}{'☆'.repeat(5 - stars)}</div>
429.             <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:18, color:'#1b1230'}}>
430.               {correct} / {total} correct {correct === total ? '🎉' : ''}
431.             </div>
432.             <div style={{display:'flex', gap:8, marginTop:12, justifyContent:'center'}}>
433.               <button onClick={()=>{setPicks(Array(total).fill('')); setChecked(false);}} style={{
434.                 background: catColor, color:'#fff', border:'none', borderRadius:10, padding:'10px 18px',
435.                 fontWeight:800, fontSize:13, cursor:'pointer',
436.               }}>↻ Try again</button>
437.               <button onClick={onClose} style={{
438.                 background:'#fff9ef', color:'#1b1230', border:'2px solid #f0e8d8', borderRadius:10, padding:'10px 18px',
439.                 fontWeight:800, fontSize:13, cursor:'pointer',
440.               }}>Done</button>
441.             </div>
442.           </div>
443.         ) : (
444.           <div style={{display:'flex', justifyContent:'flex-end', marginTop:16}}>
445.             <button onClick={()=>setChecked(true)} disabled={picks.some(p => p === '')} style={{
446.               background: picks.some(p => p === '') ? '#d8cfb8' : '#ffc83d',
447.               color:'#1b1230', border:'none', borderRadius:10, padding:'10px 22px',
448.               fontWeight:800, fontSize:14, cursor: picks.some(p => p === '') ? 'not-allowed' : 'pointer',
449.             }}>Check answers</button>
450.           </div>
451.         )}
452.       </div>
453.     </div>
454.   );
455. }
456. 
457. function KeywordCard({ kw, idx, expanded, onToggle }) {
458.   const palette = [
459.     {bg:'#ffece8', c:'#ff6b5b'}, {bg:'#e0f6f3', c:'#17b3a6'}, {bg:'#eee5ff', c:'#9061f9'},
460.     {bg:'#fff4c2', c:'#c9931f'}, {bg:'#ffe4ef', c:'#ff6ba0'},
461.   ][idx % 5];
462.   return (
463.     <button onClick={onToggle} style={{
464.       background: expanded ? palette.c : palette.bg,
465.       color: expanded ? '#fff' : '#1b1230',
466.       border:'none', borderRadius:12, padding:'12px 14px', textAlign:'left',
467.       cursor:'pointer', display:'flex', flexDirection:'column', gap:4,
468.       transition:'all .2s',
469.       boxShadow:'0 2px 0 rgba(27,18,48,0.06)',
470.     }}>
471.       <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:16, color: expanded ? '#fff' : palette.c}}>{kw.term}</div>
472.       {expanded && <div style={{fontSize:12, lineHeight:1.4}}>{kw.def}</div>}
473.       {!expanded && <div style={{fontSize:11, fontWeight:700, opacity:.65}}>Tap to reveal →</div>}
474.     </button>
475.   );
476. }
477. 
478. // ——————— ANALYZE TAB (Background + Structure, with article reference) ———————
479. function AnalyzeTab({ article, paragraphs, onNext }) {
480.   const [articleOpen, setArticleOpen] = useStateA(false);
481.   const catColor = getCatColor(article.category);
482. 
483.   const isTree = article.level === 'Tree';
484. 
485.   // Background paragraphs: prefer payload's background_read (deeper at middle,
486.   // simpler at easy). Fall back to a generic intro sentence only if missing.
487.   const bgParagraphs = (article.backgroundRead || '').trim()
488.     ? article.backgroundRead.split(/\n\n+/).map(s => s.trim()).filter(Boolean)
489.     : [`This story comes from ${article.source}, a ${article.category === 'Science' ? 'science source' : 'news source'} that covers stories for kids. When you read, think about WHO is doing something, WHAT is happening, WHERE it takes place, and WHY it matters.`];
490. 
491.   // Easy level: parse WHO/WHAT/WHERE/WHY into a 5W grid.
492.   // Tree level: render Article_Structure as a nested mind-tree preserving
493.   // leading-whitespace + └─/├─ indentation from the payload.
494.   let structureBlock = null;
495.   if (isTree) {
496.     structureBlock = (
497.       <div style={{display:'flex', flexDirection:'column', gap:6}}>
498.         {(article.articleStructure || []).map((line, i) => {
499.           const raw = typeof line === 'string' ? line : String(line);
500.           const m = raw.match(/^(\s*)(.*)$/);
501.           const indent = m ? m[1].length : 0;
502.           const text = m ? m[2] : raw;
503.           // Split "LABEL: rest" so label can be bolded
504.           const lm = text.match(/^([A-Z][A-Z \/]*[A-Z]|[A-Z][a-z]+):\s*(.*)$/);
505.           return (
506.             <div key={i} style={{
507.               paddingLeft: indent * 8,
508.               fontSize:14, lineHeight:1.55, color:'#2a1f3d',
509.               fontFamily:'Nunito, sans-serif',
510.             }}>
511.               {lm ? (
512.                 <span>
513.                   <span style={{fontWeight:800, color:'#1b1230'}}>{lm[1]}</span>
514.                   <span>: </span>
515.                   <span>{highlightText(lm[2], article.keywords, catColor)}</span>
516.                 </span>
517.               ) : (
518.                 <span>{highlightText(text, article.keywords, catColor)}</span>
519.               )}
520.             </div>
521.           );
522.         })}
523.       </div>
524.     );
525.   } else {
526.     const structure = {};
527.     for (const line of (article.articleStructure || [])) {
528.       const m = typeof line === 'string' ? line.match(/^\s*([A-Za-z]+)\s*:\s*(.*)$/) : null;
529.       if (m) structure[m[1].toUpperCase()] = m[2].trim();
530.     }
531.     const who = structure.WHO || (article.title.split(' ').slice(0, 3).join(' ') + '…');
532.     const what = structure.WHAT || ((article.summary || '').split('.')[0] + '.');
533.     const where = structure.WHERE || (article.category === 'Science' ? 'In labs, field studies, or around the world' : 'Mentioned in the story');
534.     const why = structure.WHY || `It matters because it affects ${article.category === 'Science' ? 'how we understand the world' : 'people, animals, or the planet'}.`;
535.     structureBlock = (
536.       <div style={{display:'flex', flexDirection:'column', gap:10}}>
537.         <WRow label="Who" emoji="👤" value={who}/>
538.         <WRow label="What" emoji="💡" value={what}/>
539.         <WRow label="Where" emoji="📍" value={where}/>
540.         <WRow label="Why" emoji="❓" value={why}/>
541.       </div>
542.     );
543.   }
544. 
545.   return (
546.     <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
547.       {/* Left: Background */}
548.       <div style={{background:'#fff', borderRadius:22, padding:'26px 30px', border:'2px solid #f0e8d8'}}>
549.         <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
550.           <div style={{fontSize:26}}>🧭</div>
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/article.jsx.**

/Users/jiong/myprojects/news-v2/website/article.jsx (lines 550-700)

<details>
<summary>151 lines</summary>

```
550.           <div style={{fontSize:26}}>🧭</div>
551.           <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Background you need</h2>
552.         </div>
553.         {bgParagraphs.map((p, i) => (
554.           <p key={i} style={{fontSize:15, lineHeight:1.7, color:'#2a1f3d', margin: i === 0 ? 0 : '12px 0 0'}}>
555.             {highlightText(p, article.keywords, catColor)}
556.           </p>
557.         ))}
558.       </div>
559. 
560.       {/* Right: Structure (5W for easy, mind-tree for middle) */}
561.       <div style={{background:'#fff', borderRadius:22, padding:'26px 30px', border:'2px solid #f0e8d8'}}>
562.         <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
563.           <div style={{fontSize:26}}>🔍</div>
564.           <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Break it down</h2>
565.         </div>
566.         {structureBlock}
567.       </div>
568. 
569.       {/* Full-width: Article reference collapsible */}
570.       <div style={{gridColumn:'span 2', background:'#fff9ef', border:'2px solid #f0e8d8', borderRadius:22, padding:0, overflow:'hidden'}}>
571.         <button onClick={()=>setArticleOpen(!articleOpen)} style={{
572.           width:'100%', background:'transparent', border:'none', padding:'16px 22px',
573.           display:'flex', alignItems:'center', gap:10, cursor:'pointer', color:'#1b1230',
574.           fontFamily:'Nunito, sans-serif',
575.         }}>
576.           <div style={{fontSize:20}}>📖</div>
577.           <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:16, flex:1, textAlign:'left'}}>
578.             {articleOpen ? 'Hide the story' : 'Peek at the story again'}
579.           </div>
580.           <div style={{fontSize:20, transform: articleOpen ? 'rotate(180deg)' : 'rotate(0)', transition:'transform .2s'}}>⌄</div>
581.         </button>
582.         {articleOpen && (
583.           <div style={{padding:'0 22px 22px', borderTop:'2px dashed #f0e8d8'}}>
584.             <div style={{paddingTop:16}}>
585.               {paragraphs.map((p, i) => (
586.                 <p key={i} style={{fontSize:15, lineHeight:1.65, color:'#2a1f3d', marginBottom:12}}>
587.                   {highlightText(p, article.keywords, catColor)}
588.                 </p>
589.               ))}
590.             </div>
591.           </div>
592.         )}
593.       </div>
594. 
595.       <div style={{gridColumn:'span 2', display:'flex', justifyContent:'center', marginTop:8}}>
596.         <BigButton bg="#ffc83d" color="#1b1230" onClick={onNext}>Ready for the quiz →</BigButton>
597.       </div>
598.     </div>
599.   );
600. }
601. 
602. function WRow({ label, emoji, value }) {
603.   return (
604.     <div style={{display:'flex', gap:12, background:'#fff9ef', padding:'10px 14px', borderRadius:12, border:'1.5px solid #f0e8d8'}}>
605.       <div style={{fontSize:22}}>{emoji}</div>
606.       <div style={{flex:1}}>
607.         <div style={{fontSize:11, fontWeight:800, color:'#9061f9', letterSpacing:'.08em', textTransform:'uppercase'}}>{label}</div>
608.         <div style={{fontSize:14, color:'#1b1230', lineHeight:1.4, fontWeight:600}}>{value}</div>
609.       </div>
610.     </div>
611.   );
612. }
613. 
614. // ——————— QUIZ TAB (split view with article reference) ———————
615. function QuizTab({ article, paragraphs, quizIdx, setQuizIdx, quizAns, setQuizAns, quizShow, setQuizShow, onFinish }) {
616.   const q = article.quiz[quizIdx];
617.   const done = quizAns.length === article.quiz.length && quizAns.every(a => a !== undefined);
618.   const correct = quizAns.filter((a,i) => a === article.quiz[i].a).length;
619.   const catColor = getCatColor(article.category);
620. 
621.   if (done) {
622.     return (
623.       <div style={{background:'#fff', borderRadius:22, padding:'44px', border:'2px solid #f0e8d8', textAlign:'center', maxWidth:560, margin:'0 auto'}}>
624.         <div style={{fontSize:64, marginBottom:8}}>🎉</div>
625.         <h2 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:36, color:'#1b1230', margin:'0 0 6px'}}>
626.           {correct === article.quiz.length ? 'Perfect!' : correct >= article.quiz.length/2 ? 'Nice work!' : 'Good try!'}
627.         </h2>
628.         <p style={{fontSize:16, color:'#6b5c80', margin:'0 0 18px'}}>
629.           You got <b>{correct}</b> out of <b>{article.quiz.length}</b> right.
630.         </p>
631.         <div style={{marginBottom:20}}><StarMeter filled={correct} total={article.quiz.length}/></div>
632.         <div style={{display:'inline-flex', gap:10, padding:'10px 16px', background:'#fff4c2', borderRadius:14, marginBottom:28}}>
633.           <span style={{fontWeight:800, color:'#8a6d00'}}>⭐ +{article.xp} XP earned!</span>
634.         </div>
635.         <div style={{display:'flex', justifyContent:'center', gap:12}}>
636.           <BigButton bg="#fff" color="#1b1230" onClick={()=>{ setQuizAns([]); setQuizIdx(0); setQuizShow(false);}} style={{boxShadow:'0 4px 0 rgba(0,0,0,0.08)', border:'2px solid #f0e8d8'}}>🔁 Try again</BigButton>
637.           <BigButton bg="#17b3a6" color="#fff" onClick={onFinish}>Next: Think time →</BigButton>
638.         </div>
639.       </div>
640.     );
641.   }
642. 
643.   return (
644.     <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:24}}>
645.       {/* Left: article reference (scrollable, sticky) */}
646.       <div style={{background:'#fff', borderRadius:22, padding:'24px 28px', border:'2px solid #f0e8d8', position:'sticky', top:90, maxHeight:'calc(100vh - 110px)', overflow:'auto'}}>
647.         <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14, paddingBottom:12, borderBottom:'2px dashed #f0e8d8'}}>
648.           <div style={{fontSize:22}}>📖</div>
649.           <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:17, color:'#1b1230'}}>Look back at the story</div>
650.         </div>
651.         <div>
652.           {paragraphs.map((p, i) => (
653.             <p key={i} style={{fontSize:14.5, lineHeight:1.65, color:'#2a1f3d', marginBottom:12}}>
654.               {highlightText(p, article.keywords, catColor)}
655.             </p>
656.           ))}
657.         </div>
658.       </div>
659. 
660.       {/* Right: quiz */}
661.       <div style={{background:'#fff', borderRadius:22, padding:'28px 32px', border:'2px solid #f0e8d8'}}>
662.         <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16}}>
663.           <div style={{display:'flex', alignItems:'center', gap:10}}>
664.             <div style={{fontSize:24}}>🎯</div>
665.             <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Quick quiz</h2>
666.           </div>
667.           <div style={{fontSize:13, fontWeight:800, color:'#6b5c80'}}>Q {quizIdx+1}/{article.quiz.length}</div>
668.         </div>
669.         <div style={{height:8, background:'#f0e8d8', borderRadius:999, marginBottom:22, overflow:'hidden'}}>
670.           <div style={{height:'100%', width:`${(quizIdx/article.quiz.length)*100}%`, background:'#17b3a6', borderRadius:999, transition:'width .4s'}}/>
671.         </div>
672. 
673.         <h3 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:22, color:'#1b1230', marginBottom:18, lineHeight:1.25}}>{q.q}</h3>
674. 
675.         <div style={{display:'flex', flexDirection:'column', gap:10}}>
676.           {q.options.map((opt, i) => {
677.             const picked = quizShow && quizAns[quizIdx] === i;
678.             const isRight = quizShow && i === q.a;
679.             const isWrong = quizShow && picked && i !== q.a;
680.             return (
681.               <button key={i} onClick={()=>{
682.                 if (quizShow) return;
683.                 const newAns = [...quizAns]; newAns[quizIdx] = i;
684.                 setQuizAns(newAns); setQuizShow(true);
685.               }} style={{
686.                 background: isRight ? '#e0f6f3' : isWrong ? '#ffe4ef' : '#fff9ef',
687.                 border:`2px solid ${isRight ? '#17b3a6' : isWrong ? '#ff6b5b' : '#f0e8d8'}`,
688.                 borderRadius:14, padding:'13px 16px', textAlign:'left', cursor: quizShow ? 'default' : 'pointer',
689.                 fontSize:14.5, fontWeight:700, color:'#1b1230', fontFamily:'Nunito, sans-serif',
690.                 display:'flex', alignItems:'center', gap:12, transition:'all .15s',
691.               }}>
692.                 <div style={{
693.                   width:26, height:26, borderRadius:8, background: isRight ? '#17b3a6' : isWrong ? '#ff6b5b' : '#fff',
694.                   color: (isRight||isWrong) ? '#fff' : '#1b1230', border:'2px solid #f0e8d8',
695.                   display:'flex', alignItems:'center', justifyContent:'center', fontWeight:900, fontSize:12, flexShrink:0,
696.                 }}>{isRight ? '✓' : isWrong ? '✗' : String.fromCharCode(65+i)}</div>
697.                 {opt}
698.               </button>
699.             );
700.           })}
```

</details>


### ✅ `grep`

**renderTree|renderStructure|node\.children**

"renderTree|renderStructure|node\.children" in *.jsx (website)

```
No matches found.
```


### 💬 Copilot

Let me check the archive date validation and URL construction more carefully:

### ✅ `grep`

**ARCHIVE_BASE|archiveDate|storyId**

"ARCHIVE_BASE|archiveDate|storyId" in *.jsx (website)

<details>
<summary>23 matches</summary>

```
/Users/jiong/myprojects/news-v2/website/article.jsx:    // Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
/Users/jiong/myprojects/news-v2/website/article.jsx:    const detailBase = baseArticle.archiveDate
/Users/jiong/myprojects/news-v2/website/article.jsx:      ? `${window.ARCHIVE_BASE}/${baseArticle.archiveDate}/article_payloads`
/Users/jiong/myprojects/news-v2/website/article.jsx:    const url = `${detailBase}/payload_${baseArticle.storyId}/${payloadLevel}.json`;
/Users/jiong/myprojects/news-v2/website/data.jsx:// Supabase Storage under /<date>/payloads/... — see ARCHIVE_BASE.
/Users/jiong/myprojects/news-v2/website/data.jsx:const ARCHIVE_BASE = `${SUPABASE_URL}/storage/v1/object/public/redesign-daily-content`;
/Users/jiong/myprojects/news-v2/website/data.jsx:// archived day. For today's content (archiveDate = null), leave as-is.
/Users/jiong/myprojects/news-v2/website/data.jsx:function resolveImageUrl(rawUrl, archiveDate) {
/Users/jiong/myprojects/news-v2/website/data.jsx:  if (!archiveDate || !rawUrl) return rawUrl || "";
/Users/jiong/myprojects/news-v2/website/data.jsx:  return `${ARCHIVE_BASE}/${archiveDate}/${rel}`;
/Users/jiong/myprojects/news-v2/website/data.jsx:function listingToArticle(entry, cat, lvl, archiveDate) {
/Users/jiong/myprojects/news-v2/website/data.jsx:    storyId: entry.id,
/Users/jiong/myprojects/news-v2/website/data.jsx:    archiveDate: archiveDate || null,   // null = today's edition
/Users/jiong/myprojects/news-v2/website/data.jsx:    image: resolveImageUrl(entry.image_url, archiveDate),
/Users/jiong/myprojects/news-v2/website/data.jsx:function listingBaseFor(archiveDate) {
/Users/jiong/myprojects/news-v2/website/data.jsx:  return archiveDate ? `${ARCHIVE_BASE}/${archiveDate}/payloads`
/Users/jiong/myprojects/news-v2/website/data.jsx:async function loadPayloads(archiveDate = null) {
/Users/jiong/myprojects/news-v2/website/data.jsx:  const base = listingBaseFor(archiveDate);
/Users/jiong/myprojects/news-v2/website/data.jsx:        for (const a of top3) all.push(listingToArticle(a, cat, lvl, archiveDate));
/Users/jiong/myprojects/news-v2/website/data.jsx:    const r = await fetch(`${ARCHIVE_BASE}/archive-index.json?t=${Date.now()}`);
/Users/jiong/myprojects/news-v2/website/data.jsx:  window.__archiveDate = date || null;
/Users/jiong/myprojects/news-v2/website/data.jsx:window.__archiveDate = null;
/Users/jiong/myprojects/news-v2/website/data.jsx:window.ARCHIVE_BASE = ARCHIVE_BASE;
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 600-728)

<details>
<summary>129 lines</summary>

```
600.       ref={spanRef}
601.       onMouseEnter={show}
602.       onMouseLeave={(e) => { e.stopPropagation(); setHover(false); }}
603.       onClick={(e) => e.stopPropagation()}
604.       style={{
605.         display:'inline-block',
606.         fontFamily:'Fraunces, Georgia, serif',
607.         fontStyle:'italic',
608.         fontWeight:700,
609.         color:'#b2541a',
610.         background: hover ? '#ffedc1' : '#fff4d6',
611.         padding:'0 6px',
612.         borderRadius:6,
613.         textDecoration:'underline dotted #d89b4a',
614.         textUnderlineOffset:'3px',
615.         cursor:'help',
616.         transition:'background .15s',
617.       }}
618.     >
619.       {term}
620.       {hover && ReactDOM.createPortal(
621.         <div style={{
622.           position:'fixed',
623.           top: pos.top,
624.           left: pos.left,
625.           transform:'translate(-50%, -100%)',
626.           background:'#1b1230',
627.           color:'#fff',
628.           padding:'10px 12px',
629.           borderRadius:12,
630.           fontFamily:'Nunito, sans-serif',
631.           fontStyle:'normal',
632.           fontSize:12,
633.           fontWeight:600,
634.           lineHeight:1.45,
635.           width:'max-content',
636.           maxWidth:240,
637.           whiteSpace:'normal',
638.           textAlign:'left',
639.           boxShadow:'0 8px 24px rgba(27,18,48,0.25)',
640.           zIndex:9999,
641.           pointerEvents:'none',
642.         }}>
643.           <div style={{
644.             fontSize:10, fontWeight:800, color:'#ffc83d',
645.             textTransform:'uppercase', letterSpacing:'.08em', marginBottom:3,
646.           }}>What it means</div>
647.           {def}
648.           <div style={{
649.             position:'absolute', top:'100%', left:'50%', transform:'translateX(-50%)',
650.             width:0, height:0,
651.             borderLeft:'6px solid transparent', borderRight:'6px solid transparent',
652.             borderTop:'6px solid #1b1230',
653.           }}/>
654.         </div>,
655.         document.body
656.       )}
657.     </span>
658.   );
659. }
660. 
661. function ArticleCard({ article, onOpen, read, pct, variant }) {
662.   const [hover, setHover] = useStateH(false);
663.   const isFeature = variant === 'feature';
664.   const isTall = variant === 'tall-feature';
665.   return (
666.     <button
667.       onClick={onOpen}
668.       onMouseEnter={()=>setHover(true)}
669.       onMouseLeave={()=>setHover(false)}
670.       style={{
671.         background:'#fff',
672.         border:'2px solid #f0e8d8',
673.         borderRadius:22,
674.         padding:0,
675.         textAlign:'left',
676.         cursor:'pointer',
677.         overflow:'hidden',
678.         position:'relative',
679.         transform: hover ? 'translateY(-4px) rotate(-0.3deg)' : 'translateY(0)',
680.         boxShadow: hover ? '0 10px 0 rgba(27,18,48,0.08)' : '0 4px 0 rgba(27,18,48,0.06)',
681.         transition:'all .2s cubic-bezier(.3,1.4,.6,1)',
682.         gridColumn: isFeature ? 'span 2' : 'auto',
683.         display:'flex',
684.         flexDirection:'column',
685.         width: isTall ? '100%' : undefined,
686.         height: isTall ? '100%' : undefined,
687.       }}
688.     >
689.       <div style={{
690.         position:'relative',
691.         background:`url(${article.image}) center/cover`,
692.         aspectRatio: isTall ? 'auto' : (isFeature ? '16/9' : '16/10'),
693.         width:'100%',
694.         flex: isTall ? '1 1 auto' : undefined,
695.         minHeight: isTall ? 280 : 'auto',
696.       }}>
697.         {(read || (pct && pct > 0)) && (
698.           <div style={{position:'absolute', top:10, right:10}}>
699.             <ProgressBadge pct={read ? 100 : pct}/>
700.           </div>
701.         )}
702.       </div>
703.       <div style={{padding: isFeature ? '26px 32px 24px' : (isTall ? '24px 26px' : '16px 18px 18px'), flex:'0 0 auto', display:'flex', flexDirection:'column', gap:10}}>
704.         <h3 style={{
705.           fontFamily:'Fraunces, serif',
706.           fontWeight:800,
707.           fontSize: isFeature ? 28 : (isTall ? 26 : 19),
708.           lineHeight:1.15,
709.           letterSpacing:'-0.01em',
710.           color:'#1b1230',
711.           margin:0,
712.         }}>{article.title}</h3>
713.         <p style={{
714.           fontSize: isFeature ? 15 : 13.5,
715.           color:'#4a3d5e',
716.           lineHeight:1.6,
717.           margin:0,
718.         }}><HighlightedSummary text={article.summary} keywords={article.keywords}/></p>
719.         <div style={{display:'flex', alignItems:'center', gap:8, flexWrap:'wrap', marginTop:'auto', paddingTop:8}}>
720.           <XpBadge xp={article.xp} small/>
721.           <span style={{fontSize:12, color:'#9a8d7a', fontWeight:700}}>⏱ {article.readMins} min</span>
722.         </div>
723.       </div>
724.     </button>
725.   );
726. }
727. 
728. Object.assign(window, { HomePage });
```

</details>


### 💬 Copilot

Let me search for the DatePopover component and archive date validation:

### ✅ `grep`

**DatePopover|archiveDayLabel**

"DatePopover|archiveDayLabel" in *.jsx (website)

```
/Users/jiong/myprojects/news-v2/website/home.jsx:                {archiveDayLabel(archiveDay)}
/Users/jiong/myprojects/news-v2/website/home.jsx:          <DatePopover onPick={(d)=>{setCalendarOpen(false); onOpenArchive(d);}} onClose={()=>setCalendarOpen(false)} />
/Users/jiong/myprojects/news-v2/website/home.jsx:function archiveDayLabel(d) {
/Users/jiong/myprojects/news-v2/website/home.jsx:function DatePopover({ onPick, onClose }) {
```


### ✅ `bash`

**Find line numbers for DatePopover and archiveDayLabel functions**

$ grep -n "^function archiveDayLabel\|^function DatePopover" /Users/jiong/myprojects/news-v2/website/home.jsx

```
345:function archiveDayLabel(d) {
351:function DatePopover({ onPick, onClose }) {
<exited with exit code 0>
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 345-450)

<details>
<summary>106 lines</summary>

```
345. function archiveDayLabel(d) {
346.   if (!d) return '';
347.   const dt = new Date(d + 'T00:00:00');
348.   return dt.toLocaleDateString(undefined, { weekday:'long', month:'short', day:'numeric' });
349. }
350. 
351. function DatePopover({ onPick, onClose }) {
352.   // Fetch the list of archived days from Supabase. The newest entry is
353.   // today; we exclude it so the picker only offers past editions.
354.   const [index, setIndex] = useStateH({ dates: [] });
355.   useStateH && React.useEffect(() => {
356.     let cancelled = false;
357.     window.loadArchiveIndex().then(r => { if (!cancelled) setIndex(r); });
358.     return () => { cancelled = true; };
359.   }, []);
360.   const todayStr = new Date().toISOString().slice(0, 10);
361.   const pastDates = (index.dates || []).filter(d => d !== todayStr).slice(0, 14);
362. 
363.   return (
364.     <>
365.       <div onClick={onClose} style={{position:'fixed', inset:0, zIndex:40, background:'transparent'}}/>
366.       <div style={{
367.         position:'absolute', top:'100%', marginTop:10, left:28, zIndex:50,
368.         background:'#fff', borderRadius:18, border:'2px solid #1b1230',
369.         padding:16, boxShadow:'0 10px 0 rgba(27,18,48,0.12)', width:340,
370.       }}>
371.         <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230', marginBottom:4}}>📅 Pick a past day</div>
372.         <div style={{fontSize:12, color:'#6b5c80', fontWeight:600, marginBottom:12}}>
373.           {pastDates.length === 0
374.             ? "No past editions yet — check back tomorrow."
375.             : "Catch up on editions you missed."}
376.         </div>
377.         {pastDates.length > 0 && (
378.           <div style={{display:'grid', gridTemplateColumns:'repeat(7, 1fr)', gap:6}}>
379.             {pastDates.map(d => {
380.               const dt = new Date(d + 'T00:00:00');
381.               return (
382.                 <button key={d} onClick={()=>onPick(d)} style={{
383.                   padding:'10px 4px', border:'2px solid #f0e8d8',
384.                   background:'#fff9ef', borderRadius:12, cursor:'pointer',
385.                   fontFamily:'Nunito, sans-serif',
386.                 }}>
387.                   <div style={{fontSize:10, fontWeight:800, color:'#9a8d7a', textTransform:'uppercase'}}>{dt.toLocaleDateString(undefined,{weekday:'short'}).slice(0,3)}</div>
388.                   <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20, color:'#1b1230'}}>{dt.getDate()}</div>
389.                   <div style={{fontSize:9, color:'#9a8d7a', fontWeight:700}}>{dt.toLocaleDateString(undefined,{month:'short'})}</div>
390.                 </button>
391.               );
392.             })}
393.           </div>
394.         )}
395.       </div>
396.     </>
397.   );
398. }
399. 
400. // ——————————— HEADER ———————————
401. function Header({ level, setLevel, theme, tweaks, onOpenUserPanel, progress, recentOpen, setRecentOpen, onOpenArticle }) {
402.   theme = theme || { bg:'#fff9ef', chip:'#f0e8d8' };
403.   tweaks = tweaks || {};
404.   return (
405.     <header style={{
406.       background: theme.bg,
407.       borderBottom: `2px solid ${theme.chip}`,
408.       position:'sticky', top:0, zIndex:30, backdropFilter:'blur(6px)',
409.     }}>
410.       <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:16}}>
411.         <div style={{display:'flex', alignItems:'center', gap:10}}>
412.           <OhYeLogo size={44}/>
413.           <div style={{lineHeight:1}}>
414.             <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:22, color:'#1b1230', letterSpacing:'-0.01em'}}>
415.               News Oh<span style={{color:'#ff6b5b'}}>,</span>Ye<span style={{color:'#ff6b5b'}}>!</span>
416.             </div>
417.             <div style={{fontSize:11, color:'#9a8d7a', fontWeight:700, marginTop:2, letterSpacing:'.08em'}}>READ · THINK · LEARN</div>
418.           </div>
419.         </div>
420. 
421.         <div style={{flex:1}}/>
422. 
423.         {/* Streak pill → opens recent reads popover */}
424.         <div style={{position:'relative'}}>
425.           <button onClick={()=>setRecentOpen(v=>!v)} style={{
426.             display:'flex', alignItems:'center', gap:10, background:'#1b1230', color:'#fff',
427.             padding:'6px 14px 6px 6px', borderRadius:999, border:'none', cursor:'pointer',
428.             fontFamily:'Nunito, sans-serif',
429.           }}>
430.             <StreakRing minutes={MOCK_USER.minutesToday} goal={MOCK_USER.dailyGoal} streak={MOCK_USER.streak} size={40}/>
431.             <div style={{lineHeight:1.1, textAlign:'left'}}>
432.               <div style={{fontSize:11, opacity:.7, fontWeight:700}}>STREAK</div>
433.               <div style={{fontWeight:800, fontSize:14}}>{MOCK_USER.streak} days 🔥</div>
434.             </div>
435.             <span style={{fontSize:11, opacity:0.7, marginLeft:4}}>▾</span>
436.           </button>
437.           {recentOpen && (
438.             <RecentReadsPopover onClose={()=>setRecentOpen(false)} onOpenArticle={(id)=>{setRecentOpen(false); onOpenArticle(id);}} readIds={(progress&&progress.readToday)||[]}/>
439.           )}
440.         </div>
441. 
442.         {/* User button — opens the profile panel */}
443.         {window.UserButton && (
444.           <window.UserButton tweaks={tweaks} streak={MOCK_USER.streak} onClick={onOpenUserPanel}/>
445.         )}
446.       </div>
447.     </header>
448.   );
449. }
450.
```

</details>


### 💬 Copilot

Now let me check how the archive index is fetched and if there's any server-side validation:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/data.jsx.**

/Users/jiong/myprojects/news-v2/website/data.jsx (lines 78-102)

<details>
<summary>25 lines</summary>

```
78. function listingBaseFor(archiveDate) {
79.   return archiveDate ? `${ARCHIVE_BASE}/${archiveDate}/payloads`
80.                      : 'payloads';
81. }
82. 
83. async function loadPayloads(archiveDate = null) {
84.   const cats = ["news", "science", "fun"];
85.   const levels = ["easy", "middle", "cn"];
86.   const base = listingBaseFor(archiveDate);
87.   const all = [];
88.   for (const cat of cats) {
89.     for (const lvl of levels) {
90.       try {
91.         const r = await fetch(`${base}/articles_${cat}_${lvl}.json?t=${Date.now()}`);
92.         if (!r.ok) { console.warn(`[data] missing: ${base}/articles_${cat}_${lvl}.json`); continue; }
93.         const { articles } = await r.json();
94.         const top3 = (articles || []).slice(0, 3);
95.         for (const a of top3) all.push(listingToArticle(a, cat, lvl, archiveDate));
96.       } catch (e) {
97.         console.warn(`[data] fetch failed: ${base}/articles_${cat}_${lvl}.json`, e);
98.       }
99.     }
100.   }
101.   return all;
102. }
```

</details>


### ✅ `bash`

**Check URL construction in article.jsx**

$ grep -A 5 -B 5 "resolveImageUrl\|url =" /Users/jiong/myprojects/news-v2/website/article.jsx | head -40

<details>
<summary>12 lines</summary>

```
// Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
    // prefix; today's content stays local.
    const detailBase = baseArticle.archiveDate
      ? `${window.ARCHIVE_BASE}/${baseArticle.archiveDate}/article_payloads`
      : 'article_payloads';
    const url = `${detailBase}/payload_${baseArticle.storyId}/${payloadLevel}.json`;
    fetch(url)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(d => {
        if (cancelled) return;
        // Map v1 field shapes to the prototype's expected shape.
<exited with exit code 0>
```

</details>


### 💬 Copilot

Let me check for potential localStorage issues and also verify what happens when archive-index.json is compromised:

### ✅ `bash`

**Find localStorage usage in index.html**

$ grep -n "localStorage" /Users/jiong/myprojects/news-v2/website/index.html | head -20

<details>
<summary>18 lines</summary>

```
50:  // restore from localStorage; if saved articleId no longer exists (payloads changed), fall back to home
53:      const saved = JSON.parse(localStorage.getItem('ohye_route') || 'null');
62:    const v = localStorage.getItem('ohye_level') || 'Sprout';
67:    const v = localStorage.getItem('ohye_cat') || 'News';
72:    // Migration: any legacy numeric value in localStorage is cleared.
73:    const v = localStorage.getItem('ohye_archive_day');
75:    if (v) localStorage.removeItem('ohye_archive_day');
80:      const saved = JSON.parse(localStorage.getItem('ohye_progress') || 'null');
87:  // Tweaks / User Panel — persisted to localStorage so name/avatar/theme/etc.
92:      const saved = JSON.parse(localStorage.getItem('ohye_tweaks') || 'null');
98:  useEffect(() => { localStorage.setItem('ohye_route', JSON.stringify(route)); }, [route]);
99:  useEffect(() => { localStorage.setItem('ohye_level', level); }, [level]);
100:  useEffect(() => { localStorage.setItem('ohye_cat', cat); }, [cat]);
102:    if (archiveDay) localStorage.setItem('ohye_archive_day', String(archiveDay));
103:    else localStorage.removeItem('ohye_archive_day');
113:  useEffect(() => { localStorage.setItem('ohye_progress', JSON.stringify(progress)); }, [progress]);
114:  useEffect(() => { localStorage.setItem('ohye_tweaks', JSON.stringify(tweaks)); }, [tweaks]);
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check error handling around localStorage writes**

$ grep -B 3 -A 3 "localStorage.setItem" /Users/jiong/myprojects/news-v2/website/index.html | head -50

<details>
<summary>19 lines</summary>

```
});
  const [userPanelOpen, setUserPanelOpen] = useState(false);

  useEffect(() => { localStorage.setItem('ohye_route', JSON.stringify(route)); }, [route]);
  useEffect(() => { localStorage.setItem('ohye_level', level); }, [level]);
  useEffect(() => { localStorage.setItem('ohye_cat', cat); }, [cat]);
  useEffect(() => {
    if (archiveDay) localStorage.setItem('ohye_archive_day', String(archiveDay));
    else localStorage.removeItem('ohye_archive_day');
    // Whenever archiveDay changes, re-load ARTICLES from the matching bundle
    // (today's local files, or a past day's Supabase prefix).
--
      });
    }
  }, [archiveDay]);
  useEffect(() => { localStorage.setItem('ohye_progress', JSON.stringify(progress)); }, [progress]);
  useEffect(() => { localStorage.setItem('ohye_tweaks', JSON.stringify(tweaks)); }, [tweaks]);

  // Edit-mode wiring
  useEffect(() => {
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check todayArticles usage**

$ grep -n "todayArticles\|displayPool" /Users/jiong/myprojects/news-v2/website/home.jsx | head -20

<details>
<summary>9 lines</summary>

```
31:  const displayPool = useMemoH(() => {
34:      out.push(...todayArticles.filter(a => a.category === c.label).slice(0, 3));
37:  }, [todayArticles]);
38:  const poolIds = useMemoH(() => new Set(displayPool.map(a => a.id)), [displayPool]);
48:      const first = displayPool.find(a => a.category === c.label);
52:  }, [displayPool]);
58:  const daily3 = useMemoH(() => activePicks.map(id => displayPool.find(a => a.id === id)).filter(Boolean), [activePicks, displayPool]);
177:              const alternates = displayPool.filter(x => x.category === a.category && !activePicks.includes(x.id));
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Find todayArticles definition**

$ grep -n "const todayArticles\|let todayArticles" /Users/jiong/myprojects/news-v2/website/home.jsx

```

<exited with exit code 1>
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 30-66)

<details>
<summary>37 lines</summary>

```
30.   // Per-category displayable pool — only the first 3 stories of each category (what's shown on pages)
31.   const displayPool = useMemoH(() => {
32.     const out = [];
33.     for (const c of CATEGORIES) {
34.       out.push(...todayArticles.filter(a => a.category === c.label).slice(0, 3));
35.     }
36.     return out;
37.   }, [todayArticles]);
38.   const poolIds = useMemoH(() => new Set(displayPool.map(a => a.id)), [displayPool]);
39. 
40.   // Pick 1 from each category by default, user can swap (only from the 3-per-category pool)
41.   const [dailyPicks, setDailyPicks] = useStateH(() => {
42.     try { const s = JSON.parse(localStorage.getItem('ohye_daily_picks_v3') || 'null'); if (s && s.length === 3) return s; } catch {}
43.     return null;
44.   });
45.   const defaultPicks = useMemoH(() => {
46.     const out = [];
47.     for (const c of CATEGORIES) {
48.       const first = displayPool.find(a => a.category === c.label);
49.       if (first) out.push(first.id);
50.     }
51.     return out.slice(0, 3);
52.   }, [displayPool]);
53.   const activePicks = (dailyPicks && dailyPicks.every(id => poolIds.has(id))) ? dailyPicks : defaultPicks;
54.   useEffectH(() => { localStorage.setItem('ohye_daily_picks_v3', JSON.stringify(activePicks)); }, [activePicks]);
55.   const swapPick = (idx, newId) => {
56.     const next = [...activePicks]; next[idx] = newId; setDailyPicks(next);
57.   };
58.   const daily3 = useMemoH(() => activePicks.map(id => displayPool.find(a => a.id === id)).filter(Boolean), [activePicks, displayPool]);
59.   const [swapOpen, setSwapOpen] = useStateH(null); // index being swapped
60. 
61.   const byCat = useMemoH(() => {
62.     const m = {};
63.     CATEGORIES.forEach(c => { m[c.label] = ARTICLES.filter(a => a.category === c.label); });
64.     return m;
65.   }, []);
66.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 19-40)

<details>
<summary>22 lines</summary>

```
19.   const filteredRaw = useMemoH(() => {
20.     const matches = ARTICLES.filter(matchesLanguageLevel);
21.     return (cat === 'All' || !cat) ? matches : matches.filter(a => a.category === cat);
22.   }, [isZh, level, cat, archiveDay]);
23.   // Cap today to 3 per category (editorial layout). Archive also 3 since
24.   // each day's bundle only has 3 per category anyway.
25.   const filtered = useMemoH(() => filteredRaw.slice(0, 3), [filteredRaw]);
26. 
27.   const [calendarOpen, setCalendarOpen] = useStateH(false);
28.   const [recentOpen, setRecentOpen] = useStateH(false);
29. 
30.   // Per-category displayable pool — only the first 3 stories of each category (what's shown on pages)
31.   const displayPool = useMemoH(() => {
32.     const out = [];
33.     for (const c of CATEGORIES) {
34.       out.push(...todayArticles.filter(a => a.category === c.label).slice(0, 3));
35.     }
36.     return out;
37.   }, [todayArticles]);
38.   const poolIds = useMemoH(() => new Set(displayPool.map(a => a.id)), [displayPool]);
39. 
40.   // Pick 1 from each category by default, user can swap (only from the 3-per-category pool)
```

</details>


### 💬 Copilot

Let me check if images can be traversed or if there's other string injection risks:

### ✅ `bash`

**Check image URL usage**

$ grep -n "article.image\|alt.image\|background.*image" /Users/jiong/myprojects/news-v2/website/home.jsx

```
200:                          <div style={{width:44, height:44, borderRadius:10, flexShrink:0, background:`url(${alt.image}) center/cover, ${catColor}`}}/>
224:                      background:`url(${a.image}) center/cover, ${catColor}`,
691:        background:`url(${article.image}) center/cover`,
<exited with exit code 0>
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/data.jsx.**

/Users/jiong/myprojects/news-v2/website/data.jsx (lines 40-76)

<details>
<summary>37 lines</summary>

```
40. // Rewrite /article_images/xxx.webp → full Supabase URL when we're loading an
41. // archived day. For today's content (archiveDate = null), leave as-is.
42. function resolveImageUrl(rawUrl, archiveDate) {
43.   if (!archiveDate || !rawUrl) return rawUrl || "";
44.   if (rawUrl.startsWith('http')) return rawUrl;
45.   const rel = rawUrl.replace(/^\//, '');   // strip leading slash
46.   return `${ARCHIVE_BASE}/${archiveDate}/${rel}`;
47. }
48. 
49. function listingToArticle(entry, cat, lvl, archiveDate) {
50.   const categoryLabel = { news: "News", science: "Science", fun: "Fun" }[cat];
51.   const isZh = lvl === "cn";
52.   const level = isZh ? null : (lvl === "easy" ? "Sprout" : "Tree");
53.   return {
54.     id: entry.id + "-" + lvl,
55.     storyId: entry.id,
56.     archiveDate: archiveDate || null,   // null = today's edition
57.     title: entry.title,
58.     summary: entry.summary,
59.     body: "",
60.     image: resolveImageUrl(entry.image_url, archiveDate),
61.     category: categoryLabel,
62.     source: entry.source || "",
63.     time: entry.time_ago || "",
64.     minedAt: entry.mined_at || "",
65.     sourcePublishedAt: entry.source_published_at || "",
66.     readMins: isZh ? 2 : (lvl === "easy" ? 3 : 5),
67.     level: level,
68.     language: isZh ? "zh" : "en",
69.     xp: isZh ? 15 : (lvl === "easy" ? 30 : 45),
70.     tag: categoryLabel,
71.     keywords: [],
72.     quiz: [],
73.     discussion: [],
74.     noDetail: isZh,
75.   };
76. }
```

</details>


### 💬 Copilot

Let me also check if there are issues with the article structure rendering:

### ✅ `bash`

**Check how articleStructure is rendered**

$ grep -B 5 -A 10 "articleStructure\|Article_Structure" /Users/jiong/myprojects/news-v2/website/article.jsx | head -60

<details>
<summary>58 lines</summary>

```
quiz: (d.questions || []).map(q => {
            const idx = q.options.findIndex(opt => opt === q.correct_answer);
            return { q: q.question, options: q.options, a: Math.max(0, idx) };
          }),
          discussion: (d.perspectives || []).map(p => `${p.perspective}: ${p.description}`),
          articleStructure: Array.isArray(d.Article_Structure) ? d.Article_Structure : [],
        };
        setDetail(mapped);
      })
      .catch(e => { if (!cancelled) { console.warn('[article] detail fetch failed', url, e); setDetailError(e); } });
    return () => { cancelled = true; };
  }, [articleId]);

  // Merged article object: prefer detail fields when loaded, fall back to the
  // listing-level stub so the title block + header render even before detail
  // arrives.
--
      backgroundRead: d.backgroundRead || '',
      whyItMatters: d.whyItMatters || '',
      keywords: d.keywords || [],
      quiz: d.quiz || [],
      discussion: d.discussion || [],
      articleStructure: d.articleStructure || [],
    };
  }, [articleId, detail]);

  // Each step completion bumps progress by 25%: read→25, analyze→50, quiz→75, discuss→100
  const bumpProgress = (pct) => {
    setProgress(p => {
      const ap = p.articleProgress || {};
      const cur = ap[article.id] || 0;
      if (cur >= pct) return p;
      const next = { ...p, articleProgress: { ...ap, [article.id]: pct } };
--
  const bgParagraphs = (article.backgroundRead || '').trim()
    ? article.backgroundRead.split(/\n\n+/).map(s => s.trim()).filter(Boolean)
    : [`This story comes from ${article.source}, a ${article.category === 'Science' ? 'science source' : 'news source'} that covers stories for kids. When you read, think about WHO is doing something, WHAT is happening, WHERE it takes place, and WHY it matters.`];

  // Easy level: parse WHO/WHAT/WHERE/WHY into a 5W grid.
  // Tree level: render Article_Structure as a nested mind-tree preserving
  // leading-whitespace + └─/├─ indentation from the payload.
  let structureBlock = null;
  if (isTree) {
    structureBlock = (
      <div style={{display:'flex', flexDirection:'column', gap:6}}>
        {(article.articleStructure || []).map((line, i) => {
          const raw = typeof line === 'string' ? line : String(line);
          const m = raw.match(/^(\s*)(.*)$/);
          const indent = m ? m[1].length : 0;
          const text = m ? m[2] : raw;
          // Split "LABEL: rest" so label can be bolded
          const lm = text.match(/^([A-Z][A-Z \/]*[A-Z]|[A-Z][a-z]+):\s*(.*)$/);
          return (
            <div key={i} style={{
              paddingLeft: indent * 8,
              fontSize:14, lineHeight:1.55, color:'#2a1f3d',
--
        })}
      </div>
    );
<exited with exit code 0>
```

</details>


### 💬 Copilot

Let me verify the exact line numbers and check one more thing about error handling:

### ✅ `bash`

**Check all fetch calls for payload loading**

$ cd /Users/jiong/myprojects/news-v2 && grep -n "fetch.*payloads\|fetch.*article_payloads" website/*.jsx

```

<exited with exit code 1>
```


### ✅ `bash`

**Check all fetch calls**

$ grep -n "fetch" /Users/jiong/myprojects/news-v2/website/data.jsx /Users/jiong/myprojects/news-v2/website/article.jsx

<details>
<summary>10 lines</summary>

```
/Users/jiong/myprojects/news-v2/website/data.jsx:91:        const r = await fetch(`${base}/articles_${cat}_${lvl}.json?t=${Date.now()}`);
/Users/jiong/myprojects/news-v2/website/data.jsx:97:        console.warn(`[data] fetch failed: ${base}/articles_${cat}_${lvl}.json`, e);
/Users/jiong/myprojects/news-v2/website/data.jsx:108:    const r = await fetch(`${ARCHIVE_BASE}/archive-index.json?t=${Date.now()}`);
/Users/jiong/myprojects/news-v2/website/data.jsx:112:    console.warn('[data] archive-index fetch failed', e);
/Users/jiong/myprojects/news-v2/website/article.jsx:20:  // Lazy-fetch v1 detail payload for this article. Chinese cards (noDetail) are
/Users/jiong/myprojects/news-v2/website/article.jsx:21:  // routed away before reaching this page, so we only fetch English variants.
/Users/jiong/myprojects/news-v2/website/article.jsx:28:    // Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
/Users/jiong/myprojects/news-v2/website/article.jsx:34:    fetch(url)
/Users/jiong/myprojects/news-v2/website/article.jsx:59:      .catch(e => { if (!cancelled) { console.warn('[article] detail fetch failed', url, e); setDetailError(e); } });
<exited with exit code 0>
```

</details>


### 💬 Copilot

Let me view the components.jsx more carefully to check for any additional issues:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/components.jsx.**

/Users/jiong/myprojects/news-v2/website/components.jsx (lines 100-200)

<details>
<summary>98 lines</summary>

```
100. }
101. 
102. function LevelChip({ level, small }) {
103.   const l = LEVELS.find(x => x.id === level) || LEVELS[1];
104.   return (
105.     <span style={{
106.       display:'inline-flex', alignItems:'center', gap:5,
107.       background:'#fff', color:'#1b1230',
108.       padding: small ? '3px 9px' : '4px 11px',
109.       borderRadius:999, fontWeight:700,
110.       fontSize: small ? 11 : 12,
111.       border:'1.5px solid #eee3d7',
112.     }}>
113.       <span>{l.emoji}</span>{l.label}
114.     </span>
115.   );
116. }
117. 
118. // ————————————————————————————————————————————————————————————
119. // XP BADGE
120. // ————————————————————————————————————————————————————————————
121. function XpBadge({ xp, small }) {
122.   return (
123.     <span style={{
124.       display:'inline-flex', alignItems:'center', gap:4,
125.       background:'#fff4c2', color:'#8a6d00',
126.       padding: small ? '2px 8px' : '3px 10px',
127.       borderRadius:999, fontWeight:800, fontSize: small ? 11 : 12,
128.     }}>
129.       <span>⭐</span>+{xp} XP
130.     </span>
131.   );
132. }
133. 
134. // ————————————————————————————————————————————————————————————
135. // BIG BUTTON
136. // ————————————————————————————————————————————————————————————
137. function BigButton({ children, onClick, color='#1b1230', bg='#ffc83d', style, disabled }) {
138.   const [press, setPress] = useState(false);
139.   return (
140.     <button
141.       onClick={onClick}
142.       disabled={disabled}
143.       onMouseDown={()=>setPress(true)}
144.       onMouseUp={()=>setPress(false)}
145.       onMouseLeave={()=>setPress(false)}
146.       style={{
147.         background: disabled ? '#e8dfd3' : bg,
148.         color: disabled ? '#9a8d7a' : color,
149.         border:'none',
150.         borderRadius:16,
151.         padding:'14px 22px',
152.         fontWeight:800,
153.         fontSize:16,
154.         fontFamily:'Nunito, sans-serif',
155.         cursor: disabled ? 'not-allowed' : 'pointer',
156.         boxShadow: disabled ? 'none' : (press ? '0 2px 0 rgba(0,0,0,0.15)' : '0 5px 0 rgba(0,0,0,0.18)'),
157.         transform: press ? 'translateY(3px)' : 'translateY(0)',
158.         transition:'transform .08s, box-shadow .08s',
159.         letterSpacing:'0.01em',
160.         ...style,
161.       }}
162.     >{children}</button>
163.   );
164. }
165. 
166. // ————————————————————————————————————————————————————————————
167. // STAR METER (quiz progress)
168. // ————————————————————————————————————————————————————————————
169. function StarMeter({ filled, total }) {
170.   return (
171.     <div style={{display:'inline-flex', gap:4}}>
172.       {Array.from({length: total}).map((_,i) => (
173.         <span key={i} style={{fontSize:18, filter: i < filled ? 'none' : 'grayscale(1) opacity(0.3)'}}>⭐</span>
174.       ))}
175.     </div>
176.   );
177. }
178. 
179. // ————————————————————————————————————————————————————————————
180. // HELPERS
181. // ————————————————————————————————————————————————————————————
182. function timeAgo(s){ return s; }
183. 
184. function getCatColor(cat){
185.   const c = CATEGORIES.find(x => x.label === cat);
186.   return c ? c.color : '#1b1230';
187. }
188. function getCatBg(cat){
189.   const c = CATEGORIES.find(x => x.label === cat);
190.   return c ? c.bg : '#f6efe3';
191. }
192. 
193. Object.assign(window, {
194.   OhYeLogo, StreakRing, CatChip, LevelChip, XpBadge, BigButton, StarMeter,
195.   timeAgo, getCatColor, getCatBg,
196. });
197.
```

</details>


### 💬 Copilot

Now let me create a comprehensive final review by checking one more detail about the URL construction:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/article.jsx.**

/Users/jiong/myprojects/news-v2/website/article.jsx (lines 28-62)

<details>
<summary>35 lines</summary>

```
28.     // Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
29.     // prefix; today's content stays local.
30.     const detailBase = baseArticle.archiveDate
31.       ? `${window.ARCHIVE_BASE}/${baseArticle.archiveDate}/article_payloads`
32.       : 'article_payloads';
33.     const url = `${detailBase}/payload_${baseArticle.storyId}/${payloadLevel}.json`;
34.     fetch(url)
35.       .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
36.       .then(d => {
37.         if (cancelled) return;
38.         // Map v1 field shapes to the prototype's expected shape.
39.         // v1 detail pattern: full body lives in `summary`; `background_read` is
40.         // supplementary context (for the Analyze tab), not the body.
41.         const bgRead = Array.isArray(d.background_read)
42.           ? d.background_read.join('\n\n')
43.           : (typeof d.background_read === 'string' ? d.background_read : '');
44.         const mapped = {
45.           body: d.summary || '',                        // FULL regenerated article body
46.           summary: d.summary || baseArticle.summary,
47.           backgroundRead: bgRead,                       // shown on Analyze tab
48.           whyItMatters: d.why_it_matters || '',
49.           keywords: (d.keywords || []).map(k => ({ term: k.term, def: k.explanation })),
50.           quiz: (d.questions || []).map(q => {
51.             const idx = q.options.findIndex(opt => opt === q.correct_answer);
52.             return { q: q.question, options: q.options, a: Math.max(0, idx) };
53.           }),
54.           discussion: (d.perspectives || []).map(p => `${p.perspective}: ${p.description}`),
55.           articleStructure: Array.isArray(d.Article_Structure) ? d.Article_Structure : [],
56.         };
57.         setDetail(mapped);
58.       })
59.       .catch(e => { if (!cancelled) { console.warn('[article] detail fetch failed', url, e); setDetailError(e); } });
60.     return () => { cancelled = true; };
61.   }, [articleId]);
62.
```

</details>


### 💬 Copilot

Based on my review of the frontend code, here are the substantive findings:

## Frontend Code Review — News Oh,Ye! v2

### CRITICAL

**Undefined variable reference (home.jsx:34)**
- **File:line**: `website/home.jsx:34`
- **What**: Reference to undefined variable `todayArticles` in `displayPool` memo.
- **Why it matters**: Will throw `ReferenceError: todayArticles is not defined` on every render, crashing the app. The app becomes non-functional when trying to load home page content.
- **Suggested fix**: Replace `todayArticles` with `ARTICLES` (or intended variable based on design). The displayPool logic attempts to group articles by category but references a non-existent variable.

---

### IMPORTANT

**Unprotected localStorage writes without error handling (index.html:98, 99, 100, 102, 113, 114)**
- **File:line**: `website/index.html:98, 99, 100, 102, 113, 114`
- **What**: `localStorage.setItem()` called without try-catch blocks in multiple useEffect hooks.
- **Why it matters**: If localStorage is full (QuotaExceededError) or disabled (private browsing, restricted environments), the write will throw and crash the app. State mutations will fail silently from user perspective but the app breaks.
- **Suggested fix**: Wrap all `localStorage.setItem()` calls in try-catch blocks. Example: `try { localStorage.setItem('ohye_route', JSON.stringify(route)); } catch(e) { console.warn('localStorage unavailable'); }`.

**Unvalidated archiveDate used in URL construction (data.jsx:79-80, article.jsx:31)**
- **File:line**: `website/data.jsx:79-80`, `website/article.jsx:31`
- **What**: `archiveDate` is interpolated directly into Supabase Storage URLs without validation when loading archived payloads.
- **Why it matters**: While index.html does validate archiveDate on localStorage load (regex `/^\d{4}-\d{2}-\d{2}$/`), dates from `archive-index.json` fetched from Supabase (data.jsx:110) are used unvalidated. If Supabase storage is compromised or misconfigured, malicious path sequences (`../../../admin`, `....//....//`) could traverse into unintended storage prefixes.
- **Suggested fix**: Validate archiveDate with the same regex *before* using it in URL construction at lines 79-80 and 31. Add: `if (archiveDate && !/^\d{4}-\d{2}-\d{2}$/.test(archiveDate)) throw new Error('Invalid archive date');`

**Unvalidated storyId used in URL construction (article.jsx:33)**
- **File:line**: `website/article.jsx:33`
- **What**: `baseArticle.storyId` (derived from listing payload) is interpolated into fetch URL without validation.
- **Why it matters**: If the backend payload contains a malicious `id` value with path traversal sequences (e.g., `../../../sensitive`), the fetch URL would become `...payload_../../../sensitive/...json`, potentially exposing unintended files if the backend storage doesn't enforce strict bounds.
- **Suggested fix**: Validate storyId is alphanumeric/safe before use. Add: `if (!/^[a-zA-Z0-9_-]+$/.test(baseArticle.storyId)) throw new Error('Invalid story ID');` or use URL normalization.

**Unvalidated image URLs in CSS background (home.jsx:200, 224, 691)**
- **File:line**: `website/home.jsx:200, 224, 691`
- **What**: Article image URLs are embedded directly in CSS `background:url()` without escaping or validation.
- **Why it matters**: If payload image_url contains CSS-breaking characters (`;`, `"`, `)`, or newlines), it could break the CSS rule or allow CSS injection. Example: `article.image = 'test.jpg"); background: url(data:...evil'` would inject a second CSS property.
- **Suggested fix**: Either (a) validate image URLs are well-formed (start with `/`, protocol, or safe prefix), or (b) use `backgroundImage` property with properly escaped URL: `style={{backgroundImage: `url(${JSON.stringify(article.image).slice(1,-1)})`, backgroundSize: 'cover'...}}` or encodeURI.

---

### MINOR

**Missing dependency or stale closure in progress state (index.html:113)**
- **File:line**: `website/index.html:113`
- **What**: `localStorage.setItem('ohye_progress', JSON.stringify(progress))` depends only on `[progress]`, but `progress` object includes nested fields that may not trigger re-renders if mutated.
- **Why it matters**: If `progress.articleProgress` is mutated directly rather than replaced, the useEffect may not fire, and saves could be lost (low priority given the bumpProgress logic replaces the object).
- **Suggested fix**: Low priority, but consider verifying `bumpProgress` always creates new object references: `const next = { ...p, articleProgress: { ...ap, [article.id]: pct } };` (already doing this correctly, so not a real issue).

---

## Summary

The codebase has **one critical runtime crash** (undefined variable), **two blocking error modes** (localStorage quota/disable, path traversal in archive URLs), and **two data-integrity/injection risks** (storyId, image URLs). The localStorage issue is the most user-visible failure mode on restricted environments. The path traversal risks are lower-probability (require Supabase compromise) but high-severity if exploited.

**Top 3 fixes (priority order):**
1. Fix `todayArticles` undefined → replace with correct variable (blocks app)
2. Add try-catch around all localStorage writes → prevents crashes on quota/disabled storage
3. Validate archiveDate and storyId before URL construction → prevents path traversal attacks


---

<sub>⏱️ 51s</sub>

### 📦 task (Completed)

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/docs/reviews.**

/Users/jiong/myprojects/news-v2/docs/reviews

```
2026-04-24-codex-review.md
2026-04-24-copilot-review-raw.md
2026-04-24-copilot-review.md
2026-04-24-review-brief.md
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/.github/workflows.**

/Users/jiong/myprojects/news-v2/.github/workflows

```
daily-pipeline.yml
```


### ✅ `glob`

****/pipeline/config.py**

"**/pipeline/config.py"

```
./pipeline/config.py
```


### ✅ `glob`

****/*env*.py**

"**/*env*.py"

```
No files matched the pattern.
```


### 💬 Copilot

Now let me read the review brief and the pipeline files:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md.**

/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md

<details>
<summary>178 lines</summary>

````
1. # Code review brief — News Oh, Ye! v2 (news.6ray.com)
2. 
3. ## Project context
4. 
5. **Goal.** Bilingual kids news site (English easy / middle + 中文 summary).
6. Fully autonomous pipeline runs daily on GitHub Actions, produces 9 stories
7. (3 News / 3 Science / 3 Fun) plus per-story detail enrichment, ships to
8. Supabase Storage, and auto-deploys to Vercel at news.6ray.com.
9. 
10. **Three-repo architecture.**
11. - `news-v2` (this repo): Python pipeline + React prototype source. Runs the
12.   daily-pipeline workflow. Goes private eventually.
13. - `kidsnews-v2` (separate repo): tiny deploy shell. A sync workflow pulls
14.   `latest.zip` from Supabase Storage, unzips into `site/`, commits, Vercel
15.   auto-deploys.
16. - `kidsnews` (legacy, v1 reference at kidsnews.6ray.com): not relevant.
17. 
18. ## Flow
19. 
20. ```
21. GitHub Action (news-v2 · daily 06:20 UTC)
22.   └── python -m pipeline.full_round
23.         ├── RSS mine (3 sources × 3 categories, per-weekday rotation)
24.         ├── Phase A per source: vet 10 briefs, return top-4 verified candidates
25.         ├── past-dedup (3-day lookback, title ≥80% similar → drop)
26.         ├── cross-source dedup (promote next candidate on dup)
27.         ├── tri-variant rewrite (easy_en / middle_en / zh) via DeepSeek chat
28.         ├── detail enrich (keywords / questions / background / mind-tree /
29.         │     why_it_matters / perspectives) via DeepSeek reasoner
30.         │     — retries 3× on JSON parse; falls back to split 3-slot batches
31.         ├── image optimize (Pillow decode + libwebp cwebp/dwebp CLI)
32.         │     → Supabase Storage redesign-article-images bucket
33.         ├── persist runs + stories to Supabase tables
34.         └── pack_and_upload
35.               ├── validate_bundle (9 listings · 18 details · all images)
36.               ├── check_not_overwriting_newer (aborts if remote is fresher)
37.               ├── zip website/ → Supabase redesign-daily-content:latest.zip
38.               │     + <YYYY-MM-DD>.zip
39.               ├── latest-manifest.json + <YYYY-MM-DD>-manifest.json
40.               ├── per-day flat files under <YYYY-MM-DD>/ prefix (new)
41.               ├── backfill_missing_archive_dirs (extracts past zips if the
42.               │     flat dir is missing — runs only once per past date)
43.               ├── update archive-index.json (list of available dates)
44.               └── retention sweep (keep 30 days)
45. 
46. GitHub Action (kidsnews-v2 · cron :15 every 2h, or dispatch on pipeline success)
47.   └── downloads latest.zip → unzips into site/ → commits if changed → push
48. 
49. Vercel (on push to kidsnews-v2)
50.   └── deploys site/ to news.6ray.com
51. ```
52. 
53. ## Key files (by importance)
54. 
55. ### Pipeline (Python 3.11)
56. - `pipeline/full_round.py` — orchestrator. Aggregate → dedup → images →
57.   rewrite+enrich → persist → pack_and_upload.
58. - `pipeline/news_rss_core.py` — shared utilities. DeepSeek call wrappers
59.   with retry, vet/rewriter/enricher prompts, RSS fetch, duplicate checker.
60. - `pipeline/pack_and_upload.py` — validation + zip + manifest + per-day
61.   flat upload + archive-index + retention.
62. - `pipeline/image_optimize.py` — webp optimizer with shutil.which() for
63.   cross-platform CLI path.
64. - `pipeline/news_sources.py` / `science_sources.py` / `fun_sources.py` —
65.   RSS source registries (per-weekday rotation for Science/Fun).
66. - `pipeline/news_aggregate.py` / `science_aggregate.py` / `fun_aggregate.py`
67.   — per-category aggregators (mostly wrappers around `run_source_with_backups`).
68. - `pipeline/supabase_io.py` — DB insert/update helpers.
69. - `pipeline/rewrite_from_db.py` — resume pipeline from DB state (skip
70.   mining + image ops). Used for debug / partial-category re-runs.
71. 
72. ### Frontend (React 18 + Babel-standalone, in-browser JSX transpile)
73. - `website/index.html` — app shell. Loads data.jsx / components.jsx /
74.   home.jsx / article.jsx / user-panel.jsx. Owns top-level state (route,
75.   level, cat, archiveDay, progress, tweaks).
76. - `website/data.jsx` — payload loader. Fetches today's listings from
77.   `/payloads/*.json` (local). For archive mode, fetches from Supabase
78.   Storage `<date>/payloads/*.json`. Exposes window.loadArchive(date).
79. - `website/home.jsx` — listing page with feature + normal card variants,
80.   DatePopover for "View old news", footer generation timestamp.
81. - `website/article.jsx` — detail page: Read & Words / Background / Quiz
82.   / Think & Share tabs. Supports mind-tree Article_Structure for Tree
83.   level, 5W boxes for Sprout.
84. - `website/components.jsx` — shared UI bits (CatChip, XpBadge, etc.).
85. - `website/user-panel.jsx` — profile drawer (name / avatar / theme / level).
86. 
87. ### CI/CD
88. - `.github/workflows/daily-pipeline.yml` — news-v2 daily cron (pipeline).
89. - (kidsnews-v2 repo) `.github/workflows/sync-from-supabase.yml` — pulls
90.   latest.zip + commits.
91. - `requirements.txt` — Python deps.
92. - `pipeline/backfill_card_summaries.py`, `pipeline/augment_mined_at.py` —
93.   one-shots used historically.
94. 
95. ## What to evaluate
96. 
97. Focus where you'd expect bugs or future pain:
98. 
99. 1. **Correctness.**
100.    - `dedup_winners` → `pick_winners_with_dedup` refactor. Two overlapping
101.      ScienceDaily feeds produced the same article; fix was to return up
102.      to 4 candidates and promote next on dup. Check edge cases: all
103.      sources returning candidates that are all pairwise dupes; candidate
104.      exhaustion mid-loop.
105.    - `filter_past_duplicates` title-similarity at 0.80 — are there
106.      obvious false positives / negatives? (titles can differ
107.      significantly while being the same story; or be identical but
108.      different stories.)
109.    - `deepseek_*_call` retry logic — does it handle rate-limit
110.      (429) differently from JSON parse errors?
111.    - `detail_enrich` split-batch fallback — what if BOTH easy and
112.      middle sub-calls fail? Currently continues with partial details;
113.      downstream validator will catch.
114. 
115. 2. **Security.**
116.    - Supabase service key lives in a committed .env loader (module
117.      top-level), overridden by GitHub Actions secret at job start.
118.      Any path where the key could end up in a log?
119.    - Vercel.json Cache-Control of 5min for user-visible assets — any
120.      risk of serving private data?
121.    - DeepSeek API key is only used server-side; confirm no frontend
122.      references.
123.    - Any HTML injection paths in the rewriter output? UI highlights
124.      keywords by matching with user-content strings.
125. 
126. 3. **Failure modes.**
127.    - Pipeline partial failure (category rewrite succeeds but enrich
128.      fails): is there a state where a partial bundle gets uploaded?
129.      (We added `check_not_overwriting_newer` and `validate_bundle`.)
130.    - Supabase Storage quota exhaustion mid-upload.
131.    - Vercel build fails after kidsnews-v2 commit — the pipeline
132.      doesn't know; only manual intervention.
133.    - Browser with localStorage full / disabled.
134. 
135. 4. **Maintainability.**
136.    - `pipeline/news_rss_core.py` is ~1200 lines. Should it split?
137.    - `full_round.py` grew fast — orchestration, dedup, image-process
138.      helpers, persistence, emit — all in one file.
139.    - React app has no build step (Babel-standalone). Fine for a
140.      prototype; risky long-term. Recommendation?
141.    - Hardcoded `/Users/jiong/...` paths were a CI bug source today;
142.      are there others lurking?
143. 
144. 5. **Architecture.**
145.    - Three-repo split: authoring / deploy / legacy. Any cleaner alt?
146.    - The zip-over-Storage indirection vs directly pushing
147.      generated artifacts to the deploy repo.
148.    - Per-day flat files coexist with zips — redundant, or
149.      justified?
150.    - "CI-only, never run locally" guard (`check_not_overwriting_newer`)
151.      — robust enough? Any evasion paths?
152. 
153. 6. **Prompt engineering.**
154.    - Rewriter prompt vs enricher prompt — any accuracy-vs-creativity
155.      trade-offs worth flagging?
156.    - `card_summary` ≤ 120 words — is the prompt actually enforceable?
157.      (We also post-trim with a word cap.)
158.    - Past-dedup threshold of 0.80 title similarity — when would you
159.      lower or raise it?
160. 
161. ## Format of your review
162. 
163. For each finding, use:
164. 
165. - **Severity**: `Critical` / `Important` / `Minor` / `Info`
166. - **File:line** (or "cross-cutting")
167. - **What**: one-sentence description
168. - **Why it matters** (1-2 sentences)
169. - **Suggested fix** (concrete, if you have one)
170. 
171. Then at the end: 3-5 line assessment summary + top 3 things to fix first.
172. 
173. Do not nitpick style unless it materially affects clarity. Do not
174. suggest broad refactors without a specific incident that justifies
175. them. Trust that the design decisions (RSS-only, three-repo split,
176. zip-via-Supabase, React-without-build) are intentional unless you spot
177. evidence they're causing real problems.
178.
````

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml.**

/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml

<details>
<summary>62 lines</summary>

```
1. name: Daily pipeline
2. 
3. on:
4.   workflow_dispatch: {}
5.   schedule:
6.     # 06:20 UTC daily ≈ 23:20 PT / 02:20 ET. Pick any time; kidsnews-v2 cron
7.     # then pulls latest.zip on its next `:15` of an even hour (≤2h lag).
8.     - cron: "20 6 * * *"
9. 
10. permissions:
11.   contents: read
12. 
13. jobs:
14.   run:
15.     runs-on: ubuntu-latest
16.     timeout-minutes: 30
17.     env:
18.       DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
19.       SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
20.       SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
21.     steps:
22.       - name: Checkout
23.         uses: actions/checkout@v4
24. 
25.       - name: Install libwebp (cwebp / dwebp)
26.         run: |
27.           sudo apt-get update -q
28.           sudo apt-get install -y -q webp
29. 
30.       - name: Set up Python
31.         uses: actions/setup-python@v5
32.         with:
33.           python-version: "3.11"
34.           cache: "pip"
35. 
36.       - name: Install Python deps
37.         run: |
38.           python -m pip install -U pip
39.           pip install -r requirements.txt
40. 
41.       - name: Write .env for modules that read it directly
42.         run: |
43.           umask 077
44.           cat > .env <<EOF
45.           DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
46.           SUPABASE_URL=${SUPABASE_URL}
47.           SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
48.           EOF
49. 
50.       - name: Run full_round
51.         run: python -m pipeline.full_round
52. 
53.       - name: Upload payloads artifact (debug)
54.         if: always()
55.         uses: actions/upload-artifact@v4
56.         with:
57.           name: website-payloads-${{ github.run_id }}
58.           path: |
59.             website/payloads/
60.             website/article_payloads/
61.           retention-days: 7
62.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/config.py.**

/Users/jiong/myprojects/news-v2/pipeline/config.py

<details>
<summary>217 lines</summary>

```
1. """Configuration constants for KidsNews v2 pipeline (Steps 1-3)."""
2. from __future__ import annotations
3. 
4. # ---------------------------------------------------------------------------
5. # Query rotation tables
6. # ---------------------------------------------------------------------------
7. 
8. NEWS_QUERY = "top 5 hottest news today"
9. NEWS_FALLBACK_QUERY = "latest kid-safe news stories"
10. NEWS_TOPIC = "Current events"
11. 
12. # News 3-lane redesign (v2-curator)
13. NEWS_CURATOR_QUERY = "top news stories today"
14. NEWS_TIER1_DOMAINS = ["npr.org", "reuters.com"]
15. NEWS_TIER2_DOMAINS = ["apnews.com", "bbc.com", "theguardian.com"]
16. NEWS_LANE_MAX_RESULTS = 5
17. 
18. # weekday() → (topic_label, tavily_query)
19. SCIENCE_ROTATION: dict[int, tuple[str, str]] = {
20.     0: ("AI / auto",                        "mind blowing AI robots automation news this week for kids"),
21.     1: ("Biology / Medicine / Health",      "mind blowing biology medicine health news this week for kids"),
22.     2: ("Space / Astronomy",                "mind blowing space astronomy discoveries news this week for kids"),
23.     3: ("Chemistry / Physics",              "mind blowing chemistry physics experiments news this week for kids"),
24.     4: ("Environment / Climate",            "mind blowing environment climate nature news this week for kids"),
25.     5: ("Technology / Engineering",         "mind blowing technology engineering invention news this week for kids"),
26.     6: ("Nature / Geometry",                "mind blowing nature geometry patterns news this week for kids"),
27. }
28. 
29. FUN_ROTATION: dict[int, tuple[str, str]] = {
30.     0: ("Music", "kids music news concerts instruments this week"),
31.     1: ("Swimming / Water sports", "kids swimming water sports news this week"),
32.     2: ("Movies / TV", "kids movies tv shows news this week"),
33.     3: ("Cool inventions / kid inventors / new toys",
34.         "best new kids toys and inventions launching this week"),
35.     4: ("Arts / Crafts", "kids arts crafts creativity news this week"),
36.     5: ("Animals / Famous person / History", "kids animals famous people history news this week"),
37.     6: ("Video games / Esports", "kids video games esports news this week"),
38. }
39. 
40. # ---------------------------------------------------------------------------
41. # RSS feeds
42. # ---------------------------------------------------------------------------
43. 
44. RSS_FEEDS: dict[str, dict] = {
45.     "News": {
46.         "url": "https://www.pbs.org/newshour/feeds/rss/headlines",
47.         "source_name": "PBS NewsHour",
48.         "target": 3,
49.     },
50.     "Science": {
51.         "url": "https://www.sciencedaily.com/rss/all.xml",
52.         "source_name": "Science Daily",
53.         "target": 3,
54.     },
55.     "Fun": {
56.         "url": "https://feeds.bbci.co.uk/sport/tennis/rss.xml",
57.         "source_name": "BBC Tennis",
58.         "target": 2,
59.     },
60. }
61. 
62. # ---------------------------------------------------------------------------
63. # Tavily tuning
64. # ---------------------------------------------------------------------------
65. 
66. TAVILY_TARGET = 3  # per-category fallback
67. # Per-category Tavily discovery targets (News bumped to 5 for wider funnel)
68. TAVILY_TARGETS: dict[str, int] = {"News": 5, "Science": 3, "Fun": 3}
69. # Per-category RSS discovery targets (News bumped to 5)
70. RSS_TARGETS: dict[str, int] = {"News": 5, "Science": 3, "Fun": 2}
71. TAVILY_MAX_RESULTS = 15  # ask for lots of extras; URL-shape filter is strict
72. TAVILY_ENDPOINT = "https://api.tavily.com/search"
73. TAVILY_EXTRACT_ENDPOINT = "https://api.tavily.com/extract"
74. TAVILY_EXTRACT_TIMEOUT = 30
75. 
76. # ---------------------------------------------------------------------------
77. # Shopping / deals filter (Fix 3)
78. # ---------------------------------------------------------------------------
79. 
80. # Hosts devoted primarily to deals / shopping listicles.
81. SHOPPING_HOSTS = (
82.     "bgr.com",
83.     "rochesterfirst.com",
84.     "slickdeals.net",
85.     "dealnews.com",
86.     "bestproducts.com",
87. )
88. 
89. # URL path fragments that signal deals/shopping sections of mainstream sites.
90. SHOPPING_PATH_MARKERS = (
91.     "/best-deals",
92.     "/select/shopping",
93.     "/shopping/",
94.     "/deals/",
95.     "/top-deals",
96.     "/gift-guide",
97.     "/buying-guide",
98. )
99. 
100. # ---------------------------------------------------------------------------
101. # Image filter
102. # ---------------------------------------------------------------------------
103. 
104. IMAGE_URL_BLACKLIST = (
105.     "logo", "icon", "avatar", "tracking", "1x1", "pixel", "spacer",
106.     # bot/crawler proxy URLs that return HTML not image bytes
107.     "crawler", "google_widget",
108. )
109. IMAGE_EXT_BLACKLIST = (".svg", ".gif")
110. IMAGE_MIN_BYTES = 20_000
111. IMAGE_HEAD_TIMEOUT = 3
112. 
113. # ---------------------------------------------------------------------------
114. # Vetter thresholds (Stage 1 on title + snippet)
115. # ---------------------------------------------------------------------------
116. 
117. VET_SAFE_MAX = 4       # 0-4 SAFE
118. VET_CAUTION_MAX = 12   # 5-12 CAUTION
119. # 13-40 REJECT
120. 
121. DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
122. DEEPSEEK_MODEL = "deepseek-chat"
123. DEEPSEEK_TEMPERATURE = 0.1
124. DEEPSEEK_MAX_TOKENS = 600
125. 
126. VETTER_SYSTEM_PROMPT = """You are a content reviewer for a kids news site (ages 8-13, grades 3-8).
127. You are judging based ONLY on the title and a short snippet.
128. 
129. PART A — SAFETY. Rate each 0-5 (0=none, 5=severe):
130. violence, sexual, substance, language, fear, adult_themes, distress, bias.
131. Compute safety_total = sum of these (0-40).
132. safety_verdict:
133.   0-4  -> SAFE
134.   5-12 -> CAUTION (publishable after rewrite softening)
135.   13+  -> REJECT (block)
136. 
137. PART B — INTEREST. A safe story still needs to be worth reading. Rate each 0-5:
138. - importance: how globally significant (0=trivial, 5=major historic event)
139. - fun_factor: how funny, delightful, surprising (0=dry, 5=hilarious/amazing)
140. - kid_appeal: how likely an 8-13 year old would WANT to read this (0=boring to a kid, 5=kid magnet)
141. Compute interest_peak = max(importance, fun_factor, kid_appeal).
142. interest_verdict:
143.   peak >= 3 -> ENGAGING
144.   peak == 2 -> MEH
145.   peak <= 1 -> BORING
146. 
147. Rule: a story can pass with EITHER high importance OR high fun_factor OR high kid_appeal — it does not need all three.
148. 
149. Return ONLY valid JSON (no markdown fences):
150. {
151.   "safety_scores": {"violence":0,"sexual":0,"substance":0,"language":0,"fear":0,"adult_themes":0,"distress":0,"bias":0},
152.   "safety_total": 0,
153.   "safety_verdict": "SAFE|CAUTION|REJECT",
154.   "interest_scores": {"importance":0,"fun_factor":0,"kid_appeal":0},
155.   "interest_peak": 0,
156.   "interest_verdict": "ENGAGING|MEH|BORING",
157.   "flags": ["..."],
158.   "rewrite_notes": "..."
159. }"""
160. 
161. # Interest thresholds already encoded in the prompt; keep exposed:
162. INTEREST_PEAK_MIN_KEEP = 2  # drop candidates with interest_peak < this (i.e., BORING gets dropped)
163. 
164. # ---------------------------------------------------------------------------
165. # Jina Reader
166. # ---------------------------------------------------------------------------
167. 
168. JINA_ENDPOINT = "https://r.jina.ai/"
169. JINA_TIMEOUT = 30
170. JINA_MIN_CONTENT_LEN = 1200  # reuse Tavily raw_content if at least this many chars
171. 
172. # ---------------------------------------------------------------------------
173. # News-lane content strategy
174. # ---------------------------------------------------------------------------
175. 
176. # If Tavily raw_content has >= this many words, treat it as sufficient and
177. # skip the Jina fallback. Applied when the category is in SKIP_JINA_CATEGORIES.
178. TAVILY_CONTENT_MIN_WORDS = 450
179. 
180. # Categories for which we do NOT fall back to Jina. News articles are often
181. # video-first and produce thin text; we'd rather drop than pay for Jina.
182. SKIP_JINA_CATEGORIES = {"News"}
183. 
184. # ---------------------------------------------------------------------------
185. # Post-vet selection
186. # ---------------------------------------------------------------------------
187. 
188. # Pick the top N (by vetted_rank) among SAFE/CAUTION per category.
189. FINAL_PUBLISH_COUNT = 3
190. 
191. # Hosts for which we trust og:image enough to skip the HEAD check.
192. TRUSTED_IMAGE_HOSTS = (
193.     "ichef.bbci.co.uk",
194.     "bbci.co.uk",
195.     "pbs.org",
196.     "pbs.twimg.com",
197.     "static.pbs.org",
198.     "image.pbs.org",
199.     "assets.sciencedaily.com",
200.     "cdn.sciencedaily.com",
201.     "sciencedaily.com",
202. )
203. 
204. # ---------------------------------------------------------------------------
205. # Output paths
206. # ---------------------------------------------------------------------------
207. 
208. import os
209. from pathlib import Path
210. 
211. PROJECT_ROOT = Path(__file__).resolve().parent.parent
212. WEBSITE_DIR = PROJECT_ROOT / "website"
213. TEST_OUTPUT_DIR = WEBSITE_DIR / "test_output"
214. 
215. # Categories to process (in order)
216. CATEGORIES = ["News", "Science", "Fun"]
217.
```

</details>


### 💬 Copilot

Now let me look at pack_and_upload.py and related pipeline files for security and operational concerns:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py

<details>
<summary>446 lines</summary>

```
1. """Pack `website/` into a zip and upload it to Supabase Storage as both
2. `<YYYY-MM-DD>.zip` (immutable archive) and `latest.zip` (what the deploy repo's
3. GitHub Action fetches). Also writes a `latest-manifest.json` (+ dated copy)
4. with the version + content hash + story IDs so anyone inspecting the bucket
5. knows what's inside without downloading.
6. 
7. Validates today's content bundle BEFORE packing. If any listing or detail file
8. is missing or incomplete, refuses to upload — the live site keeps yesterday's
9. zip until the pipeline produces a fully-formed bundle.
10. 
11. After a successful upload, runs retention: keeps `latest.*` + the last
12. `RETENTION_DAYS` dated archives; deletes older dated zips + manifests."""
13. from __future__ import annotations
14. 
15. import hashlib
16. import json
17. import logging
18. import os
19. import re
20. import sys
21. import zipfile
22. from datetime import datetime, timezone
23. from io import BytesIO
24. from pathlib import Path
25. 
26. from supabase import create_client
27. 
28. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
29. log = logging.getLogger("pack")
30. 
31. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
32. for _line in (_envp.open() if _envp.exists() else []):
33.     if "=" in _line and not _line.startswith("#"):
34.         k, v = _line.strip().split("=", 1)
35.         os.environ[k] = v
36. 
37. ROOT = Path(__file__).resolve().parent.parent
38. WEB = ROOT / "website"
39. BUCKET = "redesign-daily-content"
40. RETENTION_DAYS = 30  # dated archives older than this get deleted
41. 
42. # Allowlist of top-level files/dirs that ship to production.
43. INCLUDE_FILES = {"index.html", "article.jsx", "home.jsx", "components.jsx",
44.                  "data.jsx", "user-panel.jsx"}
45. INCLUDE_DIRS = {"payloads", "article_payloads", "article_images", "assets"}
46. 
47. 
48. def collect_files() -> list[tuple[Path, str]]:
49.     out: list[tuple[Path, str]] = []
50.     for name in INCLUDE_FILES:
51.         p = WEB / name
52.         if p.is_file():
53.             out.append((p, name))
54.     for d in INCLUDE_DIRS:
55.         base = WEB / d
56.         if not base.is_dir():
57.             continue
58.         for p in base.rglob("*"):
59.             if p.is_file() and not p.name.startswith("."):
60.                 out.append((p, str(p.relative_to(WEB))))
61.     return out
62. 
63. 
64. CATS = ("news", "science", "fun")
65. # (field, min_count) — what a detail payload MUST contain to count as complete.
66. DETAIL_MIN = [
67.     ("keywords", 3),
68.     ("questions", 3),
69.     ("background_read", 1),
70.     ("Article_Structure", 3),
71. ]
72. 
73. 
74. def validate_bundle(today: str) -> None:
75.     """Fail (SystemExit 1) if today's bundle is incomplete. Check:
76.       · 9 listing files (3 cats × easy/middle/cn), each with exactly 3 articles
77.       · 18 detail payloads (9 stories × easy/middle), each with non-empty
78.         keywords/questions/background_read/Article_Structure
79.       · 9 article images on disk (one per story id)
80.     """
81.     errs: list[str] = []
82. 
83.     # Listing files — 2 or 3 per cat/lvl acceptable (ideal=3; 2 after
84.     # cross-source dup drops when all backups are exhausted). <2 is fatal.
85.     payloads = WEB / "payloads"
86.     short_cats: set[str] = set()  # cats that shipped <3
87.     for cat in CATS:
88.         for lvl in ("easy", "middle", "cn"):
89.             p = payloads / f"articles_{cat}_{lvl}.json"
90.             if not p.is_file():
91.                 errs.append(f"missing listing: {p.name}")
92.                 continue
93.             try:
94.                 doc = json.loads(p.read_text())
95.                 arts = doc.get("articles") or []
96.                 if len(arts) < 2:
97.                     errs.append(f"{p.name}: {len(arts)} articles (need ≥2)")
98.                 elif len(arts) < 3:
99.                     short_cats.add(f"{cat}/{lvl}")
100.                 for a in arts:
101.                     if not (a.get("title") and a.get("summary") and a.get("id")):
102.                         errs.append(f"{p.name}: article {a.get('id','?')} missing title/summary/id")
103.             except Exception as e:  # noqa: BLE001
104.                 errs.append(f"{p.name}: parse error {e}")
105.     if short_cats:
106.         log.warning("Shipping with <3 articles in: %s", sorted(short_cats))
107. 
108.     # Detail payloads (easy + middle only; cn has no detail page) — iterate
109.     # actual story IDs from the middle listing so 2-article cats validate
110.     # cleanly.
111.     details = WEB / "article_payloads"
112.     all_story_ids: list[str] = []
113.     for cat in CATS:
114.         p = payloads / f"articles_{cat}_middle.json"
115.         if p.is_file():
116.             try:
117.                 arts = json.loads(p.read_text()).get("articles") or []
118.                 all_story_ids.extend(a.get("id") for a in arts if a.get("id"))
119.             except Exception:
120.                 pass
121.     for story_id in all_story_ids:
122.         story_dir = details / f"payload_{story_id}"
123.         if not story_dir.is_dir():
124.             errs.append(f"missing detail dir: payload_{story_id}")
125.             continue
126.         for lvl in ("easy", "middle"):
127.             p = story_dir / f"{lvl}.json"
128.             if not p.is_file():
129.                 errs.append(f"missing detail: {story_id}/{lvl}.json")
130.                 continue
131.             try:
132.                 d = json.loads(p.read_text())
133.                 if not (d.get("summary") and len((d.get("summary") or "").split()) >= 50):
134.                     errs.append(f"{story_id}/{lvl}: summary missing or <50 words")
135.                 for field, min_n in DETAIL_MIN:
136.                     if len(d.get(field) or []) < min_n:
137.                         errs.append(
138.                             f"{story_id}/{lvl}: {field} has "
139.                             f"{len(d.get(field) or [])} (need ≥{min_n})"
140.                         )
141.             except Exception as e:  # noqa: BLE001
142.                 errs.append(f"{story_id}/{lvl}: parse error {e}")
143. 
144.     # Per-story images (same image used across easy/middle for a story)
145.     images_dir = WEB / "article_images"
146.     needed_images: set[str] = set()
147.     for cat in CATS:
148.         # Pull image_urls from today's listings — whichever level works
149.         for lvl in ("middle", "easy"):
150.             p = payloads / f"articles_{cat}_{lvl}.json"
151.             if not p.is_file():
152.                 continue
153.             try:
154.                 doc = json.loads(p.read_text())
155.                 for a in doc.get("articles") or []:
156.                     url = a.get("image_url") or ""
157.                     if url:
158.                         needed_images.add(Path(url).name)
159.                 break
160.             except Exception:
161.                 continue
162.     for name in needed_images:
163.         if not (images_dir / name).is_file():
164.             errs.append(f"missing image: article_images/{name}")
165. 
166.     if errs:
167.         log.error("Bundle validation FAILED — refusing to pack/upload:")
168.         for e in errs:
169.             log.error("  · %s", e)
170.         raise SystemExit(1)
171.     log.info("Bundle validation OK: 9 listings · 18 details · %d images",
172.              len(needed_images))
173. 
174. 
175. def build_zip() -> bytes:
176.     buf = BytesIO()
177.     files = collect_files()
178.     with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
179.         for p, arc in files:
180.             zf.write(p, arcname=arc)
181.     log.info("Packed %d files (%d bytes)", len(files), buf.tell())
182.     return buf.getvalue()
183. 
184. 
185. def build_manifest(today: str, body: bytes) -> dict:
186.     """Summarize what this zip contains — version + content hash + story IDs.
187.     Consumers can compare manifest sha256 without downloading the zip."""
188.     stories: list[dict] = []
189.     for cat in CATS:
190.         p = WEB / "payloads" / f"articles_{cat}_middle.json"
191.         if not p.is_file():
192.             continue
193.         try:
194.             for a in (json.loads(p.read_text()).get("articles") or []):
195.                 stories.append({
196.                     "id": a.get("id"),
197.                     "category": a.get("category"),
198.                     "title": a.get("title"),
199.                     "mined_at": a.get("mined_at"),
200.                     "source": a.get("source"),
201.                     "source_published_at": a.get("source_published_at"),
202.                 })
203.         except Exception:
204.             pass
205.     return {
206.         "version": today,
207.         "packed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
208.         "git_sha": os.environ.get("GITHUB_SHA") or "",
209.         "zip_bytes": len(body),
210.         "zip_sha256": hashlib.sha256(body).hexdigest(),
211.         "story_count": len(stories),
212.         "stories": stories,
213.     }
214. 
215. 
216. DATED_ZIP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.zip$")
217. DATED_MANIFEST_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-manifest\.json$")
218. DATED_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
219. 
220. 
221. def upload_dated_flat_files(sb, date_str: str, bundle: bytes | None = None) -> int:
222.     """Upload each file under the website bundle to `<date>/<relpath>` in the
223.     bucket so the UI can fetch past days' content directly (no zip parsing
224.     in the browser). `bundle` is an optional zip body — if given, files are
225.     extracted from it; otherwise read from local disk. Returns file count."""
226.     uploaded = 0
227.     if bundle is not None:
228.         zf = zipfile.ZipFile(BytesIO(bundle))
229.         members = [n for n in zf.namelist()
230.                    if n.endswith(".json") or n.endswith(".webp")]
231.         for name in members:
232.             body = zf.read(name)
233.             ctype = "application/json" if name.endswith(".json") else "image/webp"
234.             sb.storage.from_(BUCKET).upload(
235.                 path=f"{date_str}/{name}",
236.                 file=body,
237.                 file_options={"content-type": ctype, "upsert": "true"},
238.             )
239.             uploaded += 1
240.     else:
241.         for p, arc in collect_files():
242.             if not (arc.endswith(".json") or arc.endswith(".webp")):
243.                 continue  # skip HTML/JSX shell from dated flat copy
244.             ctype = "application/json" if arc.endswith(".json") else "image/webp"
245.             sb.storage.from_(BUCKET).upload(
246.                 path=f"{date_str}/{arc}",
247.                 file=p.read_bytes(),
248.                 file_options={"content-type": ctype, "upsert": "true"},
249.             )
250.             uploaded += 1
251.     log.info("dated-flat: uploaded %d files under %s/", uploaded, date_str)
252.     return uploaded
253. 
254. 
255. def update_archive_index(sb, dates: list[str]) -> None:
256.     """Merge `dates` into `archive-index.json` (descending, deduped, cap 30)."""
257.     try:
258.         body = sb.storage.from_(BUCKET).download("archive-index.json")
259.         idx = json.loads(body.decode() if isinstance(body, bytes) else body)
260.     except Exception:
261.         idx = {"dates": []}
262.     existing = set(idx.get("dates") or [])
263.     existing.update(dates)
264.     all_dates = sorted(existing, reverse=True)[:RETENTION_DAYS]
265.     idx = {"dates": all_dates,
266.            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
267.     sb.storage.from_(BUCKET).upload(
268.         path="archive-index.json",
269.         file=json.dumps(idx, ensure_ascii=False, indent=2).encode(),
270.         file_options={"content-type": "application/json", "upsert": "true"},
271.     )
272.     log.info("archive-index updated: %d dates (newest=%s)",
273.              len(all_dates), all_dates[0] if all_dates else "-")
274. 
275. 
276. def backfill_missing_archive_dirs(sb, current_index: list[str]) -> list[str]:
277.     """For any YYYY-MM-DD.zip in the bucket whose date isn't in the archive
278.     index AND doesn't yet have its flat dir, extract the zip and upload
279.     flat files. Returns list of backfilled dates."""
280.     current_set = set(current_index)
281.     objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
282.     candidates = []
283.     for o in objs or []:
284.         m = DATED_ZIP_RE.match(o.get("name") or "")
285.         if m and m.group(1) not in current_set:
286.             candidates.append(m.group(1))
287.     backfilled: list[str] = []
288.     for d in sorted(candidates):
289.         try:
290.             body = sb.storage.from_(BUCKET).download(f"{d}.zip")
291.             body = bytes(body) if not isinstance(body, bytes) else body
292.             upload_dated_flat_files(sb, d, bundle=body)
293.             backfilled.append(d)
294.         except Exception as e:  # noqa: BLE001
295.             log.warning("backfill %s failed: %s", d, e)
296.     return backfilled
297. 
298. 
299. def cleanup_retention(sb, keep_days: int) -> None:
300.     """Delete dated archives older than `keep_days`. Keeps `latest.*` always.
301.     Also removes all files under `<date>/` prefix for expired dates."""
302.     from datetime import date, timedelta
303.     cutoff = date.today() - timedelta(days=keep_days)
304.     expired: set[str] = set()
305.     objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
306.     to_delete: list[str] = []
307.     for o in objs or []:
308.         name = o.get("name") or ""
309.         for rx in (DATED_ZIP_RE, DATED_MANIFEST_RE, DATED_DIR_RE):
310.             m = rx.match(name)
311.             if not m:
312.                 continue
313.             try:
314.                 day = datetime.strptime(m.group(1), "%Y-%m-%d").date()
315.             except ValueError:
316.                 continue
317.             if day < cutoff:
318.                 if rx is DATED_DIR_RE:
319.                     expired.add(name)
320.                 else:
321.                     to_delete.append(name)
322.     # For each expired dir, list its files + delete them
323.     for d in expired:
324.         try:
325.             subs = sb.storage.from_(BUCKET).list(d, {"limit": 1000})
326.             for s in subs or []:
327.                 to_delete.append(f"{d}/{s.get('name')}")
328.         except Exception as e:  # noqa: BLE001
329.             log.warning("retention: listing %s/ failed: %s", d, e)
330.     if not to_delete:
331.         log.info("retention: 0 old files (keep %d days)", keep_days)
332.         return
333.     # Supabase remove() takes a list of paths.
334.     sb.storage.from_(BUCKET).remove(to_delete)
335.     log.info("retention: deleted %d files older than %s",
336.              len(to_delete), cutoff.isoformat())
337. 
338. 
339. def local_freshest_mined_at() -> str | None:
340.     """ISO-8601 of the most recent mined_at across all today's listings."""
341.     stamps: list[str] = []
342.     for cat in CATS:
343.         p = WEB / "payloads" / f"articles_{cat}_middle.json"
344.         if not p.is_file():
345.             continue
346.         try:
347.             for a in json.loads(p.read_text()).get("articles") or []:
348.                 if a.get("mined_at"):
349.                     stamps.append(a["mined_at"])
350.         except Exception:
351.             continue
352.     return max(stamps) if stamps else None
353. 
354. 
355. def check_not_overwriting_newer(sb) -> None:
356.     """Refuse to upload if the bucket already has a manifest whose packed_at
357.     (or freshest story mined_at) is newer than our local content. Prevents a
358.     local `pack_and_upload` from silently replacing CI-generated output."""
359.     try:
360.         body = sb.storage.from_(BUCKET).download("latest-manifest.json")
361.         remote = json.loads(body.decode() if isinstance(body, bytes) else body)
362.     except Exception:
363.         return  # nothing remote yet — safe to upload
364.     remote_stamps = [s.get("mined_at") for s in (remote.get("stories") or [])
365.                      if s.get("mined_at")]
366.     remote_freshest = max(remote_stamps) if remote_stamps else remote.get("packed_at")
367.     local_freshest = local_freshest_mined_at()
368.     if not (remote_freshest and local_freshest):
369.         return
370.     if local_freshest < remote_freshest:
371.         msg = (f"REFUSE: remote manifest is newer than local. "
372.                f"remote freshest={remote_freshest} · local freshest={local_freshest}. "
373.                "If you really want to overwrite, set ALLOW_STALE_UPLOAD=1.")
374.         if os.environ.get("ALLOW_STALE_UPLOAD") != "1":
375.             log.error(msg)
376.             raise SystemExit(1)
377.         log.warning("ALLOW_STALE_UPLOAD=1 set — proceeding despite: %s", msg)
378. 
379. 
380. def main() -> None:
381.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
382.     validate_bundle(today)
383.     body = build_zip()
384.     manifest = build_manifest(today, body)
385.     manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
386.     sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
387.     check_not_overwriting_newer(sb)
388. 
389.     # Write zip in two locations: dated archive (immutable history) + latest.
390.     for key in (f"{today}.zip", "latest.zip"):
391.         sb.storage.from_(BUCKET).upload(
392.             path=key,
393.             file=body,
394.             file_options={"content-type": "application/zip", "upsert": "true"},
395.         )
396.         log.info("uploaded %s", key)
397. 
398.     # Same for the manifest — dated archive + latest pointer.
399.     for key in (f"{today}-manifest.json", "latest-manifest.json"):
400.         sb.storage.from_(BUCKET).upload(
401.             path=key,
402.             file=manifest_bytes,
403.             file_options={"content-type": "application/json", "upsert": "true"},
404.         )
405.         log.info("uploaded %s", key)
406. 
407.     log.info("manifest: version=%s · zip_bytes=%d · zip_sha256=%s · stories=%d",
408.              manifest["version"], manifest["zip_bytes"],
409.              manifest["zip_sha256"][:12], manifest["story_count"])
410. 
411.     # Flat per-day files — the UI fetches these when user picks a past date.
412.     try:
413.         upload_dated_flat_files(sb, today)
414.     except Exception as e:  # noqa: BLE001
415.         log.warning("dated-flat upload failed (non-fatal): %s", e)
416. 
417.     # Read existing archive-index, backfill any dated zip that doesn't yet
418.     # have a flat dir, then update archive-index with both backfilled +
419.     # today's date.
420.     try:
421.         body = sb.storage.from_(BUCKET).download("archive-index.json")
422.         existing_idx = json.loads(body.decode() if isinstance(body, bytes) else body)
423.         existing_dates = existing_idx.get("dates") or []
424.     except Exception:
425.         existing_dates = []
426.     try:
427.         backfilled = backfill_missing_archive_dirs(sb, existing_dates)
428.         if backfilled:
429.             log.info("archive backfill: %s", backfilled)
430.         update_archive_index(sb, [today] + backfilled)
431.     except Exception as e:  # noqa: BLE001
432.         log.warning("archive-index update failed (non-fatal): %s", e)
433. 
434.     # Retention sweep: delete dated archives older than RETENTION_DAYS.
435.     try:
436.         cleanup_retention(sb, RETENTION_DAYS)
437.     except Exception as e:  # noqa: BLE001
438.         log.warning("retention sweep failed (non-fatal): %s", e)
439. 
440.     pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
441.     log.info("public URL: %s", pub)
442. 
443. 
444. if __name__ == "__main__":
445.     main()
446.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 1-100)

<details>
<summary>100 lines</summary>

```
1. """Full round — news + science + fun aggregators → optimize images → upload to
2. Storage → write redesign_runs + redesign_stories → emit v1-shape payload files
3. for the new v2 UI.
4. 
5. Run:  python -m pipeline.full_round
6. View: http://localhost:18100/  (UI loads from website/payloads/ + article_payloads/ + article_images/)
7. """
8. from __future__ import annotations
9. 
10. import hashlib
11. import json
12. import logging
13. from datetime import datetime, timezone
14. from pathlib import Path
15. from urllib.parse import urlparse
16. 
17. from .news_rss_core import (check_duplicates, detail_enrich,
18.                               run_source_phase_a, tri_variant_rewrite)
19. from .fun_sources import todays_enabled_sources as fun_sources
20. from .fun_sources import todays_topic as fun_topic
21. from .science_sources import todays_enabled_sources as science_sources
22. from .science_sources import todays_topic as science_topic
23. from .image_optimize import fetch_and_optimize
24. from .supabase_io import insert_run, insert_story, update_run, upload_image
25. from .news_sources import enabled_sources as news_sources
26. from .news_aggregate import run_source_with_backups as run_news
27. from .science_aggregate import run_source_with_backups as run_sci
28. from .fun_aggregate import run_source_with_backups as run_fun
29. from .news_sources import backup_sources as news_backups
30. from .science_sources import todays_backup_sources as sci_backups
31. from .fun_sources import todays_backup_sources as fun_backups
32. 
33. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
34. log = logging.getLogger("full-round")
35. 
36. 
37. # -------------------------------------------------------------------
38. # 1) Aggregate 3 categories
39. # -------------------------------------------------------------------
40. 
41. def aggregate_category(label: str, enabled: list, backups: list, runner) -> dict[str, dict]:
42.     """Run Phase A for each source; return `{source_name: {source, candidates}}`.
43.     Each source contributes up to 4 ranked candidates (choice_1…). If the
44.     primary source yields 0 candidates, rotates to a backup source (handled
45.     inside `runner`)."""
46.     log.info("[%s] aggregating from %d sources", label, len(enabled))
47.     used_backups: set[str] = set()
48.     by_source: dict[str, dict] = {}
49.     for source in enabled:
50.         avail = [b for b in backups if b.name not in used_backups]
51.         res = runner(source, avail)
52.         if not res:
53.             continue
54.         # Supports both the new multi-candidate Phase A return shape and the
55.         # legacy single-winner shape (some aggregator paths still produce
56.         # the latter, e.g. after backup rotation).
57.         cands = res.get("candidates")
58.         if not cands and res.get("winner"):
59.             cands = [{"winner": res["winner"], "slot": res.get("winner_slot") or "choice_1"}]
60.         if not cands:
61.             continue
62.         src_obj = res["source"]
63.         by_source[src_obj.name] = {"source": src_obj, "candidates": cands}
64.         if res.get("used_backup"):
65.             used_backups.add(src_obj.name)
66.     return by_source
67. 
68. 
69. def _normalize_title(t: str) -> str:
70.     """lowercase + strip punctuation + collapse whitespace for similarity match."""
71.     import re as _re
72.     s = (t or "").lower()
73.     s = _re.sub(r"[^\w\s]", " ", s)
74.     s = _re.sub(r"\s+", " ", s).strip()
75.     return s
76. 
77. 
78. def _title_similarity(a: str, b: str) -> float:
79.     from difflib import SequenceMatcher
80.     return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()
81. 
82. 
83. # Shape used by filter_past_duplicates + pick_winners_with_dedup:
84. #   by_source = {
85. #     <source_name>: {"source": <SourceObj>, "candidates": [{"winner": art, "slot": "choice_1"}, ...]},
86. #     ...
87. #   }
88. 
89. 
90. def filter_past_duplicates(category: str, by_source: dict[str, dict],
91.                            days: int = 3, threshold: float = 0.80) -> dict[str, dict]:
92.     """Drop candidates whose title ≥threshold-matches any story this category
93.     published in the last `days` days. Cheap — SequenceMatcher on a few
94.     dozen title pairs is microseconds."""
95.     from datetime import date, timedelta
96.     from .supabase_io import client
97.     try:
98.         sb = client()
99.     except Exception as e:
100.         log.warning("past-dedup skipped — Supabase unreachable: %s", e)
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/supabase_io.py.**

/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py

<details>
<summary>84 lines</summary>

```
1. """Supabase helpers — Storage uploads + DB inserts for the v2 redesign schema."""
2. from __future__ import annotations
3. 
4. import logging
5. import os
6. from pathlib import Path
7. from typing import Any
8. 
9. from supabase import Client, create_client
10. 
11. log = logging.getLogger("supa")
12. 
13. # Load .env once
14. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
15. for _line in (_envp.open() if _envp.exists() else []):
16.     if "=" in _line and not _line.startswith("#"):
17.         _k, _v = _line.strip().split("=", 1)
18.         os.environ[_k] = _v
19. 
20. SUPABASE_URL = os.environ.get("SUPABASE_URL")
21. SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
22. STORAGE_BUCKET = "redesign-article-images"
23. 
24. 
25. def client() -> Client:
26.     if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
27.         raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY must be set in .env")
28.     return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
29. 
30. 
31. def upload_image(local_path: Path, remote_name: str) -> str | None:
32.     """Upload a local file to the storage bucket. Returns public URL or None."""
33.     try:
34.         sb = client()
35.         data = local_path.read_bytes()
36.         sb.storage.from_(STORAGE_BUCKET).upload(
37.             remote_name,
38.             data,
39.             file_options={
40.                 "content-type": "image/webp",
41.                 "upsert": "true",           # string, not bool — Supabase quirk
42.             },
43.         )
44.         public_url = sb.storage.from_(STORAGE_BUCKET).get_public_url(remote_name)
45.         # Supabase appends "?" sometimes — strip
46.         return public_url.rstrip("?")
47.     except Exception as e:
48.         log.warning("upload_image failed %s: %s", remote_name, e)
49.         return None
50. 
51. 
52. def insert_run(row: dict[str, Any]) -> str | None:
53.     """Insert a redesign_runs row, return generated id."""
54.     try:
55.         sb = client()
56.         res = sb.table("redesign_runs").insert(row).execute()
57.         return res.data[0]["id"] if res.data else None
58.     except Exception as e:
59.         log.error("insert_run failed: %s", e)
60.         return None
61. 
62. 
63. def update_run(run_id: str, fields: dict[str, Any]) -> bool:
64.     try:
65.         sb = client()
66.         sb.table("redesign_runs").update(fields).eq("id", run_id).execute()
67.         return True
68.     except Exception as e:
69.         log.error("update_run failed: %s", e)
70.         return False
71. 
72. 
73. def insert_story(row: dict[str, Any]) -> str | None:
74.     """Insert a redesign_stories row. Upsert on (published_date, category, story_slot)."""
75.     try:
76.         sb = client()
77.         res = sb.table("redesign_stories").upsert(
78.             row, on_conflict="published_date,category,story_slot"
79.         ).execute()
80.         return res.data[0]["id"] if res.data else None
81.     except Exception as e:
82.         log.error("insert_story failed: %s", e)
83.         return None
84.
```

</details>


### 💬 Copilot

Now let me check for env-loading patterns and look for logging of secrets:

### ✅ `grep`

**DEEPSEEK_API_KEY|SUPABASE_SERVICE_KEY|SUPABASE_URL**

"DEEPSEEK_API_KEY|SUPABASE_SERVICE_KEY|SUPABASE_URL"

<details>
<summary>41 matches</summary>

```
/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml:      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml:      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml:      SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml:          DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml:          SUPABASE_URL=${SUPABASE_URL}
/Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml:          SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:DEEPSEEK_API_KEY=<required>
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:SUPABASE_URL=<required>
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:SUPABASE_SERVICE_KEY=<required>
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:      'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:      'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:  process.env.SUPABASE_URL,
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:  process.env.SUPABASE_SERVICE_KEY
/Users/jiong/myprojects/news-v2/PIPELINE-IMPLEMENTATION.md:TAVILY_API_KEY=... DEEPSEEK_API_KEY=... node pipeline.mjs
/Users/jiong/myprojects/news-v2/vetter-comparison-test.mjs: *   - DEEPSEEK_API_KEY env var
/Users/jiong/myprojects/news-v2/vetter-comparison-test.mjs:const DEEPSEEK_KEY = process.env.DEEPSEEK_API_KEY || '';
/Users/jiong/myprojects/news-v2/vetter-comparison-test.mjs:    throw new Error('DEEPSEEK_API_KEY is required');
/Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-copilot-review.md:   - **Risk**: IfNow pipeline let me rea failsd all or the relevant logs are capture files:d, `DEEPSEEK_API_KEY` and `SUPABASE_SERVICE_KEY` become plaintext in GitHub logs
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_rewrite.py:DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_rewrite.py:    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
/Users/jiong/myprojects/news-v2/pipeline/main.py:    for k in ("TAVILY_API_KEY", "DEEPSEEK_API_KEY"):
/Users/jiong/myprojects/news-v2/pipeline/main.py:        "deepseek": os.getenv("DEEPSEEK_API_KEY"),
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_enrich.py:DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:    sb_base = os.environ["SUPABASE_URL"].rstrip("/")
/Users/jiong/myprojects/news-v2/pipeline/news_exa_pipeline.py:DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
/Users/jiong/myprojects/news-v2/pipeline/augment_mined_at.py:    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:SUPABASE_URL = os.environ.get("SUPABASE_URL")
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:        raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY must be set in .env")
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:    pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
/Users/jiong/myprojects/news-v2/pipeline/seed_source_configs.py:    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
/Users/jiong/myprojects/news-v2/docs/superpowers/specs/2026-04-23-kidsnews-v2-pipeline-design.md:- `DEEPSEEK_API_KEY`
/Users/jiong/myprojects/news-v2/docs/superpowers/specs/2026-04-23-kidsnews-v2-pipeline-design.md:- `SUPABASE_URL`
/Users/jiong/myprojects/news-v2/docs/superpowers/specs/2026-04-23-kidsnews-v2-pipeline-design.md:- `SUPABASE_SERVICE_KEY` (bypasses RLS)
/Users/jiong/myprojects/news-v2/website/data.jsx:const SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co';
/Users/jiong/myprojects/news-v2/website/data.jsx:const ARCHIVE_BASE = `${SUPABASE_URL}/storage/v1/object/public/redesign-daily-content`;
```

</details>


### ✅ `grep`

**log\.|print\(|sys\.stdout**

"log\.|print\(|sys\.stdout" in py files (pipeline)

<details>
<summary>32 matches</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/read.py:6
/Users/jiong/myprojects/news-v2/pipeline/main.py:23
/Users/jiong/myprojects/news-v2/pipeline/augment_mined_at.py:2
/Users/jiong/myprojects/news-v2/pipeline/output.py:4
/Users/jiong/myprojects/news-v2/pipeline/curator.py:2
/Users/jiong/myprojects/news-v2/pipeline/image_optimize.py:4
/Users/jiong/myprojects/news-v2/pipeline/tune_query.py:10
/Users/jiong/myprojects/news-v2/pipeline/backfill_card_summaries.py:5
/Users/jiong/myprojects/news-v2/pipeline/tune_news.py:12
/Users/jiong/myprojects/news-v2/pipeline/test_fun_feeds.py:6
/Users/jiong/myprojects/news-v2/pipeline/vet.py:1
/Users/jiong/myprojects/news-v2/pipeline/enrich_existing.py:8
/Users/jiong/myprojects/news-v2/pipeline/seed_source_configs.py:3
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_rewrite.py:27
/Users/jiong/myprojects/news-v2/pipeline/test_science_feeds.py:7
/Users/jiong/myprojects/news-v2/pipeline/news_aj_rss.py:10
/Users/jiong/myprojects/news-v2/pipeline/discover.py:9
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:4
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_enrich.py:10
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:21
/Users/jiong/myprojects/news-v2/pipeline/news_raw_list.py:6
/Users/jiong/myprojects/news-v2/pipeline/news_exa_pipeline.py:14
/Users/jiong/myprojects/news-v2/pipeline/news_exa_list.py:9
/Users/jiong/myprojects/news-v2/pipeline/news_aggregate.py:21
/Users/jiong/myprojects/news-v2/pipeline/news_guardian_full.py:21
/Users/jiong/myprojects/news-v2/pipeline/test_replacement_feeds.py:9
/Users/jiong/myprojects/news-v2/pipeline/science_aggregate.py:15
/Users/jiong/myprojects/news-v2/pipeline/full_round.py:30
/Users/jiong/myprojects/news-v2/pipeline/test_sciencedaily_topics.py:6
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:33
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:15
/Users/jiong/myprojects/news-v2/pipeline/fun_aggregate.py:14
```

</details>


### 💬 Copilot

Let me check the news_rss_core.py for logging of sensitive data and API calls:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 1-150)

<details>
<summary>150 lines</summary>

```
1. """Shared core for RSS → filter → batched vet+cluster → batched rewrite.
2. 
3. Used by news_aj_full.py and news_pbs_full.py. Parameterized by:
4.   - RSS URL
5.   - source label (for HTML title)
6.   - MAX_KEPT (cap on articles sent to vetter)
7.   - PICK_COUNT (how many the curator picks)
8.   - TARGET_WORDS (kids article length)
9.   - output filenames
10. 
11. Vet thresholds (locked 2026-04-23):
12.   - REJECT if any dim >= 4 OR total > 6
13.   - CAUTION if total 5-6 AND every dim <= 3
14.   - SAFE if total 0-4 AND every dim <= 3
15. """
16. from __future__ import annotations
17. 
18. import html
19. import json
20. import logging
21. import os
22. import re
23. import time
24. from datetime import datetime, timezone
25. from pathlib import Path
26. from urllib.parse import urlparse
27. 
28. import feedparser
29. import requests
30. 
31. from .cleaner import extract_article_from_html
32. 
33. log = logging.getLogger("rss-core")
34. 
35. # Load .env once on module import
36. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
37. for _line in (_envp.open() if _envp.exists() else []):
38.     if "=" in _line and not _line.startswith("#"):
39.         _k, _v = _line.strip().split("=", 1)
40.         os.environ[_k] = _v
41. 
42. DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
43. DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
44. 
45. MIN_WORDS_DEFAULT = 500
46. MAX_RSS_DEFAULT = 25
47. VIDEO_PATH_RE = re.compile(r"/video/", re.I)
48. HTML_FETCH_TIMEOUT = 15
49. HTML_FETCH_HEADERS = {
50.     # Real browser UA — NPR and some others block bot-flavored UAs.
51.     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
52.                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
53.     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
54.     "Accept-Language": "en-US,en;q=0.9",
55. }
56. 
57. SAFETY_DIMS = ["violence", "sexual", "substance", "language", "fear",
58.                "adult_themes", "distress", "bias"]
59. SAFETY_SHORT = ["Viol", "Sex", "Subst", "Lang", "Fear", "Adult", "Distr", "Bias"]
60. 
61. # Generic social-share default images (usually a site logo or blank template,
62. # not a real article image). Detected by URL substring.
63. BAD_IMAGE_PATTERNS = (
64.     "facebook-default",
65.     "twitter-default",
66.     "og-default",
67.     "share-default",
68.     "default-share",
69.     "default-og",
70.     "default-social",
71. )
72. 
73. MIN_PICK_BODY_WORDS = 250   # fall back to alternate if pick's body is thinner than this
74. 
75. 
76. def is_generic_social_image(url: str | None) -> bool:
77.     if not url:
78.         return True
79.     u = url.lower()
80.     return any(p in u for p in BAD_IMAGE_PATTERNS)
81. 
82. 
83. # ---------------------------------------------------------------------------
84. # Vet threshold evaluator (Python-side, authoritative)
85. # ---------------------------------------------------------------------------
86. 
87. def apply_vet_thresholds(safety: dict) -> str:
88.     """Authoritative verdict from safety scores.
89. 
90.     REJECT if any dim >= 4 OR total > 6.
91.     CAUTION if total 5-6 AND every dim <= 3.
92.     SAFE if total 0-4 AND every dim <= 3.
93.     """
94.     dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
95.     total = safety.get("total")
96.     if total is None:
97.         total = sum(dims)
98.     max_dim = max(dims) if dims else 0
99.     if max_dim >= 4 or total > 6:
100.         return "REJECT"
101.     if 5 <= total <= 6:
102.         return "CAUTION"
103.     return "SAFE"
104. 
105. 
106. # ---------------------------------------------------------------------------
107. # Step 1+2: RSS + HTML scrape + filter
108. # ---------------------------------------------------------------------------
109. 
110. def fetch_rss_entries(url: str, max_entries: int = MAX_RSS_DEFAULT) -> list[dict]:
111.     feed = feedparser.parse(url)
112.     out = []
113.     for entry in feed.entries[:max_entries]:
114.         out.append({
115.             "title": getattr(entry, "title", ""),
116.             "link": getattr(entry, "link", ""),
117.             "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
118.             "summary": getattr(entry, "summary", ""),
119.         })
120.     return out
121. 
122. 
123. def fetch_html(url: str) -> str | None:
124.     try:
125.         r = requests.get(url, timeout=HTML_FETCH_TIMEOUT, headers=HTML_FETCH_HEADERS,
126.                          allow_redirects=True)
127.         if r.status_code >= 400:
128.             return None
129.         return r.text
130.     except requests.RequestException:
131.         return None
132. 
133. 
134. def process_entry(entry: dict, min_words: int = MIN_WORDS_DEFAULT) -> dict:
135.     url = entry["link"]
136.     if VIDEO_PATH_RE.search(url):
137.         return {**entry, "og_image": None, "body": "", "word_count": 0,
138.                 "skip_reason": "video URL", "highlights": [], "paragraphs": []}
139.     html_text = fetch_html(url)
140.     if not html_text:
141.         return {**entry, "og_image": None, "body": "", "word_count": 0,
142.                 "skip_reason": "html fetch failed", "highlights": [], "paragraphs": []}
143.     extracted = extract_article_from_html(url, html_text)
144.     body = extracted.get("cleaned_body") or ""
145.     paragraphs = extracted.get("paragraphs") or []
146.     og_image = extracted.get("og_image")
147.     wc = len(body.split()) if body else 0
148.     skip_reason = None
149.     if wc < min_words:
150.         skip_reason = f"{wc}w < {min_words}w"
```

</details>


### ✅ `bash`

**Find logging statements in news_rss_core.py**

$ grep -n "log\." /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py | head -30

<details>
<summary>31 lines</summary>

```
266:            log.warning("chat attempt %d/%d failed: %s",
302:            log.warning("  dropping picked id=%s — REJECT on strict thresholds", pid)
626:            log.info("  [%s] dropped hallucinated keywords: %s", slot_key, dropped)
657:            log.warning("reasoner attempt %d/%d failed: %s",
696:        log.warning("detail_enrich 6-slot call failed after retries (%s) — "
708:                log.info("split-batch %s: %d slots OK", level,
711:                log.error("split-batch %s failed: %s", level, e2)
820:    log.info("[%s] Phase A: flow=%s", source.name, source.flow)
822:    log.info("[%s]  RSS entries: %d", source.name, len(rss_entries))
830:            log.warning("[%s]  only %d kept — insufficient for choice_1+choice_2", source.name, len(kept))
848:            log.warning("[%s]  only %d briefs — insufficient", source.name, len(briefs))
851:    log.info("[%s]  vetter input: %d briefs (reasoner)", source.name, len(briefs))
889:            log.info("[%s]  fetching [%s id=%d] %s", source.name, slot, cid,
898:            log.info("[%s]  ✓ [%s id=%d] %dw", source.name, slot, cid,
901:            log.info("[%s]  ✗ [%s id=%d] %s — %s", source.name, slot, cid,
905:        log.warning("[%s]  no viable candidate after %d attempts", source.name,
909:    log.info("[%s]  → %d candidates ready", source.name, len(candidates))
1159:    log.info("[%s] Step 1: fetch RSS %s", source_label, rss_url)
1161:    log.info("  %d entries", len(rss_entries))
1163:    log.info("[%s] Step 2: scrape + filter (≥%dw, has image, not /video/)", source_label, min_words)
1167:    log.info("  kept=%d, rejected=%d", len(kept), len(rejected))
1171:        log.info("  capping kept at %d for vetter (was %d)", max_kept, len(kept))
1175:        log.error("Only %d kept — need ≥ %d", len(kept), pick_count)
1178:    log.info("[%s] Step 3: batched vet+cluster+pick (1 call, %d in)", source_label, len(kept))
1182:    log.info("  clusters: %d (hot: %d)", len(clusters),
1184:    log.info("  picks: %s", [p.get("id") for p in picks])
1188:            log.info("    ★ [%s] %s", pid, kept[pid].get("title",""))
1191:        log.warning("Curator returned only %d picks (wanted %d)", len(picks), pick_count)
1193:        log.error("No picks returned — aborting")
1196:    log.info("[%s] Step 4: batched rewrite (1 call, %d in)", source_label, len(picks))
<exited with exit code 0>
```

</details>


### 💬 Copilot

Let me check for logging of URLs that might contain secrets or API keys in more detail:

### ✅ `bash`

**Search for potential secret logging**

$ grep -r "log\..*DEEPSEEK\|log\..*SUPABASE\|log\..*url\|log\..*token\|log\..*key" /Users/jiong/myprojects/news-v2/pipeline --include="*.py" | head -20

<details>
<summary>21 lines</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/news_guardian_full.py:        log.info("  fetching [%d] %s", pid, url)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:        log.info("uploaded %s", key)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:        log.info("uploaded %s", key)
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:            log.info("  [%s] dropped hallucinated keywords: %s", slot_key, dropped)
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:    log.info("[%s] Step 1: fetch RSS %s", source_label, rss_url)
/Users/jiong/myprojects/news-v2/pipeline/full_round.py:    log.info("=== PERSIST TO SUPABASE ===")
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:        log.warning("fetch failed %s: %s", url, e)
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:    log.info("=== SYNC IMAGES FROM SUPABASE (missing-only) ===")
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:                    log.warning("  image fetch %s: %s", url, e)
/Users/jiong/myprojects/news-v2/pipeline/discover.py:            log.info("HTML fetch %s -> %d", url, r.status_code)
/Users/jiong/myprojects/news-v2/pipeline/discover.py:            log.info("HTML fetch %s -> non-html (%s)", url, ct)
/Users/jiong/myprojects/news-v2/pipeline/discover.py:        log.info("HTML fetch failed %s: %s", url, e)
/Users/jiong/myprojects/news-v2/pipeline/discover.py:            log.info("skipping non-article URL: %s", url)
/Users/jiong/myprojects/news-v2/pipeline/discover.py:            log.info("skipping advertisement/deals listicle: %s | %s", url, title[:80])
/Users/jiong/myprojects/news-v2/pipeline/discover.py:            log.info("skipping video article: %s | %s", url, title[:80])
/Users/jiong/myprojects/news-v2/pipeline/discover.py:            log.info("extract_article_from_html failed for %s: %s", url, e)
/Users/jiong/myprojects/news-v2/pipeline/discover.py:        log.warning("feedparser failed for %s: %s", feed_url, e)
/Users/jiong/myprojects/news-v2/pipeline/image_optimize.py:            log.warning("image download %s -> %d", url, r.status_code)
/Users/jiong/myprojects/news-v2/pipeline/image_optimize.py:            log.warning("image download %s -> non-image content-type: %s", url, ct)
/Users/jiong/myprojects/news-v2/pipeline/image_optimize.py:        log.warning("image download failed %s: %s", url, e)
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check manifest logging**

$ grep -r "manifest\['zip_sha256" /Users/jiong/myprojects/news-v2/pipeline

```

<exited with exit code 1>
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py (lines 405-445)

<details>
<summary>41 lines</summary>

```
405.         log.info("uploaded %s", key)
406. 
407.     log.info("manifest: version=%s · zip_bytes=%d · zip_sha256=%s · stories=%d",
408.              manifest["version"], manifest["zip_bytes"],
409.              manifest["zip_sha256"][:12], manifest["story_count"])
410. 
411.     # Flat per-day files — the UI fetches these when user picks a past date.
412.     try:
413.         upload_dated_flat_files(sb, today)
414.     except Exception as e:  # noqa: BLE001
415.         log.warning("dated-flat upload failed (non-fatal): %s", e)
416. 
417.     # Read existing archive-index, backfill any dated zip that doesn't yet
418.     # have a flat dir, then update archive-index with both backfilled +
419.     # today's date.
420.     try:
421.         body = sb.storage.from_(BUCKET).download("archive-index.json")
422.         existing_idx = json.loads(body.decode() if isinstance(body, bytes) else body)
423.         existing_dates = existing_idx.get("dates") or []
424.     except Exception:
425.         existing_dates = []
426.     try:
427.         backfilled = backfill_missing_archive_dirs(sb, existing_dates)
428.         if backfilled:
429.             log.info("archive backfill: %s", backfilled)
430.         update_archive_index(sb, [today] + backfilled)
431.     except Exception as e:  # noqa: BLE001
432.         log.warning("archive-index update failed (non-fatal): %s", e)
433. 
434.     # Retention sweep: delete dated archives older than RETENTION_DAYS.
435.     try:
436.         cleanup_retention(sb, RETENTION_DAYS)
437.     except Exception as e:  # noqa: BLE001
438.         log.warning("retention sweep failed (non-fatal): %s", e)
439. 
440.     pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
441.     log.info("public URL: %s", pub)
442. 
443. 
444. if __name__ == "__main__":
445.     main()
```

</details>


### ✅ `bash`

**Check bundle None handling**

$ grep -A5 "if bundle is not None" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py | head -20

<details>
<summary>7 lines</summary>

```
if bundle is not None:
        zf = zipfile.ZipFile(BytesIO(bundle))
        members = [n for n in zf.namelist()
                   if n.endswith(".json") or n.endswith(".webp")]
        for name in members:
            body = zf.read(name)
<exited with exit code 0>
```

</details>


### 💬 Copilot

Now let me examine error handling in full_round.py and whether partial uploads can happen:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 100-250)

<details>
<summary>151 lines</summary>

```
100.         log.warning("past-dedup skipped — Supabase unreachable: %s", e)
101.         return by_source
102.     start = (date.today() - timedelta(days=days)).isoformat()
103.     try:
104.         r = sb.table("redesign_stories").select(
105.             "source_title, category, published_date"
106.         ).eq("category", category).gte("published_date", start).execute()
107.         past_titles = [row.get("source_title") or "" for row in (r.data or [])]
108.     except Exception as e:
109.         log.warning("past-dedup query failed — skipping: %s", e)
110.         return by_source
111. 
112.     if not past_titles:
113.         log.info("  [%s] past-dedup: no prior stories in last %d days", category, days)
114.         return by_source
115. 
116.     result: dict[str, dict] = {}
117.     for name, bundle in by_source.items():
118.         kept: list[dict] = []
119.         for c in bundle["candidates"]:
120.             t = (c["winner"].get("title") or "")
121.             best = max((_title_similarity(t, pt) for pt in past_titles), default=0.0)
122.             if best >= threshold:
123.                 log.info("  [%s/%s] past-dup drop %s (sim=%.2f) — %s",
124.                          category, name, c.get("slot"), best, t[:60])
125.             else:
126.                 kept.append(c)
127.         result[name] = {"source": bundle["source"], "candidates": kept}
128.     return result
129. 
130. 
131. def pick_winners_with_dedup(by_source: dict[str, dict]) -> list[dict]:
132.     """Pick the highest-ranked surviving candidate per source, then
133.     cross-source dedup. When a pair of today's picks duplicates, drop the
134.     weaker source's current pick and promote its NEXT candidate (no extra
135.     DeepSeek-and-RSS round-trip — we already mined up to 4 per source)."""
136.     ptrs: dict[str, int] = {name: 0 for name in by_source}
137.     exhausted: set[str] = set()
138. 
139.     def current_for(name: str) -> dict | None:
140.         idx = ptrs.get(name, 0)
141.         cands = by_source[name].get("candidates") or []
142.         return cands[idx] if idx < len(cands) else None
143. 
144.     for _round in range(8):
145.         picks: list[tuple[str, dict]] = []
146.         for name in by_source:
147.             if name in exhausted:
148.                 continue
149.             c = current_for(name)
150.             if c:
151.                 picks.append((name, c))
152.         if len(picks) < 2:
153.             break
154.         briefs = [
155.             {"id": i, "title": c["winner"].get("title"),
156.              "source_name": name,
157.              "source_priority": getattr(by_source[name]["source"], "priority", 9),
158.              "excerpt": (c["winner"].get("body") or "")[:400]}
159.             for i, (name, c) in enumerate(picks)
160.         ]
161.         dup = check_duplicates(briefs)
162.         if dup.get("verdict") != "DUP_FOUND":
163.             break
164.         drop_id = dup.get("drop_suggestion")
165.         if drop_id is None and dup.get("duplicate_pairs"):
166.             pair = dup["duplicate_pairs"][0]["ids"]
167.             drop_id = max(pair, key=lambda i: briefs[i]["source_priority"])
168.         if drop_id is None or drop_id >= len(picks):
169.             break
170.         drop_name, drop_cand = picks[drop_id]
171.         log.info("  cross-source dup — promoting next candidate for [%s] "
172.                  "(was %s: %s)",
173.                  drop_name, drop_cand["slot"],
174.                  (drop_cand["winner"].get("title") or "")[:50])
175.         ptrs[drop_name] += 1
176.         if ptrs[drop_name] >= len(by_source[drop_name].get("candidates") or []):
177.             log.warning("  [%s] exhausted all candidates — skipping", drop_name)
178.             exhausted.add(drop_name)
179. 
180.     final: list[dict] = []
181.     for name, bundle in by_source.items():
182.         if name in exhausted:
183.             continue
184.         c = current_for(name)
185.         if c:
186.             final.append({
187.                 "source": bundle["source"],
188.                 "winner": c["winner"],
189.                 "winner_slot": c["slot"],
190.             })
191.     return final
192. 
193. 
194. # -------------------------------------------------------------------
195. # 2) Optimize + upload images
196. # -------------------------------------------------------------------
197. 
198. def _short_hash(s: str) -> str:
199.     return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
200. 
201. 
202. def process_images(stories: list[dict], today: str, website_dir: Path) -> None:
203.     """For each story winner, download + optimize og:image → local cache + Supabase Storage.
204.     Annotates each story dict with _image_local, _image_storage_url.
205.     """
206.     images_dir = website_dir / "article_images"
207.     images_dir.mkdir(parents=True, exist_ok=True)
208.     for s in stories:
209.         art = s["winner"]
210.         og = art.get("og_image")
211.         if not og:
212.             log.warning("[%s] no og:image", art.get("title", "")[:60])
213.             continue
214.         img_id = _short_hash(art.get("link") or og)
215.         filename = f"article_{img_id}.webp"
216.         local_path = images_dir / filename
217.         info = fetch_and_optimize(og, local_path)
218.         if not info:
219.             log.warning("  skip image for %s", art.get("title", "")[:60])
220.             continue
221.         s["_image_id"] = img_id
222.         s["_image_local"] = f"article_images/{filename}"
223.         s["_image_info"] = info
224.         # Upload to Supabase Storage (public)
225.         storage_name = f"{today}/{filename}"
226.         storage_url = upload_image(local_path, storage_name)
227.         if storage_url:
228.             s["_image_storage_url"] = storage_url
229.         log.info("  ✓ image %s (%.1f KB, q=%d)  %s",
230.                  filename, info["final_bytes"] / 1024, info["final_quality"],
231.                  "+ uploaded" if storage_url else "local-only")
232. 
233. 
234. # -------------------------------------------------------------------
235. # 3) Rewrite (tri-variant) — batched per category
236. # -------------------------------------------------------------------
237. 
238. def rewrite_for_category(stories: list[dict]) -> tuple[dict[int, dict], dict]:
239.     """Tri-variant rewrite, then detail enrichment. Returns
240.     (variants_by_src_id, details_by_slot). Raises if either step ultimately
241.     fails — callers decide whether that's fatal for the whole run."""
242.     if not stories:
243.         return {}, {}
244.     articles_for_rewrite = [(i, s["winner"]) for i, s in enumerate(stories)]
245.     rewrite_res = tri_variant_rewrite(articles_for_rewrite)
246.     variants = {a.get("source_id"): a for a in rewrite_res.get("articles") or []}
247.     if len(variants) < len(stories):
248.         raise RuntimeError(
249.             f"rewrite returned {len(variants)} variants for {len(stories)} stories"
250.         )
```

</details>


### ✅ `bash`

**Check how pack_and_upload is called**

$ grep -n "pack_and_upload\|validate_bundle\|import pack_and_upload" /Users/jiong/myprojects/news-v2/pipeline/full_round.py

```
529:        from .pack_and_upload import main as _pack_upload
532:        log.warning("pack_and_upload failed — site will lag until next run: %s", e)
<exited with exit code 0>
```


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 520-550)

<details>
<summary>24 lines</summary>

```
520.     count = 0
521.     if run_id:
522.         count = persist_to_supabase(stories_by_cat, variants_by_cat, today, run_id)
523.         update_run(run_id, {"status": "completed",
524.                             "finished_at": datetime.now(timezone.utc).isoformat(),
525.                             "notes": f"stories persisted: {count}"})
526. 
527.     log.info("=== PACK + UPLOAD ZIP (deploy trigger) ===")
528.     try:
529.         from .pack_and_upload import main as _pack_upload
530.         _pack_upload()
531.     except Exception as e:  # noqa: BLE001
532.         log.warning("pack_and_upload failed — site will lag until next run: %s", e)
533. 
534.     log.info("=== DONE ===")
535.     total_stories = sum(len(ws) for ws in stories_by_cat.values())
536.     log.info("Run: %s · Stories: %d · DB persisted: %d", run_id or "(no DB)",
537.              total_stories, count)
538.     log.info("View: http://localhost:18100/")
539. 
540. 
541. if __name__ == "__main__":
542.     main()
543.
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 250-350)

<details>
<summary>101 lines</summary>

```
250.         )
251. 
252.     # Phase D — detail enrichment (1 extra call per category)
253.     enrich = detail_enrich(rewrite_res)
254.     details_by_slot = enrich.get("details") or {}
255.     expected_slots = len(stories) * 2  # easy + middle per story
256.     if len(details_by_slot) < expected_slots:
257.         raise RuntimeError(
258.             f"detail_enrich returned {len(details_by_slot)} slots, "
259.             f"expected {expected_slots}"
260.         )
261.     return variants, details_by_slot
262. 
263. 
264. # -------------------------------------------------------------------
265. # 4) Emit v1-shape payload files (what the existing v2 UI reads)
266. # -------------------------------------------------------------------
267. 
268. def make_story_id(date: str, category: str, slot: int) -> str:
269.     return f"{date}-{category.lower()}-{slot}"
270. 
271. 
272. def card_summary(variant: dict, max_words: int = 120) -> str:
273.     """Short blurb for the home-page card. Prefer `card_summary` from the
274.     rewriter; fall back to the first few sentences of `body` capped at
275.     `max_words`. Strip to whole sentence so it never ends mid-word."""
276.     cs = (variant.get("card_summary") or "").strip()
277.     if cs:
278.         words = cs.split()
279.         if len(words) <= max_words:
280.             return cs
281.         return " ".join(words[:max_words]).rstrip(",;:") + "…"
282.     body = (variant.get("body") or "").strip()
283.     if not body:
284.         return ""
285.     import re
286.     sentences = re.split(r'(?<=[.!?])\s+', body)
287.     out, count = [], 0
288.     for s in sentences:
289.         n = len(s.split())
290.         if count + n > max_words and out:
291.             break
292.         out.append(s)
293.         count += n
294.         if count >= max_words * 0.6:  # stop once we have a reasonable blurb
295.             break
296.     return " ".join(out).strip()
297. 
298. 
299. def emit_v1_shape(stories_by_cat: dict[str, list[dict]],
300.                   variants_by_cat: dict[str, dict[int, dict]],
301.                   details_by_cat: dict[str, dict[str, dict]],
302.                   today: str,
303.                   website_dir: Path) -> None:
304.     """Write v1-compatible payload files the prototype UI already reads:
305.       payloads/articles_<cat>_<level>.json  (listings)
306.       article_payloads/payload_<id>/<level>.json  (detail)
307.     """
308.     payloads_dir = website_dir / "payloads"
309.     details_dir = website_dir / "article_payloads"
310.     payloads_dir.mkdir(parents=True, exist_ok=True)
311.     details_dir.mkdir(parents=True, exist_ok=True)
312. 
313.     mined_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
314. 
315.     for category in ("News", "Science", "Fun"):
316.         stories = stories_by_cat.get(category, [])
317.         variants = variants_by_cat.get(category, {})
318.         details = details_by_cat.get(category, {})
319.         # Build one listing file per level (easy / middle / cn) per category
320.         per_level_articles = {"easy": [], "middle": [], "cn": []}
321.         for slot, s in enumerate(stories, start=1):
322.             art = s["winner"]
323.             var = variants.get(slot - 1) or {}
324.             story_id = s.get("_story_id") or make_story_id(today, category, slot)
325.             s["_story_id"] = story_id
326.             img_local = s.get("_image_local") or ""
327.             src_name = s["source"].name
328.             src_url = art.get("link") or ""
329.             time_ago = art.get("published") or ""
330. 
331.             easy = var.get("easy_en") or {}
332.             middle = var.get("middle_en") or {}
333.             zh = var.get("zh") or {}
334. 
335.             # Listings (flat, v1-shape) — summary is short card blurb (≤120 words)
336.             common_listing = {
337.                 "id": story_id,
338.                 "source": src_name,
339.                 "time_ago": time_ago,
340.                 "mined_at": mined_at,                  # when this pipeline run captured the story
341.                 "source_published_at": art.get("published") or "",
342.                 "image_url": f"/{img_local}" if img_local else "",
343.                 "category": category,
344.             }
345.             per_level_articles["easy"].append({**common_listing,
346.                 "title": easy.get("headline") or art.get("title") or "",
347.                 "summary": card_summary(easy),
348.             })
349.             per_level_articles["middle"].append({**common_listing,
350.                 "title": middle.get("headline") or art.get("title") or "",
```

</details>


### 💬 Copilot

Let me check env loading security more thoroughly:

### ✅ `bash`

**Find .env file patterns**

$ find /Users/jiong/myprojects/news-v2 -name ".env*" -o -name "*.py" -exec grep -l "_envp\|\.env\|os.environ" {} \; | head -20

<details>
<summary>21 lines</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/news_exa_list.py
/Users/jiong/myprojects/news-v2/pipeline/test_replacement_feeds.py
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py
/Users/jiong/myprojects/news-v2/pipeline/seed_source_configs.py
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py
/Users/jiong/myprojects/news-v2/pipeline/tune_query.py
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py
/Users/jiong/myprojects/news-v2/pipeline/test_fun_feeds.py
/Users/jiong/myprojects/news-v2/pipeline/tune_news.py
/Users/jiong/myprojects/news-v2/pipeline/augment_mined_at.py
/Users/jiong/myprojects/news-v2/pipeline/news_raw_list.py
/Users/jiong/myprojects/news-v2/pipeline/news_exa_pipeline.py
/Users/jiong/myprojects/news-v2/pipeline/test_sciencedaily_topics.py
/Users/jiong/myprojects/news-v2/pipeline/test_science_feeds.py
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_enrich.py
/Users/jiong/myprojects/news-v2/pipeline/main.py
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_rewrite.py
/Users/jiong/myprojects/news-v2/pipeline/backfill_card_summaries.py
/Users/jiong/myprojects/news-v2/.venv/lib/python3.14/site-packages/packaging/pylock.py
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check .gitignore for .env**

$ cat /Users/jiong/myprojects/news-v2/.gitignore 2>/dev/null | grep -E ".env|secrets"

```
.env
.env.local
.venv/
<exited with exit code 0>
```


### 💬 Copilot

Now let me examine the artifact upload and see if there could be any secret exposure:

### ✅ `bash`

**Check artifact upload configuration**

$ grep -A10 "upload-artifact" /Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml

<details>
<summary>8 lines</summary>

```
uses: actions/upload-artifact@v4
        with:
          name: website-payloads-${{ github.run_id }}
          path: |
            website/payloads/
            website/article_payloads/
          retention-days: 7
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check what's in payloads**

$ ls -la /Users/jiong/myprojects/news-v2/website/payloads 2>/dev/null | head -10

<details>
<summary>11 lines</summary>

```
total 96
drwxr-xr-x@ 11 jiong  staff   352 Apr 23 23:11 .
drwxr-xr-x@ 27 jiong  staff   864 Apr 24 18:44 ..
-rw-r--r--@  1 jiong  staff  4552 Apr 24 09:24 articles_fun_cn.json
-rw-r--r--@  1 jiong  staff  2441 Apr 24 09:24 articles_fun_easy.json
-rw-r--r--@  1 jiong  staff  2612 Apr 24 09:24 articles_fun_middle.json
-rw-r--r--@  1 jiong  staff  4893 Apr 24 09:24 articles_news_cn.json
-rw-r--r--@  1 jiong  staff  3246 Apr 24 09:24 articles_news_easy.json
-rw-r--r--@  1 jiong  staff  3348 Apr 24 09:24 articles_news_middle.json
-rw-r--r--@  1 jiong  staff  5335 Apr 24 09:24 articles_science_cn.json
<exited with exit code 0>
```

</details>


### 💬 Copilot

Let me check the requirements.txt to understand dependencies and any potential security issues:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/requirements.txt.**

/Users/jiong/myprojects/news-v2/requirements.txt

<details>
<summary>7 lines</summary>

```
1. beautifulsoup4>=4.12
2. feedparser>=6.0
3. pillow>=10.3
4. python-dotenv>=1.0
5. requests>=2.31
6. supabase>=2.7
7.
```

</details>


### ✅ `bash`

**Check for env var bypass**

$ grep -n "ALLOW_STALE" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py

```
373:               "If you really want to overwrite, set ALLOW_STALE_UPLOAD=1.")
374:        if os.environ.get("ALLOW_STALE_UPLOAD") != "1":
377:        log.warning("ALLOW_STALE_UPLOAD=1 set — proceeding despite: %s", msg)
<exited with exit code 0>
```


### 💬 Copilot

Let me check for any logging of environment variables or secrets in the pipeline code:

### ✅ `bash`

**Look for secret exposure in pack_and_upload**

$ grep -rn "environ\|log.info\|log.warning\|log.error" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py | grep -E "SUPABASE|DEEPSEEK|environ\['|environ\[\"" | head -20

```
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:386:    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:440:    pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
<exited with exit code 0>
```


### ✅ `bash`

**Check direct environ access**

$ grep -n "os.environ\[" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py

```
35:        os.environ[k] = v
386:    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
440:    pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
<exited with exit code 0>
```


### 💬 Copilot

Let me check for any other issues with the workflow and partial failure scenarios:

### ✅ `bash`

**Check backfill logic for potential blind spots**

$ grep -B5 -A10 "def backfill_missing_archive_dirs" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py | head -25

<details>
<summary>15 lines</summary>

```
)
    log.info("archive-index updated: %d dates (newest=%s)",
             len(all_dates), all_dates[0] if all_dates else "-")


def backfill_missing_archive_dirs(sb, current_index: list[str]) -> list[str]:
    """For any YYYY-MM-DD.zip in the bucket whose date isn't in the archive
    index AND doesn't yet have its flat dir, extract the zip and upload
    flat files. Returns list of backfilled dates."""
    current_set = set(current_index)
    objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
    candidates = []
    for o in objs or []:
        m = DATED_ZIP_RE.match(o.get("name") or "")
        if m and m.group(1) not in current_set:
            candidates.append(m.group(1))
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check for existence checks**

$ grep -n "if already" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py

```

<exited with exit code 1>
```


### 💬 Copilot

Let me check for potential issues with logging configuration and whether secrets could leak through standard output:

### ✅ `bash`

**Check logging configuration**

$ grep -n "logging.basicConfig\|StreamHandler" /Users/jiong/myprojects/news-v2/pipeline/*.py | head -10

<details>
<summary>11 lines</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/augment_mined_at.py:16:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/backfill_card_summaries.py:14:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/enrich_existing.py:21:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/full_round.py:33:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/fun_aggregate.py:32:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/main.py:25:logging.basicConfig(
/Users/jiong/myprojects/news-v2/pipeline/news_aggregate.py:40:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/news_aj_full.py:9:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/news_aj_rss.py:21:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
/Users/jiong/myprojects/news-v2/pipeline/news_bbc_full.py:14:logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check if python-dotenv is really used**

$ python3 -c "from dotenv import load_dotenv; print('dotenv available')" 2>&1

<details>
<summary>6 lines</summary>

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from dotenv import load_dotenv; print('dotenv available')
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ModuleNotFoundError: No module named 'dotenv'
<exited with exit code 1>
```

</details>


### 💬 Copilot

Let me examine the actual secret masking issue more carefully and check if there are any bypass scenarios:

### ✅ `bash`

**Check direct secret usage in code**

$ grep -n "DEEPSEEK_API_KEY\|SUPABASE" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py | head -5

```
42:DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
<exited with exit code 0>
```


### ✅ `bash`

**Check for API calls that might log details**

$ grep -n "requests\|http\|api" /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py | head -20

<details>
<summary>12 lines</summary>

```
29:import requests
43:DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
125:        r = requests.get(url, timeout=HTML_FETCH_TIMEOUT, headers=HTML_FETCH_HEADERS,
130:    except requests.RequestException:
248:            r = requests.post(DEEPSEEK_ENDPOINT,
263:        except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
264:                requests.Timeout) as e:
638:            r = requests.post(
654:        except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
655:                requests.Timeout) as e:
1232:    log.info("View: http://localhost:18100/%s.html", output_slug)
<exited with exit code 0>
```

</details>


### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 240-280)

<details>
<summary>41 lines</summary>

````
240. 
241. def deepseek_call(system: str, user: str, max_tokens: int, temperature: float = 0.2,
242.                   max_attempts: int = 3) -> dict:
243.     """Call deepseek-chat with JSON output. Retries on JSON parse failure
244.     (model occasionally emits malformed JSON) and transient HTTP errors."""
245.     last_err: Exception | None = None
246.     for attempt in range(1, max_attempts + 1):
247.         try:
248.             r = requests.post(DEEPSEEK_ENDPOINT,
249.                 json={
250.                     "model": "deepseek-chat",
251.                     "messages": [{"role": "system", "content": system},
252.                                  {"role": "user", "content": user}],
253.                     "temperature": temperature,
254.                     "max_tokens": max_tokens,
255.                 },
256.                 headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
257.                 timeout=120)
258.             r.raise_for_status()
259.             content = r.json()["choices"][0]["message"]["content"]
260.             content = re.sub(r"^```json\s*", "", content.strip())
261.             content = re.sub(r"\s*```\s*$", "", content)
262.             return json.loads(content)
263.         except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
264.                 requests.Timeout) as e:
265.             last_err = e
266.             log.warning("chat attempt %d/%d failed: %s",
267.                         attempt, max_attempts, str(e)[:200])
268.             if attempt < max_attempts:
269.                 time.sleep(2 * attempt)
270.     raise RuntimeError(f"deepseek_call exhausted {max_attempts} attempts") from last_err
271. 
272. 
273. def vet_curator_input(briefs: list[dict], pick_count: int) -> str:
274.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.",
275.              f"Articles to vet + cluster + pick {pick_count}:", ""]
276.     for i, b in enumerate(briefs):
277.         hls = b.get("highlights") or []
278.         hls_text = " ".join(hls)[:400] if hls else (b.get("summary", "") or "")[:400]
279.         lines.append(f"[id: {i}] {b.get('title','')}")
280.         lines.append(f"  first paragraphs: {hls_text}")
````

</details>


### 💬 Copilot

Let me check if there's any risk of the .env file being checked in or exported:

### ✅ `bash`

**Check .gitignore**

$ cat /Users/jiong/myprojects/news-v2/.gitignore

<details>
<summary>20 lines</summary>

```
.DS_Store
.env
.env.local
node_modules/
*.log
*.tmp
*.backup

# Python
.venv/
__pycache__/
*.pyc

# Local API-key helper scripts (interactive installers; never pushed)
add-*-key.sh
add-pipeline-keys.sh

# Pipeline run output (not committed)
website/test_output/

# Prototype scratch (not part of repo history)
newdesign/screenshots/
newdesign/uploads/
<exited with exit code 0>
```

</details>


### ✅ `bash`

**Check for uncommitted .env**

$ git -C /Users/jiong/myprojects/news-v2 status --short 2>/dev/null | head -10

```
?? docs/reviews/
<exited with exit code 0>
```


### 💬 Copilot

Let me check the validate_bundle edge cases more carefully:

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py (lines 74-110)

<details>
<summary>37 lines</summary>

```
74. def validate_bundle(today: str) -> None:
75.     """Fail (SystemExit 1) if today's bundle is incomplete. Check:
76.       · 9 listing files (3 cats × easy/middle/cn), each with exactly 3 articles
77.       · 18 detail payloads (9 stories × easy/middle), each with non-empty
78.         keywords/questions/background_read/Article_Structure
79.       · 9 article images on disk (one per story id)
80.     """
81.     errs: list[str] = []
82. 
83.     # Listing files — 2 or 3 per cat/lvl acceptable (ideal=3; 2 after
84.     # cross-source dup drops when all backups are exhausted). <2 is fatal.
85.     payloads = WEB / "payloads"
86.     short_cats: set[str] = set()  # cats that shipped <3
87.     for cat in CATS:
88.         for lvl in ("easy", "middle", "cn"):
89.             p = payloads / f"articles_{cat}_{lvl}.json"
90.             if not p.is_file():
91.                 errs.append(f"missing listing: {p.name}")
92.                 continue
93.             try:
94.                 doc = json.loads(p.read_text())
95.                 arts = doc.get("articles") or []
96.                 if len(arts) < 2:
97.                     errs.append(f"{p.name}: {len(arts)} articles (need ≥2)")
98.                 elif len(arts) < 3:
99.                     short_cats.add(f"{cat}/{lvl}")
100.                 for a in arts:
101.                     if not (a.get("title") and a.get("summary") and a.get("id")):
102.                         errs.append(f"{p.name}: article {a.get('id','?')} missing title/summary/id")
103.             except Exception as e:  # noqa: BLE001
104.                 errs.append(f"{p.name}: parse error {e}")
105.     if short_cats:
106.         log.warning("Shipping with <3 articles in: %s", sorted(short_cats))
107. 
108.     # Detail payloads (easy + middle only; cn has no detail page) — iterate
109.     # actual story IDs from the middle listing so 2-article cats validate
110.     # cleanly.
```

</details>


### ✅ `bash`

**Check exit handling**

$ grep -n "raise SystemExit\|sys.exit" /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py

```
170:        raise SystemExit(1)
376:            raise SystemExit(1)
<exited with exit code 0>
```


### 💬 Copilot

Let me verify the exception handling behavior:

### ✅ `bash`

**Check SystemExit handling**

$ python3 -c "
try:
    raise SystemExit(1)
except Exception as e:
    print('Caught by Exception')
except BaseException as e:
    print('Caught by BaseException')
" 2>&1

```
Caught by BaseException
<exited with exit code 0>
```


### 💬 Copilot

Now let me create a comprehensive summary. Let me verify one more detail about the workflow permissions:

### ✅ `bash`

**Check workflow permissions**

$ grep -A20 "permissions:" /Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml

<details>
<summary>19 lines</summary>

```
permissions:
  contents: read

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install libwebp (cwebp / dwebp)
        run: |
          sudo apt-get update -q
          sudo apt-get install -y -q webp

      - name: Set up Python
<exited with exit code 0>
```

</details>


### 💬 Copilot

Perfect. Now I have all the information I need. Let me compile the final findings:

## SUBSTANTIVE FINDINGS — News-v2 Workflow Security & Operations Review

### **1. CRITICAL: Unsafe Secret Handling in GitHub Actions Workflow**
- **Severity**: Critical
- **File**: `.github/workflows/daily-pipeline.yml:41-48`
- **What**: `.env` file written via heredoc with secrets expanded in shell, creating unnecessary surface for secret exposure.
- **Why it matters**: While GitHub Actions masks secrets in logs, heredocs can expose secrets in process listings, shell history, or if masking is bypassed. The `.env` file is unnecessary since Python modules read `os.environ` directly.
- **Suggested fix**: Remove lines 41-48. Secrets are already injected into the job environment via `env:` block (lines 17-20). Modules should continue using `os.environ.get()` without the intermediate `.env` file.

---

### **2. IMPORTANT: SUPABASE_URL Incorrectly Marked as Secret**
- **Severity**: Important  
- **File**: `.github/workflows/daily-pipeline.yml:19` + `website/data.jsx` hardcoded public URL
- **What**: `SUPABASE_URL` is stored in GitHub Secrets but is publicly visible in frontend source code, creating operational confusion about security boundaries.
- **Why it matters**: Developers may assume the URL is sensitive when it's not, leading to over-protection of non-sensitive data and missed protection of actual secrets. Only `DEEPSEEK_API_KEY` and `SUPABASE_SERVICE_KEY` are truly sensitive.
- **Suggested fix**: Remove `SUPABASE_URL` from GitHub Secrets. Define it as a public repository variable or in a non-secret config file. Keep only the two API keys as secrets.

---

### **3. IMPORTANT: Partial Upload Risk with Non-Fatal Exception Handling**
- **Severity**: Important
- **File**: `pipeline/full_round.py:528-532`
- **What**: `pack_and_upload()` is wrapped in bare `except Exception` handler that logs only a warning, allowing the pipeline to report success even if Supabase uploads partially fail.
- **Why it matters**: If `validate_bundle` passes but then `upload_dated_flat_files()` (line 413) fails, the zip is already in Supabase but the supporting flat files are missing. The kidsnews-v2 sync workflow may pull incomplete data. Pipeline reports success when deployment is partially failed.
- **Suggested fix**: Distinguish between fatal failures (validation) and non-fatal (retention). For Supabase upload failures (not retention), raise an exception to fail the step. Only catch Supabase connectivity during cleanup operations.

---

### **4. IMPORTANT: Archive Index Failure Creates Operational Blind Spot**
- **Severity**: Important
- **File**: `pipeline/pack_and_upload.py:431-432` + `420-425`
- **What**: If `update_archive_index()` fails (line 430), today's date is not recorded, but the zip was already uploaded. Next run, `backfill_missing_archive_dirs()` will re-extract and re-upload files unnecessarily.
- **Why it matters**: Silent failures in non-fatal operations accumulate inefficiency and make it hard to diagnose why archive state is inconsistent. Logs show success when archive-index is stale.
- **Suggested fix**: Log archive-index failures with `log.error()` not `log.warning()`. Consider making archive-index update fatal or at minimum add a check on next run to validate archive-index freshness.

---

### **5. IMPORTANT: Dated-Flat Upload Failure Not Surfaced**
- **Severity**: Important
- **File**: `pipeline/pack_and_upload.py:412-415`
- **What**: `upload_dated_flat_files()` failure (line 413) is caught and logged as non-fatal, but this breaks the UI's ability to fetch past-day content directly from Storage.
- **Why it matters**: Frontend uses `\<date\>/payloads/*.json` directly from Supabase (website/data.jsx fetchArchive flow). If upload fails, archive dates will be listed in archive-index but files won't exist, causing 404s in the UI.
- **Suggested fix**: Make `upload_dated_flat_files()` for today's date fatal (non-negotiable for today's deployment). Only mark backfill of old dates as non-fatal.

---

### **6. MINOR: Unnecessary SUPABASE_URL Logged**
- **Severity**: Minor
- **File**: `pipeline/pack_and_upload.py:440-441`
- **What**: SUPABASE_URL is logged as part of the public URL string, creating noise in logs and potentially exposing bucket structure.
- **Why it matters**: Bucket name (`redesign-daily-content`) and URL are logged unnecessarily. While not a secret, this information should only be logged if needed for debugging.
- **Suggested fix**: Remove line 441 or only log the filename (`latest.zip`) without the full URL.

---

### **7. INFO: No Remote Freshness Check on Partial Data**
- **Severity**: Info
- **File**: `pipeline/pack_and_upload.py:355-377` (check_not_overwriting_newer)
- **What**: Freshness check compares `mined_at` timestamps, but only for stories in `latest-manifest.json`. If archive-index update failed, manifest may be stale while zip is fresh.
- **Why it matters**: Edge case where local pipeline is prevented from uploading because manifest from yesterday's successful zip is newer, but today's data is ready. This is acceptable behavior (conservative) but worth noting.
- **Suggested fix**: Acceptable as-is; the check prevents accidental overwrites. If this becomes a blocker, add explicit logging of the decision.

---

## Summary

**Overall Assessment**: Pipeline has solid validation (`validate_bundle`), but error handling in `pack_and_upload()` conflates fatal (validation, freshness check) and non-fatal (cleanup) failures. The three-repo architecture works because kidsnews-v2 pulls immutable `latest.zip`, but silent failures in archive-index and dated-flat uploads can cause the frontend's archive browsing feature to break without visibility.

**Top 3 fixes (priority order)**:
1. **Remove `.env` file creation** in workflow (line 41-48) — unnecessary and risky
2. **Differentiate fatal vs non-fatal failures** in `pack_and_upload.py` — make dated-flat for today fatal, archive-index failure log.error()
3. **Move SUPABASE_URL out of Secrets** — it's public; reduces confusion and operational overhead


---

<sub>⏱️ 3m 10s</sub>

### ✅ `rg`

**def pick_winners_with_dedup|def filter_past_duplicates|def detail_enrich|def deepseek_call|def deepseek_reasoner_call|check_not_overwriting_newer|upload_dated_flat_files|update_archive_index|ALLOW_STALE_UPLOAD|/Users/jiong**

"def pick_winners_with_dedup|def filter_past_duplicates|def detail_enrich|def deepseek_call|def deepseek_reasoner_call|check_not_overwriting_newer|upload_dated_flat_files|update_archive_index|ALLOW_STALE_UPLOAD|/Users/jiong" in pipeline/*.py

<details>
<summary>40 matches</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py:52:WEBSITE_DIR = Path("/Users/jiong/myprojects/news-v2/website")
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_rewrite.py:98:    details_dir = Path("/Users/jiong/myprojects/news-v2/website/article_payloads")
/Users/jiong/myprojects/news-v2/pipeline/news_exa_pipeline.py:162:def deepseek_call(system: str, user: str, max_tokens: int = 800, temperature: float = 0.2) -> dict:
/Users/jiong/myprojects/news-v2/pipeline/news_exa_pipeline.py:439:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / \
/Users/jiong/myprojects/news-v2/pipeline/news_exa_pipeline.py:458:    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-exa-kids.html")
/Users/jiong/myprojects/news-v2/pipeline/full_round.py:90:def filter_past_duplicates(category: str, by_source: dict[str, dict],
/Users/jiong/myprojects/news-v2/pipeline/full_round.py:131:def pick_winners_with_dedup(by_source: dict[str, dict]) -> list[dict]:
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:221:def upload_dated_flat_files(sb, date_str: str, bundle: bytes | None = None) -> int:
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:255:def update_archive_index(sb, dates: list[str]) -> None:
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:292:            upload_dated_flat_files(sb, d, bundle=body)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:355:def check_not_overwriting_newer(sb) -> None:
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:373:               "If you really want to overwrite, set ALLOW_STALE_UPLOAD=1.")
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:374:        if os.environ.get("ALLOW_STALE_UPLOAD") != "1":
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:377:        log.warning("ALLOW_STALE_UPLOAD=1 set — proceeding despite: %s", msg)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:387:    check_not_overwriting_newer(sb)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:413:        upload_dated_flat_files(sb, today)
/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py:430:        update_archive_index(sb, [today] + backfilled)
/Users/jiong/myprojects/news-v2/pipeline/backfill_card_summaries.py:23:ROOT = Path("/Users/jiong/myprojects/news-v2/website/payloads")
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:241:def deepseek_call(system: str, user: str, max_tokens: int, temperature: float = 0.2,
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:570:def detail_enrich_input(rewrite_result: dict) -> str:
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:630:def deepseek_reasoner_call(system: str, user: str, max_tokens: int = 16000,
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:681:def detail_enrich(rewrite_result: dict) -> dict:
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:1209:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / \
/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py:1226:    html_path = Path(f"/Users/jiong/myprojects/news-v2/website/{output_slug}.html")
/Users/jiong/myprojects/news-v2/pipeline/enrich_existing.py:26:    details_dir = Path("/Users/jiong/myprojects/news-v2/website/article_payloads")
/Users/jiong/myprojects/news-v2/pipeline/news_aggregate.py:348:    today_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / today
/Users/jiong/myprojects/news-v2/pipeline/news_aggregate.py:372:    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-today.html")
/Users/jiong/myprojects/news-v2/pipeline/news_exa_list.py:178:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output")
/Users/jiong/myprojects/news-v2/pipeline/news_exa_list.py:187:    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-exa.html")
/Users/jiong/myprojects/news-v2/pipeline/news_guardian_full.py:419:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / today
/Users/jiong/myprojects/news-v2/pipeline/news_guardian_full.py:436:    html_path = Path(f"/Users/jiong/myprojects/news-v2/website/{OUTPUT_SLUG}.html")
/Users/jiong/myprojects/news-v2/pipeline/test_thinking_enrich.py:121:    details_dir = Path("/Users/jiong/myprojects/news-v2/website/article_payloads")
/Users/jiong/myprojects/news-v2/pipeline/fun_aggregate.py:286:    today_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / today_date
/Users/jiong/myprojects/news-v2/pipeline/fun_aggregate.py:298:    html_path = Path("/Users/jiong/myprojects/news-v2/website/fun-today.html")
/Users/jiong/myprojects/news-v2/pipeline/news_raw_list.py:168:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output")
/Users/jiong/myprojects/news-v2/pipeline/news_raw_list.py:177:    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-raw.html")
/Users/jiong/myprojects/news-v2/pipeline/science_aggregate.py:299:    today_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / today_date
/Users/jiong/myprojects/news-v2/pipeline/science_aggregate.py:311:    html_path = Path("/Users/jiong/myprojects/news-v2/website/science-today.html")
/Users/jiong/myprojects/news-v2/pipeline/news_aj_rss.py:216:    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / \
/Users/jiong/myprojects/news-v2/pipeline/news_aj_rss.py:224:    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-aj-rss.html")
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `rg`

**todayArticles|localStorage\.setItem|loadArchive|archiveDate|storyId|background:url|dangerouslySetInnerHTML|postMessage|unpkg.com|babel|fetch\(**

"todayArticles|localStorage\.setItem|loadArchive|archiveDate|storyId|background:url|dangerouslySetInnerHTML|postMessage|unpkg.com|babel|fetch\(" in website/*.{jsx,html}

<details>
<summary>56 matches</summary>

```
/Users/jiong/myprojects/news-v2/website/data.jsx:4:// initial today's load), and window.loadArchive(date) to swap in a past day.
/Users/jiong/myprojects/news-v2/website/data.jsx:41:// archived day. For today's content (archiveDate = null), leave as-is.
/Users/jiong/myprojects/news-v2/website/data.jsx:42:function resolveImageUrl(rawUrl, archiveDate) {
/Users/jiong/myprojects/news-v2/website/data.jsx:43:  if (!archiveDate || !rawUrl) return rawUrl || "";
/Users/jiong/myprojects/news-v2/website/data.jsx:46:  return `${ARCHIVE_BASE}/${archiveDate}/${rel}`;
/Users/jiong/myprojects/news-v2/website/data.jsx:49:function listingToArticle(entry, cat, lvl, archiveDate) {
/Users/jiong/myprojects/news-v2/website/data.jsx:55:    storyId: entry.id,
/Users/jiong/myprojects/news-v2/website/data.jsx:56:    archiveDate: archiveDate || null,   // null = today's edition
/Users/jiong/myprojects/news-v2/website/data.jsx:60:    image: resolveImageUrl(entry.image_url, archiveDate),
/Users/jiong/myprojects/news-v2/website/data.jsx:78:function listingBaseFor(archiveDate) {
/Users/jiong/myprojects/news-v2/website/data.jsx:79:  return archiveDate ? `${ARCHIVE_BASE}/${archiveDate}/payloads`
/Users/jiong/myprojects/news-v2/website/data.jsx:83:async function loadPayloads(archiveDate = null) {
/Users/jiong/myprojects/news-v2/website/data.jsx:86:  const base = listingBaseFor(archiveDate);
/Users/jiong/myprojects/news-v2/website/data.jsx:91:        const r = await fetch(`${base}/articles_${cat}_${lvl}.json?t=${Date.now()}`);
/Users/jiong/myprojects/news-v2/website/data.jsx:95:        for (const a of top3) all.push(listingToArticle(a, cat, lvl, archiveDate));
/Users/jiong/myprojects/news-v2/website/data.jsx:106:async function loadArchiveIndex() {
/Users/jiong/myprojects/news-v2/website/data.jsx:108:    const r = await fetch(`${ARCHIVE_BASE}/archive-index.json?t=${Date.now()}`);
/Users/jiong/myprojects/news-v2/website/data.jsx:119:async function loadArchive(date) {
/Users/jiong/myprojects/news-v2/website/data.jsx:122:  window.__archiveDate = date || null;
/Users/jiong/myprojects/news-v2/website/data.jsx:130:window.__archiveDate = null;
/Users/jiong/myprojects/news-v2/website/data.jsx:132:window.loadArchive = loadArchive;
/Users/jiong/myprojects/news-v2/website/data.jsx:133:window.loadArchiveIndex = loadArchiveIndex;
/Users/jiong/myprojects/news-v2/website/home.jsx:17:  // When archiveDay changes, ARTICLES is swapped wholesale by loadArchive()
/Users/jiong/myprojects/news-v2/website/home.jsx:34:      out.push(...todayArticles.filter(a => a.category === c.label).slice(0, 3));
/Users/jiong/myprojects/news-v2/website/home.jsx:37:  }, [todayArticles]);
/Users/jiong/myprojects/news-v2/website/home.jsx:54:  useEffectH(() => { localStorage.setItem('ohye_daily_picks_v3', JSON.stringify(activePicks)); }, [activePicks]);
/Users/jiong/myprojects/news-v2/website/home.jsx:357:    window.loadArchiveIndex().then(r => { if (!cancelled) setIndex(r); });
/Users/jiong/myprojects/news-v2/website/article.jsx:28:    // Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
/Users/jiong/myprojects/news-v2/website/article.jsx:30:    const detailBase = baseArticle.archiveDate
/Users/jiong/myprojects/news-v2/website/article.jsx:31:      ? `${window.ARCHIVE_BASE}/${baseArticle.archiveDate}/article_payloads`
/Users/jiong/myprojects/news-v2/website/article.jsx:33:    const url = `${detailBase}/payload_${baseArticle.storyId}/${payloadLevel}.json`;
/Users/jiong/myprojects/news-v2/website/article.jsx:34:    fetch(url)
/Users/jiong/myprojects/news-v2/website/index.html:20:<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L" crossorigin="anonymous"></script>
/Users/jiong/myprojects/news-v2/website/index.html:21:<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm" crossorigin="anonymous"></script>
/Users/jiong/myprojects/news-v2/website/index.html:22:<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y" crossorigin="anonymous"></script>
/Users/jiong/myprojects/news-v2/website/index.html:27:<script type="text/babel" src="data.jsx?v=20260424e"></script>
/Users/jiong/myprojects/news-v2/website/index.html:28:<script type="text/babel" src="components.jsx"></script>
/Users/jiong/myprojects/news-v2/website/index.html:29:<script type="text/babel" src="home.jsx?v=20260424e"></script>
/Users/jiong/myprojects/news-v2/website/index.html:30:<script type="text/babel" src="article.jsx?v=20260424e"></script>
/Users/jiong/myprojects/news-v2/website/index.html:31:<script type="text/babel" src="user-panel.jsx"></script>
/Users/jiong/myprojects/news-v2/website/index.html:33:<script type="text/babel">
/Users/jiong/myprojects/news-v2/website/index.html:98:  useEffect(() => { localStorage.setItem('ohye_route', JSON.stringify(route)); }, [route]);
/Users/jiong/myprojects/news-v2/website/index.html:99:  useEffect(() => { localStorage.setItem('ohye_level', level); }, [level]);
/Users/jiong/myprojects/news-v2/website/index.html:100:  useEffect(() => { localStorage.setItem('ohye_cat', cat); }, [cat]);
/Users/jiong/myprojects/news-v2/website/index.html:102:    if (archiveDay) localStorage.setItem('ohye_archive_day', String(archiveDay));
/Users/jiong/myprojects/news-v2/website/index.html:106:    if (typeof window.loadArchive === 'function') {
/Users/jiong/myprojects/news-v2/website/index.html:107:      window.loadArchive(archiveDay).then(() => {
/Users/jiong/myprojects/news-v2/website/index.html:113:  useEffect(() => { localStorage.setItem('ohye_progress', JSON.stringify(progress)); }, [progress]);
/Users/jiong/myprojects/news-v2/website/index.html:114:  useEffect(() => { localStorage.setItem('ohye_tweaks', JSON.stringify(tweaks)); }, [tweaks]);
/Users/jiong/myprojects/news-v2/website/index.html:125:    try { window.parent.postMessage({ type:'__edit_mode_available' }, '*'); } catch {}
/Users/jiong/myprojects/news-v2/website/index.html:132:    try { window.parent.postMessage({ type:'__edit_mode_set_keys', edits }, '*'); } catch {}
/Users/jiong/myprojects/news-v2/website/index.html:158:    // (Tree-level / middle) via storyId. If no Tree twin exists, fall back to
/Users/jiong/myprojects/news-v2/website/index.html:162:      const tree = ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en' && a.level === 'Tree');
/Users/jiong/myprojects/news-v2/website/index.html:163:      const any = tree || ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en');
/Users/jiong/myprojects/news-v2/website/index.html:264:// Wait for all babel scripts to load AND for payloads to be fetched.
/Users/jiong/myprojects/news-v2/website/test-preview.html:376:    return fetch(url).then(function (r) {
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 1-220)

<details>
<summary>220 lines</summary>

```
1. // Home page — News Oh,Ye!
2. const { useState: useStateH, useEffect: useEffectH, useMemo: useMemoH } = React;
3. 
4. function HomePage({ onOpen, onOpenArchive, level, setLevel, cat, setCat, progress, theme, heroVariant, tweaks, onOpenUserPanel, archiveDay }) {
5.   theme = theme || { bg:'#fff9ef', accent:'#ffc83d', hero1:'#ffe2a8', hero2:'#ffc0a8', border:'#ffb98a', heroTextAccent:'#c14e2a', card:'#fff', chip:'#f0e8d8' };
6. 
7.   const isZh = tweaks && tweaks.language === 'zh';
8.   // In zh mode we show the Chinese summary cards (language === 'zh'); otherwise
9.   // we show English cards at the selected level (Sprout => easy, Tree => middle).
10.   const matchesLanguageLevel = (a) => {
11.     if (isZh) return a.language === 'zh';
12.     return a.language === 'en' && a.level === level;
13.   };
14.   // archiveDay is now a date string "YYYY-MM-DD" (or null for today).
15.   const isArchive = typeof archiveDay === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(archiveDay);
16. 
17.   // When archiveDay changes, ARTICLES is swapped wholesale by loadArchive()
18.   // in index.html. Everything below filters the current ARTICLES in-memory.
19.   const filteredRaw = useMemoH(() => {
20.     const matches = ARTICLES.filter(matchesLanguageLevel);
21.     return (cat === 'All' || !cat) ? matches : matches.filter(a => a.category === cat);
22.   }, [isZh, level, cat, archiveDay]);
23.   // Cap today to 3 per category (editorial layout). Archive also 3 since
24.   // each day's bundle only has 3 per category anyway.
25.   const filtered = useMemoH(() => filteredRaw.slice(0, 3), [filteredRaw]);
26. 
27.   const [calendarOpen, setCalendarOpen] = useStateH(false);
28.   const [recentOpen, setRecentOpen] = useStateH(false);
29. 
30.   // Per-category displayable pool — only the first 3 stories of each category (what's shown on pages)
31.   const displayPool = useMemoH(() => {
32.     const out = [];
33.     for (const c of CATEGORIES) {
34.       out.push(...todayArticles.filter(a => a.category === c.label).slice(0, 3));
35.     }
36.     return out;
37.   }, [todayArticles]);
38.   const poolIds = useMemoH(() => new Set(displayPool.map(a => a.id)), [displayPool]);
39. 
40.   // Pick 1 from each category by default, user can swap (only from the 3-per-category pool)
41.   const [dailyPicks, setDailyPicks] = useStateH(() => {
42.     try { const s = JSON.parse(localStorage.getItem('ohye_daily_picks_v3') || 'null'); if (s && s.length === 3) return s; } catch {}
43.     return null;
44.   });
45.   const defaultPicks = useMemoH(() => {
46.     const out = [];
47.     for (const c of CATEGORIES) {
48.       const first = displayPool.find(a => a.category === c.label);
49.       if (first) out.push(first.id);
50.     }
51.     return out.slice(0, 3);
52.   }, [displayPool]);
53.   const activePicks = (dailyPicks && dailyPicks.every(id => poolIds.has(id))) ? dailyPicks : defaultPicks;
54.   useEffectH(() => { localStorage.setItem('ohye_daily_picks_v3', JSON.stringify(activePicks)); }, [activePicks]);
55.   const swapPick = (idx, newId) => {
56.     const next = [...activePicks]; next[idx] = newId; setDailyPicks(next);
57.   };
58.   const daily3 = useMemoH(() => activePicks.map(id => displayPool.find(a => a.id === id)).filter(Boolean), [activePicks, displayPool]);
59.   const [swapOpen, setSwapOpen] = useStateH(null); // index being swapped
60. 
61.   const byCat = useMemoH(() => {
62.     const m = {};
63.     CATEGORIES.forEach(c => { m[c.label] = ARTICLES.filter(a => a.category === c.label); });
64.     return m;
65.   }, []);
66. 
67.   const minutesToday = progress.minutesToday;
68.   const streak = MOCK_USER.streak;
69.   const goal = MOCK_USER.dailyGoal;
70.   const goalPct = Math.min(1, minutesToday / goal);
71.   const readCount = progress.readToday.length;
72. 
73.   return (
74.     <div style={{background: theme.bg, minHeight:'100vh'}}>
75.       {/* ——————————— HEADER ——————————— */}
76.       <Header level={level} setLevel={setLevel} theme={theme} tweaks={tweaks} onOpenUserPanel={onOpenUserPanel} progress={progress} recentOpen={recentOpen} setRecentOpen={setRecentOpen} onOpenArticle={onOpen} />
77. 
78.       {/* ——————————— ARCHIVE BANNER (when viewing an old day) ——————————— */}
79.       {isArchive && (
80.         <section style={{maxWidth:1180, margin:'16px auto 0', padding:'0 28px'}}>
81.           <div style={{
82.             background:'#1b1230', color:'#fff', borderRadius:18,
83.             padding:'14px 20px', display:'flex', alignItems:'center', gap:14, flexWrap:'wrap',
84.           }}>
85.             <div style={{fontSize:26}}>🗂️</div>
86.             <div style={{flex:1, minWidth:200}}>
87.               <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20, lineHeight:1.1}}>
88.                 {archiveDayLabel(archiveDay)}
89.               </div>
90.               <div style={{fontSize:12, color:'#ffc83d', fontWeight:700, letterSpacing:'.06em', textTransform:'uppercase', marginTop:2}}>
91.                 Reading an old edition
92.               </div>
93.             </div>
94.             <button onClick={()=>onOpenArchive(null)} style={{
95.               background:'#ffc83d', color:'#1b1230', border:'none', borderRadius:999,
96.               padding:'10px 18px', fontWeight:900, fontSize:13, cursor:'pointer', fontFamily:'Nunito, sans-serif',
97.             }}>← Return to today</button>
98.           </div>
99.         </section>
100.       )}
101. 
102.       {/* ——————————— TODAY'S 15 HERO (hidden in archive) ——————————— */}
103.       {!isArchive && (
104.       <section style={{maxWidth:1180, margin:'0 auto', padding:'24px 28px 0'}}>
105.         <div style={{
106.           background:`linear-gradient(135deg, ${theme.hero1} 0%, ${theme.hero2} 100%)`,
107.           borderRadius:28,
108.           padding:'28px 32px',
109.           display:'grid',
110.           gridTemplateColumns: heroVariant === 'streak' ? '1fr 1fr' : '1.2fr 1fr',
111.           gap:28,
112.           alignItems:'center',
113.           position:'relative',
114.           overflow:'hidden',
115.           border:`2px solid ${theme.border}`,
116.         }}>
117.           {/* doodles */}
118.           <svg style={{position:'absolute', right:-20, bottom:-30, opacity:.18}} width="240" height="240" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" stroke="#1b1230" strokeWidth="2" fill="none"/><circle cx="50" cy="50" r="28" stroke="#1b1230" strokeWidth="2" fill="none" strokeDasharray="4 6"/></svg>
119. 
120.           <div style={{position:'relative'}}>
121.             <div style={{fontFamily:'Nunito, sans-serif', fontWeight:800, color: theme.heroTextAccent, fontSize:13, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:6}}>
122.               Hi Mia! 👋 &nbsp;·&nbsp; Thursday, Oct 24
123.             </div>
124.             {heroVariant === 'streak' ? (
125.               <>
126.                 <div style={{display:'inline-flex', alignItems:'center', gap:8, background:'#1b1230', color:'#ffc83d', padding:'6px 14px', borderRadius:999, fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:12, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:12}}>
127.                   🔥 Streak mode
128.                 </div>
129.                 <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:64, lineHeight:0.95, color:'#1b1230', margin:'0 0 10px', letterSpacing:'-0.03em'}}>
130.                   {MOCK_USER.streak} days<br/><span style={{color: theme.heroTextAccent, fontStyle:'italic'}}>on fire.</span>
131.                 </h1>
132.                 <p style={{fontSize:17, color:'#3a2a4a', margin:'0 0 14px', lineHeight:1.5, maxWidth:480}}>
133.                   Read today to hit <b>day {MOCK_USER.streak+1}</b>. You've practiced <b>{minutesToday} of {goal} min</b>.
134.                 </p>
135.                 {/* mini calendar of last 7 days */}
136.                 <div style={{display:'flex', gap:6, marginBottom:16}}>
137.                   {Array.from({length:7}).map((_,i)=>{
138.                     const done = i < 6;
139.                     return (
140.                       <div key={i} style={{width:36, height:44, borderRadius:10, background: done ? '#1b1230' : 'rgba(255,255,255,0.65)', color: done ? '#ffc83d' : '#9a8d7a', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:11, border: i===6 ? `2px dashed ${theme.heroTextAccent}` : 'none'}}>
141.                         <div style={{fontSize:9, opacity:0.7}}>{['M','T','W','T','F','S','S'][i]}</div>
142.                         <div style={{fontSize:14}}>{done ? '✓' : '·'}</div>
143.                       </div>
144.                     );
145.                   })}
146.                 </div>
147.               </>
148.             ) : (
149.               <>
150.                 <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:52, lineHeight:1.02, color:'#1b1230', margin:'0 0 12px', letterSpacing:'-0.02em'}}>
151.                   Today's <span style={{background: theme.accent, padding:'0 10px', borderRadius:12, display:'inline-block', transform:'rotate(-2deg)'}}>15 minutes</span>
152.                 </h1>
153.                 <p style={{fontSize:17, color:'#3a2a4a', margin:'0 0 18px', lineHeight:1.5, maxWidth:480}}>
154.                   Read 3 smart stories, learn new words, and win your streak. You've read <b>{readCount} of 3</b> today.
155.                 </p>
156.               </>
157.             )}
158.             <div style={{display:'flex', gap:10, alignItems:'center', flexWrap:'wrap'}}>
159.               <BigButton bg="#1b1230" color="#fff" onClick={() => onOpen(daily3.find(a => !progress.readToday.includes(a.id))?.id || daily3[0].id)}>
160.                 ▶ &nbsp;Start today's read
161.               </BigButton>
162.               <div style={{display:'flex', alignItems:'center', gap:8, padding:'10px 14px', background:'rgba(255,255,255,0.65)', borderRadius:14, fontWeight:700, fontSize:14}}>
163.                 <span style={{fontSize:18}}>⏱️</span>
164.                 <span>{minutesToday}/{goal} min today</span>
165.               </div>
166.             </div>
167.           </div>
168. 
169.           {/* Daily 3 stack — swappable picks */}
170.           <div style={{display:'flex', flexDirection:'column', gap:10, position:'relative'}}>
171.             <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
172.               <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:18, color:'#1b1230'}}>⚡ Today's 3 · 5 min</div>
173.               <div style={{fontSize:11, color:'#6b5c80', fontWeight:700}}>Tap ⇆ to swap</div>
174.             </div>
175.             {daily3.map((a, i) => {
176.               const catColor = CATEGORIES.find(c => c.label === a.category)?.color || '#1b1230';
177.               const alternates = displayPool.filter(x => x.category === a.category && !activePicks.includes(x.id));
178.               const canSwap = alternates.length > 0;
179.               const isSwapping = swapOpen === i;
180.               return (
181.                 <div key={a.id} style={{position:'relative'}}>
182.                   {isSwapping ? (
183.                     <div style={{
184.                       background:'#1b1230', borderRadius:16, padding:10,
185.                       boxShadow:'0 4px 0 rgba(27,18,48,0.15)',
186.                     }}>
187.                       <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'2px 6px 8px'}}>
188.                         <div style={{fontSize:10, fontWeight:800, color:'#ffc83d', textTransform:'uppercase', letterSpacing:'.08em'}}>Pick a different {a.category} story</div>
189.                         <button onClick={()=>setSwapOpen(null)} style={{
190.                           background:'transparent', border:'none', color:'#ffc83d', fontWeight:900, cursor:'pointer', fontSize:16, padding:'0 4px',
191.                         }} title="Close">✕</button>
192.                       </div>
193.                       {alternates.map(alt => (
194.                         <button key={alt.id} onClick={()=>{swapPick(i, alt.id); setSwapOpen(null);}} style={{
195.                           display:'flex', alignItems:'center', gap:10, width:'100%', textAlign:'left',
196.                           background:'rgba(255,255,255,0.06)', color:'#fff',
197.                           border:'none', padding:8, borderRadius:10, cursor:'pointer',
198.                           marginBottom:6,
199.                         }} onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.14)'} onMouseLeave={e=>e.currentTarget.style.background='rgba(255,255,255,0.06)'}>
200.                           <div style={{width:44, height:44, borderRadius:10, flexShrink:0, background:`url(${alt.image}) center/cover, ${catColor}`}}/>
201.                           <div style={{flex:1, minWidth:0}}>
202.                             <div style={{fontWeight:800, fontSize:13, lineHeight:1.25}}>{alt.title}</div>
203.                             <div style={{fontSize:10, opacity:0.7, fontWeight:700, marginTop:3}}>{alt.readMins} min · {alt.tag}</div>
204.                           </div>
205.                         </button>
206.                       ))}
207.                       {alternates.length === 0 && (
208.                         <div style={{color:'#fff', opacity:0.6, fontSize:12, padding:10, textAlign:'center'}}>No other {a.category} stories today.</div>
209.                       )}
210.                     </div>
211.                   ) : (
212.                   <div style={{
213.                     background:'#fff', border:'2px solid #fff', borderRadius:16,
214.                     padding:'10px 12px', display:'flex', gap:12, alignItems:'center',
215.                     boxShadow:'0 2px 0 rgba(27,18,48,0.08)',
216.                   }}>
217.                     <div style={{
218.                       width:36, height:36, borderRadius:12, flexShrink:0,
219.                       background: catColor, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center',
220.                       fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18,
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/data.jsx.**

/Users/jiong/myprojects/news-v2/website/data.jsx (lines 1-260)

<details>
<summary>138 lines</summary>

```
1. // data.jsx — v2 payload loader
2. // Consumes v1 listing payloads and exposes window.ARTICLES, window.CATEGORIES,
3. // window.LEVELS, window.MOCK_USER, window.__payloadsLoaded (promise for
4. // initial today's load), and window.loadArchive(date) to swap in a past day.
5. //
6. // Today's content is served from the Vercel deploy (same origin, flat paths
7. // under /payloads/ and /article_images/). Past days are served directly from
8. // Supabase Storage under /<date>/payloads/... — see ARCHIVE_BASE.
9. //
10. // Contract mapping (v2 UI <-- v1 source):
11. //   Sprout level        <- easy
12. //   Tree level          <- middle
13. //   Chinese summary card<- cn  (no detail page — summary only)
14. 
15. const SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co';
16. const ARCHIVE_BASE = `${SUPABASE_URL}/storage/v1/object/public/redesign-daily-content`;
17. 
18. const CATEGORIES = [
19.   { id: "news",    label: "News",    emoji: "📰", color: "#ff6b5b", bg: "#ffece8" },
20.   { id: "science", label: "Science", emoji: "🔬", color: "#17b3a6", bg: "#e0f6f3" },
21.   { id: "fun",     label: "Fun",     emoji: "🎈", color: "#9061f9", bg: "#eee5ff" },
22. ];
23. 
24. const LEVELS = [
25.   { id: "Sprout", emoji: "🌱", label: "Sprout", sub: "Easy" },
26.   { id: "Tree",   emoji: "🌳", label: "Tree",   sub: "Middle" },
27. ];
28. 
29. const MOCK_USER = {
30.   name: "Mia",
31.   streak: 7,
32.   minutesToday: 6,
33.   dailyGoal: 15,
34.   totalXp: 1240,
35.   weekXp: 310,
36.   badges: ["🦉", "🔭", "🌱"],
37.   readToday: ["a2"],
38. };
39. 
40. // Rewrite /article_images/xxx.webp → full Supabase URL when we're loading an
41. // archived day. For today's content (archiveDate = null), leave as-is.
42. function resolveImageUrl(rawUrl, archiveDate) {
43.   if (!archiveDate || !rawUrl) return rawUrl || "";
44.   if (rawUrl.startsWith('http')) return rawUrl;
45.   const rel = rawUrl.replace(/^\//, '');   // strip leading slash
46.   return `${ARCHIVE_BASE}/${archiveDate}/${rel}`;
47. }
48. 
49. function listingToArticle(entry, cat, lvl, archiveDate) {
50.   const categoryLabel = { news: "News", science: "Science", fun: "Fun" }[cat];
51.   const isZh = lvl === "cn";
52.   const level = isZh ? null : (lvl === "easy" ? "Sprout" : "Tree");
53.   return {
54.     id: entry.id + "-" + lvl,
55.     storyId: entry.id,
56.     archiveDate: archiveDate || null,   // null = today's edition
57.     title: entry.title,
58.     summary: entry.summary,
59.     body: "",
60.     image: resolveImageUrl(entry.image_url, archiveDate),
61.     category: categoryLabel,
62.     source: entry.source || "",
63.     time: entry.time_ago || "",
64.     minedAt: entry.mined_at || "",
65.     sourcePublishedAt: entry.source_published_at || "",
66.     readMins: isZh ? 2 : (lvl === "easy" ? 3 : 5),
67.     level: level,
68.     language: isZh ? "zh" : "en",
69.     xp: isZh ? 15 : (lvl === "easy" ? 30 : 45),
70.     tag: categoryLabel,
71.     keywords: [],
72.     quiz: [],
73.     discussion: [],
74.     noDetail: isZh,
75.   };
76. }
77. 
78. function listingBaseFor(archiveDate) {
79.   return archiveDate ? `${ARCHIVE_BASE}/${archiveDate}/payloads`
80.                      : 'payloads';
81. }
82. 
83. async function loadPayloads(archiveDate = null) {
84.   const cats = ["news", "science", "fun"];
85.   const levels = ["easy", "middle", "cn"];
86.   const base = listingBaseFor(archiveDate);
87.   const all = [];
88.   for (const cat of cats) {
89.     for (const lvl of levels) {
90.       try {
91.         const r = await fetch(`${base}/articles_${cat}_${lvl}.json?t=${Date.now()}`);
92.         if (!r.ok) { console.warn(`[data] missing: ${base}/articles_${cat}_${lvl}.json`); continue; }
93.         const { articles } = await r.json();
94.         const top3 = (articles || []).slice(0, 3);
95.         for (const a of top3) all.push(listingToArticle(a, cat, lvl, archiveDate));
96.       } catch (e) {
97.         console.warn(`[data] fetch failed: ${base}/articles_${cat}_${lvl}.json`, e);
98.       }
99.     }
100.   }
101.   return all;
102. }
103. 
104. // Fetch the list of available archive days from Supabase.
105. // Returns { dates: [...], updated_at } or { dates: [] } on failure.
106. async function loadArchiveIndex() {
107.   try {
108.     const r = await fetch(`${ARCHIVE_BASE}/archive-index.json?t=${Date.now()}`);
109.     if (!r.ok) return { dates: [] };
110.     return await r.json();
111.   } catch (e) {
112.     console.warn('[data] archive-index fetch failed', e);
113.     return { dates: [] };
114.   }
115. }
116. 
117. // Callable from the app: swap window.ARTICLES to point at a past day's
118. // bundle, or back to today when passed null.
119. async function loadArchive(date) {
120.   const list = await loadPayloads(date || null);
121.   window.ARTICLES = list;
122.   window.__archiveDate = date || null;
123.   return list;
124. }
125. 
126. window.CATEGORIES = CATEGORIES;
127. window.LEVELS = LEVELS;
128. window.MOCK_USER = MOCK_USER;
129. window.ARTICLES = [];
130. window.__archiveDate = null;
131. window.ARCHIVE_BASE = ARCHIVE_BASE;
132. window.loadArchive = loadArchive;
133. window.loadArchiveIndex = loadArchiveIndex;
134. window.__payloadsLoaded = loadPayloads().then(list => {
135.   window.ARTICLES = list;
136.   return list;
137. });
138.
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/article.jsx.**

/Users/jiong/myprojects/news-v2/website/article.jsx (lines 1-260)

<details>
<summary>260 lines</summary>

```
1. // Article detail page — News Oh,Ye!
2. const { useState: useStateA, useMemo: useMemoA, useEffect: useEffectA } = React;
3. 
4. // Format an ISO-8601 timestamp as "Apr 24, 2026". Returns "" on bad input
5. // so callers can safely conditionally render.
6. function formatDate(iso) {
7.   if (!iso) return '';
8.   const d = new Date(iso);
9.   if (isNaN(d.getTime())) return '';
10.   return d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
11. }
12. 
13. function ArticlePage({ articleId, onBack, onComplete, progress, setProgress }) {
14.   const baseArticle = ARTICLES.find(a => a.id === articleId) || ARTICLES[0];
15.   const [tab, setTab] = useStateA('read');
16.   const [tabsVisited, setTabsVisited] = useStateA({ read: true });
17.   const [detail, setDetail] = useStateA(null);
18.   const [detailError, setDetailError] = useStateA(null);
19. 
20.   // Lazy-fetch v1 detail payload for this article. Chinese cards (noDetail) are
21.   // routed away before reaching this page, so we only fetch English variants.
22.   useEffectA(() => {
23.     if (!baseArticle || baseArticle.noDetail) { setDetail(null); return; }
24.     let cancelled = false;
25.     setDetail(null);
26.     setDetailError(null);
27.     const payloadLevel = baseArticle.level === 'Sprout' ? 'easy' : 'middle';
28.     // Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
29.     // prefix; today's content stays local.
30.     const detailBase = baseArticle.archiveDate
31.       ? `${window.ARCHIVE_BASE}/${baseArticle.archiveDate}/article_payloads`
32.       : 'article_payloads';
33.     const url = `${detailBase}/payload_${baseArticle.storyId}/${payloadLevel}.json`;
34.     fetch(url)
35.       .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
36.       .then(d => {
37.         if (cancelled) return;
38.         // Map v1 field shapes to the prototype's expected shape.
39.         // v1 detail pattern: full body lives in `summary`; `background_read` is
40.         // supplementary context (for the Analyze tab), not the body.
41.         const bgRead = Array.isArray(d.background_read)
42.           ? d.background_read.join('\n\n')
43.           : (typeof d.background_read === 'string' ? d.background_read : '');
44.         const mapped = {
45.           body: d.summary || '',                        // FULL regenerated article body
46.           summary: d.summary || baseArticle.summary,
47.           backgroundRead: bgRead,                       // shown on Analyze tab
48.           whyItMatters: d.why_it_matters || '',
49.           keywords: (d.keywords || []).map(k => ({ term: k.term, def: k.explanation })),
50.           quiz: (d.questions || []).map(q => {
51.             const idx = q.options.findIndex(opt => opt === q.correct_answer);
52.             return { q: q.question, options: q.options, a: Math.max(0, idx) };
53.           }),
54.           discussion: (d.perspectives || []).map(p => `${p.perspective}: ${p.description}`),
55.           articleStructure: Array.isArray(d.Article_Structure) ? d.Article_Structure : [],
56.         };
57.         setDetail(mapped);
58.       })
59.       .catch(e => { if (!cancelled) { console.warn('[article] detail fetch failed', url, e); setDetailError(e); } });
60.     return () => { cancelled = true; };
61.   }, [articleId]);
62. 
63.   // Merged article object: prefer detail fields when loaded, fall back to the
64.   // listing-level stub so the title block + header render even before detail
65.   // arrives.
66.   const article = useMemoA(() => {
67.     const d = detail || {};
68.     return {
69.       ...baseArticle,
70.       summary: d.summary || baseArticle.summary,
71.       body: d.body || '',
72.       backgroundRead: d.backgroundRead || '',
73.       whyItMatters: d.whyItMatters || '',
74.       keywords: d.keywords || [],
75.       quiz: d.quiz || [],
76.       discussion: d.discussion || [],
77.       articleStructure: d.articleStructure || [],
78.     };
79.   }, [articleId, detail]);
80. 
81.   // Each step completion bumps progress by 25%: read→25, analyze→50, quiz→75, discuss→100
82.   const bumpProgress = (pct) => {
83.     setProgress(p => {
84.       const ap = p.articleProgress || {};
85.       const cur = ap[article.id] || 0;
86.       if (cur >= pct) return p;
87.       const next = { ...p, articleProgress: { ...ap, [article.id]: pct } };
88.       // When reaching 100, mark as fully read + add minutes
89.       if (pct === 100 && !p.readToday.includes(article.id)) {
90.         next.readToday = [...p.readToday, article.id];
91.         next.minutesToday = (p.minutesToday || 0) + article.readMins;
92.       }
93.       return next;
94.     });
95.   };
96.   const [expandedKw, setExpandedKw] = useStateA(null);
97.   const [quizIdx, setQuizIdx] = useStateA(0);
98.   const [quizAns, setQuizAns] = useStateA([]);
99.   const [quizShow, setQuizShow] = useStateA(false);
100.   const [confetti, setConfetti] = useStateA(false);
101. 
102.   const stages = [
103.     { id:'read', label:'Read & Words', emoji:'📖' },
104.     { id:'analyze', label:'Background', emoji:'🔍' },
105.     { id:'quiz', label:'Quiz', emoji:'🎯' },
106.     { id:'discuss', label:'Think', emoji:'💭' },
107.   ];
108. 
109.   const catColor = getCatColor(article.category);
110. 
111.   // Build paragraphs for the Read tab from detail.body (preferred) or a
112.   // sentence-grouped fallback over the summary while detail is loading.
113.   const paragraphs = useMemoA(() => {
114.     const text = article.body || article.summary || '';
115.     if (article.body) {
116.       // Detail body has explicit paragraph breaks ("\n\n") we can honor.
117.       const paras = text.split(/\n\n+/).map(s => s.trim()).filter(Boolean);
118.       if (paras.length > 0) return paras;
119.     }
120.     // Fallback: group sentences into 3-sentence paragraphs (prototype behavior).
121.     const sentences = text.split(/(?<=\.)\s+/);
122.     const groups = [];
123.     for (let i=0; i<sentences.length; i+=3) groups.push(sentences.slice(i, i+3).join(' '));
124.     return groups;
125.   }, [article.id, article.body, article.summary]);
126. 
127.   const switchTab = (id) => {
128.     setTab(id);
129.     setTabsVisited(v => ({...v, [id]: true}));
130.   };
131. 
132.   // Block tabs until detail is loaded. Header/title block still render so the
133.   // user gets feedback while the payload arrives.
134.   const detailReady = !!detail;
135. 
136.   return (
137.     <div style={{background:'#fff9ef', minHeight:'100vh'}}>
138.       {/* ——— Top bar ——— */}
139.       <div style={{background:'#fff9ef', borderBottom:'2px solid #f0e8d8', position:'sticky', top:0, zIndex:30}}>
140.         <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:14}}>
141.           <button onClick={onBack} style={{
142.             background:'#fff', border:'2px solid #f0e8d8', borderRadius:14, padding:'8px 14px',
143.             fontWeight:800, fontSize:14, cursor:'pointer', color:'#1b1230',
144.             display:'inline-flex', alignItems:'center', gap:6,
145.           }}>← Back</button>
146.           <div style={{display:'flex', alignItems:'center', gap:10}}>
147.             <OhYeLogo size={32}/>
148.             <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>News Oh,Ye!</div>
149.           </div>
150.           <div style={{flex:1}}/>
151.           <div style={{display:'flex', alignItems:'center', gap:6}}>
152.             {stages.map((s, i) => {
153.               const curPct = (progress.articleProgress || {})[article.id] || 0;
154.               const stepPct = (i + 1) * 25;
155.               const stepDone = curPct >= stepPct;
156.               return (
157.                 <React.Fragment key={s.id}>
158.                   <button onClick={()=>switchTab(s.id)} style={{
159.                     background: tab===s.id ? catColor : (stepDone ? '#d4f3ef' : '#fff'),
160.                     color: tab===s.id ? '#fff' : (stepDone ? '#0e8d82' : '#6b5c80'),
161.                     border: `2px solid ${tab===s.id ? catColor : (stepDone ? '#8fd6cd' : '#f0e8d8')}`,
162.                     borderRadius:999, padding:'6px 12px', fontWeight:800, fontSize:13, cursor:'pointer',
163.                     display:'inline-flex', alignItems:'center', gap:5,
164.                   }}>
165.                     <span>{stepDone && tab !== s.id ? '✓' : s.emoji}</span>{s.label}
166.                   </button>
167.                   {i < stages.length-1 && <div style={{width:8, height:2, background: stepDone ? '#8fd6cd' : '#f0e8d8', borderRadius:2}}/>}
168.                 </React.Fragment>
169.               );
170.             })}
171.           </div>
172.         </div>
173.       </div>
174. 
175.       <div style={{maxWidth:1180, margin:'0 auto', padding:'24px 28px 60px'}}>
176. 
177.         {/* ——— Title block ——— */}
178.         <div style={{display:'grid', gridTemplateColumns:'1.1fr 1fr', gap:28, alignItems:'stretch', marginBottom:24}}>
179.           <div>
180.             <div style={{display:'flex', gap:8, marginBottom:14, flexWrap:'wrap'}}>
181.               <CatChip cat={article.category}/>
182.               <XpBadge xp={article.xp}/>
183.             </div>
184.             <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:40, lineHeight:1.05, color:'#1b1230', margin:'0 0 14px', letterSpacing:'-0.02em'}}>{article.title}</h1>
185.             <div style={{display:'flex', gap:14, color:'#6b5c80', fontSize:13, fontWeight:700, flexWrap:'wrap', alignItems:'center'}}>
186.               <span>📰 {article.source}</span><span>·</span>
187.               <span>⏱ {article.readMins} min read</span>
188.               {article.minedAt && (<>
189.                 <span>·</span>
190.                 <span title={`Mined ${article.minedAt}${article.sourcePublishedAt ? ' · source published ' + article.sourcePublishedAt : ''}`}>
191.                   🗞 Mined {formatDate(article.minedAt)}
192.                 </span>
193.               </>)}
194.             </div>
195.           </div>
196.           <div style={{borderRadius:22, overflow:'hidden', border:`3px solid ${catColor}`, background:`url(${article.image}) center/cover`, minHeight:220, position:'relative'}}>
197.             <div style={{position:'absolute', bottom:12, right:12, background:'rgba(255,255,255,0.9)', padding:'6px 12px', borderRadius:999, fontSize:11, fontWeight:700, color:'#6b5c80'}}>
198.               📷 {article.source}
199.             </div>
200.           </div>
201.         </div>
202. 
203.         {/* ——— TABS CONTENT ——— */}
204.         {!detailReady && !detailError && (
205.           <div style={{background:'#fff', borderRadius:22, padding:'40px 32px', border:'2px dashed #f0e8d8', textAlign:'center', color:'#6b5c80'}}>
206.             <div style={{fontSize:36, marginBottom:10}}>📡</div>
207.             <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', marginBottom:6}}>Loading the full story…</div>
208.             <div style={{fontSize:13}}>Fetching keywords, quiz, and background.</div>
209.           </div>
210.         )}
211.         {detailError && (
212.           <div style={{background:'#fff', borderRadius:22, padding:'40px 32px', border:'2px solid #ffb98a', textAlign:'center', color:'#6b5c80'}}>
213.             <div style={{fontSize:36, marginBottom:10}}>⚠️</div>
214.             <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', marginBottom:6}}>Couldn't load this story.</div>
215.             <div style={{fontSize:13}}>Try again in a moment.</div>
216.           </div>
217.         )}
218. 
219.         {detailReady && tab === 'read' && (
220.           <ReadAndWordsTab
221.             article={article}
222.             paragraphs={paragraphs}
223.             expanded={expandedKw}
224.             setExpanded={setExpandedKw}
225.             onFinish={() => { bumpProgress(25); switchTab('analyze'); }}
226.           />
227.         )}
228. 
229.         {detailReady && tab === 'analyze' && (
230.           <AnalyzeTab article={article} paragraphs={paragraphs} onNext={()=>{ bumpProgress(50); switchTab('quiz'); }} />
231.         )}
232. 
233.         {detailReady && tab === 'quiz' && (
234.           <QuizTab
235.             article={article} paragraphs={paragraphs}
236.             quizIdx={quizIdx} setQuizIdx={setQuizIdx}
237.             quizAns={quizAns} setQuizAns={setQuizAns}
238.             quizShow={quizShow} setQuizShow={setQuizShow}
239.             onFinish={() => { bumpProgress(75); setConfetti(true); setTimeout(()=>setConfetti(false), 1800); switchTab('discuss'); }}
240.           />
241.         )}
242. 
243.         {detailReady && tab === 'discuss' && (
244.           <DiscussTab article={article} paragraphs={paragraphs} onDone={()=>{ bumpProgress(100); onComplete(); }} />
245.         )}
246.       </div>
247. 
248.       {confetti && <Confetti/>}
249.     </div>
250.   );
251. }
252. 
253. // ——— Highlight keywords in a text string ———
254. // Matches base terms AND common English inflections (ban → banned, fine → fined).
255. // The base term is captured as group 1 so we can look up the definition even
256. // when the matched text is an inflected form like "banned".
257. function highlightText(text, keywords, catColor) {
258.   if (!keywords || !keywords.length) return [text];
259.   const termMap = {};
260.   keywords.forEach(k => { termMap[k.term.toLowerCase()] = k; });
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 1-360)

<details>
<summary>360 lines</summary>

```
1. """Full round — news + science + fun aggregators → optimize images → upload to
2. Storage → write redesign_runs + redesign_stories → emit v1-shape payload files
3. for the new v2 UI.
4. 
5. Run:  python -m pipeline.full_round
6. View: http://localhost:18100/  (UI loads from website/payloads/ + article_payloads/ + article_images/)
7. """
8. from __future__ import annotations
9. 
10. import hashlib
11. import json
12. import logging
13. from datetime import datetime, timezone
14. from pathlib import Path
15. from urllib.parse import urlparse
16. 
17. from .news_rss_core import (check_duplicates, detail_enrich,
18.                               run_source_phase_a, tri_variant_rewrite)
19. from .fun_sources import todays_enabled_sources as fun_sources
20. from .fun_sources import todays_topic as fun_topic
21. from .science_sources import todays_enabled_sources as science_sources
22. from .science_sources import todays_topic as science_topic
23. from .image_optimize import fetch_and_optimize
24. from .supabase_io import insert_run, insert_story, update_run, upload_image
25. from .news_sources import enabled_sources as news_sources
26. from .news_aggregate import run_source_with_backups as run_news
27. from .science_aggregate import run_source_with_backups as run_sci
28. from .fun_aggregate import run_source_with_backups as run_fun
29. from .news_sources import backup_sources as news_backups
30. from .science_sources import todays_backup_sources as sci_backups
31. from .fun_sources import todays_backup_sources as fun_backups
32. 
33. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
34. log = logging.getLogger("full-round")
35. 
36. 
37. # -------------------------------------------------------------------
38. # 1) Aggregate 3 categories
39. # -------------------------------------------------------------------
40. 
41. def aggregate_category(label: str, enabled: list, backups: list, runner) -> dict[str, dict]:
42.     """Run Phase A for each source; return `{source_name: {source, candidates}}`.
43.     Each source contributes up to 4 ranked candidates (choice_1…). If the
44.     primary source yields 0 candidates, rotates to a backup source (handled
45.     inside `runner`)."""
46.     log.info("[%s] aggregating from %d sources", label, len(enabled))
47.     used_backups: set[str] = set()
48.     by_source: dict[str, dict] = {}
49.     for source in enabled:
50.         avail = [b for b in backups if b.name not in used_backups]
51.         res = runner(source, avail)
52.         if not res:
53.             continue
54.         # Supports both the new multi-candidate Phase A return shape and the
55.         # legacy single-winner shape (some aggregator paths still produce
56.         # the latter, e.g. after backup rotation).
57.         cands = res.get("candidates")
58.         if not cands and res.get("winner"):
59.             cands = [{"winner": res["winner"], "slot": res.get("winner_slot") or "choice_1"}]
60.         if not cands:
61.             continue
62.         src_obj = res["source"]
63.         by_source[src_obj.name] = {"source": src_obj, "candidates": cands}
64.         if res.get("used_backup"):
65.             used_backups.add(src_obj.name)
66.     return by_source
67. 
68. 
69. def _normalize_title(t: str) -> str:
70.     """lowercase + strip punctuation + collapse whitespace for similarity match."""
71.     import re as _re
72.     s = (t or "").lower()
73.     s = _re.sub(r"[^\w\s]", " ", s)
74.     s = _re.sub(r"\s+", " ", s).strip()
75.     return s
76. 
77. 
78. def _title_similarity(a: str, b: str) -> float:
79.     from difflib import SequenceMatcher
80.     return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()
81. 
82. 
83. # Shape used by filter_past_duplicates + pick_winners_with_dedup:
84. #   by_source = {
85. #     <source_name>: {"source": <SourceObj>, "candidates": [{"winner": art, "slot": "choice_1"}, ...]},
86. #     ...
87. #   }
88. 
89. 
90. def filter_past_duplicates(category: str, by_source: dict[str, dict],
91.                            days: int = 3, threshold: float = 0.80) -> dict[str, dict]:
92.     """Drop candidates whose title ≥threshold-matches any story this category
93.     published in the last `days` days. Cheap — SequenceMatcher on a few
94.     dozen title pairs is microseconds."""
95.     from datetime import date, timedelta
96.     from .supabase_io import client
97.     try:
98.         sb = client()
99.     except Exception as e:
100.         log.warning("past-dedup skipped — Supabase unreachable: %s", e)
101.         return by_source
102.     start = (date.today() - timedelta(days=days)).isoformat()
103.     try:
104.         r = sb.table("redesign_stories").select(
105.             "source_title, category, published_date"
106.         ).eq("category", category).gte("published_date", start).execute()
107.         past_titles = [row.get("source_title") or "" for row in (r.data or [])]
108.     except Exception as e:
109.         log.warning("past-dedup query failed — skipping: %s", e)
110.         return by_source
111. 
112.     if not past_titles:
113.         log.info("  [%s] past-dedup: no prior stories in last %d days", category, days)
114.         return by_source
115. 
116.     result: dict[str, dict] = {}
117.     for name, bundle in by_source.items():
118.         kept: list[dict] = []
119.         for c in bundle["candidates"]:
120.             t = (c["winner"].get("title") or "")
121.             best = max((_title_similarity(t, pt) for pt in past_titles), default=0.0)
122.             if best >= threshold:
123.                 log.info("  [%s/%s] past-dup drop %s (sim=%.2f) — %s",
124.                          category, name, c.get("slot"), best, t[:60])
125.             else:
126.                 kept.append(c)
127.         result[name] = {"source": bundle["source"], "candidates": kept}
128.     return result
129. 
130. 
131. def pick_winners_with_dedup(by_source: dict[str, dict]) -> list[dict]:
132.     """Pick the highest-ranked surviving candidate per source, then
133.     cross-source dedup. When a pair of today's picks duplicates, drop the
134.     weaker source's current pick and promote its NEXT candidate (no extra
135.     DeepSeek-and-RSS round-trip — we already mined up to 4 per source)."""
136.     ptrs: dict[str, int] = {name: 0 for name in by_source}
137.     exhausted: set[str] = set()
138. 
139.     def current_for(name: str) -> dict | None:
140.         idx = ptrs.get(name, 0)
141.         cands = by_source[name].get("candidates") or []
142.         return cands[idx] if idx < len(cands) else None
143. 
144.     for _round in range(8):
145.         picks: list[tuple[str, dict]] = []
146.         for name in by_source:
147.             if name in exhausted:
148.                 continue
149.             c = current_for(name)
150.             if c:
151.                 picks.append((name, c))
152.         if len(picks) < 2:
153.             break
154.         briefs = [
155.             {"id": i, "title": c["winner"].get("title"),
156.              "source_name": name,
157.              "source_priority": getattr(by_source[name]["source"], "priority", 9),
158.              "excerpt": (c["winner"].get("body") or "")[:400]}
159.             for i, (name, c) in enumerate(picks)
160.         ]
161.         dup = check_duplicates(briefs)
162.         if dup.get("verdict") != "DUP_FOUND":
163.             break
164.         drop_id = dup.get("drop_suggestion")
165.         if drop_id is None and dup.get("duplicate_pairs"):
166.             pair = dup["duplicate_pairs"][0]["ids"]
167.             drop_id = max(pair, key=lambda i: briefs[i]["source_priority"])
168.         if drop_id is None or drop_id >= len(picks):
169.             break
170.         drop_name, drop_cand = picks[drop_id]
171.         log.info("  cross-source dup — promoting next candidate for [%s] "
172.                  "(was %s: %s)",
173.                  drop_name, drop_cand["slot"],
174.                  (drop_cand["winner"].get("title") or "")[:50])
175.         ptrs[drop_name] += 1
176.         if ptrs[drop_name] >= len(by_source[drop_name].get("candidates") or []):
177.             log.warning("  [%s] exhausted all candidates — skipping", drop_name)
178.             exhausted.add(drop_name)
179. 
180.     final: list[dict] = []
181.     for name, bundle in by_source.items():
182.         if name in exhausted:
183.             continue
184.         c = current_for(name)
185.         if c:
186.             final.append({
187.                 "source": bundle["source"],
188.                 "winner": c["winner"],
189.                 "winner_slot": c["slot"],
190.             })
191.     return final
192. 
193. 
194. # -------------------------------------------------------------------
195. # 2) Optimize + upload images
196. # -------------------------------------------------------------------
197. 
198. def _short_hash(s: str) -> str:
199.     return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
200. 
201. 
202. def process_images(stories: list[dict], today: str, website_dir: Path) -> None:
203.     """For each story winner, download + optimize og:image → local cache + Supabase Storage.
204.     Annotates each story dict with _image_local, _image_storage_url.
205.     """
206.     images_dir = website_dir / "article_images"
207.     images_dir.mkdir(parents=True, exist_ok=True)
208.     for s in stories:
209.         art = s["winner"]
210.         og = art.get("og_image")
211.         if not og:
212.             log.warning("[%s] no og:image", art.get("title", "")[:60])
213.             continue
214.         img_id = _short_hash(art.get("link") or og)
215.         filename = f"article_{img_id}.webp"
216.         local_path = images_dir / filename
217.         info = fetch_and_optimize(og, local_path)
218.         if not info:
219.             log.warning("  skip image for %s", art.get("title", "")[:60])
220.             continue
221.         s["_image_id"] = img_id
222.         s["_image_local"] = f"article_images/{filename}"
223.         s["_image_info"] = info
224.         # Upload to Supabase Storage (public)
225.         storage_name = f"{today}/{filename}"
226.         storage_url = upload_image(local_path, storage_name)
227.         if storage_url:
228.             s["_image_storage_url"] = storage_url
229.         log.info("  ✓ image %s (%.1f KB, q=%d)  %s",
230.                  filename, info["final_bytes"] / 1024, info["final_quality"],
231.                  "+ uploaded" if storage_url else "local-only")
232. 
233. 
234. # -------------------------------------------------------------------
235. # 3) Rewrite (tri-variant) — batched per category
236. # -------------------------------------------------------------------
237. 
238. def rewrite_for_category(stories: list[dict]) -> tuple[dict[int, dict], dict]:
239.     """Tri-variant rewrite, then detail enrichment. Returns
240.     (variants_by_src_id, details_by_slot). Raises if either step ultimately
241.     fails — callers decide whether that's fatal for the whole run."""
242.     if not stories:
243.         return {}, {}
244.     articles_for_rewrite = [(i, s["winner"]) for i, s in enumerate(stories)]
245.     rewrite_res = tri_variant_rewrite(articles_for_rewrite)
246.     variants = {a.get("source_id"): a for a in rewrite_res.get("articles") or []}
247.     if len(variants) < len(stories):
248.         raise RuntimeError(
249.             f"rewrite returned {len(variants)} variants for {len(stories)} stories"
250.         )
251. 
252.     # Phase D — detail enrichment (1 extra call per category)
253.     enrich = detail_enrich(rewrite_res)
254.     details_by_slot = enrich.get("details") or {}
255.     expected_slots = len(stories) * 2  # easy + middle per story
256.     if len(details_by_slot) < expected_slots:
257.         raise RuntimeError(
258.             f"detail_enrich returned {len(details_by_slot)} slots, "
259.             f"expected {expected_slots}"
260.         )
261.     return variants, details_by_slot
262. 
263. 
264. # -------------------------------------------------------------------
265. # 4) Emit v1-shape payload files (what the existing v2 UI reads)
266. # -------------------------------------------------------------------
267. 
268. def make_story_id(date: str, category: str, slot: int) -> str:
269.     return f"{date}-{category.lower()}-{slot}"
270. 
271. 
272. def card_summary(variant: dict, max_words: int = 120) -> str:
273.     """Short blurb for the home-page card. Prefer `card_summary` from the
274.     rewriter; fall back to the first few sentences of `body` capped at
275.     `max_words`. Strip to whole sentence so it never ends mid-word."""
276.     cs = (variant.get("card_summary") or "").strip()
277.     if cs:
278.         words = cs.split()
279.         if len(words) <= max_words:
280.             return cs
281.         return " ".join(words[:max_words]).rstrip(",;:") + "…"
282.     body = (variant.get("body") or "").strip()
283.     if not body:
284.         return ""
285.     import re
286.     sentences = re.split(r'(?<=[.!?])\s+', body)
287.     out, count = [], 0
288.     for s in sentences:
289.         n = len(s.split())
290.         if count + n > max_words and out:
291.             break
292.         out.append(s)
293.         count += n
294.         if count >= max_words * 0.6:  # stop once we have a reasonable blurb
295.             break
296.     return " ".join(out).strip()
297. 
298. 
299. def emit_v1_shape(stories_by_cat: dict[str, list[dict]],
300.                   variants_by_cat: dict[str, dict[int, dict]],
301.                   details_by_cat: dict[str, dict[str, dict]],
302.                   today: str,
303.                   website_dir: Path) -> None:
304.     """Write v1-compatible payload files the prototype UI already reads:
305.       payloads/articles_<cat>_<level>.json  (listings)
306.       article_payloads/payload_<id>/<level>.json  (detail)
307.     """
308.     payloads_dir = website_dir / "payloads"
309.     details_dir = website_dir / "article_payloads"
310.     payloads_dir.mkdir(parents=True, exist_ok=True)
311.     details_dir.mkdir(parents=True, exist_ok=True)
312. 
313.     mined_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
314. 
315.     for category in ("News", "Science", "Fun"):
316.         stories = stories_by_cat.get(category, [])
317.         variants = variants_by_cat.get(category, {})
318.         details = details_by_cat.get(category, {})
319.         # Build one listing file per level (easy / middle / cn) per category
320.         per_level_articles = {"easy": [], "middle": [], "cn": []}
321.         for slot, s in enumerate(stories, start=1):
322.             art = s["winner"]
323.             var = variants.get(slot - 1) or {}
324.             story_id = s.get("_story_id") or make_story_id(today, category, slot)
325.             s["_story_id"] = story_id
326.             img_local = s.get("_image_local") or ""
327.             src_name = s["source"].name
328.             src_url = art.get("link") or ""
329.             time_ago = art.get("published") or ""
330. 
331.             easy = var.get("easy_en") or {}
332.             middle = var.get("middle_en") or {}
333.             zh = var.get("zh") or {}
334. 
335.             # Listings (flat, v1-shape) — summary is short card blurb (≤120 words)
336.             common_listing = {
337.                 "id": story_id,
338.                 "source": src_name,
339.                 "time_ago": time_ago,
340.                 "mined_at": mined_at,                  # when this pipeline run captured the story
341.                 "source_published_at": art.get("published") or "",
342.                 "image_url": f"/{img_local}" if img_local else "",
343.                 "category": category,
344.             }
345.             per_level_articles["easy"].append({**common_listing,
346.                 "title": easy.get("headline") or art.get("title") or "",
347.                 "summary": card_summary(easy),
348.             })
349.             per_level_articles["middle"].append({**common_listing,
350.                 "title": middle.get("headline") or art.get("title") or "",
351.                 "summary": card_summary(middle),
352.             })
353.             per_level_articles["cn"].append({**common_listing,
354.                 "title": zh.get("headline") or "",
355.                 "summary": zh.get("summary") or "",
356.             })
357. 
358.             # Detail payloads (per-story, per-level). Chinese is summary-only → no detail.
359.             story_detail_dir = details_dir / f"payload_{story_id}"
360.             story_detail_dir.mkdir(parents=True, exist_ok=True)
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 1-900)

<details>
<summary>492 lines</summary>

````
1. """Shared core for RSS → filter → batched vet+cluster → batched rewrite.
2. 
3. Used by news_aj_full.py and news_pbs_full.py. Parameterized by:
4.   - RSS URL
5.   - source label (for HTML title)
6.   - MAX_KEPT (cap on articles sent to vetter)
7.   - PICK_COUNT (how many the curator picks)
8.   - TARGET_WORDS (kids article length)
9.   - output filenames
10. 
11. Vet thresholds (locked 2026-04-23):
12.   - REJECT if any dim >= 4 OR total > 6
13.   - CAUTION if total 5-6 AND every dim <= 3
14.   - SAFE if total 0-4 AND every dim <= 3
15. """
16. from __future__ import annotations
17. 
18. import html
19. import json
20. import logging
21. import os
22. import re
23. import time
24. from datetime import datetime, timezone
25. from pathlib import Path
26. from urllib.parse import urlparse
27. 
28. import feedparser
29. import requests
30. 
31. from .cleaner import extract_article_from_html
32. 
33. log = logging.getLogger("rss-core")
34. 
35. # Load .env once on module import
36. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
37. for _line in (_envp.open() if _envp.exists() else []):
38.     if "=" in _line and not _line.startswith("#"):
39.         _k, _v = _line.strip().split("=", 1)
40.         os.environ[_k] = _v
41. 
42. DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
43. DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
44. 
45. MIN_WORDS_DEFAULT = 500
46. MAX_RSS_DEFAULT = 25
47. VIDEO_PATH_RE = re.compile(r"/video/", re.I)
48. HTML_FETCH_TIMEOUT = 15
49. HTML_FETCH_HEADERS = {
50.     # Real browser UA — NPR and some others block bot-flavored UAs.
51.     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
52.                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
53.     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
54.     "Accept-Language": "en-US,en;q=0.9",
55. }
56. 
57. SAFETY_DIMS = ["violence", "sexual", "substance", "language", "fear",
58.                "adult_themes", "distress", "bias"]
59. SAFETY_SHORT = ["Viol", "Sex", "Subst", "Lang", "Fear", "Adult", "Distr", "Bias"]
60. 
61. # Generic social-share default images (usually a site logo or blank template,
62. # not a real article image). Detected by URL substring.
63. BAD_IMAGE_PATTERNS = (
64.     "facebook-default",
65.     "twitter-default",
66.     "og-default",
67.     "share-default",
68.     "default-share",
69.     "default-og",
70.     "default-social",
71. )
72. 
73. MIN_PICK_BODY_WORDS = 250   # fall back to alternate if pick's body is thinner than this
74. 
75. 
76. def is_generic_social_image(url: str | None) -> bool:
77.     if not url:
78.         return True
79.     u = url.lower()
80.     return any(p in u for p in BAD_IMAGE_PATTERNS)
81. 
82. 
83. # ---------------------------------------------------------------------------
84. # Vet threshold evaluator (Python-side, authoritative)
85. # ---------------------------------------------------------------------------
86. 
87. def apply_vet_thresholds(safety: dict) -> str:
88.     """Authoritative verdict from safety scores.
89. 
90.     REJECT if any dim >= 4 OR total > 6.
91.     CAUTION if total 5-6 AND every dim <= 3.
92.     SAFE if total 0-4 AND every dim <= 3.
93.     """
94.     dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
95.     total = safety.get("total")
96.     if total is None:
97.         total = sum(dims)
98.     max_dim = max(dims) if dims else 0
99.     if max_dim >= 4 or total > 6:
100.         return "REJECT"
101.     if 5 <= total <= 6:
102.         return "CAUTION"
103.     return "SAFE"
104. 
105. 
106. # ---------------------------------------------------------------------------
107. # Step 1+2: RSS + HTML scrape + filter
108. # ---------------------------------------------------------------------------
109. 
110. def fetch_rss_entries(url: str, max_entries: int = MAX_RSS_DEFAULT) -> list[dict]:
111.     feed = feedparser.parse(url)
112.     out = []
113.     for entry in feed.entries[:max_entries]:
114.         out.append({
115.             "title": getattr(entry, "title", ""),
116.             "link": getattr(entry, "link", ""),
117.             "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
118.             "summary": getattr(entry, "summary", ""),
119.         })
120.     return out
121. 
122. 
123. def fetch_html(url: str) -> str | None:
124.     try:
125.         r = requests.get(url, timeout=HTML_FETCH_TIMEOUT, headers=HTML_FETCH_HEADERS,
126.                          allow_redirects=True)
127.         if r.status_code >= 400:
128.             return None
129.         return r.text
130.     except requests.RequestException:
131.         return None
132. 
133. 
134. def process_entry(entry: dict, min_words: int = MIN_WORDS_DEFAULT) -> dict:
135.     url = entry["link"]
136.     if VIDEO_PATH_RE.search(url):
137.         return {**entry, "og_image": None, "body": "", "word_count": 0,
138.                 "skip_reason": "video URL", "highlights": [], "paragraphs": []}
139.     html_text = fetch_html(url)
140.     if not html_text:
141.         return {**entry, "og_image": None, "body": "", "word_count": 0,
142.                 "skip_reason": "html fetch failed", "highlights": [], "paragraphs": []}
143.     extracted = extract_article_from_html(url, html_text)
144.     body = extracted.get("cleaned_body") or ""
145.     paragraphs = extracted.get("paragraphs") or []
146.     og_image = extracted.get("og_image")
147.     wc = len(body.split()) if body else 0
148.     skip_reason = None
149.     if wc < min_words:
150.         skip_reason = f"{wc}w < {min_words}w"
151.     elif not og_image:
152.         skip_reason = "no og:image"
153.     hls = [p for p in paragraphs if len(p.split()) >= 12][:3]
154.     return {
155.         **entry,
156.         "og_image": og_image,
157.         "body": body,
158.         "word_count": wc,
159.         "paragraphs": paragraphs,
160.         "highlights": hls,
161.         "skip_reason": skip_reason,
162.     }
163. 
164. 
165. # ---------------------------------------------------------------------------
166. # Step 3: BATCHED vet+cluster+curate (1 DeepSeek call)
167. # ---------------------------------------------------------------------------
168. 
169. def build_vet_prompt(pick_count: int) -> str:
170.     return f"""You are a content reviewer + curator for a kids news site (readers age 12).
171. 
172. You will receive a numbered list of news articles (id 0..N-1), each with title + first paragraphs.
173. 
174. TASK 1 — Vet every article on 8 safety dimensions and 3 interest dimensions.
175. 
176.   Safety (score each 0-5, where 0=none, 5=severe):
177.     violence, sexual, substance, language, fear, adult_themes, distress, bias
178.     Compute total = sum of 8 dims.
179.     Initial safety_verdict (we will re-apply strict thresholds downstream):
180.       any_dim >= 4 or total > 6  -> REJECT
181.       total 5-6 (and all dims <= 3) -> CAUTION
182.       total 0-4 -> SAFE
183. 
184.   Interest (score each 0-5):
185.     importance  — how globally significant
186.     fun_factor  — how delightful / surprising / fun
187.     kid_appeal  — how likely a 12-year-old would want to read this
188.     interest_peak = max(importance, fun_factor, kid_appeal)
189.     interest_verdict:
190.       peak >= 3 -> ENGAGING
191.       peak == 2 -> MEH
192.       peak <= 1 -> BORING
193. 
194. TASK 2 — Detect topic clusters.
195.   A cluster = 2+ articles on the SAME real-world story/topic.
196.   Give each cluster a short id and theme. Size-3+ clusters are HOT.
197. 
198. TASK 3 — Pick exactly {pick_count} stories for publishing.
199.   Rules:
200.     R1: NEVER pick a REJECT (any_dim >= 4 or total > 6).
201.     R2: Prefer HOT cluster members at SAFE level. CAUTION is acceptable only
202.         if no SAFE hot-cluster member exists.
203.     R3: Prefer interest_verdict=ENGAGING. Never pick BORING unless no alternative.
204.     R4: Diversify — picks should come from DIFFERENT clusters if possible.
205.     R5: Avoid gossip, obituaries, dry business jargon, sports-results-only.
206. 
207. TASK 4 — List 3-4 RANKED alternates (next-best IDs) in case a pick fails the
208.   later content-quality check (thin body, missing real image, etc.).
209.   Do not repeat picks in alternates.
210. 
211. Return ONLY valid JSON (no markdown fences):
212. {{
213.   "vet": [
214.     {{
215.       "id": 0,
216.       "safety": {{"violence": 0, "sexual": 0, "substance": 0, "language": 0,
217.                   "fear": 0, "adult_themes": 0, "distress": 0, "bias": 0,
218.                   "total": 0, "verdict": "SAFE"}},
219.       "interest": {{"importance": 0, "fun_factor": 0, "kid_appeal": 0,
220.                     "peak": 0, "verdict": "ENGAGING"}},
221.       "cluster_id": "cluster_x",
222.       "flags": ["..."]
223.     }},
224.     ... one per input ...
225.   ],
226.   "clusters": [
227.     {{"id": "cluster_x", "theme": "...", "members": [0,1], "size": 2, "is_hot": false}}
228.   ],
229.   "picks": [
230.     {{"id": 0, "reason": "must cite safety verdict, interest peak, and cluster status"}},
231.     ... {pick_count} total ...
232.   ],
233.   "alternates": [
234.     {{"id": 7, "reason": "..."}},
235.     {{"id": 12, "reason": "..."}},
236.     {{"id": 3, "reason": "..."}}
237.   ]
238. }}"""
239. 
240. 
241. def deepseek_call(system: str, user: str, max_tokens: int, temperature: float = 0.2,
242.                   max_attempts: int = 3) -> dict:
243.     """Call deepseek-chat with JSON output. Retries on JSON parse failure
244.     (model occasionally emits malformed JSON) and transient HTTP errors."""
245.     last_err: Exception | None = None
246.     for attempt in range(1, max_attempts + 1):
247.         try:
248.             r = requests.post(DEEPSEEK_ENDPOINT,
249.                 json={
250.                     "model": "deepseek-chat",
251.                     "messages": [{"role": "system", "content": system},
252.                                  {"role": "user", "content": user}],
253.                     "temperature": temperature,
254.                     "max_tokens": max_tokens,
255.                 },
256.                 headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
257.                 timeout=120)
258.             r.raise_for_status()
259.             content = r.json()["choices"][0]["message"]["content"]
260.             content = re.sub(r"^```json\s*", "", content.strip())
261.             content = re.sub(r"\s*```\s*$", "", content)
262.             return json.loads(content)
263.         except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
264.                 requests.Timeout) as e:
265.             last_err = e
266.             log.warning("chat attempt %d/%d failed: %s",
267.                         attempt, max_attempts, str(e)[:200])
268.             if attempt < max_attempts:
269.                 time.sleep(2 * attempt)
270.     raise RuntimeError(f"deepseek_call exhausted {max_attempts} attempts") from last_err
271. 
272. 
273. def vet_curator_input(briefs: list[dict], pick_count: int) -> str:
274.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.",
275.              f"Articles to vet + cluster + pick {pick_count}:", ""]
276.     for i, b in enumerate(briefs):
277.         hls = b.get("highlights") or []
278.         hls_text = " ".join(hls)[:400] if hls else (b.get("summary", "") or "")[:400]
279.         lines.append(f"[id: {i}] {b.get('title','')}")
280.         lines.append(f"  first paragraphs: {hls_text}")
281.         lines.append("")
282.     return "\n".join(lines)
283. 
284. 
285. def vet_and_curate(briefs: list[dict], pick_count: int) -> dict:
286.     result = deepseek_call(build_vet_prompt(pick_count), vet_curator_input(briefs, pick_count),
287.                            max_tokens=3500, temperature=0.2)
288.     # Re-apply thresholds authoritatively on Python side
289.     for v in result.get("vet") or []:
290.         safety = v.get("safety") or {}
291.         # Recompute total from dims (trust dim scores, not model's stated total)
292.         dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
293.         safety["total"] = sum(dims)
294.         safety["verdict"] = apply_vet_thresholds(safety)
295.     # Filter out any picks that are REJECT under the new rule
296.     vet_by_id = {v["id"]: v for v in result.get("vet") or []}
297.     filtered_picks = []
298.     for p in result.get("picks") or []:
299.         pid = p.get("id")
300.         v = vet_by_id.get(pid)
301.         if v and v.get("safety", {}).get("verdict") == "REJECT":
302.             log.warning("  dropping picked id=%s — REJECT on strict thresholds", pid)
303.             continue
304.         filtered_picks.append(p)
305.     result["picks"] = filtered_picks
306.     return result
307. 
308. 
309. # ---------------------------------------------------------------------------
310. # Step 4: BATCHED rewrite (1 DeepSeek call)
311. # ---------------------------------------------------------------------------
312. 
313. def build_rewriter_prompt(pick_count: int, target_words: int) -> str:
314.     return f"""You are a news writer for "News Oh, Ye!", a news site for 12-year-old readers.
315. 
316. You will receive {pick_count} source articles (with title + full body). Rewrite EACH as a
317. kid-friendly news story at a 12-year-old / 7th-grade reading level.
318. 
319. WORD COUNT — STRICT:
320.   Each article's `body` MUST be {target_words - 20}-{target_words + 20} words.
321.   Count silently before returning; if under, add a concrete example or vivid detail.
322. 
323. READING LEVEL:
324.   Aim for 12 years old (7th grade). That means:
325.   · Use real, interesting vocabulary — not baby talk. Words like
326.     "crucial", "controversial", "ambitious", "negotiation", "historic",
327.     "escalate", "diplomat", "coalition", "sanction", "evacuate",
328.     "unprecedented", "stabilize", "devastation" are fair game.
329.   · The FIRST time you use any specialized term, EXPLAIN it inline in
330.     plain English:
331.     "a ceasefire (when both sides agree to stop fighting for a while)"
332.     "sanctions — rules that block trade and money between countries"
333.   · Mix sentence lengths: some short and punchy, some longer with clauses.
334. 
335. TONE & STRUCTURE (every article):
336.   Para 1 — HOOK (surprising detail, vivid scene, or question) + the
337.            essential WHO, WHAT, WHERE, WHEN in 2-4 sentences.
338.   Para 2-3 — EXPLAIN the background a 12-year-old needs to understand why.
339.   Para 4 — PERSPECTIVES: what do different sides think?
340.   Para 5 — "WHY IT MATTERS": 1-2 sentences connecting to the reader's world.
341. 
342. ACCURACY:
343.   Every fact MUST come from the source. Don't invent names, dates, numbers.
344. 
345. HEADLINE:
346.   A NEW kid-friendly headline — different wording from the source.
347. 
348. OUTPUT — valid JSON only (no markdown fences):
349. {{
350.   "articles": [
351.     {{
352.       "source_id": <int>,
353.       "headline": "...",
354.       "body": "paragraph 1\\n\\nparagraph 2\\n\\n...",
355.       "why_it_matters": "..."
356.     }},
357.     ... one per input ...
358.   ]
359. }}"""
360. 
361. 
362. def rewriter_input(articles_with_ids: list[tuple[int, dict]], target_words: int) -> str:
363.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
364.     for src_id, art in articles_with_ids:
365.         host = urlparse(art.get("link") or "").netloc.replace("www.", "")
366.         body = art.get("body") or ""
367.         words = body.split()
368.         body_trimmed = " ".join(words[:2500])
369.         lines.append(f"=== SOURCE [id: {src_id}] ===")
370.         lines.append(f"Title: {art.get('title','')}")
371.         lines.append(f"Host: {host}")
372.         lines.append(f"Date: {art.get('published','')}")
373.         lines.append("")
374.         lines.append("Full body:")
375.         lines.append(body_trimmed)
376.         lines.append("")
377.     lines.append(f"Write {len(articles_with_ids)} kids articles. Each body: "
378.                  f"{target_words - 20}-{target_words + 20} words.")
379.     return "\n".join(lines)
380. 
381. 
382. def rewrite_batch(articles_with_ids: list[tuple[int, dict]], target_words: int) -> dict:
383.     return deepseek_call(build_rewriter_prompt(len(articles_with_ids), target_words),
384.                          rewriter_input(articles_with_ids, target_words),
385.                          max_tokens=3000, temperature=0.5)
386. 
387. 
388. # ---------------------------------------------------------------------------
389. # Tri-variant rewriter (easy_en + middle_en + zh-summary)
390. # ---------------------------------------------------------------------------
391. 
392. TRI_VARIANT_REWRITER_PROMPT = """You are a 小记者 (junior reporter) at "News Oh, Ye!" — YOU
393. are a kid yourself, writing for OTHER kids. Your voice is curious, excited, and
394. engaging — like a smart older sibling who just found a cool story and can't wait
395. to tell their friends. Don't sound like a grown-up news anchor. NEVER be boring.
396. 
397. What real kid reporters do:
398.   · Start with a HOOK — a surprising detail, a vivid scene, or a direct
399.     question to the reader. NEVER open with a dry "who did what" summary.
400.   · Use "you" to pull the reader in ("Have you ever wondered…?", "Imagine…")
401.   · Find the WEIRD, COOL, or SURPRISING part of the story and lead with it
402.   · Use specific details (real numbers, names, places) — concrete beats vague
403.   · Compare new concepts to things kids already know
404.     ("about the size of a school bus", "as tall as a 10-story building",
405.      "that's like filling 50 swimming pools with…")
406.   · Mix sentence lengths. Short ones for impact. Longer ones for explaining.
407.   · Show enthusiasm — let the "wow, did you know?!" energy come through
408. 
409. You will receive N source articles. For EACH, produce THREE variants:
410. 
411. 1. easy_en — English. READER IS A 10-YEAR-OLD (grade 4).
412.    · body: 170-210 words (STRICT — count before returning)
413.    · Simple but not baby-talk; explain any hard word inline in plain English:
414.      "a ceasefire (when both sides agree to stop fighting for a while)"
415.    · Short, punchy sentences; lead with a hook — not a summary
416.    · card_summary: 6-9 sentences, MAX 120 words. Shown on the home-page card.
417.      Opens with a hook, then covers the WHO / WHAT / WHERE / WHY in plain
418.      words — enough that a kid understands the story without clicking. Uses
419.      one or two concrete details (names, numbers, places). NOT a restatement
420.      of the headline. Ends with punctuation.
421. 
422. 2. middle_en — English. READER IS A MIDDLE SCHOOLER (grade 7-8, age 12-14).
423.    · body: 320-350 words (STRICT — if under 320, add MORE vivid details,
424.      specific names or numbers, or a direct quote from the source; never invent)
425.    · Richer vocabulary ("crucial", "unprecedented", "diplomat", "negotiation",
426.      "escalate", "sanction", "controversial", "coalition"); explain inline
427.      the first time you use a specialized term
428.    · Mix short impact sentences with longer, complex ones
429.    · card_summary: 6-9 sentences, MAX 120 words. Shown on the home-page card.
430.      Opens with a hook, covers the WHO / WHAT / WHERE / WHY plus one line on
431.      the tension or stakes. Include 2-3 concrete details (names, numbers,
432.      places, quotes) so a middle-schooler can grasp the story without
433.      clicking. NOT a restatement of the headline. Ends with punctuation.
434. 
435. 3. zh — 简体中文. 摘要卡片 only (no body, no quiz, no keywords).
436.    · headline: 有意思的中文标题 (可保留 CEO / iPhone / iPad 等专有名词为英文)
437.    · summary: 260-300 汉字 (STRICT — count silently, must not exceed 300)
438.      保持小记者的口吻 — 好奇、生动、抓住读者注意。
439.      不要写成干巴巴的新闻摘要。用具体细节、用比喻、用提问。
440. 
441. RULES (all variants):
442.   · ACCURACY — every fact must come from the source. No invented names, dates,
443.     numbers, or quotes.
444.   · NEW HEADLINE per variant — don't copy the source headline verbatim.
445.   · NO dry summary tone — you're a kid reporter excited about a story,
446.     not a wire-service editor.
447. 
448. OUTPUT — valid JSON only (no markdown fences):
449. {
450.   "articles": [
451.     {
452.       "source_id": <int>,
453.       "easy_en":   {"headline": "...", "card_summary": "...", "body": "..."},
454.       "middle_en": {"headline": "...", "card_summary": "...", "body": "..."},
455.       "zh":        {"headline": "...", "summary": "..."}
456.     },
457.     ... one entry per input article ...
458.   ]
459. }"""
460. 
461. 
462. def tri_variant_rewriter_input(articles_with_ids: list[tuple[int, dict]]) -> str:
463.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
464.     for src_id, art in articles_with_ids:
465.         host = urlparse(art.get("link") or "").netloc.replace("www.", "")
466.         body = art.get("body") or ""
467.         body_trimmed = " ".join(body.split()[:2500])
468.         lines.append(f"=== SOURCE [id: {src_id}] ===")
469.         lines.append(f"Title: {art.get('title','')}")
470.         lines.append(f"Host: {host}")
471.         lines.append(f"Date: {art.get('published','')}")
472.         lines.append("")
473.         lines.append("Full body:")
474.         lines.append(body_trimmed)
475.         lines.append("")
476.     lines.append("Write 3 tri-variant entries (easy_en + middle_en + zh) per the rules.")
477.     return "\n".join(lines)
478. 
479. 
480. def tri_variant_rewrite(articles_with_ids: list[tuple[int, dict]]) -> dict:
481.     return deepseek_call(TRI_VARIANT_REWRITER_PROMPT,
482.                          tri_variant_rewriter_input(articles_with_ids),
483.                          max_tokens=5000, temperature=0.5)
484. 
485. 
486. # ---------------------------------------------------------------------------
487. # Detail enrichment — 1 call per category, 6 items (3 articles × 2 EN variants)
488. # References bodies by id instead of re-returning them (saves tokens).
489. # ---------------------------------------------------------------------------
490. 
491. DETAIL_ENRICH_PROMPT = """You are enriching kids-news articles with DEPTH beyond the body text.

[Output truncated. Use view_range=[492, ...] to continue reading. In your next response, you may batch this with other view calls. File has at least 1233 lines.]
````

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py.**

/Users/jiong/myprojects/news-v2/pipeline/pack_and_upload.py (lines 1-520)

<details>
<summary>446 lines</summary>

```
1. """Pack `website/` into a zip and upload it to Supabase Storage as both
2. `<YYYY-MM-DD>.zip` (immutable archive) and `latest.zip` (what the deploy repo's
3. GitHub Action fetches). Also writes a `latest-manifest.json` (+ dated copy)
4. with the version + content hash + story IDs so anyone inspecting the bucket
5. knows what's inside without downloading.
6. 
7. Validates today's content bundle BEFORE packing. If any listing or detail file
8. is missing or incomplete, refuses to upload — the live site keeps yesterday's
9. zip until the pipeline produces a fully-formed bundle.
10. 
11. After a successful upload, runs retention: keeps `latest.*` + the last
12. `RETENTION_DAYS` dated archives; deletes older dated zips + manifests."""
13. from __future__ import annotations
14. 
15. import hashlib
16. import json
17. import logging
18. import os
19. import re
20. import sys
21. import zipfile
22. from datetime import datetime, timezone
23. from io import BytesIO
24. from pathlib import Path
25. 
26. from supabase import create_client
27. 
28. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
29. log = logging.getLogger("pack")
30. 
31. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
32. for _line in (_envp.open() if _envp.exists() else []):
33.     if "=" in _line and not _line.startswith("#"):
34.         k, v = _line.strip().split("=", 1)
35.         os.environ[k] = v
36. 
37. ROOT = Path(__file__).resolve().parent.parent
38. WEB = ROOT / "website"
39. BUCKET = "redesign-daily-content"
40. RETENTION_DAYS = 30  # dated archives older than this get deleted
41. 
42. # Allowlist of top-level files/dirs that ship to production.
43. INCLUDE_FILES = {"index.html", "article.jsx", "home.jsx", "components.jsx",
44.                  "data.jsx", "user-panel.jsx"}
45. INCLUDE_DIRS = {"payloads", "article_payloads", "article_images", "assets"}
46. 
47. 
48. def collect_files() -> list[tuple[Path, str]]:
49.     out: list[tuple[Path, str]] = []
50.     for name in INCLUDE_FILES:
51.         p = WEB / name
52.         if p.is_file():
53.             out.append((p, name))
54.     for d in INCLUDE_DIRS:
55.         base = WEB / d
56.         if not base.is_dir():
57.             continue
58.         for p in base.rglob("*"):
59.             if p.is_file() and not p.name.startswith("."):
60.                 out.append((p, str(p.relative_to(WEB))))
61.     return out
62. 
63. 
64. CATS = ("news", "science", "fun")
65. # (field, min_count) — what a detail payload MUST contain to count as complete.
66. DETAIL_MIN = [
67.     ("keywords", 3),
68.     ("questions", 3),
69.     ("background_read", 1),
70.     ("Article_Structure", 3),
71. ]
72. 
73. 
74. def validate_bundle(today: str) -> None:
75.     """Fail (SystemExit 1) if today's bundle is incomplete. Check:
76.       · 9 listing files (3 cats × easy/middle/cn), each with exactly 3 articles
77.       · 18 detail payloads (9 stories × easy/middle), each with non-empty
78.         keywords/questions/background_read/Article_Structure
79.       · 9 article images on disk (one per story id)
80.     """
81.     errs: list[str] = []
82. 
83.     # Listing files — 2 or 3 per cat/lvl acceptable (ideal=3; 2 after
84.     # cross-source dup drops when all backups are exhausted). <2 is fatal.
85.     payloads = WEB / "payloads"
86.     short_cats: set[str] = set()  # cats that shipped <3
87.     for cat in CATS:
88.         for lvl in ("easy", "middle", "cn"):
89.             p = payloads / f"articles_{cat}_{lvl}.json"
90.             if not p.is_file():
91.                 errs.append(f"missing listing: {p.name}")
92.                 continue
93.             try:
94.                 doc = json.loads(p.read_text())
95.                 arts = doc.get("articles") or []
96.                 if len(arts) < 2:
97.                     errs.append(f"{p.name}: {len(arts)} articles (need ≥2)")
98.                 elif len(arts) < 3:
99.                     short_cats.add(f"{cat}/{lvl}")
100.                 for a in arts:
101.                     if not (a.get("title") and a.get("summary") and a.get("id")):
102.                         errs.append(f"{p.name}: article {a.get('id','?')} missing title/summary/id")
103.             except Exception as e:  # noqa: BLE001
104.                 errs.append(f"{p.name}: parse error {e}")
105.     if short_cats:
106.         log.warning("Shipping with <3 articles in: %s", sorted(short_cats))
107. 
108.     # Detail payloads (easy + middle only; cn has no detail page) — iterate
109.     # actual story IDs from the middle listing so 2-article cats validate
110.     # cleanly.
111.     details = WEB / "article_payloads"
112.     all_story_ids: list[str] = []
113.     for cat in CATS:
114.         p = payloads / f"articles_{cat}_middle.json"
115.         if p.is_file():
116.             try:
117.                 arts = json.loads(p.read_text()).get("articles") or []
118.                 all_story_ids.extend(a.get("id") for a in arts if a.get("id"))
119.             except Exception:
120.                 pass
121.     for story_id in all_story_ids:
122.         story_dir = details / f"payload_{story_id}"
123.         if not story_dir.is_dir():
124.             errs.append(f"missing detail dir: payload_{story_id}")
125.             continue
126.         for lvl in ("easy", "middle"):
127.             p = story_dir / f"{lvl}.json"
128.             if not p.is_file():
129.                 errs.append(f"missing detail: {story_id}/{lvl}.json")
130.                 continue
131.             try:
132.                 d = json.loads(p.read_text())
133.                 if not (d.get("summary") and len((d.get("summary") or "").split()) >= 50):
134.                     errs.append(f"{story_id}/{lvl}: summary missing or <50 words")
135.                 for field, min_n in DETAIL_MIN:
136.                     if len(d.get(field) or []) < min_n:
137.                         errs.append(
138.                             f"{story_id}/{lvl}: {field} has "
139.                             f"{len(d.get(field) or [])} (need ≥{min_n})"
140.                         )
141.             except Exception as e:  # noqa: BLE001
142.                 errs.append(f"{story_id}/{lvl}: parse error {e}")
143. 
144.     # Per-story images (same image used across easy/middle for a story)
145.     images_dir = WEB / "article_images"
146.     needed_images: set[str] = set()
147.     for cat in CATS:
148.         # Pull image_urls from today's listings — whichever level works
149.         for lvl in ("middle", "easy"):
150.             p = payloads / f"articles_{cat}_{lvl}.json"
151.             if not p.is_file():
152.                 continue
153.             try:
154.                 doc = json.loads(p.read_text())
155.                 for a in doc.get("articles") or []:
156.                     url = a.get("image_url") or ""
157.                     if url:
158.                         needed_images.add(Path(url).name)
159.                 break
160.             except Exception:
161.                 continue
162.     for name in needed_images:
163.         if not (images_dir / name).is_file():
164.             errs.append(f"missing image: article_images/{name}")
165. 
166.     if errs:
167.         log.error("Bundle validation FAILED — refusing to pack/upload:")
168.         for e in errs:
169.             log.error("  · %s", e)
170.         raise SystemExit(1)
171.     log.info("Bundle validation OK: 9 listings · 18 details · %d images",
172.              len(needed_images))
173. 
174. 
175. def build_zip() -> bytes:
176.     buf = BytesIO()
177.     files = collect_files()
178.     with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
179.         for p, arc in files:
180.             zf.write(p, arcname=arc)
181.     log.info("Packed %d files (%d bytes)", len(files), buf.tell())
182.     return buf.getvalue()
183. 
184. 
185. def build_manifest(today: str, body: bytes) -> dict:
186.     """Summarize what this zip contains — version + content hash + story IDs.
187.     Consumers can compare manifest sha256 without downloading the zip."""
188.     stories: list[dict] = []
189.     for cat in CATS:
190.         p = WEB / "payloads" / f"articles_{cat}_middle.json"
191.         if not p.is_file():
192.             continue
193.         try:
194.             for a in (json.loads(p.read_text()).get("articles") or []):
195.                 stories.append({
196.                     "id": a.get("id"),
197.                     "category": a.get("category"),
198.                     "title": a.get("title"),
199.                     "mined_at": a.get("mined_at"),
200.                     "source": a.get("source"),
201.                     "source_published_at": a.get("source_published_at"),
202.                 })
203.         except Exception:
204.             pass
205.     return {
206.         "version": today,
207.         "packed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
208.         "git_sha": os.environ.get("GITHUB_SHA") or "",
209.         "zip_bytes": len(body),
210.         "zip_sha256": hashlib.sha256(body).hexdigest(),
211.         "story_count": len(stories),
212.         "stories": stories,
213.     }
214. 
215. 
216. DATED_ZIP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.zip$")
217. DATED_MANIFEST_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-manifest\.json$")
218. DATED_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
219. 
220. 
221. def upload_dated_flat_files(sb, date_str: str, bundle: bytes | None = None) -> int:
222.     """Upload each file under the website bundle to `<date>/<relpath>` in the
223.     bucket so the UI can fetch past days' content directly (no zip parsing
224.     in the browser). `bundle` is an optional zip body — if given, files are
225.     extracted from it; otherwise read from local disk. Returns file count."""
226.     uploaded = 0
227.     if bundle is not None:
228.         zf = zipfile.ZipFile(BytesIO(bundle))
229.         members = [n for n in zf.namelist()
230.                    if n.endswith(".json") or n.endswith(".webp")]
231.         for name in members:
232.             body = zf.read(name)
233.             ctype = "application/json" if name.endswith(".json") else "image/webp"
234.             sb.storage.from_(BUCKET).upload(
235.                 path=f"{date_str}/{name}",
236.                 file=body,
237.                 file_options={"content-type": ctype, "upsert": "true"},
238.             )
239.             uploaded += 1
240.     else:
241.         for p, arc in collect_files():
242.             if not (arc.endswith(".json") or arc.endswith(".webp")):
243.                 continue  # skip HTML/JSX shell from dated flat copy
244.             ctype = "application/json" if arc.endswith(".json") else "image/webp"
245.             sb.storage.from_(BUCKET).upload(
246.                 path=f"{date_str}/{arc}",
247.                 file=p.read_bytes(),
248.                 file_options={"content-type": ctype, "upsert": "true"},
249.             )
250.             uploaded += 1
251.     log.info("dated-flat: uploaded %d files under %s/", uploaded, date_str)
252.     return uploaded
253. 
254. 
255. def update_archive_index(sb, dates: list[str]) -> None:
256.     """Merge `dates` into `archive-index.json` (descending, deduped, cap 30)."""
257.     try:
258.         body = sb.storage.from_(BUCKET).download("archive-index.json")
259.         idx = json.loads(body.decode() if isinstance(body, bytes) else body)
260.     except Exception:
261.         idx = {"dates": []}
262.     existing = set(idx.get("dates") or [])
263.     existing.update(dates)
264.     all_dates = sorted(existing, reverse=True)[:RETENTION_DAYS]
265.     idx = {"dates": all_dates,
266.            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
267.     sb.storage.from_(BUCKET).upload(
268.         path="archive-index.json",
269.         file=json.dumps(idx, ensure_ascii=False, indent=2).encode(),
270.         file_options={"content-type": "application/json", "upsert": "true"},
271.     )
272.     log.info("archive-index updated: %d dates (newest=%s)",
273.              len(all_dates), all_dates[0] if all_dates else "-")
274. 
275. 
276. def backfill_missing_archive_dirs(sb, current_index: list[str]) -> list[str]:
277.     """For any YYYY-MM-DD.zip in the bucket whose date isn't in the archive
278.     index AND doesn't yet have its flat dir, extract the zip and upload
279.     flat files. Returns list of backfilled dates."""
280.     current_set = set(current_index)
281.     objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
282.     candidates = []
283.     for o in objs or []:
284.         m = DATED_ZIP_RE.match(o.get("name") or "")
285.         if m and m.group(1) not in current_set:
286.             candidates.append(m.group(1))
287.     backfilled: list[str] = []
288.     for d in sorted(candidates):
289.         try:
290.             body = sb.storage.from_(BUCKET).download(f"{d}.zip")
291.             body = bytes(body) if not isinstance(body, bytes) else body
292.             upload_dated_flat_files(sb, d, bundle=body)
293.             backfilled.append(d)
294.         except Exception as e:  # noqa: BLE001
295.             log.warning("backfill %s failed: %s", d, e)
296.     return backfilled
297. 
298. 
299. def cleanup_retention(sb, keep_days: int) -> None:
300.     """Delete dated archives older than `keep_days`. Keeps `latest.*` always.
301.     Also removes all files under `<date>/` prefix for expired dates."""
302.     from datetime import date, timedelta
303.     cutoff = date.today() - timedelta(days=keep_days)
304.     expired: set[str] = set()
305.     objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
306.     to_delete: list[str] = []
307.     for o in objs or []:
308.         name = o.get("name") or ""
309.         for rx in (DATED_ZIP_RE, DATED_MANIFEST_RE, DATED_DIR_RE):
310.             m = rx.match(name)
311.             if not m:
312.                 continue
313.             try:
314.                 day = datetime.strptime(m.group(1), "%Y-%m-%d").date()
315.             except ValueError:
316.                 continue
317.             if day < cutoff:
318.                 if rx is DATED_DIR_RE:
319.                     expired.add(name)
320.                 else:
321.                     to_delete.append(name)
322.     # For each expired dir, list its files + delete them
323.     for d in expired:
324.         try:
325.             subs = sb.storage.from_(BUCKET).list(d, {"limit": 1000})
326.             for s in subs or []:
327.                 to_delete.append(f"{d}/{s.get('name')}")
328.         except Exception as e:  # noqa: BLE001
329.             log.warning("retention: listing %s/ failed: %s", d, e)
330.     if not to_delete:
331.         log.info("retention: 0 old files (keep %d days)", keep_days)
332.         return
333.     # Supabase remove() takes a list of paths.
334.     sb.storage.from_(BUCKET).remove(to_delete)
335.     log.info("retention: deleted %d files older than %s",
336.              len(to_delete), cutoff.isoformat())
337. 
338. 
339. def local_freshest_mined_at() -> str | None:
340.     """ISO-8601 of the most recent mined_at across all today's listings."""
341.     stamps: list[str] = []
342.     for cat in CATS:
343.         p = WEB / "payloads" / f"articles_{cat}_middle.json"
344.         if not p.is_file():
345.             continue
346.         try:
347.             for a in json.loads(p.read_text()).get("articles") or []:
348.                 if a.get("mined_at"):
349.                     stamps.append(a["mined_at"])
350.         except Exception:
351.             continue
352.     return max(stamps) if stamps else None
353. 
354. 
355. def check_not_overwriting_newer(sb) -> None:
356.     """Refuse to upload if the bucket already has a manifest whose packed_at
357.     (or freshest story mined_at) is newer than our local content. Prevents a
358.     local `pack_and_upload` from silently replacing CI-generated output."""
359.     try:
360.         body = sb.storage.from_(BUCKET).download("latest-manifest.json")
361.         remote = json.loads(body.decode() if isinstance(body, bytes) else body)
362.     except Exception:
363.         return  # nothing remote yet — safe to upload
364.     remote_stamps = [s.get("mined_at") for s in (remote.get("stories") or [])
365.                      if s.get("mined_at")]
366.     remote_freshest = max(remote_stamps) if remote_stamps else remote.get("packed_at")
367.     local_freshest = local_freshest_mined_at()
368.     if not (remote_freshest and local_freshest):
369.         return
370.     if local_freshest < remote_freshest:
371.         msg = (f"REFUSE: remote manifest is newer than local. "
372.                f"remote freshest={remote_freshest} · local freshest={local_freshest}. "
373.                "If you really want to overwrite, set ALLOW_STALE_UPLOAD=1.")
374.         if os.environ.get("ALLOW_STALE_UPLOAD") != "1":
375.             log.error(msg)
376.             raise SystemExit(1)
377.         log.warning("ALLOW_STALE_UPLOAD=1 set — proceeding despite: %s", msg)
378. 
379. 
380. def main() -> None:
381.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
382.     validate_bundle(today)
383.     body = build_zip()
384.     manifest = build_manifest(today, body)
385.     manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
386.     sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
387.     check_not_overwriting_newer(sb)
388. 
389.     # Write zip in two locations: dated archive (immutable history) + latest.
390.     for key in (f"{today}.zip", "latest.zip"):
391.         sb.storage.from_(BUCKET).upload(
392.             path=key,
393.             file=body,
394.             file_options={"content-type": "application/zip", "upsert": "true"},
395.         )
396.         log.info("uploaded %s", key)
397. 
398.     # Same for the manifest — dated archive + latest pointer.
399.     for key in (f"{today}-manifest.json", "latest-manifest.json"):
400.         sb.storage.from_(BUCKET).upload(
401.             path=key,
402.             file=manifest_bytes,
403.             file_options={"content-type": "application/json", "upsert": "true"},
404.         )
405.         log.info("uploaded %s", key)
406. 
407.     log.info("manifest: version=%s · zip_bytes=%d · zip_sha256=%s · stories=%d",
408.              manifest["version"], manifest["zip_bytes"],
409.              manifest["zip_sha256"][:12], manifest["story_count"])
410. 
411.     # Flat per-day files — the UI fetches these when user picks a past date.
412.     try:
413.         upload_dated_flat_files(sb, today)
414.     except Exception as e:  # noqa: BLE001
415.         log.warning("dated-flat upload failed (non-fatal): %s", e)
416. 
417.     # Read existing archive-index, backfill any dated zip that doesn't yet
418.     # have a flat dir, then update archive-index with both backfilled +
419.     # today's date.
420.     try:
421.         body = sb.storage.from_(BUCKET).download("archive-index.json")
422.         existing_idx = json.loads(body.decode() if isinstance(body, bytes) else body)
423.         existing_dates = existing_idx.get("dates") or []
424.     except Exception:
425.         existing_dates = []
426.     try:
427.         backfilled = backfill_missing_archive_dirs(sb, existing_dates)
428.         if backfilled:
429.             log.info("archive backfill: %s", backfilled)
430.         update_archive_index(sb, [today] + backfilled)
431.     except Exception as e:  # noqa: BLE001
432.         log.warning("archive-index update failed (non-fatal): %s", e)
433. 
434.     # Retention sweep: delete dated archives older than RETENTION_DAYS.
435.     try:
436.         cleanup_retention(sb, RETENTION_DAYS)
437.     except Exception as e:  # noqa: BLE001
438.         log.warning("retention sweep failed (non-fatal): %s", e)
439. 
440.     pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
441.     log.info("public URL: %s", pub)
442. 
443. 
444. if __name__ == "__main__":
445.     main()
446.
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py.**

/Users/jiong/myprojects/news-v2/pipeline/rewrite_from_db.py (lines 1-220)

<details>
<summary>220 lines</summary>

```
1. """Resume pipeline from DB state — optionally single-category for testing.
2. 
3. Given today's redesign_stories already picked + images already in Storage,
4. this regenerates body + detail payload without re-doing Phase A/B.
5. 
6. Steps (per category):
7.   1. Query redesign_stories for today → source URLs, image paths, story metadata
8.   2. Re-fetch each source URL + extract body via cleaner
9.   3. Tri-variant rewrite (1 call per category)
10.   4. Detail enrich (1 call per category)
11.   5. Emit v1-shape payload files
12. 
13. Run all 3 categories:
14.   python -m pipeline.rewrite_from_db
15. 
16. Run one category only (for testing):
17.   python -m pipeline.rewrite_from_db News
18.   python -m pipeline.rewrite_from_db Science
19.   python -m pipeline.rewrite_from_db Fun
20. """
21. from __future__ import annotations
22. 
23. import json
24. import logging
25. import os
26. from collections import defaultdict
27. from datetime import datetime, timezone
28. from pathlib import Path
29. 
30. import requests
31. from supabase import create_client
32. 
33. from .cleaner import extract_article_from_html
34. from .full_round import card_summary
35. from .news_rss_core import detail_enrich, tri_variant_rewrite
36. 
37. logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
38. log = logging.getLogger("resume")
39. 
40. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
41. for _line in (_envp.open() if _envp.exists() else []):
42.     if "=" in _line and not _line.startswith("#"):
43.         _k, _v = _line.strip().split("=", 1)
44.         os.environ[_k] = _v
45. 
46. HEADERS = {
47.     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
48.                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
49.     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
50. }
51. 
52. WEBSITE_DIR = Path("/Users/jiong/myprojects/news-v2/website")
53. 
54. 
55. def fetch_body(url: str) -> tuple[str, list[str]]:
56.     try:
57.         r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
58.         if r.status_code >= 400:
59.             return "", []
60.         ex = extract_article_from_html(url, r.text)
61.         return ex.get("cleaned_body") or "", ex.get("paragraphs") or []
62.     except Exception as e:
63.         log.warning("fetch failed %s: %s", url, e)
64.         return "", []
65. 
66. 
67. def main() -> None:
68.     import sys
69.     only_cat = sys.argv[1] if len(sys.argv) > 1 else None
70. 
71.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
72.     sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
73.     q = sb.table("redesign_stories").select("*").eq("published_date", today)
74.     if only_cat:
75.         q = q.eq("category", only_cat)
76.     res = q.order("category").order("story_slot").execute()
77.     stories = res.data
78.     log.info("Fetched %d stories from DB for %s%s", len(stories), today,
79.              f" (category={only_cat})" if only_cat else "")
80. 
81.     if not stories:
82.         log.error("No stories in DB for today — aborting")
83.         return
84. 
85.     # Group by category
86.     by_cat: dict[str, list[dict]] = defaultdict(list)
87.     for s in stories:
88.         by_cat[s["category"]].append(s)
89. 
90.     # Re-fetch bodies for each story
91.     log.info("=== REFETCH BODIES ===")
92.     for cat, group in by_cat.items():
93.         for s in group:
94.             body, paras = fetch_body(s["source_url"])
95.             s["_body"] = body
96.             s["_paragraphs"] = paras
97.             log.info("  [%s #%d] %dw · %s", cat, s["story_slot"], len(body.split()),
98.                      s["source_title"][:50] if s.get("source_title") else "")
99. 
100.     # Ensure referenced images exist on local disk (CI may have produced them
101.     # without syncing to this workstation). Pull any missing ones from the
102.     # redesign-article-images bucket — dated subfolder first, then flat root.
103.     log.info("=== SYNC IMAGES FROM SUPABASE (missing-only) ===")
104.     images_dir = WEBSITE_DIR / "article_images"
105.     images_dir.mkdir(parents=True, exist_ok=True)
106.     sb_base = os.environ["SUPABASE_URL"].rstrip("/")
107.     for cat, group in by_cat.items():
108.         for s in group:
109.             local = (s.get("primary_image_local") or "").strip()
110.             if not local:
111.                 continue
112.             fname = Path(local).name
113.             dest = images_dir / fname
114.             if dest.is_file():
115.                 continue
116.             for subpath in (f"2026-04-24/{fname}", today + "/" + fname, fname):
117.                 url = f"{sb_base}/storage/v1/object/public/redesign-article-images/{subpath}"
118.                 try:
119.                     r = requests.get(url, timeout=15)
120.                     if r.status_code == 200 and len(r.content) > 1000:
121.                         dest.write_bytes(r.content)
122.                         log.info("  pulled %s (%d bytes)", fname, len(r.content))
123.                         break
124.                 except Exception as e:
125.                     log.warning("  image fetch %s: %s", url, e)
126.             else:
127.                 log.warning("  MISSING image %s — live site will 404 until re-run", fname)
128. 
129.     # Build rewrite input shape
130.     log.info("=== REWRITE + ENRICH (2 calls per category) ===")
131.     details_dir = WEBSITE_DIR / "article_payloads"
132.     payloads_dir = WEBSITE_DIR / "payloads"
133.     details_dir.mkdir(parents=True, exist_ok=True)
134.     payloads_dir.mkdir(parents=True, exist_ok=True)
135. 
136.     per_cat_listings: dict[str, dict[str, list]] = {}
137. 
138.     for cat, group in by_cat.items():
139.         # Build articles_with_ids for tri_variant_rewrite: [(slot, art_dict)]
140.         arts = []
141.         for i, s in enumerate(group):
142.             art = {
143.                 "title": s.get("source_title") or "",
144.                 "link": s.get("source_url") or "",
145.                 "published": "",
146.                 "body": s.get("_body") or "",
147.             }
148.             arts.append((i, art))
149.         if not arts:
150.             continue
151.         log.info("  [%s] %d stories", cat, len(arts))
152. 
153.         rewrite_res = tri_variant_rewrite(arts)
154.         enrich_res = detail_enrich(rewrite_res)
155.         variants = {a["source_id"]: a for a in rewrite_res.get("articles") or []}
156.         details = enrich_res.get("details") or {}
157.         log.info("    rewrite=%d variants · detail=%d slots", len(variants), len(details))
158. 
159.         # Emit listings + details
160.         per_level: dict[str, list] = {"easy": [], "middle": [], "cn": []}
161.         for i, s in enumerate(group):
162.             var = variants.get(i) or {}
163.             easy = var.get("easy_en") or {}
164.             middle = var.get("middle_en") or {}
165.             zh = var.get("zh") or {}
166.             story_id = s.get("payload_story_id") or f"{today}-{cat.lower()}-{s['story_slot']}"
167.             img_local = s.get("primary_image_local") or ""
168.             img_url = f"/{img_local}" if img_local else ""
169. 
170.             # Preserve the original mining timestamp — DB has it as created_at.
171.             mined_at = s.get("created_at") or datetime.now(timezone.utc).isoformat()
172.             source_pub = s.get("source_published_at") or ""
173.             common_listing = {
174.                 "id": story_id,
175.                 "source": s.get("source_name", ""),
176.                 "time_ago": "",
177.                 "mined_at": mined_at,
178.                 "source_published_at": source_pub,
179.                 "image_url": img_url,
180.                 "category": cat,
181.             }
182.             per_level["easy"].append({**common_listing,
183.                 "title": easy.get("headline") or s.get("source_title") or "",
184.                 "summary": card_summary(easy),
185.             })
186.             per_level["middle"].append({**common_listing,
187.                 "title": middle.get("headline") or s.get("source_title") or "",
188.                 "summary": card_summary(middle),
189.             })
190.             per_level["cn"].append({**common_listing,
191.                 "title": zh.get("headline") or "",
192.                 "summary": zh.get("summary") or "",
193.             })
194. 
195.             # Per-story detail files (easy + middle; no cn detail)
196.             story_dir = details_dir / f"payload_{story_id}"
197.             story_dir.mkdir(parents=True, exist_ok=True)
198.             for lvl_key, var_obj in (("easy", easy), ("middle", middle)):
199.                 slot_key = f"{i}_{lvl_key}"
200.                 det = details.get(slot_key) or {}
201.                 bg = det.get("background_read") or []
202.                 if isinstance(bg, str):
203.                     bg = [bg]
204.                 detail = {
205.                     "title": var_obj.get("headline") or s.get("source_title") or "",
206.                     "summary": var_obj.get("body") or "",
207.                     "why_it_matters": det.get("why_it_matters", ""),
208.                     "image_url": img_url,
209.                     "keywords": det.get("keywords") or [],
210.                     "questions": det.get("questions") or [],
211.                     "background_read": bg,
212.                     "Article_Structure": det.get("Article_Structure") or [],
213.                     "perspectives": det.get("perspectives") or [],
214.                     "mined_at": mined_at,
215.                     "source_published_at": source_pub,
216.                     "source_name": s.get("source_name", ""),
217.                     "source_url": s.get("source_url", ""),
218.                 }
219.                 (story_dir / f"{lvl_key}.json").write_text(
220.                     json.dumps(detail, ensure_ascii=False, indent=2)
```

</details>


---

<sub>⏱️ 3m 10s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/config.py.**

/Users/jiong/myprojects/news-v2/pipeline/config.py (lines 1-220)

<details>
<summary>217 lines</summary>

```
1. """Configuration constants for KidsNews v2 pipeline (Steps 1-3)."""
2. from __future__ import annotations
3. 
4. # ---------------------------------------------------------------------------
5. # Query rotation tables
6. # ---------------------------------------------------------------------------
7. 
8. NEWS_QUERY = "top 5 hottest news today"
9. NEWS_FALLBACK_QUERY = "latest kid-safe news stories"
10. NEWS_TOPIC = "Current events"
11. 
12. # News 3-lane redesign (v2-curator)
13. NEWS_CURATOR_QUERY = "top news stories today"
14. NEWS_TIER1_DOMAINS = ["npr.org", "reuters.com"]
15. NEWS_TIER2_DOMAINS = ["apnews.com", "bbc.com", "theguardian.com"]
16. NEWS_LANE_MAX_RESULTS = 5
17. 
18. # weekday() → (topic_label, tavily_query)
19. SCIENCE_ROTATION: dict[int, tuple[str, str]] = {
20.     0: ("AI / auto",                        "mind blowing AI robots automation news this week for kids"),
21.     1: ("Biology / Medicine / Health",      "mind blowing biology medicine health news this week for kids"),
22.     2: ("Space / Astronomy",                "mind blowing space astronomy discoveries news this week for kids"),
23.     3: ("Chemistry / Physics",              "mind blowing chemistry physics experiments news this week for kids"),
24.     4: ("Environment / Climate",            "mind blowing environment climate nature news this week for kids"),
25.     5: ("Technology / Engineering",         "mind blowing technology engineering invention news this week for kids"),
26.     6: ("Nature / Geometry",                "mind blowing nature geometry patterns news this week for kids"),
27. }
28. 
29. FUN_ROTATION: dict[int, tuple[str, str]] = {
30.     0: ("Music", "kids music news concerts instruments this week"),
31.     1: ("Swimming / Water sports", "kids swimming water sports news this week"),
32.     2: ("Movies / TV", "kids movies tv shows news this week"),
33.     3: ("Cool inventions / kid inventors / new toys",
34.         "best new kids toys and inventions launching this week"),
35.     4: ("Arts / Crafts", "kids arts crafts creativity news this week"),
36.     5: ("Animals / Famous person / History", "kids animals famous people history news this week"),
37.     6: ("Video games / Esports", "kids video games esports news this week"),
38. }
39. 
40. # ---------------------------------------------------------------------------
41. # RSS feeds
42. # ---------------------------------------------------------------------------
43. 
44. RSS_FEEDS: dict[str, dict] = {
45.     "News": {
46.         "url": "https://www.pbs.org/newshour/feeds/rss/headlines",
47.         "source_name": "PBS NewsHour",
48.         "target": 3,
49.     },
50.     "Science": {
51.         "url": "https://www.sciencedaily.com/rss/all.xml",
52.         "source_name": "Science Daily",
53.         "target": 3,
54.     },
55.     "Fun": {
56.         "url": "https://feeds.bbci.co.uk/sport/tennis/rss.xml",
57.         "source_name": "BBC Tennis",
58.         "target": 2,
59.     },
60. }
61. 
62. # ---------------------------------------------------------------------------
63. # Tavily tuning
64. # ---------------------------------------------------------------------------
65. 
66. TAVILY_TARGET = 3  # per-category fallback
67. # Per-category Tavily discovery targets (News bumped to 5 for wider funnel)
68. TAVILY_TARGETS: dict[str, int] = {"News": 5, "Science": 3, "Fun": 3}
69. # Per-category RSS discovery targets (News bumped to 5)
70. RSS_TARGETS: dict[str, int] = {"News": 5, "Science": 3, "Fun": 2}
71. TAVILY_MAX_RESULTS = 15  # ask for lots of extras; URL-shape filter is strict
72. TAVILY_ENDPOINT = "https://api.tavily.com/search"
73. TAVILY_EXTRACT_ENDPOINT = "https://api.tavily.com/extract"
74. TAVILY_EXTRACT_TIMEOUT = 30
75. 
76. # ---------------------------------------------------------------------------
77. # Shopping / deals filter (Fix 3)
78. # ---------------------------------------------------------------------------
79. 
80. # Hosts devoted primarily to deals / shopping listicles.
81. SHOPPING_HOSTS = (
82.     "bgr.com",
83.     "rochesterfirst.com",
84.     "slickdeals.net",
85.     "dealnews.com",
86.     "bestproducts.com",
87. )
88. 
89. # URL path fragments that signal deals/shopping sections of mainstream sites.
90. SHOPPING_PATH_MARKERS = (
91.     "/best-deals",
92.     "/select/shopping",
93.     "/shopping/",
94.     "/deals/",
95.     "/top-deals",
96.     "/gift-guide",
97.     "/buying-guide",
98. )
99. 
100. # ---------------------------------------------------------------------------
101. # Image filter
102. # ---------------------------------------------------------------------------
103. 
104. IMAGE_URL_BLACKLIST = (
105.     "logo", "icon", "avatar", "tracking", "1x1", "pixel", "spacer",
106.     # bot/crawler proxy URLs that return HTML not image bytes
107.     "crawler", "google_widget",
108. )
109. IMAGE_EXT_BLACKLIST = (".svg", ".gif")
110. IMAGE_MIN_BYTES = 20_000
111. IMAGE_HEAD_TIMEOUT = 3
112. 
113. # ---------------------------------------------------------------------------
114. # Vetter thresholds (Stage 1 on title + snippet)
115. # ---------------------------------------------------------------------------
116. 
117. VET_SAFE_MAX = 4       # 0-4 SAFE
118. VET_CAUTION_MAX = 12   # 5-12 CAUTION
119. # 13-40 REJECT
120. 
121. DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
122. DEEPSEEK_MODEL = "deepseek-chat"
123. DEEPSEEK_TEMPERATURE = 0.1
124. DEEPSEEK_MAX_TOKENS = 600
125. 
126. VETTER_SYSTEM_PROMPT = """You are a content reviewer for a kids news site (ages 8-13, grades 3-8).
127. You are judging based ONLY on the title and a short snippet.
128. 
129. PART A — SAFETY. Rate each 0-5 (0=none, 5=severe):
130. violence, sexual, substance, language, fear, adult_themes, distress, bias.
131. Compute safety_total = sum of these (0-40).
132. safety_verdict:
133.   0-4  -> SAFE
134.   5-12 -> CAUTION (publishable after rewrite softening)
135.   13+  -> REJECT (block)
136. 
137. PART B — INTEREST. A safe story still needs to be worth reading. Rate each 0-5:
138. - importance: how globally significant (0=trivial, 5=major historic event)
139. - fun_factor: how funny, delightful, surprising (0=dry, 5=hilarious/amazing)
140. - kid_appeal: how likely an 8-13 year old would WANT to read this (0=boring to a kid, 5=kid magnet)
141. Compute interest_peak = max(importance, fun_factor, kid_appeal).
142. interest_verdict:
143.   peak >= 3 -> ENGAGING
144.   peak == 2 -> MEH
145.   peak <= 1 -> BORING
146. 
147. Rule: a story can pass with EITHER high importance OR high fun_factor OR high kid_appeal — it does not need all three.
148. 
149. Return ONLY valid JSON (no markdown fences):
150. {
151.   "safety_scores": {"violence":0,"sexual":0,"substance":0,"language":0,"fear":0,"adult_themes":0,"distress":0,"bias":0},
152.   "safety_total": 0,
153.   "safety_verdict": "SAFE|CAUTION|REJECT",
154.   "interest_scores": {"importance":0,"fun_factor":0,"kid_appeal":0},
155.   "interest_peak": 0,
156.   "interest_verdict": "ENGAGING|MEH|BORING",
157.   "flags": ["..."],
158.   "rewrite_notes": "..."
159. }"""
160. 
161. # Interest thresholds already encoded in the prompt; keep exposed:
162. INTEREST_PEAK_MIN_KEEP = 2  # drop candidates with interest_peak < this (i.e., BORING gets dropped)
163. 
164. # ---------------------------------------------------------------------------
165. # Jina Reader
166. # ---------------------------------------------------------------------------
167. 
168. JINA_ENDPOINT = "https://r.jina.ai/"
169. JINA_TIMEOUT = 30
170. JINA_MIN_CONTENT_LEN = 1200  # reuse Tavily raw_content if at least this many chars
171. 
172. # ---------------------------------------------------------------------------
173. # News-lane content strategy
174. # ---------------------------------------------------------------------------
175. 
176. # If Tavily raw_content has >= this many words, treat it as sufficient and
177. # skip the Jina fallback. Applied when the category is in SKIP_JINA_CATEGORIES.
178. TAVILY_CONTENT_MIN_WORDS = 450
179. 
180. # Categories for which we do NOT fall back to Jina. News articles are often
181. # video-first and produce thin text; we'd rather drop than pay for Jina.
182. SKIP_JINA_CATEGORIES = {"News"}
183. 
184. # ---------------------------------------------------------------------------
185. # Post-vet selection
186. # ---------------------------------------------------------------------------
187. 
188. # Pick the top N (by vetted_rank) among SAFE/CAUTION per category.
189. FINAL_PUBLISH_COUNT = 3
190. 
191. # Hosts for which we trust og:image enough to skip the HEAD check.
192. TRUSTED_IMAGE_HOSTS = (
193.     "ichef.bbci.co.uk",
194.     "bbci.co.uk",
195.     "pbs.org",
196.     "pbs.twimg.com",
197.     "static.pbs.org",
198.     "image.pbs.org",
199.     "assets.sciencedaily.com",
200.     "cdn.sciencedaily.com",
201.     "sciencedaily.com",
202. )
203. 
204. # ---------------------------------------------------------------------------
205. # Output paths
206. # ---------------------------------------------------------------------------
207. 
208. import os
209. from pathlib import Path
210. 
211. PROJECT_ROOT = Path(__file__).resolve().parent.parent
212. WEBSITE_DIR = PROJECT_ROOT / "website"
213. TEST_OUTPUT_DIR = WEBSITE_DIR / "test_output"
214. 
215. # Categories to process (in order)
216. CATEGORIES = ["News", "Science", "Fun"]
217.
```

</details>


---

<sub>⏱️ 3m 17s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 560-780)

<details>
<summary>221 lines</summary>

````
560.     "0_easy":   {"keywords":[...], "questions":[...], "background_read":[...], "Article_Structure":[...], "why_it_matters":"...", "perspectives":[...]},
561.     "0_middle": {...},
562.     "1_easy":   {...},
563.     "1_middle": {...},
564.     "2_easy":   {...},
565.     "2_middle": {...}
566.   }
567. }"""
568. 
569. 
570. def detail_enrich_input(rewrite_result: dict) -> str:
571.     """Build the user message for detail enrichment from the tri-variant rewrite result."""
572.     lines = ["3 articles below. For each, generate detail fields for easy and middle levels.", ""]
573.     for i, art in enumerate(rewrite_result.get("articles") or []):
574.         easy = art.get("easy_en") or {}
575.         middle = art.get("middle_en") or {}
576.         lines.append(f"=== Article [id: {i}] ===")
577.         lines.append(f"easy_en headline: {easy.get('headline','')}")
578.         lines.append(f"easy_en body ({len((easy.get('body') or '').split())} words):")
579.         lines.append((easy.get("body") or ""))
580.         lines.append("")
581.         lines.append(f"middle_en headline: {middle.get('headline','')}")
582.         lines.append(f"middle_en body ({len((middle.get('body') or '').split())} words):")
583.         lines.append((middle.get("body") or ""))
584.         lines.append("")
585.     lines.append("Return the JSON with the 6 slots keyed as 0_easy, 0_middle, 1_easy, 1_middle, 2_easy, 2_middle.")
586.     return "\n".join(lines)
587. 
588. 
589. KEYWORD_SUFFIX_RE = r"(?:s|es|ed|d|ing|ning|ned|ting|ted|er|ers|ion|ions|ensions|ensión|ly)?"
590. 
591. 
592. def keyword_in_body(term: str, body: str) -> bool:
593.     """Same suffix-aware match the UI uses — term or inflected form present?"""
594.     import re
595.     if not term or not body:
596.         return False
597.     escaped = re.escape(term)
598.     pattern = rf"\b{escaped}{KEYWORD_SUFFIX_RE}\b"
599.     return bool(re.search(pattern, body, flags=re.IGNORECASE))
600. 
601. 
602. def filter_keywords(details: dict, rewrite_result: dict) -> dict:
603.     """Drop keywords that don't appear in the corresponding body. Logs drops."""
604.     articles_by_id = {a["source_id"]: a for a in rewrite_result.get("articles") or []}
605.     for slot_key, det in details.items():
606.         kws = det.get("keywords") or []
607.         if not kws:
608.             continue
609.         try:
610.             aid_str, lvl = slot_key.rsplit("_", 1)
611.             aid = int(aid_str)
612.         except (ValueError, TypeError):
613.             continue
614.         art = articles_by_id.get(aid, {})
615.         variant = art.get(f"{lvl}_en" if lvl in ("easy", "middle") else lvl) or {}
616.         body = variant.get("body") or ""
617.         kept = []
618.         dropped = []
619.         for k in kws:
620.             if keyword_in_body(k.get("term", ""), body):
621.                 kept.append(k)
622.             else:
623.                 dropped.append(k.get("term"))
624.         det["keywords"] = kept
625.         if dropped:
626.             log.info("  [%s] dropped hallucinated keywords: %s", slot_key, dropped)
627.     return details
628. 
629. 
630. def deepseek_reasoner_call(system: str, user: str, max_tokens: int = 16000,
631.                            max_attempts: int = 3) -> dict:
632.     """Call deepseek-reasoner (thinking mode). Returns parsed JSON from final
633.     content. Retries on JSON parse failure (model occasionally drops a comma
634.     in large payloads) and on transient HTTP/network errors."""
635.     last_err: Exception | None = None
636.     for attempt in range(1, max_attempts + 1):
637.         try:
638.             r = requests.post(
639.                 DEEPSEEK_ENDPOINT,
640.                 json={
641.                     "model": "deepseek-reasoner",
642.                     "messages": [{"role": "system", "content": system},
643.                                  {"role": "user", "content": user}],
644.                     "max_tokens": max_tokens,
645.                 },
646.                 headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
647.                 timeout=300,
648.             )
649.             r.raise_for_status()
650.             content = r.json()["choices"][0]["message"]["content"]
651.             content = re.sub(r"^```json\s*", "", content.strip())
652.             content = re.sub(r"\s*```\s*$", "", content)
653.             return json.loads(content)
654.         except (json.JSONDecodeError, requests.HTTPError, requests.ConnectionError,
655.                 requests.Timeout) as e:
656.             last_err = e
657.             log.warning("reasoner attempt %d/%d failed: %s",
658.                         attempt, max_attempts, str(e)[:200])
659.             if attempt < max_attempts:
660.                 time.sleep(2 * attempt)  # 2s, 4s
661.     raise RuntimeError(f"deepseek_reasoner_call exhausted {max_attempts} attempts") from last_err
662. 
663. 
664. def _detail_enrich_input_single_level(rewrite_result: dict, level: str) -> str:
665.     """Build an input covering only easy OR only middle slots (3 slots total).
666.     Smaller payload → less chance of malformed JSON under reasoner load."""
667.     assert level in ("easy", "middle")
668.     lines = [f"3 articles below. For EACH, generate detail fields ONLY for the "
669.              f"{level} level.", ""]
670.     for i, art in enumerate(rewrite_result.get("articles") or []):
671.         v = art.get(f"{level}_en") or {}
672.         lines.append(f"=== Article [id: {i}] ===")
673.         lines.append(f"{level}_en headline: {v.get('headline','')}")
674.         lines.append(f"{level}_en body ({len((v.get('body') or '').split())} words):")
675.         lines.append((v.get("body") or ""))
676.         lines.append("")
677.     lines.append(f"Return JSON with 3 slots keyed as 0_{level}, 1_{level}, 2_{level}.")
678.     return "\n".join(lines)
679. 
680. 
681. def detail_enrich(rewrite_result: dict) -> dict:
682.     """Detail enrichment with two-stage fallback:
683.       1. Single 6-slot call (fast, cheaper).
684.       2. If that fails JSON parse even after retries, split into TWO 3-slot
685.          calls (easy-only + middle-only). Smaller prompts → higher chance of
686.          well-formed JSON per call, and if one half still fails the other is
687.          salvageable.
688.     Post-filter hallucinated keywords at the end."""
689.     try:
690.         res = deepseek_reasoner_call(DETAIL_ENRICH_PROMPT,
691.                                      detail_enrich_input(rewrite_result),
692.                                      max_tokens=16000)
693.         details = res.get("details") or {}
694.         # Accept even partial success here (all 6 slots expected; caller checks).
695.     except RuntimeError as e:
696.         log.warning("detail_enrich 6-slot call failed after retries (%s) — "
697.                     "falling back to split 3-slot batches", e)
698.         details = {}
699.         for level in ("easy", "middle"):
700.             try:
701.                 res = deepseek_reasoner_call(
702.                     DETAIL_ENRICH_PROMPT,
703.                     _detail_enrich_input_single_level(rewrite_result, level),
704.                     max_tokens=12000,
705.                 )
706.                 for k, v in (res.get("details") or {}).items():
707.                     details[k] = v
708.                 log.info("split-batch %s: %d slots OK", level,
709.                          len(res.get("details") or {}))
710.             except RuntimeError as e2:
711.                 log.error("split-batch %s failed: %s", level, e2)
712.                 # Continue — the other level may still succeed.
713. 
714.     filter_keywords(details, rewrite_result)
715.     return {"details": details}
716. 
717. 
718. # ---------------------------------------------------------------------------
719. # Cross-source duplicate check
720. # ---------------------------------------------------------------------------
721. 
722. DUP_CHECK_PROMPT = """You are checking a small set of kids news article briefs for
723. cross-source DUPLICATES.
724. 
725. A "duplicate" = two briefs covering the SAME news event (e.g. "Pope on Iran peace"
726. appears in both PBS and AJ). Different angles on the same event still count as
727. duplicates. Different stories that merely share a topic (both about science, etc.)
728. are NOT duplicates.
729. 
730. Input: N briefs. Each has an id, title, source, and a short excerpt.
731. 
732. Return ONLY valid JSON:
733. {
734.   "verdict": "OK" | "DUP_FOUND",
735.   "duplicate_pairs": [
736.     {"ids": [i, j], "reason": "why these two cover the same event"}
737.   ],
738.   "drop_suggestion": <id of the brief to drop if DUP_FOUND, else null>
739. }
740. 
741. If verdict is OK, duplicate_pairs should be [] and drop_suggestion null.
742. If DUP_FOUND, prefer to drop the one with lower priority source (if given) or
743. the less-engaging one. Only suggest dropping ONE brief even if multiple pairs exist
744. (we handle one substitution per cycle)."""
745. 
746. 
747. def dup_check_input(briefs: list[dict]) -> str:
748.     """briefs: [{id, title, source_name, source_priority, snippet_or_excerpt}]"""
749.     lines = ["Check the following briefs for cross-source duplicates:", ""]
750.     for b in briefs:
751.         lines.append(f"[id: {b['id']}] {b.get('title', '')}")
752.         lines.append(f"  source: {b.get('source_name', '')} (priority {b.get('source_priority', '?')})")
753.         lines.append(f"  excerpt: {(b.get('excerpt') or '')[:400]}")
754.         lines.append("")
755.     return "\n".join(lines)
756. 
757. 
758. def check_duplicates(briefs: list[dict]) -> dict:
759.     return deepseek_call(DUP_CHECK_PROMPT, dup_check_input(briefs),
760.                          max_tokens=500, temperature=0.1)
761. 
762. 
763. # ---------------------------------------------------------------------------
764. # Phase A — per-source mining (unified full+light)
765. # ---------------------------------------------------------------------------
766. 
767. MAX_PICK_BODY_WORDS = 5000   # reject picks with suspiciously long body (probably aggregate page)
768. 
769. 
770. def verify_article_content(art: dict) -> tuple[bool, str | None]:
771.     """Check body words + image quality. Returns (ok, reject_reason)."""
772.     wc = art.get("word_count", 0)
773.     if wc < MIN_PICK_BODY_WORDS:
774.         return False, f"body {wc}w < {MIN_PICK_BODY_WORDS}w"
775.     if wc > MAX_PICK_BODY_WORDS:
776.         return False, f"body {wc}w > {MAX_PICK_BODY_WORDS}w (suspect aggregate page)"
777.     if is_generic_social_image(art.get("og_image")):
778.         return False, f"generic social image: {art.get('og_image')}"
779.     if not art.get("og_image"):
780.         return False, "no og:image"
````

</details>


---

<sub>⏱️ 3m 17s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/home.jsx.**

/Users/jiong/myprojects/news-v2/website/home.jsx (lines 220-460)

<details>
<summary>241 lines</summary>

```
220.                       fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18,
221.                     }}>{i+1}</div>
222.                     <div style={{
223.                       width:52, height:52, borderRadius:12, flexShrink:0,
224.                       background:`url(${a.image}) center/cover, ${catColor}`,
225.                       border:`2px solid ${catColor}`,
226.                     }}/>
227.                     <button onClick={()=>onOpen(a.id)} style={{
228.                       flex:1, minWidth:0, background:'transparent', border:'none', textAlign:'left', cursor:'pointer', padding:0,
229.                     }}>
230.                       <div style={{fontWeight:800, fontSize:14, color:'#1b1230', lineHeight:1.25, marginBottom:4, display:'-webkit-box', WebkitBoxOrient:'vertical', WebkitLineClamp:2, overflow:'hidden'}}>
231.                         {a.title}
232.                       </div>
233.                       <div style={{display:'flex', gap:6, alignItems:'center', fontSize:11, color:'#6b5c80'}}>
234.                         <CatChip cat={a.category} small/>
235.                         <span>· {a.readMins} min</span>
236.                       </div>
237.                     </button>
238.                     {(() => {
239.                       const p = (progress.articleProgress||{})[a.id] || 0;
240.                       const done = progress.readToday.includes(a.id);
241.                       if (done) return <span style={{fontSize:22, color:'#17b3a6'}}>✓</span>;
242.                       if (p > 0) return <span style={{fontSize:11, fontWeight:800, color:'#f4a24c', background:'#fff4e0', padding:'3px 8px', borderRadius:999, border:'1.5px solid #f4a24c'}}>{p}%</span>;
243.                       return null;
244.                     })()}
245.                     {canSwap && (
246.                       <button onClick={()=>setSwapOpen(i)} title={`Pick a different ${a.category} story`} style={{
247.                         background:'transparent', color:'#6b5c80',
248.                         border:'2px solid #f0e8d8', borderRadius:10,
249.                         width:32, height:32, cursor:'pointer', fontSize:14, fontWeight:900,
250.                         display:'flex', alignItems:'center', justifyContent:'center',
251.                       }}>⇆</button>
252.                     )}
253.                   </div>
254.                   )}
255.                 </div>
256.               );
257.             })}
258.           </div>
259.         </div>
260.       </section>
261.       )}
262. 
263.       {/* ——————————— CATEGORY TABS ——————————— */}
264.       <section style={{maxWidth:1180, margin: isArchive ? '24px auto 0' : '32px auto 0', padding:'0 28px', position:'relative'}}>
265.         <div style={{display:'flex', gap:12, flexWrap:'wrap', alignItems:'center'}}>
266.           {CATEGORIES.map(c => (
267.             <CatTab key={c.id} label={c.label} emoji={c.emoji} color={c.color} bg={c.bg} active={cat===c.label} onClick={()=>setCat(c.label)} />
268.           ))}
269.           {!isArchive && (
270.             <button onClick={()=>setCalendarOpen(v=>!v)} style={{
271.               background: calendarOpen ? '#1b1230' : '#fff', color: calendarOpen ? '#ffc83d' : '#1b1230',
272.               border: calendarOpen ? '2px solid #1b1230' : '2px dashed #c9b99a',
273.               borderRadius:999, padding:'8px 16px', fontWeight:800, fontSize:13, cursor:'pointer',
274.               display:'inline-flex', alignItems:'center', gap:6, fontFamily:'Nunito, sans-serif',
275.             }}>📅 View old news</button>
276.           )}
277.           <div style={{flex:1}}/>
278.           <span style={{fontSize:13, color:'#7a6b8c', fontWeight:600}}>
279.             {isZh ? (<>Reading in <b style={{color:'#1b1230'}}>中文</b> · summary only</>) : (<>Showing stories at <b style={{color:'#1b1230'}}>{level}</b> level</>)}
280.           </span>
281.         </div>
282.         {calendarOpen && (
283.           <DatePopover onPick={(d)=>{setCalendarOpen(false); onOpenArchive(d);}} onClose={()=>setCalendarOpen(false)} />
284.         )}
285.       </section>
286. 
287.       {/* ——————————— ARTICLES GRID ——————————— */}
288.       <section style={{maxWidth:1180, margin:'20px auto 0', padding:'0 28px 60px'}}>
289.         {filtered.length === 0 ? (
290.           <div style={{textAlign:'center', padding:'40px 20px', color:'#9a8d7a', background:'#fff', borderRadius:16, border:'2px dashed #f0e8d8'}}>
291.             <div style={{fontSize:36, marginBottom:8}}>🌱</div>
292.             <div style={{fontWeight:800, color:'#1b1230', marginBottom:4}}>No stories here</div>
293.             <div style={{fontSize:13}}>Try a different level from your profile, or a different day.</div>
294.           </div>
295.         ) : filtered.length === 3 && !isArchive ? (
296.           /* Editorial layout: big feature on top (photo left, article right) + 2 companions below */
297.           <div style={{display:'flex', flexDirection:'column', gap:20}}>
298.             <ArticleCard article={filtered[0]} onOpen={()=>onOpen(filtered[0].id)} read={progress.readToday.includes(filtered[0].id)} pct={(progress.articleProgress||{})[filtered[0].id]} variant="feature" />
299.             <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
300.               <ArticleCard article={filtered[1]} onOpen={()=>onOpen(filtered[1].id)} read={progress.readToday.includes(filtered[1].id)} pct={(progress.articleProgress||{})[filtered[1].id]} variant="normal" />
301.               <ArticleCard article={filtered[2]} onOpen={()=>onOpen(filtered[2].id)} read={progress.readToday.includes(filtered[2].id)} pct={(progress.articleProgress||{})[filtered[2].id]} variant="normal" />
302.             </div>
303.           </div>
304.         ) : (
305.           <div style={{
306.             display:'grid',
307.             gridTemplateColumns:'repeat(auto-fill, minmax(280px, 1fr))',
308.             gap:20,
309.           }}>
310.             {filtered.map((a, i) => (
311.               <ArticleCard key={a.id} article={a} onOpen={()=>onOpen(a.id)} read={progress.readToday.includes(a.id)} pct={(progress.articleProgress||{})[a.id]} variant={i===0 && !isArchive ? 'feature' : 'normal'} />
312.             ))}
313.           </div>
314.         )}
315.       </section>
316. 
317.       {/* ——————————— FOOTER ——————————— */}
318.       <footer style={{textAlign:'center', padding:'28px 20px 40px', color:'#9a8d7a', fontSize:13}}>
319.         {(() => {
320.           // Use the freshest mined_at across all loaded articles as the "page
321.           // generated" timestamp. Displayed in the reader's local timezone.
322.           const ms = (ARTICLES || [])
323.             .map(a => a.minedAt ? new Date(a.minedAt).getTime() : 0)
324.             .filter(t => t > 0);
325.           if (!ms.length) return null;
326.           const d = new Date(Math.max(...ms));
327.           const when = d.toLocaleString(undefined, {
328.             year:'numeric', month:'short', day:'numeric',
329.             hour:'numeric', minute:'2-digit',
330.           });
331.           return (
332.             <div style={{marginBottom:6, fontSize:12, color:'#b0a490'}}>
333.               📅 Page generated · {when}
334.             </div>
335.           );
336.         })()}
337.         Made for curious kids · News Oh,Ye! 🎈
338.       </footer>
339.     </div>
340.   );
341. }
342. 
343. // ——————————— DATE POPOVER ———————————
344. // archiveDay is a "YYYY-MM-DD" string.
345. function archiveDayLabel(d) {
346.   if (!d) return '';
347.   const dt = new Date(d + 'T00:00:00');
348.   return dt.toLocaleDateString(undefined, { weekday:'long', month:'short', day:'numeric' });
349. }
350. 
351. function DatePopover({ onPick, onClose }) {
352.   // Fetch the list of archived days from Supabase. The newest entry is
353.   // today; we exclude it so the picker only offers past editions.
354.   const [index, setIndex] = useStateH({ dates: [] });
355.   useStateH && React.useEffect(() => {
356.     let cancelled = false;
357.     window.loadArchiveIndex().then(r => { if (!cancelled) setIndex(r); });
358.     return () => { cancelled = true; };
359.   }, []);
360.   const todayStr = new Date().toISOString().slice(0, 10);
361.   const pastDates = (index.dates || []).filter(d => d !== todayStr).slice(0, 14);
362. 
363.   return (
364.     <>
365.       <div onClick={onClose} style={{position:'fixed', inset:0, zIndex:40, background:'transparent'}}/>
366.       <div style={{
367.         position:'absolute', top:'100%', marginTop:10, left:28, zIndex:50,
368.         background:'#fff', borderRadius:18, border:'2px solid #1b1230',
369.         padding:16, boxShadow:'0 10px 0 rgba(27,18,48,0.12)', width:340,
370.       }}>
371.         <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230', marginBottom:4}}>📅 Pick a past day</div>
372.         <div style={{fontSize:12, color:'#6b5c80', fontWeight:600, marginBottom:12}}>
373.           {pastDates.length === 0
374.             ? "No past editions yet — check back tomorrow."
375.             : "Catch up on editions you missed."}
376.         </div>
377.         {pastDates.length > 0 && (
378.           <div style={{display:'grid', gridTemplateColumns:'repeat(7, 1fr)', gap:6}}>
379.             {pastDates.map(d => {
380.               const dt = new Date(d + 'T00:00:00');
381.               return (
382.                 <button key={d} onClick={()=>onPick(d)} style={{
383.                   padding:'10px 4px', border:'2px solid #f0e8d8',
384.                   background:'#fff9ef', borderRadius:12, cursor:'pointer',
385.                   fontFamily:'Nunito, sans-serif',
386.                 }}>
387.                   <div style={{fontSize:10, fontWeight:800, color:'#9a8d7a', textTransform:'uppercase'}}>{dt.toLocaleDateString(undefined,{weekday:'short'}).slice(0,3)}</div>
388.                   <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20, color:'#1b1230'}}>{dt.getDate()}</div>
389.                   <div style={{fontSize:9, color:'#9a8d7a', fontWeight:700}}>{dt.toLocaleDateString(undefined,{month:'short'})}</div>
390.                 </button>
391.               );
392.             })}
393.           </div>
394.         )}
395.       </div>
396.     </>
397.   );
398. }
399. 
400. // ——————————— HEADER ———————————
401. function Header({ level, setLevel, theme, tweaks, onOpenUserPanel, progress, recentOpen, setRecentOpen, onOpenArticle }) {
402.   theme = theme || { bg:'#fff9ef', chip:'#f0e8d8' };
403.   tweaks = tweaks || {};
404.   return (
405.     <header style={{
406.       background: theme.bg,
407.       borderBottom: `2px solid ${theme.chip}`,
408.       position:'sticky', top:0, zIndex:30, backdropFilter:'blur(6px)',
409.     }}>
410.       <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:16}}>
411.         <div style={{display:'flex', alignItems:'center', gap:10}}>
412.           <OhYeLogo size={44}/>
413.           <div style={{lineHeight:1}}>
414.             <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:22, color:'#1b1230', letterSpacing:'-0.01em'}}>
415.               News Oh<span style={{color:'#ff6b5b'}}>,</span>Ye<span style={{color:'#ff6b5b'}}>!</span>
416.             </div>
417.             <div style={{fontSize:11, color:'#9a8d7a', fontWeight:700, marginTop:2, letterSpacing:'.08em'}}>READ · THINK · LEARN</div>
418.           </div>
419.         </div>
420. 
421.         <div style={{flex:1}}/>
422. 
423.         {/* Streak pill → opens recent reads popover */}
424.         <div style={{position:'relative'}}>
425.           <button onClick={()=>setRecentOpen(v=>!v)} style={{
426.             display:'flex', alignItems:'center', gap:10, background:'#1b1230', color:'#fff',
427.             padding:'6px 14px 6px 6px', borderRadius:999, border:'none', cursor:'pointer',
428.             fontFamily:'Nunito, sans-serif',
429.           }}>
430.             <StreakRing minutes={MOCK_USER.minutesToday} goal={MOCK_USER.dailyGoal} streak={MOCK_USER.streak} size={40}/>
431.             <div style={{lineHeight:1.1, textAlign:'left'}}>
432.               <div style={{fontSize:11, opacity:.7, fontWeight:700}}>STREAK</div>
433.               <div style={{fontWeight:800, fontSize:14}}>{MOCK_USER.streak} days 🔥</div>
434.             </div>
435.             <span style={{fontSize:11, opacity:0.7, marginLeft:4}}>▾</span>
436.           </button>
437.           {recentOpen && (
438.             <RecentReadsPopover onClose={()=>setRecentOpen(false)} onOpenArticle={(id)=>{setRecentOpen(false); onOpenArticle(id);}} readIds={(progress&&progress.readToday)||[]}/>
439.           )}
440.         </div>
441. 
442.         {/* User button — opens the profile panel */}
443.         {window.UserButton && (
444.           <window.UserButton tweaks={tweaks} streak={MOCK_USER.streak} onClick={onOpenUserPanel}/>
445.         )}
446.       </div>
447.     </header>
448.   );
449. }
450. 
451. function _HeaderOldContentRemoved() { return null; }
452. 
453. // ——————————— RECENT READS POPOVER ———————————
454. function RecentReadsPopover({ onClose, onOpenArticle, readIds }) {
455.   // Take most recent 15 articles the user has read (from readIds, in order)
456.   const recent = [];
457.   const seen = new Set();
458.   for (let i = readIds.length - 1; i >= 0 && recent.length < 15; i--) {
459.     const id = readIds[i];
460.     if (seen.has(id)) continue;
```

</details>


---

<sub>⏱️ 3m 17s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/website/index.html.**

/Users/jiong/myprojects/news-v2/website/index.html (lines 90-310)

<details>
<summary>187 lines</summary>

```
90.   const [tweaks, setTweaks] = useState(() => {
91.     try {
92.       const saved = JSON.parse(localStorage.getItem('ohye_tweaks') || 'null');
93.       return saved ? { ...TWEAK_DEFAULTS, ...saved } : TWEAK_DEFAULTS;
94.     } catch { return TWEAK_DEFAULTS; }
95.   });
96.   const [userPanelOpen, setUserPanelOpen] = useState(false);
97. 
98.   useEffect(() => { localStorage.setItem('ohye_route', JSON.stringify(route)); }, [route]);
99.   useEffect(() => { localStorage.setItem('ohye_level', level); }, [level]);
100.   useEffect(() => { localStorage.setItem('ohye_cat', cat); }, [cat]);
101.   useEffect(() => {
102.     if (archiveDay) localStorage.setItem('ohye_archive_day', String(archiveDay));
103.     else localStorage.removeItem('ohye_archive_day');
104.     // Whenever archiveDay changes, re-load ARTICLES from the matching bundle
105.     // (today's local files, or a past day's Supabase prefix).
106.     if (typeof window.loadArchive === 'function') {
107.       window.loadArchive(archiveDay).then(() => {
108.         // Force a re-render by bumping a dummy state; route stays put.
109.         setRoute(r => ({ ...r }));
110.       });
111.     }
112.   }, [archiveDay]);
113.   useEffect(() => { localStorage.setItem('ohye_progress', JSON.stringify(progress)); }, [progress]);
114.   useEffect(() => { localStorage.setItem('ohye_tweaks', JSON.stringify(tweaks)); }, [tweaks]);
115. 
116.   // Edit-mode wiring
117.   useEffect(() => {
118.     const handler = (e) => {
119.       if (!e.data) return;
120.       if (e.data.type === '__activate_edit_mode') setUserPanelOpen(true);
121.       if (e.data.type === '__deactivate_edit_mode') setUserPanelOpen(false);
122.     };
123.     window.addEventListener('message', handler);
124.     // Announce AFTER listener
125.     try { window.parent.postMessage({ type:'__edit_mode_available' }, '*'); } catch {}
126.     return () => window.removeEventListener('message', handler);
127.   }, []);
128. 
129.   const updateTweak = (key, val) => {
130.     const edits = { [key]: val };
131.     setTweaks(t => ({...t, ...edits}));
132.     try { window.parent.postMessage({ type:'__edit_mode_set_keys', edits }, '*'); } catch {}
133.   };
134. 
135.   // Apply theme to root
136.   const themeVars = {
137.     sunny: { bg:'#fff9ef', accent:'#ffc83d', hero1:'#ffe2a8', hero2:'#ffc0a8', border:'#ffb98a', heroTextAccent:'#c14e2a', card:'#fff', chip:'#f0e8d8' },
138.     sky:   { bg:'#eef6ff', accent:'#5bb4ff', hero1:'#cfe6ff', hero2:'#bfd9ff', border:'#8ec2ff', heroTextAccent:'#1f6bbf', card:'#fff', chip:'#dce8f5' },
139.     candy: { bg:'#fff0f6', accent:'#ff6ba0', hero1:'#ffd0e2', hero2:'#e0cbff', border:'#ffa0c5', heroTextAccent:'#b73a79', card:'#fff', chip:'#f5dce8' },
140.     forest:{ bg:'#f3f8ec', accent:'#7cbf5a', hero1:'#d9ecc0', hero2:'#f2e1a6', border:'#a7d685', heroTextAccent:'#4a7a2a', card:'#fff', chip:'#e0e8cf' },
141.   };
142.   const theme = themeVars[tweaks.theme] || themeVars.sunny;
143. 
144.   useEffect(() => {
145.     document.body.style.background = theme.bg;
146.     const root = document.documentElement;
147.     root.style.setProperty('--theme-bg', theme.bg);
148.     root.style.setProperty('--theme-accent', theme.accent);
149.     root.style.setProperty('--theme-hero1', theme.hero1);
150.     root.style.setProperty('--theme-hero2', theme.hero2);
151.     root.style.setProperty('--theme-border', theme.border);
152.     root.style.setProperty('--theme-hero-text', theme.heroTextAccent);
153.     root.style.setProperty('--theme-chip', theme.chip);
154.   }, [tweaks.theme]);
155. 
156.   const onOpen = (id) => {
157.     // Chinese summary cards have no detail page — route to the English twin
158.     // (Tree-level / middle) via storyId. If no Tree twin exists, fall back to
159.     // any English variant of the same story.
160.     const target = ARTICLES.find(a => a.id === id);
161.     if (target && target.noDetail && target.language === 'zh') {
162.       const tree = ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en' && a.level === 'Tree');
163.       const any = tree || ARTICLES.find(a => a.storyId === target.storyId && a.language === 'en');
164.       if (any) id = any.id;
165.     }
166.     setRoute({ page:'article', articleId:id });
167.   };
168.   const onBack = () => setRoute({ page:'home', articleId:null });
169.   const onComplete = () => setRoute({ page:'home', articleId:null });
170. 
171.   return (
172.     <div data-screen-label={route.page==='home' ? '01 Home' : '02 Article'} style={{minHeight:'100vh', background: theme.bg}}>
173.       {route.page === 'home' ? (
174.         <HomePage
175.           onOpen={onOpen}
176.           onOpenArchive={(d)=>{ setArchiveDay(d); setCat('All'); window.scrollTo({top:0}); }}
177.           archiveDay={archiveDay}
178.           level={level} setLevel={setLevel}
179.           cat={cat} setCat={setCat}
180.           progress={progress}
181.           theme={theme}
182.           heroVariant={tweaks.heroVariant}
183.           tweaks={tweaks}
184.           onOpenUserPanel={()=>setUserPanelOpen(true)}
185.         />
186.       ) : (
187.         <ArticlePage
188.           articleId={route.articleId}
189.           onBack={onBack}
190.           onComplete={onComplete}
191.           progress={progress}
192.           setProgress={setProgress}
193.         />
194.       )}
195. 
196.       {userPanelOpen && (
197.         <UserPanel
198.           tweaks={tweaks}
199.           updateTweak={updateTweak}
200.           level={level}
201.           setLevel={setLevel}
202.           onClose={()=>setUserPanelOpen(false)}
203.         />
204.       )}
205.     </div>
206.   );
207. }
208. 
209. function TweaksPanel({ tweaks, updateTweak, setTweaksVisible }) {
210.   return (
211.     <div style={{
212.       position:'fixed', bottom:20, right:20, width:280, background:'#fff',
213.       borderRadius:18, border:'2px solid #1b1230', padding:'16px 18px',
214.       boxShadow:'0 10px 0 rgba(27,18,48,0.18)', zIndex:100,
215.       fontFamily:'Nunito, sans-serif',
216.     }}>
217.       <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
218.         <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>🎨 Tweaks</div>
219.         <button onClick={()=>setTweaksVisible(false)} style={{background:'none', border:'none', fontSize:18, cursor:'pointer', color:'#9a8d7a'}}>×</button>
220.       </div>
221. 
222.       <TwkRow label="Color theme">
223.         <select value={tweaks.theme} onChange={e=>updateTweak('theme', e.target.value)} style={twkInput}>
224.           <option value="sunny">☀️ Sunny</option>
225.           <option value="sky">🌊 Sky</option>
226.           <option value="candy">🍬 Candy</option>
227.           <option value="forest">🌳 Forest</option>
228.         </select>
229.       </TwkRow>
230. 
231.       <TwkRow label="Hero style">
232.         <select value={tweaks.heroVariant} onChange={e=>updateTweak('heroVariant', e.target.value)} style={twkInput}>
233.           <option value="daily15">Daily 15 banner</option>
234.           <option value="streak">Streak-focused</option>
235.         </select>
236.       </TwkRow>
237. 
238.       <TwkRow label="Quiz confetti">
239.         <label style={{display:'flex', alignItems:'center', gap:8, fontSize:13, fontWeight:700, cursor:'pointer'}}>
240.           <input type="checkbox" checked={tweaks.showConfetti} onChange={e=>updateTweak('showConfetti', e.target.checked)}/>
241.           {tweaks.showConfetti ? 'On' : 'Off'}
242.         </label>
243.       </TwkRow>
244. 
245.       <div style={{fontSize:11, color:'#9a8d7a', marginTop:10, borderTop:'1px dashed #eee', paddingTop:10}}>
246.         Toggle Tweaks from the toolbar to customize.
247.       </div>
248.     </div>
249.   );
250. }
251. const twkInput = {
252.   width:'100%', padding:'8px 10px', border:'1.5px solid #f0e8d8', borderRadius:10,
253.   fontSize:13, fontWeight:700, fontFamily:'Nunito, sans-serif', background:'#fff9ef', color:'#1b1230',
254. };
255. function TwkRow({ label, children }) {
256.   return (
257.     <div style={{marginBottom:10}}>
258.       <div style={{fontSize:11, fontWeight:800, color:'#6b5c80', letterSpacing:'.06em', textTransform:'uppercase', marginBottom:5}}>{label}</div>
259.       {children}
260.     </div>
261.   );
262. }
263. 
264. // Wait for all babel scripts to load AND for payloads to be fetched.
265. function mount() {
266.   if (!window.HomePage || !window.ArticlePage || !window.UserPanel) { setTimeout(mount, 50); return; }
267.   if (!window.__payloadsLoaded) { setTimeout(mount, 50); return; }
268.   window.__payloadsLoaded.then(() => {
269.     ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
270.   });
271. }
272. setTimeout(mount, 0);
273. </script>
274. </body>
275. </html>
276.
```

</details>


---

<sub>⏱️ 3m 17s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/full_round.py.**

/Users/jiong/myprojects/news-v2/pipeline/full_round.py (lines 360-620)

<details>
<summary>184 lines</summary>

```
360.             story_detail_dir.mkdir(parents=True, exist_ok=True)
361.             # slot-based lookup into details_by_slot: "<article_index>_<level>"
362.             for lvl_key, var_obj in (("easy", easy), ("middle", middle)):
363.                 slot_key = f"{slot - 1}_{lvl_key}"
364.                 det = details.get(slot_key) or {}
365.                 bg = det.get("background_read") or []
366.                 if isinstance(bg, str):
367.                     bg = [bg]
368.                 detail = {
369.                     "title": var_obj.get("headline") or art.get("title") or "",
370.                     "summary": var_obj.get("body") or "",      # full body (v1 pattern)
371.                     "why_it_matters": det.get("why_it_matters", ""),
372.                     "image_url": f"/{img_local}" if img_local else "",
373.                     "keywords": det.get("keywords") or [],
374.                     "questions": det.get("questions") or [],
375.                     "background_read": bg,
376.                     "Article_Structure": det.get("Article_Structure") or [],
377.                     "perspectives": det.get("perspectives") or [],
378.                     "mined_at": mined_at,
379.                     "source_published_at": art.get("published") or "",
380.                     "source_name": src_name,
381.                     "source_url": src_url,
382.                 }
383.                 (story_detail_dir / f"{lvl_key}.json").write_text(
384.                     json.dumps(detail, ensure_ascii=False, indent=2)
385.                 )
386. 
387.         # Write 3 listing files per category (easy / middle / cn)
388.         cat_slug = category.lower()
389.         for lvl_key, items in per_level_articles.items():
390.             out = payloads_dir / f"articles_{cat_slug}_{lvl_key}.json"
391.             out.write_text(json.dumps({"articles": items},
392.                                        ensure_ascii=False, indent=2))
393. 
394. 
395. # -------------------------------------------------------------------
396. # 5) Persist to Supabase (runs + stories rows)
397. # -------------------------------------------------------------------
398. 
399. def persist_to_supabase(stories_by_cat, variants_by_cat, today: str, run_id: str) -> int:
400.     """Insert stories rows; return count inserted."""
401.     count = 0
402.     for category, stories in stories_by_cat.items():
403.         variants = variants_by_cat.get(category, {})
404.         for slot, s in enumerate(stories, start=1):
405.             art = s["winner"]
406.             story_id = s.get("_story_id") or make_story_id(today, category, slot)
407.             vet = art.get("_vet_info") or {}
408.             safety = vet.get("safety") or {}
409.             interest = vet.get("interest") or {}
410.             src_host = urlparse(art.get("link") or "").netloc.replace("www.", "")
411.             row = {
412.                 "run_id": run_id,
413.                 "category": category,
414.                 "story_slot": slot,
415.                 "published_date": today,
416.                 "source_name": s["source"].name,
417.                 "source_url": art.get("link") or "",
418.                 "source_title": art.get("title") or "",
419.                 "source_published_at": None,   # skip for now
420.                 "winner_slot": s.get("winner_slot"),
421.                 "used_backup": bool(s.get("used_backup")),
422.                 "backup_for_source": s.get("primary_source_name"),
423.                 "safety_violence":   safety.get("violence"),
424.                 "safety_sexual":     safety.get("sexual"),
425.                 "safety_substance":  safety.get("substance"),
426.                 "safety_language":   safety.get("language"),
427.                 "safety_fear":       safety.get("fear"),
428.                 "safety_adult_themes": safety.get("adult_themes"),
429.                 "safety_distress":   safety.get("distress"),
430.                 "safety_bias":       safety.get("bias"),
431.                 "safety_total":      safety.get("total"),
432.                 "safety_verdict":    safety.get("verdict"),
433.                 "interest_importance": interest.get("importance"),
434.                 "interest_fun_factor": interest.get("fun_factor"),
435.                 "interest_kid_appeal": interest.get("kid_appeal"),
436.                 "interest_peak":       interest.get("peak"),
437.                 "interest_verdict":    interest.get("verdict"),
438.                 "vet_flags": safety.get("flags") or vet.get("flags") or [],
439.                 "primary_image_url": s.get("_image_storage_url") or art.get("og_image"),
440.                 "primary_image_local": s.get("_image_local"),
441.                 "primary_image_credit": src_host,
442.                 "payload_path": f"payloads/articles_{category.lower()}_easy.json",
443.                 "payload_story_id": story_id,
444.             }
445.             sid = insert_story(row)
446.             if sid:
447.                 count += 1
448.                 log.info("  → redesign_stories id=%s · %s #%d %s",
449.                          sid[:8], category, slot, art.get("title", "")[:50])
450.             else:
451.                 log.warning("  insert failed: %s", art.get("title", "")[:60])
452.     return count
453. 
454. 
455. # -------------------------------------------------------------------
456. # Orchestrator
457. # -------------------------------------------------------------------
458. 
459. def main() -> None:
460.     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
461.     website_dir = Path(__file__).resolve().parent.parent / "website"
462. 
463.     # Start run record
464.     run_id = insert_run({"run_date": today, "status": "running"})
465.     if not run_id:
466.         log.warning("insert_run failed — continuing without DB persistence")
467. 
468.     log.info("=== AGGREGATE (up to 4 candidates per source) ===")
469.     news_bs = aggregate_category("News", news_sources(), news_backups(), run_news)
470.     science_bs = aggregate_category("Science", science_sources(), sci_backups(), run_sci)
471.     fun_bs = aggregate_category("Fun", fun_sources(), fun_backups(), run_fun)
472. 
473.     log.info("=== PAST-DEDUP (3-day lookback · title ≥80%% similar = dup) ===")
474.     news_bs = filter_past_duplicates("News", news_bs, days=3)
475.     science_bs = filter_past_duplicates("Science", science_bs, days=3)
476.     fun_bs = filter_past_duplicates("Fun", fun_bs, days=3)
477. 
478.     log.info("=== PICK + CROSS-SOURCE DEDUP (promote next candidate on dup) ===")
479.     news = pick_winners_with_dedup(news_bs)
480.     science = pick_winners_with_dedup(science_bs)
481.     fun = pick_winners_with_dedup(fun_bs)
482.     stories_by_cat = {"News": news, "Science": science, "Fun": fun}
483.     for cat, ws in stories_by_cat.items():
484.         log.info("  %s: %d winners", cat, len(ws))
485. 
486.     log.info("=== IMAGES (optimize + upload) ===")
487.     for cat, ws in stories_by_cat.items():
488.         log.info("[%s] processing %d images", cat, len(ws))
489.         process_images(ws, today, website_dir)
490. 
491.     log.info("=== REWRITE (tri-variant + detail enrich, 2 calls per category) ===")
492.     variants_by_cat: dict[str, dict] = {}
493.     details_by_cat: dict[str, dict] = {}
494.     failures: list[str] = []
495.     for cat, ws in stories_by_cat.items():
496.         try:
497.             v, d = rewrite_for_category(ws)
498.             variants_by_cat[cat] = v
499.             details_by_cat[cat] = d
500.             log.info("  [%s] rewrite: %d variants · detail slots: %d",
501.                      cat, len(v), len(d))
502.         except Exception as e:  # noqa: BLE001
503.             log.error("  [%s] rewrite/enrich FAILED: %s", cat, e)
504.             failures.append(f"{cat}: {e}")
505. 
506.     if failures:
507.         # Mark run as failed (if DB tracking on), don't upload a partial zip.
508.         msg = f"{len(failures)} category failures: " + " | ".join(failures)
509.         if run_id:
510.             update_run(run_id, {"status": "failed",
511.                                 "finished_at": datetime.now(timezone.utc).isoformat(),
512.                                 "notes": msg})
513.         log.error("Aborting — %s", msg)
514.         raise SystemExit(1)
515. 
516.     log.info("=== EMIT v1-shape payload files ===")
517.     emit_v1_shape(stories_by_cat, variants_by_cat, details_by_cat, today, website_dir)
518. 
519.     log.info("=== PERSIST TO SUPABASE ===")
520.     count = 0
521.     if run_id:
522.         count = persist_to_supabase(stories_by_cat, variants_by_cat, today, run_id)
523.         update_run(run_id, {"status": "completed",
524.                             "finished_at": datetime.now(timezone.utc).isoformat(),
525.                             "notes": f"stories persisted: {count}"})
526. 
527.     log.info("=== PACK + UPLOAD ZIP (deploy trigger) ===")
528.     try:
529.         from .pack_and_upload import main as _pack_upload
530.         _pack_upload()
531.     except Exception as e:  # noqa: BLE001
532.         log.warning("pack_and_upload failed — site will lag until next run: %s", e)
533. 
534.     log.info("=== DONE ===")
535.     total_stories = sum(len(ws) for ws in stories_by_cat.values())
536.     log.info("Run: %s · Stories: %d · DB persisted: %d", run_id or "(no DB)",
537.              total_stories, count)
538.     log.info("View: http://localhost:18100/")
539. 
540. 
541. if __name__ == "__main__":
542.     main()
543.
```

</details>


---

<sub>⏱️ 4m 43s</sub>

### ✅ `rg`

**DEEPSEEK|SUPABASE_SERVICE_KEY|SUPABASE_URL**

"DEEPSEEK|SUPABASE_SERVICE_KEY|SUPABASE_URL" in website/*.{jsx,html}

```
/Users/jiong/myprojects/news-v2/website/data.jsx:15:const SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co';
/Users/jiong/myprojects/news-v2/website/data.jsx:16:const ARCHIVE_BASE = `${SUPABASE_URL}/storage/v1/object/public/redesign-daily-content`;
```


---

<sub>⏱️ 4m 43s</sub>

### ✅ `rg`

**def client|SUPABASE_SERVICE_KEY|create_client|logging**

"def client|SUPABASE_SERVICE_KEY|create_client|logging" in supabase_io.py (pipeline)

<details>
<summary>8 matches</summary>

```
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:4:import logging
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:9:from supabase import Client, create_client
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:11:log = logging.getLogger("supa")
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:21:SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:25:def client() -> Client:
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:26:    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:27:        raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY must be set in .env")
/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py:28:    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
```

</details>


---

<sub>⏱️ 4m 43s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/supabase_io.py.**

/Users/jiong/myprojects/news-v2/pipeline/supabase_io.py (lines 1-220)

<details>
<summary>84 lines</summary>

```
1. """Supabase helpers — Storage uploads + DB inserts for the v2 redesign schema."""
2. from __future__ import annotations
3. 
4. import logging
5. import os
6. from pathlib import Path
7. from typing import Any
8. 
9. from supabase import Client, create_client
10. 
11. log = logging.getLogger("supa")
12. 
13. # Load .env once
14. _envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
15. for _line in (_envp.open() if _envp.exists() else []):
16.     if "=" in _line and not _line.startswith("#"):
17.         _k, _v = _line.strip().split("=", 1)
18.         os.environ[_k] = _v
19. 
20. SUPABASE_URL = os.environ.get("SUPABASE_URL")
21. SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
22. STORAGE_BUCKET = "redesign-article-images"
23. 
24. 
25. def client() -> Client:
26.     if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
27.         raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY must be set in .env")
28.     return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
29. 
30. 
31. def upload_image(local_path: Path, remote_name: str) -> str | None:
32.     """Upload a local file to the storage bucket. Returns public URL or None."""
33.     try:
34.         sb = client()
35.         data = local_path.read_bytes()
36.         sb.storage.from_(STORAGE_BUCKET).upload(
37.             remote_name,
38.             data,
39.             file_options={
40.                 "content-type": "image/webp",
41.                 "upsert": "true",           # string, not bool — Supabase quirk
42.             },
43.         )
44.         public_url = sb.storage.from_(STORAGE_BUCKET).get_public_url(remote_name)
45.         # Supabase appends "?" sometimes — strip
46.         return public_url.rstrip("?")
47.     except Exception as e:
48.         log.warning("upload_image failed %s: %s", remote_name, e)
49.         return None
50. 
51. 
52. def insert_run(row: dict[str, Any]) -> str | None:
53.     """Insert a redesign_runs row, return generated id."""
54.     try:
55.         sb = client()
56.         res = sb.table("redesign_runs").insert(row).execute()
57.         return res.data[0]["id"] if res.data else None
58.     except Exception as e:
59.         log.error("insert_run failed: %s", e)
60.         return None
61. 
62. 
63. def update_run(run_id: str, fields: dict[str, Any]) -> bool:
64.     try:
65.         sb = client()
66.         sb.table("redesign_runs").update(fields).eq("id", run_id).execute()
67.         return True
68.     except Exception as e:
69.         log.error("update_run failed: %s", e)
70.         return False
71. 
72. 
73. def insert_story(row: dict[str, Any]) -> str | None:
74.     """Insert a redesign_stories row. Upsert on (published_date, category, story_slot)."""
75.     try:
76.         sb = client()
77.         res = sb.table("redesign_stories").upsert(
78.             row, on_conflict="published_date,category,story_slot"
79.         ).execute()
80.         return res.data[0]["id"] if res.data else None
81.     except Exception as e:
82.         log.error("insert_story failed: %s", e)
83.         return None
84.
```

</details>


---

<sub>⏱️ 4m 43s</sub>

### ✅ `view`

**view the file at /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py.**

/Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py (lines 462-520)

<details>
<summary>59 lines</summary>

```
462. def tri_variant_rewriter_input(articles_with_ids: list[tuple[int, dict]]) -> str:
463.     lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
464.     for src_id, art in articles_with_ids:
465.         host = urlparse(art.get("link") or "").netloc.replace("www.", "")
466.         body = art.get("body") or ""
467.         body_trimmed = " ".join(body.split()[:2500])
468.         lines.append(f"=== SOURCE [id: {src_id}] ===")
469.         lines.append(f"Title: {art.get('title','')}")
470.         lines.append(f"Host: {host}")
471.         lines.append(f"Date: {art.get('published','')}")
472.         lines.append("")
473.         lines.append("Full body:")
474.         lines.append(body_trimmed)
475.         lines.append("")
476.     lines.append("Write 3 tri-variant entries (easy_en + middle_en + zh) per the rules.")
477.     return "\n".join(lines)
478. 
479. 
480. def tri_variant_rewrite(articles_with_ids: list[tuple[int, dict]]) -> dict:
481.     return deepseek_call(TRI_VARIANT_REWRITER_PROMPT,
482.                          tri_variant_rewriter_input(articles_with_ids),
483.                          max_tokens=5000, temperature=0.5)
484. 
485. 
486. # ---------------------------------------------------------------------------
487. # Detail enrichment — 1 call per category, 6 items (3 articles × 2 EN variants)
488. # References bodies by id instead of re-returning them (saves tokens).
489. # ---------------------------------------------------------------------------
490. 
491. DETAIL_ENRICH_PROMPT = """You are enriching kids-news articles with DEPTH beyond the body text.
492. Use careful reasoning. The reader already has the body; you're adding what the
493. body alone doesn't provide — historical context, real-world pattern, nuance.
494. 
495. You will receive 3 articles. Each has two rewritten English bodies:
496.   easy_en  — grade 4 / 10-year-old reader (~200 words)
497.   middle_en — grade 7-8 / 12-14 year old reader (~320 words)
498. 
499. For each of the 6 slots (3 articles × {easy,middle}) produce:
500. 
501.   [common to both easy and middle]
502.   · keywords: 6 {term, explanation} pairs. EVERY term MUST literally appear (or
503.     appear as a common inflection — "banned" for "ban", "fined" for "fine")
504.     in the corresponding body. Do NOT invent concepts that aren't in the text.
505.   · questions: 6 MCQ questions, each {question, options:[4], correct_answer}.
506.     correct_answer MUST match one option character-for-character.
507. 
508.   ———— easy slot (10-year-old reader) ————
509.   · background_read: array of 2-3 SIMPLE sentences giving RELATED real-world
510.     context. Add historical facts, related events, or concepts the kid might
511.     not know. Avoid generic filler about the news source itself.
512.   · Article_Structure: array of 4 strings: WHO / WHAT / WHERE / WHY
513.     (format: "WHO: ...", "WHAT: ...", etc.) — specific answers drawn from the
514.     body, not a template.
515.   · why_it_matters: 1 sentence connecting the story to a 10-year-old's life
516.     (school / family / community / future).
517.   · perspectives: 2-3 {perspective, description} POV pairs covering clear
518.     different stances (positive / critical / neutral).
519. 
520.   ———— middle slot (12-14 year old reader) ————
```

</details>


---

<sub>⏱️ 6m 36s</sub>

### 💬 Copilot

- **Severity**: `Critical`  
  **File:line**: `website/home.jsx:31-37`  
  **What**: `HomePage` references `todayArticles`, but that identifier is never defined anywhere in the file.  
  **Why**: That `useMemo` runs during render, so the first trip through the home page throws a `ReferenceError` and the UI never mounts the listing view. This is a hard correctness bug, not just a stale-code smell.  
  **Fix**: Build `displayPool` from an actually defined source (`ARTICLES`, `filteredRaw`, or another explicit per-category pool) and keep the dependency list aligned with that source.

- **Severity**: `Important`  
  **File:line**: cross-cutting (`website/index.html:61-76,98-114`; `website/home.jsx:41-55`)  
  **What**: The app reads and writes `localStorage` in several places without a safe wrapper.  
  **Why**: Browsers can throw on `localStorage` access when storage is disabled/restricted, and writes can throw `QuotaExceededError` when storage is full. In this app those exceptions happen inside state initializers/effects, so one bad storage environment can take down routing, archive mode, progress saving, or daily-picks persistence.  
  **Fix**: Centralize `getItem` / `setItem` / `removeItem` behind a small `safeStorage` helper with `try/catch`, and fall back to in-memory defaults when storage is unavailable.

- **Severity**: `Important`  
  **File:line**: `pipeline/full_round.py:521-532`  
  **What**: The run is marked `completed` in Supabase before `pack_and_upload()` runs, and upload-phase exceptions are downgraded to a warning.  
  **Why**: A run can be recorded as completed even when the bundle never ships, archive uploads fail, or deployment lags. That creates false-green operational state exactly when you most need the DB status to tell you the truth.  
  **Fix**: Move `update_run(... status="completed" ...)` until after a successful pack/upload phase, and record a failed/degraded terminal state when upload or archive publication fails.

- **Severity**: `Important`  
  **File:line**: cross-cutting (`pipeline/pack_and_upload.py:276-296,411-432`; `website/data.jsx:78-80,106-123`; `website/home.jsx:351-383`)  
  **What**: Flat-file upload and archive-index update are treated as non-fatal even though the frontend depends on them for archive browsing.  
  **Why**: The UI reads old editions from `\<date\>/payloads/*.json` and discovers dates from `archive-index.json`; if flat upload fails and the date still lands in the index, the site advertises an archive day whose payloads 404. Worse, once that date is in the index, future backfill logic stops considering it “missing,” so the bad state can stick.  
  **Fix**: Only add `today` to `archive-index.json` after flat files are confirmed present, and fail the run (or at least leave the date out of the index) if both direct upload and backfill fail.

- **Severity**: `Important`  
  **File:line**: `pipeline/news_rss_core.py:241-270,630-661`  
  **What**: DeepSeek retry logic treats malformed JSON, 429/rate limiting, and generic network failures as the same class of error with the same short linear backoff.  
  **Why**: Those failures need different behavior: malformed JSON often merits a quick retry, while 429 usually needs a longer wait or explicit surfacing. The current 2s/4s backoff is too short for quota/rate-limit recovery and makes the logs less actionable.  
  **Fix**: Split retry policy by failure type: inspect HTTP status, honor `Retry-After` when present, use longer exponential backoff for 429s, and keep JSON-repair retries separate.

- **Severity**: `Important`  
  **File:line**: cross-cutting (`pipeline/news_rss_core.py:462-477,495-500,570-585,668-678`; `pipeline/full_round.py:242-260`)  
  **What**: The rewrite/enrich prompts are hard-coded for exactly 3 articles / 6 slots, but the pipeline explicitly supports thinner categories after dedup.  
  **Why**: On a legitimate 2-story day, the model is still told “3 articles” and asked for slot keys through `2_middle`, which increases the chance of hallucinated extra output, malformed structure, or attention wasted on nonexistent items. This is prompt-contract drift between orchestration and prompt design.  
  **Fix**: Parameterize prompt text and expected slot keys from the actual article count instead of embedding `3 articles`, `6 slots`, and `0..2` literals.

- **Severity**: `Minor`  
  **File:line**: `pipeline/full_round.py:69-80,90-128`  
  **What**: Past-duplicate filtering is driven entirely by `SequenceMatcher` title similarity at a fixed `0.80` threshold.  
  **Why**: Title-only matching will inevitably miss same-story rewrites with different wording and occasionally drop distinct stories with templated/similar headlines. Because this filter runs before cross-source promotion, false positives directly shrink the candidate pool on already-thin days.  
  **Fix**: Keep the cheap title check, but add a second signal before dropping (for example source URL hostname + named-entity overlap, or a small semantic duplicate pass on borderline cases).

- **Severity**: `Minor`  
  **File:line**: cross-cutting (`pipeline/rewrite_from_db.py:52`; `pipeline/news_rss_core.py:1209,1226`; `pipeline/news_aggregate.py:348,372`)  
  **What**: Hard-coded `/Users/jiong/...` paths still exist in the resume/debug path and related helper scripts.  
  **Why**: The brief called this out as a real CI footgun today, and those machine-specific paths are still present in non-primary flows. That means recovery/debug tooling remains host-bound and easy to break on CI or another workstation.  
  **Fix**: Route every website/output path through one repo-root-derived constant (`Path(__file__).resolve().parent.parent / "website"` or `config.PROJECT_ROOT`) instead of embedding absolute user paths.

Overall, the architecture still looks directionally sound: zip-for-deploy plus flat-files-for-archive is justified, and I did not see any frontend leak of the DeepSeek key or Supabase service key. The bigger problems are reliability mismatches between “pipeline succeeded” and “site/archive is actually usable,” plus one outright frontend crash. Prompt contracts have also drifted from the new 2-or-3-story reality, which will show up exactly on the hardest days.

**Top 3 things to fix first**
1. Fix the `todayArticles` crash in `website/home.jsx`.
2. Make upload/archive publication failures truthfully fail or degrade the run state instead of recording `completed`.
3. Parameterize rewrite/enrich prompts by actual story count so 2-story days are first-class, not an accidental edge case.

---

<sub>Generated by [GitHub Copilot CLI](https://github.com/features/copilot/cli)</sub>
