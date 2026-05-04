-- supabase/seeds/2026-05-04-cadence-seed.sql
-- 39 sources across News (7) + Science (11) + Fun (21).
-- ON CONFLICT (name) DO UPDATE — many rows already exist; this brings
-- them to spec values without duplicating.
-- UNIQUE(name) constraint comes from Task 1's migration.

-- News (7)
INSERT INTO redesign_source_configs
  (category, name, rss_url, feed_kind, flow, max_to_vet, min_body_words,
   priority, cadence_days, enabled, is_backup, state)
VALUES
  ('News', 'PBS NewsHour',  'https://www.pbs.org/newshour/feeds/rss/headlines',
   'rss', 'full', 6, 500, 1, 1, true, false, 'live'),
  ('News', 'NPR World',     'https://feeds.npr.org/1003/rss.xml',
   'rss', 'light', 10, 300, 2, 1, true, false, 'live'),
  ('News', 'Al Jazeera',    'https://www.aljazeera.com/xml/rss/all.xml',
   'rss', 'full', 10, 300, 3, 1, true, false, 'live'),
  ('News', 'BBC News',      'http://feeds.bbci.co.uk/news/rss.xml',
   'rss', 'full', 10, 300, 4, 1, true, false, 'live'),
  ('News', 'ScienceDaily Top Technology', 'https://www.sciencedaily.com/rss/top/technology.xml',
   'rss', 'full', 10, 300, 5, 1, true, false, 'live'),
  ('News', 'ScienceDaily Strange & Offbeat', 'https://www.sciencedaily.com/rss/strange_offbeat.xml',
   'rss', 'full', 10, 300, 6, 2, true, false, 'live'),
  ('News', 'ScienceDaily Most Popular', 'https://www.sciencedaily.com/rss/most_popular.xml',
   'rss', 'full', 10, 300, 7, 2, true, false, 'live')
ON CONFLICT (name) DO UPDATE SET
  category=EXCLUDED.category,
  rss_url=EXCLUDED.rss_url,
  feed_kind=EXCLUDED.feed_kind,
  flow=EXCLUDED.flow,
  max_to_vet=EXCLUDED.max_to_vet,
  min_body_words=EXCLUDED.min_body_words,
  priority=EXCLUDED.priority,
  cadence_days=EXCLUDED.cadence_days,
  enabled=EXCLUDED.enabled,
  is_backup=EXCLUDED.is_backup,
  state=EXCLUDED.state;

-- Science (11)
INSERT INTO redesign_source_configs
  (category, name, rss_url, feed_kind, flow, max_to_vet, min_body_words,
   priority, cadence_days, enabled, is_backup, state)
VALUES
  ('Science', 'ScienceDaily All', 'https://www.sciencedaily.com/rss/all.xml',
   'rss', 'full', 10, 300, 1, 1, true, false, 'live'),
  ('Science', 'Science News Explores', 'https://www.snexplores.org/feed',
   'rss', 'full', 10, 300, 2, 2, true, false, 'live'),
  ('Science', 'MIT Tech Review', 'https://www.technologyreview.com/feed/',
   'rss', 'full', 10, 300, 3, 7, true, false, 'live'),
  ('Science', 'NPR Health', 'https://feeds.npr.org/1027/rss.xml',
   'rss', 'light', 10, 300, 3, 3, true, false, 'live'),
  ('Science', 'Space.com', 'https://www.space.com/feeds/all',
   'rss', 'full', 10, 300, 3, 1, true, false, 'live'),
  ('Science', 'Physics World', 'https://physicsworld.com/feed/',
   'rss', 'full', 10, 300, 3, 7, true, false, 'live'),
  ('Science', 'ScienceDaily Top Environment', 'https://www.sciencedaily.com/rss/top/environment.xml',
   'rss', 'full', 10, 300, 3, 1, true, false, 'live'),
  ('Science', 'IEEE Spectrum', 'https://spectrum.ieee.org/feeds/feed.rss',
   'rss', 'full', 10, 300, 3, 5, true, false, 'live'),
  ('Science', 'Smithsonian Science-Nature', 'https://www.smithsonianmag.com/rss/science-nature/',
   'rss', 'full', 10, 300, 3, 7, true, false, 'live'),
  ('Science', 'NASA News', 'https://www.nasa.gov/news-release/feed/',
   'rss', 'full', 10, 300, 4, 3, true, false, 'live'),
  ('Science', 'Popular Science', 'https://www.popsci.com/feed',
   'rss', 'full', 10, 300, 5, 3, true, false, 'live')
ON CONFLICT (name) DO UPDATE SET
  category=EXCLUDED.category,
  rss_url=EXCLUDED.rss_url,
  feed_kind=EXCLUDED.feed_kind,
  flow=EXCLUDED.flow,
  max_to_vet=EXCLUDED.max_to_vet,
  min_body_words=EXCLUDED.min_body_words,
  priority=EXCLUDED.priority,
  cadence_days=EXCLUDED.cadence_days,
  enabled=EXCLUDED.enabled,
  is_backup=EXCLUDED.is_backup,
  state=EXCLUDED.state;

-- Fun (21)
INSERT INTO redesign_source_configs
  (category, name, rss_url, feed_kind, feed_config, flow, max_to_vet,
   min_body_words, priority, cadence_days, enabled, is_backup, state)
