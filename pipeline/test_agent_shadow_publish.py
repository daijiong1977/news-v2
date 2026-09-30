import json
from types import SimpleNamespace

import pytest

from pipeline import agent_shadow as runner
from pipeline import agent_shadow_publish as publish


def test_publish_refuses_incomplete_run(tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("must not deploy"))
    with pytest.raises(ValueError, match="finish all"):
        publish.publish(tmp_path)


def test_publish_is_pinned_to_shadow_project_and_submits_once(tmp_path, monkeypatch):
    runner.write(tmp_path / "done.json", {})
    runner.write(tmp_path / "site/shadow-run.json", {"content_hash": "abc"})
    calls = []
    def deploy(args, **kw):
        calls.append(args)
        assert kw["cwd"] == tmp_path / "site"
        assert kw["env"]["VERCEL_PROJECT_ID"] == publish.PROJECT
        assert kw["env"]["VERCEL_ORG_ID"] == publish.ORG
        return SimpleNamespace(returncode=0, stdout="https://example.vercel.app\n")
    monkeypatch.setattr("subprocess.run", deploy)
    assert publish.publish(tmp_path)["next"] == "verify"
    assert publish.publish(tmp_path)["next"] == "verify"
    assert len(calls) == 1


def test_verify_rejects_stale_remote_manifest(tmp_path, monkeypatch):
    runner.write(tmp_path / "site/shadow-run.json", {"content_hash": "abc", "date": "2026-09-30", "counts": {}})
    remote = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"content_hash": "old"})
    monkeypatch.setattr("requests.get", lambda *a, **k: remote)
    with pytest.raises(ValueError, match="not this run"):
        publish.verify(tmp_path)
    assert not (tmp_path / "published.json").exists()


def test_verify_recomputes_served_hash_not_only_manifest(tmp_path, monkeypatch):
    import hashlib
    names = [f"payloads/articles_{c}_{l}.json" for c in publish_verify_categories() for l in ("easy", "middle", "cn")]
    raw = json.dumps({"articles": []}).encode()
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(name.encode() + b"\0" + raw + b"\0")
        path = tmp_path / "site" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    manifest = {"content_hash": digest.hexdigest(), "date": "2026-09-30", "counts": {"news": 0, "science": 0, "fun": 0}}
    runner.write(tmp_path / "site/shadow-run.json", manifest)
    def get(url, **kw):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: manifest, content=raw)
    monkeypatch.setattr("requests.get", get)
    assert publish.verify(tmp_path)["verified_files"] == 9
    monkeypatch.setattr("requests.get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: manifest, content=b"different"))
    with pytest.raises(ValueError, match="hash mismatch"):
        publish.verify(tmp_path)


def publish_verify_categories():
    return ("news", "science", "fun")
