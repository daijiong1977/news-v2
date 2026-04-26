-- Kid identity layer
-- =================
-- Three identity entry points: anonymous client_id (default),
-- 6-digit pairing-code claim, and Gmail SSO. The latter two let a
-- kid keep their reading_events / streak across browsers + devices.
--
-- Pairing-code claim (kid self-service):
--   - lookup_pairing_code(code) — anon-callable, single-use, returns
--     the client_id the code is bound to. Reuses redesign_kid_pairing_codes
--     (same table the parent-link flow uses; whichever consumer calls
--     first wins).
--
-- Gmail SSO claim:
--   - redesign_kid_email_links — canonical email ↔ client_id table
--   - claim_or_create_kid_for_email(p_local_client_id) — auth-required,
--     reads auth.email() of the caller. If a mapping exists, returns
--     the existing client_id (so a second device with same Gmail gets
--     the same identity). If no mapping, links p_local_client_id (the
--     anonymous id this device has been using) so the kid's existing
--     reading history transfers to the Gmail-linked identity.
--
-- Cloud-side history read (so a freshly-claimed device has data to
-- render even before the kid reads anything new):
--   - get_reading_history(p_client_id, p_limit) — anon-callable,
--     returns the most recent N reading_events as a flat list. Powers
--     the Continue-reading rail + streak popover after a claim.
--
-- All RPCs SECURITY DEFINER + explicit grants. Row-level security on
-- email_links is permissive read for anon (so the "is this email
-- linked?" check pre-sign-in works), but writes go through the RPCs
-- only.

-- ----------------------------------------------------------------------
-- 1. Email ↔ client_id mapping (Gmail SSO)
-- ----------------------------------------------------------------------
create table if not exists public.redesign_kid_email_links (
  email      text primary key,
  client_id  uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_kid_email_links_client_id
  on public.redesign_kid_email_links (client_id);

alter table public.redesign_kid_email_links enable row level security;

-- Read: anon can SELECT (we need to check existence pre-sign-in for the
-- 'I'm signed in but never linked' case). Returns email→client_id mapping.
drop policy if exists email_links_read on public.redesign_kid_email_links;
create policy email_links_read on public.redesign_kid_email_links
  for select using (true);

-- Writes go only through the RPC.
drop policy if exists email_links_no_direct_write on public.redesign_kid_email_links;
create policy email_links_no_direct_write on public.redesign_kid_email_links
  for all using (false) with check (false);

-- ----------------------------------------------------------------------
-- 2. lookup_pairing_code — kid self-claim, anon
-- ----------------------------------------------------------------------
create or replace function public.lookup_pairing_code(p_code text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_client_id uuid;
begin
  select client_id into v_client_id
    from public.redesign_kid_pairing_codes
    where code = p_code
      and consumed_at is null
      and expires_at > now()
    for update;
  if v_client_id is null then
    raise exception 'Code is invalid or has expired';
  end if;
  -- Single-use. Mark it consumed by a kid (vs by a parent through
  -- consume_pairing_code) so we can audit which path consumed it.
  update public.redesign_kid_pairing_codes
    set consumed_at = now(), consumer_email = '__kid_self_claim__'
    where code = p_code;
  -- Touch last_seen on the kid profile.
  update public.redesign_kid_profiles
    set last_seen_at = now()
    where client_id = v_client_id;
  return v_client_id;
end;
$$;
grant execute on function public.lookup_pairing_code(text) to anon, authenticated;

-- ----------------------------------------------------------------------
-- 3. claim_or_create_kid_for_email — Gmail SSO
-- ----------------------------------------------------------------------
-- Called after a successful Google sign-in. Caller passes their current
-- local (anonymous) client_id. If an email mapping exists, returns the
-- canonical client_id (overrides the local one). If not, links the
-- local client_id so the kid's pre-SSO history transfers seamlessly.
create or replace function public.claim_or_create_kid_for_email(p_local_client_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_canonical uuid;
begin
  v_email := auth.email();
  if v_email is null then
    raise exception 'Sign-in required';
  end if;

  -- Existing mapping?
  select client_id into v_canonical
    from public.redesign_kid_email_links
    where email = v_email;

  if v_canonical is not null then
    -- Refresh updated_at so we can spot stale rows.
    update public.redesign_kid_email_links
      set updated_at = now()
      where email = v_email;
    -- Touch last_seen on the kid profile.
    update public.redesign_kid_profiles
      set last_seen_at = now()
      where client_id = v_canonical;
    return v_canonical;
  end if;

  -- First time this email signs in. Bind it to the device's local
  -- client_id so existing anonymous events belong to this Gmail going
  -- forward. Auto-create the kid profile if it doesn't exist.
  insert into public.redesign_kid_profiles (client_id)
    values (p_local_client_id)
    on conflict (client_id) do update set last_seen_at = now();

  insert into public.redesign_kid_email_links (email, client_id)
    values (v_email, p_local_client_id);

  return p_local_client_id;
end;
$$;
grant execute on function public.claim_or_create_kid_for_email(uuid) to authenticated;

-- ----------------------------------------------------------------------
-- 4. get_reading_history — cloud-side hydration
-- ----------------------------------------------------------------------
-- Returns the kid's last N completed-step reading events (one row per
-- (story_id, step) tuple). The kid app calls this on every launch to
-- repopulate readHistory + articleProgress in case localStorage was
-- cleared. Anon-callable so a kid still claiming via pairing code can
-- pre-fetch history without waiting for auth.
create or replace function public.get_reading_history(
  p_client_id uuid,
  p_limit int default 100
)
returns table (
  story_id     text,
  step         text,
  category     text,
  level        text,
  occurred_at  timestamptz,
  day_key      text
)
language sql
security definer
set search_path = public
stable
as $$
  select e.story_id, e.step, e.category, e.level, e.occurred_at, e.day_key
    from public.redesign_reading_events e
   where e.client_id = p_client_id
     and e.occurred_at > now() - interval '21 days'
   order by e.occurred_at desc
   limit greatest(1, least(coalesce(p_limit, 100), 500));
$$;
grant execute on function public.get_reading_history(uuid, int) to anon, authenticated;
