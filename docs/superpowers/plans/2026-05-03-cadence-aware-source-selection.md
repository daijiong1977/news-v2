# Cadence-Aware Source Selection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch the daily pipeline from hardcoded `*_sources.py` lists to DB-driven source selection with cadence-aware scheduling. Same algorithm for News, Science, Fun. Sources sleep for `cadence_days` after a winning contribution; never-used and overdue sources are picked first.

**Architecture:** Add 2 columns to `redesign_source_configs` (`cadence_days`, `next_pickup_at`). Rewrite `db_config.load_sources` with the 5-step algorithm. Replace 3 calls in `full_round.main()`. Drop the backup-pool concept — folded into primaries with conservative cadence. Same-PR deletion of hardcoded sources (no transition window).

**Tech Stack:** Postgres (Supabase), Python 3.11, pytest-style smoke scripts.

**Spec:** `docs/superpowers/specs/2026-05-03-cadence-aware-source-selection-design.md`

---

## File structure

| Path | Action | Responsibility |
|---|---|---|
| `supabase/migrations/20260504_cadence_aware_sources.sql` | NEW | Add `cadence_days` + `next_pickup_at` + index |
| `supabase/seeds/2026-05-04-cadence-seed.sql` | NEW | 39 ON CONFLICT INSERTs covering News (7) + Science (11) + Fun (21) |
| `pipeline/db_config.py` | MODIFY | Rewrite `load_sources` with 5-step algorithm; drop `load_backup_sources` |
| `pipeline/news_aggregate.py` | MODIFY | Drop `backup` arg from `run_source_with_backups`; rename → `run_source` |
| `pipeline/science_aggregate.py` | MODIFY | Same as above |
| `pipeline/fun_aggregate.py` | MODIFY | Same as above |
| `pipeline/full_round.py` | MODIFY | Lines 1083-1085: replace 3 source loaders. Lines 1004-1023: extend stamp loop with `next_pickup_at`. |
| `pipeline/news_sources.py` | DELETE-CONTENTS | Delete `SOURCES`, `enabled_sources`, `backup_sources`. Keep `NewsSource` dataclass only. |
| `pipeline/science_sources.py` | DELETE-CONTENTS | Same — keep nothing besides imports. |
| `pipeline/fun_sources.py` | DELETE-CONTENTS | Same. |
| `pipeline/test_load_sources.py` | NEW | Offline algorithm tests (8 cases) |

---

## Task 1: Schema migration

**Files:**
- Create: `supabase/migrations/20260504_cadence_aware_sources.sql`

- [ ] **Step 1: Write migration**

```sql
-- supabase/migrations/20260504_cadence_aware_sources.sql
ALTER TABLE redesign_source_configs
  ADD COLUMN IF NOT EXISTS cadence_days INTEGER NOT NULL DEFAULT 1
    CHECK (cadence_days BETWEEN 1 AND 60),
  ADD COLUMN IF NOT EXISTS next_pickup_at DATE;

CREATE INDEX IF NOT EXISTS redesign_source_configs_pickup_eligible_idx
  ON redesign_source_configs (category, next_pickup_at NULLS FIRST)
  WHERE enabled = true;

-- Verified pre-migration: no duplicate names exist in production.
-- Adding UNIQUE so the seed in Task 2 can use ON CONFLICT (name).
ALTER TABLE redesign_source_configs
  ADD CONSTRAINT redesign_source_configs_name_unique UNIQUE (name);
```

- [ ] **Step 2: Apply via Supabase MCP**

```
mcp__claude_ai_Supabase__apply_migration
  name: cadence_aware_sources
  query: <contents of file above>
```

- [ ] **Step 3: Verify**

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'redesign_source_configs'
  AND column_name IN ('cadence_days', 'next_pickup_at');
```

Expected: `cadence_days INTEGER default '1'`, `next_pickup_at DATE default NULL`.

```sql
SELECT count(*) FROM redesign_source_configs WHERE cadence_days = 1;
```

Expected: count = total existing rows (default backfilled all of them).

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/20260504_cadence_aware_sources.sql
git commit -m "feat(sources): add cadence_days + next_pickup_at columns"
```

