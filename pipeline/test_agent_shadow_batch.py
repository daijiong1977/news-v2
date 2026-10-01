"""Offline 8→5→3 end-to-end; never calls a real model or publication service."""
from copy import deepcopy
from collections import Counter
import pytest

from pipeline import agent_shadow as runner
from pipeline import agent_shadow_batch as batch
from pipeline.test_agent_shadow_review_fixes import fixture_round, run_steps, draft


def setup_batch(root, monkeypatch):
    fetched, _, previous = fixture_round(root, monkeypatch, n=16)
    snapshot = runner.read(root / 'input.json')
    snapshot.update(editor_mode='autonomous', test_profile='batch-deepseek', review_mode='modifier')
    # At least two independent science publishers are available in the first eight.
    for b in snapshot['candidates']:
        if b['category'] == 'Science' and int(b['id'][-2:]) % 2:
            b['source'] = 'NASA'
    runner.write(root / 'input.json', snapshot)
    from pipeline import agent_shadow_autonomous as autonomous
    def original(b):
        fetched[b['id']] += 1
        return {**b, 'body': 'fact ' * 400, 'word_count': 400,
                'skip_reason': None, 'og_image': 'https://example.invalid/image.webp'}
    monkeypatch.setattr(autonomous, 'fetch_original', original)
    photos = Counter()
    def image(url, path):
        photos['downloads'] += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'RIFFfakeWEBP')
        return True
    monkeypatch.setattr(batch, 'safe_image', image)
    monkeypatch.setattr(autonomous, 'safe_image', lambda *a: pytest.fail('final images downloaded twice'))
    tasks = []
    def answer(root, key, system, material, validate, **kw):
        tasks.append(key)
        if key == 'plan':
            from pipeline.news_topics import TOPICS_BY_CATEGORY
            value = {'catalog': {c: [{'id': f'{c.lower()}{i:02d}', 'topic': list(TOPICS_BY_CATEGORY[c])[i%6],
                'importance': 4 if i == 4 else 1, 'initial_risk': 0,
                'history_status': 'clear', 'history_confidence': 1} for i in range(16)] for c in runner.CATS}}
        elif key.startswith('rewrite-batch-'):
            value = {'drafts': [{'id': b['id'], 'reason': 'Important and varied', 'article': draft()}
                                for b in material['candidates'][:5]]}
        elif key.startswith('select-batch-'):
            value = {'order': [b['id'] for b in material['drafts']]}
        elif key.startswith('review-modify-'):
            from pipeline.news_rss_core import SAFETY_DIMS
            value = {'corrected_article': deepcopy(material['article']),
                     'scores': {'0': {d: 0 for d in SAFETY_DIMS}},
                     'facts_supported': True, 'event_clear': True, 'notes': 'Supported by source'}
        else:
            return previous(root, key, system, material, validate, **kw)
        assert not validate(value), (key, validate(value))
        return value
    monkeypatch.setattr(runner, 'ask', answer)
    return fetched, photos, tasks, answer


def test_full_batch_nine_and_resume_no_second_writes_or_photos(tmp_path, monkeypatch):
    fetched, photos, tasks, _ = setup_batch(tmp_path, monkeypatch)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    assert sum(fetched.values()) == 24 and all(n == 1 for n in fetched.values())
    assert photos['downloads'] == 24
    # Stepwise handoffs can revisit ask mocks; unique tasks correspond to three API requests.
    assert len({k for k in tasks if k.startswith('rewrite-batch-')}) == 3
    assert not any(k.startswith('rewrite-') and not k.startswith('rewrite-batch-') for k in tasks)
    accepted = runner.read(tmp_path / 'editor-state.json')
    assert accepted['News']['accepted'][0]['candidate']['importance'] == 4
    listing = runner.read(tmp_path / 'site/payloads/articles_science_easy.json')['articles']
    assert {x['source'] for x in listing} == {'ScienceDaily', 'NASA'}
    before = list(tasks)
    assert runner.advance(tmp_path)['already_done']
    assert tasks == before


