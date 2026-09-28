"""Tests for repair_wordcounts — the deterministic word-band enforcement
that runs before the Stage 3 safety vet.

Bug: docs/bugs/2026-09-15-middle-body-wordcount-repair.md
"""
import pipeline.news_rss_core as core
from pipeline.quality_digest import score_article
from pipeline.wordcount_policy import body_band


def _art(easy_wc: int, middle_wc: int) -> dict:
    return {
        "source_id": 0,
        "easy_en": {"headline": "h", "body": " ".join(["w"] * easy_wc)},
        "middle_en": {"headline": "h", "body": " ".join(["w"] * middle_wc)},
    }


def test_short_fun_prompt_uses_shorter_targets_only_for_short_source():
    short = {"title": "Tennis final", "body": "sport " * 270, "word_count": 270}
    long = {"title": "Long feature", "body": "sport " * 450, "word_count": 450}
    fun_prompt = core.tri_variant_rewriter_input([(0, short), (1, long)], category="Fun")
    assert fun_prompt.count("This Fun source is short") == 1
    assert "easy body 135–185 words; middle body 265–315 words" in fun_prompt
    assert "This Fun source is short" not in core.tri_variant_rewriter_input(
        [(0, short)], category="News")


def test_short_fun_bands_align_generation_and_published_digest():
    assert body_band("easy", category="Fun", source_word_count=270) == (120, 220)
    assert body_band("middle", category="Fun", source_word_count=270) == (250, 350)
    assert core._wc_within_qa("middle", 245, category="Fun", source_word_count=270)
    assert not core._wc_within_qa("middle", 245, category="News", source_word_count=270)
    payload = {"summary": "word " * 245, "category": "Fun", "source_word_count": 270,
               "source_name": "BBC", "image_url": "https://example.org/image.jpg"}
    metrics = score_article(payload, "middle")
    assert metrics["body_ok"] and metrics["body_target"] == "250-350 (±15%)"
    assert not score_article({**payload, "category": "News"}, "middle")["body_ok"]


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


def test_accepts_repair_inside_digest_tolerance(monkeypatch):
    """A 285-word repair is below the ideal band but clears the ±15% QA gate."""
    monkeypatch.setattr(core, "deepseek_call",
                        lambda *a, **k: {"body": " ".join(["x"] * 285)})
    rr = {"articles": [_art(250, 203)]}
    assert core.repair_wordcounts(rr) == 1
    assert len(rr["articles"][0]["middle_en"]["body"].split()) == 285


def test_second_deepseek_edit_uses_failed_count_and_original_source(monkeypatch):
    prompts = []
    lengths = iter((240, 350))

    def fake_call(system, user, **kwargs):
        prompts.append(user)
        return {"body": " ".join(["x"] * next(lengths))}

    monkeypatch.setattr(core, "deepseek_call", fake_call)
    rr = {"articles": [_art(250, 203)]}
    assert core.repair_wordcounts(rr, {0: {"body": "SOURCE_MARKER " * 500}}) == 1
    assert len(prompts) == 2
    assert "240 words" in prompts[1] and "SOURCE_MARKER" in prompts[1]
    assert len(rr["articles"][0]["middle_en"]["body"].split()) == 350


def test_second_edit_can_shorten_after_first_still_too_long(monkeypatch):
    lengths = iter((501, 370))
    calls = []

    def fake(system, user, **kwargs):
        calls.append((system, user))
        return {"body": " ".join(["x"] * next(lengths))}

    monkeypatch.setattr(core, "deepseek_call", fake)
    rr = {"articles": [_art(250, 503)]}
    assert core.repair_wordcounts(rr) == 1
    assert len(rr["articles"][0]["middle_en"]["body"].split()) == 370
    assert len(calls) == 2
    assert calls[1][0] == core.WC_REPAIR_REWRITE_PROMPT
    assert "501 words" in calls[1][1] and "ORIGINAL BODY" in calls[1][1]


def test_retry_cannot_replace_qa_acceptable_draft_with_worse_one(monkeypatch):
    lengths = iter((285, 240))
    monkeypatch.setattr(core, "deepseek_call", lambda *a, **k: {
        "body": " ".join(["x"] * next(lengths))})
    rr = {"articles": [_art(250, 203)]}
    assert core.repair_wordcounts(rr) == 1
    assert len(rr["articles"][0]["middle_en"]["body"].split()) == 285


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