---

## Task 2: Seed cadence values

**Files:**
- Create: `supabase/seeds/2026-05-04-cadence-seed.sql`

- [ ] **Step 1: Write seed file**

```sql
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
  -- 3 already-inserted html_list rows (DOGOnews, NG Kids x 2)
  -- already in DB from PR #17. ON CONFLICT updates cadence/priority.
  ('Fun', 'DOGOnews', 'https://www.dogonews.com/', 'html_list',
   '{"article_selector": "article a[href*=\"/2026\"], article a[href*=\"/2025\"]", "exclude_pattern": "#comment"}',
   'full', 10, 200, 1, 1, true, false, 'live'),
  ('Fun', 'NG Kids — Space', 'https://kids.nationalgeographic.com/space/', 'html_list',
   '{"article_selector": "a[href*=\"/space/\"][href*=\"/article/\"]"}',
   'full', 10, 200, 2, 7, true, false, 'live'),
  ('Fun', 'NG Kids — Geography', 'https://kids.nationalgeographic.com/geography/', 'html_list',
   '{"article_selector": "a[href*=\"/geography/\"]", "exclude_pattern": "/games/|/videos/"}',
   'full', 10, 300, 3, 7, true, false, 'live'),
  -- 18 RSS sources from fun_sources.py
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

-- Drop the duplicate cross-category Fun backups left from old code.
-- Smithsonian Science-Nature is in Science as primary (above);
-- NPR Music backup duplicates the Fun NPR Music primary (above).
DELETE FROM redesign_source_configs
WHERE name IN ('NPR Music (backup)', 'Smithsonian Science-Nature (Fun backup)');
```

- [ ] **Step 2: Apply via Supabase MCP**

```
mcp__claude_ai_Supabase__execute_sql
  query: <contents above>
```

- [ ] **Step 3: Verify counts**

```sql
SELECT category, count(*) AS n
FROM redesign_source_configs
WHERE enabled = true
GROUP BY category
ORDER BY category;
```

Expected: News=7, Science=11, Fun=21. Total enabled = 39.

```sql
SELECT category, name, priority, cadence_days
FROM redesign_source_configs
WHERE enabled = true
ORDER BY category, priority, cadence_days, name;
```

Spot-check: DOGOnews cadence=1, NG Kids cadence=7, IEEE Spectrum cadence=5.

- [ ] **Step 4: Commit**

```bash
git add supabase/seeds/2026-05-04-cadence-seed.sql
git commit -m "chore(sources): seed cadence_days for 39 production sources"
```

---

## Task 3: Offline tests for `load_sources` algorithm

**Files:**
- Create: `pipeline/test_load_sources.py`

- [ ] **Step 1: Write failing tests**

