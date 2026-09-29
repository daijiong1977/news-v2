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
        self.event_calls = 0
        self.by_title: dict[str, float] = {}
        self.fit_by_title: dict[str, float] = {}
        self.sports_priority_by_title: dict[str, float] = {}
        self.value_by_title: dict[str, float] = {}
        self.neutrality_risk_by_title: dict[str, float] = {}

    def system_one(self, state, questions):
        if self.delay:
            time.sleep(self.delay)
        if "story" in state:
            assert "want" not in questions  # unused annotation must not cost a JEV answer
            self.rank_calls += 1
            t = state["story"]["headline"]
            if any(f in t for f in self.fail):
                raise RuntimeError("boom")
            answers = {
                "pick": SimpleNamespace(noul=self.by_title[t]),
                "category_fit": SimpleNamespace(
                    noul=self.fit_by_title.get((t, state["story"]["section"]),
                                               self.fit_by_title.get(t, 0.95))),
            }
            if "sports_priority" in questions:
                answers["sports_priority"] = SimpleNamespace(
                    score=self.sports_priority_by_title.get(t, 0))
            if "section_value" in questions:
                answers["section_value"] = SimpleNamespace(score=self.value_by_title.get(t, 2))
            if "neutrality_risk" in questions:
                answers["neutrality_risk"] = SimpleNamespace(
                    score=self.neutrality_risk_by_title.get(t, 0))
            return SimpleNamespace(answers=answers)
        self.pair_calls += 1
        if self.pairs_fail:
            raise RuntimeError("pair boom")
        a, b = state["headline_A"], state["headline_B"]
        if "same_event" in questions:
            self.event_calls += 1
            # "the same single event" when both headlines carry the same marker phrase
            same = any(m in a.lower() and m in b.lower()
                       for m in ("white house", "assisted dying", "fat bear week"))
            return SimpleNamespace(
                answers={"same_event": SimpleNamespace(noul=0.9 if same else 0.05)},
                usage=SimpleNamespace(input_tokens=42, output_tokens=3))
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


def _distinct(bs):
    return len({b["_source_name"] for b in bs})


def _topic_brief(title, group, pick, source, send, *, important=False):
    brief = _b(title, src=source, pick=pick)
    brief["_jev_topic_group"] = group
    brief["_jev_rank"] = {"send": send, "editorial_pick": pick,
                          "category_fit": 0.95, "floor": jr.FLOOR["News"],
                          "section_value": 3 if important else 2}
    return brief


def test_curator_shortlist_uses_comparable_new_topic_from_full_catalog():
    pool = [
        _topic_brief("Diplomacy A", "international_relations", .80, "A", True, important=True),
        _topic_brief("Diplomacy B", "international_relations", .74, "B", True),
        _topic_brief("Weather A", "severe_weather", .73, "C", True),
        _topic_brief("Weather B", "severe_weather", .69, "D", True),
        _topic_brief("Civic AI", "technology_business", .68, "E", True),
        _topic_brief("Weather C", "severe_weather", .66, "F", True),
        _topic_brief("Health", "public_health", .64, "G", False),
    ]
    original = list(pool)
    sent = jr.for_curator({"News": pool})["News"]
    assert len(sent) == 6
    assert "Health" in _titles(sent)
    assert len({b["_jev_topic_group"] for b in sent}) == 4
    assert "Diplomacy A" in _titles(sent)
    assert pool == original  # the full refill catalog remains unchanged


def test_curator_topic_variety_does_not_sacrifice_quality_or_source_diversity():
    pool = [
        _topic_brief("Important A", "international_relations", .80, "A", True, important=True),
        _topic_brief("Diplomacy B", "international_relations", .75, "B", True),
        _topic_brief("Diplomacy C", "international_relations", .70, "C", True),
        _topic_brief("Weather A", "severe_weather", .69, "D", True),
        _topic_brief("Weather B", "severe_weather", .68, "E", True),
        _topic_brief("Weather C", "severe_weather", .67, "F", True),
        _topic_brief("Low quality topic", "public_health", .42, "G", False),
        _topic_brief("Too weak", "us_politics", .35, "H", False),
        _topic_brief("Same source topic", "transport_infrastructure", .66, "A", False),
    ]
    sent = jr.for_curator({"News": pool})["News"]
    assert _titles(sent) == _titles(pool[:6])


