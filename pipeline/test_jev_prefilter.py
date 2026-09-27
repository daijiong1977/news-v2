"""Tests for the Jev pre-filter (Stage 1.2).

The rules themselves were validated offline on 35 days of checkpoints; what is
tested here is the contract the pipeline relies on: Jev is optional, and no
failure mode may drop a brief or raise.

Run: python -m pipeline.test_jev_prefilter   (also works under pytest)
"""
from __future__ import annotations

import os
import time
from types import SimpleNamespace

from pipeline import jev_prefilter as jp


def _brief(title: str, cat: str = "News") -> dict:
    return {"title": title, "summary": "s", "_category": cat, "_source_name": "Src", "link": title}


class FakeClient:
    """Scores by keyword so tests read naturally."""

    def __init__(self, fail_on: tuple[str, ...] = (), delay: float = 0.0):
        self.fail_on, self.delay, self.calls, self.closed = fail_on, delay, 0, False

    def system_one(self, state, questions):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        t = state["title"]
        if any(f in t for f in self.fail_on):
            raise RuntimeError("boom")
        ans = {
            "shopping": SimpleNamespace(noul=0.98 if "Deals" in t else 0.03),
            "harm": SimpleNamespace(score=3.6 if "massacre" in t else 2.8 if "remembrance" in t else 0.2),
            "uk_domestic": SimpleNamespace(noul=0.97 if "Tory" in t else 0.6 if "Davis Cup" in t else 0.04),
        }
        return SimpleNamespace(answers=ans)

    def close(self):
        self.closed = True


def _pool(n: int, prefix: str = "Story") -> list[dict]:
    return [_brief(f"{prefix} {i}") for i in range(n)]


def _run(briefs_by_cat, client, mode="on"):
    os.environ["JEV_PREFILTER"] = mode
    try:
        return jp.prefilter_briefs(briefs_by_cat, client=client, questions={})
    finally:
        os.environ.pop("JEV_PREFILTER", None)


def test_drops_the_four_rule_classes():
    pool = _pool(10) + [_brief("WATCH LIVE: Senate votes"), _brief("Best Grill Deals 2026"),
                        _brief("Village massacre leaves dozens dead"), _brief("Tory reshuffle: Stride out")]
    out, rep = _run({"News": pool}, FakeClient())
    titles = {b["title"] for b in out["News"]}
    assert len(titles) == 10 and all(t.startswith("Story") for t in titles)
    assert sorted(d["why"].split("=")[0] for d in rep["dropped"]) == \
        ["harm", "livestream", "shopping", "uk_domestic"]


def test_borderline_cases_are_left_for_the_curator():
    """9/11 remembrance scored 2.83 and Davis Cup 0.66 on real data: both must survive."""
    pool = _pool(10) + [_brief("A day of remembrance for the lives lost"), _brief("GB win on Davis Cup debut")]
    out, rep = _run({"News": pool}, FakeClient())
    assert len(out["News"]) == 12 and rep["dropped"] == []


def test_livestream_regex_is_narrow():
    keep = ["Alive and well: the frog that came back", "Live Aid at 40", "How to live on Mars",
            "Olive oil prices surge"]
    drop = ["WATCH LIVE: House considers bills", "Listen live: launch coverage",
            "Hurricane Lala live updates", "Election night live blog"]
    assert not any(jp.LIVE_RE.search(t) for t in keep)
    assert all(jp.LIVE_RE.search(t) for t in drop)


def test_no_api_key_keeps_everything_but_still_applies_regex():
    saved = os.environ.pop("TYPESAFE_API_KEY", None)
    try:
        pool = _pool(9) + [_brief("Best Grill Deals 2026"), _brief("WATCH LIVE: hearing")]
        out, rep = jp.prefilter_briefs({"News": pool})
    finally:
        if saved is not None:
            os.environ["TYPESAFE_API_KEY"] = saved
    assert len(out["News"]) == 10 and "IGNORED" in rep["jev"]
    assert [d["why"] for d in rep["dropped"]] == ["livestream"]
    assert not any("_jev" in b for b in out["News"])


