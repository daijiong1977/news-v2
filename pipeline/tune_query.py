"""Tavily query shoot-out across all 3 categories.

Usage:
    source .venv/bin/activate
    python -m pipeline.tune_query

Runs 3 candidate queries per category and prints a consolidated markdown
comparison so we can pick the best phrasing for each category.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

TAVILY_KEY = os.environ["TAVILY_API_KEY"]
TAVILY_ENDPOINT = "https://api.tavily.com/search"

# 3 candidate queries per category. Idea:
# - variation 1: "hot/top" framing
# - variation 2: "cool/coolest" framing
# - variation 3: slightly different / more topical
QUERIES: dict[str, list[str]] = {
    "News": [
        "top 5 hottest news today",
        "biggest most important news stories happening today",
        "top kids-appropriate news stories today",
    ],
    "Science": [
        "coolest science discoveries this week",
        "mind blowing science news kids this week",
        "amazing new science stories today",
    ],
    "Fun (toys/inventors)": [
        "coolest new toys for this week",
        "young inventors creative new toy release news this week",
        "best new kids toys and inventions launching this week",
    ],
}


def run(query: str, days: int = 7) -> dict:
    payload = {
        "api_key": TAVILY_KEY,
        "query": query,
        "topic": "news",
        "days": days,
        "search_depth": "advanced",
        "include_raw_content": True,
        "include_images": True,
        "include_image_descriptions": True,
        "max_results": 10,
    }
    r = requests.post(TAVILY_ENDPOINT, json=payload, timeout=45)
    r.raise_for_status()
    return r.json()


def summarize_query(category: str, query: str, resp: dict) -> None:
    results = resp.get("results", []) or []
    images = resp.get("images", []) or []

    # Counts
    good_article_count = 0
    for r in results:
        raw = r.get("raw_content") or ""
        words = len(raw.split()) if raw else 0
        path = urlparse(r.get("url", "")).path
        chars = sum(1 for ch in path if ch != "/")
        # Article-shaped + has real content
        if words >= 200 and chars >= 15 and ("-" in path or any(c.isdigit() for c in path)):
            good_article_count += 1

    print(f"\n### `{category}` — query: *{query}*")
    print(f"Results: **{len(results)}** · Article-shaped: **{good_article_count}** · Images: **{len(images)}**")
    print()
    print("| # | Host | Title | Words |")
    print("|---|---|---|---|")
    for i, r in enumerate(results[:6], 1):
        url = r.get("url", "")
        host = urlparse(url).netloc.replace("www.", "")[:22]
        title = (r.get("title") or "").replace("|", "\\|")[:70]
        raw = r.get("raw_content") or ""
        words = len(raw.split()) if raw else 0
        print(f"| {i} | {host} | {title} | {words} |")


def main() -> None:
    print(f"# Tavily query shoot-out — {len(sum(QUERIES.values(), []))} queries total")
    for category, query_list in QUERIES.items():
        print(f"\n## Category: {category}")
        for q in query_list:
            try:
                resp = run(q)
                summarize_query(category, q, resp)
            except requests.HTTPError as e:
                print(f"\n### `{category}` — query: *{q}* — HTTP error {e.response.status_code}")
            except Exception as e:
                print(f"\n### `{category}` — query: *{q}* — error: {e}")


if __name__ == "__main__":
    main()