def test_curator_ignores_unknown_topic_instead_of_treating_it_as_a_catalog():
    pool = [
        _topic_brief("Diplomacy A", "international_relations", .80, "A", True),
        _topic_brief("Diplomacy B", "international_relations", .75, "B", True),
        _topic_brief("Unknown", "other", .73, "C", True),
        _topic_brief("New group", "public_health", .72, "D", False),
    ]
    sent = jr.for_curator({"News": pool})["News"]
    assert "New group" in _titles(sent)
    assert "Unknown" in _titles(sent)


def test_deep_dig_category_gate_rejects_wrong_section_and_unscored():
    briefs = [_b("New telescope discovery", cat="Fun", pick=0.9),
              _b("Kids win football final", cat="Fun", pick=0.8),
              _b("Unscored feed item", cat="Fun", pick=0.7)]
    fake = Fake(fail=("Unscored",))
    for b in briefs:
        fake.by_title[b["title"]] = b["_p"]
    fake.fit_by_title = {"New telescope discovery": 0.15,
                         "Kids win football final": 0.91}
    kept = jr.gate_deep_dig_category("Fun", briefs, client=fake)
    assert [b["title"] for b in kept] == ["Kids win football final"]
    assert briefs[0]["_jev_category_fit"] == 0.15
    assert "_jev_category_fit" not in briefs[2]


def test_deep_dig_never_admits_news_from_sports_article_url():
    sport = _b("Ireland wears black armbands for Israel game", cat="News", pick=0.9)
    sport["link"] = "https://www.bbc.co.uk/sport/football/articles/example"
    fake = Fake()
    fake.by_title[sport["title"]] = 0.9
    fake.fit_by_title = {sport["title"]: 0.99}
    assert jr.gate_deep_dig_category("News", [sport], client=fake) == []


def test_news_neutrality_gate_excludes_loaded_briefs_even_from_refill_catalog():
    loaded = [
        _b("Fairness protectors cut in half, leaving disabled children helpless",
           src="A", pick=0.98),
        _b("Aid airdrop saves starving city as one army blocks every escape",
           src="B", pick=0.95),
    ]
    factual = _b("Government reports office closures and complaint backlog",
                 src="C", pick=0.70)
    attributed = _b("Officials dispute cause of food shortage near front line",
                    src="D", pick=0.65)
    fake = Fake()
    fake.neutrality_risk_by_title = {
        loaded[0]["title"]: 3.0,
        loaded[1]["title"]: 4.0,
        attributed["title"]: 2.0,
    }
    for b in loaded + [factual, attributed]:
        fake.by_title[b["title"]] = b["_p"]
    out, report = jr.rank_briefs({"News": loaded + [factual, attributed]}, client=fake)
    assert _titles(out["News"]) == [factual["title"], attributed["title"]]
    assert len([item for item in report["skipped"]
                if item["why"] == "one-sided or unsupported framing"]) == 2
    assert attributed["_jev_rank"]["neutrality_risk"] == 2.0
    assert fake.rank_calls == 4  # neutrality rides in the existing per-brief call


def test_news_neutrality_gate_also_applies_to_late_deep_dig():
    loaded = _b("One side blamed for every shortage", pick=0.9)
    factual = _b("Aid groups describe food deliveries and disputed access", pick=0.8)
    fake = Fake()
    fake.by_title = {b["title"]: b["_p"] for b in (loaded, factual)}
    fake.neutrality_risk_by_title = {loaded["title"]: 3.0,
                                      factual["title"]: 2.0}
    assert jr.gate_deep_dig_category("News", [loaded, factual], client=fake) == [factual]


def test_deep_dig_category_gate_fails_closed_when_jev_unavailable():
    brief = _b("Unexpected science story", cat="Fun", pick=0.8)
    old = jr.make_client
    jr.make_client = lambda: (None, "test outage")
    try:
        assert jr.gate_deep_dig_category("Fun", [brief]) == []
    finally:
        jr.make_client = old


