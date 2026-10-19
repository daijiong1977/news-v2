// Actual PostgreSQL (WASM), isolated in memory; never connects to production.
import { PGlite } from 'npm:@electric-sql/pglite@0.3.14';
import { validateBundle } from './bundle.ts';
function assert(value: unknown): asserts value { if (!value) throw Error('assertion failed'); }
Deno.test('transaction: DB/search/cadence replay, superseded revision and rollback', async () => {
  const db = new PGlite();
  try {
    // Contract fixture for verified live columns; not the incompatible April schema.
    await db.exec(`
      create role anon; create role authenticated; create role service_role;
      create schema storage;
      create schema auth; create function auth.uid() returns uuid language sql as 'select null::uuid';
      create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
      create table storage.objects(id uuid, bucket_id text,name text);
      create table redesign_runs(id uuid primary key,run_date date,started_at timestamptz,finished_at timestamptz,status text,notes text);
      create table redesign_stories(id uuid primary key default gen_random_uuid(),run_id uuid references redesign_runs(id),
        category text,story_slot integer,published_date date,source_name text,source_url text,source_title text,
        payload_path text,payload_story_id text,archived boolean,primary_image_local text,primary_image_url text,primary_image_credit text,
        interest_importance integer,safety_violence integer,safety_sexual integer,safety_substance integer,
        safety_language integer,safety_fear integer,safety_adult_themes integer,safety_distress integer,
        safety_bias integer,safety_total integer,safety_verdict text,vet_flags jsonb,
        unique(published_date,category,story_slot));
      create table redesign_search_index(story_id text, published_date date,category text,level text,title text,
        summary text,why text,keywords text[],image_url text,source_name text,updated_at timestamptz default now(),
        unique(story_id,level));
      create table redesign_source_configs(id integer primary key,cadence_days integer,last_used_at date,next_pickup_at date);
    `);
    const migration = await Deno.readTextFile(new URL('../../migrations/20261001_bot_publication_handoff.sql', import.meta.url));
    await db.exec(migration);
    const path = Deno.env.get('KIDSNEWS_TEST_BUNDLE');
    if (!path) throw Error('KIDSNEWS_TEST_BUNDLE required');
    const bundle = await validateBundle(await Deno.readFile(path));
    for (const item of bundle.usage) await db.query('insert into redesign_source_configs(id,cadence_days) values($1,7)', [item.source_id]);
    const owner = crypto.randomUUID();
    await db.query('select claim_kidsnews_publication_worker($1)', [owner]);
    const commit = (manifest = bundle.manifest, usage = bundle.usage) => db.query(
      'select commit_kidsnews_publication($1,$2::jsonb,$3::jsonb,$4::jsonb,$5::jsonb) as result',
      [owner, JSON.stringify(manifest), JSON.stringify(bundle.stories), JSON.stringify(bundle.search), JSON.stringify(usage)]);
    await commit(); await commit();
    assert((await db.query<{n: number}>('select count(*)::int n from redesign_stories')).rows[0].n === 9);
    assert((await db.query<{n: number}>('select count(*)::int n from redesign_search_index')).rows[0].n === 27);
    assert((await db.query<{n: number}>('select count(*)::int n from redesign_runs')).rows[0].n === 1);
    assert((await db.query<{n: number}>('select count(*)::int n from redesign_source_configs where next_pickup_at=last_used_at+7')).rows[0].n === bundle.usage.length);
    let failed = false;
    try { await commit({...bundle.manifest, package_id: 'b'.repeat(64), run_id: crypto.randomUUID()}); } catch { failed = true; }
    assert(failed);
    failed = false;
    try {
      await commit({...bundle.manifest, package_id: 'c'.repeat(64), run_id: crypto.randomUUID(),
        started_at: '2099-01-01T00:00:00Z'}, [{source_id: -1, used_date: '1900-01-01'}]);
    } catch { failed = true; }
    assert(failed);
    // A bad usage record occurs after story/search upserts, all of which must roll back.
    assert((await db.query<{n: number}>('select count(*)::int n from redesign_runs')).rows[0].n === 1);
    assert((await db.query<{n: number}>('select count(*)::int n from kidsnews_publication_receipts')).rows[0].n === 1);
  } finally { await db.close(); }
});
