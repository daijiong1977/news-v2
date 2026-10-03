"""Versioned source-first collection. Python only; never writes production state.

One frozen feed, at most twelve unique articles; per-category pass quotas. All
evidence/photos are checkpointed before editorial models receive metadata.
"""
from dataclasses import asdict
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import re
import time
from urllib.parse import urljoin, urlsplit

from .agent_shadow_autonomous import fetch_original as generic_original, fetch_bytes, safe_image
from .news_rss_core import fetch_source_entries, is_generic_social_image as is_bad_image_url
from .editorial_policy import publisher_key, editorial_exclusion
from .agent_shadow_lengths import original_band

PROFILE = 'source-first-grok'
MAX_SOURCES_PER_SECTION = 40
MIN_IMAGE_BYTES = 20_000


def group_sources(sources, today):
    """Round robin publishers within due/backup tiers; stable cadence order."""
    out = []
    for sleeping, backup in ((False, False), (False, True), (True, False), (True, True)):
        groups = {}
        for source in sources:
            if bool(source.next_pickup_at and source.next_pickup_at[:10] > today) == sleeping and source.is_backup == backup:
                groups.setdefault(publisher_key(source), []).append(source)
        while any(groups.values()):
            for rows in groups.values():
                if rows:
                    out.append(rows.pop(0))
    return out


