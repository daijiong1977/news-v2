import pytest
from pipeline.agent_shadow_lengths import rewrite_band, acceptance_band
from pipeline.agent_shadow_editor import validate_rewrite


@pytest.mark.parametrize('category,source_words,level,target,accepted', [
    ('News', 500, 'easy', (140, 270), (119, 310)),
    ('News', 500, 'middle', (300, 410), (255, 471)),
    ('Science', 500, 'easy', (140, 320), (119, 368)),
    ('Science', 500, 'middle', (300, 520), (255, 598)),
    ('Fun', 250, 'easy', (120, 220), (102, 253)),
    ('Fun', 250, 'middle', (180, 350), (153, 402)),
    ('Fun', 500, 'middle', (180, 410), (153, 471)),
])
def test_tolerance_boundaries_keep_generation_targets(category, source_words, level, target, accepted):
    assert rewrite_band(level, category, source_words) == target
    assert acceptance_band(level, category, source_words) == accepted
    entry = {'source_id': 0, 'zh': {'headline': '标题', 'summary': '摘要'}}
    for name in ('easy', 'middle'):
        lo, hi = rewrite_band(name, category, source_words)
        entry[name + '_en'] = {'headline': 'Story', 'card_summary': 'A story', 'body': 'word ' * ((lo + hi) // 2)}
    for count in (accepted[0], accepted[1]):
        entry[level + '_en']['body'] = 'word ' * count
        assert validate_rewrite({'articles': [entry]}, category, source_words) == []
    for count in (accepted[0] - 1, accepted[1] + 1):
        entry[level + '_en']['body'] = 'word ' * count
        assert validate_rewrite({'articles': [entry]}, category, source_words)
