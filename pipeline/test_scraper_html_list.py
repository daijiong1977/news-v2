"""Offline smoke test for pipeline.scraper html_list path + the
fetch_source_entries dispatcher.

Run: python -m pipeline.test_scraper_html_list

No network — all fetches are monkey-patched. Asserts that:
  1. _from_html_list parses an inline DOGOnews-shaped listing page
     correctly (article URLs extracted, junk filtered).
  2. fetch_source_entries dispatches to the right backend by feed_kind
     and returns the unified {title, link, published, summary} shape.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import patch

from . import scraper
from .news_rss_core import fetch_source_entries
from .news_sources import NewsSource

# A fixture mimicking a kid-news listing page. Two real article anchors,
# one bad anchor (different host), one excluded by exclude_pattern, and
# duplicate of the first.
LIST_PAGE_HTML = """
<html><body>
  <article>
    <a href="/2026/5/3/giraffes-can-hum">Scientists discover giraffes can hum</a>
  </article>
  <article>
    <a href="/2026/5/2/space-elevator">Could a space elevator work?</a>
  </article>
  <article>
    <a href="/games/some-game">Play this game</a>  <!-- excluded -->
  </article>
  <a href="https://other-site.com/external">External link</a>  <!-- different host -->
  <article>
    <a href="/2026/5/3/giraffes-can-hum">Same as #1</a>  <!-- duplicate -->
  </article>
</body></html>
"""


def fake_fetch(url, timeout=20):
    return LIST_PAGE_HTML, "text/html", url


def test_html_list_extraction() -> None:
    src = {
        "rss_url": "https://www.dogonews.com/",
        "feed_kind": "html_list",
        "feed_config": json.dumps({
            "article_selector": "article a",
            "exclude_pattern": "/games/",
        }),
    }
    with patch.object(scraper, "_fetch", side_effect=fake_fetch):
        items = scraper.discover_article_urls(src, top_n=5)

    assert len(items) == 2, f"expected 2 unique articles, got {len(items)}: {items}"
    urls = [i["url"] for i in items]
    assert urls[0] == "https://www.dogonews.com/2026/5/3/giraffes-can-hum"
    assert urls[1] == "https://www.dogonews.com/2026/5/2/space-elevator"
    assert all("title" in i and "url" in i for i in items)
    assert all(not i["url"].startswith("https://other-site.com") for i in items)
    assert all("/games/" not in i["url"] for i in items)
    print("PASS: _from_html_list extracted 2 unique same-host article URLs, junk filtered")


def test_dispatcher_html_list() -> None:
    """fetch_source_entries(NewsSource(feed_kind=html_list)) returns
    the unified {title, link, published, summary} shape."""
    src = NewsSource(
        id=999, name="DOGOnews-test",
        rss_url="https://www.dogonews.com/",
        flow="full", max_to_vet=5, min_body_words=200,
        priority=99, enabled=True, is_backup=False,
        feed_kind="html_list",
        feed_config=json.dumps({
            "article_selector": "article a",
            "exclude_pattern": "/games/",
        }),
    )
    with patch.object(scraper, "_fetch", side_effect=fake_fetch):
        entries = fetch_source_entries(src, max_entries=5)

    assert len(entries) == 2, f"expected 2 entries, got {len(entries)}"
    e0 = entries[0]
    assert set(e0.keys()) == {"title", "link", "published", "summary"}, \
        f"shape mismatch: {e0.keys()}"
    assert e0["link"] == "https://www.dogonews.com/2026/5/3/giraffes-can-hum"
    assert e0["title"] == "Scientists discover giraffes can hum"
    print("PASS: fetch_source_entries returned 2 shape-compatible dicts for html_list")


def test_dispatcher_rss_unchanged() -> None:
    """fetch_source_entries with feed_kind='rss' (default) delegates to
    fetch_rss_entries — the existing path is untouched."""
    src = NewsSource(
        id=1, name="rss-test",
        rss_url="https://example.com/feed.xml",
        flow="full", max_to_vet=5, min_body_words=200,
        priority=99, enabled=True, is_backup=False,
        # feed_kind defaults to "rss"
    )
    sentinel = [{"title": "x", "link": "https://x", "published": "", "summary": ""}]
    with patch("pipeline.news_rss_core.fetch_rss_entries", return_value=sentinel) as m:
        entries = fetch_source_entries(src, max_entries=5)

    m.assert_called_once_with("https://example.com/feed.xml", 5, 5.0)
    assert entries is sentinel
    print("PASS: feed_kind='rss' (default) delegates to fetch_rss_entries unchanged")


def main() -> int:
    try:
        test_html_list_extraction()
        test_dispatcher_html_list()
        test_dispatcher_rss_unchanged()
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("\nAll 3 tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
