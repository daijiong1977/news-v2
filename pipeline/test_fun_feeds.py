"""Shoot-out for Fun weekday feeds. BBC Tennis wants 3x/week."""
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

CANDIDATES = [
    ("Mon · Music", [
        ("NPR Music",             "https://feeds.npr.org/1039/rss.xml"),
        ("Pitchfork",             "https://pitchfork.com/rss/news/"),
        ("Rolling Stone Music",   "https://www.rollingstone.com/music/feed/"),
        ("Billboard",             "https://www.billboard.com/feed/"),
    ]),
    ("Tue · Swimming / Water sports (+ tennis)", [
        ("SwimSwam",              "https://swimswam.com/feed/"),
        ("BBC Tennis",            "https://feeds.bbci.co.uk/sport/tennis/rss.xml"),
        ("World Aquatics News",   "https://www.worldaquatics.com/news/rss/latest"),
    ]),
    ("Wed · Movies / TV", [
        ("Variety",               "https://variety.com/feed/"),
        ("Hollywood Reporter",    "https://www.hollywoodreporter.com/feed/"),
        ("/Film",                 "https://www.slashfilm.com/feed/"),
        ("IndieWire",             "https://www.indiewire.com/feed/"),
    ]),
    ("Thu · Inventions / kid inventors / toys", [
        ("Wired Gear",            "https://www.wired.com/feed/category/gear/latest/rss"),
        ("Popular Mechanics",     "https://www.popularmechanics.com/rss/all.xml"),
        ("MIT News",              "https://news.mit.edu/rss/feed"),
        ("Mashable Tech",         "https://mashable.com/feeds/rss/tech"),
    ]),
    ("Fri · Arts / Crafts", [
        ("Guardian Art & Design", "https://www.theguardian.com/artanddesign/rss"),
        ("Smithsonian Arts",      "https://www.smithsonianmag.com/rss/arts-culture/"),
        ("Hyperallergic",         "https://hyperallergic.com/feed/"),
    ]),
    ("Sat · Animals / Famous person / History (+ tennis)", [
        ("BBC Tennis",            "https://feeds.bbci.co.uk/sport/tennis/rss.xml"),
        ("History Extra",         "https://www.historyextra.com/feed/"),
        ("Live Science",          "https://www.livescience.com/feeds/all"),
        ("Smithsonian History",   "https://www.smithsonianmag.com/rss/history/"),
    ]),
    ("Sun · Video games / Esports (+ tennis)", [
        ("Polygon",               "https://www.polygon.com/rss/index.xml"),
        ("IGN",                   "https://feeds.ign.com/ign/all"),
        ("BBC Tennis",            "https://feeds.bbci.co.uk/sport/tennis/rss.xml"),
        ("Kotaku",                "https://kotaku.com/rss"),
    ]),
]


def test_feed(url: str):
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
    except Exception as e:
        return (0, [f"parse error: {e}"], None)
    entries = feed.entries[:5]
    titles = [getattr(e, "title", "")[:55] for e in entries[:3]]
    extr = None
    if entries:
        link = getattr(entries[0], "link", "")
        try:
            r = requests.get(link, headers=HEADERS, timeout=15)
            if r.status_code < 400:
                ex = extract_article_from_html(link, r.text)
                extr = {"words": len((ex.get("cleaned_body") or "").split()),
                        "og_image": bool(ex.get("og_image"))}
            else:
                extr = {"http_status": r.status_code}
        except Exception as e:
            extr = {"error": str(e)[:60]}
    return (len(feed.entries), titles, extr)


def main() -> None:
    print("# Fun RSS feed shoot-out\n")
    for day_topic, feeds in CANDIDATES:
        print(f"\n## {day_topic}")
        print("| # | Source | RSS | 1st body (w) | Img | Verdict |")
        print("|---|---|---|---|---|---|")
        for i, (name, url) in enumerate(feeds, 1):
            count, titles, extr = test_feed(url)
            if count == 0:
                verdict = "❌ parse fail"
                words = "—"
                img = "—"
            elif extr is None or extr.get("error") or extr.get("http_status"):
                verdict = f"❌ fetch: {extr.get('http_status') or extr.get('error','?')}"
                words = 0
                img = "—"
            else:
                words = extr["words"]
                img = "✓" if extr["og_image"] else "—"
                verdict = "✅ works" if (words >= 300 and extr["og_image"]) else "⚠ thin/no-image"
            print(f"| {i} | {name} | {count} | {words} | {img} | {verdict} |")
            if titles:
                print(f"|   | *samples:* {' · '.join(t.replace('|','\\|') for t in titles[:2])} | | | | |")


if __name__ == "__main__":
    main()
