"""Pro shortlist regressions from the paired Flash/Pro summary replay."""
import json
from pathlib import Path

import pytest

from pipeline import agent_shadow as runner


def row(number, **changes):
    return {'id': number, 'topic': 'community', 'importance': 3, 'initial_risk': 1,
            'history_status': 'clear', 'history_confidence': .9,
            'event_key': f'event-{number}', **changes}


def test_compact_ids_map_exactly_and_filter_ineligible_duplicate_events():
    from pipeline.agent_shadow_rank_contract import normalize_rank
    ids = {i: f'stable-hash-{i}' for i in range(1, 7)}
    value = {'ranked': [row(1, event_key='same-case'), row(2, event_key=' Same Case '),
                        row(3, history_status='duplicate'), row(4, initial_risk=4),
                        row(5, history_confidence=.5), row(6)]}
    result = normalize_rank(value, ids, 'News')
    assert [r['id'] for r in result['catalog']['News']] == [ids[1], ids[6]]
    assert [r['reason'] for r in result['shortlist_audit']] == [
        'same_event_in_shortlist', 'history_duplicate', 'initial_risk', 'history_uncertain']
    assert value['ranked'][0]['id'] == 1


@pytest.mark.parametrize('bad', [True, 1.0, '1', 'stable-hash-1', 0, 99])
def test_compact_ids_never_guess_or_fuzzy_match(bad):
    from pipeline.agent_shadow_rank_contract import normalize_rank
    with pytest.raises(ValueError):
        normalize_rank({'ranked': [row(bad)]}, {1: 'stable-hash-1'}, 'News')


def test_invalid_enum_duplicate_id_and_missing_event_do_not_pass():
    from pipeline.agent_shadow_rank_contract import normalize_rank
    for rows in ([row(1), row(1)], [row(1, topic='not-a-topic')],
                 [row(1, importance=True)], [row(1, event_key='')],
                 [row(1, history_status='maybe')]):
        with pytest.raises(ValueError):
            normalize_rank({'ranked': rows}, {1: 'stable'}, 'News')


@pytest.mark.parametrize('title,summary,category,reason', [
    ('This giant stick insect fooled scientists', 'Scientists identified two new species.', 'Fun', 'research_belongs_science'),
    ('New plant armor triples strawberry yields', 'A protective fabric from research.', 'Fun', 'research_belongs_science'),
    ('Jackie tribute celebrates eagle life', 'Forever missed.', 'Fun', 'memorial_not_fun'),
    ('Which music release is your favorite? Vote!', '', 'Fun', 'poll_or_setlist_not_story'),
    ('Concert setlist: every song', '', 'Fun', 'poll_or_setlist_not_story'),
    ('Governor responds to rape inquiry', '', 'News', 'sexual_assault_not_child_suitable'),
    ('Backup execution plans', 'Capital punishment policies.', 'News', 'execution_not_child_suitable'),
])
def test_explicit_unsuitable_metadata_is_removed_before_ranking(title, summary, category, reason):
    from pipeline.agent_shadow_rank_contract import metadata_exclusion
    assert metadata_exclusion({'title': title, 'summary': summary}, category) == reason


def test_metadata_guard_keeps_science_research_and_genuine_fun():
    from pipeline.agent_shadow_rank_contract import metadata_exclusion
    assert not metadata_exclusion({'title': 'Scientists find new species', 'summary': 'A study.'}, 'Science')
    for title in ('Messi animation trailer', 'Djokovic wins tennis match', 'Swimmer breaks world record',
                  'Scientist rescues a lost turtle', 'Robot hand plays a video game', 'Shooting stars light up the sky'):
        assert not metadata_exclusion({'title': title}, 'Fun')


def test_new_default_uses_pro_rank_and_flash_writer_without_thinking(tmp_path):
    from pipeline.agent_shadow_providers import TaskRouter
    config = runner.read(Path(runner.__file__).resolve().parents[1] / 'config/shadow-source-first-deepseek.json')
    runner.write(tmp_path / 'providers.json', config)
    rank = TaskRouter(tmp_path, 'rank-shortlist-News-8').prepare_payload({'messages': []})
    batch = TaskRouter(tmp_path, 'rewrite-batch-News-8').prepare_payload({'messages': []})
    assert rank['model'] == 'deepseek-v4-pro'
    assert batch['model'] == 'deepseek-flash'
    assert rank['thinking'] == batch['thinking'] == {'type': 'disabled'}


def test_new_contract_only_sends_summary_and_restores_internal_ids(tmp_path, monkeypatch):
    from pipeline.test_source_first_deepseek import fixture
    from pipeline.agent_shadow_shortlist import DeepSeekSourceEditor
    snapshot, _, _, _, _ = fixture(tmp_path, monkeypatch)
    snapshot['shortlist_contract'] = 'indices-v1'
    policy = DeepSeekSourceEditor(tmp_path, snapshot, None, runner.boundary, False)
    policy.catalog = {c: [] for c in runner.CATS}
    expected = [c['id'] for c in snapshot['candidates'] if c['category'] == 'News']
    def answer(root, key, prompt, material, validate, **kwargs):
        assert all(type(c['id']) is int and set(c) == {'id', 'abstract'} for c in material['candidates'])
        assert not any(sid in json.dumps(material) for sid in expected)
        assert 'fact fact' not in json.dumps(material)
        chosen = next(c['id'] for c in material['candidates'] if c['abstract'].startswith('News'))
        result = kwargs['normalize']({'ranked': [row(chosen)]})
        assert not validate(result)
        return result
    policy.ask = answer
    rows = policy._rank('News', 8)
    assert rows[0]['id'] == expected[0]
    record = runner.read(tmp_path / 'shortlist-News-8.json')
    assert record['contract'] == 'indices-v1' and record['index_to_id']


