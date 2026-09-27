from types import SimpleNamespace
import pytest

from pipeline.publication_history import PublicationHistoryGuard, HistoryReviewBudget, assert_history_clear
from pipeline import editorial_policy as ep, full_round as fr, jev_rank as jr

PAST = "Nor'easter brings flooding as New York and New Jersey declare emergency"
CURRENT = "Powerful storm causes widespread flooding, outages in northeast U.S."
ROW = {"source_title": PAST, "source_url": "https://bbc.example/storm",
       "published_date": "2026-09-26", "category": "News"}


class Reviewer:
    def __init__(self, choice="past_0", confidence=.98, fail=False):
        self.choice, self.confidence, self.fail = choice, confidence, fail
        self.calls = []

    def system_one(self, *, state, questions):
        self.calls.append((state, questions))
        if self.fail:
            raise TimeoutError("timed out")
        return SimpleNamespace(answers={"published_event": SimpleNamespace(
            choice=self.choice, confidence=self.confidence)},
            usage=SimpleNamespace(input_tokens=100, output_tokens=2))


def test_actual_cbc_bbc_storm_reaches_early_pair_check_with_one_shared_word():
    assert jr._tokens(CURRENT) & jr._tokens(PAST) == {"flooding"}
    class Client:
        def system_one(self, **kwargs):
            return SimpleNamespace(answers={"same_event": SimpleNamespace(noul=.99)})
    pairs = jr._Pairs(Client(), {}, {}, {}, deadline=float("inf"))
    assert pairs.already_published({"title": CURRENT}, [PAST]) == PAST
    assert pairs.published_calls == 1


def test_history_review_has_no_shared_word_requirement_and_caches():
    reviewer = Reviewer()
    guard = PublicationHistoryGuard([ROW], client=reviewer)
    brief = {"title": "Residents evacuate coastal communities", "summary": "The same nor'easter continues."}
    assert not jr._tokens(brief["title"]) & jr._tokens(PAST)
    assert not guard.allows(brief)
    assert not guard.allows(dict(brief))
    assert len(reviewer.calls) == 1
    assert guard.report()["input_tokens"] == 100
    assert guard.review(brief)["match"] == ROW


def test_different_flood_in_bangkok_is_not_a_duplicate_event():
    guard = PublicationHistoryGuard([ROW], client=Reviewer(choice="none"))
    assert guard.allows({"title": "Bangkok roads submerged as flood disaster declared"})


def test_news_guard_excludes_science_and_fun_even_for_same_url():
    reviewer = Reviewer(choice="none")
    other = {**ROW, "category": "Fun"}
    guard = PublicationHistoryGuard([other], category="News", client=reviewer)
    assert guard.allows({"title": PAST, "link": ROW["source_url"]})
    assert guard.report()["history_stories"] == 0
    assert reviewer.calls == []


def test_exact_url_tracking_variant_is_blocked_without_model():
    reviewer = Reviewer(choice="none")
    guard = PublicationHistoryGuard([ROW], client=reviewer)
    assert not guard.allows({"title": "A rewritten title", "link": ROW["source_url"] + "?utm_source=rss"})
    assert reviewer.calls == []


@pytest.mark.parametrize("choice,confidence,fail", [
    ("none", .5, False), ("none", float("nan"), False),
    ("bad_id", .99, False), ("none", .99, True)])
def test_uncertain_invalid_and_failed_reviews_never_count_as_clear(choice, confidence, fail):
    guard = PublicationHistoryGuard([ROW], client=Reviewer(choice, confidence, fail))
    assert guard.review({"title": CURRENT})["status"] == "unverified"


def test_checkpoint_resume_cannot_bypass_history_review():
    guard = PublicationHistoryGuard([ROW], client=Reviewer())
    with pytest.raises(RuntimeError, match="Publication history gate blocked"):
        assert_history_clear({"News": [{"winner": {"title": CURRENT}}]}, guard)


def test_short_new_edition_is_allowed_for_title_reviewed_pack_topup():
    guard = PublicationHistoryGuard([])
    assert_history_clear({"News": [{"winner": {"title": "A genuinely new story"}}]}, guard)


@pytest.mark.parametrize("probability,status", [(.01, "clear"), (.99, "duplicate"), (.5, "unverified")])
def test_ambiguous_choice_gets_one_bounded_binary_confirmation(probability, status):
    class Confirm(Reviewer):
        def system_one(self, *, state, questions):
            if "repeated_event" in questions:
                return SimpleNamespace(answers={"repeated_event": SimpleNamespace(noul=probability)})
            return super().system_one(state=state, questions=questions)
    guard = PublicationHistoryGuard([ROW], client=Confirm(choice="none", confidence=.65))
    assert guard.review({"title": CURRENT})["status"] == status
    assert guard.calls == 2


def test_history_review_budget_failure_is_not_clean(monkeypatch):
    monkeypatch.setattr("pipeline.publication_history.MAX_CALLS", 0)
    guard = PublicationHistoryGuard([ROW], client=Reviewer(choice="none"))
    assert guard.review({"title": CURRENT})["status"] == "unverified"


def test_sections_share_total_call_budget(monkeypatch):
    monkeypatch.setattr("pipeline.publication_history.MAX_CALLS", 1)
    budget = HistoryReviewBudget()
    first = PublicationHistoryGuard([ROW], client=Reviewer(choice="none"), budget=budget)
    second = PublicationHistoryGuard([ROW], client=Reviewer(choice="none"), budget=budget)
    assert first.allows({"title": "A new event"})
    assert second.review({"title": "A different event"})["status"] == "unverified"
    assert budget.calls == 1 and second.calls == 0


