"""Jev News topics are a soft diversity signal, separate from event/safety gates."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline import full_round as fr
from pipeline import mega_curator as mc
from pipeline import news_rss_core as core
from pipeline import news_topics as nt


class Source:
    def __init__(self, name):
        self.name = name


class FakeJev:
    def system_one(self, state, questions):
        title = state["headline"]
        label, confidence = {
            "Hurricane in Hawaii": ("severe_weather", 1.0),
            "Nor'easter in New York": ("severe_weather", 1.0),
            "FEMA responds to coastal homes": ("us_politics", 0.51),
        }[title]
        return SimpleNamespace(answers={"topic": SimpleNamespace(
            choice=label, confidence=confidence)})


def _pick(rank, title, group, source):
    return {"rank": rank, "source": Source(source),
            "brief": {"title": title, "_jev_topic_group": group}}


def test_jev_groups_different_storms_but_leaves_uncertain_ungrouped():
    briefs = [{"title": title} for title in
              ("Hurricane in Hawaii", "Nor'easter in New York",
               "FEMA responds to coastal homes")]
    report = nt.tag_news_topics(briefs, client=FakeJev())
    assert report == {"tagged": 2, "uncertain": 1, "failed": 0}
    assert [nt.topic_group(b) for b in briefs] == ["severe_weather", "severe_weather", ""]


def test_soft_topic_swap_prefers_three_groups_without_losing_source_diversity():
    picks = [_pick(1, "Hurricane in Hawaii", "severe_weather", "NPR"),
             _pick(2, "Nor'easter in New York", "severe_weather", "BBC"),
             _pick(3, "US fuel rules", "us_politics", "AJ"),
             _pick(4, "International summit", "international_relations", "PBS")]
    out = mc._prefer_top3_topic_diversity({"News": picks})["News"]
    assert [nt.topic_group(p["brief"]) for p in out[:3]] == [
        "severe_weather", "international_relations", "us_politics"]
    assert len({p["source"].name for p in out[:3]}) == 3
    assert [p["rank"] for p in out] == [1, 2, 3, 4]


def test_two_same_topic_are_allowed_when_no_suitable_alternative():
    picks = [_pick(1, "Hurricane in Hawaii", "severe_weather", "NPR"),
             _pick(2, "Nor'easter in New York", "severe_weather", "BBC"),
             _pick(3, "US fuel rules", "us_politics", "AJ"),
             _pick(4, "Another policy", "us_politics", "PBS")]
    out = mc._prefer_top3_topic_diversity({"News": picks})["News"]
    assert [p["brief"]["title"] for p in out[:3]] == [
        "Hurricane in Hawaii", "Nor'easter in New York", "US fuel rules"]
    assert nt.topic_group({"_jev_topic_group": "other"}) == ""


def test_stage3_spare_prefers_new_topic_and_keeps_unattempted(monkeypatch):
    attempts = []
    monkeypatch.setattr(core, "verify_article_content", lambda art: (True, None))
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda articles, category: (
        attempts.append(articles[0][1]["title"]) or {"articles": [{"source_id": 0}]}))
    monkeypatch.setattr(fr, "filter_safe_rewrites", lambda result, sources=None: (result["articles"], []))

    def spare(title, group, source):
        brief = {"title": title, "_jev_topic_group": group,
                 "_probe_art": {"title": title, "link": title}}
        return {"_unverified_spare": True, "_winner_brief": brief,
                "source": Source(source), "_rank": 4}

    pool = [spare("Another storm", "severe_weather", "PBS"),
            spare("International summit", "international_relations", "NPR")]
    winner, _ = fr.promote_spare_and_rewrite(
        "News", pool, used_source_names={"NPR"},
        used_briefs=[{"title": "Hurricane in Hawaii"}],
        used_topic_groups={"severe_weather"})
    assert winner["winner"]["title"] == "International summit"
    assert attempts == ["International summit"]
    assert [s["_winner_brief"]["title"] for s in pool] == ["Another storm"]


def test_science_and_fun_soft_topic_swaps():
    science = [_pick(1, "Moon mission", "astronomy_space", "A"),
               _pick(2, "Star map", "astronomy_space", "B"),
               _pick(3, "New frog", "biology_ecology", "C"),
               _pick(4, "New molecule", "chemistry_materials", "D")]
    fun = [_pick(1, "Soccer match", "other_sports", "A"),
           _pick(2, "Tennis match", "tennis", "B"),
           _pick(3, "New song", "music", "C"),
           _pick(4, "Fat Bear Week", "animal_events", "D")]
    out = mc._prefer_top3_topic_diversity({"Science": science, "Fun": fun})
    assert {nt.topic_group(p["brief"]) for p in out["Science"][:3]} == {
        "astronomy_space", "biology_ecology", "chemistry_materials"}
    assert {nt.topic_group(p["brief"]) for p in out["Fun"][:3]} == {
        "other_sports", "tennis", "music"}


def test_science_and_fun_topic_labels_are_recognized():
    assert nt.topic_group({"_jev_topic_group": "physics"}) == "physics"
    assert nt.topic_group({"_jev_topic_group": "animal_events"}) == "animal_events"
    assert nt.topic_group({"_jev_topic_group": "swimming"}) == "swimming"
    assert nt.topic_group({"_jev_topic_group": "tennis"}) == "tennis"
    assert nt.topic_group({"_jev_topic_group": "other_sports"}) == "other_sports"


def test_fun_can_select_swimming_and_tennis_together():
    picks = [_pick(1, "Swim race", "swimming", "SwimSwam"),
             _pick(2, "Tennis final", "tennis", "BBC Tennis"),
             _pick(3, "Second tennis story", "tennis", "ESPN"),
             _pick(4, "Football final", "other_sports", "AP")]
    out = mc._prefer_top3_topic_diversity({"Fun": picks})["Fun"]
    assert [nt.topic_group(p["brief"]) for p in out[:3]] == [
        "swimming", "tennis", "other_sports"]
    assert len({p["source"].name for p in out[:3]}) == 3


def test_fun_does_not_drop_second_tennis_story_without_alternative():
    picks = [_pick(1, "Swim race", "swimming", "SwimSwam"),
             _pick(2, "Tennis final", "tennis", "BBC Tennis"),
             _pick(3, "Another tennis final", "tennis", "ESPN")]
    out = mc._prefer_top3_topic_diversity({"Fun": picks})["Fun"]
    assert [p["brief"]["title"] for p in out[:3]] == [
        "Swim race", "Tennis final", "Another tennis final"]


def test_curator_sees_major_fun_sport_priority():
    brief = {"title": "Swimmer breaks world record", "summary": "A new record today",
             "_source_name": "SwimSwam", "_jev_topic_group": "swimming",
             "_jev_rank": {"sports_priority": 4}}
    message, _ = mc._build_mega_curator_input({"News": [], "Science": [], "Fun": [brief]})
    assert "editorial_topic=swimming sports_priority=4" in message
