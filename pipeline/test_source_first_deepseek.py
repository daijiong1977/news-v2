"""Compact DeepSeek shortlist and continuous fifteen-draft handoff; no real APIs."""
from copy import deepcopy
import json
import sys
import pytest

from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_source_first import full_fixture


def fixture(root, monkeypatch):
    from pipeline.news_topics import TOPICS_BY_CATEGORY
    snapshot, calls, tasks, previous = full_fixture(root, monkeypatch)
    snapshot['test_profile'] = 'source-first-deepseek'
    runner.write(root / 'input.json', snapshot)
    materials = []
    def ask(root, key, prompt, material, validate, **kw):
        if key.startswith('rank-shortlist-'):
            tasks.append(key)
            materials.append(deepcopy(material))
            cat = material['category']
            # Prefer the original-category fixture titles, while cross-category
            # metadata is available for real animal/tech routing decisions.
            rows = [b for b in material['candidates'] if b['abstract'].startswith(cat)]
            value = {'catalog': {c: [] for c in runner.CATS}}
            value['catalog'][cat] = [{'id': b['id'], 'topic': list(TOPICS_BY_CATEGORY[cat])[i % len(TOPICS_BY_CATEGORY[cat])],
                'importance': 4 if i == 0 else 1, 'initial_risk': 0,
                'history_status': 'clear', 'history_confidence': 1} for i, b in enumerate(rows[:8])]
            assert not validate(value)
            return value
        return previous(root, key, prompt, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', ask)
    return snapshot, calls, tasks, materials, ask


def test_preflight_fifteen_trilingual_drafts_before_any_native_selection(tmp_path, monkeypatch):
    from pipeline.agent_shadow_shortlist import build_drafts
    snapshot, calls, tasks, materials, ask = fixture(tmp_path, monkeypatch)
    result = build_drafts(tmp_path)
    assert result['counts'] == {c: 5 for c in runner.CATS}
    handoff = runner.read(tmp_path / 'drafts-for-grok.json')
    assert len(handoff['articles']) == 15
    assert all({'source_id', 'easy_en', 'middle_en', 'zh'} <= set(a['article']) for a in handoff['articles'])
    assert len(materials) == 3
    for material in materials:
        assert all(set(b) == {'id', 'abstract'} for b in material['candidates'])
        assert 'fact fact' not in json.dumps(material)
        assert len(material['candidates']) <= len(snapshot['candidates'])
    assert len([k for k in tasks if k.startswith('rewrite-batch-')]) == 3
    assert not any(k.startswith(('select-', 'review-finish')) for k in tasks)
    assert all('python_audit' in a for a in handoff['articles'])
    before = list(tasks)
    assert build_drafts(tmp_path) == result
    assert tasks == before and sum(calls.values()) == 36
    # Resume consumes the saved five drafts; no second writer invocation.
    runner.advance(tmp_path)
    assert len([k for k in tasks if k.startswith('rewrite-batch-')]) == 3
    assert len([k for k in tasks if k.startswith('select-batch-')]) == 3


def test_shortlist_cannot_invent_id_duplicate_or_wrong_section(tmp_path, monkeypatch):
    from pipeline.agent_shadow_shortlist import validate_shortlist
    from pipeline.news_topics import TOPICS_BY_CATEGORY
    row = {'id': 'a', 'topic': next(iter(TOPICS_BY_CATEGORY['News'])), 'importance': 4,
           'initial_risk': 0, 'history_status': 'clear', 'history_confidence': 1}
    value = {'catalog': {'News': [row], 'Science': [], 'Fun': []}}
    assert not validate_shortlist(value, {'a'}, 'News')
    assert validate_shortlist(value, {'b'}, 'News')
    assert validate_shortlist({'catalog': {'News': [row, row], 'Science': [], 'Fun': []}}, {'a'}, 'News')
    assert validate_shortlist(value, {'a'}, 'Fun')
    assert validate_shortlist({'catalog': {'News': [{**row, 'history_status': 'uncertain'}], 'Science': [], 'Fun': []}}, {'a'}, 'News')


def test_casualty_outbreak_removed_before_paid_news_ranking(tmp_path, monkeypatch):
    from pipeline.agent_shadow_shortlist import DeepSeekSourceEditor
    from pipeline.agent_shadow_news_audience import NEWS_AUDIENCE_RULE
    snapshot, _, _, _, ask = fixture(tmp_path, monkeypatch)
    target = next(c for c in snapshot['candidates'] if c['category'] == 'News')
    target['title'] = "Congo's Ebola outbreak passes 4,000 deaths"
    policy = DeepSeekSourceEditor(tmp_path, snapshot, ask, lambda *a: None, False)
    policy.catalog = {c: [] for c in runner.CATS}
    originals = [{'id': target['id']}, {'id': next(c['id'] for c in snapshot['candidates']
                  if c['category'] == 'News' and c['id'] != target['id'])}]
    monkeypatch.setattr(policy, 'originals', lambda *a, **kw: originals)
    def rank(root, key, prompt, material, validate):
        assert NEWS_AUDIENCE_RULE in prompt
        assert target['id'] not in {c['id'] for c in material['candidates']}
        return {'catalog': {'News': [], 'Science': [], 'Fun': []}}
    policy.ask = rank
    assert policy._rank('News', 8) == []
    assert runner.read(tmp_path / 'shortlist-exclusions-News-8.json')[target['id']]
    assert target['id'] in {c['id'] for c in snapshot['candidates']}


def test_rank_role_and_new_profile_do_not_change_old_routing():
    from pipeline.agent_shadow_providers import task_role, validate_config
    from pipeline.agent_shadow_profiles import is_source_first, is_batch, uses_native_details
    assert task_role('rank-shortlist-News-8') == 'rank'
    assert task_role('plan') == 'editor' and task_role('select-batch-News-8') == 'editor'
    assert all(fn({'test_profile': 'source-first-deepseek'}) for fn in (is_source_first, is_batch, uses_native_details))
    validate_config({'roles': {'rank': {'type': 'http', 'model': 'deepseek-chat',
                    'endpoint': 'https://api.deepseek.com/chat/completions', 'key_env': 'DEEPSEEK_API_KEY'}}})


def test_grok_overrides_deepseek_order_and_no_soft_quota_refill(tmp_path, monkeypatch):
    _, calls, tasks, _, answer = fixture(tmp_path, monkeypatch)
    chosen = {}
    def editor(root, key, prompt, material, validate, **kw):
        if key.startswith('select-batch-'):
            tasks.append(key)
            cat = material['category']
            # Grok may rank a lower-importance draft first. Python must not
            # silently swap its composition, nor chase publisher quotas.
            ids = [d['id'] for d in material['drafts']]
            order = ids[1:] + ids[:1]
            chosen[cat] = order
            assert not validate({'order': order})
            assert 'python_audit' in material and 'FIVE-to-THREE' in prompt
            return {'order': order}
        return answer(root, key, prompt, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', editor)
    result = runner.advance(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    state = runner.read(tmp_path / 'editor-state.json')
    for cat in runner.CATS:
        assert [a['candidate']['id'] for a in state[cat]['accepted']] == chosen[cat][:3]
        assert state[cat]['target'] == 8
    assert sum(calls.values()) == 36
    assert len([k for k in tasks if k.startswith('review-finish-')]) == 9
    assert len([k for k in tasks if k.startswith('rewrite-batch-')]) == 3


def test_reserves_stay_inside_fixed_five_and_failed_group_never_backfills(tmp_path, monkeypatch):
    _, calls, tasks, _, answer = fixture(tmp_path, monkeypatch)
    def reject(root, key, prompt, material, validate, **kw):
        value = answer(root, key, prompt, material, validate, **kw)
        if key.startswith('review-finish-'):
            cat = material['category']
            order = runner.read(root / f'batch-{cat}-8.json')['order']
            sid = key.split(cat + '-', 1)[1]
            if cat == 'News' and sid in order[:2]:
                value['event_clear'] = False
        return value
    monkeypatch.setattr(runner, 'ask', reject)
    assert runner.advance(tmp_path)['counts']['news'] == 3
    state = runner.read(tmp_path / 'editor-state.json')['News']
    assert [a['candidate']['id'] for a in state['accepted']] == state['order'][2:]
    assert [o['selection_round'] for o in state['outcomes']] == [1, 1, 1, 2, 2]
    assert sum(calls.values()) == 36
    other = tmp_path / 'all-bad'; other.mkdir()
    _, calls2, tasks2, _, ask2 = fixture(other, monkeypatch)
    def all_bad(root, key, prompt, material, validate, **kw):
        value = ask2(root, key, prompt, material, validate, **kw)
        if key.startswith('review-finish-'):
            value['event_clear'] = False
        return value
    monkeypatch.setattr(runner, 'ask', all_bad)
    with pytest.raises(ValueError, match='fixed five'):
        runner.advance(other)
    assert not (other / 'done.json').exists()
    assert len(runner.read(other / 'group-blocked.json')['fixed_ids']) == 5
    assert sum(calls2.values()) == 36
    assert len([k for k in tasks2 if k.startswith('rewrite-batch-')]) == 3


def test_preflight_interruption_keeps_first_batch_and_completed_rank(tmp_path, monkeypatch):
    from pipeline.agent_shadow_shortlist import build_drafts
    _, calls, tasks, _, answer = fixture(tmp_path, monkeypatch)
    def interrupted(root, key, *a, **kw):
        if key == 'rewrite-batch-Science-8':
            raise RuntimeError('power lost')
        return answer(root, key, *a, **kw)
    monkeypatch.setattr(runner, 'ask', interrupted)
    with pytest.raises(RuntimeError, match='power lost'):
        build_drafts(tmp_path)
    assert (tmp_path / 'raw-batch-News-8.json').exists()
    monkeypatch.setattr(runner, 'ask', answer)
    build_drafts(tmp_path)
    assert len([k for k in tasks if k.startswith('rank-shortlist-')]) == 3
    assert tasks.count('rewrite-batch-News-8') == 1
    assert sum(calls.values()) == 36


def test_fixed_group_validator_and_mechanical_audit():
    from pipeline.agent_shadow_batch import validate_fixed_order
    from pipeline.agent_shadow_shortlist import audit_draft
    from pipeline.test_agent_shadow_review_fixes import draft
    ids = [str(i) for i in range(5)]
    pool = [{'id': sid} for sid in ids]
    assert not validate_fixed_order({'order': ids[::-1]}, pool)
    assert validate_fixed_order({'order': ids[:3]}, pool)
    assert validate_fixed_order({'order': ids[:-1] + ['outside']}, pool)
    assert validate_fixed_order({'order': [[], *ids[:4]]}, pool)
    art = {'body': 'fact ' * 400, 'word_count': 400}
    assert audit_draft(draft(), art, 'News')['status'] == 'pass'
    assert audit_draft(None, art, 'News')['status'] == 'repair_required'


def test_three_part_cli_drains_python_boundaries_yields_once_and_never_deploys_early(tmp_path, monkeypatch, capsys):
    from pipeline import kidsnews_bot as bot
    runner.write(tmp_path / 'input.json', {'test_profile': 'source-first-deepseek'})
    runner.write(tmp_path / 'drafts-for-grok.json', {})
    calls = []
    results = iter([(0, {'completed_step': 'plan'}), (0, {'completed_step': 'batch'}),
                    (2, {'read': 'request.json', 'write_to': 'answer.json'})])
    def invoke(*a):
        calls.append(a); return next(results)
    monkeypatch.setattr(bot, 'invoke', invoke)
    monkeypatch.setattr(sys, 'argv', ['bot', '--run-dir', str(tmp_path)])
    assert bot.main() == 2
    rows = capsys.readouterr().out.splitlines()
    assert len(rows) == 1 and json.loads(rows[0])['read'] == 'request.json'
    assert len(calls) == 3 and all(c[0] == 'pipeline.agent_shadow' for c in calls)
    monkeypatch.setattr(sys, 'argv', ['bot', '--run-dir', str(tmp_path), '--publish'])
    assert bot.main() == 1 and 'ack-same-day' in capsys.readouterr().out


def test_fixed_group_zip_official_reader_delivery_is_idempotent(tmp_path, monkeypatch):
    from pipeline import kidsnews_bot as bot, website_delivery as delivery
    from pipeline.website_release import build_reader, zip_files
    from pipeline.publication_bundle import encoded
    from pipeline.test_source_first_reader import template
    fixture(tmp_path, monkeypatch)
    runner.advance(tmp_path)
    shell = tmp_path / 'shell'; shell.mkdir()
    (shell / 'index.html').write_text('<script src="article.jsx"></script>')
    (shell / 'article.jsx').write_text(template())
    def invoke(module, *args):
        assert module == 'pipeline.website_release'
        reader = build_reader((tmp_path / 'publication.zip').read_bytes(), shell, 'a' * 40)
        from pathlib import Path
        out = Path(args[args.index('--output-dir') + 1]); out.mkdir()
        (out / 'reader.zip').write_bytes(reader['zip'])
        runner.write(out / 'latest-manifest.json', reader['manifest'])
        runner.write(out / 'records.json', reader['records'])
        return 0, {'ok': True}
    monkeypatch.setattr(bot, 'invoke', invoke)
    calls = []
    def handoff(*args, **kw):
        calls.append(args); return {'branch': args[1], 'pushed': True}
    monkeypatch.setattr(delivery, 'handoff', handoff)
    local = bot.artifacts(tmp_path)
    assert not local['published'] and not calls
    from pipeline.publication_bundle import unpack
    assert unpack((tmp_path / 'publication.zip').read_bytes())[1]['editorial_profile'] == 'source-first-deepseek'
    first = bot.artifacts(tmp_path, True, 'codex/website-release-test')
    assert first == bot.artifacts(tmp_path, True, 'codex/website-release-test')
    assert len(calls) == 1 and first['status'] == 'ci_verification_pending'
    assert first['published'] is False
    with pytest.raises(ValueError, match='already attempted'):
        bot.artifacts(tmp_path, True, 'codex/website-release-other')


def test_preflight_command_stdout_single_json_no_native_tasks(tmp_path, monkeypatch, capsys):
    fixture(tmp_path, monkeypatch)
    from pathlib import Path
    runner.write(tmp_path / 'providers.json', runner.read(Path(runner.__file__).resolve().parents[1] /
                                                       'config/shadow-source-first-deepseek.json'))
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline-test-placeholder')
    monkeypatch.setattr(runner, 'prepare', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(runner, 'check_stale', lambda *a, **kw: None)
    monkeypatch.setattr(sys, 'argv', ['agent_shadow', 'preflight', '--run-dir', str(tmp_path),
                                   '--test-profile', 'source-first-deepseek', '--editor-mode', 'autonomous'])
    assert runner.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 and json.loads(lines[0])['counts'] == {c: 5 for c in runner.CATS}


def test_uncertain_handoff_stays_attempting_and_never_repushes(tmp_path, monkeypatch):
    from pipeline import kidsnews_bot as bot, website_delivery as delivery
    from pipeline.website_release import build_reader
    from pipeline.publication_bundle import sha
    fixture(tmp_path, monkeypatch)
    runner.advance(tmp_path)
    from pipeline.publication_bundle import build
    internal = tmp_path / 'publication.zip'; build(tmp_path, internal)
    out = tmp_path / 'reader-artifact'; out.mkdir()
    from pipeline.test_source_first_reader import template
    shell = tmp_path / 'shell'; shell.mkdir()
    (shell / 'index.html').write_text('<script src="article.jsx"></script>')
    (shell / 'article.jsx').write_text(template())
    generated = build_reader(internal.read_bytes(), shell, 'a' * 40)
    data = generated['zip']
    (out / 'reader.zip').write_bytes(data)
    runner.write(out / 'latest-manifest.json', generated['manifest'])
    runner.write(out / 'records.json', generated['records'])
    runner.write(out / 'reader-build.json', {'publication_sha256': sha(internal.read_bytes())})
    calls = []
    def uncertain(*a, **kw):
        calls.append(a); raise ConnectionError('Git push outcome uncertain')
    monkeypatch.setattr(delivery, 'handoff', uncertain)
    with pytest.raises(ConnectionError):
        bot.artifacts(tmp_path, True, 'codex/website-release-test')
    with pytest.raises(ValueError, match='already attempted'):
        bot.artifacts(tmp_path, True, 'codex/website-release-test')
    assert len(calls) == 1 and runner.read(tmp_path / 'website-handoff.json')['status'] == 'attempting'
