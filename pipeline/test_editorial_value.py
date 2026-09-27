"""Section-specific value, early semantic exclusions and seven Fun choices."""
from types import SimpleNamespace

import pytest

from pipeline import editorial_policy as ep
from pipeline import jev_prefilter as jp
from pipeline import jev_rank as jr
from pipeline.test_jev_rank import Fake, _b, _run


@pytest.mark.parametrize("cat,expected", [("News", 6), ("Science", 6), ("Fun", 7)])
def test_section_specific_curator_capacity(cat, expected):
    pool = [_b(f"Headline{i} event{i} discovery{i}", src=f"Outlet{i}", cat=cat, pick=.8) for i in range(12)]
    (out, _), _ = _run({cat: pool})
    assert len(jr.for_curator(out)[cat]) == expected
    assert len(out[cat]) == 10


def test_low_fun_not_resurrected_by_thin_pool_or_reserves_or_deep_dig():
    fake = Fake()
    fake.value_by_title = {"Routine roster announcement": 1}
    bad = _b("Routine roster announcement", cat="Fun", pick=.99)
    good = _b("Kids create a playful festival", src="Other", cat="Fun", pick=.7)
    (out, report), _ = _run({"Fun": [bad, good]}, fake)
    assert out["Fun"] == [good]
    assert any(x["why"] == "low Fun value" for x in report["skipped"])
    assert jr.gate_deep_dig_category("Fun", [bad], client=fake) == []


def test_news_importance_reaches_shortlist_but_not_if_wrong_category():
    pool = [_b(f"Routine story {i}", src=f"Outlet{i}", pick=.85) for i in range(8)]
    important = _b("New school lunch access rule", src="Education", pick=.5)
    wrong = _b("Major telescope discovery", src="Space", pick=.9)
    fake = Fake()
    fake.value_by_title = {important["title"]: 4, wrong["title"]: 4}
    fake.fit_by_title = {wrong["title"]: .1}
    (out, _), _ = _run({"News": pool + [important, wrong]}, fake)
    selected = jr.for_curator(out)["News"]
    assert important in selected and wrong not in selected


def test_final_importance_preference_only_uses_available_qualified_items():
    rows = [{"brief": {}, "article": i} for i in range(3)]
    important = {"brief": {"_jev_rank": {"section_value": 4, "pick": .5,
                                         "category_fit": .9}}, "article": 3}
    assert ep.prefer_important_news(rows) == rows
    assert ep.prefer_important_news(rows + [important])[:3] == rows[:2] + [important]
    important["brief"]["_jev_rank"]["pick"] = .2
    assert ep.prefer_important_news(rows + [important]) == rows + [important]


@pytest.mark.parametrize("mode,removed", [("on", True), ("shadow", False), ("off", False)])
def test_semantic_recruitment_exclusion_is_early_and_not_floor_restored(monkeypatch, mode, removed):
    monkeypatch.setenv("JEV_PREFILTER", mode)
    class Client:
        def system_one(self, **kwargs):
            return SimpleNamespace(answers={
                "shopping": SimpleNamespace(noul=0), "harm": SimpleNamespace(score=0),
                "uk_domestic": SimpleNamespace(noul=0), "recruiting": SimpleNamespace(noul=.96)})
    # Deliberately no regex keyword: the model can recognize paraphrased recruitment.
    brief = {"title": "A new home for next season", "_category": "Fun"}
    out, report = jp.prefilter_briefs({"Fun": [brief]}, client=Client(), questions={"recruiting": object()})
    assert (out["Fun"] == []) is removed
    if removed:
        assert report["restored"] == 0
        assert report["dropped"][0]["why"] == "recruiting=0.96"


def test_value_bonus_does_not_stack_with_sports_bonus():
    fake = Fake()
    fake.by_title = {"Champion": .7}
    fake.value_by_title = {"Champion": 4}
    fake.sports_priority_by_title = {"Champion": 4}
    score = jr._score_one(fake, jr._section_questions(jr._questions()[0], "Fun"), "Fun", _b("Champion"))
    assert score["editorial_pick"] == .88


def test_invalid_value_fails_scoring():
    fake = Fake()
    fake.by_title = {"Invalid": .7}
    fake.value_by_title = {"Invalid": float("nan")}
    with pytest.raises(ValueError):
        jr._score_one(fake, jr._section_questions(jr._questions()[0], "News"), "News", _b("Invalid"))
