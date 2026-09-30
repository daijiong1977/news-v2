"""Only adapters know how a model/agent receives a task.

Editorial prompts, thresholds, retries and publication remain with the callers.
Python 3.10 compatible for the Bot VM. No Grok API key is needed for file handoff.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

import requests


class CompletionProvider(Protocol):
    def complete(self, payload: dict, timeout: int) -> dict:
        """Return a chat-completion envelope; callers parse and validate content."""
        ...


class OpenAICompatibleProvider:
    """DeepSeek today; another compatible endpoint can use the same adapter."""

    def __init__(self, *, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key

    def complete(self, payload: dict, timeout: int) -> dict:
        response = requests.post(
            self.endpoint, json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"}, timeout=timeout,
        )
        response.raise_for_status()
        return response.json()


class AgentNeeded(Exception):
    """Control signal for an agent-aware CLI, not a transport retry."""

    def __init__(self, request_id: str, request: Path, answer: Path, errors: list[str]):
        super().__init__("agent answer required")
        self.request_id, self.request, self.answer, self.errors = request_id, request, answer, errors

    def as_dict(self) -> dict:
        return {"ok": False, "request_id": self.request_id, "next": "answer request and rerun this stage",
                "read": str(self.request), "write_to": str(self.answer), "errors": self.errors}


def _atomic_json(path: Path, value: dict) -> None:
    """Concurrent identical requests never expose a partly written file."""
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".request-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class AgentFilesProvider:
    """Grok Bot or any agent reads request.json and writes answer.json.

    The directory is scoped by the caller to a run/date and review stage. Identical
    requests within that scope reuse an answer; changed prompts get a new ID.
    No network calls, credentials or database access happen in this adapter.
    """

    def __init__(self, work_dir: Path):
        self.work_dir = Path(work_dir).resolve()

    def complete(self, payload: dict, timeout: int) -> dict:
        # timeout applies to HTTP transport; the agent CLI controls its own deadline.
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        request_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        directory = self.work_dir / request_id
        directory.mkdir(parents=True, exist_ok=True)
        request, answer = directory / "request.json", directory / "answer.json"
        _atomic_json(request, {
            "schema_version": 1, "request_id": request_id, "task": payload,
            "instructions": "Use only the supplied material. Follow task.messages and its output schema. "
                            "Do not change code or publish. Write the answer file then rerun the calling stage.",
            "write_to": str(answer),
            "answer_example": {"request_id": request_id, "content": "{\"example\": true}",
                               "finish_reason": "stop"},
        })
        if not answer.exists():
            raise AgentNeeded(request_id, request, answer, ["Read request.json and write answer.json."])
        try:
            data = json.loads(answer.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise AgentNeeded(request_id, request, answer, [f"Answer must be UTF-8 JSON: {exc}"]) from exc
        errors = []
        if not isinstance(data, dict):
            errors.append("Answer must be an object.")
        else:
            if data.get("request_id") != request_id:
                errors.append("Copy the current request_id exactly; an older answer cannot be reused.")
            if not isinstance(data.get("content"), str) or not data["content"].strip():
                errors.append("content must be a nonempty string containing the task's answer.")
            if data.get("finish_reason") not in ("stop", "length"):
                errors.append("finish_reason must be stop or length; use length for an incomplete answer.")
        if errors:
            raise AgentNeeded(request_id, request, answer, errors)
        # Native Bot usage is not available here; never fabricate API token counts.
        return {"choices": [{"message": {"content": data["content"]},
                              "finish_reason": data["finish_reason"]}], "usage": {}}
