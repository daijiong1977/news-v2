-- Add feed_kind + feed_config to redesign_source_configs.
--
-- Driver: sourcefinder is promoting non-RSS candidates (DOGOnews,
-- NG Kids — Space, NG Kids — Geography). The current pipeline only
-- knows RSS at fetch time; these need an HTML-listing-page selector.
--
-- See docs/HANDOVER-from-sourcefinder-html_list.md for the contract.
--
-- Backwards-compatible: every existing row defaults to feed_kind='rss',
-- so behavior is unchanged for live sources.

ALTER TABLE redesign_source_configs
    ADD COLUMN IF NOT EXISTS feed_kind TEXT NOT NULL DEFAULT 'rss';

ALTER TABLE redesign_source_configs
    ADD COLUMN IF NOT EXISTS feed_config TEXT;  -- JSON; nullable for rss

-- Lock the values feed_kind can take. Adding a new kind requires a
-- migration AND a code update in pipeline/scraper.py:discover_article_urls.
ALTER TABLE redesign_source_configs
    DROP CONSTRAINT IF EXISTS redesign_source_configs_feed_kind_check;

ALTER TABLE redesign_source_configs
    ADD CONSTRAINT redesign_source_configs_feed_kind_check
    CHECK (feed_kind IN ('rss', 'sitemap', 'html_list'));