def test_deep_dig_borderline_checks_other_sections():
    hurricane = _b("Hurricane approaching Hawaii", cat="Science", pick=0.8)
    sports = _b("Kids win a close football final", cat="Fun", pick=0.8)
    fake = Fake()
    fake.by_title = {b["title"]: b["_p"] for b in (hurricane, sports)}
    fake.fit_by_title = {
        (hurricane["title"], "Science"): 0.61,
        (hurricane["title"], "News"): 0.84,
        (hurricane["title"], "Fun"): 0.10,
        (sports["title"], "Fun"): 0.66,
        (sports["title"], "News"): 0.14,
        (sports["title"], "Science"): 0.20,
    }
    assert jr.gate_deep_dig_category("Science", [hurricane], client=fake) == []
    assert hurricane["_jev_other_category_fit"]["News"] == 0.84
    assert jr.gate_deep_dig_category("Fun", [sports], client=fake) == [sports]
    assert sports["_jev_other_category_fit"]["Science"] == 0.20


def test_orders_by_pick_and_keeps_full_catalog_for_refill():
    pool = [_b(f"Story {i:02d} alpha{i}", src=f"S{i % 5}", pick=0.55 + i / 100) for i in range(14)]
    (out, rep), _ = _run({"Science": pool})
    assert len(out["Science"]) == len(pool)
    assert [b["_jev_rank"]["pos"] for b in out["Science"]] == list(range(1, len(pool) + 1))
    assert len(_sent(out, "Science")) == jr.TO_CURATOR == len(rep["sent"]["Science"])
    reserve = [b["_jev_rank"]["pick"] for b in out["Science"] if not b["_jev_rank"]["send"]]
    assert reserve == sorted(reserve, reverse=True)


def test_major_swimming_and_tennis_news_get_soft_priority_without_extra_calls():
    ordinary = _b("Singer rehearses a routine song", src="Music", cat="Fun", pick=0.65)
    swim = _b("Swimmer breaks world record at championships", src="SwimSwam", cat="Fun", pick=0.55)
    tennis = _b("Tennis star wins US Open final", src="BBC Tennis", cat="Fun", pick=0.56)
    fake = Fake()
    fake.by_title = {b["title"]: b["_p"] for b in (ordinary, swim, tennis)}
    fake.sports_priority_by_title = {swim["title"]: 4, tennis["title"]: 4}
    out, report = jr.rank_briefs({"Fun": [ordinary, swim, tennis]}, client=fake)
    assert fake.rank_calls == 3  # extra judgment in the same per-brief call
    assert _titles(out["Fun"][:3]) == [tennis["title"], swim["title"], ordinary["title"]]
    assert tennis["_jev_rank"]["editorial_pick"] == 0.74
    assert swim["_jev_rank"]["sports_priority"] == 4
    assert report["sent"]["Fun"][0]["raw_pick"] == 0.56


def test_old_tennis_recap_and_wrong_section_do_not_gain_priority():
    recap = _b("Tennis star recalls match from last month", src="BBC", cat="Fun", pick=0.60)
    major = _b("Swimmer breaks world record", src="SwimSwam", cat="Fun", pick=0.52)
    wrong = _b("Scientists discover a new atom", src="Science", cat="Fun", pick=0.95)
    fake = Fake()
    fake.by_title = {b["title"]: b["_p"] for b in (recap, major, wrong)}
    fake.sports_priority_by_title = {recap["title"]: 1, major["title"]: 4}
    fake.fit_by_title[wrong["title"]] = 0.1
    out, _ = jr.rank_briefs({"Fun": [recap, major, wrong]}, client=fake)
    assert major["_jev_rank"]["editorial_pick"] == 0.70
    assert recap["_jev_rank"]["editorial_pick"] == 0.60
    assert wrong["title"] not in _sent(out, "Fun")


