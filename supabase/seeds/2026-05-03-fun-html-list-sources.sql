-- Seed the 3 html_list candidates from sourcefinder into Fun category.
--
-- Inserted with enabled=false so they're staged but stay OUT of the
-- pipeline rotation until PR #17 (feed_kind dispatcher) is merged
-- and deployed. After merge, flip them on with:
--
--   UPDATE redesign_source_configs SET enabled = true
--   WHERE category = 'Fun' AND feed_kind = 'html_list';
--
-- Empirical wordcounts (per docs/HANDOVER-from-sourcefinder-html_list.md):
--   - DOGOnews: ~334 wc avg
--   - NG Kids — Space: ~247 wc avg (some shorter)
--   - NG Kids — Geography: ~682 wc avg

INSERT INTO redesign_source_configs
    (category, name, rss_url, feed_kind, feed_config,
     flow, max_to_vet, min_body_words, priority,
     enabled, is_backup, state, notes)
VALUES
    ('Fun', 'DOGOnews',
     'https://www.dogonews.com/',
     'html_list',
     '{"article_selector": "article a[href*=\"/2026\"], article a[href*=\"/2025\"]", "exclude_pattern": "#comment"}',
     'full', 10, 200, 6,
     false, false, 'live',
     'html_list source from sourcefinder 2026-05-03; flip enabled=true after PR #17 deploy'),

    ('Fun', 'NG Kids — Space',
     'https://kids.nationalgeographic.com/space/',
     'html_list',
     '{"article_selector": "a[href*=\"/space/\"][href*=\"/article/\"]"}',
     'full', 10, 200, 7,
     false, false, 'live',
     'html_list source from sourcefinder 2026-05-03; min_body=200 (some pieces ~247 wc)'),

    ('Fun', 'NG Kids — Geography',
     'https://kids.nationalgeographic.com/geography/',
     'html_list',
     '{"article_selector": "a[href*=\"/geography/\"]", "exclude_pattern": "/games/|/videos/"}',
     'full', 10, 300, 8,
     false, false, 'live',
     'html_list source from sourcefinder 2026-05-03; ~682 wc avg, comfortable margin');

-- Verification: after running this seed, ensure 3 rows exist with feed_kind='html_list'
-- in Fun, all enabled=false:
--
--   SELECT name, feed_kind, enabled, priority FROM redesign_source_configs
--   WHERE category = 'Fun' AND feed_kind = 'html_list' ORDER BY priority;
--
-- After PR #17 merges + deploys, smoke-test ONE source first:
--
--   UPDATE redesign_source_configs SET enabled = true WHERE name = 'DOGOnews';
--
-- Watch the next pipeline run's logs for "[DOGOnews] Phase A: flow=full feed_kind=html_list"
-- + "[DOGOnews]  entries: N" with N >= 3. If green, flip the other two:
--
--   UPDATE redesign_source_configs SET enabled = true
--   WHERE category = 'Fun' AND feed_kind = 'html_list';