def test_history_blocked_spare_never_reaches_rewrite(monkeypatch):
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda *a, **k: pytest.fail("duplicate rewritten"))
    spare = {"_unverified_spare": True, "source": SimpleNamespace(name="CBC"),
             "_winner_brief": {"title": CURRENT}}
    guard = PublicationHistoryGuard([ROW], client=Reviewer())
    assert fr.promote_spare_and_rewrite("News", [spare], history_guard=guard) == (None, None)


def test_refill_tries_other_catalog_without_same_day_model_call(monkeypatch):
    from pipeline import news_rss_core as core

    monkeypatch.setattr(core, "verify_article_content", lambda art: (True, None))
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda articles, category: {
        "articles": [{"source_id": 0}]})
    monkeypatch.setattr(fr, "filter_safe_rewrites", lambda result, sources: (
        result["articles"], []))
    monkeypatch.setattr("pipeline.publication_history.make_client",
                        lambda: pytest.fail("different catalog needed no same-day model call"))
    source = SimpleNamespace(name="NPR")
    pool = [
        {"_unverified_spare": True, "source": source,
         "_winner_brief": {"title": "Another weather story",
                           "_jev_topic_group": "severe_weather",
                           "_probe_art": {"title": "Another weather story"}}},
        {"_unverified_spare": True, "source": source,
         "_winner_brief": {"title": "Students build a new playground",
                           "_jev_topic_group": "community",
                           "_probe_art": {"title": "Students build a new playground"}}},
    ]
    existing = [{"title": "New York flood", "_jev_topic_group": "severe_weather"},
                {"title": "Bangkok flood", "_jev_topic_group": "severe_weather"}]
    winner, _ = fr.promote_spare_and_rewrite(
        "News", pool, used_briefs=existing,
        used_topic_groups={"severe_weather"}, history_guard=PublicationHistoryGuard([]))
    assert winner["winner"]["title"] == "Students build a new playground"
    assert [s["_winner_brief"]["title"] for s in pool] == ["Another weather story"]


def test_same_catalog_refill_uses_best_remaining_catalog_pick(monkeypatch):
    from pipeline import news_rss_core as core

    monkeypatch.setattr(core, "verify_article_content", lambda art: (True, None))
    rewritten = []
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda articles, category: (
        rewritten.append(articles[0][1]["title"]) or {"articles": [{"source_id": 0}]}))
    monkeypatch.setattr(fr, "filter_safe_rewrites", lambda result, sources: (
        result["articles"], []))

    monkeypatch.setattr("pipeline.publication_history.make_client",
                        lambda: pytest.fail("catalog refill needed no same-day model call"))
    source = SimpleNamespace(name="CBC")
    titles = ["New Jersey begins storm recovery", "Bangkok roads submerged as flood disaster declared"]
    pool = [{"_unverified_spare": True, "source": source,
             "_winner_brief": {"title": title, "_jev_topic_group": "severe_weather",
                               "_probe_art": {"title": title}}}
            for title in titles]
    existing = [{"title": CURRENT, "_jev_topic_group": "severe_weather"},
                {"title": "Politics in Europe", "_jev_topic_group": "international_relations"}]
    winner, _ = fr.promote_spare_and_rewrite(
        "News", pool, used_briefs=existing,
        used_topic_groups={"severe_weather", "international_relations"},
        history_guard=PublicationHistoryGuard([]))
    assert winner["winner"]["title"] == titles[0]
    assert rewritten == [titles[0]]
    assert [s["_winner_brief"]["title"] for s in pool] == [titles[1]]


def choice(title, topic, publisher):
    return {"source": SimpleNamespace(name=publisher, rss_url=f"https://{publisher}.example/rss"),
            "brief": {"title": title, "_jev_topic_group": topic}}


def test_final_topics_beat_a_third_source_when_safe_alternative_exists():
    items = [choice("US storm", "severe_weather", "a"),
             choice("Diplomacy", "international_relations", "b"),
             choice("Bangkok", "severe_weather", "c"),
             choice("New school", "community", "a")]
    result = ep.prefer_final_editorial_diversity("News", items)
    assert len({x["brief"]["_jev_topic_group"] for x in result[:3]}) == 3
    assert "New school" in [x["brief"]["title"] for x in result[:3]]


def test_thin_pool_allows_same_topic_different_events():
    items = [choice("US storm", "severe_weather", "a"),
             choice("Diplomacy", "international_relations", "b"),
             choice("Bangkok", "severe_weather", "c")]
    assert ep.prefer_final_editorial_diversity("News", items) == items


def test_science_publisher_target_survives_final_joint_selection():
    items = [choice("Physics", "physics", "a"), choice("Chemistry", "chemistry_materials", "a"),
             choice("Planet", "astronomy_space", "a"), choice("Other planet", "astronomy_space", "b")]
    result = ep.prefer_final_editorial_diversity("Science", items)[:3]
    assert len({ep.publisher_key(x["source"]) for x in result}) == 2
    assert len({x["brief"]["_jev_topic_group"] for x in result}) == 3


def test_topic_only_promotion_keeps_other_spares_for_normal_refill(monkeypatch):
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda *a, **k: pytest.fail("same topic rewritten"))
    spare = {"_unverified_spare": True, "source": SimpleNamespace(name="BBC"),
             "_winner_brief": {"title": "Bangkok flood", "_jev_topic_group": "severe_weather"}}
    pool = [spare]
    assert fr.promote_spare_and_rewrite("News", pool, used_topic_groups={"severe_weather"},
                                        require_new_topic=True) == (None, None)
    assert pool == [spare]
