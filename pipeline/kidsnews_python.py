"""Python orchestrator, JSON stdin/stdout. No Edge Function or AI tool handoff.

Existing website CI remains unchanged. Database/archive are an explicit optional
post-publication stage with private durable backups, SQL pairs and verification.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

import requests

from .agent_shadow import read, write, run_lock
from .cursor_json import CursorJSONProvider
from .kidsnews_api_editor import CachedJSON, edit_groups
from .publication_database import PROJECT, private_root, private_write, load_artifact
from .publication_bundle import encoded, sha


def agent_provider(config):
    """Business logic knows only complete(payload)->JSON, never provider tools."""
    choice = config.get('agent_provider', {'type': 'cursor', 'model': config.get('model')})
    if isinstance(choice, str):
        choice = {'type': choice}
    deepseek = choice.get('type') == 'deepseek'
    if choice.get('type') == 'grok':
        choice = {**choice, 'type':'cursor', 'model':choice.get('model','grok-4.7-high')}
    if choice.get('type') == 'deepseek':
        choice = {**choice, 'type':'http', 'model':choice.get('model','deepseek-flash'),
                  'endpoint':'https://api.deepseek.com/chat/completions', 'key_env':'DEEPSEEK_API_KEY'}
    if choice.get('type') == 'claude':
        from .claude_json import ClaudeJSONProvider
        provider = ClaudeJSONProvider(choice.get('model','sonnet'), choice.get('binary'))
        return provider, {'type':'claude-cli-json', 'model':provider.model}
    if choice.get('type') == 'codex':
        from .codex_json import CodexJSONProvider
        provider = CodexJSONProvider(choice.get('model'), choice.get('binary'), choice.get('reasoning','low'))
        return provider, {'type':'codex-cli-json', 'model':provider.model or 'cli-default (not reported)',
                          'reasoning':provider.reasoning}
    if choice.get('type') == 'cursor':
        provider = CursorJSONProvider(choice.get('model'))
        return provider, {'type': 'cursor-cli-json', 'model': provider.model}
    if choice.get('type') == 'http':
        from urllib.parse import urlsplit
        from .ai_providers.transport import OpenAICompatibleProvider
        endpoint = choice['endpoint']; parts = urlsplit(endpoint)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
            raise ValueError('Agent API requires credential-free HTTPS endpoint')
        model, key_env = choice['model'], choice['key_env']
        if not isinstance(model, str) or not model or not isinstance(key_env, str):
            raise ValueError('Agent model/key_env required')
        delegate = OpenAICompatibleProvider(endpoint=endpoint, api_key=os.environ[key_env])
        class HTTP:
            def complete(self, payload, timeout):
                return delegate.complete({**payload, 'model': model,
                    **({'thinking':{'type':'disabled'}} if deepseek else {}),
                    'response_format': {'type': 'json_object'}, 'max_tokens': 16384}, timeout)
        return HTTP(), {'type': 'http', 'endpoint': endpoint, 'model': model, 'key_env': key_env}
    raise ValueError('Agent provider must be deepseek, grok, codex, claude, cursor or http')


def database_client(config):
    if config.get('database_transport','rest')=='rest':
        from .publication_rest import RestClient
        return RestClient()
    if config.get('database_transport')=='postgres':
        from .publication_postgres import PostgresClient
        return PostgresClient()
    raise ValueError('database_transport must be rest or postgres')


def registry(day, root):
    """Freeze paginated read-only source/history registry; never silently zero history."""
    path = root/'api-registry.json'
    if path.exists():
        if read(path).get('date') != day:
            raise ValueError('Frozen registry belongs to another day')
        return path
    key = os.environ.get('SUPABASE_READ_TOKEN') or os.environ['SUPABASE_SERVICE_KEY']
    headers = {'Authorization': 'Bearer '+key, 'apikey': key}
    def rows(table, params):
        result = []
        for offset in range(0, 10000, 500):
            response = requests.get(f'https://{PROJECT}.supabase.co/rest/v1/{table}',
                headers=headers, params={**params, 'limit': 500, 'offset': offset}, timeout=30)
            response.raise_for_status(); batch = response.json()
            if not isinstance(batch, list):
                raise ValueError('Registry response must be rows')
            result.extend(batch)
            if len(batch) < 500:
                return result
        raise ValueError('Registry pagination budget exhausted')
    start = (date.fromisoformat(day)-timedelta(days=7)).isoformat()
    value = {'date': day,
             'sources': rows('redesign_source_configs', {'select': '*', 'order': 'id.asc'}),
             'history': rows('redesign_stories', {'select': 'id,published_date,category,source_title,source_url,archived',
                 'and': f'(published_date.gte.{start},published_date.lt.{day})', 'order': 'id.asc'})}
    if not value['sources'] or not value['history']:
        raise ValueError('Registry sources/history empty; check access')
    write(path, value); return path


def run_cli(module, *args):
    from .kidsnews_bot import invoke
    return invoke(module, *args)


def prepare_api(root, day, registry_path, provider, identity, all_ai=False, batch_writer=None):
    """DeepSeek normal prepare; Cursor answers ONLY requested format fix JSON."""
    cached = CachedJSON(root, provider, identity)
    batch_cached = cached
    extra = []
    routed = hasattr(provider, 'for_task')
    if all_ai or batch_writer is not None or routed:
        if all_ai and batch_writer is None and not routed and identity.get('type') != 'codex-cli-json':
            raise ValueError('all_ai currently requires explicit Codex provider')
        path = root/'all-ai-providers.json'
        config = {'roles':{role:{'type':'native'} for role in
                  ('rank','editor','write','review','details','detail_review','discovery','image_review')}}
        if routed:
            if batch_writer is not None:
                raise ValueError('Use ai_stages.batch_write instead of also setting batch_writer')
            for stage, role in (('pickup','rank'),('batch_write','write')):
                stage_identity = provider.backends[stage][1]
                if stage_identity['type'] == 'http':
                    config['roles'][role] = {k:stage_identity[k] for k in ('type','endpoint','model','key_env')}
        if batch_writer is not None:
            choice = {'type':batch_writer} if isinstance(batch_writer,str) else batch_writer
            if not isinstance(choice,dict) or choice.get('type') not in {'deepseek','grok','codex','claude'}:
                raise ValueError('batch_writer must be deepseek, grok, codex or claude')
            if set(choice)-{'type','model','reasoning','binary'} or any(not isinstance(v,str) or not v for v in choice.values()):
                raise ValueError('batch_writer accepts only nonempty type/model/reasoning/binary strings; never credentials')
            if choice['type'] == 'codex':
                choice = {'model':'gpt-6.1-sol','reasoning':'medium',**choice}
            batch_provider, batch_identity = agent_provider({'agent_provider':choice})
            frozen = {'selection':choice,'identity':batch_identity}
            batch_path = root/'batch-writer.json'
            if batch_path.exists() and read(batch_path) != frozen:
                raise ValueError('Frozen batch writer changed; use a new directory')
            write(batch_path,frozen)
            from .kidsnews_groups import pin
            pin(root,batch_path)
            if choice['type'] == 'deepseek':
                config['roles']['write'] = {'type':'http','model':batch_identity['model'],
                    'endpoint':batch_identity['endpoint'],'key_env':batch_identity['key_env']}
            else:
                batch_cached = CachedJSON(root,batch_provider,batch_identity,'api-batch-provider.json')
        if path.exists() and read(path) != config:
            raise ValueError('Frozen all-AI provider changed')
        write(path,config)
        extra = ['--providers-config',path]
    for _ in range(24):
        code, result = run_cli('pipeline.kidsnews_bot', '--stage', 'prepare', '--run-dir', root,
                              '--date', day, '--registry', registry_path, *extra)
        if code == 0:
            return result
        if code != 2 or not result.get('read') or not result.get('write_to'):
            raise ValueError('Prepare failed: '+str(result.get('error') or result.get('errors')))
        request = read(Path(result['read']))
        task = request.get('task')
        if not isinstance(task, dict) or not isinstance(task.get('messages'), list):
            raise ValueError('Unsupported prepare handoff; preserve state')
        errors = result.get('errors',[])
        prior = read(Path(result['write_to'])) if Path(result['write_to']).exists() else None
        native_tasks = all_ai or batch_writer is not None or routed
        material = {'task':task,'validation_errors':errors,'previous_answer':prior} if native_tasks else task
        from .agent_shadow_providers import task_role
        is_write = task_role(Path(result['read']).parent.parent.name) == 'write'
        active = batch_cached if is_write else cached
        key = 'prepare-format-'+request['request_id']+('-correction' if prior else '')
        if routed:
            stage = 'format_fix' if prior else 'batch_write' if is_write else 'pickup'
            key = 'stage:'+stage+':'+key
        value = active(root, key,
            ('Follow the supplied task.messages exactly. Return its complete required JSON object. '
             'If a previous answer failed, correct the listed validation errors, preserving IDs and supported facts.'
             if native_tasks else 'Answer the supplied messages as JSON. Correct only the requested malformed answer; preserve content and IDs.'),
            material, lambda v: [] if isinstance(v, dict) else ['JSON object required'])
        answer_identity = provider.backends[stage][1] if routed else active.identity
        write(Path(result['write_to']), {'request_id': request['request_id'],
              'content': json.dumps(value, ensure_ascii=False), 'finish_reason': 'stop',
              'writer_provider':answer_identity.get('type','native'), **active.last_metadata})
    raise ValueError('Prepare repair budget exhausted')


def refresh_history_api(root, provider, identity, confirm=False):
    """Stale resumes require explicit approval and a fresh read-only history check."""
    from .agent_shadow import verify_answer_hashes
    verify_answer_hashes(root)
    if (root/'done.json').exists():
        return
    metrics = read(root/'metrics.json')
    started = metrics.get('history_rechecked_at') or metrics.get('started_at')
    if not started or (datetime.now(timezone.utc)-datetime.fromisoformat(started)).total_seconds() <= 86400:
        return
    if not confirm:
        raise ValueError('stale_run: preserve state; confirm_stale:true requires fresh API history check')
    today = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    fresh_root = root/'history-registry'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    fresh_root.mkdir(parents=True)
    fresh = read(registry(today, fresh_root))
    from .agent_shadow import registry_history, CATS
    from .kidsnews_groups import pin
    history = {cat: registry_history(fresh['history'],cat,today,exclude_date=read(root/'input.json')['date']) for cat in CATS}
    if not any(history.values()):
        raise ValueError('Fresh history empty; check connector')
    ask = CachedJSON(root, provider, identity)
    blocked = []
    for cat in CATS:
        request = read(root/'groups'/f'{cat}-request.json')
        candidates = [{'id': r['id'], 'title': r['source']['title'],
                       'abstract': r['source'].get('summary','')} for r in request['candidates']]
        ids = {r['id'] for r in candidates}
        def validate(v):
            clear, bad = v.get('clear_ids'), v.get('blocked_ids')
            if not isinstance(clear,list) or not isinstance(bad,list) or any(not isinstance(i,str) for i in clear+bad):
                return ['clear_ids and blocked_ids required']
            return [] if len(clear+bad)==len(ids) and set(clear+bad)==ids else ['Partition every supplied ID exactly once']
        value = ask(root,'history-refresh-'+cat,
            'Compare ONLY supplied category past-seven-day history; partition every supplied ID into '
            '{clear_ids:[],blocked_ids:[]}. Same/uncertain event or URL goes blocked. Do not rewrite.',
            {'category':cat,'history':history[cat],'candidates':candidates},validate)
        blocked.extend(value['blocked_ids'])
    state = read(root/'editor-state.json') if (root/'editor-state.json').exists() else {}
    if any(a['candidate']['id'] in blocked for section in state.values() for a in section.get('accepted',[])):
        raise ValueError('Accepted article became duplicate/uncertain; preserve it and stop for review')
    write(root/'groups/history-refresh.json',{'history':history,'blocked_ids':blocked,'date':today})
    pin(root,root/'groups/history-refresh.json')
    metrics['history_rechecked_at']=datetime.now(timezone.utc).isoformat();write(root/'metrics.json',metrics)


def verify_website(artifact):
    from .website_release import SITE
    from urllib.parse import urljoin, urlsplit
    scope, manifest, _, files = load_artifact(artifact)
    response = requests.get(f'https://{PROJECT}.supabase.co/storage/v1/object/public/'
        'redesign-daily-content/latest-manifest.json', params={'publication_verify': scope['zip_sha256']},
        timeout=30, allow_redirects=False)
    response.raise_for_status()
    if response.json() != manifest:
        raise ValueError('Another/older edition is latest; do not update archive/database')
    for name, expected in files.items():
        url = SITE+'/'+name
        for _ in range(4):
            response = requests.get(url, params={'publication_verify': scope['zip_sha256']},
                                    timeout=30, allow_redirects=False)
            if response.status_code not in (301,302,303,307,308):
                break
            target = urljoin(url,response.headers.get('Location',''))
            parts = urlsplit(target)
            if (not response.headers.get('Location') or parts.scheme!='https'
                    or parts.netloc!=urlsplit(SITE).netloc or parts.username or parts.password):
                raise ValueError('Unsafe website redirect: '+name)
            url = target
        else:
            raise ValueError('Website redirect budget exceeded: '+name)
        response.raise_for_status()
        if sha(response.content) != sha(expected):
            raise ValueError('Website hash mismatch: '+name)
    return scope


def finish_publication(artifact, state, client, storage):
    """Durable cross-system saga; failures keep explicit resume/rollback evidence."""
    state = private_root(state)
    try:
        result = _finish_publication(artifact, state, client, storage)
    except Exception as exc:
        private_write(state/'recovery-required.json', encoded({
            'action': 'resume_or_rollback', 'error_class': type(exc).__name__,
            'automatic_republish': False, 'state_dir': str(state)}))
        raise
    private_write(state/'recovery-required.json', encoded({'action': 'none', 'status': 'verified'}))
    return result


def _finish_publication(artifact, state, client, storage):
    from .publication_database import prepare, commit
    from .publication_archive import prepare_archive, apply_archive
    state = private_root(state)
    scope = load_artifact(artifact)[0]
    with run_lock(state), client.publication_lock():
        marker = state/'publication.json'
        saved = json.loads(marker.read_bytes()) if marker.exists() else {}
        if saved and saved.get('artifact_hashes') != scope['artifact_hashes']:
            raise ValueError('Publication state belongs to different artifact')
        verify_website(artifact)
        # Both database and archive before-images BEFORE either system mutates.
        prepare(artifact, state/'database', client)
        prepare_archive(artifact, state/'archive', storage)
        private_write(marker, encoded({**scope, 'phase': 'backups_prepared'}))
        apply_archive(artifact, state/'archive', storage)
        private_write(marker, encoded({**scope, 'phase': 'archive_verified'}))
        verify_website(artifact)  # Stop if a newer website overtook this operation.
        commit(artifact, state/'database', client)
        client.verify_database(state/'database')
        client.verify_archive(artifact)
        verify_website(artifact)
        private_write(marker, encoded({**scope, 'phase': 'complete',
                        'verified_at': datetime.now(timezone.utc).isoformat()}))
        return {'ok': True, 'status': 'complete', 'date': scope['date'],
                'zip_sha256': scope['zip_sha256'], 'database_verified': True, 'archive_verified': True}


def rollback_publication(state, client, storage):
    """Scoped DB+archive rollback only. Website/latest have separate CI backup."""
    from .publication_database import rollback, verify_prepared
    from .publication_archive import rollback_archive, verify_plan
    state = private_root(state)
    with run_lock(state), client.publication_lock():
        verify_prepared(state/'database')
        plan = json.loads((state/'archive/prepared.json').read_bytes())
        verify_plan(state/'archive', plan)
        # Archive competing-writer preflight BEFORE restoring DB.
        journal = json.loads((state/'archive/journal.json').read_bytes())
        for row in plan['objects']:
            if row['name'] not in journal['writes']:
                continue
            remote = storage.get(row['name'])
            if (sha(remote) if remote is not None else None) not in {row['before_sha'], row['after_sha']}:
                raise ValueError('Newer archive edition; stop rollback')
        execution = json.loads((state/'database/execution.json').read_bytes()) if (state/'database/execution.json').exists() else {}
        if execution.get('status') in ('committed', 'rolled_back'):
            rollback(state/'database', client)
        elif (state/'database/rest-execution.json').exists() and hasattr(client,'apply_prepared'):
            rollback(state/'database',client)
        elif execution:
            raise ValueError('Database outcome uncertain; inspect before rollback')
        rollback_archive(state/'archive', storage)
        private_write(state/'rollback.json', encoded({'status': 'rolled_back', 'website_restored': False}))
        return {'ok': True, 'status': 'rolled_back', 'website_restored': False}


def execute(config):
    if config.get('env_file'):
        from dotenv import load_dotenv
        path = Path(config['env_file'])
        if not path.is_file():
            raise ValueError('Configured private env file missing')
        load_dotenv(path, override=False)
    operation = config.get('operation', 'run')
    if operation not in ('run', 'backfill', 'rollback'):
        raise ValueError('Unknown operation')
    backend = config.get('database_archive') is True or operation in ('backfill', 'rollback')
    publish = config.get('publish') is True
    if (backend or publish) and config.get('execute') is not True:
        raise ValueError('Publication writes require execute:true')
    if publish and (config.get('ack_same_day_replacement') is not True or not config.get('branch')):
        raise ValueError('Publication requires branch and same-day replacement acknowledgement BEFORE writes')
    if backend:
        private_root(Path(config['state_dir']))
        database_client(config).preflight()  # Read-only credential check before any website work.
        if not os.environ.get('SUPABASE_SERVICE_KEY'):
            raise ValueError('SUPABASE_SERVICE_KEY required for archive')
    if operation == 'run' and backend and not publish:
        raise ValueError('run database_archive requires publish:true; use backfill for existing website')
    if operation == 'run':
        root = Path(config['run_dir']).resolve(); root.mkdir(parents=True, exist_ok=True)
        day = date.fromisoformat(config['date']).isoformat()
        if 'ai_stages' in config:
            from .ai_stage_config import StageProviders
            provider = StageProviders(root, config, agent_provider)
            identity = provider.identity
        else:
            provider, identity = agent_provider(config)
        registry_path = Path(config['registry']) if config.get('registry') else registry(day, root)
        prepare_api(root, day, registry_path, provider, identity, all_ai=config.get('all_ai') is True,
                    batch_writer=config.get('batch_writer'))
        refresh_history_api(root, provider, identity, config.get('confirm_stale') is True)
        edit_groups(root, provider, identity)
        from .agent_shadow import advance
        from .kidsnews_bot import artifacts
        with run_lock(root):
            advance(root, stepwise=False)
        result = artifacts(root, publish, config.get('branch'))
        artifact = root/'reader-artifact'
        if publish:
            if config.get('ack_same_day_replacement') is not True:
                raise ValueError('Same-day replacement acknowledgement required')
            # Existing Action continues unchanged; bounded polling reads only.
            for attempt in range(45):
                try:
                    verify_website(artifact); break
                except (ValueError, requests.RequestException):
                    if attempt == 44:
                        raise ValueError('Website pending/failed; resume same directory, not regenerate')
                    time.sleep(20)
            result.update(status='website_verified', published=True)
        if not backend:
            return result
        if not publish:
            raise ValueError('run database_archive requires publish:true; use backfill for a verified existing edition')
    else:
        artifact = Path(config['artifact_dir']) if operation == 'backfill' else None
    from .publication_archive import ArchiveStorage
    client = database_client(config)
    storage = ArchiveStorage(f'https://{PROJECT}.supabase.co', os.environ['SUPABASE_SERVICE_KEY'])
    state = Path(config['state_dir'])
    return rollback_publication(state, client, storage) if operation == 'rollback' else finish_publication(artifact, state, client, storage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-file', type=Path)
    args = parser.parse_args()
    config, started = {}, time.monotonic()
    try:
        config = read(args.input_file) if args.input_file else json.load(sys.stdin)
        if not isinstance(config, dict):
            raise ValueError('JSON object required')
        if config.get('operation','run') == 'run' and config.get('run_dir'):
            folder = Path(config['run_dir'])/'.orchestration-lock'
            folder.mkdir(parents=True,exist_ok=True)
            with run_lock(folder):
                result = execute(config)
        else:
            result = execute(config)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError)
                          else type(exc).__name__, 'resume': 'Preserve same run/state; never remove attempts or backups'})); return 1
    finally:
        if isinstance(config, dict) and config.get('operation', 'run') == 'run' and config.get('run_dir'):
            root = Path(config['run_dir'])
            if root.exists():
                try:
                    with (root/'steps.jsonl').open('a', encoding='utf-8') as stream:
                        stream.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(),
                            'cmd': 'kidsnews_python', 'seconds': round(time.monotonic()-started, 3)})+'\n')
                except OSError:
                    print('Could not append run timing; preserve state', file=sys.stderr)
                from .agent_shadow_logs import ship
                ship(root)


if __name__ == '__main__':
    raise SystemExit(main())
