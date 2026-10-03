"""Shared shadow control signals, identical under import and python -m."""


class AnswerRejected(RuntimeError):
    """Bounded answer repair exhausted; callers drop/replace this item."""


def correction_kind(errors):
    """Recognize old persisted parse errors as format repairs on resume."""
    return 'format' if any(str(e).startswith('Invalid task answer:') for e in errors) else 'content'
