"""Configuration constants for KidsNews v2 pipeline (Steps 1-3)."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Query rotation tables
# ---------------------------------------------------------------------------

NEWS_QUERY = "top 5 hottest news today"
NEWS_FALLBACK_QUERY = "latest kid-safe news stories"
NEWS_TOPIC = "Current events"

# News 3-lane redesign (v2-curator)
NEWS_CURATOR_QUERY = "top news stories today"
NEWS_TIER1_DOMAINS = ["npr.org", "reuters.com"]
NEWS_TIER2_DOMAINS = ["apnews.com", "bbc.com", "theguardian.com"]
NEWS_LANE_MAX_RESULTS = 5

# weekday() → (topic_label, tavily_query)
SCIENCE_ROTATION: dict[int, tuple[str, str]] = {
    0: ("AI / auto",                        "mind blowing AI robots automation news this week for kids"),
    1: ("Biology / Medicine / Health",      "mind blowing biology medicine health news this week for kids"),
    2: ("Space / Astronomy",                "mind blowing space astronomy discoveries news this week for kids"),
    3: ("Chemistry / Physics",              "mind blowing chemistry physics experiments news this week for kids"),
    4: ("Environment / Climate",            "mind blowing environment climate nature news this week for kids"),
    5: ("Technology / Engineering",         "mind blowing technology engineering invention news this week for kids"),
    6: ("Nature / Geometry",                "mind blowing nature geometry patterns news this week for kids"),
}

FUN_ROTATION: dict[int, tuple[str, str]] = {
    0: ("Music", "kids music news concerts instruments this week"),
    1: ("Swimming / Water sports", "kids swimming water sports news this week"),
    2: ("Movies / TV", "kids movies tv shows news this week"),
    3: ("Cool inventions / kid inventors / new toys",
        "best new kids toys and inventions launching this week"),
    4: ("Arts / Crafts", "kids arts crafts creativity news this week"),
    5: ("Animals / Famous person / History", "kids animals famous people history news this week"),
    6: ("Video games / Esports", "kids video games esports news this week"),
}

# ---------------------------------------------------------------------------
# RSS feeds
# ---------------------------------------------------------------------------

RSS_FEEDS: dict[str, dict] = {
    "News": {
        "url": "https://www.pbs.org/newshour/feeds/rss/headlines",
        "source_name": "PBS NewsHour",
        "target": 3,
    },
    "Science": {
        "url": "https://www.sciencedaily.com/rss/all.xml",
        "source_name": "Science Daily",
        "target": 3,
    },
    "Fun": {
        "url": "https://feeds.bbci.co.uk/sport/tennis/rss.xml",
        "source_name": "BBC Tennis",
        "target": 2,
    },
}

# ---------------------------------------------------------------------------
# Tavily tuning
# ---------------------------------------------------------------------------

TAVILY_TARGET = 3  # per-category fallback
# Per-category Tavily discovery targets (News bumped to 5 for wider funnel)
TAVILY_TARGETS: dict[str, int] = {"News": 5, "Science": 3, "Fun": 3}
# Per-category RSS discovery targets (News bumped to 5)
RSS_TARGETS: dict[str, int] = {"News": 5, "Science": 3, "Fun": 2}
TAVILY_MAX_RESULTS = 15  # ask for lots of extras; URL-shape filter is strict
TAVILY_ENDPOINT = "https://api.tavily.com/search"
TAVILY_EXTRACT_ENDPOINT = "https://api.tavily.com/extract"
TAVILY_EXTRACT_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Shopping / deals filter (Fix 3)
# ---------------------------------------------------------------------------

# Hosts devoted primarily to deals / shopping listicles.
SHOPPING_HOSTS = (
    "bgr.com",
    "rochesterfirst.com",
    "slickdeals.net",
    "dealnews.com",
    "bestproducts.com",
)

# URL path fragments that signal deals/shopping sections of mainstream sites.
SHOPPING_PATH_MARKERS = (
    "/best-deals",
    "/select/shopping",
    "/shopping/",
    "/deals/",
    "/top-deals",
    "/gift-guide",
    "/buying-guide",
)

# ---------------------------------------------------------------------------
# Image filter
# ---------------------------------------------------------------------------

IMAGE_URL_BLACKLIST = (
    "logo", "icon", "avatar", "tracking", "1x1", "pixel", "spacer",
    # bot/crawler proxy URLs that return HTML not image bytes
    "crawler", "google_widget",
)
IMAGE_EXT_BLACKLIST = (".svg", ".gif")
IMAGE_MIN_BYTES = 20_000
IMAGE_HEAD_TIMEOUT = 3

# ---------------------------------------------------------------------------
# Vetter thresholds (Stage 1 on title + snippet)
# ---------------------------------------------------------------------------

VET_SAFE_MAX = 4       # 0-4 SAFE
VET_CAUTION_MAX = 12   # 5-12 CAUTION
# 13-40 REJECT

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_TEMPERATURE = 0.1
DEEPSEEK_MAX_TOKENS = 600

VETTER_SYSTEM_PROMPT = """You are a content reviewer for a kids news site (ages 8-13, grades 3-8).
You are judging based ONLY on the title and a short snippet.

