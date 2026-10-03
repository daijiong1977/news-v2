"""Automatic, private paired SQL preparation for an approved reader edition.

Never modifies Storage/latest, legacy full_round, or schema. Backend-only commit
requires an explicit CLI flag; preparation is read-only. Resume keeps the original
before-image, even if delivery was interrupted. Do not put state under Bot work/.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from zoneinfo import ZoneInfo

import requests
from .agent_shadow import run_lock
from .publication_bundle import encoded, sha
from .website_release import check_reader

TABLES=('redesign_runs','redesign_stories','redesign_search_index','redesign_source_configs')
PROJECT='lfknsvavhiqrsasdfyrs'
PAIR_FILES=('before.json','after.json','scope.json','apply.sql','rollback.sql')


def timestamp(value):
    value=re.sub(r'\.(\d+)(?=[+-])',lambda m:'.'+m.group(1).ljust(6,'0'),value.replace('Z','+00:00'))
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def canonical(rows,table):
    result=[]
    for original in rows:
        row={k:v for k,v in original.items() if not(table=='redesign_search_index' and k in ('doc_tsv','updated_at'))}
        for key,value in row.items():
            if key.endswith('_at') and isinstance(value,str) and 'T' in value:
                normalized=timestamp(value).isoformat()
                row[key]=re.sub(r'\.(\d+)\+00:00',lambda m:'.'+m.group(1).rstrip('0')+'+00:00',normalized)
        result.append(row)
    return sorted(result,key=lambda r:r['id'])


def private_write(path,data):
    path=Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as temp:
        os.fchmod(temp.fileno(),0o600);temp.write(data);temp.flush();os.fsync(temp.fileno())
        name=temp.name
    os.replace(name,path)


def literal(value):
    text=encoded(value).decode()
    tag='$j'+sha(text.encode())[:20]+'$'
    if tag in text:raise ValueError('SQL delimiter collision')
    return tag+text+tag+'::jsonb'


def identifier(value):
    if not re.fullmatch(r'[a-z][a-z0-9_]*',value):raise ValueError('Unsafe column name')
    return '"'+value+'"'


def condition(table,scope):
    if table=='redesign_runs':return "id='"+scope['run_id']+"'::uuid"
    if table=='redesign_source_configs':return 'id in ('+','.join(map(str,scope['source_ids']))+')' if scope['source_ids'] else 'false'
    return "published_date='"+scope['date']+"'::date"


def guard(table,rows,scope):
    expr="to_jsonb(t)-'doc_tsv'-'updated_at'" if table=='redesign_search_index' else 'to_jsonb(t)'
    return (f"IF (select coalesce(jsonb_agg({expr} order by t.id),'[]'::jsonb) from public.{table} t where {condition(table,scope)})"
            f" <> {literal(canonical(rows,table))} THEN RAISE EXCEPTION 'Changed records: {table}; preserve original recovery files'; END IF;")


def upsert(table,rows,restore=False):
    statements=[]
    for row in rows:
        columns=[c for c in row if restore or c!='doc_tsv']
        names=','.join(identifier(c) for c in columns)
        updates=','.join(identifier(c)+'=excluded.'+identifier(c) for c in columns if c!='id')
        statements.append(f'insert into public.{table} ({names}) select {names} from jsonb_populate_record(null::public.{table},{literal(row)}) '
                          f'on conflict(id) do update set {updates};')
    return '\n'.join(statements)


def sql_pair(before,after,scope):
    block='$b'+sha(encoded([before,after,scope]))[:20]+'$'
    if block in encoded([before,after,scope]).decode():raise ValueError('SQL block delimiter collision')
    def transaction(expected,target,restore=False):
        commands=['begin;',"set local lock_timeout='5s';","set local statement_timeout='30s';",
                  'lock table '+','.join('public.'+t for t in TABLES)+' in share row exclusive mode;',
                  'DO '+block+' BEGIN '+''.join(guard(t,expected[t],scope) for t in TABLES)+' END '+block+';']
        if not restore:commands.append(upsert('redesign_runs',target['redesign_runs']))
        commands.append(upsert('redesign_stories',target['redesign_stories']))
        if restore:
            new_ids={r['id'] for r in expected['redesign_stories']}-{r['id'] for r in target['redesign_stories']}
            if new_ids:commands.append('delete from public.redesign_stories where id in ('+','.join("'"+str(uuid.UUID(i))+"'::uuid" for i in sorted(new_ids))+');')
            commands.append('alter table public.redesign_search_index disable trigger redesign_search_index_tsv_update;')
        commands.append(f"delete from public.redesign_search_index where {condition('redesign_search_index',scope)};")
        commands.append(upsert('redesign_search_index',target['redesign_search_index'],restore))
        if restore:commands.append('alter table public.redesign_search_index enable trigger redesign_search_index_tsv_update;')
        commands.append(upsert('redesign_source_configs',target['redesign_source_configs']))
        if restore:commands.append(f"delete from public.redesign_runs where {condition('redesign_runs',scope)};")
        commands+=['DO '+block+' BEGIN '+''.join(guard(t,target[t],scope) for t in TABLES)+' END '+block+';','commit;']
        return '\n'.join(commands)
    return transaction(before,after),transaction(after,before,True)


def load_artifact(root):
    root=Path(root)
    raw={n:(root/n).read_bytes() for n in ('reader.zip','latest-manifest.json','records.json')}
    manifest=json.loads(raw['latest-manifest.json']);records=json.loads(raw['records.json'])
    files=check_reader(raw['reader.zip'],manifest)
    day=date.fromisoformat(manifest['version']).isoformat()
    expected={f'{day}-{cat}-{i}' for cat in ('news','science','fun') for i in range(1,4)}
    if len(records)!=9 or {r['payload_story_id'] for r in records}!=expected:raise ValueError('Exactly nine fixed date slots required')
    source_ids=sorted({r['source_config_id'] for r in records if r.get('source_config_id') is not None})
    if any(type(i) is not int or i<=0 for i in source_ids):raise ValueError('Invalid source ID')
    rid=str(uuid.uuid5(uuid.NAMESPACE_URL,'kidsnews-archive:'+manifest['zip_sha256']))
    scope={'date':day,'source_ids':source_ids,'run_id':rid,'zip_sha256':manifest['zip_sha256'],
           'artifact_hashes':{n:sha(b) for n,b in raw.items()}}
    return scope,manifest,records,files


def plan_rows(scope,manifest,records,files,snapshot):
    before=snapshot['rows']
    if set(before)!=set(TABLES) or before['redesign_runs']:raise ValueError('Wrong snapshot or release already recorded; resume original state')
    if sorted(r['id'] for r in before['redesign_source_configs'])!=scope['source_ids']:raise ValueError('Missing source configs')
    allowed={r['payload_story_id'] for r in records}
    for table,key in (('redesign_stories','payload_story_id'),('redesign_search_index','story_id')):
        if any(r['published_date']!=scope['date'] or r[key] not in allowed for r in before[table]):raise ValueError('Foreign day/slot in snapshot')
    stamp=manifest['packed_at'];timestamp(stamp);rid=scope['run_id']
    oldstories={r['payload_story_id']:r for r in before['redesign_stories']}
    oldsearch={(r['story_id'],r['level']):r for r in before['redesign_search_index']}
    after={t:[] for t in TABLES}
    after['redesign_runs']=[{'id':rid,'run_date':scope['date'],'started_at':stamp,'finished_at':stamp,'created_at':stamp,
        'status':'completed','deepseek_calls':None,'http_fetches':None,
        'notes':'Pinned reader DB handoff SHA256 '+scope['zip_sha256'],
        'telemetry':{'archive_backfill':True,'usage_known':False}}]
    for rec in records:
        sid=rec['payload_story_id'];cat=rec['category'];slot=rec['story_slot']
        if cat not in ('News','Science','Fun') or sid!=f"{scope['date']}-{cat.lower()}-{slot}" or rec['published_date']!=scope['date']:
            raise ValueError('Record category/slot/date mismatch')
        if rec.get('event_clear') is not True or type(rec.get('facts_supported')) is not bool:raise ValueError('Missing qualification evidence')
        if not rec['facts_supported'] and not rec.get('fact_warning'):raise ValueError('Missing fact warning')
        score=rec['safety_scores']
        from .news_rss_core import SAFETY_DIMS,evaluate_rewriter_safety
        if set(score)!=set(SAFETY_DIMS) or evaluate_rewriter_safety({'safety':score},category=cat)['verdict']!='PASS':raise ValueError('Unsafe record')
        if any(type(v) is not int for v in score.values()):raise ValueError('Integer safety scores required')
        row=dict(oldstories.get(sid,{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,rid+sid)),'created_at':stamp,'archived':False}))
        row.update(run_id=rid,category=cat,story_slot=slot,published_date=scope['date'],payload_story_id=sid,
            source_name=rec['source_name'],source_url=rec['source_url'],source_title=rec['source_title'],source_published_at=None,
            winner_slot=None,used_backup=False,backup_for_source=None,primary_image_url=rec.get('primary_image_url'),
            primary_image_local=rec['primary_image_local'],primary_image_credit=rec['source_name'],payload_path=rec['payload_path'],
            interest_importance=rec['importance'],interest_fun_factor=None,interest_kid_appeal=None,interest_peak=None,interest_verdict=None,
            safety_total=sum(score.values()),safety_verdict='SAFE',
            vet_flags=['bot_modifier_self_check','writer:'+rec.get('writer_provider','unknown'),'topic:'+rec['topic']])
        row.update({'safety_'+k:v for k,v in score.items()})
        for level in ('easy','middle','cn'):
            listing=json.loads(files[f'payloads/articles_{cat.lower()}_{level}.json'])['articles']
            if {c['id'] for c in listing}!={f"{scope['date']}-{cat.lower()}-{i}" for i in range(1,4)}:raise ValueError('Listing IDs mismatch')
            card=next(c for c in listing if c['id']==sid)
            body=json.loads(files[f'article_payloads/payload_{sid}/{level}.json']) if level!='cn' else card
            if level!='cn' and body['source_url']!=rec['source_url']:raise ValueError('Source URL mismatch')
            image=card.get('image_url','').lstrip('/')
            if image and (not image.startswith('article_images/') or image not in files or image!=rec['primary_image_local'].lstrip('/')):raise ValueError('Image mismatch')
            if level=='easy' and card.get('source_published_at'):row['source_published_at']=parsedate_to_datetime(card['source_published_at']).astimezone(timezone.utc).isoformat()
            lev='zh' if level=='cn' else level
            search=dict(oldsearch.get((sid,lev),{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,rid+sid+lev)),'created_at':stamp}))
            search.update(story_id=sid,published_date=scope['date'],category=cat,level=lev,title=card['title'],summary=body['summary'],
                why=body.get('why_it_matters',''),keywords=[k['term'] for k in body.get('keywords',[])],
                image_url=card.get('image_url',''),source_name=rec['source_name'],updated_at=stamp)
            after['redesign_search_index'].append(search)
        after['redesign_stories'].append(row)
    for old in before['redesign_source_configs']:
        row=dict(old);used=timestamp(stamp)
        if old.get('last_used_at'):used=max(used,timestamp(old['last_used_at']))
        used_day=max(date.fromisoformat(scope['date']),used.astimezone(ZoneInfo('America/New_York')).date())
        next_day=(used_day+timedelta(days=max(1,old.get('cadence_days') or 1))).isoformat()
        row.update(last_used_at=used.isoformat(),next_pickup_at=max(next_day,old.get('next_pickup_at') or next_day))
        after['redesign_source_configs'].append(row)
    return before,after


def verify_prepared(root):
    root=Path(root)
    if not (root/'prepared.json').is_file():raise ValueError('Missing complete SQL pair marker; partial preparation')
    manifest=json.loads((root/'prepared.json').read_bytes())
    if set(manifest['files'])!=set(PAIR_FILES):raise ValueError('Incomplete SQL pair manifest')
    for name,digest in manifest['files'].items():
        if sha((root/name).read_bytes())!=digest:raise ValueError('Prepared file hash mismatch: '+name)
    return manifest


def _prepare(artifact,root,client):
    scope,manifest,records,files=load_artifact(artifact)
    if (root/'prepared.json').exists():
        saved=verify_prepared(root)
        if saved['artifact_hashes']!=scope['artifact_hashes']:raise ValueError('Different release; use a new private state directory')
        return saved
    if any(p.name not in ('.lock','.run.lock') for p in root.iterdir()):raise ValueError('Interrupted/partial preparation: preserve original snapshot; do not recapture')
    snapshot=client.snapshot(scope)
    before,after=plan_rows(scope,manifest,records,files,snapshot)
    apply_sql,rollback_sql=sql_pair(before,after,scope)
    values={'before.json':encoded(before),'after.json':encoded(after),'scope.json':encoded(scope),
            'apply.sql':apply_sql.encode(),'rollback.sql':rollback_sql.encode()}
    for name,data in values.items():private_write(root/name,data)
    ready={**scope,'schema_version':1,'files':{n:sha(b) for n,b in values.items()},'backup_scope':'affected business rows; not full database or Storage backup'}
    private_write(root/'prepared.json',encoded(ready))
    return verify_prepared(root)


def private_root(root):
    root=Path(root).resolve()
    # SQL before-images must never be swept into the Bot's logs Git branch.
    repo=Path(__file__).resolve().parent.parent
    if root==repo or repo in root.parents or 'work' in root.parts:raise ValueError('Use private state outside repo/work; SQL backups must not enter Git logs')
    root.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(root,0o700)
    return root


def prepare(artifact,root,client):
    root=private_root(root)
    with run_lock(root):return _prepare(artifact,root,client)


def commit(artifact,root,client):
    root=private_root(root)
    with run_lock(root):
        ready=_prepare(artifact,root,client)  # ALWAYS generate both before first write.
        execution=root/'execution.json'
        if execution.exists():
            previous=json.loads(execution.read_bytes())
            if previous.get('status')=='committed':return ready
            raise ValueError('SQL outcome uncertain; inspect DB with original pair, never blindly resend')
        verify_prepared(root)
        client.verify_archive(artifact)  # DB cannot claim a package that was not archived.
        private_write(execution,encoded({'status':'attempting','zip_sha256':ready['zip_sha256']}))
        client.execute((root/'apply.sql').read_text())
        private_write(execution,encoded({'status':'committed','zip_sha256':ready['zip_sha256']}))
        return ready


def rollback(root,client):
    root=private_root(root)
    with run_lock(root):
        ready=verify_prepared(root)
        execution=root/'execution.json'
        previous=json.loads(execution.read_bytes()) if execution.exists() else {}
        if previous.get('status')=='rolled_back':return ready
        if previous.get('status')!='committed':raise ValueError('Uncertain SQL outcome; verify before rollback')
        private_write(execution,encoded({'status':'rollback_attempting','zip_sha256':ready['zip_sha256']}))
        client.execute((root/'rollback.sql').read_text())
        private_write(execution,encoded({'status':'rolled_back','zip_sha256':ready['zip_sha256']}))
        return ready


class ManagementClient:
    def __init__(self,project,token):
        if project!=PROJECT:raise ValueError('Unsupported Supabase project')
        self.project=project;self.token=token
    def query(self,query):
        response=requests.post(f'https://api.supabase.com/v1/projects/{self.project}/database/query',
            headers={'Authorization':'Bearer '+self.token},json={'query':query},timeout=60)
        response.raise_for_status();return response.json()
    def snapshot(self,scope):
        # One read-only statement captures all four before-images together.
        parts=[f"select '{t}' as name,coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) as rows from public.{t} t where {condition(t,scope)}" for t in TABLES]
        return {'columns':{},'rows':{r['name']:r['rows'] for r in self.query(' union all '.join(parts))}}
    def execute(self,sql):return self.query(sql)
    def verify_archive(self,artifact):
        scope,manifest,_,files=load_artifact(artifact)
        base=f'https://{self.project}.supabase.co/storage/v1/object/public/redesign-daily-content'
        targets={scope['date']+'.zip':(Path(artifact)/'reader.zip').read_bytes(),
                 scope['date']+'-manifest.json':encoded(manifest)}
        targets.update({scope['date']+'/'+name:data for name,data in files.items()
                        if name.startswith(('payloads/','article_payloads/','article_images/'))})
        for name,expected in targets.items():
            response=requests.get(base+'/'+name,params={'sql_pair_verify':scope['zip_sha256']},
                                  timeout=30,allow_redirects=False)
            response.raise_for_status()
            if name.endswith('-manifest.json'):
                matches=response.json()==manifest
            else:matches=sha(response.content)==sha(expected)
            if not matches:raise ValueError('Dated archive readback mismatch; no DB commit: '+name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','commit','rollback'))
    parser.add_argument('--artifact-dir',type=Path)
    parser.add_argument('--state-dir',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    try:
        if args.command in ('commit','rollback') and not args.execute:raise ValueError('Writes require explicit --execute; prepare is read-only')
        if args.command!='rollback' and not args.artifact_dir:raise ValueError('--artifact-dir required')
        client=ManagementClient(PROJECT,os.environ['SUPABASE_ACCESS_TOKEN'])
        if args.command=='rollback':result=rollback(args.state_dir,client)
        else:result=(commit if args.command=='commit' else prepare)(args.artifact_dir,args.state_dir,client)
        print(json.dumps({'ok':True,'date':result['date'],'run_id':result['run_id'],
            'state_dir':str(args.state_dir),'sql_pair_verified':True,'operation':args.command,
            'committed':args.command=='commit','rolled_back':args.command=='rollback'}));return 0
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc) if isinstance(exc,ValueError) else type(exc).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
