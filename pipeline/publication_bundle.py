"""ZIP handoff: local validation/build/staging, upload only (never calls an Edge Function).

Supabase remains the source/history authority. A scheduler, not this CLI, finalizes
verified packages. No arbitrary SQL is accepted. Production activation is separate.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, datetime, timezone

from .agent_shadow import read, write, run_lock

MAX_ZIP = 20 * 1024 * 1024
MAX_EXPANDED = 80 * 1024 * 1024
MAX_FILE = 5 * 1024 * 1024
MAX_FILES = 200
CATS = ('News', 'Science', 'Fun')
LEVELS = ('easy', 'middle', 'cn')


def encoded(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    return bool(name and not p.is_absolute() and str(p) == name and
                '\\' not in name and ':' not in name and not any(x in ('..', '.') for x in p.parts))


def unpack(data):
    if len(data) > MAX_ZIP:
        raise ValueError('ZIP exceeds compressed size budget')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
        if not 1 <= len(infos) <= MAX_FILES or sum(i.file_size for i in infos) > MAX_EXPANDED:
            raise ValueError('ZIP file/expanded size budget exceeded')
        names = [i.filename for i in infos]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate ZIP entries')
        for i in infos:
            if (not safe_name(i.filename) or i.is_dir() or i.file_size > MAX_FILE
                    or (i.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe ZIP entry')
        files = {i.filename: z.read(i) for i in infos}
    manifest = json.loads(files.pop('publication-manifest.json'))
    hashes = {n: sha(b) for n, b in sorted(files.items())}
    if manifest.get('schema_version') != 1 or manifest.get('files') != hashes or manifest.get('package_id') != sha(encoded(hashes)):
        raise ValueError('Manifest/hash mismatch')
    files['publication-manifest.json'] = encoded(manifest)
    validate_contents(files, manifest)
    return files, manifest


def validate_contents(files, manifest):
    from PIL import Image
    from .agent_shadow_lengths import rewrite_band
    run_date = manifest['date']
    date.fromisoformat(run_date)
    uuid.UUID(manifest['run_id'])
    rows = json.loads(files['publication-records.json'])
    usage = json.loads(files['source-usage.json'])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 9:
        raise ValueError('Refuse empty/oversized publication')
    ids = set()
    for cat in CATS:
        section = [r for r in rows if r['category'] == cat]
        expected = [f'{run_date}-{cat.lower()}-{i}' for i in range(1, len(section) + 1)]
        if len(section) > 3 or [r['payload_story_id'] for r in section] != expected:
            raise ValueError('Publication slots mismatch')
        if manifest['counts'].get(cat.lower()) != len(section):
            raise ValueError('Publication counts mismatch')
        for level in LEVELS:
            listing = json.loads(files[f'payloads/articles_{cat.lower()}_{level}.json'])['articles']
            if [x['id'] for x in listing] != expected:
                raise ValueError('Listing/record ID mismatch')
        for row in section:
            sid = row['payload_story_id']
            if sid in ids or row['published_date'] != run_date or row.get('facts_supported') is not True or row.get('event_clear') is not True:
                raise ValueError('Unqualified publication record')
            ids.add(sid)
            scores = row['safety_scores']
            from .news_rss_core import SAFETY_DIMS, evaluate_rewriter_safety
            if set(scores) != set(SAFETY_DIMS) or any(type(v) not in (int, float) or not 0 <= v <= 5 for v in scores.values()):
                raise ValueError('Missing safety evidence')
            if evaluate_rewriter_safety({'safety': scores}, category=cat)['verdict'] != 'PASS':
                raise ValueError('Unsafe final content')
            for level in ('easy', 'middle'):
                body = json.loads(files[f'article_payloads/payload_{sid}/{level}.json'])
                lo, hi = rewrite_band(level, cat, body['source_word_count'])
                if not lo <= len(body['summary'].split()) <= hi or body['source_url'] != row['source_url']:
                    raise ValueError('Body length/source mismatch')
                image = body.get('image_url')
                if image:
                    name = image.lstrip('/')
                    if not name.startswith('article_images/') or name not in files:
                        raise ValueError('Image mapping mismatch')
                    with Image.open(io.BytesIO(files[name])) as im:
                        if im.format not in ('WEBP', 'PNG', 'JPEG') or min(im.size) < 1 or max(im.size) > 4096:
                            raise ValueError('Image size/format invalid')
                        im.verify()
    if len(ids) != len(rows):
        raise ValueError('Unknown category')
    source_ids = {r['source_config_id'] for r in rows if r['source_config_id'] is not None}
    if {x['source_id'] for x in usage} != source_ids or len(usage) != len(source_ids):
        raise ValueError('Source usage does not match published articles')
    if any(type(x['source_id']) is not int or x['source_id'] <= 0 or x['used_date'] != run_date for x in usage):
        raise ValueError('Invalid source usage')


def build(root: Path, output: Path, shell: Path | None = None):
    from .agent_shadow import verify_answer_hashes
    verify_answer_hashes(root)
    done, snapshot, state = (read(root / n) for n in ('done.json', 'input.json', 'editor-state.json'))
    if done.get('test_profile') != 'batch-deepseek':
        raise ValueError('Publication handoff requires completed batch-deepseek run')
    files = {}
    site = root / 'site'
    for path in sorted(site.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in site')
        if path.is_file():
            files[path.relative_to(site).as_posix()] = path.read_bytes()
    if shell:
        # Use the actual existing reader shell for production, not the shadow app.
        for path in sorted(shell.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink in reader shell')
            parts = path.relative_to(shell).parts
            if (path.is_file() and path.suffix.lower() in {'.html', '.js', '.css', '.json', '.svg', '.webp', '.png', '.jpg', '.jpeg', '.ico', '.txt', '.woff', '.woff2', '.ttf'}
                    and not any(x.startswith('.') or x in ('payloads', 'article_payloads', 'article_images', 'node_modules', 'work') for x in parts)):
                files[path.relative_to(shell).as_posix()] = path.read_bytes()
    records = []
    photos = read(root / 'candidate-images.json') if (root / 'candidate-images.json').exists() else {}
    source_by_id = {b['id']: snapshot['sources'][b['source']]['id'] for b in snapshot['candidates']}
    for cat in CATS:
        accepted = {a['candidate']['id']: a for a in state[cat]['accepted']}
        listing = json.loads(files[f'payloads/articles_{cat.lower()}_easy.json'])['articles']
        for slot, card in enumerate(listing, 1):
            sid = card['id']
            body = json.loads(files[f'article_payloads/payload_{sid}/easy.json'])
            match = next((a for a in accepted.values() if a['candidate']['article']['link'] == body['source_url']), None)
            if not match:
                raise ValueError('No accepted source matches payload')
            candidate_id = match['candidate']['id']
            outcome = next(o for o in reversed(state[cat]['outcomes']) if o['id'] == candidate_id)
            src_id = source_by_id.get(candidate_id)
            records.append({'category': cat, 'story_slot': slot, 'published_date': snapshot['date'],
                'payload_story_id': sid, 'source_name': body['source_name'], 'source_url': body['source_url'],
                'source_title': match['candidate']['article']['title'],
                'source_config_id': src_id if src_id is not None and src_id > 0 else None,
                'topic': match['candidate']['topic'], 'importance': match['candidate']['importance'],
                'writer_provider': match['candidate'].get('writer_provider', 'deepseek'),
                'safety_scores': outcome['safety']['scores'], 'facts_supported': outcome['facts_supported'],
                'event_clear': outcome['event_clear'], 'primary_image_local': body['image_url'].lstrip('/'),
                'primary_image_url': photos.get(candidate_id, {}).get('source_url') or None,
                'payload_path': f'payloads/articles_{cat.lower()}_easy.json'})
    usage = [{'source_id': sid, 'used_date': snapshot['date']} for sid in sorted({r['source_config_id'] for r in records if r['source_config_id']})]
    files['publication-records.json'], files['source-usage.json'] = encoded(records), encoded(usage)
    hashes = {n: sha(b) for n, b in sorted(files.items())}
    run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, sha(encoded(hashes))))
    manifest = {'schema_version': 1, 'run_id': run_id, 'date': snapshot['date'], 'counts': done['counts'],
                'files': hashes, 'package_id': sha(encoded(hashes)), 'shell': 'provided' if shell else 'shadow',
                'started_at': read(root / 'metrics.json').get('started_at') or read(site / 'shadow-run.json')['generated_at'],
                'publication_verified': False}
    files['publication-manifest.json'] = encoded(manifest)
    validate_contents(files, manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    data = stream.getvalue()
    unpack(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != data:
        raise ValueError('Existing bundle differs; choose a new output')
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as f:
        f.write(data)
        temporary = f.name
    os.replace(temporary, output)
    return {'ok': True, 'zip': str(output), 'zip_sha256': sha(data), **manifest}


def stage(data, destination):
    files, manifest = unpack(data)
    if destination.exists():
        raise ValueError('Stage into a NEW directory; never overwrite a checkout')
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='bundle-') as scratch:
        for name, content in files.items():
            p = Path(scratch) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
        Path(scratch).rename(destination)
    return manifest


def upload(data, storage):
    """storage is an authenticated connector handle; never create a DB writer here."""
    _, manifest = unpack(data)
    key = f"pending/{manifest['package_id']}.zip"
    storage.upload(key, data, file_options={'content-type': 'application/zip', 'upsert': 'false'})
    return key


def verify_site(data, site_url, get):
    from urllib.parse import urlsplit
    url = urlsplit(site_url)
    if url.scheme != 'https' or url.username or url.password or url.query or url.fragment:
        raise ValueError('Verification target must be explicit HTTPS site')
    files, manifest = unpack(data)
    # Prove the actual public payloads/images, not only a claimed manifest.
    for name, content in files.items():
        if name.startswith(('payloads/', 'article_payloads/', 'article_images/')) or name == 'publication-manifest.json':
            response = get(site_url.rstrip('/') + '/' + name, timeout=20, allow_redirects=False)
            if response.status_code != 200 or response.content != content:
                raise ValueError(f'Public site mismatch: {name}')
    return {'package_id': manifest['package_id'], 'zip_sha256': sha(data), 'site_url': site_url,
            'verified_at': datetime.now(timezone.utc).isoformat()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('build', 'check', 'stage', 'upload', 'verify'))
    p.add_argument('--run-dir', type=Path)
    p.add_argument('--zip', type=Path, required=True)
    p.add_argument('--shell-dir', type=Path)
    p.add_argument('--destination', type=Path)
    p.add_argument('--site-url')
    args = p.parse_args()
    try:
        if args.command == 'build':
            if not args.run_dir:
                raise ValueError('--run-dir required')
            with run_lock(args.run_dir):
                result = build(args.run_dir, args.zip, args.shell_dir)
        else:
            data = args.zip.read_bytes()
            _, manifest = unpack(data)
            if args.command == 'check':
                result = manifest
            elif args.command == 'stage':
                if not args.destination:
                    raise ValueError('--destination required')
                result = stage(data, args.destination)
            elif args.command == 'upload':
                from dotenv import load_dotenv
                load_dotenv()
                from supabase import create_client
                from supabase import ClientOptions
                sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_ANON_KEY'],
                    options=ClientOptions(headers={'Authorization': 'Bearer ' + os.environ['SUPABASE_UPLOAD_TOKEN']}))
                result = {'pending_key': upload(data, sb.storage.from_('kidsnews-publication-pending'))}
            else:
                if not args.site_url:
                    raise ValueError('--site-url required')
                import requests
                result = verify_site(data, args.site_url, requests.get)
                # Ready marker is immutable and small; scheduler re-verifies the public site.
                from dotenv import load_dotenv
                load_dotenv()
                from supabase import create_client
                from supabase import ClientOptions
                sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_ANON_KEY'],
                    options=ClientOptions(headers={'Authorization': 'Bearer ' + os.environ['SUPABASE_UPLOAD_TOKEN']}))
                sb.storage.from_('kidsnews-publication-pending').upload(f"pending/{manifest['package_id']}.ready.json",
                    encoded(result), file_options={'content-type': 'application/json', 'upsert': 'false'})
        print(json.dumps({'ok': True, **result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Do not expose authentication/HTTP exception messages containing credentials.
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