def extract_npr(url, html):
    """Written NPR report only; never transcribe an audio/video-primary page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select_one('.is-DACS-only, .is-tiny-desk'):
        return {'skip_reason': 'npr_audio_or_video_primary'}
    story = soup.select_one('.storytext')
    if story is None:
        return {'skip_reason': 'npr_no_written_report'}
    for node in story.select('.transcript, script, style, .audio-module, .video-module'):
        node.decompose()
    paragraphs = [p.get_text(' ', strip=True) for p in story.select('p') if p.get_text(strip=True)]
    body = '\n\n'.join(paragraphs)
    tag = soup.select_one('meta[property="og:image"]')
    image = urljoin(url, tag.get('content', '')) if tag else ''
    if not body or not image or is_bad_image_url(image) or 'default-' in image.lower():
        return {'skip_reason': 'npr_missing_body_or_article_photo'}
    return {'cleaned_body': body, 'paragraphs': paragraphs, 'og_image': image, 'skip_reason': None}


def fetch_original(candidate):
    from .source_freshness import publication_dates
    host = (urlsplit(candidate['link']).hostname or '').lower()
    if host == 'timeforkids.com' or host.endswith('.timeforkids.com'):
        from .news_rss_core import extract_article_from_html
        from .agent_shadow_candidate_quality import extraction_reason
        data, url, encoding = fetch_bytes(candidate['link'], ('text/html', 'application/xhtml+xml'))
        html = data.decode(encoding, errors='replace')
        extracted = extract_article_from_html(url, html)
        body = extracted.get('cleaned_body') or ''
        return {**candidate, **extracted, 'body': body, 'word_count': len(body.split()),
                'source_publication_dates': publication_dates(html),
                'skip_reason': extraction_reason(url, html, body) or (None if body else 'empty original'),
                'evidence_url': url, 'evidence_sha256': hashlib.sha256(body.encode()).hexdigest(),
                'highlights': [], 'image_candidates': []}
    if host != 'npr.org' and not host.endswith('.npr.org'):
        return generic_original(candidate)
    data, url, encoding = fetch_bytes(candidate['link'], ('text/html', 'application/xhtml+xml'))
    extracted = extract_npr(url, data.decode(encoding, errors='replace'))
    body = extracted.get('cleaned_body', '')
    return {**candidate, **extracted, 'body': body, 'word_count': len(body.split()),
            'source_publication_dates': publication_dates(data.decode(encoding, errors='replace')),
            'evidence_url': url, 'evidence_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'highlights': [], 'image_candidates': []}


def freshness(published, today):
    from .source_freshness import freshness as check
    return check(published, today)


def collect(root, sources_by_cat, today, *, expand=None):
    """Resume same checkpoint; expand ONLY one insufficient section if requested.

    All-run budget is frozen at 12 * configured feeds (max 40/section). Network
    failures consume a unique slot. An interrupted attempt is failed closed on
    resume rather than silently refunding its slot/repeating an image download.
    """
    from .agent_shadow import read, write
    from .full_round import _canonical_source_url, _normalize_title
    from .news_sources import NewsSource
    path = root / 'source-collection.json'
    if path.exists():
        state = read(path)
        if state['date'] != today:
            raise ValueError('source checkpoint date is frozen')
    else:
        context_path = root / 'prepare-context.json'
        fixed = context_path.exists() and read(context_path).get('selection_policy') == 'twelve-five-three-v1'
        sections = {}
        for cat, rows in sources_by_cat.items():
            selected = group_sources(rows, today) if cat == 'Science' else rows
            if len(selected) > MAX_SOURCES_PER_SECTION:
                raise ValueError('More than 40 configured sources/section: explicitly reduce registry; never silently truncate')
            sections[cat] = {'sources': [{'source': asdict(s), 'publisher': publisher_key(s),
                'results': [], 'windows': [], 'status': 'pending'} for s in selected], 'complete': False}
        from .source_freshness import POLICY
        state = {'version': 1, 'date': today, 'sections': sections, 'freshness_policy': POLICY,
                 'news_metadata_screen': True, 'routing_max_words': 2000,
                 'category_limits': {'News': {'pass_target': 6, 'min_good': 18}} if fixed else {},
                 'limits': {'per_source': 12, 'pass_target': 4, 'min_groups': 0 if fixed else 3, 'min_good': 12 if fixed else 10,
                            'max_unique_articles': 12 * sum(len(c['sources']) for c in sections.values())},
                 'unique_attempts': 0}
        write(path, state)
    all_results = lambda: [r for c in state['sections'].values() for s in c['sources'] for r in s['results']]
    from .source_freshness import POLICY, LEGACY_POLICY, rejection, freshness as date_check
    date_policy = state.get('freshness_policy')
    strict_dates = date_policy in (POLICY, LEGACY_POLICY)
    def sync():
        # These caches can always be rebuilt from the single atomic source journal.
        write(path, state)
        results = all_results()
        write(root / 'bodies.json', {r['candidate']['id']: r['article'] for r in results if r.get('qualified')})
        write(root / 'candidate-images.json', {r['candidate']['id']: r['photo'] for r in results if r.get('qualified')})
        metrics_path = root / 'metrics.json'
        if metrics_path.exists():
            metrics = read(metrics_path)
            metrics.update(source_unique_attempts=state['unique_attempts'],
                           body_fetches=sum(r.get('body_attempted', False) for r in results),
                           photo_fetches=sum(r.get('photo_attempted', False) for r in results))
            write(metrics_path, metrics)
    seen_urls = {_canonical_source_url(r['candidate']['link']) for r in all_results()}
    seen_urls.update(_canonical_source_url(r['article']['evidence_url']) for r in all_results()
                     if r.get('article', {}).get('evidence_url'))
    seen_titles = {_normalize_title(r['candidate']['title']) for r in all_results()}
    for cat, section in state['sections'].items():
        limits = {**state['limits'], **state.get('category_limits', {}).get(cat, {})}
        if expand and cat != expand:
            continue
        if section['complete'] and expand != cat:
            continue
        if expand == cat:
            section['complete'] = False
        done_groups, good, newly_processed = set(), 0, 0
        for source_state in section['sources']:
            if source_state['status'] in ('complete', 'suspended', 'feed_failed'):
                done_groups.add(source_state['publisher'] if cat == 'Science' else source_state['source']['name'])
                good += sum(r.get('qualified', False) for r in source_state['results'])
                continue
            # Initial stop respects group opportunities; incremental stop finishes one new source.
            if (not expand and len(done_groups) >= limits['min_groups']
                    and good >= limits['min_good']) or (expand and newly_processed >= 1):
                break
            source = NewsSource(**source_state['source'])
            if 'entries' not in source_state:
                t0 = time.monotonic()
                try:
                    source_state['entries'] = [dict(e) for e in fetch_source_entries(source, max_entries=12)][:12]
                except Exception as exc:
                    source_state.update(entries=[], status='feed_failed', reason=type(exc).__name__)
                source_state['feed_seconds'] = round(time.monotonic() - t0, 3)
                sync()
            for record in source_state['results']:
                if record['status'] == 'attempting':
                    record.update(status='complete', qualified=False, reason='interrupted_attempt_not_refunded')
            qualified = sum(r.get('qualified', False) for r in source_state['results'])
            entries = source_state['entries']
            for offset in range(len(source_state['results']), len(entries)):
                if qualified >= limits['pass_target']:
                    break
                if (not expand and cat in state.get('category_limits', {})
                        and good + qualified >= limits['min_good']):
                    break
                if offset == 6 and qualified == 0:
                    source_state['status'] = 'suspended'
                    break
                window = 6 if offset < 6 else 3
                if offset in (0, 6, 9):
                    source_state['windows'].append(window)
                entry = entries[offset]
                url, title = entry.get('link', ''), entry.get('title', '')
                sid = 's' + hashlib.sha256(f'{cat}|{source.id}|{source.rss_url}|{offset}|{url}'.encode()).hexdigest()[:16]
                b = {'id': sid, 'category': cat, 'title': title, 'link': url, 'source': source.name,
                     'summary': re.sub(r'<[^>]+>', ' ', entry.get('summary', ''))[:600],
                     'published': entry.get('published', ''), 'publisher': source_state['publisher']}
                record = {'candidate': b, 'status': 'attempting', 'qualified': False}
                source_state['results'].append(record)
                state['unique_attempts'] += 1
                if state['unique_attempts'] > state['limits']['max_unique_articles']:
                    raise ValueError('Frozen source collection budget exhausted')
                canonical, normalized = _canonical_source_url(url), _normalize_title(title)
                from .agent_shadow_candidate_quality import commercial_reason
                date_reason = (rejection(b, today, policy=date_policy) if strict_dates else
                               'stale_feed_entry' if date_check(b['published'], today, 5) == 'stale' else None)
                reason = ('duplicate_url_or_title' if not canonical or not normalized or canonical in seen_urls or normalized in seen_titles
                          else date_reason or commercial_reason(b) or editorial_exclusion(b))
                if not reason and cat == 'News' and state.get('news_metadata_screen'):
                    from .agent_shadow_rank_contract import metadata_exclusion
                    reason = metadata_exclusion(b, cat)
                seen_urls.add(canonical); seen_titles.add(normalized)
                sync()  # reserve the slot BEFORE network activity
                started = time.monotonic()
                if not reason:
                    try:
                        record['body_attempted'] = True
                        sync()
                        art = fetch_original(b)
                        reason = art.get('skip_reason') or commercial_reason(b, art.get('body', ''))
                        if not reason and strict_dates:
                            reason = rejection(b, today, art, policy=date_policy)
                        count = len(art.get('body', '').split())
                        art['word_count'] = count
                        routing_max = state.get('routing_max_words', 1500)
                        if not reason and not 180 <= count <= routing_max:
                            reason = f'original_outside_routing_band_180_{routing_max}'
                        evidence = _canonical_source_url(art.get('evidence_url') or url)
                        if not reason and evidence != canonical and evidence in seen_urls:
                            reason = 'duplicate_redirect_url'
                        if not reason:
                            image_url = art.get('og_image', '')
                            if not image_url or is_bad_image_url(image_url):
                                reason = 'missing_article_photo'
                            else:
                                dest = root / 'candidate-images' / f'{sid}.webp'
                                record['photo_attempted'] = True
                                sync()
                                info = safe_image(image_url, dest)
                                if not info or not dest.is_file() or dest.is_symlink():
                                    reason = 'image_unavailable'
                                elif dest.stat().st_size < MIN_IMAGE_BYTES:
                                    reason = 'image_below_20000'
                                else:
                                    from PIL import Image
                                    with Image.open(dest) as image:
                                        image.verify()
                                    photo = {'ok': True, 'path': str(dest), 'source_url': image_url,
                                             'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(),
                                             'final_bytes': dest.stat().st_size}
                                    record.update(article=art, photo=photo, qualified=True)
                                    art['_publisher_key'] = publisher_key({'rss_url': art.get('evidence_url') or url})
                                    b['publisher'] = art['_publisher_key']
                                    qualified += 1
                                    seen_urls.add(evidence)
                                    b['mechanical'] = {'image_bytes': photo['final_bytes'], 'words': count,
                                        'freshness': ('not_required' if cat == 'Science' else 'current') if strict_dates else date_check(b['published'], today, 5),
                                        'fits': [c for c in ('News', 'Science', 'Fun') if original_band(c)[0] <= count <= original_band(c)[1]]}
                    except Exception as exc:
                        reason = 'fetch_or_decode_' + type(exc).__name__
                record.update(status='complete', reason=reason or '', seconds=round(time.monotonic() - started, 3))
                sync()
            if source_state['status'] != 'feed_failed':
                source_state['status'] = 'suspended' if len(source_state['results']) >= 6 and not qualified else 'complete'
            done_groups.add(source_state['publisher'] if cat == 'Science' else source.name)
            good += qualified
            newly_processed += 1
            sync()
        section.update(complete=True, qualified=good, attempted_groups=len(done_groups),
                       shortfall=max(0, limits['min_good'] - good),
                       groups_shortfall=max(0, limits['min_groups'] - len(done_groups)))
        sync()
    return [r['candidate'] for r in all_results() if r.get('qualified')]


def validate_priority_batch(value, pool, category):
    from .agent_shadow_batch import validate_batch
    errors = validate_batch(value, pool, category)
    if not errors and category == 'News' and pool:
        highest = max(b['importance'] for b in pool)
        best = {b['id'] for b in pool if b['importance'] == highest}
        included = {b['id'] for b in value['drafts']}
        skipped = {b['id'] for b in value.get('skipped', [])}
        if not best & included and not best <= skipped:
            errors.append('Highest importance News must be included first or every tied highest explicitly skipped with reason')
    return errors
