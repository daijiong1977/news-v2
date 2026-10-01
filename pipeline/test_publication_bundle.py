import io
import zipfile
from types import SimpleNamespace
from pathlib import Path
import pytest
from PIL import Image
from pipeline import publication_bundle as bundle
from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_batch import setup_batch
from pipeline.test_agent_shadow_review_fixes import run_steps


def full_bundle(tmp_path, monkeypatch):
    fetched, _, tasks, _ = setup_batch(tmp_path, monkeypatch)
    from pipeline import agent_shadow_batch
    def image(url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (320, 180), 'blue').save(path, format='WEBP')
        return True
    monkeypatch.setattr(agent_shadow_batch, 'safe_image', image)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    output = tmp_path / 'publication.zip'
    report = bundle.build(tmp_path, output)
    return output, report


def test_full_round_pack_upload_verify_same_zip_and_repeat(tmp_path, monkeypatch):
    output, report = full_bundle(tmp_path, monkeypatch)
    data = output.read_bytes()
    files, manifest = bundle.unpack(data)
    assert sum(manifest['counts'].values()) == 9
    assert len(runner.read(tmp_path / 'editor-state.json')['News']['accepted']) >= 3
    assert bundle.build(tmp_path, output)['zip_sha256'] == report['zip_sha256']
    staged = tmp_path / 'git-stage'
    bundle.stage(data, staged)
    assert (staged / 'payloads/articles_news_middle.json').read_bytes() == files['payloads/articles_news_middle.json']
    uploaded = []
    storage = SimpleNamespace(upload=lambda key, body, **kw: uploaded.append((key, body)))
    assert bundle.upload(data, storage) == f"pending/{manifest['package_id']}.zip"
    assert uploaded[0][1] == data
    def public(url, **kw):
        name = url.split('example.com/', 1)[1]
        return SimpleNamespace(status_code=200, content=files[name])
    proof = bundle.verify_site(data, 'https://example.com', public)
    assert proof['zip_sha256'] == report['zip_sha256']
    runner.write(tmp_path / 'offline-test-report.json', {'test_mode': 'offline_fakes_not_live_models',
        'counts': manifest['counts'], 'zip_sha256': report['zip_sha256'], 'body_fetches': 24,
        'normal_batch_calls': 3, 'site_verified': 'fake_HTTP_only'})


def test_bad_public_site_never_has_ready_proof(tmp_path, monkeypatch):
    path, _ = full_bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='Public site mismatch'):
        bundle.verify_site(path.read_bytes(), 'https://example.com', lambda *a, **kw: SimpleNamespace(status_code=200, content=b'old'))


def test_corrupted_manifest_hash_refused(tmp_path, monkeypatch):
    path, _ = full_bundle(tmp_path, monkeypatch)
    data = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files = {n: z.read(n) for n in z.namelist()}
    files['source-usage.json'] = b'[]'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        for n, content in files.items():
            z.writestr(n, content)
    with pytest.raises(ValueError, match='hash mismatch'):
        bundle.unpack(stream.getvalue())


@pytest.mark.parametrize('name', ['../evil', '/evil', 'x/../../evil', 'x\\evil', 'C:evil'])
def test_traversal_refused_before_extract(name):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr(name, b'bad')
    with pytest.raises(ValueError, match='Unsafe ZIP'):
        bundle.unpack(stream.getvalue())


def test_stage_refuses_existing_directory(tmp_path, monkeypatch):
    path, _ = full_bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='NEW directory'):
        bundle.stage(path.read_bytes(), tmp_path)


def test_only_published_sources_in_usage(tmp_path, monkeypatch):
    path, _ = full_bundle(tmp_path, monkeypatch)
    files, _ = bundle.unpack(path.read_bytes())
    import json
    rows = json.loads(files['publication-records.json'])
    usage = json.loads(files['source-usage.json'])
    assert {r['source_config_id'] for r in rows} == {u['source_id'] for u in usage}
    assert len(usage) < len(runner.read(tmp_path / 'input.json')['candidates'])


def test_registry_reads_current_sources_and_only_previous_seven_days():
    from pipeline.registry_snapshot import snapshot
    calls = []
    class Query:
        def __init__(self, table): self.table = table
        def __getattr__(self, name):
            def fn(*args):
                calls.append((self.table, name, args))
                if name == 'execute':
                    return SimpleNamespace(data=[{'id': 1}])
                return self
            return fn
    result = snapshot(SimpleNamespace(table=lambda name: Query(name)), '2026-10-01')
    assert result['sources'] and result['history']
    assert ('redesign_stories', 'gte', ('published_date', '2026-09-24')) in calls
    assert ('redesign_stories', 'lt', ('published_date', '2026-10-01')) in calls
    assert not any(method in ('insert', 'update', 'upsert', 'delete') for _, method, _ in calls)
