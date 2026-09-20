# 2026-09-20 — every keyword dropped when Stage 3 rejects an article

**Severity:** high
**Area:** pipeline
**Status:** fixed
**Keywords:** filter_keywords, Word Treasure, keywords, hallucinated, slot_key, source_id, enrich, stage3, empty vocabulary, articles_by_id

## Symptom

Two of the nine articles published on 2026-09-20 shipped with an **empty Word
Treasure** — the vocabulary panel rendered its title and nothing else. Spotted
on a phone by the reader: "好像 keyword 也不对".

The run log named the cause without anyone noticing it was wrong:

    [0_easy]   dropped hallucinated keywords: ['vaccine', 'Ebola', 'outbreak',
                                               'Ervebo', 'clinical trial', 'licensed']
    [2_easy]   dropped hallucinated keywords: ['artificial intelligence', 'AI tsar',
                                               'Industrial Revolution', 'GDP', 'hoax']
    [0_middle] dropped hallucinated keywords: [...]
    [2_middle] dropped hallucinated keywords: [...]

"Ebola", "vaccine" and "outbreak" were called hallucinations in a story about
an Ebola vaccination drive. All six terms went, for both levels, on both
articles — the giveaway that nothing was being matched at all.

## Root cause

`filter_keywords` (pipeline/news_rss_core.py) drops any keyword whose term
does not appear in its article's body. It found the article like this:

    articles_by_id = {a["source_id"]: a for a in rewrite_result["articles"]}
    aid = int(slot_key.rsplit("_", 1)[0])
    art = articles_by_id.get(aid, {})
    body = (art.get(f"{lvl}_en") or {}).get("body") or ""

But the slot keys it parses are **positional**, not source ids.
`_detail_enrich_input_single_level` builds them as:

    expected_keys = [f"{i}_{level}" for i in range(len(arts))]

The two agreed only while `source_id` happened to equal the position, which
is true straight out of the rewrite — `articles = [(i, w["winner"]) for i, w
in enumerate(verified)]`. Stage 3 then rejects unsafe rewrites and promotes
spares, and the survivors keep their original `source_id` while their
positions close up. From that moment:

  · a slot whose position matches a rejected article's id finds nothing,
    `body` is `""`, and every term is "not in the body" → all dropped
  · a slot that finds a *different* article validates against the wrong body

On 2026-09-20 Stage 3 rejected one News article and promoted one spare, so
News slots 0 and 2 both lost their entire vocabulary.

The invariant violated: a key and its lookup must be built from the same
thing. Here one side used position and the other used identity, and the
mismatch could only appear after attrition — which is exactly the path that
gets least attention.

Nothing caught it because dropping keywords is a *normal, expected* outcome
of this validator, so the log line reads like the system working. There was
no assertion that a slot retains at least one keyword, and no test covering
the post-attrition shape.

## Fix

Branch `fix-mobile-span`. `filter_keywords` indexes `rewrite_result["articles"]`
by position, matching how the slot keys are built, and fails open in the two
cases where validation is impossible:

  · slot position outside the article list → keep the keywords, log a warning
  · article found but its body is empty → keep the keywords, log a warning

Dropping every keyword because there was nothing to compare against is the one
outcome that is certainly wrong.

`pipeline/test_keyword_slots.py` covers the post-attrition shape (survivors
0, 2, 3 against slots 0, 1, 2), a genuinely absent term still being dropped,
and both fail-open paths.

## Prevention

When a key is generated in one place and parsed in another, both sides must
name the same thing — write the format once and reuse it, or assert the
round-trip. And a validator whose normal job is to remove things needs a floor:
"removed everything" is nearly always a bug in the validator, not the data.
