"""Website-only release regressions: no real model, Storage or GitHub writes."""
import json
from pathlib import Path
import pytest
from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_batch import setup_batch
from pipeline.test_agent_shadow_review_fixes import run_steps
from pipeline.test_publication_bundle import full_bundle


def test_rejected_batch_never_resends_same_candidates(tmp_path, monkeypatch):
    _, _, _, answer = setup_batch(tmp_path, monkeypatch)
    seen = []
    def reject(root, key, system, material, validate, **kw):
        if key.startswith('discover-'):
            return {'articles': []}
        if key.startswith('rewrite-batch-Fun-'):
            ids = tuple(x['id'] for x in material['candidates'])
            assert ids not in seen, 'Rejected candidates submitted again'
            seen.append(ids)
            raise runner.AnswerRejected('invalid batch')
        return answer(root, key, system, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', reject)
    run_steps(tmp_path)
    assert seen
    assert all(runner.read(p)['considered'] for p in tmp_path.glob('batch-Fun-*.json') if runner.read(p).get('reason'))


def test_shell_copy_includes_every_index_reference(tmp_path, monkeypatch):
    from pipeline.publication_bundle import build, unpack
    _, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path / 'shell'
    shell.mkdir()
    (shell / 'index.html').write_text('<script src="data.jsx"></script>')
    (shell / 'data.jsx').write_text('window.TEST=1;')
    out = tmp_path / 'with-shell.zip'
    build(tmp_path, out, shell)
    assert 'data.jsx' in unpack(out.read_bytes())[0]


def test_reader_zip_has_no_internal_or_shadow_files(tmp_path, monkeypatch):
    from pipeline.website_release import build_reader, check_reader
    internal, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path / 'shell'
    shell.mkdir()
    (shell / 'index.html').write_text('<script src="data.jsx"></script>')
    (shell / 'data.jsx').write_text('window.TEST=1;')
    result = build_reader(internal.read_bytes(), shell, 'a' * 40)
    files = check_reader(result['zip'], result['manifest'])
    assert not {'publication-records.json', 'source-usage.json', 'app.js', 'shadow-run.json', 'vercel.json'} & files.keys()
    assert 'data.jsx' in files and result['manifest']['story_count'] == 9


def test_reader_rejects_missing_dependency_and_tampered_zip(tmp_path, monkeypatch):
    from pipeline.website_release import build_reader, check_reader
    internal, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path / 'shell'; shell.mkdir()
    (shell / 'index.html').write_text('<script src="data.jsx"></script>')
    with pytest.raises(ValueError, match='dependency'):
        build_reader(internal.read_bytes(), shell, 'a'*40)
    (shell / 'data.jsx').write_text('ok')
    result = build_reader(internal.read_bytes(), shell, 'a'*40)
    with pytest.raises(ValueError, match='hash'):
        check_reader(result['zip'] + b'x', result['manifest'])


def test_latest_backup_resume_and_rollback_are_exact(tmp_path, monkeypatch):
    from pipeline.website_release import build_reader, LatestRelease
    internal, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path / 'shell'; shell.mkdir()
    (shell / 'index.html').write_text('official')
    package = build_reader(internal.read_bytes(), shell, 'a'*40)
    objects = {'latest.zip': package['zip'], 'latest-manifest.json': json.dumps(package['manifest']).encode()}
    calls = []
    class Storage:
        def download(self, key): return objects[key]
        def upload(self, path, file, file_options):
            calls.append(path); objects[path] = file
    release = LatestRelease(tmp_path/'release', Storage())
    release.backup()
    release.publish(package['zip'], package['manifest'], acknowledge_slots=True)
    count = len(calls)
    release.publish(package['zip'], package['manifest'], acknowledge_slots=True)
    assert len(calls) == count
    release.rollback()
    assert objects['latest.zip'] == package['zip']
    assert set(calls) == {'latest.zip', 'latest-manifest.json'}


def test_uncertain_upload_reads_back_without_resend(tmp_path, monkeypatch):
    from pipeline.website_release import build_reader, LatestRelease
    internal, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path / 'shell'; shell.mkdir(); (shell/'index.html').write_text('official')
    package = build_reader(internal.read_bytes(), shell, 'a'*40)
    objects = {'latest.zip': package['zip'], 'latest-manifest.json': json.dumps(package['manifest']).encode()}
    calls = []
    class Storage:
        def download(self, key): return objects[key]
        def upload(self, path, file, file_options):
            calls.append(path); objects[path] = file
            if len(calls) == 1: raise TimeoutError('after sending')
    release = LatestRelease(tmp_path/'release', Storage()); release.backup()
    with pytest.raises(TimeoutError): release.publish(package['zip'], package['manifest'], acknowledge_slots=True)
    release.publish(package['zip'], package['manifest'], acknowledge_slots=True)
    assert calls.count('latest.zip') == 1


def test_rollback_refuses_corrupt_backup(tmp_path, monkeypatch):
    from pipeline.website_release import build_reader, LatestRelease
    internal, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path/'shell'; shell.mkdir(); (shell/'index.html').write_text('ok')
    package = build_reader(internal.read_bytes(), shell, 'a'*40)
    class Storage:
        def download(self, key): return package['zip'] if key.endswith('.zip') else json.dumps(package['manifest']).encode()
        def upload(self, **kw): pytest.fail('Must not upload corrupt backup')
    release = LatestRelease(tmp_path/'release', Storage()); release.backup()
    (tmp_path/'release'/'backup.zip').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash'): release.rollback()


def test_history_overlay_only_effective_prior_seven_days():
    from pipeline.website_release import overlay_history
    registry = {'date':'2026-10-01','history': [{'category':'Fun','published_date':'2026-09-30','source_title':'Old','source_url':'https://a'}]}
    ledger = {'2026-09-30':[{'category':'Fun','source_title':'New','source_url':'https://b'}],
              '2026-10-01':[{'category':'News','source_title':'Today','source_url':'https://c'}]}
    result = overlay_history(registry, ledger)
    assert [r['source_title'] for r in result['history']] == ['New']


def test_publish_refuses_changed_latest_after_backup(tmp_path, monkeypatch):
    from pipeline.website_release import build_reader, LatestRelease
    internal, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path/'shell'; shell.mkdir(); (shell/'index.html').write_text('ok')
    package = build_reader(internal.read_bytes(),shell,'a'*40)
    objects={'latest.zip':package['zip'],'latest-manifest.json':json.dumps(package['manifest']).encode()}
    class Storage:
        def download(self,key): return objects[key]
        def upload(self,**kw): pytest.fail('Competing writer must not be overwritten')
    release=LatestRelease(tmp_path/'release',Storage()); release.backup()
    objects['latest.zip']=b'another writer'
    with pytest.raises(ValueError,match='Competing'):
        release.publish(package['zip'],package['manifest'],acknowledge_slots=True)


def test_approval_binds_records_and_expires(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from pipeline.website_delivery import validate_receipt
    from pipeline.website_release import build_reader, sha
    internal,_=full_bundle(tmp_path,monkeypatch)
    shell=tmp_path/'shell'; shell.mkdir(); (shell/'index.html').write_text('ok')
    package=build_reader(internal.read_bytes(),shell,'a'*40)
    (tmp_path/'reader.zip').write_bytes(package['zip'])
    runner.write(tmp_path/'latest-manifest.json',package['manifest']); runner.write(tmp_path/'records.json',package['records'])
    receipt={'operation':'publish','target':'kidsnews.21mins.com','ack_same_day_slots':True,
        'zip_sha256':sha(package['zip']),'records_sha256':sha((tmp_path/'records.json').read_bytes()),
        'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    runner.write(tmp_path/'approval.json',receipt)
    validate_receipt(tmp_path)
    runner.write(tmp_path/'records.json',[])
    with pytest.raises(ValueError,match='records'): validate_receipt(tmp_path)


@pytest.mark.parametrize('text', ['English 中文 mixed', 'There were 2029 events.', 'He said "a sentence never in the source".'])
def test_evidence_gate_catches_known_bad_and_passes_good(text):
    from pipeline.website_release import evidence_gate
    original='In 2026, she said "we will try again tomorrow".'
    evidence_gate('In 2026, she said "we will try again tomorrow".',original)
    with pytest.raises(ValueError): evidence_gate(text,original)
