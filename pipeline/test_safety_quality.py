"""Tests for the safety & content-quality batch (2026-07-08).

Covers:
  1. Independent safety vet — a separate LLM call scores the rewritten
     bodies; the rewriter's self-scores are only a fallback. (The author
     must not be the only gate on its own text.)
  2. Deterministic forbidden-term backstop over the REWRITTEN bodies
     (self-harm etc. previously only screened RSS title/summary).
  3. Word-count flags at generation time (the digest gates 200-320 easy /
     300-410 middle, but nothing measured until the next day).
  4. Prompt band alignment — the easy band told the model 170-210 words
     while QA gates at 200-320, manufacturing body_too_short tickets.

Run: python -m pipeline.test_safety_quality   (also works under pytest)
"""
from __future__ import annotations

from pipeline import news_rss_core as core


def _article(sid=0, middle_words=340, easy_words=250, middle_text=None, safety=None):
    mid = middle_text or ("word " * middle_words).strip()
    return {
        "source_id": sid,
        "easy_en": {"headline": "E", "card_summary": "c", "body": ("word " * easy_words).strip()},
        "middle_en": {"headline": "M", "card_summary": "c", "body": mid},
        "zh": {"headline": "标题", "summary": "摘要"},
        "safety": safety if safety is not None else {d: 0 for d in core.SAFETY_DIMS},
    }


def _clean_scores(sid=0, **overrides):
    dims = {d: 0 for d in core.SAFETY_DIMS}
    dims.update(overrides)
    return {"scores": {str(sid): dims}}


def _with_fake_vet(payload_or_exc, fn):
    orig = core.deepseek_call
    def fake(system, user, max_tokens, **kw):
        if isinstance(payload_or_exc, Exception):
            raise payload_or_exc
        return payload_or_exc
    core.deepseek_call = fake
    try:
        return fn()
    finally:
        core.deepseek_call = orig


def test_independent_vet_overrides_clean_self_scores():
    # Rewriter says "all clean"; the independent vet finds violence=4 → REJECT.
    art = _article(sid=0)          # self-scores all 0
    kept, rejected = _with_fake_vet(
        _clean_scores(0, violence=4),
        lambda: core.filter_safe_rewrites({"articles": [art]}),
    )
    assert kept == [] and len(rejected) == 1
    assert rejected[0]["safety"]["violence"] == 4          # independent won
    assert rejected[0]["safety_self"]["violence"] == 0     # self kept for telemetry


def test_independent_vet_reads_chinese_and_english_cards(monkeypatch):
    article = _article()
    article["zh"] = {"headline": "公平守护者被砍掉", "summary": "投诉被直接扔掉"}
    seen = []
    def fake(system, user, max_tokens, **kw):
        seen.append((system, user))
        return _clean_scores(0, bias=3)
    monkeypatch.setattr(core, "deepseek_call", fake)
    scores = core.independent_safety_vet([article])
    assert scores[0]["bias"] == 3
    assert "公平守护者被砍掉" in seen[0][1]
    assert "published Chinese headline" in seen[0][1]
    assert "card summaries" in seen[0][0]


def test_independent_vet_failure_falls_back_to_self_scores():
    art = _article(sid=0)          # self-scores all 0 → PASS on fallback
    kept, rejected = _with_fake_vet(
        RuntimeError("LLM down"),
        lambda: core.filter_safe_rewrites({"articles": [art]}),
    )
    assert len(kept) == 1 and rejected == []


def test_one_malformed_vet_row_retries_without_discarding_other_rows(monkeypatch):
    first = _clean_scores(0, fear=2)
    first["scores"]["1"] = {d: 0 for d in core.SAFETY_DIMS}
    first["scores"]["1"]["fear"] = None
    calls = []

    def fake(system, user, max_tokens, **kw):
        calls.append(user)
        return first if len(calls) == 1 else _clean_scores(1, fear=1)

    monkeypatch.setattr(core, "deepseek_call", fake)
    articles = [_article(sid=0), _article(sid=1)]
    kept, rejected = core.filter_safe_rewrites({"articles": articles})
    assert len(calls) == 2 and "source_id=1" in calls[1]
    assert rejected == []
    assert [a["safety"]["fear"] for a in kept] == [2, 1]
    assert all(a["_independent_vet_status"] == "scored" for a in kept)


def test_malformed_retry_falls_back_only_for_that_article(monkeypatch):
    first = _clean_scores(0, fear=2)
    first["scores"]["1"] = {d: 0 for d in core.SAFETY_DIMS}
    first["scores"]["1"]["fear"] = None
    monkeypatch.setattr(core, "deepseek_call", lambda *args, **kwargs: first)
    kept, rejected = core.filter_safe_rewrites({"articles": [_article(0), _article(1)]})
    assert rejected == []
    assert [a["_independent_vet_status"] for a in kept] == ["scored", "fallback"]
    assert kept[0]["safety"]["fear"] == 2
    assert kept[1]["safety"]["fear"] == 0


