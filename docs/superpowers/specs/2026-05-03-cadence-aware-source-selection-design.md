# Cadence-Aware Source Selection — Design Spec

**Date**: 2026-05-03
**Status**: Draft (pending user review)
**Owner**: Jiong + Claude

## Problem statement

The daily pipeline picks 3 articles per category (News / Science / Fun)
from a static set of RSS / html_list sources. Two coupled problems:

1. **Hardcoded source lists.** Source selection lives in
   `pipeline/news_sources.py`, `pipeline/science_sources.py`,
   `pipeline/fun_sources.py` — Python literals, weekday-keyed dicts.
   Activating a new source requires editing code + opening a PR.
   The PR-#17 html_list rows in `redesign_source_configs` are
   inert today because no live code path reads from the DB.
2. **No cadence awareness.** Some sources update weekly or monthly
   (NG Kids — Geography, Smithsonian Arts). Vetting them daily costs
   a reasoner LLM call per (re-vetted) article. Worse, the same
   stale brief gets re-evaluated every day until it ages out of
   the freshness window.

We need source selection that is (a) DB-driven so admin can rotate
without code changes, and (b) aware of each source's natural update
cadence so weekly sources are vetted weekly, not daily.

## Goals (v1)

- Source selection reads from `redesign_source_configs` for ALL three
  categories (News / Science / Fun). Hardcoded `*_sources.py` modules
  are deleted.
- Each source carries a `cadence_days` integer separate from
  `priority`. The two columns express orthogonal axes:
  - `priority`: when ties happen, which source wins (importance/order).
  - `cadence_days`: how many days to "rest" between picks.
- Day-D selection picks the most-overdue eligible sources first;
  fills any shortfall with the closest-to-eligible sources. Same
  algorithm for all 3 categories.
- Initial cadence values are seeded from already-known/observed
  values (sourcefinder has been recording publish-date gaps for
  weeks). Manual override is supported for sources we want to pin.
- Weekday-rotation special cases (Sunday=games, Friday=arts, etc.)
  are removed. Variety emerges from cadence-driven rotation across
  the evergreen pool, not from calendar pinning.

## Non-goals (v1)

- **Auto-tuning of `cadence_days`.** Will be a separate spec. v1 ships
  with manual seed values from sourcefinder's observations; auto-tune
  is a weekly cron that updates `cadence_days` based on observed RSS
  gap medians, reserved for v1.1.
- **Backup-source rotation.** Today's pipeline has a "primary fails →
  swap in backup" path (`run_source_with_backups`). v1 keeps that
  unchanged — backups live on the same table flagged `is_backup=true`,
  and the dispatcher logic in `*_aggregate.py` is untouched.
- **Cross-category source reuse.** Each source still belongs to
  exactly one category. No multi-category rows.

## Background — current code path

```
full_round.main() (active)
  ├── news_sources.enabled_sources()      → hardcoded SOURCES list
  ├── science_sources.todays_enabled_sources() → SCIENCE_ALWAYS + SCIENCE_WEEKDAY[wd]
  ├── fun_sources.todays_enabled_sources()     → WEEKDAY_SOURCES[wd]
  └── for each cat: aggregate_category(cat, sources, backups, runner)
         └── for each source: phase_a → fetch_source_entries → vet → ...
```

Source counts today (de-duplicated; e.g. BBC Tennis appears in 3 Fun weekdays
but is one source):
| File | Unique sources | Notes |
|---|---:|---|
| `news_sources.py` | 7 | 7 evergreen primaries (no weekday rotation) |
| `science_sources.py` | 11 | 2 always-on + 7 weekday rotation + 2 backup |
| `fun_sources.py` | 18 | 3 BBC Tennis dupes + 1 Pop Mech dupe collapse |
| html_list rows in DB | 3 | DOGOnews + NG Kids × 2 (already inserted) |
| **Total unique** | **39** | After v1 migration, all in `redesign_source_configs` |

`db_config.load_sources(cat)` exists and reads the DB but is only
called for checkpoint hydration today — it doesn't drive selection.

