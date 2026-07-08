"""Unit tests for quiz option shuffling.

Fixes the "correct answer is almost always B" bias: DeepSeek emits MCQ
options with the right answer in a fixed position, and nothing downstream
reorders them, so every quiz answer lands on the same letter.

Pure logic — no network, no env, no DeepSeek. Runnable two ways:
    python -m pipeline.test_quiz_shuffle      # standalone
    pytest pipeline/test_quiz_shuffle.py      # under pytest
"""
from __future__ import annotations

import collections

from pipeline.quiz_shuffle import shuffle_quiz_options


def _question(correct_idx: int, n: int = 4, label: str = "Q") -> dict:
    opts = [f"opt{i}" for i in range(n)]
    return {"question": label, "options": list(opts), "correct_answer": opts[correct_idx]}


def _details_all_correct_at(idx: int, count: int) -> dict:
    """One slot, `count` questions, each with the correct answer at `idx`."""
    return {"0_middle": {"questions": [_question(idx, label=f"Q{i}") for i in range(count)]}}


def test_preserves_option_set_and_correct_answer():
    d = {"0_middle": {"questions": [_question(1)]}}
    ca_before = d["0_middle"]["questions"][0]["correct_answer"]
    opts_before = set(d["0_middle"]["questions"][0]["options"])

    shuffle_quiz_options(d)

    q = d["0_middle"]["questions"][0]
    assert set(q["options"]) == opts_before          # same 4 option strings
    assert q["correct_answer"] == ca_before          # correct_answer string untouched
    assert q["correct_answer"] in q["options"]        # still resolvable by the frontend


def test_breaks_positional_bias():
    d = _details_all_correct_at(1, 40)   # all correct at "B" before shuffle
    shuffle_quiz_options(d)

    positions = [q["options"].index(q["correct_answer"]) for q in d["0_middle"]["questions"]]
    counts = collections.Counter(positions)
    assert len(counts) >= 3, f"expected spread across >=3 positions, got {counts}"
    assert max(counts.values()) <= len(positions) * 0.6, f"too skewed: {counts}"


def test_deterministic_across_runs():
    d1 = _details_all_correct_at(1, 10)
    d2 = _details_all_correct_at(1, 10)
    shuffle_quiz_options(d1)
    shuffle_quiz_options(d2)
    seq1 = [q["options"] for q in d1["0_middle"]["questions"]]
    seq2 = [q["options"] for q in d2["0_middle"]["questions"]]
    assert seq1 == seq2   # same input -> same output (no reshuffle churn on re-runs)


def test_malformed_questions_left_untouched():
    # correct_answer not among options -> leave order alone, do not crash
    q_bad = {"question": "x", "options": ["a", "b", "c", "d"], "correct_answer": "zzz"}
    d = {"0_easy": {"questions": [q_bad]}}
    shuffle_quiz_options(d)
    assert d["0_easy"]["questions"][0]["options"] == ["a", "b", "c", "d"]

    # fewer than 2 options -> nothing to shuffle
    q_thin = {"question": "y", "options": ["a"], "correct_answer": "a"}
    d2 = {"0_easy": {"questions": [q_thin]}}
    shuffle_quiz_options(d2)
    assert d2["0_easy"]["questions"][0]["options"] == ["a"]


def test_slots_without_questions_are_ignored():
    d = {"0_easy": {"keywords": [{"term": "x"}]}}   # no "questions" key
    shuffle_quiz_options(d)                          # must not raise
    assert "questions" not in d["0_easy"]


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