```python
"""Offline algorithm tests for db_config.load_sources cadence-aware path.

Run: python -m pipeline.test_load_sources

Patches db_config.client to return synthetic rows; never hits the real DB.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from . import db_config


def _row(name, *, cat="Fun", priority=1, cadence_days=1,
         enabled=True, is_backup=False, last_used=None,
         next_pickup=None, state="live"):
    return {
        "id": hash(name) & 0xFFFF, "name": name, "category": cat,
        "rss_url": f"https://example.com/{name}",
        "feed_kind": "rss", "feed_config": None,
        "flow": "full", "max_to_vet": 10, "min_body_words": 300,
        "priority": priority, "cadence_days": cadence_days,
        "enabled": enabled, "is_backup": is_backup,
        "last_used_at": last_used, "next_pickup_at": next_pickup,
        "state": state, "notes": "",
    }


def _patch_rows(rows):
    """Return a context manager that makes db_config.client() return these rows."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value.data = rows
    db_config._src_cache = None  # bypass cache
    return patch.object(db_config, "client", return_value=sb)


def _names(srcs):
    return [s.name for s in srcs]


def test_never_used_sorts_first():
    """NULL next_pickup_at + NULL last_used_at sort to top of eligible pool."""
    today = date(2026, 5, 3)
    rows = [
        _row("Old",   priority=1, last_used="2026-04-29", next_pickup="2026-05-01"),
        _row("New",   priority=2, last_used=None,         next_pickup=None),
        _row("Older", priority=1, last_used="2026-04-26", next_pickup="2026-04-28"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=3)
    assert _names(out) == ["New", "Older", "Old"], _names(out)
    print("PASS: never-used sorts before any dated entry")


def test_eligible_only_picked():
    """Only sources with next_pickup_at <= today are in the eligible pool."""
    today = date(2026, 5, 3)
    rows = [
        _row("Today",      priority=1, next_pickup="2026-05-03"),
        _row("Tomorrow",   priority=1, next_pickup="2026-05-04"),  # NOT eligible
        _row("Yesterday",  priority=2, next_pickup="2026-05-02"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=3)
    # Step 3 takes 2 eligible, Step 4 fills with Tomorrow
    assert _names(out) == ["Yesterday", "Today", "Tomorrow"], _names(out)
    print("PASS: Step 4 fills shortfall from closest non-eligible")


def test_priority_tiebreak_within_eligible():
    """Same next_pickup, low priority wins."""
    today = date(2026, 5, 3)
    rows = [
        _row("LowPri",  priority=2, next_pickup="2026-05-03"),
        _row("HighPri", priority=1, next_pickup="2026-05-03"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=2)
    assert _names(out) == ["HighPri", "LowPri"], _names(out)
    print("PASS: priority tiebreak within same next_pickup")


def test_lru_secondary_tiebreak():
    """Same next_pickup AND priority, oldest last_used wins."""
    today = date(2026, 5, 3)
    rows = [
        _row("Recent", priority=1, next_pickup="2026-05-03",
             last_used="2026-05-02"),
        _row("Old",    priority=1, next_pickup="2026-05-03",
             last_used="2026-04-26"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=2)
    assert _names(out) == ["Old", "Recent"], _names(out)
    print("PASS: LRU tiebreak — oldest last_used wins")


def test_disabled_excluded():
    """enabled=false sources never appear."""
    today = date(2026, 5, 3)
    rows = [
        _row("Active",  enabled=True),
        _row("Disabled", enabled=False),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=3)
    assert _names(out) == ["Active"], _names(out)
    print("PASS: disabled sources excluded")


def test_is_backup_now_included():
    """Q1=b: is_backup is no longer a filter. Backup rows participate."""
    today = date(2026, 5, 3)
    rows = [
        _row("Primary", is_backup=False, priority=1),
        _row("Backup",  is_backup=True,  priority=2),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=2)
    assert _names(out) == ["Primary", "Backup"], _names(out)
    print("PASS: is_backup field is ignored (Q1=b)")


def test_cross_category_excluded():
    """Sources from other categories never appear."""
    today = date(2026, 5, 3)
    rows = [
        _row("FunSrc", cat="Fun"),
        _row("NewsSrc", cat="News"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=3)
    assert _names(out) == ["FunSrc"], _names(out)
    print("PASS: cross-category sources excluded")


def test_under_fill_accepted():
    """Category with fewer than N enabled sources returns what it has."""
    today = date(2026, 5, 3)
    rows = [
        _row("Only",  next_pickup="2026-05-03"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=3)
    assert len(out) == 1
    print("PASS: under-fill returns < N gracefully")


def main():
    import sys
    tests = [
        test_never_used_sorts_first,
        test_eligible_only_picked,
        test_priority_tiebreak_within_eligible,
        test_lru_secondary_tiebreak,
        test_disabled_excluded,
        test_is_backup_now_included,
        test_cross_category_excluded,
        test_under_fill_accepted,
    ]
    try:
        for t in tests:
            t()
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run — should fail (load_sources doesn't accept `today=` / `n=` kwargs yet)**

```bash
.venv/bin/python -m pipeline.test_load_sources
```

Expected: TypeError on first test (missing kwargs in current signature).

- [ ] **Step 3: Commit failing test**

```bash
git add pipeline/test_load_sources.py
git commit -m "test(sources): cadence-aware load_sources test suite (8 cases, currently failing)"
```

---

## Task 4: Implement new `load_sources` algorithm

**Files:**
- Modify: `pipeline/db_config.py`

- [ ] **Step 1: Read current `load_sources` to know what to replace**

```bash
grep -n "def load_sources\|def load_backup_sources\|def _row_to_source" pipeline/db_config.py
```

- [ ] **Step 2: Add cadence_days + last_used_at + next_pickup_at to `NewsSource` dataclass**

In `pipeline/news_sources.py`:

```python
@dataclass
class NewsSource:
    id: int
    name: str
    rss_url: str
    flow: str
    max_to_vet: int
    min_body_words: int
    priority: int
    enabled: bool
    is_backup: bool
    notes: str = ""
    feed_kind: str = "rss"
    feed_config: str | None = None
    cadence_days: int = 1                    # NEW
    last_used_at: str | None = None          # NEW (ISO date string or None)
    next_pickup_at: str | None = None        # NEW (ISO date string or None)
