"""Tests for repair_wordcounts — the deterministic word-band enforcement
that runs before the Stage 3 safety vet.

Bug: docs/bugs/2026-09-15-middle-body-wordcount-repair.md
"""
import pipeline.news_rss_core as core


def _art(easy_wc: int, middle_wc: int) -> dict:
    return {
        "source_id": 0,
        "easy_en": {"headline": "h", "body": " ".join(["w"] * easy_wc)},
        "middle_en": {"headline": "h", "body": " ".join(["w"] * middle_wc)},
    }


def test_repairs_long_middle_body(monkeypatch):
    calls = []

    def fake_call(system, user, max_tokens, temperature=0.2, **kw):
        calls.append(user)
        return {"body": " ".join(["x"] * 350)}

    monkeypatch.setattr(core, "deepseek_call", fake_call)
    rr = {"articles": [_art(250, 724)]}
    assert core.repair_wordcounts(rr) == 1
    assert len(rr["articles"][0]["middle_en"]["body"].split()) == 350
    # easy was in band → exactly one repair call, for middle only
    assert len(calls) == 1
    assert "724 words" in calls[0]


def test_keeps_original_when_repair_still_out_of_band(monkeypatch):
    monkeypatch.setattr(core, "deepseek_call",
                        lambda *a, **k: {"body": " ".join(["x"] * 500)})
    rr = {"articles": [_art(250, 724)]}
    assert core.repair_wordcounts(rr) == 0
    assert len(rr["articles"][0]["middle_en"]["body"].split()) == 724


def test_keeps_original_when_call_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("transport down")

    monkeypatch.setattr(core, "deepseek_call", boom)
    rr = {"articles": [_art(190, 350)]}  # easy short → 1 attempted repair
    assert core.repair_wordcounts(rr) == 0
    assert len(rr["articles"][0]["easy_en"]["body"].split()) == 190


def test_in_band_bodies_make_no_llm_calls(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("deepseek_call must not run for in-band bodies")

    monkeypatch.setattr(core, "deepseek_call", boom)
    rr = {"articles": [_art(250, 350)]}
    assert core.repair_wordcounts(rr) == 0


def test_short_easy_body_expanded(monkeypatch):
    monkeypatch.setattr(core, "deepseek_call",
                        lambda *a, **k: {"body": " ".join(["x"] * 240)})
    # Below the easy QA floor, whatever the band currently is.
    too_short = core.WC_BANDS["easy"][0] - 20
    rr = {"articles": [_art(too_short, 350)]}
    assert core.repair_wordcounts(rr) == 1
    assert len(rr["articles"][0]["easy_en"]["body"].split()) == 240


# --- source-article threading (the 2026-09-15 echo-back regression) ---

def test_expand_prompt_carries_source_article(monkeypatch):
    """Too-short bodies must get the SOURCE article as raw material —
    without it the model echoed the input back unchanged."""
    calls = []

    def fake_call(system, user, max_tokens, temperature=0.2, **kw):
        calls.append(user)
        return {"body": " ".join(["x"] * 350)}

    monkeypatch.setattr(core, "deepseek_call", fake_call)
    rr = {"articles": [_art(250, 254)]}          # middle too short
    srcs = {0: {"body": "SOURCE_MATERIAL_MARKER " + " ".join(["s"] * 50)}}
    assert core.repair_wordcounts(rr, srcs) == 1
    assert "EXPAND" in calls[0]
    assert "SOURCE ARTICLE" in calls[0]
    assert "SOURCE_MATERIAL_MARKER" in calls[0]


def test_shrink_prompt_has_no_source_section(monkeypatch):
    calls = []

    def fake_call(system, user, max_tokens, temperature=0.2, **kw):
        calls.append(user)
        return {"body": " ".join(["x"] * 350)}

    monkeypatch.setattr(core, "deepseek_call", fake_call)
    rr = {"articles": [_art(250, 724)]}          # middle too long
    srcs = {0: {"body": "SOURCE_MATERIAL_MARKER"}}
    assert core.repair_wordcounts(rr, srcs) == 1
    assert "SHORTEN" in calls[0]
    assert "SOURCE ARTICLE" not in calls[0]


def test_expand_without_source_still_attempts(monkeypatch):
    """Missing source (e.g. the spare-promotion path) must not crash."""
    monkeypatch.setattr(core, "deepseek_call",
                        lambda *a, **k: {"body": " ".join(["x"] * 350)})
    rr = {"articles": [_art(250, 254)]}
    assert core.repair_wordcounts(rr, None) == 1
