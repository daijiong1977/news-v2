"""Shadow length overrides; do not change the live pipeline's policy."""
from .wordcount_policy import body_band


def original_band(category):
    # 2026-09-30: short Fun stories should not be padded or discarded for length alone.
    return (180, 1200) if category == 'Fun' else (350, 1500) if category == 'Science' else (350, 2000)


def rewrite_band(level, category, source_words):
    if category == 'Fun':
        if 180 <= source_words < 350:
            return (120, 220) if level == 'easy' else (180, 350)
        if level == 'middle':
            return (180, 410)
    return body_band(level, category=category, source_word_count=source_words)


def acceptance_band(level, category, source_words):
    """Accept integer body counts within 15% of targets, without widening targets."""
    lo, hi = rewrite_band(level, category, source_words)
    return ((lo * 85 + 99) // 100, hi * 115 // 100)


WORD_TOLERANCE_RULE = ('English body_word_bands are writing targets. Python accepts '
    '15% below the lower bound and 15% above the upper bound (integer counts). '
    'Do not repair or reject a body solely for length within this tolerance. '
    'This does not relax source length, Chinese, safety, structure or image rules.')


def rewrite_rules(category, source_words):
    if category != 'Fun':
        return ''
    easy = rewrite_band('easy', category, source_words)
    middle = rewrite_band('middle', category, source_words)
    return (f'\nSHADOW FUN LENGTH OVERRIDE: easy body {easy[0]}-{easy[1]} words; '
            f'middle body {middle[0]}-{middle[1]} words. These ranges override earlier '
            'length instructions. Prefer a concise complete story; do not pad with '
            'invented facts or repetitive background. All fact and safety rules still apply. '
            + WORD_TOLERANCE_RULE)