def test_forbidden_term_in_rewritten_body_rejects():
    # Independent vet returns clean scores, but the rewritten middle body
    # carries a self-harm term → deterministic backstop REJECTs.
    bad_body = ("word " * 150) + "the note mentioned suicide " + ("word " * 150)
    art = _article(sid=0, middle_text=bad_body)
    kept, rejected = _with_fake_vet(
        _clean_scores(0),
        lambda: core.filter_safe_rewrites({"articles": [art]}),
    )
    assert kept == [] and len(rejected) == 1
    assert "forbidden" in rejected[0]["_safety_eval"]["reason"].lower()


def test_wordcount_flags_annotated(monkeypatch):
    monkeypatch.setattr(core, "repair_wordcounts", lambda *args: 0)
    short_easy = _article(sid=0, easy_words=core.WC_BANDS["easy"][0] - 20)
    kept, _ = _with_fake_vet(
        _clean_scores(0),
        lambda: core.filter_safe_rewrites({"articles": [short_easy]}),
    )
    assert len(kept) == 1
    flags = kept[0].get("_wc_flags") or []
    assert any("easy" in f for f in flags)

    ok = _article(sid=0)                            # 250/340 — in band
    kept2, _ = _with_fake_vet(
        _clean_scores(0),
        lambda: core.filter_safe_rewrites({"articles": [ok]}),
    )
    assert not (kept2[0].get("_wc_flags") or [])


def test_outside_digest_tolerance_rejected_after_failed_repair(monkeypatch):
    monkeypatch.setattr(core, "repair_wordcounts", lambda *args: 0)
    art = _article(sid=0, middle_words=203)
    kept, rejected = _with_fake_vet(
        _clean_scores(0),
        lambda: core.filter_safe_rewrites({"articles": [art]}),
    )
    assert not kept
    assert len(rejected) == 1
    assert "word-count QA" in rejected[0]["_safety_eval"]["reason"]


def test_easy_band_aligned_with_digest_gate():
    """The easy word band is stated in four places: the rewriter prompt, the
    repair targets, the generation-time QA band, and quality_digest's gate.
    They drift silently — the prompt is prose, the rest are tuples — and the
    symptom is a morning full of body_too_short tickets for bodies the
    rewriter was told to write. Assert all four agree."""
    from pipeline.quality_digest import BODY_TARGETS, WC_SLACK

    assert core.WC_QA_SLACK == WC_SLACK

    for level in ("easy", "middle"):
        t_lo, t_hi = core.WC_REPAIR_TARGETS[level]
        b_lo, b_hi = core.WC_BANDS[level]
        assert f"{t_lo}-{t_hi} words" in core.TRI_VARIANT_REWRITER_PROMPT, \
            f"{level}: prompt does not state the repair target {t_lo}-{t_hi}"
        assert b_lo < t_lo and t_hi < b_hi, \
            f"{level}: QA band {b_lo}-{b_hi} must sit outside repair target {t_lo}-{t_hi}"
        assert BODY_TARGETS[level] == core.WC_BANDS[level], \
            f"{level}: quality_digest gate {BODY_TARGETS[level]} != WC_BANDS {core.WC_BANDS[level]}"


# ── per-dimension safety thresholds (2026-07-08) ──

def _safety(**dims):
    base = {d: 0 for d in core.SAFETY_DIMS}
    base.update(dims)
    return {"safety": base}


def test_moderate_news_dims_pass():
    # War/politics/conflict at a MODERATE level (3) is allowed for a news site.
    assert core.evaluate_rewriter_safety(
        _safety(violence=3, fear=3, distress=3, adult_themes=3, bias=2), category="News"
    )["verdict"] == "PASS"


def test_prominent_one_sided_framing_rejected_at_3():
    assert core.evaluate_rewriter_safety(_safety(bias=3), category="News")["verdict"] == "REJECT"
    assert core.evaluate_rewriter_safety(_safety(bias=3), category="Fun")["verdict"] == "PASS"


def test_severe_news_dim_rejected():
    # Graphic/severe (>=4) still rejects.
    assert core.evaluate_rewriter_safety(_safety(violence=4))["verdict"] == "REJECT"
    assert core.evaluate_rewriter_safety(_safety(fear=5))["verdict"] == "REJECT"


def test_factual_war_death_is_not_an_automatic_safety_reject(monkeypatch):
    article = _article(middle_text=("The war continued. One person died. Talks continued. " * 38).strip())
    monkeypatch.setattr(core, "repair_hard_news_safety",
                        lambda art: (_ for _ in ()).throw(AssertionError("unneeded repair")))
    monkeypatch.setattr(core, "independent_safety_vet", lambda arts: {
        0: {**{d: 0 for d in core.SAFETY_DIMS}, "violence": 1, "adult_themes": 2}})
    kept, rejected = core.filter_safe_rewrites({"articles": [article]}, category="News")
    assert len(kept) == 1 and not rejected
    assert kept[0]["_independent_vet_status"] == "scored"


