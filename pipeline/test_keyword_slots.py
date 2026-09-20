"""Keyword validation must survive Stage-3 attrition.

Run: python -m pipeline.test_keyword_slots   (also works under pytest)
"""
from __future__ import annotations

from pipeline import news_rss_core as core


def _art(sid, easy_body, middle_body="middle body text"):
    return {"source_id": sid,
            "easy_en": {"body": easy_body},
            "middle_en": {"body": middle_body}}


def test_slot_keys_are_positional_not_source_ids():
    """After Stage 3 rejects an article, the survivors keep their original
    source_ids but the enrich slot keys are rebuilt as 0..n-1. Looking up by
    source_id then hit the wrong article — or none — and dropped every keyword.
    Bug: docs/bugs/2026-09-20-keywords-dropped-by-slot-id-mismatch.md"""
    # rewrite produced ids 0,1,2,3; Stage 3 rejected 1 — survivors keep 0,2,3
    rewrite = {"articles": [
        _art(0, "Congo began giving the Ebola vaccine to health workers."),
        _art(2, "Trump wants an AI Force led by an AI tsar."),
        _art(3, "Orcas smashed a sunfish to pieces."),
    ]}
    details = {
        "0_easy": {"keywords": [{"term": "Ebola"}, {"term": "vaccine"}]},
        "1_easy": {"keywords": [{"term": "AI tsar"}, {"term": "AI Force"}]},
        "2_easy": {"keywords": [{"term": "orcas"}, {"term": "sunfish"}]},
    }
    core.filter_keywords(details, rewrite)
    assert [k["term"] for k in details["0_easy"]["keywords"]] == ["Ebola", "vaccine"]
    assert [k["term"] for k in details["1_easy"]["keywords"]] == ["AI tsar", "AI Force"]
    assert [k["term"] for k in details["2_easy"]["keywords"]] == ["orcas", "sunfish"]


def test_a_genuinely_absent_term_is_still_dropped():
    rewrite = {"articles": [_art(0, "Congo began giving the Ebola vaccine.")]}
    details = {"0_easy": {"keywords": [{"term": "Ebola"}, {"term": "quantum entanglement"}]}}
    core.filter_keywords(details, rewrite)
    assert [k["term"] for k in details["0_easy"]["keywords"]] == ["Ebola"]


def test_missing_body_keeps_keywords_rather_than_dropping_all():
    """Validating against an empty body marks every term a hallucination. That
    is the one outcome that is certainly wrong."""
    rewrite = {"articles": [_art(0, "")]}
    details = {"0_easy": {"keywords": [{"term": "Ebola"}, {"term": "vaccine"}]}}
    core.filter_keywords(details, rewrite)
    assert len(details["0_easy"]["keywords"]) == 2


def test_slot_beyond_the_article_list_keeps_its_keywords():
    rewrite = {"articles": [_art(0, "Congo began giving the Ebola vaccine.")]}
    details = {"7_easy": {"keywords": [{"term": "Ebola"}]}}
    core.filter_keywords(details, rewrite)
    assert len(details["7_easy"]["keywords"]) == 1


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok  ", fn.__name__)
    print(f"\n{len(fns)} passed")
