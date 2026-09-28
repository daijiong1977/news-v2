"""Contracts for the numeric-only whole-News comparison (no API calls)."""
import json

from pipeline.news_global_rank import rerank_news_catalog


def _brief(n, source=None, pick=.7, topic=None):
    b = {"title": f"Story {n}", "summary": f"Brief {n}",
         "_source_name": source or f"Source {n % 4}",
         "_jev_rank": {"send": n <= 6, "editorial_pick": pick, "pos": n}}
    if topic:
        b["_jev_topic_group"] = topic
    return b


def test_numbered_list_changes_shortlist_and_keeps_full_catalog():
    catalog = [_brief(i) for i in range(1, 9)]
    seen = {}

    def call(system, user, **kwargs):
        seen["payload"] = json.loads(user)
        seen["kwargs"] = kwargs
        return [8, 7, 6, 5, 4, 3, 2, 1]

    out, report = rerank_news_catalog(catalog, ["Older news"], call=call)
    assert report == {"status": "applied", "compared": 8, "sent": 6}
    assert [b["title"] for b in out] == [f"Story {i}" for i in range(8, 0, -1)]
    assert len(out) == len(catalog)
    assert seen["kwargs"]["json_mode"] is False
    assert seen["payload"]["published_news_titles_prior_7d"] == ["Older news"]
    assert [b["title"] for b in out if b["_jev_rank"]["send"]] == [
        "Story 8", "Story 7", "Story 6", "Story 5", "Story 4", "Story 3"]


def test_bad_or_partial_response_keeps_jev_order_and_flags():
    for answer in ([1, 1, 3], [1, 2], [1, 2, "3"], {"ranking": [1, 2, 3]}):
        catalog = [_brief(i) for i in range(1, 4)]
        original_flags = [b["_jev_rank"]["send"] for b in catalog]
        out, report = rerank_news_catalog(catalog, [], call=lambda *_a, **_k: answer)
        assert out is catalog
        assert report["status"] == "ignored"
        assert [b["_jev_rank"]["send"] for b in out] == original_flags


def test_only_29_numbers_sent_but_deeper_refill_candidates_survive():
    catalog = [_brief(i) for i in range(1, 36)]

    def call(_system, user, **_kwargs):
        assert len(json.loads(user)["candidates"]) == 29
        return list(range(29, 0, -1))

    out, report = rerank_news_catalog(catalog, [], call=call)
    assert report["compared"] == 29
    assert len(out) == 35
    assert [b["title"] for b in out[-6:]] == [f"Story {i}" for i in range(30, 36)]
    assert not any(b["_jev_rank"]["send"] for b in out[-6:])


def test_shortlist_does_not_take_six_from_one_source():
    catalog = [_brief(i, source="A" if i <= 6 else chr(65 + i - 6))
               for i in range(1, 10)]
    out, report = rerank_news_catalog(catalog, [],
                                      call=lambda *_a, **_k: list(range(1, 10)))
    assert report["sent"] == 6
    sent = [b for b in out if b["_jev_rank"]["send"]]
    assert sum(b["_source_name"] == "A" for b in sent) <= 3
    assert len({b["_source_name"] for b in sent}) >= 3
