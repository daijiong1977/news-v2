"""Five-draft JSON contract; no network or production changes."""
from pipeline.agent_shadow_batch import batch_prompt, batch_material
from pipeline.agent_shadow_providers import TaskRouter
from pipeline.agent_shadow import write


def test_batch_prompt_has_one_envelope_and_no_per_input_override():
    prompt = batch_prompt({'test_profile': 'source-first-deepseek'}, 'Fun')
    assert 'For EACH' not in prompt
    assert 'one entry per input article' not in prompt
    assert 'exactly min(5' in prompt
    assert 'article:null' in prompt
    assert 'No extra draft' in prompt
    assert 'body_word_bands' in prompt
    assert 'FAMILY SPORTS PREFERENCE' in prompt
    assert 'No details' in prompt
    assert 'best-to-worst order' in prompt
    assert 'positions 4-5 reserves' in prompt
    assert 'zh contains exactly headline and summary' in prompt


def test_batch_prompt_preserves_news_and_science_editorial_rules():
    news = batch_prompt({'test_profile': 'source-first-deepseek'}, 'News')
    science = batch_prompt({'test_profile': 'source-first-deepseek'}, 'Science')
    assert 'highest-importance' in news
    assert 'Do not invent hope' in news
    assert 'physics, chemistry' in science
    assert 'independent publishers' in science


def test_http_batch_parameters_are_explicit_but_native_unchanged(tmp_path):
    write(tmp_path / 'providers.json', {'roles': {'write': {
        'type': 'http', 'model': 'deepseek-chat',
        'endpoint': 'https://api.deepseek.com/chat/completions', 'key_env': 'TEST_KEY'}}})
    payload = {'model': 'native-agent', 'messages': [], 'max_tokens': 8192}
    sent = TaskRouter(tmp_path, 'rewrite-batch-Fun-8').prepare_payload(payload)
    assert sent['max_tokens'] == 16384
    assert sent['response_format'] == {'type': 'json_object'}
    assert sent['thinking'] == {'type': 'disabled'}
    assert sent['temperature'] == 0.2
    assert payload['max_tokens'] == 8192
    assert TaskRouter(tmp_path, 'review-modify-Fun-x').prepare_payload(payload) == payload


def test_batch_material_has_full_text_once_and_exact_count():
    rows = [{'id': str(i), 'importance': 1, 'article': {'body': 'original text',
             'word_count': 400, 'title': 'Story', 'paragraphs': ['original text'],
             'og_image': 'unused', '_publisher_key': 'example.org'}} for i in range(8)]
    material = batch_material('2026-10-02', 'Fun', rows)
    assert material['output_contract']['draft_count'] == 5
    assert all(r['article']['body'] == 'original text' for r in material['candidates'])
    assert all('paragraphs' not in r['article'] for r in material['candidates'])
    assert material['candidates'][0]['target_words'] == {'easy': 205, 'middle': 295}
    assert rows[0]['article']['paragraphs'] == ['original text']
