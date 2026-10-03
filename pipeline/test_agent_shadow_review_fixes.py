"""2026-09-30 review regressions. All network/model/deploy operations are fakes."""
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import agent_shadow as runner
from pipeline import agent_shadow_details as details
from pipeline import agent_shadow_publish as publish
from pipeline.ai_providers import AgentNeeded
from pipeline.news_sources import NewsSource


def draft():
    return {"source_id": 0, "safety": {"writer": "not a reviewer"},
            "easy_en": {"headline": "Easy", "body": "fact " * 170, "card_summary": "Card"},
            "middle_en": {"headline": "Middle", "body": "fact " * 330, "card_summary": "Card"},
            "zh": {"headline": "标题", "summary": "摘要"}}


def extra():
    return {f"0_{level}": {"keywords": [{"term": "fact", "explanation": "Known information."}],
        "questions": [{"question": f"Question {i}", "options": ["fact", "a", "b", "c"],
                       "correct_answer": "fact"} for i in range(6)],
        "background_read": [], "Article_Structure": ["WHAT: facts"], "why_it_matters": "We learn.",
        "perspectives": []} for level in ("easy", "middle")}


def fixture_round(root, monkeypatch, n=24):
    from pipeline import news_rss_core
    candidates, sources, catalog = [], {}, {}
    for ci, cat in enumerate(runner.CATS):
        catalog[cat] = []
        for i in range(n):
            name = ("BBC", "PBS", "CBC")[i % 3] if cat != "Science" else ("ScienceDaily" if i < 12 else "NASA")
            s = NewsSource(ci * 100 + i, name, f"https://{name.lower()}.example.invalid/feed", "full", 10, 350, 1, True, False)
            sources[name] = asdict(s)
            sid = f"{cat.lower()}{i:02d}"
            candidates.append({"id": sid, "category": cat, "source": name, "title": f"Title {sid}",
                               "link": f"https://example.invalid/{sid}", "summary": "facts", "published": ""})
            catalog[cat].append({"id": sid, "topic": f"topic{i % 6}", "importance": 4 if i == 0 else 1,
                                "history_status": "clear", "history_confidence": 1, "initial_risk": 0})
    runner.write(root / "input.json", {"date": "2026-09-30", "candidates": candidates,
        "sources": sources, "history": {c: [] for c in runner.CATS}})
    runner.write(root / "metrics.json", {"steps": [], "body_fetches": 0})
    fetched, picks = Counter(), []
    def original(b, **kw):
        fetched[b["id"]] += 1
        return {**b, "body": "fact " * 400, "word_count": 400, "skip_reason": None,
                "og_image": "https://example.invalid/image.webp"}
    monkeypatch.setattr(news_rss_core, "process_entry", original)
    monkeypatch.setattr("requests.post", lambda *a, **kw: pytest.fail("real model/database HTTP forbidden"))
    def image(url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFFfakeWEBP" + b"x" * 20_000)
        return {"local_path": str(path)}
    monkeypatch.setattr("pipeline.image_optimize.fetch_and_optimize", image)
    def answer(root, key, system, material, validate, **kw):
        if key == "rank":
            v = {"catalog": catalog}
        elif key.startswith("pick"):
            picks.append((key, hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()))
            v = {"order": [b["id"] for b in material]}
        elif key.startswith("rewrite"):
            v = {"articles": [draft()]}
        elif key.startswith("details"):
            v = {"details": extra()}
        elif key.startswith("review-details"):
            v = {"slots": {slot: {"fields": {field: True for field in obj if field != "questions"},
                 "questions": [True] * len(obj["questions"])} for slot, obj in material["details"].items()}}
        else:
            assert "safety" not in material["article"]
            v = {"scores": {"0": {d: 0 for d in news_rss_core.SAFETY_DIMS}}, "facts_supported": True}
        if kw.get("normalize"):
            v = kw["normalize"](v)
        assert not validate(v), (key, validate(v))
        return v
    monkeypatch.setattr(runner, "ask", answer)
    return fetched, picks, answer


def run_steps(root):
    for _ in range(200):
        try:
            return runner.advance(root, stepwise=True)
        except runner.StepFinished:
            continue
    pytest.fail("run failed to terminate")


def test_h1_science_refill_does_not_touch_news_and_preserves_accepted(tmp_path, monkeypatch):
    fetched, picks, _ = fixture_round(tmp_path, monkeypatch)
    monkeypatch.setattr(details, "enrich_and_review", lambda *a, **kw: {c: {} for c in runner.CATS})
    result = run_steps(tmp_path)
    assert result["counts"] == {"news": 3, "science": 3, "fun": 3}
    assert set(k for k in fetched if k.startswith("news")) == {f"news{i:02d}" for i in range(12)}
    assert all(n == 1 for n in fetched.values())
    assert len({h for k, h in picks if k.startswith("pick-News")}) == 1
    assert {k for k, _ in picks if k.startswith("pick-News")} == {"pick-News"}
    targets = runner.read(tmp_path / "backfill.json")["targets"]
    assert targets["News"] == targets["Fun"] == 6 and targets["Science"] > 6
    listing = runner.read(tmp_path / "site/payloads/articles_science_easy.json")["articles"]
    assert {x["source"] for x in listing} == {"ScienceDaily", "NASA"}
    approved = runner.read(tmp_path / "editor-state.json")["Science"]["accepted"]
    assert approved[0]["candidate"]["id"] == "science00"
    assert len(approved) >= 4
    report = runner.read(tmp_path / "review-results.json")
    assert any(x["id"] == "news00" and x["status"] == "accepted" for x in report["outcomes"])
    assert not any("no qualified high-importance" in w for w in result["warnings"])
    assert (tmp_path / "site/article_images/news-news00.webp").is_file()


def test_h2_rewrite_invalid_uses_reserve_and_reports(tmp_path, monkeypatch):
    _, _, answer = fixture_round(tmp_path, monkeypatch)
    def fail(root, key, *a, **kw):
        if key == "rewrite-News-news00":
            raise runner.AnswerRejected("one correction already attempted; bad words")
        return answer(root, key, *a, **kw)
    monkeypatch.setattr(runner, "ask", fail)
    result = run_steps(tmp_path)
    assert result["counts"]["news"] == 3
    assert any(x["id"] == "news00" and x["status"] == "rewrite_invalid"
               for x in runner.read(tmp_path / "review-results.json")["outcomes"])


def test_h2_details_bad_keywords_are_filtered_and_invalid_extras_omitted(tmp_path, monkeypatch):
    _, _, answer = fixture_round(tmp_path, monkeypatch)
    def fail(root, key, *a, **kw):
        if key == "details-News-news00":
            raise runner.AnswerRejected("one correction already attempted; malformed question")
        return answer(root, key, *a, **kw)
    monkeypatch.setattr(runner, "ask", fail)
    result = run_steps(tmp_path)
    assert result["counts"]["news"] == 3
    assert any("Enrichment omitted" in w for w in result["warnings"])
    page = runner.read(tmp_path / "site/article_payloads/payload_2026-09-30-news-1/easy.json")
    assert page["summary"] and page["questions"] == []


def test_h2_keyword_normalization_drops_only_misaligned_terms(tmp_path, monkeypatch):
    runner.write(tmp_path / "metrics.json", {"steps": []})
    v = {"details": extra()}
    v["details"]["0_easy"]["keywords"].append({"term": "elephant", "explanation": "An animal"})
    normalize = lambda obj: details.normalize_keywords(obj, draft())
    with pytest.raises(AgentNeeded) as pending:
        runner.ask(tmp_path, "details-News-c1", "Details", {}, lambda obj: details.validate_details(obj, {0: draft()}), normalize=normalize)
    runner.write(pending.value.answer, {"request_id": pending.value.request_id, "content": json.dumps(v), "finish_reason": "stop"})
    answer = runner.ask(tmp_path, "details-News-c1", "Details", {}, lambda obj: details.validate_details(obj, {0: draft()}), normalize=normalize)
    assert [kw["term"] for kw in answer["details"]["0_easy"]["keywords"]] == ["fact"]


def test_h3_write_is_atomic_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    runner.write(path, {"old": True})
    def interrupted(*a):
        raise OSError("simulated crash before replace")
    monkeypatch.setattr("os.replace", interrupted)
    with pytest.raises(OSError):
        runner.write(path, {"new": "large" * 1000})
    assert runner.read(path) == {"old": True}
    assert len(list(tmp_path.iterdir())) == 1


def test_h3_second_cli_step_exits_one_with_json(tmp_path):
    import fcntl
    with (tmp_path / ".run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = cli(tmp_path, "step")
    assert r.returncode == 1
    assert "another command" in json.loads(r.stdout)["error"]


@pytest.mark.parametrize("history", [None, []])
def test_m3_registry_missing_or_zero_history_rejected(tmp_path, monkeypatch, history):
    from pipeline import db_config, full_round
    monkeypatch.setattr(db_config, "load_sources", lambda *a, **kw: [])
    monkeypatch.setattr(full_round, "phase_a_light", lambda *a, **kw: [])
    reg = {"date": "2026-09-30", "sources": []}
    if history is not None:
        reg["history"] = history
    runner.write(tmp_path / "registry.json", reg)
    with pytest.raises(ValueError, match="connector|history"):
        runner.prepare(tmp_path / "run", "2026-09-30", registry_file=tmp_path / "registry.json")
    assert not (tmp_path / "run/input.json").exists()


def ready_publish(root):
    runner.write(root / "done.json", {})
    runner.write(root / "site/shadow-run.json", {"date": "2026-09-30", "content_hash": "abc", "counts": {"news": 1}})


def test_m4_timeout_marks_attempt_before_call_and_blocks_blind_retry(tmp_path, monkeypatch):
    ready_publish(tmp_path)
    calls = []
    def timeout(*a, **kw):
        calls.append(1)
        assert (tmp_path / "deployment-attempt.json").exists()
        raise subprocess.TimeoutExpired("fake", 180)
    monkeypatch.setattr("subprocess.run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        publish.publish(tmp_path)
    assert publish.publish(tmp_path)["next"] == "verify"
    assert len(calls) == 1
    with pytest.raises(ValueError, match="failed verify"):
        publish.publish(tmp_path, retry_after_failed_verify=True)
    monkeypatch.setattr("requests.get", lambda *a, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"content_hash": "old"}))
    with pytest.raises(ValueError):
        publish.verify(tmp_path)
    with pytest.raises(subprocess.TimeoutExpired):
        publish.publish(tmp_path, retry_after_failed_verify=True)
    assert len(calls) == 2
    assert publish.publish(tmp_path)["next"] == "verify"


def test_m4_zero_articles_cannot_publish(tmp_path, monkeypatch):
    ready_publish(tmp_path)
    manifest = runner.read(tmp_path / "site/shadow-run.json")
    manifest["counts"] = {c.lower(): 0 for c in runner.CATS}
    runner.write(tmp_path / "site/shadow-run.json", manifest)
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: pytest.fail("empty site must not deploy"))
    with pytest.raises(ValueError, match="zero"):
        publish.publish(tmp_path)


