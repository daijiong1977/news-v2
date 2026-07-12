"""Tests for deterministic same-story dedup in curation (2026-07-11).

Live bug: News shipped two cards about the SAME event — NYT reporters
subpoenaed over Air Force One — one from PBS, one from NPR. The curator
tagged BOTH with the same cluster_id `nyt_subpoena_af1` and subject "New
York Times", but nothing dropped the duplicate: cluster_id was never
enforced deterministically, and #43's subject-cap only guards the top 3
(the dup sat at rank 4 and got promoted when rank 3 was dropped).

Fix: `_dedupe_ranked_stories` drops, across the WHOLE ranked list, any
pick whose cluster_id repeats, whose title is near-identical, or (News)
whose subject repeats. `titles_same_story` is the shared title-overlap
predicate, reused by the Stage-3 promotion guard.

Run: python -m pipeline.test_story_dedup   (also works under pytest)
"""
from __future__ import annotations

from pipeline import mega_curator as mc


class _Src:
    def __init__(self, name): self.name = name


def _pick(rank, src, title, cluster="", subject=""):
    return {"rank": rank, "id": rank, "source": _Src(src),
            "brief": {"title": title, "_source_name": src},
            "vet": {"cluster_id": cluster, "subject": subject}}


def _ranks_titles(picks):
    return [(p["rank"], p["brief"]["title"])
            for p in sorted(picks, key=lambda p: p["rank"])]


# ── shared title predicate ──

def test_titles_same_story_detects_near_duplicate():
    assert mc.titles_same_story(
        "Typhoon Bavi makes landfall in eastern China",
        "Typhoon Bavi makes landfall in China as millions flee") is True
    assert mc.titles_same_story(
        "The biggest steam locomotive whistle-stops across the U.S.",
        "Justice Department subpoenas New York Times reporters") is False
    assert mc.titles_same_story("", "anything") is False


# ── the reported bug: same cluster_id, both shipped ──

def test_same_cluster_id_dropped_and_reranked():
    picks = [_pick(1, "NPR", "Big Boy steam locomotive tours the U.S.",
                   cluster="big_boy"),
             _pick(2, "PBS", "NYT reporters subpoenaed after Air Force One stories",
                   cluster="nyt_subpoena_af1", subject="New York Times"),
             _pick(3, "AlJazeera", "FIFA is not an independent sporting body",
                   cluster="fifa"),
             _pick(4, "NPR", "Justice Dept subpoenas NYT reporters over AF1 reporting",
                   cluster="nyt_subpoena_af1", subject="New York Times"),
             _pick(5, "PBS", "Typhoon Bavi makes landfall in eastern China",
                   cluster="typhoon")]
    out = mc._dedupe_ranked_stories({"News": picks})["News"]
    titles = [t for _, t in _ranks_titles(out)]
    # exactly one NYT story survives; ranks compacted to 1..4
    assert sum("subpoena" in t.lower() or "subpoenaed" in t.lower()
               for t in titles) == 1
    assert [p["rank"] for p in out] == [1, 2, 3, 4]
    assert "Typhoon" in " ".join(titles)          # rank-5 survivor promoted


# ── near-duplicate title with DIFFERENT cluster_id still caught ──

def test_near_duplicate_title_dropped_even_with_diff_cluster():
    picks = [_pick(1, "PBS", "Wildfires force thousands to evacuate in California",
                   cluster="ca_fire_a"),
             _pick(2, "NPR", "Wildfires force thousands to evacuate across California",
                   cluster="ca_fire_b")]     # LLM gave a different cluster_id
    out = mc._dedupe_ranked_stories({"News": picks})["News"]
    assert len(out) == 1 and out[0]["rank"] == 1


# ── News subject cap across the WHOLE list (not just top 3) ──

def test_same_subject_dropped_full_list_news_only():
    picks = [_pick(1, "NPR", "Trump signs the budget bill", subject="Donald Trump"),
             _pick(2, "PBS", "Storm hits the coast", subject=""),
             _pick(3, "BBC", "New museum opens downtown", subject=""),
             _pick(4, "AlJazeera", "Trump visits NATO summit", subject="Donald Trump")]
    news = mc._dedupe_ranked_stories({"News": [dict(p) for p in picks]})["News"]
    trump = [p for p in news if p["vet"]["subject"] == "Donald Trump"]
    assert len(trump) == 1                       # 2nd Trump dropped in News
    # Science: subject cap does NOT apply (only same story/title/cluster).
    sci = mc._dedupe_ranked_stories({"Science": [dict(p) for p in picks]})["Science"]
    assert len([p for p in sci if p["vet"]["subject"] == "Donald Trump"]) == 2


def test_distinct_stories_all_kept():
    picks = [_pick(1, "A", "Bees pollinate city rooftops", cluster="bees"),
             _pick(2, "B", "New comet visible next week", cluster="comet"),
             _pick(3, "C", "Ancient shipwreck found off Greece", cluster="wreck")]
    out = mc._dedupe_ranked_stories({"News": picks})["News"]
    assert len(out) == 3 and [p["rank"] for p in out] == [1, 2, 3]


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
