"""Tests for the per-subject cap in News pickup (2026-07-08).

Owner ask: yesterday all 3 News stories were about Trump. Cap any single
dominant subject (person/org) to ONE story in News's top 3, and fill the
freed slots with different-subject candidates.

Mechanism: the curator tags each pick with a `subject` (dominant named
person/org, "" if none). `_enforce_top3_subject_diversity` is a
deterministic backstop — mirrors `_enforce_top3_source_diversity` — that
swaps a repeated-subject pick out of the top 3 for a different-subject
spare. Scoped to News. Empty subject never collides (generic stories).

Run: python -m pipeline.test_subject_cap   (also works under pytest)
"""
from __future__ import annotations

from pipeline import mega_curator as mc


class _Src:
    def __init__(self, name): self.name = name


def _pick(rank, subject, src):
    return {"rank": rank, "id": rank, "source": _Src(src),
            "brief": {}, "vet": {"subject": subject}}


def _subs(picks):
    return [p["vet"]["subject"]
            for p in sorted(picks, key=lambda p: p["rank"])[:3]]


def _srcs(picks):
    return [p["source"].name
            for p in sorted(picks, key=lambda p: p["rank"])[:3]]


# ── 1. core cap ──

def test_caps_repeated_subject_and_fills_from_spares():
    picks = [_pick(1, "Donald Trump", "NPR"),
             _pick(2, "Donald Trump", "BBC"),
             _pick(3, "Donald Trump", "PBS"),
             _pick(4, "Climate", "AlJazeera"),
             _pick(5, "Space", "Reuters")]
    out = mc._enforce_top3_subject_diversity({"News": picks})["News"]
    subs = _subs(out)
    assert subs.count("Donald Trump") == 1
    assert len(set(subs)) == 3                 # 3 distinct subjects ship
    # A diverse-source fill was available, so source diversity survives too.
    assert len(set(_srcs(out))) == 3
    assert len(out) == 5 and len({p["rank"] for p in out}) == 5


def test_empty_subject_never_counts_as_duplicate():
    # Two "no dominant subject" stories are NOT a collision.
    picks = [_pick(1, "", "NPR"), _pick(2, "", "BBC"),
             _pick(3, "Donald Trump", "PBS"),
             _pick(4, "Climate", "AlJazeera"), _pick(5, "Space", "Reuters")]
    out = mc._enforce_top3_subject_diversity({"News": picks})["News"]
    assert _subs(out) == ["", "", "Donald Trump"]   # untouched


# ── 2. scope: News only ──

def test_non_news_categories_untouched():
    picks = [_pick(1, "NASA", "A"), _pick(2, "NASA", "B"),
             _pick(3, "NASA", "C"), _pick(4, "Ocean", "D"), _pick(5, "Bugs", "E")]
    out = mc._enforce_top3_subject_diversity({"Science": [dict(p) for p in picks]})
    assert _subs(out["Science"]) == ["NASA", "NASA", "NASA"]


# ── 3. graceful degrade ──

def test_no_diverse_spare_leaves_picks_intact():
    picks = [_pick(i, "Donald Trump", s)
             for i, s in enumerate(["NPR", "BBC", "PBS", "AlJazeera", "Reuters"], 1)]
    out = mc._enforce_top3_subject_diversity({"News": picks})["News"]
    # Nothing to swap to — degrades (still all Trump) but no crash / no loss.
    assert len(out) == 5 and _subs(out).count("Donald Trump") == 3


def test_prefers_spare_that_also_keeps_source_diversity():
    # Two candidate fills differ in subject; only one keeps 3 distinct sources.
    picks = [_pick(1, "Donald Trump", "NPR"),
             _pick(2, "Donald Trump", "BBC"),
             _pick(3, "Weather", "PBS"),
             _pick(4, "Climate", "NPR"),        # different subject but source NPR (dup)
             _pick(5, "Space", "Reuters")]      # different subject AND new source
    out = mc._enforce_top3_subject_diversity({"News": picks})["News"]
    subs = _subs(out)
    assert subs.count("Donald Trump") == 1
    assert len(set(_srcs(out))) == 3            # picked Reuters, not the NPR dup


# ── 4. prompt carries the rule ──

def test_prompt_has_subject_field_and_news_cap_rule():
    p = mc.MEGA_CURATOR_SYSTEM_PROMPT
    assert '"subject"' in p
    assert "subject" in p.lower() and "News" in p
    # names the failure mode so the model has an anchor
    assert "one" in p.lower()


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