def cli(root, command):
    return subprocess.run([sys.executable, "-m", "pipeline.agent_shadow", command, "--run-dir", str(root)],
                          capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def test_m5_real_handoff_cli_and_changed_completed_answer_rejected(tmp_path):
    runner.write(tmp_path / "input.json", {"date": "2026-09-30", "candidates": [], "history": {c: [] for c in runner.CATS}})
    runner.write(tmp_path / "metrics.json", {"steps": [], "body_fetches": 0})
    first = cli(tmp_path, "step")
    assert first.returncode == 2 and len(first.stdout.splitlines()) == 1
    task = json.loads(first.stdout)
    path = Path(task["write_to"])
    runner.write(path, {"request_id": task["request_id"], "content": json.dumps({"catalog": {c: [] for c in runner.CATS}}), "finish_reason": "stop"})
    second = cli(tmp_path, "step")
    assert second.returncode == 0 and json.loads(second.stdout)["completed_step"] == "rank"
    assert len(second.stdout.splitlines()) == 1
    path.write_text(path.read_text() + " ")
    changed = cli(tmp_path, "step")
    assert changed.returncode == 1 and "changed" in json.loads(changed.stdout)["error"]


def test_small_timezone_error_is_json_exit_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["agent_shadow", "status", "--run-dir", str(tmp_path)])
    monkeypatch.setattr(runner, "ZoneInfo", lambda *a: (_ for _ in ()).throw(RuntimeError("tz missing")))
    assert runner.main() == 1
    assert json.loads(capsys.readouterr().out)["error"] == "tz missing"


