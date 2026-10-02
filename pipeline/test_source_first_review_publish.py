"""Review regressions using the actual pinned reader and fake Storage only."""
import json
import re
from pathlib import Path

import pytest


def test_pinned_reader_preserves_omitted_status_in_fetch_mapper():
    from pipeline.source_first_reader import adapt_article_shell
    source = Path(__file__).parent.parent / 'reader-shell/article.jsx'
    adapted = adapt_article_shell(source.read_bytes()).decode()
    mapper = adapted.split('const mapped = {', 1)[1].split('setDetail(mapped)', 1)[0]
    assert re.search(r'detail_status\s*:\s*d\.detail_status', mapper)
    assert "detail.detail_status !== 'omitted' && tab === 'quiz'" in adapted


def test_resume_rejects_changed_manifest_before_any_write(tmp_path):
    from pipeline import website_release as wr
    from pipeline.agent_shadow import write
    original = {'version': '2026-10-02', 'zip_sha256': wr.sha(b'target')}
    write(tmp_path / 'release.json', {'mode': 'publish', 'target_sha': wr.sha(b'target'),
        'target_manifest_sha': wr.sha(wr.encoded(original))})
    class Storage:
        def download(self, key): pytest.fail('Changed approved manifest must fail before reads')
        def upload(self, **kwargs): pytest.fail('Changed approved manifest must never upload')
    with pytest.raises(ValueError, match='manifest'):
        wr.LatestRelease(tmp_path, Storage())._replace(b'target', {**original, 'version': '2026-10-03'}, 'publish')


def test_rollback_refuses_foreign_manifest_with_same_zip(tmp_path):
    from pipeline import website_release as wr
    data = wr.zip_files({'index.html': b'reader'})
    backup = {'zip_sha256': wr.sha(data), 'zip_bytes': len(data), 'version': '2026-10-01'}
    objects = {'latest.zip': data, 'latest-manifest.json': wr.encoded(backup)}
    class Storage:
        def download(self, key): return objects[key]
        def upload(self, **kwargs): pytest.fail('Foreign manifest must not be overwritten')
    release = wr.LatestRelease(tmp_path, Storage())
    release.backup()
    objects['latest-manifest.json'] = wr.encoded({**backup, 'version': '2026-10-03'})
    with pytest.raises(ValueError, match='Competing'):
        release.rollback()


def test_partial_rollback_resumes_original_pair_without_reupload(tmp_path):
    from pipeline import website_release as wr
    old_data = wr.zip_files({'index.html': b'old'})
    new_data = wr.zip_files({'index.html': b'new'})
    old = {'zip_sha256': wr.sha(old_data), 'zip_bytes': len(old_data), 'version': '2026-10-01'}
    new = {'zip_sha256': wr.sha(new_data), 'zip_bytes': len(new_data), 'version': '2026-10-02'}
    objects = {'latest.zip': old_data, 'latest-manifest.json': wr.encoded(old)}
    uploads = []
    class Storage:
        interrupt = False
        def download(self, key): return objects[key]
        def upload(self, path, file, file_options):
            uploads.append(path)
            objects[path] = file
            if self.interrupt and path == 'latest.zip':
                self.interrupt = False
                raise TimeoutError('Rollback upload executed before lost response')
    storage = Storage()
    release = wr.LatestRelease(tmp_path, storage)
    release.backup()
    release.publish(new_data, new, acknowledge_slots=True)
    storage.interrupt = True
    with pytest.raises(TimeoutError):
        release.rollback()
    release.rollback()
    assert objects == {'latest.zip': old_data, 'latest-manifest.json': wr.encoded(old)}
    assert uploads == ['latest.zip', 'latest-manifest.json', 'latest.zip', 'latest-manifest.json']


@pytest.mark.parametrize('numeric', [False, True])
def test_pack_checks_card_evidence_and_keeps_quote_warnings(tmp_path, monkeypatch, numeric):
    from pipeline.test_publication_bundle import full_bundle
    from pipeline import publication_bundle as bundle
    from pipeline.agent_shadow import read, write
    full_bundle(tmp_path, monkeypatch)
    path = tmp_path / 'site/payloads/articles_news_easy.json'
    listing = read(path)
    listing['articles'][0]['title'] = 'There are 987654321 people' if numeric else 'She said "a wholly unsupported quotation here"'
    write(path, listing)
    if numeric:
        with pytest.raises(ValueError, match='Numeric evidence'):
            bundle.build(tmp_path, tmp_path / 'review.zip')
    else:
        report = bundle.build(tmp_path, tmp_path / 'review.zip')
        assert any('easy.card_title: Unsupported quoted sentence' in w for w in report['evidence_warnings'])
