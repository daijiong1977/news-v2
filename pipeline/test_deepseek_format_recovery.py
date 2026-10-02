import json
import pytest
from pipeline.agent_shadow_batch_json import decode_batch


def test_extra_closer_and_misplaced_chinese_preserve_all_text():
    article = {'source_id': 0, 'easy_en': {'body': 'A } bracket inside text.'},
               'middle_en': {'body': 'Original words.'}}
    value = {'drafts': [{'id': 'a', 'reason': 'good', 'article': article,
                        'zh': {'headline': '标题', 'summary': '原摘要'}}], 'skipped': []}
    raw = json.dumps(value, ensure_ascii=False).replace('}],', '}}],')
    result, repairs = decode_batch(raw)
    assert result['drafts'][0]['article'] == {**article, 'zh': value['drafts'][0]['zh']}
    assert 'zh' not in result['drafts'][0]
    assert repairs == ['drop_unmatched_object_closer', 'move_sibling_zh:a']


def test_valid_answer_is_unchanged_and_ambiguous_or_truncated_stays_error():
    raw = '{"drafts":[],"skipped":[]}'
    assert decode_batch(raw) == (json.loads(raw), [])
    for bad in ('{"drafts":[', '{"drafts":[],"drafts":[]}', raw + 'garbage',
                '{"drafts":[{"article":{"zh":{"summary":"one"}},"zh":{"summary":"two"}}]}'):
        with pytest.raises(ValueError):
            decode_batch(bad)


def test_ask_recovers_envelope_without_rewriting_answer_or_native_handoff(tmp_path, monkeypatch):
    from pipeline import agent_shadow as runner
    from pipeline.ai_providers.transport import AgentFilesProvider, AgentNeeded
    value = {'drafts': [{'id': 'a', 'article': {'source_id': 0},
                        'zh': {'headline': '原标题', 'summary': '原摘要'}}]}
    raw = json.dumps(value).replace('}]}', '}}]}')
    envelope = {'choices': [{'message': {'content': raw}, 'finish_reason': 'stop'}]}
    original_complete = AgentFilesProvider.complete
    def answer(provider, payload, timeout):
        try:
            return original_complete(provider, payload, timeout)
        except AgentNeeded as pending:
            runner.write(pending.answer, {'request_id': pending.request_id,
                         'content': raw, 'finish_reason': 'stop'})
            return original_complete(provider, payload, timeout)
    monkeypatch.setattr(AgentFilesProvider, 'complete', answer)
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    result = runner.ask(tmp_path, 'rewrite-batch-Fun-8', 'JSON', {}, lambda v: [])
    assert result['drafts'][0]['article']['zh'] == value['drafts'][0]['zh']
    journal = runner.read(tmp_path / 'batch-format-recovery.json')
    assert next(iter(journal.values()))['content_policy'] == 'text unchanged; envelope only'
    assert len(runner.read(tmp_path / 'metrics.json')['steps']) == 1


def test_fence_and_trailing_comma_recovery_never_changes_article_strings():
    from pipeline.agent_shadow_batch_json import decode_json_object
    raw = '```json\n{"ranked":[{"id":1,"text":"Keep ,} and \\\"quotes\\\"",},],}\n```'
    value, actions = decode_json_object(raw)
    assert value == {'ranked': [{'id': 1, 'text': 'Keep ,} and "quotes"'}]}
    assert actions == ['strip_json_fence', 'drop_trailing_comma', 'drop_trailing_comma', 'drop_trailing_comma']
    for bad in ('prefix {"ranked":[]}', '{"ranked":[],"ranked":[1]}',
                '{"ranked":[{"id":1}', '{"ranked":[1,,2]}', '{"ranked":NaN}'):
        with pytest.raises(ValueError):
            decode_json_object(bad)
