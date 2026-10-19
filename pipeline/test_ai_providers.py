import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from pipeline.ai_providers import AgentFilesProvider, AgentNeeded, OpenAICompatibleProvider


PAYLOAD = {"model": "editor", "messages": [{"role": "user", "content": "Rank IDs 1, 2"}]}


def pending(provider, payload=PAYLOAD):
    with pytest.raises(AgentNeeded) as exc:
        provider.complete(payload, 30)
    return exc.value


def test_http_preserves_payload_timeout_and_credentials(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            calls.append("checked")

        def json(self):
            return {"choices": [], "usage": {"total_tokens": 3}}

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr("pipeline.ai_providers.transport.requests.post", post)
    result = OpenAICompatibleProvider(endpoint="https://example.invalid/chat", api_key="test-key").complete(PAYLOAD, 42)
    assert calls == [(("https://example.invalid/chat",), {"json": PAYLOAD,
                     "headers": {"Authorization": "Bearer test-key"}, "timeout": 42}), "checked"]
    assert result["usage"]["total_tokens"] == 3


def test_handoff_cache_and_prompt_change(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.ai_providers.transport.requests.post", lambda *a, **k: pytest.fail("no HTTP"))
    provider = AgentFilesProvider(tmp_path)
    need = pending(provider)
    assert need.as_dict()["write_to"] == str(need.answer)
    assert json.loads(need.request.read_text())["task"] == PAYLOAD
    need.answer.write_text(json.dumps({"request_id": need.request_id, "content": "[2,1]", "finish_reason": "stop"}))
    assert provider.complete(PAYLOAD, 30)["choices"][0]["message"]["content"] == "[2,1]"
    changed = pending(provider, {**PAYLOAD, "messages": [{"role": "user", "content": "Rank IDs 3, 4"}]})
    assert changed.request_id != need.request_id
    assert need.answer.exists()  # no deleting previous answers


@pytest.mark.parametrize("answer", [[], {"request_id": "stale", "content": "ok", "finish_reason": "stop"},
                                   {"content": "", "finish_reason": "stop"}, {"content": "ok", "finish_reason": "oops"}])
def test_invalid_answer_requests_correction(tmp_path, answer):
    provider = AgentFilesProvider(tmp_path)
    need = pending(provider)
    need.answer.write_text(json.dumps(answer))
    assert pending(provider).errors


def test_concurrent_handoffs_share_complete_request(tmp_path):
    provider = AgentFilesProvider(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        needs = list(pool.map(lambda _: pending(provider), range(16)))
    assert len({n.request_id for n in needs}) == 1
    assert json.loads(needs[0].request.read_text())["task"] == PAYLOAD


def test_core_keeps_json_repair_and_usage(monkeypatch):
    from pipeline import news_rss_core

    def complete(self, payload, timeout):
        assert self.endpoint == "https://example.invalid/chat"
        assert self.api_key == "test-key"
        return {"choices": [{"message": {"content": '{"picks": [2,1,],}'},
                             "finish_reason": "stop"}], "usage": {"total_tokens": 3}}

    monkeypatch.setattr(OpenAICompatibleProvider, "complete", complete)
    result = news_rss_core._deepseek_post(PAYLOAD, 42, api_key="test-key", endpoint="https://example.invalid/chat")
    assert result.parsed == {"picks": [2, 1]}
    assert result.repair_kind == "trailing-commas"
    assert result.usage == {"total_tokens": 3}
