"""Tests for reactive deep-dig backfill (2026-07-11).

Owner: when a category ends short (1-2 stories after dedup/safety/image),
dig DEEPER into that day's same sources — pull items 5..15 of each feed
(the initial phase_a only fetched 4/source) and try those as fresh
candidates — BEFORE falling back to yesterday's carry-over.

`_deep_dig_spares` fetches deeper feed items, drops already-seen links,
interleaves across sources, and wraps each as an unverified Stage-3 spare
(same promote_spare_and_rewrite gate: body/image verify + safety vet +
title-dedup vs shipped).

Run: python -m pipeline.test_deep_dig   (also works under pytest)
"""
from __future__ import annotations

from pipeline import full_round as fr
from pipeline import news_rss_core as core


class _Src:
    def __init__(self, name): self.name = name


def _entries(*title_link):
    return [{"title": t, "link": l, "summary": "", "published": ""}
            for t, l in title_link]


def _with_feeds(feeds, fn):
    orig = core.fetch_source_entries
    core.fetch_source_entries = lambda source, max_entries=25: \
        feeds.get(source.name, [])[:max_entries]
    try:
        return fn()
    finally:
        core.fetch_source_entries = orig


def test_excludes_seen_links_and_interleaves():
    feeds = {"NPR": _entries(("a1", "/a1"), ("a2", "/a2"), ("a3", "/a3")),
             "BBC": _entries(("b1", "/b1"), ("b2", "/b2"))}
    spares = _with_feeds(feeds, lambda: fr._deep_dig_spares(
        "News", [_Src("NPR"), _Src("BBC")],
        exclude_links={"/a1", "/b1"}, max_per_source=15))
    links = [s["_winner_brief"]["link"] for s in spares]
    assert "/a1" not in links and "/b1" not in links      # already-seen excluded
    assert set(links) == {"/a2", "/a3", "/b2"}
    assert links[0] == "/a2" and links[1] == "/b2"        # round-robin by source
    for s in spares:
        assert s["_unverified_spare"] is True
        assert s["source"].name == s["_winner_brief"]["_source_name"]
        assert str(s["_rank"]).startswith("dig")


def test_dedups_same_link_across_sources():
    feeds = {"A": _entries(("x", "/dup")),
             "B": _entries(("x2", "/dup"), ("y", "/y"))}
    spares = _with_feeds(feeds, lambda: fr._deep_dig_spares(
        "News", [_Src("A"), _Src("B")], exclude_links=set()))
    links = [s["_winner_brief"]["link"] for s in spares]
    assert links.count("/dup") == 1 and "/y" in links


def test_fetch_failure_is_non_fatal():
    def boom(source, max_entries=25):
        if source.name == "BAD":
            raise RuntimeError("feed down")
        return _entries(("ok", "/ok"))
    orig = core.fetch_source_entries
    core.fetch_source_entries = boom
    try:
        spares = fr._deep_dig_spares("News", [_Src("BAD"), _Src("GOOD")],
                                     exclude_links=set())
    finally:
        core.fetch_source_entries = orig
    assert [s["_winner_brief"]["link"] for s in spares] == ["/ok"]


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