```

- [ ] **Step 3: Update `_row_to_source` to pass new fields**

In `pipeline/db_config.py`:

```python
def _row_to_source(row: dict) -> NewsSource:
    return NewsSource(
        id=int(row["id"]),
        name=row["name"],
        rss_url=row["rss_url"],
        flow=row.get("flow") or "light",
        max_to_vet=int(row.get("max_to_vet") or 10),
        min_body_words=int(row.get("min_body_words") or 300),
        priority=int(row.get("priority") or 99),
        enabled=bool(row.get("enabled") if row.get("enabled") is not None else True),
        is_backup=bool(row.get("is_backup") or False),
        notes=row.get("notes") or "",
        feed_kind=row.get("feed_kind") or "rss",
        feed_config=row.get("feed_config"),
        cadence_days=int(row.get("cadence_days") or 1),
        last_used_at=row.get("last_used_at"),
        next_pickup_at=row.get("next_pickup_at"),
    )
```

- [ ] **Step 4: Rewrite `load_sources` with the 5-step algorithm**

```python
def load_sources(category_name: str, *,
                 today: "date | None" = None,
                 n: int = 3) -> list[NewsSource]:
    """Cadence-aware source selection per category.

    See docs/superpowers/specs/2026-05-03-cadence-aware-source-selection-design.md
    for the full algorithm. Returns up to `n` sources, ordered by:
      next_pickup_at ASC NULLS FIRST, priority ASC, last_used_at ASC NULLS FIRST.

    Eligible (next_pickup_at IS NULL OR <= today) come first; if fewer than
    `n` are eligible, fill from closest-to-eligible (next_pickup_at > today,
    soonest first). The pool is exhausted before under-fill is accepted.
    `is_backup` is ignored — all enabled sources participate.
    """
    from datetime import date as _date
    if today is None:
        today = _date.today()

    raw_by_cat = _ensure_src_cache()
    rows = raw_by_cat.get(category_name, [])

    # Filter: enabled, state in (NULL, 'live'). is_backup ignored (Q1=b).
    candidates = [r for r in rows
                  if r.get("enabled")
                  and (r.get("state") in (None, "live"))]

    def _sort_key(r):
        npa = r.get("next_pickup_at") or ""        # NULL → "" sorts first
        prio = int(r.get("priority") or 99)
        lua = r.get("last_used_at") or ""
        return (npa, prio, lua)

    today_iso = today.isoformat()
    eligible = sorted(
        [r for r in candidates
         if not r.get("next_pickup_at") or r["next_pickup_at"] <= today_iso],
        key=_sort_key,
    )
    sleeping = sorted(
        [r for r in candidates
         if r.get("next_pickup_at") and r["next_pickup_at"] > today_iso],
        key=_sort_key,
    )

    picked = eligible[:n]
    if len(picked) < n:
        picked += sleeping[:n - len(picked)]

    return [_row_to_source(r) for r in picked]
