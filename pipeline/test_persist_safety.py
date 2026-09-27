"""The story audit row must describe the final child-facing rewrite."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline import full_round as fr
from pipeline import supabase_io


class _EmptyDelete:
    def delete(self): return self
    def eq(self, *args): return self
    def gt(self, *args): return self
    def execute(self): return SimpleNamespace(data=[])


class _Client:
    def table(self, name): return _EmptyDelete()


def _persist(story, variant):
    rows = []
    old_insert, old_client = fr.insert_story, supabase_io.client
    fr.insert_story = lambda row: rows.append(row) or "test-id"
    supabase_io.client = lambda: _Client()
    try:
        count = fr.persist_to_supabase({"Fun": [story]}, {"Fun": {0: variant}},
                                       "2026-09-26", "test-run")
    finally:
        fr.insert_story, supabase_io.client = old_insert, old_client
    assert count == 1
    return rows[0]


def test_persists_independent_rewrite_safety_instead_of_original():
    story = {"source": SimpleNamespace(name="Mixed"),
             "winner": {"title": "Sport", "link": "https://example.org/sport",
                        "_vet_info": {"safety": {"violence": 0, "total": 0,
                                                 "verdict": "SAFE"}}}}
    variant = {"_safety_eval": {"verdict": "PASS", "scores": {
        "violence": 1, "fear": 2, "sexual": 0, "substance": 0,
        "language": 0, "adult_themes": 0, "distress": 0, "bias": 0}}}
    row = _persist(story, variant)
    assert row["safety_violence"] == 1
    assert row["safety_fear"] == 2
    assert row["safety_total"] == 3
    assert row["safety_verdict"] == "SAFE"


def test_legacy_row_still_uses_source_vet_without_final_eval():
    story = {"source": SimpleNamespace(name="Source"),
             "winner": {"title": "Title", "link": "https://example.org/story",
                        "_vet_info": {"safety": {"fear": 2, "total": 2,
                                                 "verdict": "CAUTION"}}}}
    row = _persist(story, {})
    assert row["safety_fear"] == 2
    assert row["safety_total"] == 2
    assert row["safety_verdict"] == "CAUTION"


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")


if __name__ == "__main__":
    _run_all()
