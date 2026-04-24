// data.jsx — v2 payload loader
// Consumes v1 listing payloads under ./payloads/ and exposes window.ARTICLES,
// window.CATEGORIES, window.LEVELS, window.MOCK_USER, and window.__payloadsLoaded
// (a promise that resolves once ARTICLES is populated).
//
// Contract mapping (v2 UI <-- v1 source):
//   Sprout level        <- easy
//   Tree level          <- middle
//   Chinese summary card<- cn  (no detail page — summary only)
//   high                -- IGNORED in v2
//   Category "News"     <- news
//   Category "Science"  <- science
//   Category "Fun"      <- fun
//
// Each category surfaces the first 3 stories per the v2 spec.
// The `cn` variants share `storyId` with their `easy`/`middle` twins so the
// app can route Chinese cards to the English (Tree-level) detail page.

const CATEGORIES = [
  { id: "news",    label: "News",    emoji: "📰", color: "#ff6b5b", bg: "#ffece8" },
  { id: "science", label: "Science", emoji: "🔬", color: "#17b3a6", bg: "#e0f6f3" },
  { id: "fun",     label: "Fun",     emoji: "🎈", color: "#9061f9", bg: "#eee5ff" },
];

const LEVELS = [
  { id: "Sprout", emoji: "🌱", label: "Sprout", sub: "Easy" },
  { id: "Tree",   emoji: "🌳", label: "Tree",   sub: "Middle" },
];

// Mock user state — unchanged from prototype (UI state, not content).
const MOCK_USER = {
  name: "Mia",
  streak: 7,
  minutesToday: 6,
  dailyGoal: 15,
  totalXp: 1240,
  weekXp: 310,
  badges: ["🦉", "🔭", "🌱"],
  readToday: ["a2"], // already read (legacy placeholder)
};

function listingToArticle(entry, cat, lvl) {
  const categoryLabel = { news: "News", science: "Science", fun: "Fun" }[cat];
  const isZh = lvl === "cn";
  const level = isZh ? null : (lvl === "easy" ? "Sprout" : "Tree");
  return {
    id: entry.id + "-" + lvl,         // unique per (story, language/level) variant
    storyId: entry.id,                // pairs same-story variants across lvl
    day: 0,
    title: entry.title,
    summary: entry.summary,
    body: "",                         // filled by lazy fetch in ArticlePage
    image: entry.image_url,           // e.g. "/article_images/article_xxx.webp"
    category: categoryLabel,
    source: entry.source || "",
    time: entry.time_ago || "",
    minedAt: entry.mined_at || "",              // ISO-8601 when pipeline captured this story
    sourcePublishedAt: entry.source_published_at || "",  // RSS pubDate (may be absent for some feeds)
    readMins: isZh ? 2 : (lvl === "easy" ? 3 : 5),
    level: level,                     // null for Chinese cards
    language: isZh ? "zh" : "en",
    xp: isZh ? 15 : (lvl === "easy" ? 30 : 45),
    tag: categoryLabel,               // minimal fallback so alt.tag renders
    keywords: [],                     // lazy-fetched
    quiz: [],                         // lazy-fetched
    discussion: [],                   // lazy-fetched
    noDetail: isZh,                   // Chinese cards have no detail page
  };
}

async function loadPayloads() {
  const cats = ["news", "science", "fun"];
  const levels = ["easy", "middle", "cn"]; // 3 x 3 = 9 fetches
  const all = [];
  for (const cat of cats) {
    for (const lvl of levels) {
      try {
        const r = await fetch(`payloads/articles_${cat}_${lvl}.json`);
        if (!r.ok) { console.warn(`[data] missing: articles_${cat}_${lvl}.json`); continue; }
        const { articles } = await r.json();
        const top3 = (articles || []).slice(0, 3); // v2 contract: 3 per category
        for (const a of top3) all.push(listingToArticle(a, cat, lvl));
      } catch (e) {
        console.warn(`[data] fetch failed: articles_${cat}_${lvl}.json`, e);
      }
    }
  }
  return all;
}

window.CATEGORIES = CATEGORIES;
window.LEVELS = LEVELS;
window.MOCK_USER = MOCK_USER;
window.ARTICLES = [];
window.__payloadsLoaded = loadPayloads().then(list => {
  window.ARTICLES = list;
  return list;
});