def test_severe_hard_news_gets_one_rewrite_and_fresh_independent_vet(monkeypatch):
    article = _article()
    scores = [{**{d: 0 for d in core.SAFETY_DIMS}, "fear": 4, "distress": 4},
              {**{d: 0 for d in core.SAFETY_DIMS}, "fear": 1, "distress": 1}]
    calls = []
    def fake_vet(arts):
        calls.append(arts[0]["middle_en"]["body"])
        return {0: scores.pop(0)}
    monkeypatch.setattr(core, "independent_safety_vet", fake_vet)
    monkeypatch.setattr(core, "deepseek_call", lambda *args, **kwargs: {
        "middle_body": "calm " * 350, "easy_body": "calm " * 200})
    kept, rejected = core.filter_safe_rewrites({"articles": [article]}, category="News")
    assert len(kept) == 1 and not rejected
    assert len(calls) == 2 and calls[0] != calls[1]
    assert kept[0]["_independent_vet_status"] == "scored_after_repair"


def test_hard_news_repair_that_fails_fresh_vet_stays_rejected(monkeypatch):
    article = _article()
    monkeypatch.setattr(core, "independent_safety_vet", lambda arts: {
        0: {**{d: 0 for d in core.SAFETY_DIMS}, "violence": 4}})
    monkeypatch.setattr(core, "deepseek_call", lambda *args, **kwargs: {
        "middle_body": "calm " * 350, "easy_body": "calm " * 200})
    kept, rejected = core.filter_safe_rewrites({"articles": [article]}, category="News")
    assert not kept and len(rejected) == 1
    assert rejected[0]["_safety_eval"]["scores"]["violence"] == 4


def test_news_bias_gets_one_source_grounded_rewrite_and_fresh_vet(monkeypatch):
    article = _article()
    article["zh"] = {"headline": "一座快饿死的城市", "summary": "一方的说法"}
    scores = [{**{d: 0 for d in core.SAFETY_DIMS}, "bias": 3},
              {d: 0 for d in core.SAFETY_DIMS}]
    reviews = []
    def fake_vet(arts):
        reviews.append(arts[0]["zh"]["headline"])
        return {0: scores.pop(0)}
    def fake_rewrite(inputs, category, editorial_feedback):
        assert category == "News" and inputs[0][1]["body"] == "source facts and both responses"
        assert "Do not invent" in editorial_feedback
        revised = _article()
        revised["zh"] = {"headline": "乌克兰空投食物，双方回应当地短缺", "summary": "双方说法各有归属"}
        return {"articles": [revised]}
    monkeypatch.setattr(core, "independent_safety_vet", fake_vet)
    monkeypatch.setattr(core, "tri_variant_rewrite", fake_rewrite)
    kept, rejected = core.filter_safe_rewrites(
        {"articles": [article]}, {0: {"body": "source facts and both responses"}},
        category="News")
    assert not rejected and len(kept) == 1
    assert reviews == ["一座快饿死的城市", "乌克兰空投食物，双方回应当地短缺"]
    assert kept[0]["_independent_vet_status"] == "scored_after_neutrality_repair"


def test_news_bias_with_no_source_for_repair_stays_rejected(monkeypatch):
    article = _article()
    monkeypatch.setattr(core, "independent_safety_vet", lambda arts: {
        0: {**{d: 0 for d in core.SAFETY_DIMS}, "bias": 3}})
    kept, rejected = core.filter_safe_rewrites({"articles": [article]}, category="News")
    assert not kept and len(rejected) == 1
    assert "bias=3" in rejected[0]["_safety_eval"]["reason"]


def test_strict_or_non_news_rejection_does_not_enter_repair(monkeypatch):
    article = _article()
    monkeypatch.setattr(core, "repair_hard_news_safety",
                        lambda art: (_ for _ in ()).throw(AssertionError("bad repair")))
    monkeypatch.setattr(core, "independent_safety_vet", lambda arts: {
        0: {**{d: 0 for d in core.SAFETY_DIMS}, "language": 3, "fear": 4}})
    assert len(core.filter_safe_rewrites({"articles": [article]}, category="News")[1]) == 1
    assert len(core.filter_safe_rewrites({"articles": [_article()]}, category="Fun")[1]) == 1


def test_strict_dims_still_reject_at_3():
    # Sexual / substance / language are never-appropriate regardless of news value.
    for d in ("sexual", "substance", "language"):
        assert core.evaluate_rewriter_safety(_safety(**{d: 3}))["verdict"] == "REJECT", d


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
