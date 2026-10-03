import json
import pytest
from pipeline.test_publication_database import fixture
from pipeline.test_kidsnews_python import Storage
from pipeline.publication_bundle import encoded, sha


def test_reader_pdfs_generated_hashed_and_archived(tmp_path, monkeypatch):
    from pipeline.publication_database import load_artifact
    from pipeline.publication_archive import targets
    artifact, result, _ = fixture(tmp_path, monkeypatch)
    files = load_artifact(artifact)[3]
    pdfs = {n: b for n, b in files.items() if n.startswith('article_pdfs/')}
    assert len(pdfs) == 18
    assert all(b.startswith(b'%PDF-') and b.endswith(b'%%EOF\n') for b in pdfs.values())
    assert all(result['manifest']['files'][n] == sha(b) for n, b in pdfs.items())
    _, objects = targets(artifact, Storage())
    assert all(result['manifest']['version']+'/'+n in objects for n in pdfs)


def cleanup_fixture(tmp_path, monkeypatch):
    from pipeline.publication_database import load_artifact
    from pipeline.publication_archive import apply_archive
    artifact, _, _ = fixture(tmp_path, monkeypatch)
    storage = Storage()
    apply_archive(artifact, tmp_path/'original', storage)
    day = load_artifact(artifact)[0]['date']
    storage.objects[day+'/article_images/unused.webp'] = b'old-photo'
    storage.objects[day+'/article_payloads/payload_old/easy.json'] = b'old-detail'
    storage.objects['2020-01-01/article_images/keep.webp'] = b'other-day'
    storage.list = lambda prefix: [n for n in storage.objects if n.startswith(prefix+'/')]
    return artifact, storage, day


def test_cleanup_backups_exact_objects_resume_and_restore(tmp_path, monkeypatch):
    from pipeline.publication_maintenance import prune_archive, restore_pruned
    artifact, storage, day = cleanup_fixture(tmp_path, monkeypatch)
    original = dict(storage.objects)
    state = tmp_path/'prune'
    plan = prune_archive(artifact, state, storage, execute=False)
    assert len(plan['objects']) == 2 and storage.objects == original
    prune_archive(artifact, state, storage, execute=True)
    assert len(storage.deletes) == 2 and storage.objects['2020-01-01/article_images/keep.webp'] == b'other-day'
    prune_archive(artifact, state, storage, execute=True)
    assert len(storage.deletes) == 2
    restore_pruned(state, storage)
    assert storage.objects == original
    with pytest.raises(ValueError, match='restored'):
        prune_archive(artifact, state, storage, execute=True)


def test_cleanup_competing_writer_and_corrupt_backup_block_delete(tmp_path, monkeypatch):
    from pipeline.publication_maintenance import prune_archive
    artifact, storage, day = cleanup_fixture(tmp_path, monkeypatch)
    state = tmp_path/'prune'
    plan = prune_archive(artifact, state, storage, execute=False)
    row = plan['objects'][0]
    storage.objects[row['name']] = b'new-writer'
    with pytest.raises(ValueError, match='Changed'):
        prune_archive(artifact, state, storage, execute=True)
    assert not storage.deletes
    storage.objects[row['name']] = (state/row['before_file']).read_bytes()
    (state/row['before_file']).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash'):
        prune_archive(artifact, state, storage, execute=True)
    assert not storage.deletes


def test_cleanup_edition_changed_blocks_all_deletes(tmp_path, monkeypatch):
    from pipeline.publication_maintenance import prune_archive
    artifact, storage, day = cleanup_fixture(tmp_path, monkeypatch)
    state = tmp_path/'prune'
    prune_archive(artifact, state, storage, execute=False)
    storage.objects[day+'-manifest.json'] = b'new-edition'
    with pytest.raises(ValueError, match='edition'):
        prune_archive(artifact, state, storage, execute=True)
    assert not storage.deletes


def test_interrupted_database_after_archive_can_rollback_exactly(tmp_path, monkeypatch):
    from copy import deepcopy
    from pipeline.test_publication_rest import Memory
    from pipeline.publication_database import load_artifact
    from pipeline.kidsnews_python import finish_publication, rollback_publication
    artifact, _, _ = fixture(tmp_path, monkeypatch)
    client = Memory(load_artifact(artifact)[0]); storage = Storage()
    before_db, before_storage = deepcopy(client.data), dict(storage.objects)
    state = tmp_path/'private-publication'
    monkeypatch.setattr('pipeline.kidsnews_python.verify_website', lambda a: None)
    client.lose = True
    with pytest.raises(Exception):
        finish_publication(artifact, state, client, storage)
    assert json.loads((state/'recovery-required.json').read_bytes())['action'] == 'resume_or_rollback'
    rollback_publication(state, client, storage)
    assert client.data == before_db and storage.objects == before_storage
    rollback_publication(state, client, storage)
    assert client.data == before_db and storage.objects == before_storage


def test_pdf_repair_preserves_every_existing_asset_and_records(tmp_path, monkeypatch):
    from pipeline.reader_pdfs import augment_artifact
    from pipeline.publication_database import load_artifact
    artifact, _, _ = fixture(tmp_path, monkeypatch)
    repair = tmp_path/'repair'
    augment_artifact(artifact, repair)
    original = load_artifact(artifact)[3]; fixed = load_artifact(repair)[3]
    assert all(fixed[n] == b for n, b in original.items())
    assert (repair/'records.json').read_bytes() == (artifact/'records.json').read_bytes()
