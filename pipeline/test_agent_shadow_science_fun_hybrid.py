"""Offline Science/Fun hybrid scope, modifier and local-only boundary."""
import pytest
from pipeline import agent_shadow as runner


def test_prepare_collects_only_science_fun(tmp_path, monkeypatch):
    from pipeline import db_config, full_round
    from pipeline.test_agent_shadow import source
    registry = tmp_path / 'registry.json'
    runner.write(registry, {'date': '2026-09-30', 'sources': [], 'history': [
        {'category': c, 'published_date': '2026-09-29'} for c in runner.CATS]})
    collected = []
    monkeypatch.setattr(db_config, 'load_sources', lambda cat, **kw: collected.append(cat) or [source()])
    monkeypatch.setattr(full_round, 'phase_a_light', lambda cat, sources, **kw: [])
    runner.prepare(tmp_path, '2026-09-30', registry_file=registry,
                   editor_mode='autonomous', test_profile='science-fun-deepseek')
    snapshot = runner.read(tmp_path / 'input.json')
    assert collected == ['Science', 'Fun']
    assert snapshot['history']['News'] == []
    assert snapshot['review_mode'] == 'modifier'


def test_science_fun_full_round_skips_news_and_retains_rules(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_autonomous import setup
    from pipeline.test_agent_shadow_review_fixes import run_steps, draft
    from pipeline.editorial_policy import publisher_key
    from pipeline.news_sources import NewsSource
    fetched, _, tasks, answer, _ = setup(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot.update(test_profile='science-fun-deepseek', active_categories=['Science', 'Fun'], review_mode='modifier')
    runner.write(tmp_path / 'input.json', snapshot)
    called = []
    def respond(root, key, system, material, validate, **kw):
        called.append(key)
        if key == 'plan':
            value = answer(root, key, system, material, lambda v: [], **kw)
            assert validate(value)  # News picks must not sneak into this test.
            value['catalog']['News'] = []
            assert not validate(value)
            return value
        if key.startswith('review-modify-'):
            value = answer(root, 'review-Science-any', system, material, lambda v: [], **kw)
            value['corrected_article'] = draft()
            assert not validate(value)
            return value
        return answer(root, key, system, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', respond)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 0, 'science': 3, 'fun': 3}
    assert not any(k.startswith('news') for k in fetched)
    assert sum(fetched.values()) == 6
    assert not any(k.startswith(('review-image-', 'review-Science-', 'review-Fun-')) for k in called)
    assert len(set(k for k in called if k.startswith('review-modify-'))) == 6
    accepted = runner.read(tmp_path / 'editor-state.json')['Science']['accepted']
    pubs = {publisher_key(NewsSource(**snapshot['sources'][a['candidate']['article']['source']])) for a in accepted}
    assert len(pubs) >= 2
    assert result['image_policy'] == 'source_only_mechanical_not_visual_review'


@pytest.mark.parametrize('command', ['publish', 'verify'])
def test_science_fun_profile_forbids_publish_and_verify(tmp_path, monkeypatch, capsys, command):
    import sys
    runner.write(tmp_path / 'input.json', {'test_profile': 'science-fun-deepseek'})
    monkeypatch.setattr('pipeline.agent_shadow_logs.ship', lambda root: None)
    monkeypatch.setattr(sys, 'argv', ['shadow', command, '--run-dir', str(tmp_path)])
    assert runner.main() == 1
    assert 'partial publication is forbidden' in capsys.readouterr().out