def test_small_locked_requirements_and_vm_runbook():
    root = Path(__file__).resolve().parent.parent
    assert (root / "requirements.txt").read_bytes() == (root / "pipeline/requirements.txt").read_bytes()
    assert "tzdata==" in (root / "requirements.txt").read_text()
    assert "3. Run `.venv/bin/python" in (root / "agent/skills/kidsnews-shadow/SKILL.md").read_text()


def test_small_matching_locks_preserve_production_pdf_dependency():
    root = Path(__file__).resolve().parents[1]
    assert any(line.startswith("fpdf2==") for line in (root / "pipeline/requirements.txt").read_text().splitlines())


def test_m1_empty_source_only_extras_and_field_quiz_review():
    v = {"details": extra()}
    assert not details.validate_details(v, {0: draft()})
    review = {"slots": {slot: {"fields": {k: k != "why_it_matters" for k in obj if k != "questions"},
               "questions": [True, False, True, True, True, True]} for slot, obj in v["details"].items()}}
    assert not details.validate_detail_review(review, v["details"])
    filtered = details.apply_detail_review(v["details"], review)
    assert len(filtered["0_easy"]["questions"]) == 5
    assert "why_it_matters" not in filtered["0_easy"]
    assert "Article_Structure" in filtered["0_easy"]


