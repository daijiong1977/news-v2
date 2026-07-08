"""Reorder MCQ options so the correct answer isn't always in the same slot.

Background
---------
DeepSeek generates each quiz question as {question, options:[4],
correct_answer}, where ``correct_answer`` is a string that must equal one
of ``options`` verbatim. The model has a strong positional bias — it parks
the correct answer in the same slot (empirically ~70% "B", ~0% "D"), and
nothing downstream reorders the options, so every rendered quiz answer
lands on the same letter. Kids can score 100% by always tapping B.

Fix
---
Permute each question's ``options`` list. Because ``correct_answer`` is
stored separately as a string, reordering ``options`` keeps the payload
valid — the frontend (and the PDF export) re-derive the correct index by
string match. The permutation is deterministic per (slot, question) so
re-running the pipeline doesn't churn the ordering and unit tests are
reproducible.

Call site: ``pipeline.news_rss_core.detail_enrich`` (once, right after
``filter_keywords``), which is the single choke point feeding both the web
payload and the printable PDF.
"""
from __future__ import annotations

import hashlib
import logging
import random

log = logging.getLogger("quiz-shuffle")

_MIN_OPTIONS = 2


def _perm_seed(slot_key: str, q_index: int, question_text: str, seed) -> int:
    """Deterministic 64-bit seed from stable per-question inputs."""
    key = f"{slot_key}|{q_index}|{question_text}|{seed}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def shuffle_quiz_options(details: dict, *, seed=None) -> dict:
    """Shuffle ``options`` for every quiz question in ``details`` in place.

    ``details`` maps slot keys (e.g. ``"0_easy"``) to dicts that may carry a
    ``"questions"`` list. Questions whose ``correct_answer`` does not match an
    option, or that have fewer than two options, are left untouched (a
    malformed question is a data bug, not something to silently reorder).

    Returns the same ``details`` object for convenience.
    """
    if not isinstance(details, dict):
        return details

    for slot_key, det in details.items():
        if not isinstance(det, dict):
            continue
        questions = det.get("questions")
        if not isinstance(questions, list):
            continue
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                continue
            opts = q.get("options")
            correct = q.get("correct_answer")
            if not isinstance(opts, list) or len(opts) < _MIN_OPTIONS:
                continue
            if correct not in opts:
                log.warning(
                    "[%s] q%d: correct_answer not among options — left unshuffled",
                    slot_key, i,
                )
                continue
            rng = random.Random(_perm_seed(slot_key, i, str(q.get("question", "")), seed))
            rng.shuffle(opts)  # in place; correct_answer string still matches an option

    return details
