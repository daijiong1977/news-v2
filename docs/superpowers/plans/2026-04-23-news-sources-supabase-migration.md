# Migrating `news_sources` from code to Supabase

**Status:** Pending (Phase 3).
**Current location:** `pipeline/news_sources.py` (hardcoded `SOURCES` list).
**Target location:** Supabase table `redesign_news_sources` in the existing project
`lfknsvavhiqrsasdfyrs.supabase.co`.

## Why migrate later
Schema is stable; the rows rarely change; hardcoding keeps iteration fast during
Phase 1-2. Migration becomes valuable when:
- We want an admin UI to toggle `enabled` without code push, or
- Multiple environments (dev/prod) diverge on which sources are on, or
- Priority and backup rotation is tuned dynamically per day

## Migration plan

### Step 1 — create the table (one-shot migration file)

Add to `supabase/migrations/` as `20260501_news_sources.sql`:

```sql
create table if not exists public.redesign_news_sources (
  id              integer primary key,
  name            text    not null,
  rss_url         text    not null,
  flow            text    not null check (flow in ('full', 'light')),
  max_to_vet      integer not null default 10,
  min_body_words  integer not null default 500,
  priority        integer not null,
  enabled         boolean not null default true,
  is_backup       boolean not null default false,
  notes           text,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index idx_redesign_news_sources_priority
  on public.redesign_news_sources(priority);
create index idx_redesign_news_sources_enabled
  on public.redesign_news_sources(enabled, is_backup);

comment on table public.redesign_news_sources is
  'RSS source registry for the v2 news pipeline. Priority orders picks; is_backup=true means only used when an enabled source fails.';
```

### Step 2 — seed rows

```sql
insert into public.redesign_news_sources
  (id, name, rss_url, flow, max_to_vet, min_body_words, priority, enabled, is_backup, notes)
values
  (1, 'Al Jazeera',     'https://www.aljazeera.com/xml/rss/all.xml',         'full',  10, 500, 1, true,  false, null),
  (2, 'PBS NewsHour',   'https://www.pbs.org/newshour/feeds/rss/headlines',  'full',   6, 500, 2, true,  false, 'cap at 6 to vetter'),
  (3, 'NPR World',      'https://feeds.npr.org/1003/rss.xml',                'light', 10, 500, 3, true,  false, null),
  (4, 'Guardian World', 'https://www.theguardian.com/world/rss',             'light', 25, 500, 4, false, true,  'backup'),
  (5, 'BBC News',       'http://feeds.bbci.co.uk/news/rss.xml',              'light', 25, 500, 5, false, true,  'backup');
```

### Step 3 — swap the registry implementation

Replace `pipeline/news_sources.py`'s hardcoded `SOURCES` list with a fetch
from Supabase (using `supabase-py`). Cache the result for the duration of
the pipeline run.

```python
def enabled_sources() -> list[NewsSource]:
    rows = supabase.table("redesign_news_sources")\
        .select("*")\
        .eq("enabled", True)\
        .eq("is_backup", False)\
        .order("priority").execute().data
    return [NewsSource(**r) for r in rows]
```

### Step 4 — verify

Run `python -m pipeline.news_aggregate` and confirm:
- Correct sources are queried (log lines show Al Jazeera / PBS / NPR).
- Output matches prior pre-migration run.

### Step 5 — (optional) build admin toggle

Once migrated, an admin can update rows via Supabase Studio to:
- `enabled=false` to disable a source
- `is_backup=true`/`false` to move between primary and backup pools
- `priority` to change the serial order

No code push needed.

## Rollback
If Supabase is unreachable, fall back to the hardcoded list for that run and
log the degradation. Keep the hardcoded list in sync with the table during the
transition period.