```

- [ ] **Step 5: Delete `load_backup_sources` (no callers after Q1=b)**

```bash
grep -n "load_backup_sources" pipeline/db_config.py
# Delete the entire function. Then grep the codebase to verify no callers:
grep -rn "load_backup_sources" pipeline/ | grep -v __pycache__
```

If grep returns hits in `full_round.py`, those calls will be removed in Task 6.

- [ ] **Step 6: Run tests**

```bash
.venv/bin/python -m pipeline.test_load_sources
```

Expected: `All 8 tests passed.`

- [ ] **Step 7: Commit**

```bash
git add pipeline/db_config.py pipeline/news_sources.py
git commit -m "feat(sources): cadence-aware load_sources with 5-step algorithm"
```

---

## Task 5: Drop `backup` arg from aggregate.py functions

**Files:**
- Modify: `pipeline/news_aggregate.py`
- Modify: `pipeline/science_aggregate.py`
- Modify: `pipeline/fun_aggregate.py`

- [ ] **Step 1: Inspect current signature**

```bash
grep -A 5 "def run_source_with_backups" pipeline/news_aggregate.py
```

- [ ] **Step 2: Rename + drop arg in each of 3 files**

For each `*_aggregate.py`, change:

```python
def run_source_with_backups(source, backups, ...):
    ...
    if no_candidates(result) and backups:
        for b in backups:
            ...
    return result
```

to:

```python
def run_source(source, ...):
    """Single-pass source run. No backup-swap fallback (Q1=b decision —
    backup pool folded into primaries via cadence)."""
    ...
    return result
```

Remove the `backups` loop. Keep the rest of the body (Phase A, vet, etc.) unchanged.

- [ ] **Step 3: Verify imports + callers**

```bash
grep -rn "run_source_with_backups" pipeline/ | grep -v __pycache__
```

Expected hits in `full_round.py` only — they get fixed in Task 6.

- [ ] **Step 4: Commit**

```bash
git add pipeline/news_aggregate.py pipeline/science_aggregate.py pipeline/fun_aggregate.py
git commit -m "refactor(aggregate): drop backup arg from run_source (Q1=b)"
```

---

## Task 6: Wire `full_round.main()` to DB-driven sources

**Files:**
- Modify: `pipeline/full_round.py`

- [ ] **Step 1: Find the source-loader calls**

```bash
grep -n "news_sources()\|science_sources()\|fun_sources()\|news_backups()\|sci_backups()\|fun_backups()" pipeline/full_round.py
```

Expected: lines 1083-1085 (the 3 aggregate_category calls).

- [ ] **Step 2: Replace lines 1083-1085**

```python
# OLD:
news_bs    = aggregate_category("News",    news_sources(),    news_backups(), run_news)
science_bs = aggregate_category("Science", science_sources(), sci_backups(),  run_sci)
fun_bs     = aggregate_category("Fun",     fun_sources(),     fun_backups(),  run_fun)
```

```python
# NEW:
from datetime import date as _date
today_d = _date.today()
news_bs    = aggregate_category("News",    db_config.load_sources("News",    today=today_d, n=3), run_news)
science_bs = aggregate_category("Science", db_config.load_sources("Science", today=today_d, n=3), run_sci)
fun_bs     = aggregate_category("Fun",     db_config.load_sources("Fun",     today=today_d, n=3), run_fun)
```

Note: `aggregate_category` signature also needs to drop the `backups` param. Update the function definition in the same file (around line 48):

```python
# OLD:
def aggregate_category(label: str, enabled: list, backups: list, runner) -> dict[str, dict]:
    used_backups: set[str] = set()
    for src_obj in enabled:
        avail = [b for b in backups if b.name not in used_backups]
        ...

# NEW:
def aggregate_category(label: str, enabled: list, runner) -> dict[str, dict]:
    """Run each source through `runner`. No backup-swap (Q1=b)."""
    out: dict[str, dict] = {}
    for src_obj in enabled:
        res = runner(src_obj)
        out[src_obj.name] = res
    return out
