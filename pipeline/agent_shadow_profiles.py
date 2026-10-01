"""Explicit opt-in local-only hybrid experiments; production defaults unchanged."""
HYBRID_PROFILES = {
    'batch-deepseek': ('News', 'Science', 'Fun'),
    'batch-grok-details': ('News', 'Science', 'Fun'),
    'news-deepseek': ('News',),
    'science-fun-deepseek': ('Science', 'Fun'),
}


def is_hybrid(snapshot):
    return snapshot.get('test_profile') in HYBRID_PROFILES


def is_batch(snapshot):
    return snapshot.get('test_profile') in ('batch-deepseek', 'batch-grok-details')


def uses_native_details(snapshot):
    return snapshot.get('test_profile') == 'batch-grok-details'
