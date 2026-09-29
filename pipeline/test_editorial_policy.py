"""Regressions for the Sep-26 publisher concentration / college recruiting edition."""
import json
from types import SimpleNamespace

import pytest

from pipeline import editorial_policy as ep
from pipeline import full_round as fr
from pipeline import jev_rank as jr
from pipeline import news_rss_core as core
from pipeline import pack_and_upload as pack


def source(name, host="sciencedaily.com"):
    return SimpleNamespace(name=name, rss_url=f"https://{host}/rss/{name}.xml")


def pick(name, topic, host="sciencedaily.com"):
    return {"source": source(name, host), "brief": {"_jev_topic_group": topic}}


def test_science_feeds_are_one_publisher_but_bbc_aliases_also_normalize():
    assert ep.publisher_key(source("All")) == ep.publisher_key(source("Chemistry"))
    assert ep.publisher_key(source("BBC", "feeds.bbci.co.uk")) == "bbc"
    assert ep.publisher_key(source("BBC", "bbc.com")) == ep.publisher_key(source("Sport", "bbc.co.uk"))
    assert ep.publisher_key(source("SD", "not-sciencedaily.com")) != "sciencedaily"


def test_two_publishers_keep_three_topics_and_keep_article_pairing():
    rows = [pick("Biology", "biology_ecology"), pick("Space", "astronomy_space"),
            pick("Chemistry", "chemistry_materials"),
            pick("Live Science", "astronomy_space", "livescience.com")]
    for i, row in enumerate(rows):
        row["article"] = {"id": i}
    out = ep.prefer_science_publishers(rows)
    assert [x["article"]["id"] for x in out[:3]] == [0, 2, 3]
    assert len({ep.publisher_key(x["source"]) for x in out[:3]}) == 2
    assert len({x["brief"]["_jev_topic_group"] for x in out[:3]}) == 3
    assert len(out) == len(rows)


def test_no_second_eligible_publisher_does_not_invent_one():
    rows = [pick("Bio", "biology_ecology"), pick("Space", "astronomy_space"),
            pick("Chem", "chemistry_materials")]
    assert ep.prefer_science_publishers(rows) == rows


def test_news_final_soft_diversity_does_not_displace_much_stronger_safe_story():
    def item(title, topic, strength, source_name):
        return {"source": source(source_name, f"{source_name}.example"),
                "brief": {"title": title, "_jev_topic_group": topic,
                          "_jev_rank": {"editorial_pick": strength,
                                        "section_value": 1, "category_fit": .9,
                                        "floor": .4}}}

    rows = [item("Venezuela", "international_relations", .69, "bbc"),
            item("Panda diplomacy", "international_relations", .82, "pbs"),
            item("Election security", "us_politics", .49, "npr"),
            item("Routine school AI", "technology_business", .50, "cbc")]
    chosen = ep.prefer_final_editorial_diversity("News", rows)[:3]
    assert "Panda diplomacy" in [x["brief"]["title"] for x in chosen]


def test_news_final_prefers_new_topic_when_quality_is_close():
    rows = [
        {"source": source(name, f"{name}.example"),
         "brief": {"title": name, "_jev_topic_group": topic,
                   "_jev_rank": {"editorial_pick": score, "section_value": 1,
                                 "category_fit": .9, "floor": .4}}}
        for name, topic, score in (
            ("a", "international_relations", .65),
            ("b", "international_relations", .61),
            ("c", "us_politics", .60),
            ("d", "technology_business", .58))]
    chosen = ep.prefer_final_editorial_diversity("News", rows)[:3]
    assert len({x["brief"]["_jev_topic_group"] for x in chosen}) == 3


def test_news_global_rank_can_rescue_undervalued_civic_explainer():
    rows = []
    for title, topic, pick_score, value, global_rank, outlet in (
            ("Panda diplomacy", "international_relations", .82, 1.56, 3, "pbs"),
            ("Venezuela", "international_relations", .69, 2.24, 7, "bbc"),
            ("Maricopa election verification", "us_politics", .49, .9, 1, "npr"),
            ("Routine school AI", "technology_business", .50, .96, 4, "npr")):
        rows.append({"source": source(outlet, f"{outlet}.example"),
                     "brief": {"title": title, "_jev_topic_group": topic,
                               "_jev_rank": {"editorial_pick": pick_score,
                                             "section_value": value,
                                             "global_rank": global_rank,
                                             "category_fit": .9, "floor": .4}}})
    chosen = ep.prefer_final_editorial_diversity("News", rows)[:3]
    assert "Maricopa election verification" in [x["brief"]["title"] for x in chosen]


def test_science_ranking_caps_publisher_not_each_feed():
    class Pairs:
        def relation(self, *args, **kwargs):
            return None

    briefs = [{"title": f"Research {i}", "_source": source(f"Feed{i}"),
               "_source_name": f"Feed{i}", "_jev_pick": .95 - i * .01}
              for i in range(5)]
    briefs += [{"title": "A new planet", "_source": source("Live", "livescience.com"),
                "_source_name": "Live", "_jev_pick": .7},
               {"title": "A new molecule", "_source": source("MIT", "news.mit.edu"),
                "_source_name": "MIT", "_jev_pick": .65}]
    selected, _, below = jr._select("Science", briefs, Pairs(), [])
    assert len({ep.publisher_key(b["_source"]) for b in selected}) >= 2
    assert sum(ep.publisher_key(b["_source"]) == "sciencedaily" for b in selected) <= 3
    assert below == 0


