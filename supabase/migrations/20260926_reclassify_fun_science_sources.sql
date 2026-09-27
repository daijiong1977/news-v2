-- Sources whose primary editorial identity is science/technology must not
-- compete for Fun slots. Mixed sources such as DOGOnews and Wired Gear stay in
-- Fun and are protected by the per-article category-fit gate in pipeline/jev_rank.py.

UPDATE redesign_source_configs
SET category = 'Science',
    notes = concat_ws(
      ' · ',
      nullif(notes, ''),
      '2026-09-26: moved from Fun to Science after category-overlap audit'
    )
WHERE name IN (
  'Live Science',
  'NG Kids — Space',
  'MIT News',
  'Popular Mechanics'
);
