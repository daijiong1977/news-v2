# 2026-04-30 — search-level-filter-loses-cross-level-matches

**Severity:** medium
**Area:** infra (search)
**Status:** fixed
**Keywords:** search, archive-search, redesign_search_index, redesign_archive_search, tsvector, tsquery, level-filter, easy, middle, cross-level

## Symptom

Admin reported "the search function suddenly stopped working" with
"returns nothing" on news.6ray.com. Specific reproduction: a user
at level='Tree' (= search level='middle') typing terms like
**ocean**, **climate**, **math** got 0 results — even though
articles on those topics exist in the archive.

Curl reproduction (level=middle):

| query | count |
|---|---|
| `news`     | 3 |
| `kids`     | 3 |
| `space`    | 3 |
| `ocean`    | **0** ← bug |
| `climate`  | 1 |
| `math`     | 0 |
| (no level) | always > 0 for the same queries |

Every story has rows at BOTH `easy` AND `middle` levels (63 stories
× 2 = 126 rows). Yet level-filtered searches missed many topics.

## Root cause

`redesign_archive_search` Postgres function had a hard level filter
in its WHERE clause:

```sql
WHERE s.doc_tsv @@ search.tsq
  AND (p_category IS NULL OR s.category = p_category)
  AND (p_level    IS NULL OR s.level    = p_level)   -- THIS LINE
```

The pipeline rewriter produces an easy version and a middle version
with **substantively different vocabulary** (the easy rewrite
deliberately swaps in shorter / simpler words). Concrete example
(story `2026-04-28-news-3`):

- **easy** body uses "ocean" — *"connects the Persian Gulf to the
  rest of the **ocean**"*
- **middle** body uses "Gulf of Oman" / "waterway" / "channel" /
  "strait" instead — never says "ocean"

So `doc_tsv` (a per-row tsvector) at level=middle does NOT contain
the lexeme `ocean`, even though the SAME story's level=easy row
does. With the strict level filter, a user at level=middle searching
"ocean" gets 0 hits — even though the article they want is right
there at level=middle, just talking about it with different words.

The level filter was protective by design (avoid showing easy
results to a Tree reader and vice versa), but the side effect of
vocabulary divergence between levels makes it actively harmful for
discovery.

## Fix

Migration `supabase/migrations/20260430_search_cross_level.sql`:

- Replace `redesign_archive_search` to **drop the level filter**.
  Search now matches across all levels.
- Edge fn `supabase/functions/archive-search/index.ts` already
  dedupes by `story_id` after the function call (keeps first row
  per story by date-DESC + rank-DESC ranking), so the dedup
  invariant is preserved.
- The level parameter is kept on the function signature for
  backward compatibility but ignored; future work can use it as
  a ranking-preference signal (prefer matches at user's level
  when both match) without breaking callers.

After fix (curl reproduction at level=middle):

| query | before | after |
|---|---|---|
| `ocean`   | 0 | 1 |
| `climate` | 1 | 1 |
| `math`    | 0 | 1 |
| `news`    | 3 | 3 |

The article-detail click handler always loads the article at the
user's preferred level (`baseArticle.level === 'Sprout' ? 'easy' :
'middle'`), so even if the search RESULT card displays the easy
version's title (because that's where the lexical match happened),
clicking opens the user's level. UX-correct.

## Invariant

`redesign_archive_search` MUST search across all levels for any
story. The level filter was removed deliberately on 2026-04-30 —
re-introducing it (e.g., as a "performance optimisation") will
re-introduce the cross-level vocabulary loss.

If level-aware ranking is added later, it should affect ORDER BY
(prefer user's preferred level when both match), not WHERE
(must not exclude rows). Validation: searching common cross-level
disjoint terms ("ocean", "math", "climate") at any level should
return ≥1 result if that story exists in the archive.

## Pinning test

After deploying:

```bash
set -a; source .env; set +a
for q in ocean math climate space "robot dog"; do
    n=$(curl -sS -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
        "$SUPABASE_URL/functions/v1/archive-search?q=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$q")&level=middle&limit=3" \
        | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',-1))")
    echo "  $q  count=$n"
done
```

Expected: at least `ocean`, `math`, `climate`, `space` should each
return ≥1. If any returns 0, search has regressed (likely the level
filter was reintroduced somewhere upstream).

## Related

- `pipeline/search_index.py` — builds the index after each daily
  pipeline run. Indexes both levels per story; healthy.
- `website/home.jsx :: SearchPage` — UI; correctly maps user's
  level (Sprout → easy, Tree → middle) and passes it to the
  edge fn. No change here.
- `supabase/functions/archive-search/index.ts` — already does
  dedup by `story_id`; no change.
