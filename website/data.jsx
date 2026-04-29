// data.jsx — v2 payload loader
// Consumes v1 listing payloads and exposes window.ARTICLES, window.CATEGORIES,
// window.LEVELS, window.MOCK_USER, window.__payloadsLoaded (promise for
// initial today's load), and window.loadArchive(date) to swap in a past day.
//
// Today's content is served from the Vercel deploy (same origin, flat paths
// under /payloads/ and /article_images/). Past days are served directly from
// Supabase Storage under /<date>/payloads/... — see ARCHIVE_BASE.
//
// Contract mapping (v2 UI <-- v1 source):
//   Sprout level        <- easy
//   Tree level          <- middle
//   Chinese summary card<- cn  (no detail page — summary only)

const SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co';
const ARCHIVE_BASE = `${SUPABASE_URL}/storage/v1/object/public/redesign-daily-content`;

// ─── Per-vertical site config ─────────────────────────────────────────
// Single point of truth for the daily-reading model + brand. Future
// "21mins" verticals (AI, finance, tech for adults) clone this with
// different values. Anything that varies by vertical lives here, never
// hardcoded in JSX.
//
// dailyGoalMinutes  =  storiesPerDay  ×  sum(stepWeights)
// 21               =  3              ×  (2+1+2+2)
const SITE_CONFIG = {
  // ── Brand / wordmark ────────────────────────────────────────────────
  brand:         "kidsnews",          // wordmark line, displayed as "kids" + "news"
  brandWordHi:   "news",              // colored portion of the wordmark (renders in --twentyone-coral)
  parent:        "21mins",            // parent brand
  endorsement:   "21MINS daily news.",// small caps endorsement under the lockup (line 1)
  endorsement2:  "Learn the real world.", // second-line endorsement
  audience:      "Kids age 8-13",
  domain:        "kidsnews.21mins.com",
  vertical:      "kidsnews",

  // ── Slogans + copy ─────────────────────────────────────────────────
  // Hero tagline: italic, sits below "Today's 21 minutes"
  tagline:      "Little daily, big magic.",
  // For OG / share / about
  longSlogan:   "21 minutes. Every day. The magic compounds.",

  // ── Daily reading model ─────────────────────────────────────────────
  dailyGoalMinutes: 21,
  storiesPerDay:    3,
  perArticleMinutes: 7,                  // = sum(stepWeights)

  // Each step contributes its weight in "minutes" to the daily counter
  // when the user finishes it. Sum must equal perArticleMinutes.
  stepWeights: {
    read:    2,   // body + words / vocabulary
    analyze: 1,   // background, structure
    quiz:    2,
    discuss: 2,   // think
  },
};
window.SITE_CONFIG = SITE_CONFIG;

// Browsers can throw on localStorage access (private mode in Safari, quota
// exhaustion, storage disabled by enterprise policy, embedded contexts).
// Wrap reads/writes so one bad environment doesn't kill route restoration,
// archive mode, progress saving, or daily-picks persistence.
const safeStorage = {
  get(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem(key, value); return true; }
    catch (e) { console.warn('[storage] set failed', key, e); return false; }
  },
  remove(key) {
    try { localStorage.removeItem(key); } catch (e) { /* swallow */ }
  },
  getJSON(key, fallback = null) {
    const raw = this.get(key);
    if (!raw) return fallback;
    try { return JSON.parse(raw); } catch { return fallback; }
  },
  setJSON(key, value) {
    return this.set(key, JSON.stringify(value));
  },
};
window.safeStorage = safeStorage;

const CATEGORIES = [
  { id: "news",    label: "News",    emoji: "📰", color: "#ff6b5b", bg: "#ffece8" },
  { id: "science", label: "Science", emoji: "🔬", color: "#17b3a6", bg: "#e0f6f3" },
  { id: "fun",     label: "Fun",     emoji: "🎈", color: "#9061f9", bg: "#eee5ff" },
];

const LEVELS = [
  { id: "Sprout", emoji: "🌱", label: "Sprout", sub: "Easy" },
  { id: "Tree",   emoji: "🌳", label: "Tree",   sub: "Middle" },
];