```

- [ ] **Step 3: Drop the now-unused imports**

```python
# DELETE these lines (around 21-33):
from .fun_sources import todays_enabled_sources as fun_sources
from .fun_sources import todays_topic as fun_topic
from .science_sources import todays_enabled_sources as science_sources
from .science_sources import todays_topic as science_topic
from .news_sources import enabled_sources as news_sources
from .news_sources import backup_sources as news_backups
from .science_sources import todays_backup_sources as sci_backups
from .fun_sources import todays_backup_sources as fun_backups
```

Keep `from .news_aggregate import run_source as run_news` (renamed in Task 5).

- [ ] **Step 4: Extend the stamp loop with `next_pickup_at`**

Find lines 1004-1023 (the `last_used_at` stamp loop):

```python
# OLD:
client().table("redesign_source_configs") \
    .update({"last_used_at": now_iso}) \
    .in_("name", list(used_source_names)) \
    .execute()
```

```python
# NEW:
from datetime import datetime, timezone, timedelta, date as _date
today_d = _date.today()
# Stamp BOTH last_used_at AND next_pickup_at = today + cadence_days.
# Per-source PATCH because cadence_days varies. Source list is small (≤9
# winners per run), so per-row PATCH is fine.
src_rows = client().table("redesign_source_configs") \
    .select("name,cadence_days") \
    .in_("name", list(used_source_names)) \
    .execute().data or []

for row in src_rows:
    cd = int(row.get("cadence_days") or 1)
    next_pickup = (today_d + timedelta(days=cd)).isoformat()
    client().table("redesign_source_configs") \
        .update({"last_used_at": now_iso, "next_pickup_at": next_pickup}) \
        .eq("name", row["name"]) \
        .execute()
log.info("  stamped last_used_at + next_pickup_at on %d source(s)",
         len(src_rows))
```

- [ ] **Step 5: Verify no remaining hardcoded source references**

```bash
grep -nE "news_sources|science_sources|fun_sources|news_backups|sci_backups|fun_backups" pipeline/full_round.py
```

Expected: zero hits (after the deletes).

- [ ] **Step 6: Smoke-import**

```bash
.venv/bin/python -c "from pipeline.full_round import main; print('imports OK')"
```

- [ ] **Step 7: Commit**

```bash
git add pipeline/full_round.py
git commit -m "feat(pipeline): main() uses db_config.load_sources for all 3 cats + cadence stamp"
```

---

## Task 7: Decommission hardcoded `*_sources.py` modules

**Files:**
- Modify: `pipeline/news_sources.py` (keep `NewsSource` dataclass only)
- Modify: `pipeline/science_sources.py` (delete contents below dataclass)
- Modify: `pipeline/fun_sources.py` (same)

- [ ] **Step 1: Remove SOURCES + helper functions from `news_sources.py`**

Keep only:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- The `@dataclass class NewsSource` block (with the new cadence_days etc. fields from Task 4)

Delete:
- `SOURCES: list[NewsSource] = [...]`
- `def enabled_sources()`
- `def backup_sources()`

- [ ] **Step 2: Same for `science_sources.py` and `fun_sources.py`**

Delete `SCIENCE_ALWAYS`, `SCIENCE_WEEKDAY`, `WEEKDAY_TOPICS`, `SCIENCE_BACKUPS`, `WEEKDAY_SOURCES`, `FUN_BACKUPS`, `todays_enabled_sources`, `todays_topic`, `todays_backup_sources`.

These two files end up with just `import` lines. Acceptable; deleting the files entirely would break any stale checkpoint that imports the module.

- [ ] **Step 3: grep verification**

```bash
grep -rn "SOURCES = \|WEEKDAY_SOURCES\|SCIENCE_WEEKDAY\|SCIENCE_BACKUPS\|FUN_BACKUPS" pipeline/ | grep -v __pycache__
# Expected: zero matches.
grep -rn "todays_enabled_sources\|todays_backup_sources\|enabled_sources\|backup_sources" pipeline/ | grep -v __pycache__
# Expected: zero matches.
```

- [ ] **Step 4: Smoke-import**

```bash
.venv/bin/python -c "
from pipeline.news_sources import NewsSource
from pipeline.science_sources import *
from pipeline.fun_sources import *
print('imports OK; NewsSource is the only export')
"
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/news_sources.py pipeline/science_sources.py pipeline/fun_sources.py
git commit -m "refactor(sources): decommission hardcoded SOURCES literals (DB-driven now)"
```

---

## Task 8: Pipeline dry-run + verify

**Files:** none modified (verification only)

- [ ] **Step 1: Push branch + open draft PR**

```bash
git push -u origin feature/cadence-aware-sources
gh pr create -R daijiong1977/news-v2 --draft --title "feat(pipeline): cadence-aware source selection" --body "$(cat <<'EOF'
Implements docs/superpowers/specs/2026-05-03-cadence-aware-source-selection-design.md.

