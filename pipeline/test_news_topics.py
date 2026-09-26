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
    monkeypatch.setattr(fr, "filter_safe_rewrites", lambda result: (result["articles"], []))

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
