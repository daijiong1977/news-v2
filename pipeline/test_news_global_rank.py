"""Contracts for the numeric-only whole-News comparison (no API calls)."""
import json

from pipeline.news_global_rank import rerank_news_catalog
from pipeline.jev_rank import for_curator
from pipeline.mega_curator import MEGA_CURATOR_SYSTEM_PROMPT, _build_mega_curator_input


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


def test_only_30_numbers_sent_but_deeper_refill_candidates_survive():
    catalog = [_brief(i) for i in range(1, 36)]

    def call(_system, user, **_kwargs):
        assert len(json.loads(user)["candidates"]) == 30
        return list(range(30, 0, -1))

    out, report = rerank_news_catalog(catalog, [], call=call)
    assert report["compared"] == 30
    assert len(out) == 35
    assert [b["title"] for b in out[-5:]] == [f"Story {i}" for i in range(31, 36)]
    assert not any(b["_jev_rank"]["send"] for b in out[-5:])


def test_shortlist_does_not_take_six_from_one_source():
    catalog = [_brief(i, source="A" if i <= 6 else chr(65 + i - 6))
               for i in range(1, 10)]
    out, report = rerank_news_catalog(catalog, [],
                                      call=lambda *_a, **_k: list(range(1, 10)))
    assert report["sent"] == 6
    sent = [b for b in out if b["_jev_rank"]["send"]]
    assert sum(b["_source_name"] == "A" for b in sent) <= 3
    assert len({b["_source_name"] for b in sent}) >= 3


def test_qualified_major_news_is_reserved_before_same_source_cap():
    catalog = [_brief(i, source="PBS" if i <= 3 else f"Outlet {i}")
               for i in range(1, 9)]
    major = catalog[2]
    major["_jev_rank"].update(section_value=2.54, category_fit=.8, floor=.4)
    ranked, report = rerank_news_catalog(
        catalog, [], call=lambda *_a, **_k: list(range(1, 9)))
    sent = for_curator({"News": ranked})["News"]
    assert report["sent"] == 6
    assert major in sent
    assert catalog[0] in sent and catalog[1] not in sent
    assert [b["title"] for b in sent] == ["Story 1", "Story 3", "Story 4",
                                           "Story 5", "Story 6", "Story 7"]
    assert "SINGLE most" in MEGA_CURATOR_SYSTEM_PROMPT


def test_low_quality_or_wrong_section_major_is_not_reserved():
    for fit, pick in ((.5, .7), (.9, .3)):
        catalog = [_brief(i, source="PBS" if i <= 3 else f"Outlet {i}")
                   for i in range(1, 9)]
        catalog[2]["_jev_rank"].update(section_value=4, category_fit=fit,
                                       editorial_pick=pick, floor=.4)
        ranked, _ = rerank_news_catalog(
            catalog, [], call=lambda *_a, **_k: list(range(1, 9)))
        sent = for_curator({"News": ranked})["News"]
        assert catalog[2] not in sent


def test_global_news_shortlist_survives_later_topic_swap():
    catalog = [_brief(i, topic="us_politics" if i <= 2 else "international_relations")
               for i in range(1, 8)]
    catalog[-1]["_jev_topic_group"] = "severe_weather"
    catalog[-1]["_jev_rank"]["editorial_pick"] = .9
    ranked, _ = rerank_news_catalog(catalog, [],
                                    call=lambda *_a, **_k: list(range(1, 8)))
    expected = [b for b in ranked if b["_jev_rank"]["send"]]
    assert for_curator({"News": ranked})["News"] == expected


def test_curator_sees_global_news_rank_without_accepting_model_titles():
    ranked, _ = rerank_news_catalog([_brief(1), _brief(2)], [],
                                    call=lambda *_a, **_k: [2, 1])
    message, registry = _build_mega_curator_input({"News": for_curator({"News": ranked})["News"]})
    assert "global_rank=1" in message and "global_rank=2" in message
    assert {entry["brief"]["title"] for entry in registry.values()} == {"Story 1", "Story 2"}
