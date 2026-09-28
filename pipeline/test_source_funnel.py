"""Tests for source fairness and metadata-first, bounded body verification.

The 2026-07-08 source-starvation fix interleaves briefs before JEV ranking.
The ranked-body stage now fetches only the top 12 originals per section and
extends in groups of six when too few survive length/image checks.

Run: python -m pipeline.test_source_funnel   (also works under pytest)
"""
from __future__ import annotations

from pipeline import full_round as fr


def _b(src: str, title: str) -> dict:
    return {"title": title, "_source_name": src}


def test_phase_a_source_limit_expands_fun_only():
    assert fr.phase_a_source_limit("Fun") == 10
    assert fr.phase_a_source_limit("News") == 8
    assert fr.phase_a_source_limit("Science") == 8
    assert fr.phase_a_source_limit("Other") == 8


# ── 1. round-robin interleave ──

def test_interleave_round_robins_sources():
    briefs = ([_b("A", f"a{i}") for i in range(4)]
              + [_b("B", f"b{i}") for i in range(4)]
              + [_b("C", f"c{i}") for i in range(2)])
    out = fr._interleave_by_source(briefs)
    # First pass touches every source once, in first-seen order.
    assert [x["_source_name"] for x in out[:3]] == ["A", "B", "C"]
    # Within-source order preserved.
    assert [x["title"] for x in out if x["_source_name"] == "A"] == \
        ["a0", "a1", "a2", "a3"]
    # Nothing lost, nothing duplicated.
    assert sorted(x["title"] for x in out) == sorted(x["title"] for x in briefs)


def test_interleave_handles_empty_and_single_source():
    assert fr._interleave_by_source([]) == []
    solo = [_b("A", "a0"), _b("A", "a1")]
    assert fr._interleave_by_source(solo) == solo


def test_fun_short_sources_pass_late_body_gate_but_news_and_science_do_not():
    assert fr._probe_min_words("Fun") == 250
    assert fr._probe_min_words("News") == fr._probe_min_words("Science") == 350
    assert fr._source_length_check("Fun", {"word_count": 250})[0]
    assert not fr._source_length_check("News", {"word_count": 250})[0]
    assert not fr._source_length_check("Science", {"word_count": 349})[0]


def test_science_source_ceiling_is_1500_after_shortlist():
    assert fr._probe_max_words("Science") == 1500
    assert fr._probe_max_words("News") == fr._probe_max_words("Fun") == 1200
    assert fr._source_length_check("Science", {"word_count": 1500})[0]
    assert not fr._source_length_check("Science", {"word_count": 1501})[0]
    assert not fr._source_length_check("Fun", {"word_count": 1201})[0]


def test_jev_and_deepseek_checkpoint_precede_ranked_body_probe():
    from pipeline.checkpoints import STAGES
    assert STAGES.index("stage1") < STAGES.index("stage1_jev") \
        < STAGES.index("phase_a_probe") < STAGES.index("jev_rank") \
        < STAGES.index("ranked_body_probe") < STAGES.index("stage2_picks")


def test_metadata_interleave_keeps_every_source_without_fetching_originals():
    ordered = []
    for src in ("PBS", "NPR", "AJ", "BBC"):
        ordered += [_b(src, f"{src}-{i}") for i in range(4)]
    inter = fr._metadata_catalog({"News": ordered})["News"]
    assert [b["_source_name"] for b in inter[:4]] == ["PBS", "NPR", "AJ", "BBC"]
    assert all("_probe_art" not in b and "word_count" not in b for b in inter)


def test_ranked_body_probe_stops_after_first_12_when_six_pass():
    catalog = [_b("NPR", str(i)) for i in range(20)]
    fetched = []
    def fetch(brief):
        fetched.append(brief["title"])
        wc = 100 if int(brief["title"]) < 6 else 500
        return {**brief, "word_count": wc, "og_image": "https://x/real.jpg"}
    valid, remaining, report = fr._probe_ranked_catalog("News", catalog, fetch=fetch)
    assert report["batches"] == [12]
    assert report["fetched"] == 12 and len(valid) == 6
    assert len(remaining) == 14 and len(fetched) == 12
    assert [b["title"] for b in valid] == [str(i) for i in range(6, 12)]
    assert all("_probe_art" not in b for b in catalog[12:])


def test_ranked_body_probe_refills_six_then_stops():
    catalog = [_b("NPR", str(i)) for i in range(25)]
    def fetch(brief):
        wc = 100 if int(brief["title"]) < 9 else 500
        return {**brief, "word_count": wc, "og_image": "https://x/real.jpg"}
    valid, remaining, report = fr._probe_ranked_catalog("News", catalog, fetch=fetch)
    assert report["batches"] == [12, 6]
    assert report["fetched"] == 18 and len(valid) == 9
    assert len(remaining) == 16
    assert all("_probe_art" not in b for b in catalog[18:])


def test_ranked_body_probe_preserves_image_gate_and_fun_target_seven():
    catalog = [_b("BBC", str(i)) for i in range(19)]
    def fetch(brief):
        n = int(brief["title"])
        return {**brief, "word_count": 300, "og_image": None if n < 6 else "https://x/real.jpg"}
    valid, _, report = fr._probe_ranked_catalog("Fun", catalog, fetch=fetch)
    assert report["batches"] == [12, 6]
    assert len(valid) == 12 and report["rejected"] == 6


def test_ranked_body_probe_uses_destination_section_range():
    brief = _b("TIME for Kids", "Animal research")
    def fetch(b):
        return {**b, "word_count": 339, "og_image": "https://x/real.jpg"}
    fun_valid, _, _ = fr._probe_ranked_catalog("Fun", [dict(brief)], fetch=fetch)
    science_valid, _, report = fr._probe_ranked_catalog("Science", [dict(brief)], fetch=fetch)
    assert len(fun_valid) == 1
    assert science_valid == [] and report["rejected"] == 1


def test_ranked_body_probe_fetch_error_refills_without_abort():
    catalog = [_b("NPR", str(i)) for i in range(15)]
    def fetch(brief):
        if int(brief["title"]) < 8:
            raise TimeoutError("article page timed out")
        return {**brief, "word_count": 500, "og_image": "https://x/real.jpg"}
    valid, _, report = fr._probe_ranked_catalog("News", catalog, fetch=fetch)
    assert report["batches"] == [12, 3]
    assert len(valid) == 7 and report["rejected"] == 8


# ── 3. verify_picks_lazy per-source stats ──

class _Src:
    def __init__(self, name): self.name = name


def test_verify_picks_lazy_records_per_source_stats():
    npr = _Src("NPR World")
    good = {"word_count": 400, "og_image": "https://x/real.jpg", "title": "good"}
    bad = {"word_count": 400, "og_image": None, "title": "bad"}
    ranked = {"News": [
        {"id": 1, "rank": 1, "source": npr,
         "brief": {"_probe_art": bad, "_source_name": "NPR World"}},
        {"id": 2, "rank": 2, "source": npr,
         "brief": {"_probe_art": good, "_source_name": "NPR World"}},
    ]}
    stats: dict = {}
    out = fr.verify_picks_lazy(ranked, max_top=4, stats=stats)
    verified = [s for s in out["News"] if not s.get("_unverified_spare")]
    assert len(verified) == 1
    assert verified[0]["winner"]["title"] == "good"
    s = stats["News"]["NPR World"]
    assert s["verified"] == 1
    assert s["rejects"] == {"no og:image": 1}


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
