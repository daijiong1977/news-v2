-- Magic-link via email — third identity entry point for kids without
-- a Google account. issue_magic_link returns a token; client emails
-- the link via send-email-v2; user clicks → consume_magic_link binds
-- email→client_id (or returns the existing canonical id).
--
-- Two notes for re-application:
--   * gen_random_bytes lives in `extensions` schema on Supabase (the
--     SECURITY DEFINER + search_path=public combo can't see it
--     unqualified — see docs/gotchas.md for the gotcha log)
--   * Rate limit: max 5 active links per email at any time. Prevents
--     accidental inbox flooding without needing a separate quota table.

create table if not exists public.redesign_email_magic_links (
  token       text primary key,
  email       text not null,
  expires_at  timestamptz not null,
  consumed_at timestamptz,
  created_at  timestamptz not null default now()
);

create index if not exists idx_email_magic_links_email_active
  on public.redesign_email_magic_links (email, created_at desc)
  where consumed_at is null;

alter table public.redesign_email_magic_links enable row level security;

drop policy if exists email_magic_no_direct on public.redesign_email_magic_links;
create policy email_magic_no_direct on public.redesign_email_magic_links
  for all using (false) with check (false);

create or replace function public.issue_magic_link(p_email text)
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
    where email = v_email
      and consumed_at is null
      and expires_at > now();
  if v_active >= 5 then
    raise exception 'Too many pending links for this email — try again later';
  end if;

  v_token := translate(encode(extensions.gen_random_bytes(24), 'base64'), '+/=', '-_');
  insert into public.redesign_email_magic_links (token, email, expires_at)
    values (v_token, v_email, now() + interval '30 minutes');

  return v_token;
end;
$$;
grant execute on function public.issue_magic_link(text) to anon, authenticated;

create or replace function public.consume_magic_link(
  p_token text,
  p_local_client_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_canonical uuid;
begin
  if p_token is null or p_local_client_id is null then
    raise exception 'Missing token or client_id';
  end if;

  select email into v_email
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
    return v_canonical;
  end if;

  insert into public.redesign_kid_profiles (client_id)
    values (p_local_client_id)
    on conflict (client_id) do update set last_seen_at = now();
  insert into public.redesign_kid_email_links (email, client_id)
    values (v_email, p_local_client_id);

  return p_local_client_id;
end;
$$;
grant execute on function public.consume_magic_link(text, uuid) to anon, authenticated;
