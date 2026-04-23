-- KidsNews redesign parallel schema
-- Creates a new table family for the redesign pipeline without changing the
-- current production schema. Old and new systems can run side by side.

begin;

create extension if not exists pgcrypto;

create table if not exists public.redesign_runs (
  id uuid primary key default gen_random_uuid(),
  run_date date not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed', 'cancelled')),
  trigger_source text not null default 'manual'
    check (trigger_source in ('manual', 'scheduled', 'retry', 'backfill')),
  notes text,
  config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.redesign_candidates (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.redesign_runs(id) on delete cascade,
  category text not null check (category in ('News', 'Science', 'Fun')),
  discovery_lane text not null check (discovery_lane in ('new_pipeline', 'rss')),
  source_name text,
  source_domain text,
  source_url text not null,
  title text not null,
  snippet text,
  raw_content text,
  image_urls jsonb not null default '[]'::jsonb,
  discovered_rank integer,
  vetted_rank integer,
  detail_rank integer,
  vetter_score integer,
  vetter_verdict text check (vetter_verdict in ('SAFE', 'CAUTION', 'REJECT')),
  vetter_flags jsonb not null default '[]'::jsonb,
  vetter_payload jsonb not null default '{}'::jsonb,
  read_method text,
  selected_for_detail boolean not null default false,
  selected_for_publish boolean not null default false,
  exhausted boolean not null default false,
  created_at timestamptz not null default now(),
  unique (run_id, source_url)
);

create table if not exists public.redesign_stories (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.redesign_runs(id) on delete cascade,
  candidate_id uuid references public.redesign_candidates(id) on delete set null,
  category text not null check (category in ('News', 'Science', 'Fun')),
  published_date date not null,
  story_slot integer not null check (story_slot between 1 and 3),
  canonical_title text not null,
  canonical_source_url text,
  primary_image_url text,
  primary_image_credit text,
  vetter_score integer,
  vetter_verdict text not null check (vetter_verdict in ('SAFE', 'CAUTION')),
  publish_status text not null default 'published'
    check (publish_status in ('published', 'archived')),
  created_at timestamptz not null default now(),
  published_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique (published_date, category, story_slot)
);

create table if not exists public.redesign_story_variants (
  id uuid primary key default gen_random_uuid(),
  story_id uuid not null references public.redesign_stories(id) on delete cascade,
  variant_key text not null check (variant_key in ('easy_en', 'middle_en', 'zh')),
  language_code text not null check (language_code in ('en', 'zh')),
  reading_level text not null check (reading_level in ('easy', 'middle', 'localized')),
  headline text not null,
  body text not null,
  why_it_matters text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (story_id, variant_key)
);

create table if not exists public.redesign_story_sources (
  id uuid primary key default gen_random_uuid(),
  story_id uuid not null references public.redesign_stories(id) on delete cascade,
  source_url text not null,
  source_name text,
  source_domain text,
  sort_order integer not null default 1,
  created_at timestamptz not null default now(),
  unique (story_id, source_url)
);

create index if not exists idx_redesign_runs_run_date
  on public.redesign_runs(run_date desc);

create index if not exists idx_redesign_candidates_run_category
  on public.redesign_candidates(run_id, category, discovery_lane);

create index if not exists idx_redesign_candidates_verdict
  on public.redesign_candidates(vetter_verdict, vetted_rank);

create index if not exists idx_redesign_stories_date_category
  on public.redesign_stories(published_date desc, category);

create index if not exists idx_redesign_story_variants_story
  on public.redesign_story_variants(story_id, variant_key);

create index if not exists idx_redesign_story_sources_story
  on public.redesign_story_sources(story_id, sort_order);

create or replace view public.redesign_published_variants_v as
select
  story.id as story_id,
  story.run_id,
  story.published_date,
  story.category,
  story.story_slot,
  story.vetter_verdict,
  story.primary_image_url,
  story.primary_image_credit,
  variant.variant_key,
  variant.language_code,
  variant.reading_level,
  variant.headline,
  variant.body,
  variant.why_it_matters,
  variant.payload
from public.redesign_stories as story
join public.redesign_story_variants as variant
  on variant.story_id = story.id
where story.publish_status = 'published';

comment on table public.redesign_runs is
  'Top-level redesign pipeline runs. Keeps old articles schema untouched during side-by-side validation.';

comment on table public.redesign_candidates is
  'All discovered and vetted candidates for a redesign run, including 6+4 funnel metadata.';

comment on table public.redesign_stories is
  'Final publishable redesign stories only. SAFE and CAUTION stories land here.';

comment on table public.redesign_story_variants is
  'Per-story outputs for easy English, middle English, and Chinese.';

comment on table public.redesign_story_sources is
  'Supporting source links attached to each redesign story.';

commit;