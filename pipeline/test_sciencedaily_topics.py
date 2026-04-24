"""Shootout for ScienceDaily topic RSS feeds."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import feedparser
import requests

from .cleaner import extract_article_from_html

for _line in open("/Users/jiong/myprojects/news-v2/.env"):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

FEEDS = [
    ("Top News",           "https://www.sciencedaily.com/rss/top.xml"),
    ("Top Science",        "https://www.sciencedaily.com/rss/top/science.xml"),
    ("Top Health",         "https://www.sciencedaily.com/rss/top/health.xml"),
    ("Top Technology",     "https://www.sciencedaily.com/rss/top/technology.xml"),
    ("Top Environment",    "https://www.sciencedaily.com/rss/top/environment.xml"),
    ("Top Society",        "https://www.sciencedaily.com/rss/top/society.xml"),
    ("Strange & Offbeat",  "https://www.sciencedaily.com/rss/strange_offbeat.xml"),
    ("Most Popular",       "https://www.sciencedaily.com/rss/most_popular.xml"),
]


def main() -> None:
    print("# ScienceDaily topic feeds shootout\n")
    print("| Feed | Entries | 1st body | og:image | Sample titles |")
    print("|---|---|---|---|---|")
    for name, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
        except Exception as e:
            print(f"| {name} | 0 | parse fail: {e} | — | — |")
            continue
        entries = feed.entries[:5]
        if not entries:
            print(f"| {name} | 0 | no entries | — | — |")
            continue
        titles = [getattr(e, "title", "")[:55] for e in entries[:2]]
        link = getattr(entries[0], "link", "")
        words = 0
        has_img = False
        try:
            r = requests.get(link, headers=HEADERS, timeout=15)
            if r.ok:
                ex = extract_article_from_html(link, r.text)
                words = len((ex.get("cleaned_body") or "").split())
                has_img = bool(ex.get("og_image"))
        except Exception:
            pass
        img = "✓" if has_img else "—"
        samples = " · ".join(t.replace("|", "\\|") for t in titles)
        print(f"| {name} | {len(feed.entries)} | {words}w | {img} | {samples} |")


if __name__ == "__main__":
    main()