def test_one_source_never_takes_more_than_the_hard_ceiling():
    """The cap is 2 and may yield by one when the alternatives are far worse
    (0.88 vs 0.62 here), but never beyond HARD_PER_SOURCE."""
    pool = [_b(f"Tennis item number{i}", src="BBC Tennis", pick=0.9 - i / 100) for i in range(5)]
    pool += [_b(f"Other piece word{i}", src=f"Src{i}", pick=0.62 - i / 100) for i in range(6)]
    (out, rep), _ = _run({"Fun": pool})
    six = jr.for_curator(out)["Fun"]
    assert len(six) == 7 and sum(b["_source_name"] == "BBC Tennis" for b in six) == jr.HARD_PER_SOURCE
    assert _distinct(six) >= jr.MIN_DISTINCT_SOURCES
    assert any("from this source" in d["why"] for d in rep["skipped"])


def test_near_identical_headlines_are_deduped_by_code_without_asking_jev():
    pool = [_b("Scientists test Einstein gravity with exotic matter", src="A", pick=0.9),
            _b("Scientists test Einstein gravity with exotic matter today", src="B", pick=0.8)]
    pool += [_b(f"Zebra{i} quokka{i}", src=f"C{i}", pick=0.62) for i in range(6)]
    (out, _), fake = _run({"Science": pool})
    assert sum("Einstein" in t for t in _sent(out, "Science")) == 1 and fake.pair_calls == 0


def test_reworded_duplicate_is_caught_by_jev():
    pool = [_b("MPs vote against fresh attempt to legalise assisted dying", src="A", pick=0.9),
            _b("An extraordinary result - why MPs rejected the assisted dying bill", src="B", pick=0.8)]
    pool += [_b(f"Zebra{i} quokka{i}", src=f"C{i}", pick=0.62) for i in range(6)]
    (out, rep), fake = _run({"News": pool})
    assert sum("assisted dying" in t for t in _sent(out, "News")) == 1
    assert fake.pair_calls >= 1 and any("same story" in d["why"] for d in rep["skipped"])
    # The known duplicate must not return from the refill catalog.
    assert "An extraordinary result - why MPs rejected the assisted dying bill" not in _titles(out["News"])


def test_news_subject_is_capped_not_banned():
    pool = [_b(t, src=f"S{i}", pick=0.95 - i / 100) for i, t in enumerate(TRUMP[:5])]
    pool += [_b(t, src=f"V{i}", pick=0.62 - i / 100) for i, t in enumerate(VOLCANO)]
    (out, rep), _ = _run({"News": pool})
    six = _sent(out, "News")
    assert sum("Trump" in t for t in six) == jr.MAX_SAME_SUBJECT and sum(t in VOLCANO for t in six) == 3
    assert any("about the same subject" in d["why"] for d in rep["skipped"])


def test_subject_rule_is_news_only():
    pool = [_b(t, src=f"S{i}", cat="Fun", pick=0.9 - i / 100) for i, t in enumerate(TRUMP[:6])]
    (out, _), _ = _run({"Fun": pool})
    assert sum("Trump" in t for t in _sent(out, "Fun")) == 6


def test_current_candidate_pools_do_not_compare_across_sections():
    news = [_b("Ed Sheeran concert goes ahead after assisted dying row", src="AJ", pick=0.9)] + \
           [_b(f"World event summit{i}", src=f"N{i}", pick=0.62) for i in range(5)]
    fun = [_b("Ed Sheeran breaks silence on assisted dying tour row", src="RS", cat="Fun", pick=0.7)] + \
          [_b(f"Game release title{i}", src=f"F{i}", cat="Fun", pick=0.62) for i in range(5)]
    (out, rep), _ = _run({"News": news, "Fun": fun})
    assert any("Sheeran" in t for t in _sent(out, "Fun"))
    assert any("Sheeran" in t for t in _sent(out, "News")) and len(_sent(out, "News")) == 6
    assert list(out) == ["News", "Fun"]                      # caller's category order preserved


