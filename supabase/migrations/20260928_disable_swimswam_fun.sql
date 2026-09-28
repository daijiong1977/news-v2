-- Retire only the verified SwimSwam Fun row (id 220). Preserve past source
-- attribution and cadence/probe history for audit and reversible recovery.
-- BBC Swimming (id 365) remains enabled.
UPDATE redesign_source_configs
SET enabled = false,
    notes = concat_ws(
      ' · ',
      nullif(notes, ''),
      '2026-09-28: retired from Fun; BBC Swimming retained for swimming news'
    )
WHERE id = 220
  AND category = 'Fun'
  AND name = 'SwimSwam'
  AND rss_url = 'https://swimswam.com/feed/'
  AND enabled = true;
