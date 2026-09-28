"""Fun whole-catalog ranking is a safe, optional editorial aid."""

import json

from pipeline.fun_global_rank import rerank_fun_catalog
from pipeline.jev_rank import for_curator
from pipeline.mega_curator import _build_mega_curator_input


def _brief(n, *, source=None, pick=.7, topic=None):
    brief = {"title": f"Fun story {n}", "summary": f"Brief {n}",
             "_source_name": source or f"Source {n % 4}",
             "_jev_rank": {"send": n <= 7, "editorial_pick": pick, "pos": n}}
    if topic:
        brief["_jev_topic_group"] = topic
    return brief


def test_numeric_ranking_changes_fun_shortlist_and_keeps_spares():
    catalog = [_brief(i, topic="swimming" if i == 8 else "film_tv")
               for i in range(1, 9)]
    seen = {}

    def call(system, user, **kwargs):
        seen["payload"] = json.loads(user)
        seen["kwargs"] = kwargs
        return [8, 7, 6, 5, 4, 3, 2, 1]

    out, report = rerank_fun_catalog(catalog, call=call)
    assert report == {"status": "applied", "compared": 8, "sent": 7}
    assert [b["title"] for b in out] == [f"Fun story {i}" for i in range(8, 0, -1)]
    assert len(out) == 8
    assert seen["kwargs"]["json_mode"] is False
    assert len(seen["payload"]["candidates"]) == 8
    assert [b["title"] for b in for_curator({"Fun": out})["Fun"]][0] == "Fun story 8"


def test_failed_or_malformed_response_keeps_jev_order_and_flags():
    for answer in ([1] * 8, list(range(1, 8)),
                   [1, 2, 3, 4, 5, 6, 7, "8"], {"ranking": list(range(1, 9))}):
        catalog = [_brief(i) for i in range(1, 9)]
        original_flags = [b["_jev_rank"]["send"] for b in catalog]
        out, report = rerank_fun_catalog(catalog, call=lambda *_a, **_k: answer)
        assert out is catalog
        assert report["status"] == "ignored"
        assert [b["_jev_rank"]["send"] for b in out] == original_flags


def test_only_29_compared_and_all_deeper_spares_survive():
    catalog = [_brief(i) for i in range(1, 36)]

    def call(_system, user, **_kwargs):
        assert len(json.loads(user)["candidates"]) == 29
        return list(range(29, 0, -1))

    out, report = rerank_fun_catalog(catalog, call=call)
    assert report["compared"] == 29
    assert len(out) == 35
    assert [b["title"] for b in out[-6:]] == [f"Fun story {i}" for i in range(30, 36)]
    assert not any(b["_jev_rank"]["send"] for b in out[-6:])


def test_thin_pool_skips_extra_model_call_and_preserves_jev_flags():
    catalog = [_brief(i, pick=.3) for i in range(1, 9)]
    out, report = rerank_fun_catalog(catalog,
                                     call=lambda *_a, **_k: 1 / 0)
    assert out is catalog
    assert report["status"] == "skipped_thin_pool"
    assert report["qualified"] == 0
    assert len(for_curator({"Fun": out})["Fun"]) == 7


def test_fun_rank_is_visible_to_curator_without_model_titles():
    out, _ = rerank_fun_catalog([_brief(i) for i in range(1, 9)],
                                call=lambda *_a, **_k: [8, 7, 6, 5, 4, 3, 2, 1])
    message, registry = _build_mega_curator_input({"Fun": for_curator({"Fun": out})["Fun"]})
    assert "global_rank=1" in message and "global_rank=2" in message
    assert {entry["brief"]["title"] for entry in registry.values()} == {
        f"Fun story {i}" for i in range(2, 9)}
