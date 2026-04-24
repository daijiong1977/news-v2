"""Test Guardian replacements for Friday Science (Environment/Climate) + Friday Fun (Arts)."""
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Check if image URL has a "logo overlay" signature — Guardian specifically uses
# `overlay-base64=...tg-default.png` or `overlay-base64=...tg-review.png`
def has_logo_overlay(img_url: str) -> bool:
    if not img_url:
        return False
    low = img_url.lower()
    return any(s in low for s in ("overlay-base64", "tg-default", "tg-review",
                                  "watermark", "logo=", "/logo-"))


CANDIDATES = [
    ("Friday Science (Environment / Climate) — replacing Guardian Env", [
        ("Inside Climate News",   "https://insideclimatenews.org/feed/"),
        ("Grist",                 "https://grist.org/feed/"),
        ("Yale Environment 360",  "https://e360.yale.edu/feed"),
        ("Mongabay",              "https://news.mongabay.com/feed/"),
        ("Anthropocene Mag",      "https://www.anthropocenemagazine.org/feed/"),
    ]),
    ("Friday Fun (Arts / Crafts) — replacing Guardian Art & Design", [
        ("Colossal",              "https://www.thisiscolossal.com/feed/"),
        ("Artnet News",           "https://news.artnet.com/feed"),
        ("ArtNews",               "https://www.artnews.com/feed/"),
        ("Artsy News",            "https://www.artsy.net/rss/news"),
        ("NPR Arts",              "https://feeds.npr.org/1008/rss.xml"),
    ]),
]


def test_feed(url: str):
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
    except Exception as e:
        return (0, [], None)
    entries = feed.entries[:5]
    titles = [getattr(e, "title", "")[:55] for e in entries[:3]]
    extr = None
    logo_flag = False
    if entries:
        link = getattr(entries[0], "link", "")
        try:
            r = requests.get(link, headers=HEADERS, timeout=15, allow_redirects=True)
            if r.status_code < 400:
                ex = extract_article_from_html(link, r.text)
                og_img = ex.get("og_image") or ""
                extr = {"words": len((ex.get("cleaned_body") or "").split()),
                        "og_image": og_img,
                        "has_logo": has_logo_overlay(og_img)}
                logo_flag = extr["has_logo"]
            else:
                extr = {"http_status": r.status_code}
        except Exception as e:
            extr = {"error": str(e)[:80]}
    return (len(feed.entries), titles, extr)


def main() -> None:
    print("# Replacement feed shoot-out\n")
    print("Checking body word count + og:image availability + logo-overlay detection.\n")
    for section, feeds in CANDIDATES:
        print(f"\n## {section}")
        print("| # | Source | RSS | 1st body (w) | og:image | Logo overlay? | Verdict |")
        print("|---|---|---|---|---|---|---|")
        for i, (name, url) in enumerate(feeds, 1):
            count, titles, extr = test_feed(url)
            if count == 0:
                print(f"| {i} | {name} | 0 | — | — | — | ❌ feed parse fail |")
                continue
            if extr is None or extr.get("error") or extr.get("http_status"):
                err = extr.get("http_status") or extr.get("error", "?")
                print(f"| {i} | {name} | {count} | 0 | — | — | ❌ fetch {err} |")
                continue
            words = extr["words"]
            img = "✓" if extr["og_image"] else "—"
            logo = "⚠️ yes" if extr["has_logo"] else "clean"
            ok = (words >= 300 and extr["og_image"] and not extr["has_logo"])
            verdict = "✅ good" if ok else ("⚠ thin" if words < 300 else "⚠ logo")
            print(f"| {i} | {name} | {count} | {words} | {img} | {logo} | {verdict} |")
            if titles:
                print(f"|   | *samples:* {' · '.join(t.replace('|','\\|') for t in titles[:2])} | | | | | |")


if __name__ == "__main__":
    main()
