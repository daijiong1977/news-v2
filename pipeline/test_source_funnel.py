"""Tests for per-source funnel fairness + telemetry (2026-07-08).

Root cause found via checkpoint reconstruction of the 2026-07-08 run:
the Stage-1.5 probe cap (PROBE_MAX_PER_CAT=10) consumed briefs in source-
priority order, so with 4 News sources × 4 briefs the first three sources
filled the cap and BBC (priority 4) never reached the curator — on any day
the earlier feeds are healthy. Fix: round-robin interleave briefs across
sources before the cap, and record a per-source tally at each funnel stage
(probe / verify / stage-3) so the next starvation is visible in telemetry.

Run: python -m pipeline.test_source_funnel   (also works under pytest)
"""
from __future__ import annotations

from pipeline import full_round as fr


def _b(src: str, title: str) -> dict:
    return {"title": title, "_source_name": src}


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


# ── 2. probe partition: classify per source, cap without silent starvation ──

def _r(src: str, i: int, wc: int) -> dict:
    return {"brief": _b(src, f"{src}{i}"), "art": {"word_count": wc}, "wc": wc}


def test_partition_classifies_thin_long_and_cap():
    results = [_r("A", 0, 500), _r("B", 0, 200),   # B0 thin
               _r("A", 1, 2000), _r("B", 1, 500),  # A1 long
               _r("A", 2, 500), _r("B", 2, 500)]   # B2 over cap
    kept, tally = fr._partition_probe_results(results, 350, 1200, cap=3)
    assert [b["title"] for b in kept] == ["A0", "B1", "A2"]
    # Kept briefs carry the cached article + word_count (probe contract).
    assert kept[0]["_probe_art"] == {"word_count": 500}
    assert kept[0]["word_count"] == 500
    assert tally["A"] == {"in": 3, "kept": 2, "thin": 0, "long": 1, "cap_cut": 0}
    assert tally["B"] == {"in": 3, "kept": 1, "thin": 1, "long": 0, "cap_cut": 1}


def test_interleave_plus_cap_keeps_every_source_represented():
    # The 2026-07-08 regression: 4 sources × 4 briefs, all pass the word
    # gate, cap 10 — in priority order the 4th source got zero slots.
    ordered = []
    for src in ("PBS", "NPR", "AJ", "BBC"):
        ordered += [_b(src, f"{src}-{i}") for i in range(4)]
    inter = fr._interleave_by_source(ordered)
    results = [{"brief": b, "art": {"word_count": 500}, "wc": 500} for b in inter]
    kept, tally = fr._partition_probe_results(results, 350, 1200, cap=10)
    kept_srcs = {b["_source_name"] for b in kept}
    assert kept_srcs == {"PBS", "NPR", "AJ", "BBC"}, f"starved: {kept_srcs}"
    # Fair split: every source lands 2-3 of the 10 slots.
    for src in ("PBS", "NPR", "AJ", "BBC"):
        assert 2 <= tally[src]["kept"] <= 3, tally


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
