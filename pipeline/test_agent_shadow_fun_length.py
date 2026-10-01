"""Shadow-only Fun short-story regression; production bands stay unchanged."""
import pytest
from pipeline.agent_shadow_editor import validate_rewrite
from pipeline.test_agent_shadow_review_fixes import draft


@pytest.mark.parametrize('source_words,middle_words', [(280, 180), (280, 247), (500, 191), (500, 291)])
def test_fun_short_middle_survives(source_words, middle_words):
    value = draft()
    value['middle_en']['body'] = ' '.join(['word'] * middle_words)
    assert validate_rewrite({'articles': [value]}, 'Fun', source_words) == []


def test_fun_179_words_still_rejected():
    value = draft()
    value['middle_en']['body'] = ' '.join(['word'] * 179)
    assert validate_rewrite({'articles': [value]}, 'Fun', 500)


def test_production_fun_band_unchanged():
    from pipeline.wordcount_policy import body_band
    assert body_band('middle', category='Fun', source_word_count=280) == (250, 350)
    assert body_band('middle', category='Fun', source_word_count=500) == (300, 410)


def test_source_and_prompt_bands_agree():
    from pipeline.agent_shadow_lengths import original_band, rewrite_rules, rewrite_band
    assert original_band('Fun') == (180, 1200)
    assert rewrite_band('easy', 'Fun', 180) == (120, 220)
    assert 'middle body 180-350 words' in rewrite_rules('Fun', 180)
    assert 'middle body 180-410 words' in rewrite_rules('Fun', 500)
    assert rewrite_rules('Science', 500) == ''
    assert original_band('Science') == (350, 1500)
    assert original_band('News') == (350, 1200)


def test_modifier_accepts_fun_180_without_extra_rewrite(tmp_path):
    from pipeline.agent_shadow_modifier import modify
    value = draft()
    value['middle_en']['body'] = ' '.join(['word'] * 180)
    def answer(root, key, prompt, material, validate):
        assert 'middle body 180-350 words' in prompt
        result = {'corrected_article': value}
        assert validate(result) == []
        return result
    _, corrected, _ = modify(tmp_path, 'Fun', 'c1', {'word_count': 280, 'body': 'source'},
                             value, {}, [], [], answer, lambda value: [])
    assert corrected == value


@pytest.mark.parametrize('category,words', [('News', 180), ('Science', 180), ('Fun', 411)])
def test_other_categories_and_fun_ceiling_not_relaxed(category, words):
    value = draft()
    value['middle_en']['body'] = ' '.join(['word'] * words)
    assert validate_rewrite({'articles': [value]}, category, 500)
