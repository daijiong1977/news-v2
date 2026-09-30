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


def test_outer_answer_correction_is_bounded(tmp_path):
    runner.write(tmp_path / "metrics.json", {"steps": []})
    with pytest.raises(AgentNeeded) as pending:
        runner.ask(tmp_path, "rank", "Rank", {}, lambda v: [])
    pending.value.answer.write_text("not json")
    with pytest.raises(AgentNeeded):
        runner.ask(tmp_path, "rank", "Rank", {}, lambda v: [])
    with pytest.raises(RuntimeError, match="one correction"):
        runner.ask(tmp_path, "rank", "Rank", {}, lambda v: [])


@pytest.mark.parametrize("stepwise", [False, True])
def test_full_shadow_round_and_resume_never_call_llm_http(tmp_path, monkeypatch, stepwise):
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
    monkeypatch.setattr("pipeline.image_optimize.fetch_and_optimize", lambda *a, **k: None)
    def answer(root, key, system, material, validate):
        if key == "rank":
            value = {"catalog": {b["category"]: [{"id": b["id"], "topic": b["category"],
                        "importance": 4, "initial_risk": 0, "history_status": "clear", "history_confidence": 1}]
                        for b in candidates}}
        elif key.startswith("pick"):
            value = {"order": [b["id"] for b in material]}
        elif key.startswith("rewrite"):
            value = {"articles": [{"source_id": 0,
                "safety": {d: 0 for d in news_rss_core.SAFETY_DIMS},
                "easy_en": {"headline": "Easy", "body": "fact " * 170, "card_summary": "Card"},
                "middle_en": {"headline": "Middle", "body": "fact " * 330, "card_summary": "Card"},
                "zh": {"headline": "标题", "summary": "摘要"}}]}
        elif key.startswith("details"):
            value = {"details": {f"0_{level}": {
                "keywords": [{"term": "fact", "explanation": "Something known."}],
                "questions": [{"question": "What is here?", "options": ["fact", "a", "b", "c"],
                               "correct_answer": "fact"} for _ in range(6)],
                "background_read": ["Facts explain the world."], "Article_Structure": ["WHAT: facts"],
                "why_it_matters": "We learn facts.", "perspectives": [{"perspective": "Readers", "description": "Learn facts."}]
            } for level in ("easy", "middle")}}
        else:
            assert "safety" not in material["article"]
            value = {"scores": {"0": {d: 0 for d in news_rss_core.SAFETY_DIMS}}, "facts_supported": True}
        assert not validate(value)
        return value
    monkeypatch.setattr(runner, "ask", answer)
    stops = []
    for _ in range(80):
        try:
            result = runner.advance(tmp_path, stepwise=stepwise)
            break
        except runner.StepFinished as finished:
            stops.append(finished.result["completed_step"])
    else:
        pytest.fail("stepwise run did not finish")
    if stepwise:
        assert stops[0] == "rank" and stops[-1] == "pack"
        assert len(stops) == len(set(stops))
        assert "details-News-c0" in stops
        assert "review-details-News-c0" in stops
    assert result["counts"] == {"news": 1, "science": 1, "fun": 1}
    assert (tmp_path / "site/index.html").exists()
    assert runner.advance(tmp_path)["already_done"]
    assert runner.read(tmp_path / "metrics.json")["body_fetches"] == 3
    detail = runner.read(tmp_path / "site/article_payloads/payload_2026-09-30-news-1/easy.json")
    assert len(detail["questions"]) == 6
    assert detail["keywords"][0]["term"] == "fact"


def test_step_stops_after_rank_before_any_original_fetch(tmp_path, monkeypatch):
    runner.write(tmp_path / "input.json", {"date": "2026-09-30", "candidates": [], "history": {}})
    monkeypatch.setattr(runner, "ask", lambda *a, **k: {"catalog": {c: [] for c in runner.CATS}})
    monkeypatch.setattr(runner, "body_pool", lambda *a, **k: pytest.fail("crossed rank boundary"))
    with pytest.raises(runner.StepFinished) as finished:
        runner.advance(tmp_path, stepwise=True)
    assert finished.value.result["completed_step"] == "rank"
    assert runner.read(tmp_path / "completed-steps.json") == ["rank"]


def test_details_catch_misaligned_keywords_and_bad_quiz():
    from pipeline.agent_shadow_details import validate_details
    entries = {0: {"easy_en": {"body": "planet"}, "middle_en": {"body": "orbit"}}}
    value = {"details": {f"0_{l}": {"keywords": [{"term": "elephant", "explanation": "An animal"}],
                        "questions": []} for l in ("easy", "middle")}}
    errors = validate_details(value, entries)
    assert any("keyword must occur" in e for e in errors)
    assert any("six questions" in e for e in errors)


def test_exact_history_url_blocks_even_when_model_says_clear(tmp_path, monkeypatch):
    from pipeline import news_rss_core
    monkeypatch.setattr(news_rss_core, "process_entry", lambda *a, **k: pytest.fail("should not fetch duplicate"))
    runner.write(tmp_path / "metrics.json", {"steps": [], "body_fetches": 0})
    snapshot = {"candidates": [{"id": "c1", "link": "https://example.invalid/a?utm_source=x"}],
                "history": {"News": [{"source_url": "https://example.invalid/a"}]}}
    ranked = {"News": [{"id": "c1", "history_status": "clear", "history_confidence": 1, "initial_risk": 0}]}
    assert runner.body_pool(tmp_path, snapshot, ranked) == {"News": []}