// Cosmetic fixtures only (name/streak/XP/badges). Daily progress lives in
// React state hydrated from localStorage `ohye_progress`; pre-filled
// `minutesToday`/`readToday` here would silently inflate a brand-new
// reader's count — keep these zero/empty.
const MOCK_USER = {
  name: "Mia",
  streak: 7,
  minutesToday: 0,
  dailyGoal: SITE_CONFIG.dailyGoalMinutes,
  totalXp: 1240,
  weekXp: 310,
  badges: ["🦉", "🔭", "🌱"],
  readToday: [],
};

// Rewrite /article_images/xxx.webp → full Supabase URL when we're loading an
// archived day. For today's content (archiveDate = null), normalize to
// an absolute path with a leading slash. Without the slash, navigating
// to /archive/<date> (Vercel rewrite serves index.html, URL stays at
// /archive/<date>) caused image fetches to resolve against /archive/...
// and 404. Normalizing ensures the browser always hits the site root.
function resolveImageUrl(rawUrl, archiveDate) {
  if (!rawUrl) return "";
  if (rawUrl.startsWith('http')) return rawUrl;
  const rel = rawUrl.replace(/^\//, '');   // drop any existing leading slash
  if (!archiveDate) return '/' + rel;       // today: absolute root
  return `${ARCHIVE_BASE}/${archiveDate}/${rel}`;
}

function listingToArticle(entry, cat, lvl, archiveDate) {
  const categoryLabel = { news: "News", science: "Science", fun: "Fun" }[cat];
  const isZh = lvl === "cn";
  const level = isZh ? null : (lvl === "easy" ? "Sprout" : "Tree");
  return {
    id: entry.id + "-" + lvl,
    storyId: entry.id,
    archiveDate: archiveDate || null,   // null = today's edition
    title: entry.title,
    summary: entry.summary,
    body: "",
    image: resolveImageUrl(entry.image_url, archiveDate),
    category: categoryLabel,
    source: entry.source || "",
    time: entry.time_ago || "",
    minedAt: entry.mined_at || "",
    sourcePublishedAt: entry.source_published_at || "",
    // English articles count for the full per-article reading budget.
    // Chinese summary cards stay shorter (they're summary-only, not the
    // full counter contributor).
    readMins: isZh ? 2 : SITE_CONFIG.perArticleMinutes,
    level: level,
    language: isZh ? "zh" : "en",
    xp: isZh ? 15 : (lvl === "easy" ? 30 : 45),
    tag: categoryLabel,
    keywords: [],
    quiz: [],
    discussion: [],
    noDetail: isZh,
  };
}

function listingBaseFor(archiveDate) {
  // For "today" (archiveDate=null), use an ABSOLUTE path. The site
  // also serves under /archive/<date> via a Vercel rewrite that
  // returns index.html unchanged. With a relative `payloads`, the
  // browser resolves it against the URL path → /archive/payloads/...
  // → 404 → "Return to today" loaded nothing → page kept showing the
  // archive content.
  return archiveDate ? `${ARCHIVE_BASE}/${archiveDate}/payloads`
                     : '/payloads';
}

// Cache per archiveDate (null = today). Lets a user revisit a recent
// archive day without re-fetching all 9 payloads. Cleared on page
// reload, so a fresh build always pulls latest.
const _archiveCache = new Map();

async function loadPayloads(archiveDate = null) {
  const cacheKey = archiveDate || '__today__';
  if (_archiveCache.has(cacheKey)) {
    return _archiveCache.get(cacheKey);
  }
  const cats = ["news", "science", "fun"];
  const levels = ["easy", "middle", "cn"];
  const base = listingBaseFor(archiveDate);
  const ts = Date.now();
  // 9 fetches in parallel. Sequential awaits used to take ~5s on the
  // archive code path (Supabase round-trips) — Promise.all drops it
  // to one round-trip's worth.
  const fetchOne = async (cat, lvl) => {
    try {
      const r = await fetch(`${base}/articles_${cat}_${lvl}.json?t=${ts}`);
      if (!r.ok) {
        console.warn(`[data] missing: ${base}/articles_${cat}_${lvl}.json`);
        return [];
      }
      const { articles } = await r.json();
      return (articles || []).slice(0, 3).map(a => listingToArticle(a, cat, lvl, archiveDate));
    } catch (e) {
      console.warn(`[data] fetch failed: ${base}/articles_${cat}_${lvl}.json`, e);
      return [];
    }
  };
  const tasks = [];
  for (const cat of cats) {
    for (const lvl of levels) {
      tasks.push(fetchOne(cat, lvl));
    }
  }
  const results = await Promise.all(tasks);
  const all = results.flat();
  _archiveCache.set(cacheKey, all);
  return all;
}

// Fetch the list of available archive days from Supabase.
// Returns { dates: [...], updated_at } or { dates: [] } on failure.
async function loadArchiveIndex() {
  try {
    const r = await fetch(`${ARCHIVE_BASE}/archive-index.json?t=${Date.now()}`);
    if (!r.ok) return { dates: [] };
    return await r.json();
  } catch (e) {
    console.warn('[data] archive-index fetch failed', e);
    return { dates: [] };
  }
}

// Callable from the app: swap window.ARTICLES to point at a past day's
// bundle, or back to today when passed null.
async function loadArchive(date) {
  const list = await loadPayloads(date || null);
  window.ARTICLES = list;
  window.__archiveDate = date || null;
  return list;
}

// Anonymous client_id — generated once per browser, persisted in localStorage.
// Used by the feedback-rewrite edge function to attribute saved responses
// without requiring login. NOT a tracking id; never sent to anywhere
// outside our own Supabase.
function getClientId() {
  let id = safeStorage.get('ohye_client_id');
  if (!id) {
    id = (crypto.randomUUID && crypto.randomUUID()) ||
         (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
    safeStorage.set('ohye_client_id', id);
  }
  return id;
}

const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxma25zdmF2aGlxcnNhc2RmeXJzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI3MzMwMjcsImV4cCI6MjA3ODMwOTAyN30.2YPvOkZOWi4hDjtwZYkVt9a-RwYSnfotjV6Raj24ZjE';
const FEEDBACK_FN = `${SUPABASE_URL}/functions/v1/feedback-rewrite`;

// Call the feedback-rewrite edge function. Returns either
//   { feedback, rewrite, scores, word_count, saved_id }
// on success, or
//   { error: "..." }
// on validation failure (status 400) or upstream error (502).
async function fetchAIFeedback({ text, articleId, articleTitle, articleSummary, articleBody, level }) {
  try {
    const r = await fetch(FEEDBACK_FN, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
      },
      body: JSON.stringify({
        text, articleId, articleTitle, articleSummary, articleBody, level,
        clientId: getClientId(),
      }),
    });
    const body = await r.json();
    if (!r.ok) return { error: body.error || `HTTP ${r.status}`, ...body };
    return body;
  } catch (e) {
    return { error: 'Network error: ' + (e.message || String(e)) };
  }
}

