-- Apply only after the bounded-RSS-fetch code has reached production.
-- The row may already exist as disabled staging data from the source audit.
INSERT INTO redesign_source_configs
  (category, name, rss_url, feed_kind, flow, max_to_vet, min_body_words,
   priority, cadence_days, enabled, is_backup, state, notes)
VALUES
  ('News', 'CBC World', 'https://www.cbc.ca/webfeed/rss/rss-world',
   'rss', 'full', 10, 300, 5, 1, true, false, 'live',
   'Added 2026-09-27: independent fifth News source; normal Jev, category, duplicate and child-safety gates apply')
ON CONFLICT (name) DO UPDATE SET
  category = EXCLUDED.category,
  rss_url = EXCLUDED.rss_url,
  feed_kind = EXCLUDED.feed_kind,
  flow = EXCLUDED.flow,
  max_to_vet = EXCLUDED.max_to_vet,
  min_body_words = EXCLUDED.min_body_words,
  priority = EXCLUDED.priority,
  cadence_days = EXCLUDED.cadence_days,
  enabled = EXCLUDED.enabled,
  is_backup = EXCLUDED.is_backup,
  state = EXCLUDED.state;
