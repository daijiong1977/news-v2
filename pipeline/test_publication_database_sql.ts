// Offline PostgreSQL execution only; no network API, live project, or credentials.
import { PGlite } from 'npm:@electric-sql/pglite@0.3.14';
const root=Deno.args[0];
const read=async(name:string)=>JSON.parse(await Deno.readTextFile(root+'/'+name));
const before=await read('before.json');const scope=await read('scope.json');
const db=new PGlite();
let assertions=0;
function check(value:unknown){if(!value)throw Error('SQL regression failed');assertions++;}
try{
 await db.exec(`
 create table redesign_runs(id uuid primary key,run_date date,started_at timestamptz,finished_at timestamptz,status text,
 deepseek_calls int,http_fetches int,notes text,created_at timestamptz,telemetry jsonb);
 create table redesign_stories(id uuid primary key,run_id uuid references redesign_runs(id),category text,story_slot int,
 published_date date,source_name text,source_url text,source_title text,source_published_at timestamptz,winner_slot text,
 used_backup bool,backup_for_source text,safety_violence int,safety_sexual int,safety_substance int,safety_language int,
 safety_fear int,safety_adult_themes int,safety_distress int,safety_bias int,safety_total int,safety_verdict text,
 interest_importance int,interest_fun_factor int,interest_kid_appeal int,interest_peak int,interest_verdict text,
 vet_flags jsonb,primary_image_url text,primary_image_local text,primary_image_credit text,payload_path text,
 payload_story_id text,created_at timestamptz,archived bool,unique(published_date,category,story_slot));
 create table redesign_search_index(id uuid primary key,story_id text,published_date date,category text,level text,title text,
 summary text,why text,keywords text[],image_url text,source_name text,doc_tsv tsvector,created_at timestamptz,updated_at timestamptz,
 unique(story_id,level));
 create table redesign_source_configs(id int primary key,cadence_days int,last_used_at timestamptz,next_pickup_at date);
 create table reading_progress(id int primary key,value text);
 insert into reading_progress values(1,'untouched');
 create function redesign_search_index_tsv_trigger() returns trigger language plpgsql as $$
 begin NEW.doc_tsv:=to_tsvector('english',coalesce(NEW.title,'')); NEW.updated_at:=now();return NEW;end $$;
 create trigger redesign_search_index_tsv_update before insert or update on redesign_search_index for each row
 execute function redesign_search_index_tsv_trigger();
 `);
 for(const table of Object.keys(before)){
  if(before[table].length)await db.query('insert into '+table+' select * from jsonb_populate_recordset(null::'+table+',$1::jsonb)',[JSON.stringify(before[table])]);
 }
 const initial=(await db.query('select to_jsonb(t) row from redesign_source_configs t order by id')).rows;
 const apply=await Deno.readTextFile(root+'/apply.sql');const rollback=await Deno.readTextFile(root+'/rollback.sql');
 await db.exec(apply);
 check((await db.query('select count(*)::int n from redesign_stories')).rows[0].n===9);
 check((await db.query('select count(*)::int n from redesign_search_index')).rows[0].n===27);
 check((await db.query('select count(*)::int n from redesign_search_index where doc_tsv is not null')).rows[0].n===27);
 check((await db.query('select value from reading_progress')).rows[0].value==='untouched');
 await db.exec(rollback);
 check((await db.query('select count(*)::int n from redesign_stories')).rows[0].n===0);
 check((await db.query('select count(*)::int n from redesign_runs')).rows[0].n===0);
 check(JSON.stringify((await db.query('select to_jsonb(t) row from redesign_source_configs t order by id')).rows)===JSON.stringify(initial));
 await db.exec(apply);
 await db.exec("update redesign_stories set source_title='another editor' where category='News' and story_slot=1");
 let blocked=false;
 try{await db.exec(rollback);}catch{blocked=true;await db.exec('rollback');}
 check(blocked);
 check((await db.query("select source_title from redesign_stories where category='News' and story_slot=1")).rows[0].source_title==='another editor');
 check((await db.query('select tgenabled from pg_trigger where tgname=\'redesign_search_index_tsv_update\'')).rows[0].tgenabled==='O');
 console.log(JSON.stringify({pass:true,assertions,date:scope.date,mode:'offline_postgres'}));
}finally{await db.close();}