`pipeline/full_round.py` has a parallel `main_mega()` (line 1256)
that IS DB-driven; it's not wired up to the workflow. We won't
revive it — the active `main()` flow gets retrofitted in place.

## Schema changes

```sql
ALTER TABLE redesign_source_configs
  ADD COLUMN cadence_days   INTEGER NOT NULL DEFAULT 1
    CHECK (cadence_days BETWEEN 1 AND 60),
  ADD COLUMN next_pickup_at DATE;

-- next_pickup_at is updated by the pipeline at end-of-run for every
-- source that contributed a winning article. Computed as:
--   next_pickup_at = run_date + cadence_days
--
-- NULL means "never used" (or freshly enabled). Never-used sources
-- are eligible immediately and sort to the top of Step 2.

-- Optional convenience index for the eligibility scan:
CREATE INDEX redesign_source_configs_pickup_eligible_idx
  ON redesign_source_configs (category, next_pickup_at NULLS FIRST)
  WHERE enabled = true AND is_backup = false;
```

### Existing columns kept as-is

| Column | Role under v1 |
|---|---|
| `priority` | Tie-break only when multiple sources are eligible the same day. Lower = earlier. Default 1. |
| `last_used_at` | Stamped when source contributes a winning article. Drives the LRU tiebreak. |
| `enabled`, `is_backup`, `state` | Filters before eligibility check. Unchanged. |
| `flow`, `max_to_vet`, `min_body_words` | Per-source tuning, untouched. |
| `feed_kind`, `feed_config` | Already shipped in PR #17. |

## Algorithm — Day-D selection (per category)

Identical for News, Science, Fun. Run once per category.

```
Step 1 — Build eligible pool
  ELIGIBLE = sources WHERE
    category    = X
    AND enabled = true
    AND is_backup = false
    AND state IN ('live', NULL)
    AND (next_pickup_at IS NULL OR next_pickup_at <= D)

Step 2 — Sort eligible
  ORDER BY
    next_pickup_at  ASC NULLS FIRST,    -- most overdue first; never-used first
    priority        ASC,                -- ties: low priority number wins
    last_used_at    ASC NULLS FIRST     -- secondary tiebreak: LRU

Step 3 — Take top N
  picked = ELIGIBLE.take(N)             -- N=3 today, configurable per cat

Step 4 — Fill shortfall with closest-to-eligible
  IF picked.length < N:
    REMAINING = sources WHERE
      category = X AND enabled AND not is_backup
      AND next_pickup_at > D
      ORDER BY next_pickup_at ASC, priority ASC
    picked += REMAINING.take(N - picked.length)

Step 5 — Stamp at end-of-run
  for src in picked:
    if src contributed a winning article in today's bundle:
      src.last_used_at   = D
      src.next_pickup_at = D + INTERVAL src.cadence_days
    else:
      # not stamped — stays eligible for tomorrow
      pass
```

### Why "winning article" for the stamp, not "picked"

If a source is picked but its candidates are all rejected (vet
verdict REJECT, or no images, or under wordcount), nothing ships
from it. Stamping it as "used" would silently sleep it for
`cadence_days` even though we got zero value. v1 stamps only on
winning contribution — sources whose candidates are all rejected
remain eligible tomorrow.

The hook: `full_round.main()` already has a `last_used_at` stamp
loop at line 1004-1023 that runs after persist. It iterates
`stories_by_cat[cat][i].source.name` — only sources whose stories
actually shipped. Add `next_pickup_at` to the same UPDATE.

### Worked example — Fun on 2026-05-03 (Sunday)

After the v1 migration runs and seeds cadence:

| Source | priority | cadence | last_used_at | next_pickup_at | Status |
|---|---:|---:|---|---|---|
| BBC Tennis | 1 | 1 | 2026-05-02 | 2026-05-03 | ✅ ready (today) |
| SwimSwam | 1 | 2 | 2026-04-29 | 2026-05-01 | ✅ ready (overdue 2d) |
| Popular Mechanics | 2 | 2 | 2026-05-01 | 2026-05-03 | ✅ ready (today) |
| Variety | 1 | 3 | 2026-05-02 | 2026-05-05 | 🛌 sleeping |
| DOGOnews | 1 | 1 | NULL | NULL | ✅ never used |
| NG Kids — Space | 2 | 7 | NULL | NULL | ✅ never used |
| NG Kids — Geography | 3 | 7 | NULL | NULL | ✅ never used |
| Polygon | 1 | 7 | 2026-04-26 | 2026-05-03 | ✅ ready (today) |
| Kotaku | 2 | 7 | 2026-04-26 | 2026-05-03 | ✅ ready (today) |

