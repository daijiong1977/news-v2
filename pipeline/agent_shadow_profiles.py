"""Explicit opt-in local-only hybrid experiments; production defaults unchanged."""
HYBRID_PROFILES = {
    'source-first-deepseek': ('News', 'Science', 'Fun'),
    'source-first-grok': ('News', 'Science', 'Fun'),
    'batch-deepseek': ('News', 'Science', 'Fun'),
    'batch-grok-details': ('News', 'Science', 'Fun'),
    'news-deepseek': ('News',),
    'science-fun-deepseek': ('Science', 'Fun'),
}


def is_hybrid(snapshot):
    return snapshot.get('test_profile') in HYBRID_PROFILES


def is_batch(snapshot):
    return snapshot.get('test_profile') in ('batch-deepseek', 'batch-grok-details', 'source-first-grok', 'source-first-deepseek')


def uses_native_details(snapshot):
    return snapshot.get('test_profile') in ('batch-grok-details', 'source-first-grok', 'source-first-deepseek')


def is_source_first(snapshot):
    return snapshot.get('test_profile') in ('source-first-grok', 'source-first-deepseek')


def uses_deepseek_shortlist(snapshot):
    return snapshot.get('test_profile') == 'source-first-deepseek'
