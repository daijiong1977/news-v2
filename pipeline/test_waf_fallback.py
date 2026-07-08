"""Tests for AWS-WAF bot-challenge detection (PBS fetch fix).

PBS put its article pages behind AWS WAF (a JavaScript challenge). A plain
`requests.get` receives a ~2KB challenge stub instead of the article, so every
PBS article extracted to 0 words and was dropped — PBS shipped 0 stories for a
month. The WAF allowlists Googlebot, so `fetch_html` detects the challenge and
refetches once with a Googlebot UA.

This file unit-tests the pure detector. The Googlebot refetch itself is network
and is verified separately against the live feed.

Run: python -m pipeline.test_waf_fallback   (needs the repo venv: feedparser/requests)
"""
from __future__ import annotations

from pipeline.news_rss_core import is_bot_challenge_page

# Minimal but representative AWS WAF challenge stub (PBS, captured 2026-07).
WAF_STUB = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title></title>'
    '<script type="text/javascript">'
    'window.awsWafCookieDomainList = [];'
    'window.gokuProps = {"key":"AQ...","iv":"D5...","context":"Z0..."};'
    '</script>'
    '<script src="https://de6588ed7367.token.awswaf.com/xxx/challenge.js"></script>'
    '</head><body><div id="challenge-container"></div>'
    '<script>AwsWafIntegration.saveReferrer();</script>'
    "<noscript><h1>JavaScript is disabled</h1>we need to verify that you're not a robot.</noscript>"
    '</body></html>'
)

# A normal, server-rendered article page.
REAL_PAGE = (
    '<!DOCTYPE html><html><head>'
    '<meta property="og:image" content="https://img.example/x.jpg">'
    '</head><body><article><p>' + ("word " * 400) + '</p></article></body></html>'
)


def test_detects_aws_waf_challenge():
    assert is_bot_challenge_page(WAF_STUB) is True


def test_real_article_is_not_a_challenge():
    assert is_bot_challenge_page(REAL_PAGE) is False


def test_empty_or_none_is_not_a_challenge():
    assert is_bot_challenge_page("") is False
    assert is_bot_challenge_page(None) is False


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
