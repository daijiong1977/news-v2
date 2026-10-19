"""Deterministic PDFs from final reader details; no extra model calls."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile


def add_reader_pdfs(files, records, day):
    from .pdf_export import render_article_pdf
    result = dict(files)
    stamp = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix='kidsnews-reader-pdfs-') as temp:
        for row in records:
            sid = row['payload_story_id']
            for level in ('easy', 'middle'):
                detail = json.loads(files[f'article_payloads/payload_{sid}/{level}.json'])
                output = Path(temp)/f'{sid}-{level}.pdf'
                render_article_pdf(detail, level, row['category'], row['source_name'],
                    day, 3 if level == 'easy' else 5, output, created_at=stamp)
                data = output.read_bytes()
                if not data.startswith(b'%PDF-'):
                    raise ValueError('Invalid reader PDF')
                result['article_pdfs/'+output.name] = data
    return result


def augment_artifact(source, destination):
    """Repair an approved edition without changing a single story or detail."""
    from .publication_database import load_artifact
    from .publication_bundle import encoded, sha
    from .website_release import zip_files, check_reader
    source, destination = Path(source), Path(destination)
    scope, manifest, records, files = load_artifact(source)
    public = add_reader_pdfs(files, records, scope['date'])
    data = zip_files(public)
    manifest = {**manifest, 'packed_at': datetime.now(timezone.utc).isoformat(),
        'zip_sha256': sha(data), 'zip_bytes': len(data),
        'files': {n: sha(b) for n, b in sorted(public.items())},
        'maintenance': {'operation': 'add_reader_pdfs', 'previous_zip_sha256': scope['zip_sha256']}}
    check_reader(data, manifest)
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'reader.zip').write_bytes(data)
    (destination/'latest-manifest.json').write_bytes(encoded(manifest))
    (destination/'records.json').write_bytes((source/'records.json').read_bytes())
    load_artifact(destination)
    return manifest
