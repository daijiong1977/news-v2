"""Test proposed Science RSS feeds — one per weekday topic.

For each feed: parse RSS, count entries, try fetching first article's HTML
to see if we can extract image + body. Report results in markdown table.
"""
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

# Candidates per topic. Each (day, topic, [(name, url), ...])
CANDIDATES = [
    ("Mon", "AI / auto", [
        ("The Verge AI",           "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("Ars Technica AI",        "https://feeds.arstechnica.com/arstechnica/ai"),
        ("MIT Tech Review",        "https://www.technologyreview.com/feed/"),
    ]),
    ("Tue", "Biology / Medicine / Health", [
        ("NPR Health",             "https://feeds.npr.org/1027/rss.xml"),
        ("ScienceDaily Plants & Animals",
                                   "https://www.sciencedaily.com/rss/plants_animals.xml"),
        ("Nature",                 "https://www.nature.com/nature.rss"),
    ]),
    ("Wed", "Space / Astronomy", [
        ("Space.com",              "https://www.space.com/feeds/all"),
        ("NASA News",              "https://www.nasa.gov/news-release/feed/"),
        ("Phys.org Space",         "https://phys.org/rss-feed/space-news/"),
    ]),
    ("Thu", "Chemistry / Physics", [
        ("ScienceDaily Physics",   "https://www.sciencedaily.com/rss/matter_energy/physics.xml"),
        ("Physics World",          "https://physicsworld.com/feed/"),
        ("Phys.org Chemistry",     "https://phys.org/rss-feed/chemistry-news/"),
    ]),
    ("Fri", "Environment / Climate", [
        ("Guardian Environment",   "https://www.theguardian.com/environment/rss"),
        ("ScienceDaily Earth/Climate",
                                   "https://www.sciencedaily.com/rss/earth_climate.xml"),
        ("Inside Climate News",    "https://insideclimatenews.org/feed/"),
    ]),
    ("Sat", "Technology / Engineering", [
        ("IEEE Spectrum",          "https://spectrum.ieee.org/feeds/feed.rss"),
        ("Popular Science",        "https://www.popsci.com/feed"),
        ("Engadget",               "https://www.engadget.com/rss.xml"),
    ]),
    ("Sun", "Nature / Geometry", [
        ("Smithsonian Science-Nature",
                                   "https://www.smithsonianmag.com/rss/science-nature/"),
        ("Atlas Obscura",          "https://www.atlasobscura.com/feed/rss"),
        ("Nautilus",               "https://nautil.us/rss/all"),
    ]),
]


def test_feed(url: str) -> tuple[int, list[str], dict | None]:
    """Returns (entry_count, sample_titles, first_entry_extraction_result)."""
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
    except Exception as e:
        return (0, [f"parse error: {e}"], None)
    entries = feed.entries[:5]
    sample_titles = [getattr(e, "title", "")[:60] for e in entries[:3]]
    first_extraction = None
    if entries:
        first = entries[0]
        link = getattr(first, "link", "")
        try:
            r = requests.get(link, headers=HEADERS, timeout=15, allow_redirects=True)
            if r.status_code < 400:
                extracted = extract_article_from_html(link, r.text)
                first_extraction = {
                    "url": link,
                    "words": len((extracted.get("cleaned_body") or "").split()),
                    "og_image": bool(extracted.get("og_image")),
                    "og_image_url": (extracted.get("og_image") or "")[:100],
                }
            else:
                first_extraction = {"url": link, "words": 0, "og_image": False,
                                    "http_status": r.status_code}
        except Exception as e:
            first_extraction = {"url": link, "words": 0, "og_image": False,
                                "error": str(e)[:80]}
    return (len(feed.entries), sample_titles, first_extraction)


def main() -> None:
    print("# Science RSS feed shoot-out\n")
    print("Testing 1 feed per topic (and 2 backups each). For each: RSS entry count + first article word count + image found.\n")

    for day, topic, candidates in CANDIDATES:
        print(f"\n## {day} · {topic}")
        print("| # | Source | RSS entries | 1st article body (w) | 1st article og:image | Verdict |")
        print("|---|---|---|---|---|---|")
        for i, (name, url) in enumerate(candidates, 1):
            count, titles, extr = test_feed(url)
            if count == 0:
                verdict = "❌ feed failed"
                words = "—"
                img = "—"
            else:
                if extr and not extr.get("error") and not extr.get("http_status"):
                    words = extr["words"]
                    img = "✓" if extr["og_image"] else "—"
                    verdict = "✅ works" if (words >= 300 and extr["og_image"]) else "⚠ thin/no-image"
                else:
                    words = 0
                    img = "—"
                    verdict = f"❌ {extr.get('http_status') or extr.get('error', 'unknown')}"
            print(f"| {i} | {name} | {count} | {words} | {img} | {verdict} |")
            if titles:
                print(f"|   | *samples:* {' · '.join(t.replace('|', '\\|') for t in titles[:2])} | | | | |")


if __name__ == "__main__":
    main()