window.CATEGORIES = CATEGORIES;
window.LEVELS = LEVELS;
window.MOCK_USER = MOCK_USER;
window.ARTICLES = [];
window.__archiveDate = null;
window.ARCHIVE_BASE = ARCHIVE_BASE;
window.loadArchive = loadArchive;
window.loadArchiveIndex = loadArchiveIndex;
window.fetchAIFeedback = fetchAIFeedback;

// Archive search — calls the archive-search edge function. Returns
// { query, count, results: [{story_id, published_date, level, title,
// snippet (HTML, with <b>...</b> highlights), image_url, source_name,
// rank}, ...] } or { error }.
async function archiveSearch(q, opts) {
  const params = new URLSearchParams({ q, limit: String((opts && opts.limit) || 10) });
  if (opts && opts.category) params.set("category", opts.category);
  if (opts && opts.level) params.set("level", opts.level);
  try {
    const r = await fetch(
      `${SUPABASE_URL}/functions/v1/archive-search?${params.toString()}`,
      { headers: { Authorization: `Bearer ${SUPABASE_ANON_KEY}` } },
    );
    return await r.json();
  } catch (e) {
    return { error: "Network error: " + (e.message || String(e)) };
  }
}
window.archiveSearch = archiveSearch;
window.getClientId = getClientId;
window.__payloadsLoaded = loadPayloads().then(list => {
  window.ARTICLES = list;
  return list;
});