def test_m2_review_session_policy_in_both_runbooks():
    root = Path(__file__).resolve().parent.parent / "agent/skills/kidsnews-shadow"
    for path in (root / "SKILL.md", root / "instructions.md"):
        text = path.read_text()
        assert "new session" in text and "tasks/rewrite-*/answer.json" in text
        assert "同模型第二遍审核" in text


def test_m3_cached_empty_history_cannot_bypass_prepare(tmp_path):
    runner.write(tmp_path / "input.json", {"date": "2026-09-30", "history": {c: [] for c in runner.CATS}})
    with pytest.raises(ValueError, match="connector"):
        runner.prepare(tmp_path, "2026-09-30")


def test_full_round_review_rejection_keeps_reserve_and_verifies_images(tmp_path, monkeypatch):
    _, _, answer = fixture_round(tmp_path, monkeypatch)
    def reject(root, key, *a, **kw):
        if key == "review-News-news01":
            from pipeline.news_rss_core import SAFETY_DIMS
            scores = {d: 0 for d in SAFETY_DIMS}
            scores[SAFETY_DIMS[0]] = 5
            return {"scores": {"0": scores}, "facts_supported": True}
        return answer(root, key, *a, **kw)
    monkeypatch.setattr(runner, "ask", reject)
    result = run_steps(tmp_path)
    assert result["counts"]["news"] == 3
    outcomes = runner.read(tmp_path / "review-results.json")["outcomes"]
    assert any(o["id"] == "news01" and o["status"] == "review_rejected" for o in outcomes)
    def get(url, **kw):
        local = tmp_path / "site" / url.removeprefix(publish.URL + "/")
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: runner.read(local), content=local.read_bytes())
    monkeypatch.setattr("requests.get", get)
    verified = publish.verify(tmp_path)
    assert verified["verified_files"] == 9 + 18 + 9
    assert not verified["production_published"]


