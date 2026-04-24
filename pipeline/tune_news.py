"""News shootout — focus on NPR + Reuters; exclude cbs/cnn/fox."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import requests

for _line in open("/Users/jiong/myprojects/news-v2/.env"):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

TAVILY_KEY = os.environ["TAVILY_API_KEY"]
ENDPOINT = "https://api.tavily.com/search"
VIDEO_PATTERNS = re.compile(r"/(video|videos|watch|live|podcast)/", re.I)

# All tests exclude the video-heavy hosts
EXCLUDE = ["cbsnews.com", "cnn.com", "foxnews.com", "nbcnews.com",
           "modernghana.com", "tipranks.com", "timesofindia.indiatimes.com"]


SCENARIOS = [
    # (label, payload extras)
    ("A. text query 'npr/reuters', no domain filter",
     {"query": "top world news headlines today from npr reuters"}),
    ("B. text query + include_domains NPR+Reuters",
     {"query": "top world news headlines today",
      "include_domains": ["npr.org", "reuters.com"]}),
    ("C. text query + exclude_domains video junk",
     {"query": "major world news headlines today",
      "exclude_domains": EXCLUDE}),
    ("D. include_domains NPR+Reuters+AP+BBC+Guardian",
     {"query": "top news stories today",
      "include_domains": ["npr.org", "reuters.com", "apnews.com", "bbc.com", "theguardian.com"]}),
    ("E. include_domains NPR+Reuters only, generic query",
     {"query": "news today",
      "include_domains": ["npr.org", "reuters.com"]}),
]


def run(payload_extras: dict) -> dict:
    payload = {
        "api_key": TAVILY_KEY,
        "topic": "news",
        "days": 3,
        "search_depth": "advanced",
        "include_raw_content": True,
        "include_images": True,
        "include_image_descriptions": True,
        "max_results": 15,
        **payload_extras,
    }
    r = requests.post(ENDPOINT, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def summarize(label: str, payload_extras: dict, resp: dict) -> None:
    results = resp.get("results", []) or []
    images = resp.get("images", []) or []
    video = sum(1 for r in results if VIDEO_PATTERNS.search(r.get("url") or ""))
    good = sum(1 for r in results
               if not VIDEO_PATTERNS.search(r.get("url") or "")
               and len((r.get("raw_content") or "").split()) >= 300)

    print(f"\n### {label}")
    print(f"Query: `{payload_extras.get('query', '')}`")
    if "include_domains" in payload_extras:
        print(f"Include domains: {payload_extras['include_domains']}")
    if "exclude_domains" in payload_extras:
        print(f"Exclude domains: {payload_extras['exclude_domains']}")
    print(f"Results: **{len(results)}** · Non-video text ≥300w: **{good}** · Video: **{video}** · Imgs: **{len(images)}**")
    print()
    print("| # | Host | Video? | Words | Title |")
    print("|---|---|---|---|---|")
    for i, r in enumerate(results[:10], 1):
        url = r.get("url") or ""
        host = urlparse(url).netloc.replace("www.", "")[:24]
        raw = r.get("raw_content") or ""
        words = len(raw.split()) if raw else 0
        v = "🎥" if VIDEO_PATTERNS.search(url) else ""
        title = (r.get("title") or "").replace("|", "\\|")[:55]
        print(f"| {i} | {host} | {v} | {words} | {title} |")


def main() -> None:
    print(f"# News shootout — {len(SCENARIOS)} scenarios\n")
    for label, extras in SCENARIOS:
        try:
            summarize(label, extras, run(extras))
        except requests.HTTPError as e:
            print(f"\n### {label} — HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            print(f"\n### {label} — error: {e}")


if __name__ == "__main__":
    main()
