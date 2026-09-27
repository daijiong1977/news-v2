"""RSS network fetch is bounded before feedparser sees the response bytes."""

from types import SimpleNamespace

import requests

from pipeline import news_rss_core as core


RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>World</title>
<item><title>First story</title><link>https://example.org/one</link>
<description>Summary one</description></item>
<item><title>Second story</title><link>https://example.org/two</link></item>
</channel></rss>"""


def test_rss_fetch_uses_bounded_http_then_parses_bytes(monkeypatch):
    seen = {}

    def get(url, *, timeout, headers):
        seen.update(url=url, timeout=timeout, headers=headers)
        return SimpleNamespace(content=RSS, raise_for_status=lambda: None)

    monkeypatch.setattr(core.requests, "get", get)
    rows = core.fetch_rss_entries("https://example.org/rss", max_entries=1)
    assert seen["timeout"] == core.RSS_FETCH_TIMEOUT
    assert seen["headers"] == core.RSS_FETCH_HEADERS
    assert seen["headers"]["User-Agent"] != core.HTML_FETCH_HEADERS["User-Agent"]
    assert rows == [{"title": "First story", "link": "https://example.org/one",
                     "published": "", "summary": "Summary one"}]


def test_rss_timeout_leaves_other_sources_available(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("feed stalled")

    monkeypatch.setattr(core.requests, "get", timeout)
    assert core.fetch_rss_entries("https://example.org/rss") == []


def test_rss_http_error_does_not_parse_error_page(monkeypatch):
    def fail():
        raise requests.HTTPError("403")

    monkeypatch.setattr(core.requests, "get", lambda *a, **k: SimpleNamespace(
        content=b"<html>blocked</html>", raise_for_status=fail))
    assert core.fetch_rss_entries("https://example.org/rss") == []
