"""Tests for deep backfill + per-category degraded publish (2026-07-08).

Owner complaint: "有一些文章没有,就导致整个 reject" — one thin category
aborted the WHOLE publish (SystemExit at pack validation) and forced a
full re-run, even though probe had kept 10 briefs and the curator only
ranked 5 (the other 5 were silently discarded).

Fix:
  1. _unpicked_probe_spares — probed-but-unranked briefs become Stage-3
     spares (source-interleaved). Each still passes body/image verify +
     the full safety vet before it can ship.
  2. _split_publishable — pack decides per category: fresh cats publish,
     a still-thin cat keeps its current live content via merge mode;
     only all-cats-thin refuses to publish at all.

Run: python -m pipeline.test_backfill_degrade   (also works under pytest)
"""
from __future__ import annotations

from pipeline import full_round as fr


class _Src:
    def __init__(self, name): self.name = name


def _brief(src_name, link):
    return {"title": f"t-{link}", "link": link,
            "_source_name": src_name, "_source": _Src(src_name),
            "_probe_art": {"word_count": 500}}


# ── 1. deep backfill pool ──

def test_unpicked_probe_spares_excludes_ranked_and_interleaves():
    briefs = [_brief("A", "a1"), _brief("A", "a2"),
              _brief("B", "b1"), _brief("B", "b2"),
              _brief("C", "c1")]
    ranked = [{"id": 1, "rank": 1, "brief": briefs[0]},   # a1 ranked
              {"id": 2, "rank": 2, "brief": briefs[2]}]   # b1 ranked
    spares = fr._unpicked_probe_spares(briefs, ranked)
    links = [s["_winner_brief"]["link"] for s in spares]
    assert set(links) == {"a2", "b2", "c1"}          # ranked ones excluded
    # Source-interleaved: three distinct sources lead in first-seen order.
    assert [s["source"].name for s in spares] == ["A", "B", "C"]
    for s in spares:
        assert s["_unverified_spare"] is True
        assert s["source"].name == s["_winner_brief"]["_source_name"]
        assert s["_winner_brief"]["_probe_art"]["word_count"] == 500


def test_unpicked_probe_spares_empty_cases():
    assert fr._unpicked_probe_spares([], []) == []
    b = _brief("A", "a1")
    assert fr._unpicked_probe_spares([b], [{"id": 1, "brief": b}]) == []


# ── 2. per-category publishable split ──

def test_split_publishable_mixed():
    final = {"News": [1], "Science": [1, 2, 3], "Fun": [1, 2]}
    ok, thin = fr._split_publishable(final)
    assert ok == ["Science", "Fun"] and thin == ["News"]


def test_split_publishable_all_ok_and_all_thin():
    ok, thin = fr._split_publishable({"News": [1, 2], "Fun": [1, 2, 3]})
    assert ok == ["News", "Fun"] and thin == []
    ok2, thin2 = fr._split_publishable({"News": [], "Fun": [1]})
    assert ok2 == [] and thin2 == ["News", "Fun"]


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