def test_automatic_provider_resume_keeps_old_flash_config(tmp_path, monkeypatch, capsys):
    import sys
    config = {'roles': {'rank': {'type': 'http', 'model': 'deepseek-flash',
              'endpoint': 'https://api.deepseek.com/chat/completions', 'key_env': 'DEEPSEEK_API_KEY'}}}
    runner.write(tmp_path / 'providers.json', config)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline')
    monkeypatch.setattr(runner, 'prepare', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(sys, 'argv', ['agent_shadow', 'prepare', '--run-dir', str(tmp_path),
                        '--test-profile', 'source-first-deepseek', '--editor-mode', 'autonomous'])
    assert runner.main() == 0
    assert runner.read(tmp_path / 'providers.json') == config
    assert json.loads(capsys.readouterr().out)['ok']


def test_shortlist_shortfall_stops_before_any_writer(tmp_path, monkeypatch):
    from pipeline.agent_shadow_shortlist import build_drafts, DeepSeekSourceEditor
    runner.write(tmp_path / 'input.json', {'test_profile': 'source-first-deepseek',
                                         'shortlist_contract': 'indices-v1'})
    monkeypatch.setattr(DeepSeekSourceEditor, 'plan', lambda s: setattr(s, 'catalog', {c: [] for c in runner.CATS}))
    monkeypatch.setattr(DeepSeekSourceEditor, 'pool', lambda *a, **kw: pytest.fail('Do not pay to write an incomplete group'))
    with pytest.raises(ValueError, match='shortlist_shortfall'):
        build_drafts(tmp_path)
    assert runner.read(tmp_path / 'shortlist-shortfalls.json') == {c: 5 for c in runner.CATS}


@pytest.mark.parametrize('old_context', [False, True])
def test_prepare_freezes_shortlist_contract_and_preserves_legacy(tmp_path, monkeypatch, old_context):
    from dataclasses import asdict
    from pipeline import db_config, agent_shadow_source_first as collection
    from pipeline.test_agent_shadow_source_first import sources
    history = [{'category': c, 'published_date': '2026-10-01', 'title': 'Prior event'} for c in runner.CATS]
    registry = tmp_path / 'registry.json'
    runner.write(registry, {'date': '2026-10-02', 'sources': [], 'history': history})
    monkeypatch.setattr(db_config, 'load_sources', lambda cat, **kw: sources(cat, 1))
    if old_context:
        runner.write(tmp_path / 'prepare-context.json', {'date': '2026-10-02',
            'test_profile': 'source-first-deepseek', 'http_fallback': None,
            'history': {c: [r for r in history if r['category'] == c] for c in runner.CATS},
            'sources': {c: [asdict(s) for s in sources(c, 1)] for c in runner.CATS}})
    def collect(root, selected, today):
        runner.write(root / 'source-collection.json', {'sections': {
            c: {'sources': [{'source': asdict(s), 'results': []} for s in rows]}
            for c, rows in selected.items()}})
        return []
    monkeypatch.setattr(collection, 'collect', collect)
    runner.prepare(tmp_path, '2026-10-02', registry_file=registry,
                   editor_mode='autonomous', test_profile='source-first-deepseek')
    assert runner.read(tmp_path / 'input.json')['shortlist_contract'] == (None if old_context else 'indices-v1')


def test_compact_three_category_rank_to_fifteen_drafts_and_resume(tmp_path, monkeypatch):
    from pipeline.test_source_first_deepseek import fixture
    from pipeline.agent_shadow_shortlist import build_drafts
    from pipeline.news_topics import TOPICS_BY_CATEGORY
    snapshot, calls, tasks, _, previous = fixture(tmp_path, monkeypatch)
    snapshot['shortlist_contract'] = 'indices-v1'
    runner.write(tmp_path / 'input.json', snapshot)
    rank_calls = []
    def answer(root, key, prompt, material, validate, **kw):
        if not key.startswith('rank-shortlist-'):
            return previous(root, key, prompt, material, validate, **kw)
        cat = material['category']
        rank_calls.append(cat)
        choices = [b for b in material['candidates'] if b['abstract'].startswith(cat)][:8]
        value = {'ranked': [row(b['id'], topic=next(iter(TOPICS_BY_CATEGORY[cat]))) for b in choices]}
        value = kw['normalize'](value)
        assert not validate(value)
        return value
    monkeypatch.setattr(runner, 'ask', answer)
    assert build_drafts(tmp_path)['counts'] == {c: 5 for c in runner.CATS}
    output = runner.read(tmp_path / 'drafts-for-grok.json')
    assert all(type(a['id']) is str and {'easy_en', 'middle_en', 'zh'} <= set(a['article']) for a in output['articles'])
    assert len(rank_calls) == 3 and len([k for k in tasks if k.startswith('rewrite-batch-')]) == 3
    build_drafts(tmp_path)
    assert len(rank_calls) == 3 and sum(calls.values()) == 36