def test_h2_real_bad_wordcount_twice_becomes_rewrite_invalid(tmp_path, monkeypatch):
    real_ask = runner.ask
    _, _, answer = fixture_round(tmp_path, monkeypatch)
    def proxy(root, key, *a, **kw):
        if key == "rewrite-News-news00":
            return real_ask(root, key, *a, **kw)
        return answer(root, key, *a, **kw)
    monkeypatch.setattr(runner, "ask", proxy)
    bad = draft()
    bad["easy_en"]["body"] = "too short"
    handoffs = 0
    for _ in range(200):
        try:
            result = runner.advance(tmp_path, stepwise=True)
            break
        except runner.StepFinished:
            pass
        except AgentNeeded as need:
            handoffs += 1
            runner.write(need.answer, {"request_id": need.request_id,
                "content": json.dumps({"articles": [bad]}), "finish_reason": "stop"})
    else:
        pytest.fail("rewrite invalid blocked the full round")
    assert handoffs == 2
    assert result["counts"]["news"] == 3
    assert any(o["status"] == "rewrite_invalid" for o in runner.read(tmp_path / "review-results.json")["outcomes"])


@pytest.mark.parametrize("stage", ["rank", "pick-News"])
def test_h2_essential_rank_and_pick_remain_fatal(tmp_path, monkeypatch, stage):
    _, _, answer = fixture_round(tmp_path, monkeypatch)
    def fail(root, key, *a, **kw):
        if key == stage:
            raise runner.AnswerRejected("essential answer correction exhausted")
        return answer(root, key, *a, **kw)
    monkeypatch.setattr(runner, "ask", fail)
    with pytest.raises(runner.AnswerRejected):
        runner.advance(tmp_path)


def test_m4_inconclusive_verify_does_not_allow_retry(tmp_path, monkeypatch):
    import requests
    ready_publish(tmp_path)
    runner.write(tmp_path / "deployment-attempt.json", {"attempt": 1, "content_hash": "abc"})
    monkeypatch.setattr("requests.get", lambda *a, **kw: (_ for _ in ()).throw(requests.Timeout("offline fake")))
    with pytest.raises(requests.Timeout):
        publish.verify(tmp_path)
    assert not (tmp_path / "verify-failure.json").exists()
    with pytest.raises(ValueError, match="failed verify"):
        publish.publish(tmp_path, retry_after_failed_verify=True)


def test_body_probe_first_twelve_then_six_with_rejected_originals(tmp_path, monkeypatch):
    from pipeline import news_rss_core
    fetched, _, _ = fixture_round(tmp_path, monkeypatch)
    index = {b["id"]: b for b in runner.read(tmp_path / "input.json")["candidates"]}
    # First twelve yield only five, next batch of six supplies the sixth.
    def original(b, **kw):
        fetched[b["id"]] += 1
        i = int(b["id"][-2:])
        return {**b, "body": "fact " * 400, "word_count": 400,
                "skip_reason": "blocked page" if 5 <= i < 12 else None}
    monkeypatch.setattr(news_rss_core, "process_entry", original)
    scores = [{"id": f"news{i:02d}", "topic": f"t{i}", "importance": 1,
        "history_status": "clear", "history_confidence": 1, "initial_risk": 0} for i in range(24)]
    pool = runner.body_pool(tmp_path, runner.read(tmp_path / "input.json"), {"News": scores})
    assert len(fetched) == 18 and len(pool["News"]) == 11
