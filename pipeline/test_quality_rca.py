"""Regression checks for the September 2026 quality-digest failures."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from pipeline import autofix_apply as af
from pipeline import full_round as fr


def test_body_autofix_requires_source_for_expansion(monkeypatch):
    monkeypatch.setattr(af, "_deepseek_call", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not call the model without source material")))
    payload = {"summary": "word " * 203, "keywords": []}
    ok, msg, _ = af._fix_body(payload, "middle", 300, 410, "short")
    assert not ok and "source article unavailable" in msg


def test_body_autofix_rejects_out_of_band_output(monkeypatch):
    monkeypatch.setattr(af, "_deepseek_call", lambda *a, **k: {"body": "word " * 203})
    payload = {"summary": "old " * 203, "keywords": []}
    ok, _, detail = af._fix_body(payload, "middle", 300, 410, "short", "source " * 600)
    assert not ok and not detail["in_target"]
    assert payload["summary"].startswith("old")


def test_body_autofix_uses_source_and_accepts_qa_band(monkeypatch):
    prompts = []

    def fake(system, prompt, **kwargs):
        prompts.append(prompt)
        return {"body": "word " * 285}

    monkeypatch.setattr(af, "_deepseek_call", fake)
    payload = {"summary": "old " * 203, "keywords": []}
    ok, _, detail = af._fix_body(payload, "middle", 300, 410, "short", "SOURCE_MARKER " * 600)
    assert ok and detail["in_target"]
    assert "SOURCE_MARKER" in prompts[0]


def test_body_autofix_retries_with_failed_count(monkeypatch):
    prompts = []
    lengths = iter((240, 350))

    def fake(system, prompt, **kwargs):
        prompts.append(prompt)
        return {"body": "word " * next(lengths)}

    monkeypatch.setattr(af, "_deepseek_call", fake)
    payload = {"summary": "old " * 203, "keywords": []}
    ok, _, detail = af._fix_body(
        payload, "middle", 300, 410, "short", "SOURCE_MARKER " * 600)
    assert ok and detail["in_ideal"]
    assert len(prompts) == 2 and "240 words" in prompts[1]
    assert "SOURCE_MARKER" in prompts[1]
    assert _count(payload["summary"]) == 350


def _count(text):
    return len(text.split())


def test_body_autofix_retry_shortens_long_draft(monkeypatch):
    lengths = iter((501, 370))
    monkeypatch.setattr(af, "_deepseek_call", lambda *a, **k: {
        "body": "word " * next(lengths)})
    payload = {"summary": "old " * 503, "keywords": []}
    ok, _, detail = af._fix_body(payload, "middle", 300, 410, "long")
    assert ok and detail["wc_after"] == 370


def test_body_autofix_keeps_first_qa_draft_if_retry_worse(monkeypatch):
    lengths = iter((285, 240))
    monkeypatch.setattr(af, "_deepseek_call", lambda *a, **k: {
        "body": "word " * next(lengths)})
    payload = {"summary": "old " * 203, "keywords": []}
    ok, _, detail = af._fix_body(payload, "middle", 300, 410, "short", "source " * 600)
    assert ok and detail["wc_after"] == 285 and not detail["in_ideal"]


def test_autofix_does_not_upload_when_safety_review_fails(monkeypatch):
    row = {"id": 1, "published_date": "2026-09-25", "story_id": "2026-09-25-news-1",
           "level": "middle", "problem_type": "body_too_long", "attempts": 0}
    monkeypatch.setattr(af, "_patch_row", lambda *a, **k: None)
    monkeypatch.setattr(af, "_fetch_json", lambda *a, **k: {"summary": "old " * 500, "keywords": []})
    monkeypatch.setattr(af, "_fix_body", lambda *a, **k: (True, "rewritten", {}))
    monkeypatch.setattr(af, "_safe_rewrite_for_storage", lambda *a, **k: (False, "unsafe"))
    monkeypatch.setattr(af, "_upload_payload_json", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("unsafe rewrite must not be uploaded")))
    result = af.process_row(row, dry_run=False)
    assert result["outcome"] == "escalated"


def test_storage_rewrite_requires_independent_verdict(monkeypatch):
    from pipeline import news_rss_core as core

    monkeypatch.setattr(af, "_fetch_json", lambda *a, **k: {"summary": "safe counterpart"})
    monkeypatch.setattr(core, "independent_safety_vet", lambda *a, **k: {})
    ok, reason = af._safe_rewrite_for_storage(
        "2026-09-25", "2026-09-25-news-1", "middle", "new safe body")
    assert not ok and "no valid verdict" in reason


def test_keyword_weave_cannot_remove_required_terms(monkeypatch):
    monkeypatch.setattr(af, "_deepseek_call", lambda *a, **k: {
        "action": "weave", "body": "The story is still readable."})
    payload = {"summary": "old body", "keywords": [{"term": "telescope"}]}
    ok, _, _ = af._fix_keyword(payload, ["telescope"])
    assert not ok and payload["summary"] == "old body"


def test_autofix_scans_archived_days_not_current_static_bundle(monkeypatch):
    from pipeline import quality_autofix as qa

    seen = []
    monkeypatch.setattr(qa, "autofix_day", lambda date_iso, dry_run: (
        seen.append(date_iso) or {"date": date_iso, "queued": [], "skipped": []}))
    today = datetime.now(qa.ET).date()
    qa.run(3, dry_run=True)
    assert seen == [(today - timedelta(days=i)).isoformat() for i in (1, 2, 3)]


def test_final_source_preference_uses_safe_fourth_pick():
    winners = [{"source": SimpleNamespace(name=name)} for name in ("A", "A", "B", "C")]
    articles = [{"id": i} for i in range(4)]
    ordered_w, ordered_a = fr._prefer_final_source_diversity(winners, articles)
    assert [w["source"].name for w in ordered_w[:3]] == ["A", "B", "C"]
    assert [a["id"] for a in ordered_a[:3]] == [0, 2, 3]


def test_new_source_spare_never_falls_back_to_repeated_source():
    # The explicit new-source request must leave a repeated-source spare
    # untouched, even when it would be the first/only candidate.
    spare = {"_unverified_spare": True, "source": SimpleNamespace(name="A"),
             "_winner_brief": {"title": "A different story"}}
    pool = [spare]
    winner, article = fr.promote_spare_and_rewrite(
        "Fun", pool, used_source_names={"A"}, require_new_source=True)
    assert winner is None and article is None and pool == [spare]


def test_new_source_spare_gets_normal_safety_gate(monkeypatch):
    from pipeline import news_rss_core as core

    monkeypatch.setattr(core, "verify_article_content", lambda art: (True, None))
    monkeypatch.setattr(fr, "tri_variant_rewrite", lambda articles, category: {
        "articles": [{"source_id": 0}]})
    checked = []
    monkeypatch.setattr(fr, "filter_safe_rewrites", lambda result, sources: (
        checked.append(sources[0]["title"]) or result["articles"], []))
    pool = [{"_unverified_spare": True, "source": SimpleNamespace(name="C"),
             "_winner_brief": {"title": "Swimming record at world championships",
                               "_probe_art": {"title": "Swimming record at world championships",
                                              "link": "https://example.com/swim"}}}]
    winner, article = fr.promote_spare_and_rewrite(
        "Fun", pool, used_source_names={"A", "B"}, require_new_source=True)
    assert winner["source"].name == "C" and article["source_id"] == 0
    assert checked == ["Swimming record at world championships"]