def test_same_section_history_blocks_rewordings_but_ignores_other_sections():
    recent = ["Ms. Rachel has entered her album era, and she is so happy about it",                  # ran as News
              "Journalists report being denied White House access after Trump bans some outlets",
              "Ed Sheeran concert set to go ahead after outcry over Gaza"]
    fun = [_b("Ms. Rachel has entered her album era, and she is so happy about it", src="NPR Music", cat="Fun", pick=0.9)]
    fun += [_b(t, src=f"F{i}", cat="Fun", pick=0.5) for i, t in enumerate(VOLCANO)]
    news = [_b("CNN, MS NOW, Politico reporters denied access to White House following Trump ban", src="NPR", pick=0.9),
            _b("Ed Sheeran admits mistakes as he addresses Macklemore controversy", src="BBC", pick=0.8)]
    news += [_b(t, src=f"N{i}", pick=0.62) for i, t in enumerate(TRUMP[:4])]
    fake = Fake()
    for bs in (fun, news):
        for b in bs:
            fake.by_title[b["title"]] = b["_p"]
    out, rep = jr.rank_briefs({"News": news, "Fun": fun}, client=fake, recent_titles={"News": recent, "Fun": []})
    assert any("Rachel" in t for t in _sent(out, "Fun"))                     # News history is not Fun history
    assert not any("White House" in t for t in _sent(out, "News"))           # reworded: Jev
    assert any("Sheeran admits" in t for t in _sent(out, "News"))            # a new development is still news
    assert sum("same story as published" in d["why"] for d in rep["skipped"]) == 1
    assert not any("White House" in t for t in _titles(out["News"]))        # cannot return as a spare


def test_fat_bear_same_category_event_check_is_measured():
    old = "Alaska's salmon-feasting bears face off in biggest Fat Bear Week ever"
    new = _b("Fat bear week celebrates its twelfth year", cat="Fun", pick=0.8)
    fake = Fake()
    q_rank, q_story, q_both, q_event = jr._questions()
    pairs = jr._Pairs(fake, q_story, q_both, q_event, time.monotonic() + 10)
    assert pairs.already_published(new, [old]) == old
    assert pairs.published_calls == pairs.calls == 1
    assert pairs.published_input_tokens == 42
    assert pairs.published_output_tokens == 3


def test_below_floor_is_held_back_until_the_pool_is_thin():
    """A weak candidate is not sent while better ones exist, but a thin category
    still fills to MIN_SEND rather than going blank."""
    strong = [_b(t, src=f"S{i}", pick=0.9 - i / 100) for i, t in enumerate(VOLCANO)]      # 4 well above
    weak = [_b(t, src=f"W{i}", pick=0.10) for i, t in enumerate(TRUMP[:4])]               # 4 far below
    (out, rep), _ = _run({"Science": strong + weak})
    sent = _sent(out, "Science")
    assert len(sent) == 4 and all(t in VOLCANO for t in sent)          # floor kept the weak ones out
    assert rep["below_floor"]["Science"] == 0
    assert any("below the Science floor" in d["why"] for d in rep["skipped"])

    # Only two clear the floor: fill to MIN_SEND from the best of the rest.
    (out, rep), _ = _run({"Science": strong[:2] + weak})
    sent = _sent(out, "Science")
    assert len(sent) == jr.MIN_SEND and rep["below_floor"]["Science"] == jr.MIN_SEND - 2


def test_wrong_section_story_is_hard_blocked_and_not_a_spare():
    """A science discovery must not ship as Fun, even on a thin day."""
    science_in_fun = _b(
        "Interstellar comet may reveal clues to life",
        src="Live Science", cat="Fun", pick=0.99,
    )
    fun = [_b(f"Young musician wins contest {i}", src=f"F{i}", cat="Fun", pick=0.8 - i / 100)
           for i in range(4)]
    fake = Fake()
    for b in [science_in_fun] + fun:
        fake.by_title[b["title"]] = b["_p"]
    fake.fit_by_title[science_in_fun["title"]] = 0.05
    out, rep = jr.rank_briefs({"Fun": [science_in_fun] + fun}, client=fake)
    assert science_in_fun["title"] not in _sent(out, "Fun")
    assert science_in_fun["_jev_category_fit"] == 0.05
    assert any("category fit" in d["why"] for d in rep["skipped"])


