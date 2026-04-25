-- KidsNews — Parent Dashboard schema
--
-- Adds parent identity, kid profiles, reading-event log, quiz/discussion/
-- reaction mirrors, and pairing codes. RLS gates each parent to seeing only
-- their own kids' data; anon write paths go through SECURITY DEFINER RPCs so
-- we never grant table-level INSERT to anon callers.
--
-- Safe to run multiple times (idempotent CREATEs + drop-then-create policies).

begin;

create extension if not exists pgcrypto;

-- ─────────────────────────────────────────────────────────────────────
-- 1. Tables
-- ─────────────────────────────────────────────────────────────────────

create table if not exists public.redesign_parent_users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  name text,
  digest_cadence text not null default 'off'
    check (digest_cadence in ('off', 'weekly', 'daily')),
  digest_last_sent_at timestamptz,
  created_at timestamptz not null default now(),
  last_login_at timestamptz not null default now()
);

create table if not exists public.redesign_kid_profiles (
  client_id uuid primary key,           -- == ohye_client_id
  parent_user_id uuid references public.redesign_parent_users(id) on delete set null,
  display_name text,
  avatar text,
  level text,
  language text,
  theme text,
  daily_goal int not null default 21,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists public.redesign_reading_events (
  id bigserial primary key,
  client_id uuid not null references public.redesign_kid_profiles(client_id) on delete cascade,
  story_id text not null,
  category text,
  level text,
  language text,
  step text not null
    check (step in ('open', 'read', 'analyze', 'quiz', 'discuss', 'finish')),
  minutes_added numeric(6,2) not null default 0,
  duration_ms int,
  occurred_at timestamptz not null default now(),
  day_key text not null                 -- 'YYYY-MM-DD' kid local TZ
);
create index if not exists idx_reading_events_client_time
  on public.redesign_reading_events (client_id, occurred_at desc);
create index if not exists idx_reading_events_client_day
  on public.redesign_reading_events (client_id, day_key);

create table if not exists public.redesign_quiz_attempts (
  id bigserial primary key,
  client_id uuid not null references public.redesign_kid_profiles(client_id) on delete cascade,
  story_id text not null,
  level text,
  picks jsonb not null,                 -- e.g. [2,1,0,3,2]
  correct int not null,
  total int not null,
  duration_ms int,
  attempted_at timestamptz not null default now(),
  day_key text not null
);
create index if not exists idx_quiz_attempts_client_time
  on public.redesign_quiz_attempts (client_id, attempted_at desc);

create table if not exists public.redesign_article_reactions (
  client_id uuid not null references public.redesign_kid_profiles(client_id) on delete cascade,
  story_id text not null,
  level text not null default '',
  reaction text not null
    check (reaction in ('love', 'meh', 'thinky', 'dislike')),
  reacted_at timestamptz not null default now(),
  primary key (client_id, story_id, level)
);

create table if not exists public.redesign_discussion_responses (
  id bigserial primary key,
  client_id uuid not null references public.redesign_kid_profiles(client_id) on delete cascade,
  story_id text not null,
  level text not null default '',
  rounds jsonb not null default '[]'::jsonb,
  saved_final boolean not null default false,
  updated_at timestamptz not null default now(),
  unique (client_id, story_id, level)
);

create table if not exists public.redesign_kid_pairing_codes (
  code text primary key,                -- 6-digit numeric
  client_id uuid not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz,
  consumer_email text                   -- email that consumed (for audit)
);
create index if not exists idx_pairing_codes_expires
  on public.redesign_kid_pairing_codes (expires_at);

-- ─────────────────────────────────────────────────────────────────────
-- 2. RLS
-- ─────────────────────────────────────────────────────────────────────

alter table public.redesign_parent_users enable row level security;
alter table public.redesign_kid_profiles enable row level security;
alter table public.redesign_reading_events enable row level security;
alter table public.redesign_quiz_attempts enable row level security;
alter table public.redesign_article_reactions enable row level security;
alter table public.redesign_discussion_responses enable row level security;
alter table public.redesign_kid_pairing_codes enable row level security;

-- Helper: caller's parent_user_id (NULL for anon / non-registered emails).
-- SECURITY DEFINER so it can read parent_users without recursing through RLS.
create or replace function public._parent_user_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select id from public.redesign_parent_users where email = auth.email();
$$;

-- redesign_parent_users: each row visible/writable only by its own email.
drop policy if exists parent_self_select on public.redesign_parent_users;
create policy parent_self_select on public.redesign_parent_users
  for select using (auth.email() is not null and email = auth.email());

drop policy if exists parent_self_update on public.redesign_parent_users;
create policy parent_self_update on public.redesign_parent_users
  for update using (auth.email() is not null and email = auth.email());

-- INSERT only via the upsert_parent_self() RPC (no policy → blocked).

-- redesign_kid_profiles: parent sees only their kids.
drop policy if exists kid_by_parent_select on public.redesign_kid_profiles;
create policy kid_by_parent_select on public.redesign_kid_profiles
  for select using (parent_user_id = public._parent_user_id());

-- No direct INSERT/UPDATE policies — kid-side writes go through SECURITY
-- DEFINER RPCs (upsert_kid_profile, claim_kid_for_caller).

-- redesign_reading_events / quiz_attempts / reactions / discussion:
-- parent sees only their kids' rows; no direct writes from anyone.
drop policy if exists events_by_parent on public.redesign_reading_events;
create policy events_by_parent on public.redesign_reading_events
  for select using (
    client_id in (
      select client_id from public.redesign_kid_profiles
      where parent_user_id = public._parent_user_id()
    )
  );

drop policy if exists quiz_by_parent on public.redesign_quiz_attempts;
create policy quiz_by_parent on public.redesign_quiz_attempts
  for select using (
    client_id in (
      select client_id from public.redesign_kid_profiles
      where parent_user_id = public._parent_user_id()
    )
  );

drop policy if exists reactions_by_parent on public.redesign_article_reactions;
create policy reactions_by_parent on public.redesign_article_reactions
  for select using (
    client_id in (
      select client_id from public.redesign_kid_profiles
      where parent_user_id = public._parent_user_id()
    )
  );

drop policy if exists discussion_by_parent on public.redesign_discussion_responses;
create policy discussion_by_parent on public.redesign_discussion_responses
  for select using (
    client_id in (
      select client_id from public.redesign_kid_profiles
      where parent_user_id = public._parent_user_id()
    )
  );

-- redesign_kid_pairing_codes: no direct read/write from anyone. RPCs only.

-- ─────────────────────────────────────────────────────────────────────
-- 3. RPCs
-- ─────────────────────────────────────────────────────────────────────

-- upsert_parent_self(): called by signed-in parent on first hit of /parent.
-- Inserts (or updates last_login_at) using the auth.email().
create or replace function public.upsert_parent_self(p_name text default null)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_id uuid;
begin
  v_email := auth.email();
  if v_email is null then
    raise exception 'Sign-in required';
  end if;
  insert into public.redesign_parent_users (email, name)
  values (v_email, coalesce(p_name, ''))
  on conflict (email) do update
    set last_login_at = now(),
        name = coalesce(nullif(excluded.name, ''), public.redesign_parent_users.name)
  returning id into v_id;
  return v_id;
end;
$$;
grant execute on function public.upsert_parent_self(text) to authenticated;

-- upsert_kid_profile: called from kid side whenever tweaks change. Anon-callable.
-- Creates the profile row if missing, else updates settings. Never touches
-- parent_user_id (only claim/consume RPCs do).
create or replace function public.upsert_kid_profile(
  p_client_id uuid,
  p_display_name text default null,
  p_avatar text default null,
  p_level text default null,
  p_language text default null,
  p_theme text default null,
  p_daily_goal int default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.redesign_kid_profiles
    (client_id, display_name, avatar, level, language, theme, daily_goal, last_seen_at)
  values
    (p_client_id, p_display_name, p_avatar, p_level, p_language, p_theme,
     coalesce(p_daily_goal, 21), now())
  on conflict (client_id) do update
    set display_name = coalesce(excluded.display_name, public.redesign_kid_profiles.display_name),
        avatar       = coalesce(excluded.avatar,       public.redesign_kid_profiles.avatar),
        level        = coalesce(excluded.level,        public.redesign_kid_profiles.level),
        language     = coalesce(excluded.language,     public.redesign_kid_profiles.language),
        theme        = coalesce(excluded.theme,        public.redesign_kid_profiles.theme),
        daily_goal   = coalesce(excluded.daily_goal,   public.redesign_kid_profiles.daily_goal),
        last_seen_at = now();
end;
$$;
grant execute on function public.upsert_kid_profile(uuid, text, text, text, text, text, int) to anon, authenticated;

-- record_reading_event: append-only event log. Anon-callable.
create or replace function public.record_reading_event(
  p_client_id uuid,
  p_story_id text,
  p_step text,
  p_category text default null,
  p_level text default null,
  p_language text default null,
  p_minutes_added numeric default 0,
  p_duration_ms int default null,
  p_day_key text default to_char(now(), 'YYYY-MM-DD')
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Auto-create kid profile row if first event.
  insert into public.redesign_kid_profiles (client_id) values (p_client_id)
    on conflict (client_id) do update set last_seen_at = now();
  insert into public.redesign_reading_events
    (client_id, story_id, category, level, language, step,
     minutes_added, duration_ms, day_key)
  values
    (p_client_id, p_story_id, p_category, p_level, p_language, p_step,
     coalesce(p_minutes_added, 0), p_duration_ms, p_day_key);
end;
$$;
grant execute on function public.record_reading_event(uuid, text, text, text, text, text, numeric, int, text) to anon, authenticated;

-- record_quiz_attempt: one row per quiz finish.
create or replace function public.record_quiz_attempt(
  p_client_id uuid,
  p_story_id text,
  p_level text,
  p_picks jsonb,
  p_correct int,
  p_total int,
  p_duration_ms int default null,
  p_day_key text default to_char(now(), 'YYYY-MM-DD')
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.redesign_kid_profiles (client_id) values (p_client_id)
    on conflict (client_id) do update set last_seen_at = now();
  insert into public.redesign_quiz_attempts
    (client_id, story_id, level, picks, correct, total, duration_ms, day_key)
  values
    (p_client_id, p_story_id, coalesce(p_level, ''), p_picks,
     p_correct, p_total, p_duration_ms, p_day_key);
end;
$$;
grant execute on function public.record_quiz_attempt(uuid, text, text, jsonb, int, int, int, text) to anon, authenticated;

-- record_article_reaction: upsert (one reaction per kid+story+level).
create or replace function public.record_article_reaction(
  p_client_id uuid,
  p_story_id text,
  p_level text,
  p_reaction text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.redesign_kid_profiles (client_id) values (p_client_id)
    on conflict (client_id) do update set last_seen_at = now();
  insert into public.redesign_article_reactions (client_id, story_id, level, reaction)
  values (p_client_id, p_story_id, coalesce(p_level, ''), p_reaction)
  on conflict (client_id, story_id, level) do update
    set reaction = excluded.reaction, reacted_at = now();
end;
$$;
grant execute on function public.record_article_reaction(uuid, text, text, text) to anon, authenticated;

-- upsert_discussion_response: stores rounds JSON + saved_final flag.
create or replace function public.upsert_discussion_response(
  p_client_id uuid,
  p_story_id text,
  p_level text,
  p_rounds jsonb,
  p_saved_final boolean
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.redesign_kid_profiles (client_id) values (p_client_id)
    on conflict (client_id) do update set last_seen_at = now();
  insert into public.redesign_discussion_responses
    (client_id, story_id, level, rounds, saved_final, updated_at)
  values
    (p_client_id, p_story_id, coalesce(p_level, ''), p_rounds, p_saved_final, now())
  on conflict (client_id, story_id, level) do update
    set rounds = excluded.rounds,
        saved_final = excluded.saved_final,
        updated_at = now();
end;
$$;
grant execute on function public.upsert_discussion_response(uuid, text, text, jsonb, boolean) to anon, authenticated;

-- generate_pairing_code: anon → returns a fresh 6-digit code, 10 min TTL.
-- Re-roll if collision (extremely unlikely but cheap to handle).
create or replace function public.generate_pairing_code(p_client_id uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_code text;
  v_attempts int := 0;
begin
  -- Auto-create profile if first time pairing.
  insert into public.redesign_kid_profiles (client_id) values (p_client_id)
    on conflict (client_id) do update set last_seen_at = now();
  loop
    v_code := lpad(floor(random() * 1000000)::text, 6, '0');
    begin
      insert into public.redesign_kid_pairing_codes
        (code, client_id, expires_at)
      values
        (v_code, p_client_id, now() + interval '10 minutes');
      return v_code;
    exception when unique_violation then
      v_attempts := v_attempts + 1;
      if v_attempts > 5 then raise exception 'Could not generate unique code'; end if;
    end;
  end loop;
end;
$$;
grant execute on function public.generate_pairing_code(uuid) to anon, authenticated;

-- consume_pairing_code: auth-required. Looks up code, checks freshness,
-- claims the kid for the caller's parent row.
create or replace function public.consume_pairing_code(p_code text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_parent_id uuid;
  v_client_id uuid;
begin
  v_email := auth.email();
  if v_email is null then
    raise exception 'Sign-in required';
  end if;
  -- Make sure parent row exists.
  v_parent_id := public.upsert_parent_self(null);

  select client_id into v_client_id
    from public.redesign_kid_pairing_codes
    where code = p_code
      and consumed_at is null
      and expires_at > now()
    for update;
  if v_client_id is null then
    raise exception 'Code is invalid or has expired';
  end if;
  update public.redesign_kid_pairing_codes
    set consumed_at = now(), consumer_email = v_email
    where code = p_code;
  update public.redesign_kid_profiles
    set parent_user_id = v_parent_id
    where client_id = v_client_id;
  return v_client_id;
end;
$$;
grant execute on function public.consume_pairing_code(text) to authenticated;

-- claim_kid_for_caller: same-device claim. Caller is the parent (auth'd),
-- p_client_id comes from the kid's localStorage on this device.
create or replace function public.claim_kid_for_caller(p_client_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_parent_id uuid;
  v_existing_parent uuid;
begin
  v_email := auth.email();
  if v_email is null then
    raise exception 'Sign-in required';
  end if;
  v_parent_id := public.upsert_parent_self(null);

  -- Make sure profile exists.
  insert into public.redesign_kid_profiles (client_id) values (p_client_id)
    on conflict (client_id) do nothing;

  select parent_user_id into v_existing_parent
    from public.redesign_kid_profiles
    where client_id = p_client_id;
  if v_existing_parent is not null and v_existing_parent <> v_parent_id then
    raise exception 'This kid is already linked to a different parent account';
  end if;

  update public.redesign_kid_profiles
    set parent_user_id = v_parent_id, last_seen_at = now()
    where client_id = p_client_id;
end;
$$;
grant execute on function public.claim_kid_for_caller(uuid) to authenticated;

-- unlink_kid: parent removes a kid from their dashboard.
create or replace function public.unlink_kid(p_client_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_parent_id uuid := public._parent_user_id();
begin
  if v_parent_id is null then
    raise exception 'Sign-in required';
  end if;
  update public.redesign_kid_profiles
    set parent_user_id = null
    where client_id = p_client_id and parent_user_id = v_parent_id;
end;
$$;
grant execute on function public.unlink_kid(uuid) to authenticated;

-- set_digest_cadence: parent toggles email-digest preference.
create or replace function public.set_digest_cadence(p_cadence text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text := auth.email();
begin
  if v_email is null then
    raise exception 'Sign-in required';
  end if;
  if p_cadence not in ('off', 'weekly', 'daily') then
    raise exception 'Invalid cadence';
  end if;
  update public.redesign_parent_users
    set digest_cadence = p_cadence
    where email = v_email;
end;
$$;
grant execute on function public.set_digest_cadence(text) to authenticated;

-- Comments
comment on table public.redesign_parent_users is
  'Parents who signed in via Google to enable cross-device sync + email digest. Local-mode parents are not stored here.';
comment on table public.redesign_kid_profiles is
  'One row per ohye_client_id ever seen. parent_user_id is NULL until claimed.';
comment on table public.redesign_reading_events is
  'Append-only log of kid reading activity. Drives all dashboard time-window aggregations.';

commit;