@pytest.mark.parametrize("title,summary", [
    ("Best Of The Rest Ranked Owen Gee Sends Verbal Commitment To Texas A&M For 2028",
     "Owen Gee is a high school swimmer announcing his college commitment."),
    ("Ohio Teen Owen Gee Commits to Texas A&M Swimming for 2028", ""),
    ("Top tennis recruiting classes for 2027", ""),
    ("NCAA swimmer enters transfer portal", ""),
    ("A swimmer's next chapter", "She has announced her verbal commitment to a university."),
    ("World record holder commits to university swimming team", "A college recruitment announcement."),
])
def test_recruitment_is_excluded(title, summary):
    assert ep.editorial_exclusion({"title": title, "summary": summary}) == "college_recruiting"


@pytest.mark.parametrize("title,summary", [
    ("College swimmer breaks world record", "Last year she announced a verbal commitment to Texas."),
    ("NCAA swimming championships begin", "Teams compete for a national title."),
    ("Teen wins US Open title", "She had previously considered college recruitment."),
    ("University commits to clean energy", "The university pledged to reduce emissions."),
    ("Tennis federation commits to cleaner events", "An environmental policy announcement."),
    ("New chemical process makes cleaner batteries", ""),
])
def test_results_and_non_recruitment_stories_stay_eligible(title, summary):
    assert ep.editorial_exclusion({"title": title, "summary": summary}) is None


def test_phase_a_excludes_recruitment_even_if_feed_is_in_news(monkeypatch):
    monkeypatch.setattr(fr, "fetch_source_entries", lambda *a, **k: [
        {"title": "Swimmer gives verbal commitment to university", "link": "bad"},
        {"title": "Swimmer wins world championship", "link": "good"}])
    briefs = fr.phase_a_light("News", [source("Sport", "example.com")])
    assert [b["link"] for b in briefs] == ["good"]


def test_spare_recruitment_does_not_reach_rewrite(monkeypatch):
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda *a, **k: pytest.fail("recruitment reached rewrite"))
    pool = [{"_unverified_spare": True, "source": source("Swim"),
             "_winner_brief": {"title": "Swimmer gives verbal commitment to college"}}]
    assert fr.promote_spare_and_rewrite("Fun", pool) == (None, None)


def test_new_publisher_spare_uses_safety_and_skips_same_publisher(monkeypatch):
    same = {"_unverified_spare": True, "source": source("Different SD feed"),
            "_winner_brief": {"title": "A safe new molecule"}}
    other = {"_unverified_spare": True, "source": source("Live", "livescience.com"),
             "_winner_brief": {"title": "A new planet",
                               "_probe_art": {"title": "A new planet"}}}
    monkeypatch.setattr(core, "verify_article_content", lambda a: (True, None))
    # This test isolates publisher diversity and the safety gate; source
    # length is covered by the ranked-body and spare length tests elsewhere.
    monkeypatch.setattr(fr, "_source_length_check", lambda *_a: (True, None))
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda *a, **k: {"articles": [{"source_id": 0}]})
    vetted = []
    monkeypatch.setattr(fr, "filter_safe_rewrites", lambda result, sources, **kwargs: (
        vetted.append(sources[0]["title"]) or [], result["articles"]))
    pool = [same, other]
    assert fr.promote_spare_and_rewrite(
        "Science", pool, used_publishers={"sciencedaily"}, require_new_publisher=True) == (None, None)
    assert vetted == ["A new planet"]
    assert pool == [same]


def test_new_publisher_cannot_replace_with_below_floor_spare(monkeypatch):
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda *a, **k: pytest.fail("below-floor rewrite"))
    pool = [{"_unverified_spare": True, "source": source("Live", "livescience.com"),
             "_winner_brief": {"title": "Another discovery",
                               "_jev_rank": {"editorial_pick": .2, "floor": .5}}}]
    assert fr.promote_spare_and_rewrite(
        "Science", pool, used_publishers={"sciencedaily"}, require_new_publisher=True) == (None, None)


def test_carryover_does_not_restore_removed_recruitment(tmp_path):
    final, old = tmp_path / "final", tmp_path / "old"
    for root in (final, old):
        (root / "payloads").mkdir(parents=True)
    fresh = [{"id": "today-1", "title": "A new movie", "summary": "Film news"},
             {"id": "today-2", "title": "Tennis champion", "summary": "Match result"}]
    previous = [{"id": "recruit", "title": "Swimmer gives verbal commitment to college", "summary": ""},
                {"id": "record", "title": "Swimmer breaks world record", "summary": "Race result"}]
    for level in ("easy", "middle", "cn"):
        (final / "payloads" / f"articles_fun_{level}.json").write_text(json.dumps({"articles": fresh}))
        (old / "payloads" / f"articles_fun_{level}.json").write_text(json.dumps({"articles": previous}))
    assert pack._topup_thin_categories(final, old) == {"fun": ["record"]}


def test_bundle_rejects_recruitment_from_old_checkpoint(tmp_path, caplog):
    (tmp_path / "payloads").mkdir()
    (tmp_path / "payloads" / "articles_fun_middle.json").write_text(json.dumps({"articles": [
        {"id": "bad", "title": "Swimmer gives verbal commitment to college", "summary": "College sports"}]}))
    with pytest.raises(SystemExit):
        pack.validate_bundle("2026-09-26", content_root=tmp_path)
    assert "excluded college recruitment" in caplog.text