Step 2 sort (next_pickup ASC NULLS FIRST, priority ASC, last_used ASC NULLS FIRST):
1. DOGOnews (NULL, p=1)
2. NG Kids — Space (NULL, p=2)
3. NG Kids — Geography (NULL, p=3)
4. SwimSwam (2026-05-01, p=1)
5. Polygon (2026-05-03, p=1)
6. BBC Tennis (2026-05-03, p=1, last_used=2026-05-02)
7. Popular Mechanics (2026-05-03, p=2)
8. Kotaku (2026-05-03, p=2)

Step 3 picks top 3 → DOGOnews + NG Kids — Space + NG Kids — Geography.
Step 5 stamps them → next_pickup of DOGOnews = 2026-05-04, NG Kids = 2026-05-10.

Tomorrow (5/4): DOGOnews ready again (cadence=1). NG Kids resting until 5/10.
The pool has plenty of others — SwimSwam, Polygon, Kotaku, Popular Mechanics, BBC Tennis all ready.

## Cadence values — initial seed (v1)

Source: sourcefinder's `daily-verify-*.json` outputs from the past 3 weeks.

| Category | Source | priority | cadence_days | Notes |
|---|---|---:|---:|---|
| News | PBS NewsHour | 1 | 1 | Hourly RSS, premium |
| News | NPR World | 2 | 1 | Hourly |
| News | Al Jazeera | 3 | 1 | Daily-ish |
| News | BBC News | 4 | 1 | Hourly |
| News | ScienceDaily Top Technology | 5 | 1 | Daily |
| News | ScienceDaily Strange & Offbeat | 6 | 2 | Most days |
| News | ScienceDaily Most Popular | 7 | 2 | Most days |
| Science | ScienceDaily All | 1 | 1 | Daily (always-on) |
| Science | Science News Explores | 2 | 2 | ~2-3 articles/wk (always-on) |
| Science | MIT Tech Review | 3 | 7 | Weekly (was Mon-only) |
| Science | NPR Health | 3 | 3 | Some days (was Tue-only) |
| Science | Space.com | 3 | 1 | Daily (was Wed-only) |
| Science | Physics World | 3 | 7 | Weekly (was Thu-only) |
| Science | ScienceDaily Top Environment | 3 | 1 | Daily (was Fri-only) |
| Science | IEEE Spectrum | 3 | 5 | ~5-day median (was Sat-only) |
| Science | Smithsonian Science-Nature | 3 | 7 | Weekly (was Sun-only) |
| Science | NASA News | 4 | 3 | Currently backup; see open question 7 below |
| Science | Popular Science | 5 | 3 | Currently backup; see open question 7 below |
| Fun | DOGOnews | 1 | 1 | Daily kids news (new from sourcefinder) |
| Fun | NG Kids — Space | 2 | 7 | Weekly (new from sourcefinder) |
| Fun | NG Kids — Geography | 3 | 7 | Weekly (new from sourcefinder) |
| Fun | BBC Tennis | 1 | 1 | Daily during seasons |
| Fun | SwimSwam | 1 | 2 | ~2-3/wk |
| Fun | Wired Gear | 1 | 2 | Most days |
| Fun | Popular Mechanics | 2 | 2 | Most days |
| Fun | MIT News | 3 | 7 | Weekly |
| Fun | Variety | 1 | 3 | Slower than expected |
| Fun | /Film | 2 | 2 | Most days |
| Fun | IndieWire | 3 | 2 | Most days |
| Fun | Polygon | 1 | 7 | Weekly cadence in our use |
| Fun | Kotaku | 2 | 7 | Weekly cadence in our use |
| Fun | Smithsonian Arts | 1 | 7 | Weekly (was Fri-only) |
| Fun | Smithsonian History | 1 | 7 | Weekly (was Sat-only) |
| Fun | Live Science | 2 | 1 | Daily (was Sat-only Fun) |
| Fun | Colossal | 2 | 7 | ~Weekly |
| Fun | Hyperallergic | 3 | 7 | Weekly |
| Fun | NPR Music | 1 | 1 | Daily during season |
| Fun | Rolling Stone Music | 2 | 2 | Most days |
| Fun | Billboard | 3 | 2 | Most days |

