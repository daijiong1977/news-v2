-- Opt-in schema/RPC only. NO cron, function deployment, or production content writes.
-- Activate only after live schema verification and shadow acceptance.
create table if not exists public.kidsnews_publication_receipts (
  package_id text primary key check (package_id ~ '^[a-f0-9]{64}$'),
  run_id uuid not null, run_date date not null, revision timestamptz not null,
  committed_at timestamptz not null default now()
);
alter table public.kidsnews_publication_receipts enable row level security;
revoke all on public.kidsnews_publication_receipts from anon, authenticated;
grant all on public.kidsnews_publication_receipts to service_role;

create table if not exists public.kidsnews_publication_worker (
  singleton boolean primary key default true check (singleton),
  owner uuid, expires_at timestamptz not null default '-infinity'
);
insert into public.kidsnews_publication_worker(singleton) values(true) on conflict do nothing;
alter table public.kidsnews_publication_worker enable row level security;
revoke all on public.kidsnews_publication_worker from anon, authenticated;
grant all on public.kidsnews_publication_worker to service_role;

create or replace function public.claim_kidsnews_publication_worker(p_owner uuid, p_release boolean default false)
returns boolean language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if p_release then
    update kidsnews_publication_worker set owner=null, expires_at='-infinity' where owner=p_owner;
  else
    update kidsnews_publication_worker set owner=p_owner, expires_at=now()+interval '5 minutes'
    where singleton and (expires_at < now() or owner=p_owner);
  end if;
  return found;
end $$;
revoke all on function public.claim_kidsnews_publication_worker(uuid, boolean) from public, anon, authenticated;
grant execute on function public.claim_kidsnews_publication_worker(uuid, boolean) to service_role;

create or replace function public.commit_kidsnews_publication(
  p_owner uuid, p_manifest jsonb, p_stories jsonb, p_search jsonb, p_usage jsonb)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare
  d date := (p_manifest->>'date')::date;
  revision timestamptz := (p_manifest->>'started_at')::timestamptz;
  rid uuid := (p_manifest->>'run_id')::uuid;
  package text := p_manifest->>'package_id';
  story jsonb; score jsonb; search_row jsonb; usage_row jsonb;
