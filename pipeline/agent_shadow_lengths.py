"""Shadow length overrides; do not change the live pipeline's policy."""
from .wordcount_policy import body_band


def original_band(category):
    # 2026-09-30: short Fun stories should not be padded or discarded for length alone.
    return (180, 1200) if category == 'Fun' else (350, 1500) if category == 'Science' else (350, 1200)


def rewrite_band(level, category, source_words):
    if category == 'Fun':
        if 180 <= source_words < 350:
            return (120, 220) if level == 'easy' else (180, 350)
        if level == 'middle':
            return (180, 410)
    return body_band(level, category=category, source_word_count=source_words)


def rewrite_rules(category, source_words):
    if category != 'Fun':
        return ''
    easy = rewrite_band('easy', category, source_words)
    middle = rewrite_band('middle', category, source_words)
    return (f'\nSHADOW FUN LENGTH OVERRIDE: easy body {easy[0]}-{easy[1]} words; '
            f'middle body {middle[0]}-{middle[1]} words. These ranges override earlier '
            'length instructions. Prefer a concise complete story; do not pad with '
            'invented facts or repetitive background. All fact and safety rules still apply.')