Final cadence_days will be cross-checked against sourcefinder's
verified observations during migration. Where sourcefinder has
strong signal it overrides the table above; where it has none we
use the table.

A source whose verified cadence is unknown defaults to
`cadence_days=1` (daily), the conservative choice — over-vetting
is wasteful but safe; under-vetting risks missing fresh content.

## Migration plan

Order matters — if the code switch ships before the data is in
the DB, the pipeline picks zero sources and fails.

1. **Apply migration** — add columns + index.
2. **Seed `redesign_source_configs`** — INSERT every source from
   `*_sources.py` modules with cadence_days set per the table above.
   Many rows already exist from PR #17 + earlier seeding; use
   `INSERT ... ON CONFLICT (name, category) DO UPDATE SET ...`
   to bring stale rows up to date.
3. **Verify** — `SELECT category, count(*) FROM redesign_source_configs
   WHERE enabled GROUP BY category` matches expected per-category
   counts (News=7, Science=11, Fun=21 — total ≥ 39).
4. **Modify `db_config.load_sources(category)`** — implement
   the 5-step algorithm. Returns a list of `NewsSource` instances
   ordered by Step 2.
5. **Modify `db_config.load_backup_sources(category)`** — pull
   `is_backup=true` rows for the category. Same shape.
6. **Modify `full_round.main()`** lines 1083-1085 — replace
   `news_sources()` / `science_sources()` / `fun_sources()` with
   `db_config.load_sources("News" / "Science" / "Fun")`. Same for
   backup helpers.
7. **Modify `full_round.main()` line 1004-1023** — extend the
   per-source `last_used_at` stamp to also set `next_pickup_at`.
8. **One pipeline dry-run** — confirm 3-per-category picks work,
   no hardcoded sources referenced. Verify telemetry shows the
   expected source mix.
9. **Decommission** — delete `*_sources.py` SOURCES literals.
   Keep the `NewsSource` dataclass; it's the in-memory type.
   Leave the empty modules with deprecation notice for one cycle
   in case anything else imports them, then remove next sprint.

The migration should be a single PR. Reverting the code change
without reverting the seed leaves the DB rows in place — harmless.
Reverting both is a clean rollback.

## Code touch points

| File | Change | LOC |
|---|---|---:|
| `supabase/migrations/20260504_cadence_aware_sources.sql` | new | ~30 |
| `supabase/seeds/2026-05-04-cadence-seed.sql` | new (39 ON CONFLICT INSERTs) | ~130 |
| `pipeline/db_config.py` | rewrite `load_sources` (5-step), add `load_backup_sources` | ~80 |
| `pipeline/full_round.py` | replace 3 source-loader calls + extend stamp loop | ~20 |
| `pipeline/news_sources.py` | empty (keep `NewsSource` only) | -90 |
| `pipeline/science_sources.py` | empty (keep dataclass) | -100 |
| `pipeline/fun_sources.py` | empty (keep dataclass) | -150 |
| Tests | offline test for `load_sources` algorithm | ~80 |

Estimated net change: ~+160 LOC, -340 LOC, **-180 net**. Real
content is the seed SQL + the algorithm + tests.

## Risks / open questions

1. **Cadence drift** — without auto-tuning (deferred to v1.1),
   if a source's actual cadence drifts (e.g., NPR Music goes
   from daily to weekly during a slow news week), our
   `cadence_days` becomes stale. Mitigation: weekly review of
   `redesign_runs.telemetry` for "candidates: 0" warnings;
   reactively bump cadence on observed misses.
