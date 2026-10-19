"""Review regressions for bounded per-article finishing; no model/network calls."""
from copy import deepcopy

from pipeline import agent_shadow as runner
from pipeline.agent_shadow_finish import finish
from pipeline.test_agent_shadow_source_first import combined_answer


ART = {'word_count': 400, 'body': 'fact ' * 400, 'link': 'https://example.org/story'}


def broken_details():
    value = combined_answer()
    value['details']['0_middle']['questions'] = []
    return value


def test_semantic_stale_event_edited_as_historical_fallback_without_retry(tmp_path):
    runner.write(tmp_path / 'source-collection.json', {'semantic_event_recency': True})
    runner.write(tmp_path / 'input.json', {'date': '2026-10-03'})
    calls = []
    def ask(root, key, prompt, data, validate):
        calls.append(key)
        assert 'three weeks ago' in prompt
        assert data['as_of_date'] == '2026-10-03'
        value = combined_answer()
        value.update(source_event_fresh=False, freshness_reason='Main event was three weeks ago')
        return value
    result = finish(tmp_path, 'Fun', 'old', ART, {}, [], [], ask)
    assert result['status'] == 'ready_stale'
    assert any('three weeks ago' in w for w in result['warnings'])
    assert calls == ['review-finish-Fun-old']
    assert finish(tmp_path, 'Fun', 'old', ART, {}, [], [], ask) == result


def test_semantic_recency_missing_answer_cannot_pass(tmp_path):
    runner.write(tmp_path / 'source-collection.json', {'semantic_event_recency': True})
    runner.write(tmp_path / 'input.json', {'date': '2026-10-03'})
    calls = []
    def ask(root, key, prompt, data, validate):
        calls.append(key)
        value = combined_answer()
        value.pop('source_event_fresh')
        return value
    result = finish(tmp_path, 'Fun', 'missing', ART, {}, [], [], ask)
    assert result['status'] == 'gone'
    assert len(calls) == 2


def test_old_checkpoint_does_not_gain_new_answer_contract(tmp_path):
    runner.write(tmp_path / 'source-collection.json', {'freshness_policy': 'category-source-date-v3'})
    def ask(root, key, prompt, data, validate):
        assert 'three weeks ago' not in prompt
        value = combined_answer()
        value.pop('source_event_fresh')
        return value
    assert finish(tmp_path, 'Fun', 'legacy', ART, {}, [], [], ask)['status'] == 'ready_full'


def test_new_finish_sees_verified_publication_date_and_source_title(tmp_path):
    runner.write(tmp_path / 'source-collection.json', {'semantic_event_recency': True})
    runner.write(tmp_path / 'input.json', {'date': '2026-10-03'})
    article = {**ART, 'title': "Sabalenka 'trying hard to be easier on myself'",
               'published': 'Fri, 02 Oct 2026 16:23:39 GMT'}
    def ask(root, key, prompt, data, validate):
        assert data['source_title'] == article['title']
        assert data['source_published'] == article['published']
        assert 'main subject' in prompt
        return combined_answer()
    finish(tmp_path, 'Fun', 'star', article, {}, [], [], ask)


def test_source_title_subject_cannot_be_displaced_by_side_paragraph():
    from pipeline.agent_shadow_finish import checked_body
    article = {**ART, 'title': "Sabalenka 'trying hard to be easier on myself'",
               'body': 'Aryna Sabalenka began her China Open campaign. ' + 'fact ' * 400 +
                       'Novak Djokovic played elsewhere.'}
    value = combined_answer()
    assert any('Sabalenka' in error for error in checked_body(value, 'Fun', article, require_fresh=True))


def test_first_detail_repair_cannot_replace_passing_body(tmp_path):
    initial = broken_details()
    def ask(root, key, prompt, data, validate):
        if 'review-detail-fix-' in key:
            return {'details': combined_answer()['details']}
        if '-fix-' not in key:
            return deepcopy(initial)
        changed = combined_answer()
        changed['corrected_article']['middle_en']['body'] = 'bad'
        return changed
    result = finish(tmp_path, 'News', 'c1', ART, initial['corrected_article'], [], [], ask)
    assert result['status'] == 'ready_full'
    assert result['entry'] == initial['corrected_article']
    assert result['body_repairs'] == 0


def test_detail_retry_preserves_already_valid_level(tmp_path):
    initial = broken_details()
    def ask(root, key, prompt, data, validate):
        if 'review-detail-fix-' in key:
            value = combined_answer()['details']
            value['0_easy']['why_it_matters'] = 'Replacement that was not needed.'
            return {'details': value}
        return deepcopy(initial)
    result = finish(tmp_path, 'News', 'c1', ART, initial['corrected_article'], [], [], ask)
    assert result['status'] == 'ready_full'
    assert result['details']['0_easy']['why_it_matters'] == initial['details']['0_easy']['why_it_matters']


def test_detail_syntax_failure_does_not_discard_good_body(tmp_path):
    initial = broken_details()
    tasks = []
    def ask(root, key, prompt, data, validate):
        tasks.append(key)
        if '-fix-' in key:
            raise runner.AnswerRejected('Malformed JSON after one correction')
        return deepcopy(initial)
    result = finish(tmp_path, 'News', 'c1', ART, initial['corrected_article'], [], [], ask)
    assert result['status'] == 'ready_degraded'
    assert result['entry'] == initial['corrected_article']
    assert set(result['details']) == {'0_easy'}
    assert len(tasks) == 3


def test_resume_empty_pending_answer_never_asks_initial_again(tmp_path):
    runner.write(tmp_path / 'finished-articles/News-c1.json',
                 {'phase': 'initial', 'body_repairs': 0, 'detail_repairs': 0, 'pending_value': {}})
    tasks = []
    def ask(root, key, prompt, data, validate):
        tasks.append(key)
        return combined_answer()
    result = finish(tmp_path, 'News', 'c1', ART, {}, [], [], ask)
    assert result['status'] == 'ready_full'
    assert tasks == ['review-finish-fix-News-c1']


def test_cleanup_removal_is_logged_when_other_level_needs_repair(tmp_path):
    initial = broken_details()
    initial['details']['0_easy']['keywords'].append({'term': 'absent', 'explanation': 'not in body'})
    def ask(root, key, prompt, data, validate):
        return {'details': combined_answer()['details']} if '-fix-' in key else deepcopy(initial)
    result = finish(tmp_path, 'News', 'c1', ART, initial['corrected_article'], [], [], ask)
    assert result['status'] == 'ready_full'
    assert '0_easy.keywords' in result['removed']
