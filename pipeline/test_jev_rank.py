"""Tests for the Jev ranking stage (Stage 1.7).

Two contracts: (1) no failure mode may raise or lose a brief — the caller falls
back to the legacy cut on None; (2) the cross-brief rules Jev cannot apply itself.

Run: python -m pipeline.test_jev_rank   (also works under pytest)
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from pipeline import jev_rank as jr


def _b(title, src="S1", cat="News", pick=None):
    return {"title": title, "summary": "", "_source_name": src, "_category": cat, "link": f"l/{title}", "_p": pick}


class Fake:
    """pick comes from the brief; pair answers from keywords in the two headlines."""

    def __init__(self, fail=(), delay=0.0, pairs_fail=False):
        self.fail, self.delay, self.pairs_fail, self.rank_calls, self.pair_calls = fail, delay, pairs_fail, 0, 0
        self.by_title: dict[str, float] = {}

    def system_one(self, state, questions):
        if self.delay:
            time.sleep(self.delay)
        if "story" in state:
            self.rank_calls += 1
            t = state["story"]["headline"]
            if any(f in t for f in self.fail):
                raise RuntimeError("boom")
            return SimpleNamespace(answers={"pick": SimpleNamespace(noul=self.by_title[t]), "want": SimpleNamespace(score=2.0)})
        self.pair_calls += 1
        if self.pairs_fail:
            raise RuntimeError("pair boom")
        a, b = state["headline_A"], state["headline_B"]
        ans = {"same_story": SimpleNamespace(noul=0.9 if ("assisted dying" in a and "assisted dying" in b) else 0.05)}
        if "same_subject" in questions:
            ans["same_subject"] = SimpleNamespace(noul=0.9 if ("Trump" in a and "Trump" in b) else 0.05)
        return SimpleNamespace(answers=ans)

    def close(self):
        pass


def _run(pools, fake=None):
    fake = fake or Fake()
    for bs in pools.values():
        for b in bs:
            fake.by_title[b["title"]] = b["_p"]
    return jr.rank_briefs(pools, client=fake), fake


TRUMP = ["Trump signs sweeping Russia sanctions bill", "Trump visits Dublin for trade talks",
         "Trump names artificial intelligence tsar", "Trump threatens tariffs on Canadian lumber",
         "Trump pardons former Arizona sheriff", "Trump hosts Japanese premier at Mar-a-Lago",
         "Trump orders review of lunar programme"]
VOLCANO = ["Volcano buries Icelandic fishing harbour", "Eruption closes eight Indonesian airports",
           "Lava reaches Hawaiian coastal highway", "Ash cloud grounds flights across Sicily"]


def _titles(bs):
    return [b["title"] for b in bs]


def _sent(out, cat):
    return _titles(jr.for_curator(out)[cat])


def test_orders_by_pick_and_keeps_top_10():
    pool = [_b(f"Story {i:02d} alpha{i}", src=f"S{i % 5}", pick=i / 20) for i in range(14)]
    (out, rep), _ = _run({"Science": pool})
    assert len(out["Science"]) == jr.POOL_KEEP
    assert [b["_jev_rank"]["pos"] for b in out["Science"]] == list(range(1, 11))
    assert len(_sent(out, "Science")) == jr.TO_CURATOR == len(rep["sent"]["Science"])
    reserve = [b["_jev_rank"]["pick"] for b in out["Science"] if not b["_jev_rank"]["send"]]
    assert reserve == sorted(reserve, reverse=True)


def test_at_most_two_per_source_among_the_six():
    pool = [_b(f"Tennis item number{i}", src="BBC Tennis", pick=0.9 - i / 100) for i in range(5)]
    pool += [_b(f"Other piece word{i}", src=f"Src{i}", pick=0.5 - i / 100) for i in range(6)]
    (out, rep), _ = _run({"Fun": pool})
    six = jr.for_curator(out)["Fun"]
    assert len(six) == 6 and sum(b["_source_name"] == "BBC Tennis" for b in six) == jr.MAX_PER_SOURCE
    assert any("already 2 from this source" in d["why"] for d in rep["skipped"])


def test_near_identical_headlines_are_deduped_by_code_without_asking_jev():
    pool = [_b("Scientists test Einstein gravity with exotic matter", src="A", pick=0.9),
            _b("Scientists test Einstein gravity with exotic matter today", src="B", pick=0.8)]
    pool += [_b(f"Zebra{i} quokka{i}", src=f"C{i}", pick=0.3) for i in range(6)]
    (out, _), fake = _run({"Science": pool})
    assert sum("Einstein" in t for t in _sent(out, "Science")) == 1 and fake.pair_calls == 0


def test_reworded_duplicate_is_caught_by_jev():
    pool = [_b("MPs vote against fresh attempt to legalise assisted dying", src="A", pick=0.9),
            _b("An extraordinary result - why MPs rejected the assisted dying bill", src="B", pick=0.8)]
    pool += [_b(f"Zebra{i} quokka{i}", src=f"C{i}", pick=0.3) for i in range(6)]
    (out, rep), fake = _run({"News": pool})
    assert sum("assisted dying" in t for t in _sent(out, "News")) == 1
    assert fake.pair_calls >= 1 and any("same story" in d["why"] for d in rep["skipped"])
    # the duplicate is not lost: it sits at the very end of the reserve
    assert _titles(out["News"])[-1] == "An extraordinary result - why MPs rejected the assisted dying bill"


def test_news_subject_is_capped_not_banned():
    pool = [_b(t, src=f"S{i}", pick=0.95 - i / 100) for i, t in enumerate(TRUMP[:5])]
    pool += [_b(t, src=f"V{i}", pick=0.4 - i / 100) for i, t in enumerate(VOLCANO)]
    (out, rep), _ = _run({"News": pool})
    six = _sent(out, "News")
    assert sum("Trump" in t for t in six) == jr.MAX_SAME_SUBJECT and sum(t in VOLCANO for t in six) == 3
    assert any("about the same subject" in d["why"] for d in rep["skipped"])


def test_subject_rule_is_news_only():
    pool = [_b(t, src=f"S{i}", cat="Fun", pick=0.9 - i / 100) for i, t in enumerate(TRUMP[:6])]
    (out, _), _ = _run({"Fun": pool})
    assert sum("Trump" in t for t in _sent(out, "Fun")) == 6


def test_cross_category_duplicate_goes_to_fun_not_news():
    news = [_b("Ed Sheeran concert goes ahead after assisted dying row", src="AJ", pick=0.9)] + \
           [_b(f"World event summit{i}", src=f"N{i}", pick=0.5) for i in range(5)]
    fun = [_b("Ed Sheeran breaks silence on assisted dying tour row", src="RS", cat="Fun", pick=0.7)] + \
          [_b(f"Game release title{i}", src=f"F{i}", cat="Fun", pick=0.5) for i in range(5)]
    (out, rep), _ = _run({"News": news, "Fun": fun})
    assert any("Sheeran" in t for t in _sent(out, "Fun"))
    assert not any("Sheeran" in t for t in _sent(out, "News")) and len(_sent(out, "News")) == 5
    assert list(out) == ["News", "Fun"]                      # caller's category order preserved


def test_thin_pool_relaxes_caps_but_never_sends_a_duplicate_story():
    pool = [_b(f"Tennis item number{i}", src="BBC Tennis", pick=0.9 - i / 100) for i in range(5)]
    (out, _), _ = _run({"Fun": pool})
    assert len(_sent(out, "Fun")) == 5


def test_unscored_brief_ranks_last_and_is_not_lost():
    pool = [_b(f"Item word{i}", src=f"S{i}", pick=0.5 + i / 100) for i in range(8)] + [_b("flaky one", src="Z", pick=0.99)]
    (out, _), _ = _run({"Science": pool}, Fake(fail=("flaky",)))
    assert _titles(out["Science"])[-1] == "flaky one" and len(out["Science"]) == 9


def test_failure_modes_return_none_so_the_caller_falls_back():
    pool = {"News": [_b(f"flaky {i}", pick=0.5) for i in range(6)] + [_b(f"fine {i}", pick=0.5) for i in range(4)]}
    (out, rep), _ = _run(pool, Fake(fail=("flaky",)))
    assert out is None and "calls failed" in rep["jev"]
    saved, jr.TIME_BUDGET_S = jr.TIME_BUDGET_S, 0.05
    try:
        (out, rep), _ = _run({"News": [_b(f"slow {i}", pick=0.5) for i in range(12)]}, Fake(delay=0.2))
    finally:
        jr.TIME_BUDGET_S = saved
    assert out is None and "time budget" in rep["jev"]
    assert jr.rank_briefs({"News": []}, client=Fake())[0] is None


def test_pair_call_failures_never_block_a_pick():
    pool = [_b(t, src=f"S{i}", pick=0.9 - i / 100) for i, t in enumerate(TRUMP)]
    (out, rep), fake = _run({"News": pool}, Fake(pairs_fail=True))
    assert out is not None and len(_sent(out, "News")) == 6 and "failed" in rep["jev"]


def test_no_key_returns_none(monkeypatch=None):
    import os
    saved = os.environ.pop("TYPESAFE_API_KEY", None)
    try:
        out, rep = jr.rank_briefs({"News": [_b("x", pick=0.5)]})
    finally:
        if saved is not None:
            os.environ["TYPESAFE_API_KEY"] = saved
    assert out is None and "TYPESAFE_API_KEY" in rep["jev"]


def test_output_is_json_safe_for_checkpoints():
    import json
    (out, _), _ = _run({"News": [_b(f"Item word{i}", src=f"S{i}", pick=i / 10) for i in range(7)]})
    json.dumps(out, allow_nan=False)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok  ", fn.__name__)
    print(f"\n{len(fns)} passed")
