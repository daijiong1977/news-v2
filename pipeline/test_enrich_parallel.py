"""Bounded category parallelism for the mega enrichment stage."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from pipeline import full_round as fr
from pipeline import news_rss_core as core


def test_two_categories_enrich_concurrently_and_keep_slots():
    barrier = Barrier(2)
    stories = {"News": [{}], "Fun": [{}]}
    variants = {"News": {0: {"category": "News"}},
                "Fun": {0: {"category": "Fun"}}}

    def fake_enrich(payload):
        barrier.wait(timeout=2)  # a serial implementation would time out
        cat = payload["articles"][0]["category"]
        return {"details": {"0_easy": {"cat": cat},
                            "0_middle": {"cat": cat}}}

    out, failures, partial, durations = fr.enrich_survivors(
        stories, variants, max_workers=2, enrich_fn=fake_enrich)
    assert failures == [] and partial == []
    assert out["News"]["0_easy"]["cat"] == "News"
    assert out["Fun"]["0_middle"]["cat"] == "Fun"
    assert set(durations) == {"News", "Fun"}


def test_serial_fallback_and_partial_failure_reporting():
    stories = {"News": [{}], "Science": [{}], "Fun": []}
    # Checkpoint JSON turns integer variant keys into strings on resume.
    variants = {"News": {"0": {"category": "News"}},
                "Science": {"0": {"category": "Science"}}}

    def fake_enrich(payload):
        if payload["articles"][0]["category"] == "News":
            raise RuntimeError("provider down")
        return {"details": {"0_easy": {"keywords": []}}}

    out, failures, partial, durations = fr.enrich_survivors(
        stories, variants, max_workers=1, enrich_fn=fake_enrich)
    assert out["Fun"] == {} and out["News"] == {}
    assert len(failures) == 1 and failures[0].startswith("News:")
    assert partial == [("Science", 1, 2)]
    assert set(durations) == {"Science"}


def test_call_stats_are_safe_under_concurrent_enrich():
    core.reset_call_stats()
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda _: core._bump_call_stat("reasoner_calls"), range(800)))
    assert core.CALL_STATS["reasoner_calls"] == 800
    core.reset_call_stats()


def _run_all():
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            test()
            print(f"  PASS {name}")


if __name__ == "__main__":
    _run_all()