begin
  perform 1 from kidsnews_publication_worker where owner=p_owner and expires_at>now() for update;
  if not found then raise exception 'worker lease missing'; end if;
  perform pg_advisory_xact_lock(hashtext('kidsnews-publication'));
  if exists(select 1 from kidsnews_publication_receipts where package_id=package) then
    return jsonb_build_object('already_committed', true);
  end if;
  if exists(select 1 from kidsnews_publication_receipts r where r.run_date=d and r.revision >= (p_manifest->>'started_at')::timestamptz) then
    raise exception 'superseded or ambiguous publication revision';
  end if;
  if jsonb_array_length(p_stories) not between 1 and 9 or jsonb_array_length(p_search) != jsonb_array_length(p_stories)*3 then
    raise exception 'invalid publication counts';
  end if;
  insert into redesign_runs(id, run_date, started_at, finished_at, status, notes)
    values(rid,d,revision,now(),'completed','Bot ZIP verified by scheduled finalizer');
  for story in select value from jsonb_array_elements(p_stories) loop
    if story->>'published_date' != d::text or story->>'category' not in ('News','Science','Fun')
       or (story->>'facts_supported')::boolean is distinct from true
       or (story->>'event_clear')::boolean is distinct from true then
      raise exception 'unqualified publication story';
    end if;
    score := story->'safety_scores';
    insert into redesign_stories(run_id, category, story_slot, published_date,
      source_name,source_url,source_title,payload_path,payload_story_id,archived,
      primary_image_local,primary_image_url,primary_image_credit,interest_importance,
      safety_violence,safety_sexual,safety_substance,safety_language,safety_fear,
      safety_adult_themes,safety_distress,safety_bias,safety_total,safety_verdict,vet_flags)
    values(rid,story->>'category',(story->>'story_slot')::integer,d,
      story->>'source_name',story->>'source_url',story->>'source_title',story->>'payload_path',story->>'payload_story_id',false,
      story->>'primary_image_local',story->>'primary_image_url',story->>'source_name',(story->>'importance')::integer,
      (score->>'violence')::numeric::integer,(score->>'sexual')::numeric::integer,
      (score->>'substance')::numeric::integer,(score->>'language')::numeric::integer,
      (score->>'fear')::numeric::integer,(score->>'adult_themes')::numeric::integer,
      (score->>'distress')::numeric::integer,(score->>'bias')::numeric::integer,
      (select sum(value::numeric)::integer from jsonb_each_text(score)), 'SAFE',
      jsonb_build_array('bot_modifier_facts_supported','topic:'||(story->>'topic')))
    on conflict(published_date,category,story_slot) do update set
      run_id=excluded.run_id,source_name=excluded.source_name,source_url=excluded.source_url,
      source_title=excluded.source_title,payload_path=excluded.payload_path,payload_story_id=excluded.payload_story_id,
      archived=false,primary_image_local=excluded.primary_image_local,primary_image_url=excluded.primary_image_url,
      primary_image_credit=excluded.primary_image_credit,
      interest_importance=excluded.interest_importance,safety_violence=excluded.safety_violence,
      safety_sexual=excluded.safety_sexual,safety_substance=excluded.safety_substance,
      safety_language=excluded.safety_language,safety_fear=excluded.safety_fear,
      safety_adult_themes=excluded.safety_adult_themes,safety_distress=excluded.safety_distress,
      safety_bias=excluded.safety_bias,safety_total=excluded.safety_total,safety_verdict=excluded.safety_verdict,
      vet_flags=excluded.vet_flags;
  end loop;
  -- Full three-section package replaces that date, never unrelated dates.
  delete from redesign_stories s where s.published_date=d
    and not exists(select 1 from jsonb_array_elements(p_stories) j where j->>'payload_story_id'=s.payload_story_id);
  delete from redesign_search_index s where s.published_date=d
    and not exists(select 1 from jsonb_array_elements(p_stories) j where j->>'payload_story_id'=s.story_id);
  for search_row in select value from jsonb_array_elements(p_search) loop
    insert into redesign_search_index(story_id,published_date,category,level,title,summary,why,keywords,image_url,source_name)
    values(search_row->>'story_id',d,search_row->>'category',search_row->>'level',search_row->>'title',
      search_row->>'summary',search_row->>'why',
      array(select jsonb_array_elements_text(search_row->'keywords')),search_row->>'image_url',search_row->>'source_name')
    on conflict(story_id,level) do update set published_date=excluded.published_date,
      category=excluded.category,title=excluded.title,summary=excluded.summary,why=excluded.why,
      keywords=excluded.keywords,image_url=excluded.image_url,source_name=excluded.source_name,updated_at=now();
  end loop;
  for usage_row in select value from jsonb_array_elements(p_usage) loop
    if usage_row->>'used_date' != d::text or not exists(
      select 1 from jsonb_array_elements(p_stories) j where j->>'source_config_id'=usage_row->>'source_id') then
      raise exception 'invalid source usage';
    end if;
    update redesign_source_configs set last_used_at=d,
      next_pickup_at=d+greatest(1,coalesce(cadence_days,1))
      where id=(usage_row->>'source_id')::integer and (last_used_at is null or last_used_at <= d);
  end loop;
  insert into kidsnews_publication_receipts(package_id,run_id,run_date,revision) values(package,rid,d,revision);
  return jsonb_build_object('already_committed',false,'stories',jsonb_array_length(p_stories));
end $$;
revoke all on function public.commit_kidsnews_publication(uuid,jsonb,jsonb,jsonb,jsonb) from public, anon, authenticated;
grant execute on function public.commit_kidsnews_publication(uuid,jsonb,jsonb,jsonb,jsonb) to service_role;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('kidsnews-publication-pending','kidsnews-publication-pending',false,20971520,
       array['application/zip','application/json']) on conflict(id) do nothing;
-- Empty allow-list: no new uploader is authorized by applying this migration.
create table if not exists public.kidsnews_publication_uploaders(user_id uuid primary key);
alter table public.kidsnews_publication_uploaders enable row level security;
revoke all on public.kidsnews_publication_uploaders from anon, authenticated;
grant all on public.kidsnews_publication_uploaders to service_role;
create or replace function public.is_kidsnews_publication_uploader()
returns boolean language sql stable security definer set search_path=public,pg_temp as $$
  select exists(select 1 from kidsnews_publication_uploaders where user_id=auth.uid());
$$;
revoke all on function public.is_kidsnews_publication_uploader() from public,anon;
grant execute on function public.is_kidsnews_publication_uploader() to authenticated;
create policy kidsnews_pending_insert on storage.objects for insert to authenticated
with check(bucket_id='kidsnews-publication-pending' and public.is_kidsnews_publication_uploader()
  and name ~ '^pending/[a-f0-9]{64}\.(zip|ready\.json)$');
create policy kidsnews_pending_read on storage.objects for select to authenticated
using(bucket_id='kidsnews-publication-pending' and public.is_kidsnews_publication_uploader()
  and name ~ '^pending/[a-f0-9]{64}\.(zip|ready\.json)$');
-- No UPDATE/DELETE, no done-marker permission, no table-write rights granted to the Bot.
-- Intentionally NO pg_cron schedule: operator activates the scheduled function after acceptance.
