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


def test_independent_vet_failure_falls_back_to_self_scores():
    art = _article(sid=0)          # self-scores all 0 → PASS on fallback
    kept, rejected = _with_fake_vet(
        RuntimeError("LLM down"),
        lambda: core.filter_safe_rewrites({"articles": [art]}),
    )
    assert len(kept) == 1 and rejected == []


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


def test_wordcount_flags_annotated():
    short_easy = _article(sid=0, easy_words=150)   # below 200 easy floor
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


def test_easy_band_aligned_with_digest_gate():
    assert "170-210" not in core.TRI_VARIANT_REWRITER_PROMPT
    assert "210-300" in core.TRI_VARIANT_REWRITER_PROMPT


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
