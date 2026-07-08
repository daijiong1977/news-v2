-- Fix: the magic link bound the email to the device that CLICKS the link,
-- not the device that REQUESTED it (and holds the reading history).
--
-- Household path — type email on the laptop, tap the link in the phone's
-- mail app — bound the account to the phone's empty client_id and stranded
-- the laptop's streak/profile, silently re-showing onboarding. The email
-- promised "sync your reading streak to this email… come back from any
-- browser", but for the most common path it synced the wrong device.
-- See docs/bugs/2026-07-08-magic-link-binds-clicking-device.md
--
-- Root gap: issue_magic_link never recorded WHICH device requested the link,
-- so consume_magic_link had nothing to bind to but the clicking device.

alter table public.redesign_email_magic_links
  add column if not exists client_id uuid;   -- the REQUESTING device

-- issue_magic_link(p_email, p_client_id) records the requester's client_id.
-- p_client_id defaults NULL so a still-cached OLD client (calling with only
-- p_email during the deploy window) keeps working — it simply falls back to
-- the clicking device at consume, i.e. the previous behavior. The old 1-arg
-- signature is dropped so PostgREST resolves {p_email} to this one.
drop function if exists public.issue_magic_link(text);
create or replace function public.issue_magic_link(p_email text, p_client_id uuid default null)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_active int;
  v_token text;
begin
  v_email := lower(trim(p_email));
  if v_email is null or position('@' in v_email) < 2 or length(v_email) > 320 then
    raise exception 'Invalid email';
  end if;

  select count(*) into v_active
    from public.redesign_email_magic_links
    where email = v_email and consumed_at is null and expires_at > now();
  if v_active >= 5 then
    raise exception 'Too many pending links for this email — try again later';
  end if;

  v_token := translate(encode(extensions.gen_random_bytes(24), 'base64'), '+/=', '-_');
  insert into public.redesign_email_magic_links (token, email, expires_at, client_id)
    values (v_token, v_email, now() + interval '30 minutes', p_client_id);

  return v_token;
end;
$$;
grant execute on function public.issue_magic_link(text, uuid) to anon, authenticated;

-- consume_magic_link: on a never-seen email, bind to the REQUESTER's
-- client_id (recorded on the token) instead of the clicking device's.
-- Returning users still resolve to their existing canonical id.
create or replace function public.consume_magic_link(
  p_token text,
  p_local_client_id uuid
)
returns table (
  client_id uuid,
  email     text
)
language plpgsql
security definer
set search_path = public
as $$
#variable_conflict use_column
declare
  v_email     text;
  v_requester uuid;
  v_canonical uuid;
  v_bind      uuid;
begin
  if p_token is null or p_local_client_id is null then
    raise exception 'Missing token or client_id';
  end if;

  select email, client_id into v_email, v_requester
    from public.redesign_email_magic_links
    where token = p_token
      and consumed_at is null
      and expires_at > now()
    for update;
  if v_email is null then
    raise exception 'Link is invalid or has expired';
  end if;

  update public.redesign_email_magic_links
    set consumed_at = now()
    where token = p_token;

  select client_id into v_canonical
    from public.redesign_kid_email_links
    where email = v_email;
  if v_canonical is not null then
    update public.redesign_kid_email_links set updated_at = now() where email = v_email;
    update public.redesign_kid_profiles set last_seen_at = now() where client_id = v_canonical;
    return query select v_canonical, v_email;
    return;
  end if;

  -- First bind: prefer the REQUESTING device (it holds the history); fall
  -- back to the clicking device only when an old client issued the link
  -- without a requester id.
  v_bind := coalesce(v_requester, p_local_client_id);
  insert into public.redesign_kid_profiles (client_id)
    values (v_bind)
    on conflict (client_id) do update set last_seen_at = now();
  insert into public.redesign_kid_email_links (email, client_id)
    values (v_email, v_bind);

  return query select v_bind, v_email;
end;
$$;
grant execute on function public.consume_magic_link(text, uuid) to anon, authenticated;
