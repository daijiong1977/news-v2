"""High-confidence section routing is reversible and never a safety gate."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline import editorial_routing as routing


class FakeJev:
    def __init__(self, answers):
        self.answers = answers

    def system_one(self, state, questions):
        target, confidence = self.answers[state["headline"]]
        return SimpleNamespace(answers={"section": SimpleNamespace(
            choice=target, confidence=confidence)})


def _pool():
    return {"News": [{"title": "Fat Bear Week"}, {"title": "A storm"}],
            "Science": [{"title": "A moon discovery"}],
            "Fun": [{"title": "A song"}]}


ANSWERS = {"Fat Bear Week": ("Fun", 0.99),
           "A storm": ("Fun", 0.65),
           "A moon discovery": ("Science", 0.99),
           "A song": ("Fun", 0.99)}


def test_only_confident_misfiled_story_moves():
    pool = _pool()
    out, report = routing.route_briefs(pool, client=FakeJev(ANSWERS), route_mode="on")
    assert [b["title"] for b in out["News"]] == ["A storm"]
    assert [b["title"] for b in out["Fun"]] == ["Fat Bear Week", "A song"]
    assert out["Fun"][0]["_category"] == "Fun"
    assert report["scored"] == 4
    assert report["uncertain"] == 1
    assert len(report["moved"]) == 1


def test_shadow_and_off_do_not_move():
    pool = _pool()
    shadow, report = routing.route_briefs(pool, client=FakeJev(ANSWERS), route_mode="shadow")
    assert [b["title"] for b in shadow["News"]] == ["Fat Bear Week", "A storm"]
    assert "_category" not in shadow["News"][0]
    assert len(report["moved"]) == 1
    off, report = routing.route_briefs(pool, route_mode="off")
    assert off is pool
    assert report["scored"] == 0


def test_failed_one_brief_keeps_its_original_section():
    pool = _pool()
    answers = {key: val for key, val in ANSWERS.items() if key != "A storm"}
    out, report = routing.route_briefs(pool, client=FakeJev(answers), route_mode="on")
    assert report["failed"] == 1
    assert [b["title"] for b in out["News"]] == ["A storm"]


def test_new_taxonomy_routes_animals_ai_and_technology_without_losing_entries():
    from pipeline.editorial_policy import SECTION_POLICY
    from pipeline import jev_rank, news_topics

    class PolicyFake(FakeJev):
        def system_one(self, state, questions):
            assert SECTION_POLICY in routing.SECTION_INSTRUCTIONS
            return super().system_one(state, questions)

    titles = ["Sea spider species discovered", "New AI school rules", "A new robot",
              "New chemical reaction", "A distant star"]
    pool = {"Science": [{"title": t} for t in [titles[0], *titles[2:]]],
            "News": [{"title": titles[1]}], "Fun": []}
    answers = {"Sea spider species discovered": ("Science", .99),
               "New AI school rules": ("News", .99),
               "A new robot": ("Fun", .99),
               "New chemical reaction": ("Science", .99),
               "A distant star": ("Science", .99)}
    out, report = routing.route_briefs(pool, client=PolicyFake(answers), route_mode="on")
    assert {b["title"] for b in out["Fun"]} == {titles[2]}
    assert {b["title"] for b in out["News"]} == {titles[1]}
    assert {b["title"] for b in out["Science"]} == {titles[0], titles[3], titles[4]}
    assert sum(map(len, out.values())) == 5
    assert len(report["moved"]) == 1
    # Assert the downstream fit gate uses exactly the same policy.
    assert all(SECTION_POLICY in v for v in jev_rank.CATEGORY_FIT_CRITERIA.values())
    assert {"animal_events", "technology", "artificial_intelligence"} <= set(news_topics.FUN_TOPIC_CRITERIA)
    assert news_topics.topic_group({"_jev_topic_group": "biology_ecology"}) == "biology_ecology"
    assert "engineering_technology" not in news_topics.SCIENCE_TOPIC_CRITERIA
    assert news_topics.topic_group({"_jev_topic_group": "engineering_technology"}) == "engineering_technology"


def test_sports_url_forces_fun_even_when_jev_calls_it_news():
    sport = {"title": "Ireland wears black armbands for Israel game",
             "link": "https://www.bbc.co.uk/sport/football/articles/example"}
    politics = {"title": "CNN excluded from Air Force One for football trip",
                "link": "https://www.pbs.org/newshour/politics/cnn-football-trip"}
    out, report = routing.route_briefs(
        {"News": [sport, politics], "Science": [], "Fun": []},
        client=FakeJev({sport["title"]: ("News", .99),
                        politics["title"]: ("News", .99)}), route_mode="on")
    assert out["News"] == [politics]
    assert out["Fun"] == [sport]
    assert len(report["moved"]) == 1
