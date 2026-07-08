"""Tests for the P1 reliability batch (2026-07-08).

Covers the deterministic parts of:
  1. Checkpoint JSONB round-trip restoring int dict keys (RESUME_FROM=enrich/
     persist raised KeyError because {0: art} came back as {"0": art}).
  2. quiz_shuffle fuzzy-matching a near-miss correct_answer (casefold/strip/
     trailing-dot) and DROPPING truly unmatched questions instead of shipping
     an unanswerable MCQ (frontend maps unmatched → "A").
  3. insert_run retrying transient Supabase failures instead of silently
     returning None (which disabled ALL persistence for the day).
  4. stamp_shipped_sources extracted from persist_to_supabase (so it can run
     after deploy success, not before).

Run: python -m pipeline.test_p1_reliability   (also works under pytest)
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from pipeline import checkpoints
from pipeline.quiz_shuffle import shuffle_quiz_options


# ── 1. checkpoint round-trip: int keys survive ──

def test_checkpoint_roundtrip_restores_int_keys():
    data = {"News": {0: "a", 1: "b"}, "meta": {"0_easy": "slotkey-stays-str"}}
    wire = json.loads(json.dumps(checkpoints._walk_to_jsonable(data)))
    assert set(wire["News"].keys()) == {"0", "1"}          # JSONB stringified
    back = checkpoints._walk_from_jsonable(wire, {})
    assert set(back["News"].keys()) == {0, 1}              # coerced back
    assert back["News"][0] == "a"
    assert set(back["meta"].keys()) == {"0_easy"}          # mixed keys untouched


# ── 2. quiz fuzzy-match / drop ──

def test_quiz_fuzzy_match_rewrites_correct_answer():
    q = {"question": "Q", "options": ["The blue whale", "A shark", "A crab", "An eel"],
         "correct_answer": "  the Blue Whale. "}     # case/space/dot near-miss
    d = {"0_easy": {"questions": [q]}}
    shuffle_quiz_options(d)
    qq = d["0_easy"]["questions"][0]
    assert qq["correct_answer"] in qq["options"]           # now resolvable
    assert qq["correct_answer"] == "The blue whale"        # rewritten verbatim


def test_quiz_unmatched_question_dropped():
    good = {"question": "G", "options": ["a", "b", "c", "d"], "correct_answer": "b"}
    bad = {"question": "B", "options": ["a", "b", "c", "d"], "correct_answer": "zzz"}
    d = {"0_easy": {"questions": [good, bad]}}
    shuffle_quiz_options(d)
    remaining = d["0_easy"]["questions"]
    assert len(remaining) == 1 and remaining[0]["question"] == "G"


# ── 3. insert_run retries transient failures ──

def test_insert_run_retries_then_succeeds():
    from pipeline import supabase_io
    attempts = {"n": 0}

    class FakeQuery:
        def insert(self, row): return self
        def execute(self):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError("transient 5xx")
            return SimpleNamespace(data=[{"id": "run-xyz"}])

    class FakeClient:
        def table(self, name): return FakeQuery()

    orig_client = supabase_io.client
    orig_sleep = supabase_io.time.sleep
    supabase_io.client = lambda: FakeClient()
    supabase_io.time.sleep = lambda s: None          # no real backoff in tests
    try:
        rid = supabase_io.insert_run({"run_date": "2026-07-08", "status": "running"})
    finally:
        supabase_io.client = orig_client
        supabase_io.time.sleep = orig_sleep

    assert rid == "run-xyz"
    assert attempts["n"] == 3                        # failed twice, then won


# ── 4. shipped-source stamping is its own post-deploy function ──

def test_stamp_shipped_sources_exists_and_noops_on_empty():
    from pipeline import full_round
    # No stories → no client() call → must return without touching the network.
    full_round.stamp_shipped_sources({})
    full_round.stamp_shipped_sources({"News": []})


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
