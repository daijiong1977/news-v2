import json
from dataclasses import asdict

import pytest

from pipeline import agent_shadow as runner
from pipeline.ai_providers import AgentNeeded
from pipeline.news_sources import NewsSource


def source():
    return NewsSource(1, "BBC News", "https://example.invalid/feed", "full", 10, 350, 1, True, False)


def test_catalog_rejects_unknown_duplicate_scores_and_uncertainty_shape():
    valid = {"catalog": {c: [] for c in runner.CATS}}
    valid["catalog"]["News"] = [{"id": "c001", "topic": "politics", "importance": 4,
        "initial_risk": 1, "history_status": "clear", "history_confidence": .9}]
    assert not runner.validate_catalog(valid, {"c001"})
    valid["catalog"]["Fun"] = valid["catalog"]["News"]
    assert runner.validate_catalog(valid, {"c001"})


def test_answer_correction_is_bounded(tmp_path):
    runner.write(tmp_path / "metrics.json", {"steps": []})
    with pytest.raises(AgentNeeded) as pending:
        runner.ask(tmp_path, "rank", "Rank", {}, lambda v: ["bad ID"])
    need = pending.value
    runner.write(need.answer, {"request_id": need.request_id, "content": "{}", "finish_reason": "stop"})
    with pytest.raises(AgentNeeded, match="agent answer required"):
        runner.ask(tmp_path, "rank", "Rank", {}, lambda v: ["bad ID"])
    with pytest.raises(RuntimeError, match="one correction"):
        runner.ask(tmp_path, "rank", "Rank", {}, lambda v: ["bad ID"])


def test_full_shadow_round_and_resume_never_call_llm_http(tmp_path, monkeypatch):
    from pipeline import news_rss_core
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("HTTP model/write forbidden"))
    candidates = [{"id": f"c{i}", "category": c, "title": "Title", "summary": "summary",
                   "link": f"https://example.invalid/{i}", "source": "BBC News", "published": ""}
                  for i, c in enumerate(runner.CATS)]
    snapshot = {"date": "2026-09-30", "candidates": candidates, "history": {c: [] for c in runner.CATS},
                "sources": {"BBC News": asdict(source())}}
    runner.write(tmp_path / "input.json", snapshot)
    runner.write(tmp_path / "metrics.json", {"steps": [], "body_fetches": 0})
    monkeypatch.setattr(news_rss_core, "process_entry", lambda b, **k: {**b, "body": "fact " * 400,
                       "word_count": 400, "skip_reason": None, "og_image": "https://example.invalid/image.jpg"})
    def answer(root, key, system, material, validate):
        if key == "rank":
            value = {"catalog": {b["category"]: [{"id": b["id"], "topic": b["category"],
                        "importance": 4, "initial_risk": 0, "history_status": "clear", "history_confidence": 1}]
                        for b in candidates}}
        elif key.startswith("pick"):
            value = {"order": [b["id"] for b in material]}
        elif key.startswith("rewrite"):
            value = {"articles": [{"source_id": 0,
                "easy_en": {"headline": "Easy", "body": "fact " * 170, "card_summary": "Card"},
                "middle_en": {"headline": "Middle", "body": "fact " * 330, "card_summary": "Card"},
                "zh": {"headline": "标题", "summary": "摘要"}}]}
        else:
            assert "safety" not in material["article"]
            value = {"scores": {"0": {d: 0 for d in news_rss_core.SAFETY_DIMS}}, "facts_supported": True}
        assert not validate(value)
        return value
    monkeypatch.setattr(runner, "ask", answer)
    result = runner.advance(tmp_path)
    assert result["counts"] == {"news": 1, "science": 1, "fun": 1}
    assert (tmp_path / "site/index.html").exists()
    assert runner.advance(tmp_path)["already_done"]
    assert runner.read(tmp_path / "metrics.json")["body_fetches"] == 3


def test_exact_history_url_blocks_even_when_model_says_clear(tmp_path, monkeypatch):
    from pipeline import news_rss_core
    monkeypatch.setattr(news_rss_core, "process_entry", lambda *a, **k: pytest.fail("should not fetch duplicate"))
    runner.write(tmp_path / "metrics.json", {"steps": [], "body_fetches": 0})
    snapshot = {"candidates": [{"id": "c1", "link": "https://example.invalid/a?utm_source=x"}],
                "history": {"News": [{"source_url": "https://example.invalid/a"}]}}
    ranked = {"News": [{"id": "c1", "history_status": "clear", "history_confidence": 1, "initial_risk": 0}]}
    assert runner.body_pool(tmp_path, snapshot, ranked) == {"News": []}