def test_news_event_family_is_grouped_before_curator():
    """The live 2026-09-25 Trump-Xi failure becomes one event group."""
    summit = [
        _b("US and China must act together, Xi says as Trump hosts state dinner",
           src="BBC", pick=0.95),
        _b("AI, trade, Iran and Taiwan top agenda at Trump-Xi summit",
           src="PBS", pick=0.94),
        _b("Xi got Trump's red carpet welcome but not everything he wanted",
           src="BBC2", pick=0.93),
    ]
    for b in summit:
        b["summary"] = "Xi and Trump met at the White House during China's state visit to discuss trade."
    other_titles = [
        "Hurricane approaches Hawaii with heavy rain",
        "Supreme Court pauses Missouri voting map change",
        "Iran offers to reopen key oil waterway",
        "New museum opens in Nairobi",
        "Farmers test drought resistant wheat",
    ]
    other = [_b(t, src=f"N{i}", pick=0.8 - i / 100)
             for i, t in enumerate(other_titles)]
    (out, rep), _ = _run({"News": summit + other})
    sent_summit = [b for b in jr.for_curator(out)["News"] if "Xi" in b["title"]]
    assert len(sent_summit) == 1
    groups = {b.get("_event_group") for b in summit}
    assert len(groups) == 1 and None not in groups
    assert sum("same story" in d["why"] for d in rep["skipped"]) >= 2


def test_news_floor_is_lower_than_science():
    """News scores systematically lower for this audience; one global floor would
    send 6 Science and 0 News. See FLOOR in jev_rank."""
    assert jr.FLOOR["News"] < jr.FLOOR["Science"]
    pool = [_b(t, src=f"S{i}", pick=0.45) for i, t in enumerate(VOLCANO)]
    (news, _), _ = _run({"News": [dict(b) for b in pool]})
    (sci, rep), _ = _run({"Science": [dict(b, _category="Science") for b in pool]})
    assert len(_sent(news, "News")) == 4                                # 0.45 clears the News floor
    assert rep["below_floor"]["Science"] == jr.MIN_SEND                 # ...but not the Science one


def test_source_cap_yields_when_the_alternative_is_much_worse():
    """Ed Sheeran 0.38 (3rd from BBC) must beat a 0.28 filler from another source."""
    pool = [_b(t, src="BBC News", pick=p) for t, p in zip(TRUMP[:3], (0.65, 0.53, 0.45))]
    pool += [_b(t, src=f"Other{i}", pick=p) for i, (t, p) in enumerate(zip(VOLCANO, (0.60, 0.55, 0.20, 0.19)))]
    (out, _), _ = _run({"News": pool})
    six = jr.for_curator(out)["News"]
    assert TRUMP[2] in _sent(out, "News")                              # the 3rd BBC item got through
    assert sum(1 for b in six if b["_source_name"] == "BBC News") == 3
    assert _distinct(six) >= jr.MIN_DISTINCT_SOURCES                   # ...without starving diversity


def test_a_pool_that_cannot_be_diverse_still_gets_the_best_briefs():
    """BBC 0.65/0.53/0.45 + one other source above the floor: three distinct
    sources are unreachable either way, so send quality rather than hold back."""
    pool = [_b(t, src="BBC News", pick=p) for t, p in zip(TRUMP[:3], (0.65, 0.53, 0.45))]
    pool += [_b(t, src=f"Other{i}", pick=p) for i, (t, p) in enumerate(zip(VOLCANO, (0.60, 0.20, 0.19, 0.18)))]
    (out, _), _ = _run({"News": pool})
    six = jr.for_curator(out)["News"]
    assert sum(1 for b in six if b["_source_name"] == "BBC News") == jr.HARD_PER_SOURCE
    assert len(six) == 4 and _distinct(six) == 2


def test_source_cap_holds_when_the_alternative_is_close():
    pool = [_b(t, src="BBC News", pick=p) for t, p in zip(TRUMP[:3], (0.65, 0.60, 0.55))]
    pool += [_b(t, src=f"Other{i}", pick=0.52 - i / 100) for i, t in enumerate(VOLCANO)]
    (out, rep), _ = _run({"News": pool})
    assert sum(1 for b in jr.for_curator(out)["News"] if b["_source_name"] == "BBC News") == jr.MAX_PER_SOURCE
    assert any("from this source" in d["why"] for d in rep["skipped"])


