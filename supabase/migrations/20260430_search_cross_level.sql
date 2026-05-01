-- Drop the level filter from redesign_archive_search.
--
-- See docs/bugs/2026-04-30-search-level-filter-loses-cross-level-matches.md
-- for the full root cause. Short version: the easy and middle versions
-- of the SAME story use deliberately different vocabulary (rewriter
-- simplifies for easy). Filtering by level at the WHERE clause loses
-- cross-level matches — searching "ocean" at level=middle gets 0
-- results even though the same story (which the user could read at
-- middle) uses "ocean" in its easy version.
--
-- Fix: search across all levels. Edge fn `archive-search` already
-- dedupes by story_id post-query. The article-detail click handler
-- in website/article.jsx loads the user's preferred level regardless
-- of which level produced the search match, so UX stays correct.
--
-- The p_level parameter is KEPT on the signature (callers send it,
-- backward-compat) but ignored. Future work can use it as a
-- ranking-preference signal in ORDER BY — but never as a WHERE
-- filter, see invariant in the bug record.

CREATE OR REPLACE FUNCTION public.redesign_archive_search(
    q text,
    p_limit integer DEFAULT 10,
    p_category text DEFAULT NULL,
    p_level text DEFAULT NULL
)
RETURNS TABLE (
    story_id text,
    published_date date,
    category text,
    level text,
    title text,
    snippet text,
    image_url text,
    source_name text,
    rank real
)
LANGUAGE sql
STABLE
AS $function$
  WITH search AS (
    SELECT websearch_to_tsquery('english', coalesce(q, '')) AS tsq
  )
  SELECT
    s.story_id,
    s.published_date,
    s.category,
    s.level,
    s.title,
    ts_headline(
      'english',
      coalesce(s.summary, ''),
      search.tsq,
      'StartSel=<b>, StopSel=</b>, MaxFragments=2, MaxWords=24, MinWords=10'
    ) AS snippet,
    s.image_url,
    s.source_name,
    ts_rank(s.doc_tsv, search.tsq) AS rank
  FROM redesign_search_index s, search
  WHERE s.doc_tsv @@ search.tsq
    AND (p_category IS NULL OR s.category = p_category)
    -- INTENTIONAL: NO p_level filter. See bug record above.
    -- p_level is accepted but ignored; could become an ORDER BY
    -- preference later (prefer user's level when both match) but
    -- never a WHERE exclusion.
  ORDER BY s.published_date DESC, rank DESC
  LIMIT p_limit;
$function$;

COMMENT ON FUNCTION public.redesign_archive_search(text, integer, text, text) IS
'Archive full-text search over redesign_search_index. Searches across ALL levels (easy + middle); edge fn dedupes by story_id post-query. p_level is accepted for backward compat but ignored — see migration 20260430_search_cross_level.sql for the cross-level-vocabulary rationale.';