def test_one_failed_call_keeps_that_brief():
    pool = _pool(10) + [_brief("Best Grill Deals 2026"), _brief("flaky Best Tool Deals")]
    out, rep = _run({"News": pool}, FakeClient(fail_on=("flaky",)))
    titles = {b["title"] for b in out["News"]}
    assert "flaky Best Tool Deals" in titles and "Best Grill Deals 2026" not in titles
    assert "IGNORED" not in rep["jev"]


def test_outage_discards_every_jev_decision():
    pool = [_brief(f"flaky {i}") for i in range(6)] + _pool(6) + [_brief("Best Grill Deals 2026")]
    out, rep = _run({"News": pool}, FakeClient(fail_on=("flaky",)))
    assert len(out["News"]) == len(pool) and "IGNORED" in rep["jev"]
    assert not any("_jev" in b for b in out["News"])


def test_time_budget_exceeded_keeps_everything():
    saved = jp.TIME_BUDGET_S
    jp.TIME_BUDGET_S = 0.05
    try:
        pool = _pool(12) + [_brief("Best Grill Deals 2026")]
        out, rep = _run({"News": pool}, FakeClient(delay=0.2))
    finally:
        jp.TIME_BUDGET_S = saved
    assert len(out["News"]) == len(pool) and "time budget" in rep["jev"]


def test_client_that_explodes_on_construction_is_survivable():
    class Broken:
        def system_one(self, *a, **k):
            raise SystemError("sdk bug")
    out, rep = _run({"News": _pool(5)}, Broken())
    assert len(out["News"]) == 5 and "IGNORED" in rep["jev"]


def test_starvation_guard_never_goes_below_floor():
    pool = _pool(3) + [_brief(f"Best Deals {i}") for i in range(9)]   # 12 in, 9 flagged
    out, rep = _run({"Fun": pool}, FakeClient())
    assert len(out["Fun"]) == jp.MIN_KEEP_PER_CAT
    assert rep["restored"] == 9 - (12 - jp.MIN_KEEP_PER_CAT)


def test_shadow_mode_scores_but_drops_nothing_from_jev():
    pool = _pool(10) + [_brief("Best Grill Deals 2026"), _brief("WATCH LIVE: hearing")]
    out, rep = _run({"News": pool}, FakeClient(), mode="shadow")
    assert len(out["News"]) == 11                      # only the regex drop
    assert [d["why"].split("=")[0] for d in rep["would_drop"]] == ["shopping"]
    assert all("_jev" in b for b in out["News"])


def test_off_mode_never_calls_jev():
    c = FakeClient()
    out, rep = _run({"News": _pool(10) + [_brief("Best Grill Deals 2026")]}, c, mode="off")
    assert c.calls == 0 and len(out["News"]) == 11 and rep["jev"] == "skipped"


def test_empty_and_missing_fields_do_not_raise():
    out, _ = _run({"News": [], "Fun": [{"link": "x"}]}, FakeClient())
    assert out == {"News": [], "Fun": [{"link": "x", "_jev": out["Fun"][0]["_jev"]}]}


def test_nan_or_out_of_range_answers_count_as_failed_calls():
    class Garbage(FakeClient):
        def system_one(self, state, questions):
            r = super().system_one(state, questions)
            if "bad" in state["title"]:
                r.answers["harm"] = SimpleNamespace(score=float("nan"))
            if "huge" in state["title"]:
                r.answers["shopping"] = SimpleNamespace(noul=7.0)
            return r
    pool = _pool(10) + [_brief("bad one"), _brief("huge one")]
    out, rep = _run({"News": pool}, Garbage())
    assert len(out["News"]) == 12 and "10/12 scored" in rep["jev"]
    assert not any("_jev" in b for b in out["News"] if b["title"] in {"bad one", "huge one"})
    import json
    json.dumps(out, allow_nan=False)


def test_annotations_are_json_safe_for_checkpoints():
    import json
    out, _ = _run({"News": _pool(9)}, FakeClient())
    json.dumps(out, allow_nan=False)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok  ", fn.__name__)
    print(f"\n{len(fns)} passed")