Marked draft until pipeline dry-run is green.
EOF
)"
```

- [ ] **Step 2: Manual dispatch a pipeline run**

```bash
gh workflow run daily-pipeline.yml -R daijiong1977/news-v2 --ref feature/cadence-aware-sources
sleep 5
gh run list -R daijiong1977/news-v2 --workflow daily-pipeline.yml --limit 1 --json databaseId,status
# Capture the run ID for the Monitor.
```

- [ ] **Step 3: Watch for completion**

Use `Monitor` to poll the run and emit on terminal status:

```bash
RUN=<id from step 2>
while true; do
  s=$(gh run view "$RUN" -R daijiong1977/news-v2 --json status,conclusion --jq '"\(.status) \(.conclusion // "")"')
  echo "$RUN: $s"
  case "$s" in *completed*) exit 0;; esac
  sleep 60
done
```

- [ ] **Step 4: Verify telemetry**

```sql
SELECT id, run_date, status, telemetry->'per_category', telemetry->'warnings'
FROM redesign_runs
WHERE run_date = current_date
ORDER BY started_at DESC
LIMIT 1;
```

Expected:
- `per_category` shows News=3, Science=3, Fun=3 winners
- `warnings` is `[]` or contains only previously-known warnings (curator truncation, etc.)
- Article distribution makes sense (e.g. one of DOGOnews/NG Kids appeared in Fun)

- [ ] **Step 5: Verify next_pickup_at stamps**

```sql
SELECT name, category, cadence_days, last_used_at, next_pickup_at
FROM redesign_source_configs
WHERE last_used_at >= current_date
ORDER BY last_used_at DESC;
```

Expected: 3-9 rows (sources whose article shipped today). For each, `next_pickup_at = today + cadence_days`. E.g., NG Kids — Space picked → next_pickup_at = today + 7.

- [ ] **Step 6: Promote PR from draft → ready-for-review**

```bash
gh pr ready <PR_NUM> -R daijiong1977/news-v2
```

- [ ] **Step 7: Final commit (if dry-run requires any tweaks)**

If telemetry shows surprises (e.g. a source the dry-run preferred but shouldn't have), tweak cadence values via SQL — no code change needed.

---

## Rollback plan

If the PR causes a production failure (e.g., load_sources returns empty):

1. **Immediate**: `gh pr revert <PR_NUM>`. The migration adds nullable columns, so reverting code without reverting the migration is safe.
2. **If migration is the culprit**: dropping `cadence_days` and `next_pickup_at` columns is a non-issue since legacy code didn't reference them. But the legacy code is gone — you'd need to revert the source-modules-deletion commit too.
3. **Quick recover**: `UPDATE redesign_source_configs SET enabled=true, cadence_days=1, next_pickup_at=NULL` reverts every row to "always eligible" — pipeline runs as if cadence didn't exist.

---

## Out of scope (next iteration)

- Auto-tune `cadence_days` from observed RSS pub dates (separate spec).
- Multi-pick per source (today: 1 article per source; future: 2-3 if RSS is rich).
- Topical pinning / curator hints across days.
