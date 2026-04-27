-- Today's picks → kid_profile so they round-trip across devices.
-- Plus articleProgress is reconstructed client-side from existing
-- redesign_reading_events on bootstrap (no schema change there;
-- events table already has every step bump).

alter table public.redesign_kid_profiles
  add column if not exists today_picks_date text,
  add column if not exists today_picks_json jsonb;

create or replace function public.set_today_picks(
  p_client_id uuid,
  p_day_key   text,
  p_ids       jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_client_id is null then
    raise exception 'client_id required';
  end if;
  insert into public.redesign_kid_profiles (client_id, today_picks_date, today_picks_json, last_seen_at)
    values (p_client_id, p_day_key, p_ids, now())
    on conflict (client_id) do update set
      today_picks_date = excluded.today_picks_date,
      today_picks_json = excluded.today_picks_json,
      last_seen_at = now();
end;
$$;
grant execute on function public.set_today_picks(uuid, text, jsonb) to anon, authenticated;

drop function if exists public.get_kid_profile(uuid);
create or replace function public.get_kid_profile(p_client_id uuid)
returns table (
  client_id        uuid,
  display_name     text,
  avatar           text,
  level            text,
  language         text,
  theme            text,
  daily_goal       int,
  today_picks_date text,
  today_picks_json jsonb
)
language sql
security definer
set search_path = public
stable
as $$
  select client_id, display_name, avatar, level, language, theme, daily_goal,
         today_picks_date, today_picks_json
    from public.redesign_kid_profiles
    where client_id = p_client_id;
$$;
grant execute on function public.get_kid_profile(uuid) to anon, authenticated;
