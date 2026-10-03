"""Three-stage disk handoff; all sources/models/deploys mocked offline."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from pipeline import agent_shadow as runner
from pipeline.kidsnews_groups import prepare_groups, import_groups, GroupNeeded
from pipeline.test_source_first_deepseek import fixture
from pipeline.test_agent_shadow_source_first import combined_answer


def prepared(root, monkeypatch):
    from pipeline.agent_shadow_shortlist import build_drafts
    _, _, tasks, _, _ = fixture(root, monkeypatch)
    build_drafts(root)
    manifest = prepare_groups(root)
    return manifest, tasks


def answers(root):
    for cat in runner.CATS:
        request = runner.read(root / 'groups' / f'{cat}-request.json')
        order = [a['id'] for a in request['candidates']][::-1]
        runner.write(root / 'groups' / f'{cat}-selection.json',
                     {'request_id': request['request_id'], 'order': order, 'reason': 'Best child interest'})
        for sid in order[:3]:
            runner.write(root / 'groups/answers' / f'{cat}-{sid}.json',
                         {'request_id': request['request_id'], 'id': sid, 'value': combined_answer()})


def test_prepare_self_contained_fifteen_and_no_native_calls(tmp_path, monkeypatch):
    manifest, tasks = prepared(tmp_path, monkeypatch)
    assert manifest['counts'] == {c: 5 for c in runner.CATS}
    assert len(tasks) == 6
    for path in manifest['requests'].values():
        request = runner.read(Path(path))
        assert len(request['candidates']) == 5
        assert request['history'] and request['prompt']
        assert all(a['source']['body'] and a['body_word_bands'] for a in request['candidates'])
    before = list(tasks)
    assert prepare_groups(tmp_path) == manifest and tasks == before
    with pytest.raises(ValueError, match='Three-stage'):
        runner.advance(tmp_path)


def test_import_nine_and_pack_with_zero_further_model_calls(tmp_path, monkeypatch):
    manifest, tasks = prepared(tmp_path, monkeypatch)
    answers(tmp_path)
    before = list(tasks)
    assert import_groups(tmp_path)['counts'] == {c: 3 for c in runner.CATS}
    monkeypatch.setattr(runner, 'ask', lambda *a, **k: pytest.fail('No model allowed after stage one'))
    assert runner.advance(tmp_path)['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    assert tasks == before
    assert import_groups(tmp_path)['counts'] == {c: 3 for c in runner.CATS}
    for cat in runner.CATS:
        req = runner.read(Path(manifest['requests'][cat]))
        accepted = runner.read(tmp_path / 'editor-state.json')[cat]['accepted']
        assert [a['candidate']['id'] for a in accepted] == [a['id'] for a in req['candidates']][::-1][:3]


def test_bad_id_and_stale_request_refused(tmp_path, monkeypatch):
    prepared(tmp_path, monkeypatch)
    answers(tmp_path)
    path = tmp_path / 'groups/News-selection.json'
    selection = runner.read(path)
    selection['order'][0] = 'not-in-five'
    runner.write(path, selection)
    with pytest.raises(GroupNeeded, match='five'):
        import_groups(tmp_path)
    answers(tmp_path)
    selection = runner.read(path)
    selection['request_id'] = 'old'
    runner.write(path, selection)
    with pytest.raises(GroupNeeded, match='request_id'):
        import_groups(tmp_path)


def test_targeted_body_fix_once_preserves_other_articles(tmp_path, monkeypatch):
    _, tasks = prepared(tmp_path, monkeypatch)
    answers(tmp_path)
    selection = runner.read(tmp_path / 'groups/News-selection.json')
    sid = selection['order'][1]
    path = tmp_path / 'groups/answers' / f'News-{sid}.json'
    good = runner.read(path)
    bad = deepcopy(good)
    bad['value']['corrected_article']['middle_en']['body'] = 'Too short.'
    runner.write(path, bad)
    with pytest.raises(GroupNeeded):
        import_groups(tmp_path)
    state = runner.read(tmp_path / 'editor-state.json')
    assert len(state['News']['accepted']) == 1
    before = deepcopy(state['News']['accepted'][0])
    assert runner.read(tmp_path / 'groups/repair.json')['errors']
    with pytest.raises(GroupNeeded):
        import_groups(tmp_path)  # no answer => no busy retry/model call
    runner.write(path, good)
    assert import_groups(tmp_path)['counts'] == {c: 3 for c in runner.CATS}
    assert runner.read(tmp_path / 'editor-state.json')['News']['accepted'][0] == before
    assert len(tasks) == 6


def test_passed_answer_and_source_tamper_are_rejected(tmp_path, monkeypatch):
    prepared(tmp_path, monkeypatch)
    answers(tmp_path)
    import_groups(tmp_path)
    path = next((tmp_path / 'groups/answers').glob('News-*.json'))
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(RuntimeError, match='completed answer'):
        import_groups(tmp_path)


def test_detail_only_fix_does_not_change_body_and_can_omit_bad_module(tmp_path, monkeypatch):
    prepared(tmp_path, monkeypatch)
    answers(tmp_path)
    selection = runner.read(tmp_path / 'groups/News-selection.json')
    sid = selection['order'][0]
    path = tmp_path / 'groups/answers' / f'News-{sid}.json'
    envelope = runner.read(path)
    envelope['value']['details']['0_middle']['questions'] = []
    runner.write(path, envelope)
    with pytest.raises(GroupNeeded):
        import_groups(tmp_path)
    # Two unsuccessful targeted detail attempts, no rewriting the group/body.
    for revision in ('fix one', 'fix two'):
        envelope['value']['notes'] = revision
        runner.write(path, envelope)
        try:
            import_groups(tmp_path)
        except GroupNeeded:
            pass
    result = runner.read(tmp_path / 'finished-articles' / f'News-{sid}.json')['result']
    assert result['status'] == 'ready_degraded'
    assert result['entry'] == combined_answer()['corrected_article']
    assert set(result['details']) == {'0_easy'}


def test_finalize_missing_prepare_never_invokes_models(tmp_path, monkeypatch, capsys):
    from pipeline import kidsnews_bot
    monkeypatch.setattr('sys.argv', ['bot', '--stage', 'finalize', '--run-dir', str(tmp_path)])
    monkeypatch.setattr(kidsnews_bot, 'invoke', lambda *a: pytest.fail('No preflight in finalize'))
    assert kidsnews_bot.main() == 1
    output = capsys.readouterr().out.strip().splitlines()
    assert len(output) == 1 and not json.loads(output[0])['ok']


def test_two_cli_stages_single_json_no_final_model_calls(tmp_path, monkeypatch, capsys):
    from pipeline import kidsnews_bot
    from pipeline.agent_shadow_shortlist import build_drafts
    fixture(tmp_path, monkeypatch)
    build_drafts(tmp_path)
    monkeypatch.setattr('sys.argv', ['bot', '--stage', 'prepare', '--run-dir', str(tmp_path)])
    assert kidsnews_bot.main() == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 1
    answers(tmp_path)
    monkeypatch.setattr(runner, 'ask', lambda *a, **kw: pytest.fail('Final Python must not call any model'))
    monkeypatch.setattr(kidsnews_bot, 'artifacts', lambda *a: {'ok': True, 'published': False})
    monkeypatch.setattr('sys.argv', ['bot', '--stage', 'finalize', '--run-dir', str(tmp_path)])
    assert kidsnews_bot.main() == 0
    assert json.loads(capsys.readouterr().out)['ok']
    assert runner.read(tmp_path / 'done.json')['counts'] == {'news': 3, 'science': 3, 'fun': 3}


def test_stale_history_recheck_is_file_only_and_does_not_mutate_input(tmp_path, monkeypatch):
    from datetime import date, datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    from pipeline.kidsnews_groups import check_group_stale
    prepared(tmp_path, monkeypatch)
    answers(tmp_path)
    before = (tmp_path / 'input.json').read_bytes()
    runner.write(tmp_path / 'metrics.json', {'started_at': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()})
    today = datetime.now(ZoneInfo('America/New_York')).date()
    # Do not accidentally use the frozen run's own day: history deliberately
    # excludes it. The old today-2 fixture became empty at the Oct 3 rollover.
    target_day = date.fromisoformat(runner.read(tmp_path / 'input.json')['date'])
    history_day = today - timedelta(days=1)
    if history_day == target_day:
        history_day = today - timedelta(days=2)
    registry = tmp_path / 'fresh.json'
    runner.write(registry, {'date': today.isoformat(), 'history': [
        {'category': cat, 'published_date': history_day.isoformat(),
         'source_title': 'Another old event', 'source_url': 'https://old.example/other'} for cat in runner.CATS]})
    monkeypatch.setattr(runner, 'ask', lambda *a, **kw: pytest.fail('Stale guard cannot call model'))
    with pytest.raises(GroupNeeded) as exc:
        check_group_stale(tmp_path, True, registry)
    request = runner.read(Path(exc.value.path))
    ids = [r['id'] for rows in request['candidates'].values() for r in rows]
    runner.write(Path(request['write_to']), {'request_id': request['request_id'], 'clear_ids': ids, 'blocked_ids': []})
    check_group_stale(tmp_path, True, registry)
    assert (tmp_path / 'input.json').read_bytes() == before
    assert runner.read(tmp_path / 'metrics.json')['history_rechecked_at']
