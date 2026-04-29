# 2026-04-28 — keyword-stem-mismatch

**Severity:** medium
**Area:** pipeline
**Status:** fixed
**Keywords:** filter_keywords, stemmer, suffix-rewrite, inflection, keyword_in_body, false-rejection

## Symptom

Articles with valid keyword content were being filtered out because
keywords like "negotiation" weren't matching body forms like
"negotiating". Pipeline kept emitting "keyword not in body" rejection
messages for stories that visibly DID discuss the term.

## Root cause

`pipeline/news_rss_core.py:keyword_in_body` did boundary-aware
substring matching only. Keywords are emitted in dictionary form
("negotiation", "deal", "approval") but the body uses inflections
("negotiating", "deals", "approving"). No stemmer.

A first attempt at suffix-stripping produced inconsistent stems
across keyword and body forms — e.g. "negotiation" stripped to
"negotia" while "negotiating" stripped to "negotiat" — so the
intersection was empty and the bug got worse, not better. (Caught
by Copilot CLI cross-check before merge.)

## Fix

- `pipeline/news_rss_core.py` — three-tier matcher:
    - Tier 1: boundary-aware substring with `(?<![A-Za-z])` lookbehind
      for single-word keywords (so "gas" doesn't match "Vegas").
    - Tier 2: legacy suffix regex (kept for backward compat).
    - Tier 3: stem-set intersection using suffix-REWRITE rules:

      ```python
      _STEM_RULES = (("ation", "at"), ("ies", "y"), ("acy", ""),
                      ("atic", ""), ("ing", ""), ("ed", ""), ("e", ""),
                      ...)
      ```

      Both keyword and body word are reduced to a SET of all rule
      applications. Match if the sets intersect.
- `filter_keywords` now caches `body_lc + body_stems` once per slot
  via `_body_word_stem_index()` and `_keyword_in_body_with_index()`.
  Reused by `pack_and_upload._scrub_detail_payload_bytes()` so it
  doesn't rebuild the index per article.

15 test cases all pass including the negative case (`gas` vs
`Vegas`).

## Invariant

Keyword-in-body matching MUST be inflection-tolerant: a keyword in
its base form MUST match a body inflection of that keyword
(plural, -ing, -ed, -ation/-at, -ies/-y, etc.) AND MUST NOT match
unrelated words that happen to share a stem prefix. If the stemmer
is replaced, the test cases in `pipeline/tests/test_keyword_match.py`
(when added) should cover these patterns.

The stemmer MUST be symmetric: applying the rules to both keyword
and body word and intersecting, NEVER asymmetrically stripping one
side.

## Pinning test

Pipeline-level: a unit test exercising the 15 known cases (positive:
"negotiation"↔"negotiating"; negative: "gas"↔"Vegas"). Currently the
cases are documented in the suffix-rewrite design discussion; if a
unit test file exists later, add it under
`pipeline/tests/test_keyword_match.py`.

Operational: monitor pipeline logs for "keyword not in body" line
counts. A sudden spike on a content-rich day signals a stemmer
regression.

## Related

- `2026-04-28-news-source-diversity.md` — shipped in the same
  pipeline-side fix batch but unrelated.
- Cross-check workflow (memory: feedback_crosscheck.md) caught the
  asymmetric-stripping mistake before merge — this is one of the
  load-bearing reasons cross-check is non-optional for any
  algorithm-level change.
