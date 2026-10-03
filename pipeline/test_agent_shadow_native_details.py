"""Grok detail POC follow-up: offline, no real provider or production writes."""
from copy import deepcopy
import sys
import pytest

from pipeline import agent_shadow as runner
from pipeline import agent_shadow_details as details
from pipeline.test_agent_shadow_review_fixes import draft, extra, run_steps
from pipeline.test_agent_shadow_batch import setup_batch


def test_native_details_no_second_audit_and_resume_preserves_article(tmp_path):
    runner.write(tmp_path / 'input.json', {'test_profile': 'batch-grok-details'})
    entry = draft()
    before = deepcopy(entry)
    final = {'News': [{'winner': {'id': 'c1', 'body': 'fact source'}}]}
    calls, prompts = [], []
    def ask(root, key, system, material, validate, **kw):
        calls.append(key); prompts.append(system)
        value = {'details': extra()}
        assert not validate(value)
        return value
    result = details.enrich_and_review(tmp_path, final, {'News': {0: entry}}, ask,
                                      lambda *a: None, False)
    assert calls == ['details-News-c1']
    assert entry == before
    report = runner.read(tmp_path / 'detail-reviews.json')['News-c1']
    assert report['review_method'] == 'Grok原生生成并自检；Python结构校验；无独立详情审核'
    assert 'longest' in prompts[0] and 'titles' in prompts[0]
    expected = deepcopy(extra())
    from pipeline.quiz_shuffle import shuffle_quiz_options
    shuffle_quiz_options(expected, seed='News-c1')
    assert result['News']['0_easy'] == expected['0_easy']
    details.enrich_and_review(tmp_path, final, {'News': {0: entry}}, ask, lambda *a: None, False)
    assert calls == ['details-News-c1']


def test_native_profile_uses_native_details_but_http_writer(tmp_path, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline-test-only')
    monkeypatch.setattr(runner, 'prepare', lambda *a, **k: {'ok': True})
    monkeypatch.setattr(sys, 'argv', ['agent_shadow', 'prepare', '--run-dir', str(tmp_path),
                                    '--editor-mode', 'autonomous', '--test-profile', 'batch-grok-details'])
    assert runner.main() == 0
    from pipeline.agent_shadow_providers import TaskRouter
    assert TaskRouter(tmp_path, 'details-News-c1').choice['type'] == 'native'
    assert TaskRouter(tmp_path, 'rewrite-batch-News-8').choice['type'] == 'http'


def test_native_details_cannot_return_body_or_title():
    value = {'details': extra(), 'title': 'Injected title'}
    assert details.validate_native_details(value, {0: draft()})
    value.pop('title')
    value['details']['0_easy']['summary'] = 'Injected body'
    assert details.validate_native_details(value, {0: draft()})


def test_longest_answer_is_warning_not_hard_rejection():
    obj = extra()
    for row in obj.values():
        for q in row['questions']:
            q['options'] = ['This correct choice is conspicuously the longest', 'a', 'b', 'c']
            q['correct_answer'] = q['options'][0]
    assert not details.validate_native_details({'details': obj}, {0: draft()})
    notes = details.quiz_quality_warnings(obj)
    assert len(notes) == 2 and all('6/6' in note for note in notes)


def test_new_profile_full_nine_and_zip_without_review_details(tmp_path, monkeypatch):
    _, _, tasks, answer = setup_batch(tmp_path, monkeypatch)
    from PIL import Image
    def photo(url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (640, 360), 'blue').save(path, 'WEBP')
        return True
    monkeypatch.setattr('pipeline.agent_shadow_batch.safe_image', photo)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot['test_profile'] = 'batch-grok-details'
    runner.write(tmp_path / 'input.json', snapshot)
    calls = []
    def record(root, key, *a, **kw):
        calls.append(key)
        return answer(root, key, *a, **kw)
    monkeypatch.setattr(runner, 'ask', record)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    assert len({k for k in calls if k.startswith('rewrite-batch-')}) == 3
    assert len({k for k in calls if k.startswith('details-')}) == 9
    assert not any(k.startswith('review-details-') for k in calls)
    from pipeline.publication_bundle import build, unpack
    build(tmp_path, tmp_path / 'publication.zip')
    assert unpack((tmp_path / 'publication.zip').read_bytes())[1]['counts']['news'] == 3


def test_two_news_publishers_allowed_only_new_profile(tmp_path, monkeypatch):
    _, _, _, _ = setup_batch(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot['test_profile'] = 'batch-grok-details'
    for c in snapshot['candidates']:
        if c['category'] == 'News' and c['source'] == 'PBS':
            c['source'] = 'BBC'
    runner.write(tmp_path / 'input.json', snapshot)
    result = run_steps(tmp_path)
    assert not any('News has fewer than 3' in w for w in result['warnings'])


def test_existing_batch_keeps_news_three_publisher_warning(tmp_path, monkeypatch):
    setup_batch(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    for c in snapshot['candidates']:
        if c['category'] == 'News' and c['source'] == 'PBS':
            c['source'] = 'BBC'
    runner.write(tmp_path / 'input.json', snapshot)
    result = run_steps(tmp_path)
    assert any('News has fewer than 3' in w for w in result['warnings'])


def test_native_details_resumes_saved_generation_without_any_model(tmp_path):
    runner.write(tmp_path / 'input.json', {'test_profile': 'batch-grok-details'})
    runner.write(tmp_path / 'enrichment-state.json',
                 {'News-c1': {'generated': extra(), 'reviewed': False}})
    def forbidden(*args, **kwargs):
        raise AssertionError('Saved generation must finish locally, not call a model')
    result = details.enrich_and_review(tmp_path,
        {'News': [{'winner': {'id': 'c1', 'body': 'source'}}]}, {'News': {0: draft()}},
        forbidden, lambda *args: None, False)
    assert result['News']['0_easy']['questions']
    assert runner.read(tmp_path / 'enrichment-state.json')['News-c1']['reviewed']
