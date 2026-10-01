"""Phase-one reader packages and latest-only publishing. No DB/archive writes.

Privileged commands belong to GitHub Actions, never the Bot VM. A Storage upload
can be picked up by the existing cron immediately; it is a publication operation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, date, timedelta, timezone
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile
import requests
from .publication_bundle import encoded, sha, safe_name, unpack, MAX_ZIP, MAX_FILES, MAX_FILE, MAX_EXPANDED
from .agent_shadow import read, write, run_lock

SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co'
BUCKET = 'redesign-daily-content'
SITE = 'https://kidsnews.21mins.com'
SHELL_FILES = {'index.html','article.jsx','home.jsx','components.jsx','data.jsx','user-panel.jsx',
    'admin.html','parent.html','parent.jsx','kidsync.js','tokens.css','fonts.css','autofix.html','podcast.html'}
CONTENT_DIRS = {'payloads','article_payloads','article_images','article_pdfs'}


def evidence_gate(text, original):
    """Cheap conservative evidence check, not a model fact audit.

    Numeric normalization permits thousands separators, not unsupported conversion.
    Quoted multi-word sentences must be verbatim (case/whitespace normalized).
    """
    if re.search(r'[\u3400-\u9fff]',text): raise ValueError('English field contains CJK')
    normalize=lambda s: ' '.join(s.replace('“','"').replace('”','"').replace('’',"'").lower().split())
    source=normalize(original)
    for quote in re.findall(r'"([^"\n]+)"',normalize(text)):
        if len(quote.split())>=4 and quote not in source: raise ValueError('Unsupported quoted sentence: '+quote)
    numbers=lambda s: set(re.findall(r'(?<!\w)\d+(?:\.\d+)?',s.replace(',','')))
    extra=numbers(text)-numbers(original)
    if extra: raise ValueError('Numeric evidence missing from source: '+', '.join(sorted(extra)))


def zip_files(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026,1,1,0,0,0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return stream.getvalue()


def reader_files(data):
    if len(data) > MAX_ZIP: raise ValueError('Reader ZIP size budget')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if not 1 <= len(infos) <= MAX_FILES or sum(i.file_size for i in infos) > MAX_EXPANDED:
            raise ValueError('Reader expanded size budget')
        if len({i.filename for i in infos}) != len(infos): raise ValueError('Duplicate file')
        for i in infos:
            if not safe_name(i.filename) or i.is_dir() or i.file_size > MAX_FILE or (i.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Unsafe reader entry')
            if i.filename not in SHELL_FILES and i.filename.split('/')[0] not in CONTENT_DIRS | {'assets','components'}:
                raise ValueError('Internal/shadow file in public reader')
        files = {i.filename: archive.read(i) for i in infos}
    if 'index.html' not in files: raise ValueError('Missing reader index')
    # HTML/JSX local script dependencies. External CDN dependencies are unchanged.
    for name, data in files.items():
        if name.endswith(('.html','.jsx','.css')):
            text = data.decode('utf-8')
            refs = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', text)
            refs += re.findall(r'url\(["\']?([^\)"\']+)', text) if name.endswith('.css') else []
            for ref in refs:
                ref = ref.split('?')[0].split('#')[0]
                if not ref or ref.startswith(('http:', 'https:', '//', 'data:', 'mailto:', '{')): continue
                if ref.endswith(('.jsx','.js','.css','.woff','.woff2','.ttf','.svg','.png','.webp','.ico')):
                    target = ref.lstrip('/') if ref.startswith('/') else (Path(name).parent / ref).as_posix()
                    if target not in files: raise ValueError('Missing reader dependency: ' + target)
    return files


def check_reader(data, manifest):
    if manifest.get('zip_sha256') != sha(data) or manifest.get('zip_bytes') != len(data):
        raise ValueError('Reader ZIP hash/size mismatch')
    files = reader_files(data)
    if manifest.get('files') and manifest['files'] != {n:sha(b) for n,b in sorted(files.items())}:
        raise ValueError('Reader file hash mismatch')
    return files


def build_reader(internal, shell, template_commit):
    files, original = unpack(internal)
    if original['counts'] != {'news':3,'science':3,'fun':3}: raise ValueError('Require three articles per section')
    if not re.fullmatch('[0-9a-f]{40}', template_commit): raise ValueError('Pin full template commit')
    public = {n:b for n,b in files.items() if n.split('/')[0] in CONTENT_DIRS}
    for path in shell.rglob('*'):
        if path.is_symlink(): raise ValueError('Reader shell symlink')
        name = path.relative_to(shell).as_posix()
        if path.is_file() and (name in SHELL_FILES or name.split('/')[0] in {'assets','components'}):
            public[name] = path.read_bytes()
    data = zip_files(public)
    records = json.loads(files['publication-records.json'])
    stamp = datetime.now(timezone.utc).isoformat()
    stories = []
    for row in records:
        listing = json.loads(public[f"payloads/articles_{row['category'].lower()}_middle.json"])['articles']
        card = next(a for a in listing if a['id'] == row['payload_story_id'])
        stories.append({'id':row['payload_story_id'], 'category':card.get('category',row['category']), 'title':card['title'],
            'mined_at':card.get('mined_at') or original['started_at'], 'source':row['source_name'], 'source_published_at':card.get('source_published_at')})
    commit = os.environ.get('GITHUB_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    manifest = {'version':original['date'], 'packed_at':stamp, 'git_sha':commit,
        'zip_bytes':len(data), 'zip_sha256':sha(data), 'story_count':9, 'stories':stories,
        'template_commit':template_commit, 'files':{n:sha(b) for n,b in sorted(public.items())}}
    check_reader(data, manifest)
    return {'zip':data, 'manifest':manifest, 'records':records}


def overlay_history(registry, ledger):
    day = date.fromisoformat(registry['date']); start = day - timedelta(days=7)
    relevant = {d:rows for d,rows in ledger.items() if start <= date.fromisoformat(d) < day}
    rows = [r for r in registry['history'] if r.get('published_date') not in relevant]
    for d, records in sorted(relevant.items()):
        rows.extend({**r, 'published_date':d, 'id':r.get('payload_story_id',r.get('id'))} for r in records)
    return {**registry,'history':rows,'website_overlay_dates':sorted(relevant)}


class LatestRelease:
    """Persistent same-directory resume. A failed/uncertain PUT is never resent blindly."""
    def __init__(self, root, storage):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True); self.storage = storage
    def state(self): return read(self.root/'release.json') if (self.root/'release.json').exists() else {}
    def backup(self):
        with run_lock(self.root):
            if (self.root/'backup.json').exists():
                meta = read(self.root/'backup.json')
                data = (self.root/'backup.zip').read_bytes()
                manifest = read(self.root/'backup-manifest.json')
                check_reader(data, manifest)
                if meta != {'zip':sha(data),'manifest':sha(encoded(manifest))}: raise ValueError('Backup hash mismatch')
                return
            data = self.storage.download('latest.zip')
            manifest = json.loads(self.storage.download('latest-manifest.json'))
            check_reader(data,manifest)
            # No remote mutation until the independent backup is complete and uploaded as CI artifact.
            _bytes(self.root/'backup.zip',data); write(self.root/'backup-manifest.json',manifest)
            write(self.root/'backup.json',{'zip':sha(data),'manifest':sha(encoded(manifest))})
    def _replace(self, data, manifest, mode):
        state = self.state()
        if state.get('target_sha') and (state['target_sha'] != sha(data) or state.get('mode') != mode):
            if mode != 'rollback': raise ValueError('Frozen release target differs')
            state = {}
        state.update({'mode':mode,'target_sha':sha(data)})
        for key, blob, content_type in [('latest.zip',data,'application/zip'),('latest-manifest.json',encoded(manifest),'application/json')]:
            digest = sha(blob); marker = state.get(key)
            if marker in ('attempting','complete'):
                remote = self.storage.download(key)
                equal = sha(remote) == digest if key.endswith('.zip') else json.loads(remote) == manifest
                if not equal: raise ValueError('Uncertain upload or competing writer: inspect before retry')
            else:
                state[key] = 'attempting'; write(self.root/'release.json',state)
                self.storage.upload(path=key,file=blob,file_options={'content-type':content_type,'upsert':'true'})
                remote = self.storage.download(key)
                equal = sha(remote) == digest if key.endswith('.zip') else json.loads(remote) == manifest
                if not equal: raise ValueError('Latest readback mismatch')
            state[key] = 'complete'; write(self.root/'release.json',state)
        if sha(self.storage.download('latest.zip')) != sha(data) or json.loads(self.storage.download('latest-manifest.json')) != manifest:
            raise ValueError('Competing writer during final readback')
        state['storage_verified'] = True; write(self.root/'release.json',state)
    def publish(self, data, manifest, acknowledge_slots=False):
        check_reader(data,manifest)
        if not acknowledge_slots: raise ValueError('Explicit same-day slot/read-progress risk acknowledgement required')
        if not (self.root/'backup.json').exists(): raise ValueError('Backup required first')
        self.backup()
        with run_lock(self.root):
            if not self.state():
                if sha(self.storage.download('latest.zip')) != read(self.root/'backup.json')['zip'] or json.loads(self.storage.download('latest-manifest.json')) != read(self.root/'backup-manifest.json'):
                    raise ValueError('Competing latest writer after backup; stop before upload')
            self._replace(data,manifest,'publish')
    def rollback(self):
        self.backup()  # revalidate all saved bytes, never replace backup
        with run_lock(self.root):
            state = self.state()
            remote_hash = sha(self.storage.download('latest.zip'))
            if remote_hash not in {state.get('target_sha'),sha((self.root/'backup.zip').read_bytes())}:
                raise ValueError('Competing latest writer; rollback requires inspection')
            self._replace((self.root/'backup.zip').read_bytes(),read(self.root/'backup-manifest.json'),'rollback')


def _bytes(path, data):
    import tempfile
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f: f.write(data); temporary = f.name
    os.replace(temporary,path)


def writer_preflight(token):
    headers = {'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'}
    for repo in ('news-v2','kidsnews-v2'):
        response = requests.get(f'https://api.github.com/repos/daijiong1977/{repo}/actions/runs',headers=headers,params={'per_page':100},timeout=30)
        response.raise_for_status()
        if any(r['status'] != 'completed' for r in response.json()['workflow_runs']):
            raise ValueError('Active workflow in '+repo+'; wait for conflict-free window')


def dispatch(root, token):
    state = read(root/'release.json')
    if not state.get('storage_verified'): raise ValueError('Storage verification required')
    if state.get('dispatch') == 'sent': return
    if state.get('dispatch') == 'attempting': raise ValueError('Dispatch uncertain: inspect existing sync runs, do not resend blindly')
    state['dispatch'] = 'attempting'; state['dispatch_at'] = datetime.now(timezone.utc).isoformat(); write(root/'release.json',state)
    response = requests.post('https://api.github.com/repos/daijiong1977/kidsnews-v2/dispatches',
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'},
        json={'event_type':'news-v2-uploaded','client_payload':{'zip_sha256':state['target_sha']}},timeout=30)
    response.raise_for_status(); state['dispatch'] = 'sent'; write(root/'release.json',state)


def verify_public(root, data, manifest):
    files = check_reader(data,manifest)
    for name, blob in files.items():
        response = requests.get(SITE+'/'+name,params={'kidsnews_verify':sha(data)},timeout=30)
        response.raise_for_status()
        if sha(response.content) != sha(blob): raise ValueError('Public file mismatch: '+name)
    state = read(root/'release.json'); state['public_verified'] = True
    state['verified_at'] = datetime.now(timezone.utc).isoformat(); write(root/'release.json',state)


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='cmd',required=True)
    b = sub.add_parser('build'); b.add_argument('--zip',type=Path,required=True); b.add_argument('--output-dir',type=Path,required=True)
    for cmd in ('check','backup','publish','rollback','dispatch','verify'):
        s = sub.add_parser(cmd); s.add_argument('--release-dir',type=Path,required=True)
        if cmd == 'publish': s.add_argument('--ack-same-day-replacement',action='store_true')
    o = sub.add_parser('overlay'); o.add_argument('--registry',type=Path,required=True); o.add_argument('--ledger',type=Path,required=True)
    args = p.parse_args()
    try:
        if args.cmd == 'overlay':
            write(args.registry,overlay_history(read(args.registry),read(args.ledger)))
        elif args.cmd == 'build':
            base = Path(__file__).resolve().parents[1]; pin = read(base/'config/reader-shell.json'); shell = base/'reader-shell'
            actual = {x.relative_to(shell).as_posix():sha(x.read_bytes()) for x in shell.rglob('*') if x.is_file()}
            if actual != pin['files']: raise ValueError('Pinned shell hashes differ')
            result = build_reader(args.zip.read_bytes(),shell,pin['commit']); out = args.output_dir
            if out.exists() and any(out.iterdir()): raise ValueError('Choose empty artifact directory')
            _bytes(out/'reader.zip',result['zip']); write(out/'latest-manifest.json',result['manifest']); write(out/'records.json',result['records'])
        else:
            root = args.release_dir; data_path = root/'reader.zip'; manifest_path = root/'latest-manifest.json'
            if args.cmd == 'check': check_reader(data_path.read_bytes(),read(manifest_path))
            elif args.cmd in ('dispatch','verify'):
                if args.cmd == 'dispatch': dispatch(root,os.environ['KIDSNEWS_DISPATCH_TOKEN'])
                else:
                    mode = read(root/'release.json')['mode']; prefix = 'backup' if mode == 'rollback' else 'reader'
                    verify_public(root,(root/(prefix+'.zip')).read_bytes(),read(root/('backup-manifest.json' if mode == 'rollback' else 'latest-manifest.json')))
            else:
                token = os.environ['KIDSNEWS_DISPATCH_TOKEN']; writer_preflight(token)
                from supabase import create_client
                release = LatestRelease(root,create_client(SUPABASE_URL,os.environ['SUPABASE_SERVICE_KEY']).storage.from_(BUCKET))
                if args.cmd == 'backup': release.backup()
                elif args.cmd == 'rollback': release.rollback()
                else: release.publish(data_path.read_bytes(),read(manifest_path),args.ack_same_day_replacement)
        print(json.dumps({'ok':True,'cmd':args.cmd})); return 0
    except Exception as exc:
        print(json.dumps({'ok':False,'cmd':args.cmd,'error':str(exc) if isinstance(exc,ValueError) else type(exc).__name__})); return 1


if __name__ == '__main__': raise SystemExit(main())
