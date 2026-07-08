"""Tests for the filtering/pickup polish batch (2026-07-08).

Covers:
  1. Forbidden filter: chat-slang acronyms \basl\b / \bcd9\b removed (they
     killed "ASL interpreter" / band-news headlines); real predator slang and
     the documented gambling editorial choice remain.
  2. verify_article_content: missing og:image reports "no og:image" (the
     generic-image check shadowed it — unreachable branch, lying telemetry).
  3. Cadence estimator: burst publishers no longer collapse to cadence=1
     (median of intra-burst gaps); per-run change is clamped.
  4. Scraper html_list titles: image-only anchors fall back to img alt /
     aria-label / URL slug (DOGOnews shipped empty titles).
  5. load_sources honors active_weekdays and prefers non-backup sources.

Run: python -m pipeline.test_filter_polish   (also works under pytest)
"""
from __future__ import annotations

from datetime import date

from pipeline.forbidden_filter import is_forbidden
from pipeline import news_rss_core as core
from pipeline import cadence_calibrate as cad
from pipeline import scraper
from pipeline import db_config


# ── 1. forbidden filter ──

def test_asl_and_cd9_no_longer_forbidden():
    assert is_forbidden("Deaf students cheer new ASL interpreter program")[0] is False
    assert is_forbidden("CD9 announces reunion tour")[0] is False


def test_real_slang_and_editorial_choices_still_forbidden():
    assert is_forbidden("teens using gnoc online")[0] is True
    assert is_forbidden("new casino opens downtown")[0] is True     # documented editorial choice
    assert is_forbidden("betting on the game")[0] is True           # ditto — deliberately kept


# ── 2. image quality: reject a missing/generic image, keep a real one ──

def test_missing_image_rejected():
    # Owner choice (2026-07-08): a real photo matters — reject rather than ship
    # a blank/wrong card. Missing image → reject, honest reason.
    art = {"word_count": (core.MIN_PICK_BODY_WORDS + core.MAX_PICK_BODY_WORDS) // 2,
           "og_image": None}
    ok, reason = core.verify_article_content(art)
    assert ok is False and reason == "no og:image"


def test_generic_image_rejected():
    # NPR's facebook-default (generic branding) image → reject (don't ship the
    # wrong photo). The safety loosening keeps News filled from real-image sources.
    art = {"word_count": (core.MIN_PICK_BODY_WORDS + core.MAX_PICK_BODY_WORDS) // 2,
           "og_image": "https://media.npr.org/include/images/facebook-default-wide.jpg"}
    ok, reason = core.verify_article_content(art)
    assert ok is False and "generic social image" in reason


def test_real_image_kept():
    art = {"word_count": (core.MIN_PICK_BODY_WORDS + core.MAX_PICK_BODY_WORDS) // 2,
           "og_image": "https://example.com/real-article-photo.jpg"}
    ok, reason = core.verify_article_content(art)
    assert ok is True and reason is None


# ── 3. cadence estimator ──

def _ts(days_ago: float) -> float:
    return 1_800_000_000.0 - days_ago * 86400.0


def test_burst_publisher_not_collapsed_to_daily():
    # 9 posts within one hour, then nothing for 14 days: median gap ≈ 0 but
    # the feed's real rhythm is a burst every ~2 weeks.
    dates = sorted([_ts(0.001 * i) for i in range(9)] + [_ts(14)], reverse=True)
    c = cad.compute_cadence_days(dates)
    assert c is not None and c >= 2, f"burst feed got cadence {c}"


def test_daily_publisher_still_daily():
    dates = [_ts(i) for i in range(10)]     # one post per day
    assert cad.compute_cadence_days(dates) == 1


def test_cadence_step_clamped():
    assert cad._clamp_step(old=1, new=30) == 3      # max +2 per run
    assert cad._clamp_step(old=10, new=1) == 8      # max -2 per run
    assert cad._clamp_step(old=3, new=4) == 4       # small moves untouched


# ── 4. scraper html_list titles ──

def test_title_falls_back_to_img_alt_and_slug():
    from bs4 import BeautifulSoup
    html = ('<a href="/articles/penguins-learn-to-surf">'
            '<img src="x.jpg" alt="Penguins learn to surf"></a>')
    el = BeautifulSoup(html, "lxml").find("a")
    t = scraper._derive_title(el, el, "https://x.com/articles/penguins-learn-to-surf", None)
    assert t == "Penguins learn to surf"

    html2 = '<a href="/articles/robot-dog-rescue"></a>'   # no text, no img
    el2 = BeautifulSoup(html2, "lxml").find("a")
    t2 = scraper._derive_title(el2, el2, "https://x.com/articles/robot-dog-rescue", None)
    assert t2.lower() == "robot dog rescue"


# ── 5. load_sources: active_weekdays + backup tier ──

_ids = iter(range(1000, 2000))

def _row(name, backup=False, weekdays=None):
    return {"id": next(_ids),
            "name": name, "category": "News", "rss_url": f"https://x/{name}",
            "enabled": True, "state": "live", "is_backup": backup,
            "active_weekdays": weekdays, "priority": 1, "cadence_days": 1,
            "next_pickup_at": None, "last_used_at": None,
            "flow": "full", "feed_kind": "rss", "feed_config": None,
            "max_to_vet": 6, "min_body_words": 300}


def _with_rows(rows, fn):
    orig = db_config._ensure_src_cache
    db_config._ensure_src_cache = lambda: {"News": rows}
    try:
        return fn()
    finally:
        db_config._ensure_src_cache = orig


def test_active_weekdays_gates_eligibility():
    tuesday = date(2026, 7, 7)   # weekday() == 1
    rows = [_row("MonOnly", weekdays=[0]), _row("TueOnly", weekdays=[1]),
            _row("AllDays", weekdays=None)]
    picked = _with_rows(rows, lambda: db_config.load_sources("News", today=tuesday, n=5))
    names = [s.name for s in picked]
    assert "MonOnly" not in names
    assert "TueOnly" in names and "AllDays" in names


def test_backups_fill_only_after_primaries():
    today = date(2026, 7, 7)
    rows = [_row("P1"), _row("P2"), _row("B1", backup=True)]
    two = _with_rows(rows, lambda: db_config.load_sources("News", today=today, n=2))
    assert [s.name for s in two] == ["P1", "P2"]          # backup not needed
    three = _with_rows(rows, lambda: db_config.load_sources("News", today=today, n=3))
    assert [s.name for s in three][-1] == "B1"            # backup fills last


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