PART A — SAFETY. Rate each 0-5 (0=none, 5=severe):
violence, sexual, substance, language, fear, adult_themes, distress, bias.
Compute safety_total = sum of these (0-40).
safety_verdict:
  0-4  -> SAFE
  5-12 -> CAUTION (publishable after rewrite softening)
  13+  -> REJECT (block)

PART B — INTEREST. A safe story still needs to be worth reading. Rate each 0-5:
- importance: how globally significant (0=trivial, 5=major historic event)
- fun_factor: how funny, delightful, surprising (0=dry, 5=hilarious/amazing)
- kid_appeal: how likely an 8-13 year old would WANT to read this (0=boring to a kid, 5=kid magnet)
Compute interest_peak = max(importance, fun_factor, kid_appeal).
interest_verdict:
  peak >= 3 -> ENGAGING
  peak == 2 -> MEH
  peak <= 1 -> BORING

Rule: a story can pass with EITHER high importance OR high fun_factor OR high kid_appeal — it does not need all three.

Return ONLY valid JSON (no markdown fences):
{
  "safety_scores": {"violence":0,"sexual":0,"substance":0,"language":0,"fear":0,"adult_themes":0,"distress":0,"bias":0},
  "safety_total": 0,
  "safety_verdict": "SAFE|CAUTION|REJECT",
  "interest_scores": {"importance":0,"fun_factor":0,"kid_appeal":0},
  "interest_peak": 0,
  "interest_verdict": "ENGAGING|MEH|BORING",
  "flags": ["..."],
  "rewrite_notes": "..."
}"""

# Interest thresholds already encoded in the prompt; keep exposed:
INTEREST_PEAK_MIN_KEEP = 2  # drop candidates with interest_peak < this (i.e., BORING gets dropped)

# ---------------------------------------------------------------------------
# Jina Reader
# ---------------------------------------------------------------------------

JINA_ENDPOINT = "https://r.jina.ai/"
JINA_TIMEOUT = 30
JINA_MIN_CONTENT_LEN = 1200  # reuse Tavily raw_content if at least this many chars

# ---------------------------------------------------------------------------
# News-lane content strategy
# ---------------------------------------------------------------------------

# If Tavily raw_content has >= this many words, treat it as sufficient and
# skip the Jina fallback. Applied when the category is in SKIP_JINA_CATEGORIES.
TAVILY_CONTENT_MIN_WORDS = 450

# Categories for which we do NOT fall back to Jina. News articles are often
# video-first and produce thin text; we'd rather drop than pay for Jina.
SKIP_JINA_CATEGORIES = {"News"}

# ---------------------------------------------------------------------------
# Post-vet selection
# ---------------------------------------------------------------------------

# Pick the top N (by vetted_rank) among SAFE/CAUTION per category.
FINAL_PUBLISH_COUNT = 3

# Hosts for which we trust og:image enough to skip the HEAD check.
TRUSTED_IMAGE_HOSTS = (
    "ichef.bbci.co.uk",
    "bbci.co.uk",
    "pbs.org",
    "pbs.twimg.com",
    "static.pbs.org",
    "image.pbs.org",
    "assets.sciencedaily.com",
    "cdn.sciencedaily.com",
    "sciencedaily.com",
)

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = PROJECT_ROOT / "website"
TEST_OUTPUT_DIR = WEBSITE_DIR / "test_output"

# Categories to process (in order)
CATEGORIES = ["News", "Science", "Fun"]