VALUES
  ('Fun', 'DOGOnews', 'https://www.dogonews.com/', 'html_list',
   '{"article_selector": "article a[href*=\"/2026\"], article a[href*=\"/2025\"]", "exclude_pattern": "#comment"}',
   'full', 10, 200, 1, 1, true, false, 'live'),
  ('Fun', 'NG Kids — Space', 'https://kids.nationalgeographic.com/space/', 'html_list',
   '{"article_selector": "a[href*=\"/space/\"][href*=\"/article/\"]"}',
   'full', 10, 200, 2, 7, true, false, 'live'),
  ('Fun', 'NG Kids — Geography', 'https://kids.nationalgeographic.com/geography/', 'html_list',
   '{"article_selector": "a[href*=\"/geography/\"]", "exclude_pattern": "/games/|/videos/"}',
   'full', 10, 300, 3, 7, true, false, 'live'),
  ('Fun', 'BBC Tennis',  'https://feeds.bbci.co.uk/sport/tennis/rss.xml',
   'rss', NULL, 'full', 10, 150, 1, 1, true, false, 'live'),
  ('Fun', 'SwimSwam',    'https://swimswam.com/feed/',
   'rss', NULL, 'full', 10, 300, 1, 2, true, false, 'live'),
  ('Fun', 'Wired Gear',  'https://www.wired.com/feed/category/gear/latest/rss',
   'rss', NULL, 'full', 10, 300, 1, 2, true, false, 'live'),
  ('Fun', 'Popular Mechanics', 'https://www.popularmechanics.com/rss/all.xml',
   'rss', NULL, 'full', 10, 300, 2, 2, true, false, 'live'),
  ('Fun', 'MIT News',    'https://news.mit.edu/rss/feed',
   'rss', NULL, 'full', 10, 300, 3, 7, true, false, 'live'),
  ('Fun', 'Variety',     'https://variety.com/feed/',
   'rss', NULL, 'full', 10, 300, 1, 3, true, false, 'live'),
  ('Fun', '/Film',       'https://www.slashfilm.com/feed/',
   'rss', NULL, 'full', 10, 300, 2, 2, true, false, 'live'),
  ('Fun', 'IndieWire',   'https://www.indiewire.com/feed/',
   'rss', NULL, 'full', 10, 300, 3, 2, true, false, 'live'),
  ('Fun', 'Polygon',     'https://www.polygon.com/rss/index.xml',
   'rss', NULL, 'full', 10, 300, 1, 7, true, false, 'live'),
  ('Fun', 'Kotaku',      'https://kotaku.com/rss',
   'rss', NULL, 'full', 10, 300, 2, 7, true, false, 'live'),
  ('Fun', 'Smithsonian Arts', 'https://www.smithsonianmag.com/rss/arts-culture/',
   'rss', NULL, 'full', 10, 300, 1, 7, true, false, 'live'),
  ('Fun', 'Smithsonian History', 'https://www.smithsonianmag.com/rss/history/',
   'rss', NULL, 'full', 10, 300, 1, 7, true, false, 'live'),
  ('Fun', 'Live Science','https://www.livescience.com/feeds/all',
   'rss', NULL, 'full', 10, 300, 2, 1, true, false, 'live'),
  ('Fun', 'Colossal',    'https://www.thisiscolossal.com/feed/',
   'rss', NULL, 'full', 10, 300, 2, 7, true, false, 'live'),
  ('Fun', 'Hyperallergic', 'https://hyperallergic.com/feed/',
   'rss', NULL, 'full', 10, 300, 3, 7, true, false, 'live'),
  ('Fun', 'NPR Music',   'https://feeds.npr.org/1039/rss.xml',
   'rss', NULL, 'light', 10, 300, 1, 1, true, false, 'live'),
  ('Fun', 'Rolling Stone Music', 'https://www.rollingstone.com/music/feed/',
   'rss', NULL, 'full', 10, 300, 2, 2, true, false, 'live'),
  ('Fun', 'Billboard',   'https://www.billboard.com/feed/',
   'rss', NULL, 'full', 10, 300, 3, 2, true, false, 'live')
ON CONFLICT (name) DO UPDATE SET
  category=EXCLUDED.category,
  rss_url=EXCLUDED.rss_url,
  feed_kind=EXCLUDED.feed_kind,
  feed_config=EXCLUDED.feed_config,
  flow=EXCLUDED.flow,
  max_to_vet=EXCLUDED.max_to_vet,
  min_body_words=EXCLUDED.min_body_words,
  priority=EXCLUDED.priority,
  cadence_days=EXCLUDED.cadence_days,
  enabled=EXCLUDED.enabled,
  is_backup=EXCLUDED.is_backup,
  state=EXCLUDED.state;

-- Drop legacy cross-category duplicate backup rows. Smithsonian
-- Science-Nature is in Science as primary above; NPR Music backup
-- duplicates the Fun NPR Music primary above.
--
-- Also drop two orphan test stubs from early development:
--   snai — abbrev of Science News AI; never made it into the curated
--          source list but lingered as enabled=true (was inflating
--          Science count to 12 instead of the spec's 11).
--   upi  — UPI top-news feed; enabled=false but still cruft.
-- Neither is in the spec's 39-source list.
DELETE FROM redesign_source_configs
WHERE name IN (
  'NPR Music (backup)',
  'Smithsonian Science-Nature (Fun backup)',
  'snai',
  'upi'
);