def test_batch_rejected_winner_uses_other_two_without_rewriting_five(tmp_path, monkeypatch):
    _, _, tasks, answer = setup_batch(tmp_path, monkeypatch)
    def reject(root, key, system, material, validate, **kw):
        value = answer(root, key, system, material, validate, **kw)
        if key == 'review-modify-Fun-fun00':
            value['facts_supported'] = False
        return value
    monkeypatch.setattr(runner, 'ask', reject)
    result = run_steps(tmp_path)
    assert result['counts']['fun'] == 3
    assert len({k for k in tasks if k.startswith('rewrite-batch-Fun-')}) == 1
    assert any(o['id'] == 'fun00' and o['status'] == 'review_rejected'
               for o in runner.read(tmp_path / 'review-results.json')['outcomes'])


def test_fun_refill_does_not_touch_settled_news_or_science(tmp_path, monkeypatch):
    fetched, _, tasks, answer = setup_batch(tmp_path, monkeypatch)
    def reject(root, key, system, material, validate, **kw):
        value = answer(root, key, system, material, validate, **kw)
        if key.startswith('review-modify-Fun-') and int(key[-2:]) < 5:
            value['facts_supported'] = False
        return value
    monkeypatch.setattr(runner, 'ask', reject)
    result = run_steps(tmp_path)
    assert result['counts']['fun'] == 3
    assert sum(v for k, v in fetched.items() if k.startswith('news')) == 8
    assert sum(v for k, v in fetched.items() if k.startswith('science')) == 8
    assert len({k for k in tasks if k.startswith('rewrite-batch-News-')}) == 1
    assert len({k for k in tasks if k.startswith('rewrite-batch-Science-')}) == 1
    batches = [runner.read(p) for p in tmp_path.glob('batch-Fun-*.json')]
    generated = [row['id'] for b in batches for row in b['drafts']]
    assert len(generated) == len(set(generated))


def test_batch_invalid_objects_and_news_priority():
    pool = [{'id': str(i), 'importance': i, 'article': {'word_count': 400}} for i in range(8)]
    assert batch.validate_batch({'drafts': [None] * 5}, pool, 'News')
    rows = [{'id': str(i), 'reason': 'Good', 'article': draft()} for i in range(5)]
    assert not batch.validate_batch({'drafts': rows}, pool, 'News')
    rows[-1]['id'] = '7'
    assert batch.validate_batch({'drafts': rows}, pool, 'News')
    rows[-1]['id'] = '4'
    rows[0]['id'] = '7'
    assert not batch.validate_batch({'drafts': rows}, pool, 'News')
    assert batch.validate_order({'order': ['0', '0']}, pool, 'Fun')


def test_short_batch_draft_corrected_by_modifier_not_another_batch(tmp_path, monkeypatch):
    _, _, tasks, answer = setup_batch(tmp_path, monkeypatch)
    def short(root, key, system, material, validate, **kw):
        if key == 'review-modify-News-news04':
            material = deepcopy(material)
            material['article']['middle_en']['body'] = 'fact ' * 330
        value = answer(root, key, system, material, validate, **kw)
        if key == 'rewrite-batch-News-8':
            value['drafts'][0]['article']['middle_en']['body'] = 'fact ' * 281
        if key == 'review-modify-News-news04':
            value['corrected_article']['middle_en']['body'] = 'fact ' * 330
        return value
    monkeypatch.setattr(runner, 'ask', short)
    result = run_steps(tmp_path)
    assert result['counts']['news'] == 3
    assert len({k for k in tasks if k.startswith('rewrite-batch-News-')}) == 1
    assert len(runner.read(tmp_path / 'site/article_payloads/payload_2026-09-30-news-1/middle.json')['summary'].split()) == 330