def test_thin_pool_relaxes_caps_but_never_sends_a_duplicate_story():
    pool = [_b(f"Tennis item number{i}", src="BBC Tennis", pick=0.9 - i / 100) for i in range(5)]
    (out, _), _ = _run({"Fun": pool})
    assert len(_sent(out, "Fun")) == jr.MIN_SEND    # one source: ceiling gives way to MIN_SEND, no further


def test_unscored_brief_ranks_last_and_is_not_lost():
    pool = [_b(f"Item word{i}", src=f"S{i}", pick=0.5 + i / 100) for i in range(8)] + [_b("flaky one", src="Z", pick=0.99)]
    (out, _), _ = _run({"Science": pool}, Fake(fail=("flaky",)))
    assert _titles(out["Science"])[-1] == "flaky one" and len(out["Science"]) == 9


def test_failure_modes_return_none_so_the_caller_falls_back():
    pool = {"News": [_b(f"flaky {i}", pick=0.5) for i in range(6)] + [_b(f"fine {i}", pick=0.62) for i in range(4)]}
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


def test_already_published_is_asked_once_per_brief():
    """_select asks hard_reason up to three times per brief. Without a cache each
    ask re-sent the same Jev calls and inflated the reported count."""
    recent = ["MPs vote against fresh attempt to legalise assisted dying"]
    pool = [_b("An extraordinary result - why MPs rejected the assisted dying bill", src="A", pick=0.9)]
    pool += [_b(t, src="BBC News", pick=0.8 - i / 100) for i, t in enumerate(TRUMP[:3])]
    pool += [_b(t, src=f"V{i}", pick=0.1) for i, t in enumerate(VOLCANO)]   # below floor, forces the fills
    fake = Fake()
    for b in pool:
        fake.by_title[b["title"]] = b["_p"]
    out, rep = jr.rank_briefs({"News": pool}, client=fake, recent_titles={"News": recent})
    assert not any("assisted dying" in t for t in _sent(out, "News"))   # it was published
    # One recent title, one brief that shares words with it: one ask, not one per pass.
    # One recent title shares >=2 content words with exactly one brief. _select asks
    # hard_reason for that brief in the main pass and again in each fill: 1 call, not 3.
    assert fake.event_calls == 1, f"{fake.event_calls} already-published calls — the cache is not working"


def test_scratch_state_never_survives_onto_the_briefs():
    """_jev_pick is internal to _select. A failure mid-selection used to leave it
    on every brief, and the caller checkpoints those briefs."""
    pool = {"News": [_b(t, src=f"S{i}", pick=0.8) for i, t in enumerate(VOLCANO)]}
    ok, _ = _run(pool)
    assert not any(k.startswith("_jev_pick") for b in pool["News"] for k in b)

    pool2 = {"News": [_b(t, src=f"S{i}", pick=0.8) for i, t in enumerate(VOLCANO)]}
    real, jr._select = jr._select, lambda *a, **k: (_ for _ in ()).throw(ZeroDivisionError("boom"))
    try:
        out, rep = _run(pool2)[0]
    finally:
        jr._select = real
    assert out is None and "unexpected error" in rep["jev"]
    assert not any(k.startswith("_jev_pick") for b in pool2["News"] for k in b)


def test_a_fill_pass_reports_the_real_blocking_reason():
    """A brief deferred by the source cap, then blocked by a duplicate when the
    fills run, must be reported as the duplicate — not as 'capped'."""
    pool = [_b("Volcano buries Icelandic fishing harbour", src="A", pick=0.9),
            _b("Volcano buries Icelandic fishing harbour today", src="B", pick=0.2)]
    pool += [_b(t, src="BBC News", pick=0.8 - i / 100) for i, t in enumerate(TRUMP[:3])]
    (out, rep), _ = _run({"News": pool})
    whys = {d["title"]: d["why"] for d in rep["skipped"]}
    dup = "Volcano buries Icelandic fishing harbour today"
    assert dup in whys and "same story" in whys[dup], whys


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