2. **Step 4 fill behavior** — if a category has 0 eligible
   sources today (everyone resting), we fill from "closest"
   sources. That source gets re-stamped on use, extending its
   cadence further. Slight risk of running off the cadence
   plan if this happens often. Acceptable — it should be rare,
   and the alternative (skipping the category for a day) is worse.
3. **Migration race** — if step 6 (code switch) ships before
   step 2 (seed), pipeline picks 0 sources. Mitigation: PR
   stages migration → seed → verify → code in one commit;
   verify in CI before deploy. The PR is reversible — code
   without seed is the failure mode, NOT seed without code.
4. **`fun_sources.py` decommission** — reviewing imports first;
   only `full_round.py` should reference these modules. A grep
   will confirm before deletion.
5. **Backups column duality** — `is_backup` flag on
   `redesign_source_configs` already separates primary vs
   backup. Keeping both `load_sources` (primary only) and
   `load_backup_sources` (backup only) is the cleanest mapping.
6. **Stamp idempotency** — if the pipeline ever runs twice on
   the same day (manual rerun + watchdog retry), the stamp
   loop runs twice. Setting `next_pickup_at = run_date +
   cadence_days` is idempotent (same input → same output)
   regardless of how many times it runs. ✓
7. **Backup-vs-primary status of NASA News / Popular Science
   / Smithsonian backups** — these were `is_backup=true`. Under
   cadence-aware scheduling, "primary sleeps" replaces the old
   "primary fails" trigger for backup activation. Two paths:
   (a) Keep them as backups, only used when Step 4 fill returns
       fewer than N. The aggregate_category backup-swap stays.
   (b) Promote to primaries with conservative cadence (3-7 days),
       drop backups concept entirely.
   v1 default: **(a)** — preserve current backup behavior, less
   blast radius. Discuss before moving to (b).

## Out of scope (future specs)

- **v1.1 — Auto-tune cadence**: weekly cron that pulls each
  source's RSS, computes median pub-date gap from last 10
  items, writes back to `cadence_days` (clamp 1-30). Triggered
  by Monday 06:00 UTC schedule. Skipped for sources flagged
  `cadence_locked=true` (a future column).
- **v1.2 — Multi-pick per source**: today the pipeline picks
  ONE article per source (then runs the curator across the
  full pool). If a source has multiple fresh articles, we
  could request 2-3 picks and let the curator choose across.
  Out of scope here; might be useful when cadence-driven
  shortfalls happen.
- **Cross-day source pinning** — useful when an editor wants
  to mark "use this article tomorrow no matter what". Future
  feature, not part of the algorithm.

## Acceptance criteria

- [ ] Migration applies cleanly on prod Supabase.
- [ ] Seed populates ≥ 35 rows across 3 categories.
- [ ] `db_config.load_sources("Fun")` returns 3 sources with
      DOGOnews + NG Kids — Space + NG Kids — Geography on the
      first run after seed (NULL `next_pickup_at` sorts first).
- [ ] Offline tests for `load_sources` cover: never-used sort,
      overdue sort, fill-from-closest, priority tiebreak.
- [ ] One pipeline dry-run completes successfully with 3
      stories per category and no reference to hardcoded
      `*_sources` modules in the run log.
- [ ] After the dry-run, the picked sources have updated
      `next_pickup_at = run_date + cadence_days` in the DB.
- [ ] Subsequent dry-run picks DIFFERENT sources (cadence
      kicked in) and again 3 stories per category.

## References

- PR #17 — `feed_kind` + `feed_config` columns (already merged,
  enables html_list ingestion at fetch time)
- `docs/HANDOVER-from-sourcefinder-html_list.md` — sourcefinder's
  empirical observations on source cadence (informs the seed)
- `docs/superpowers/specs/2026-04-27-source-engine-design.md` —
  the broader source-engine vision (this spec is one slice of it)
- `pipeline/full_round.py:1004-1023` — existing `last_used_at`
  stamp loop (extension point for `next_pickup_at`)
- `pipeline/db_config.py:116` — existing `load_sources` (rewrite
  target)
