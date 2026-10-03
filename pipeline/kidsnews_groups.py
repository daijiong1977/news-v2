"""Offline Grok workspace between two Python invocations; no model calls.

Prepare freezes self-contained groups. Import reuses the existing bounded finish
validator, but reads Agent-written files instead of requesting another model.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from .agent_shadow import CATS, read, write, verify_answer_hashes


class GroupNeeded(ValueError):
    def __init__(self, message, path):
        super().__init__(message)
        self.path = str(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def limit_fun_sports_order(order, pool):
    """Keep the model's highest-ranked tennis/swimming story per sport, no AI."""
    from .agent_shadow_batch import FUN_SPORTS_TOPICS, validate_fixed_order
    errors = validate_fixed_order({'order': order}, pool)
    if errors:
        raise ValueError('; '.join(errors))
    index = {b['id']: b for b in pool}
    eligible, moved = [], []
    sports_seen = set()
    for sid in order:
        topic = index[sid].get('topic')
        if topic in FUN_SPORTS_TOPICS:
            if topic in sports_seen:
                moved.append(sid)
                continue
            sports_seen.add(topic)
        eligible.append(sid)
    if len(eligible) < 3:
        raise ValueError('Fun fixed five needs three eligible stories under one-per-tennis/swimming caps; preserve state')
    winners = eligible[:3]
    return winners + [sid for sid in order if sid not in winners], moved


def answer_json(path):
    try:
        value = read(path)
    except (ValueError, OSError) as exc:
        raise GroupNeeded('Fix this answer JSON: ' + type(exc).__name__, path) from exc
    if not isinstance(value, dict):
        raise GroupNeeded('Answer envelope must be a JSON object', path)
    return value


def pin(root, path):
    index = root / 'accepted-answer-hashes.json'
    hashes = read(index) if index.exists() else {}
    hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(index, hashes)


def check_group_stale(root, confirm, registry):
    """Refresh history through a FILE judgment, never HTTP/native ask in Python."""
    from .agent_shadow import registry_history
    from zoneinfo import ZoneInfo
    verify_answer_hashes(root)
    if (root / 'done.json').exists():
        return
    metrics = read(root / 'metrics.json')
    started = metrics.get('history_rechecked_at') or metrics.get('started_at')
    if not started or (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds() <= 86400:
        return
    if not confirm or registry is None:
        raise ValueError('stale_run: preserve files; finalize --confirm-stale --registry FRESH_REGISTRY to get a file-only history recheck')
    fresh = read(registry)
    today = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    snapshot = read(root / 'input.json')
    if fresh.get('date') != today or not isinstance(fresh.get('history'), list):
        raise ValueError('Fresh registry must have today ET date and history list')
    history = {cat: registry_history(fresh['history'], cat, today, exclude_date=snapshot['date']) for cat in CATS}
    if not any(history.values()):
        raise ValueError('Fresh history is zero; check connector')
    candidates = {cat: [{'id': r['id'], 'title': r['source']['title'],
                        'abstract': r['source'].get('summary', '')}
                       for r in read(root / 'groups' / f'{cat}-request.json')['candidates']] for cat in CATS}
    material = {'date': today, 'target_date': snapshot['date'], 'history': history, 'candidates': candidates,
                'prompt': 'Recheck every ID ONLY against its own category seven-day history. Return all IDs partitioned into clear_ids and blocked_ids; duplicate OR uncertain goes blocked. Do not modify articles, code or frozen input.'}
    request_id = digest(material)
    folder = root / 'groups/history-refresh' / request_id
    answer = folder / 'answer.json'
    write(folder / 'request.json', {**material, 'request_id': request_id, 'write_to': str(answer),
        'schema': {'request_id': request_id, 'clear_ids': [], 'blocked_ids': []}})
    pin(root, folder / 'request.json')
    if not answer.exists():
        raise GroupNeeded('Recheck stale history using this request and write its answer, then finalize again', folder / 'request.json')
    value = answer_json(answer)
    ids = {r['id'] for rows in candidates.values() for r in rows}
    clear, blocked = value.get('clear_ids'), value.get('blocked_ids')
    if (value.get('request_id') != request_id or not isinstance(clear, list) or not isinstance(blocked, list)
            or any(not isinstance(sid, str) for sid in clear + blocked)
            or len(set(clear + blocked)) != len(clear + blocked) or set(clear + blocked) != ids):
        raise GroupNeeded('Partition all fifteen supplied IDs once, with matching request_id', answer)
    # Fixed membership remains fixed; a fresh duplicate cannot slip through
    # merely because a body was already accepted earlier in the same directory.
    for cat in CATS:
        selection = root / 'groups' / f'{cat}-selection.json'
        if selection.exists() and set(read(selection).get('order', [])[:3]) & set(blocked):
            raise GroupNeeded('Winner is duplicate/uncertain under fresh history; select within the same five, preserve already accepted articles', selection)
    pin(root, answer)
    write(root / 'groups/history-refresh.json', {'request_id': request_id, 'history': history, 'blocked_ids': blocked})
    pin(root, root / 'groups/history-refresh.json')
    metrics['history_rechecked_at'] = datetime.now(timezone.utc).isoformat()
    write(root / 'metrics.json', metrics)


def prepare_groups(root):
    from .agent_shadow_finish import PROMPT
    from .agent_shadow_lengths import rewrite_band
    from .agent_shadow_batch import FAMILY_SPORTS_PREFERENCE, FUN_SPORTS_LIMIT_RULE
    verify_answer_hashes(root)
    folder = root / 'groups'
    manifest = folder / 'manifest.json'
    if manifest.exists():
        return read(manifest)
    if (root / 'editor-state.json').exists():
        raise ValueError('Cannot convert an interleaved run to three-stage mode; keep its original command')
    snapshot = read(root / 'input.json')
    drafts = read(root / 'drafts-for-grok.json')
    if snapshot.get('test_profile') != 'source-first-deepseek' or drafts['counts'] != {c: 5 for c in CATS}:
        raise ValueError('Three-stage mode requires the complete fixed fifteen drafts')
    files = {}
    for cat in CATS:
        raw = read(root / f'raw-batch-{cat}-8.json')
        originals = {b['id']: b for b in raw['originals']}
        rows = []
        for item in (r for r in drafts['articles'] if r['category'] == cat):
            source = originals[item['id']]['article']
            rows.append({**item, 'source': source,
                         'topic': originals[item['id']]['topic'],
                         'importance': originals[item['id']]['importance'],
                         'body_word_bands': {level: rewrite_band(level, cat, source['word_count'])
                                             for level in ('easy', 'middle')}})
        material = {'date': snapshot['date'], 'category': cat, 'history': snapshot['history'][cat],
                    'candidates': rows, 'prompt': '''Choose exactly THREE from these fixed FIVE.
Return all five IDs in order, the three completed winners FIRST and two reserves.
News: important suitable story first. Science: prefer different disciplines and
publishers. Fun: genuine fun, current swimming/tennis stars, then other topics.
These are soft preferences except the Fun sports hard limit below; relax soft
preferences to complete three, never add a sixth.
Exactly three finished stories per category is the goal. Science can have all
three from one publisher and one discipline. Similar topics are allowed, but
the same event/research/discovery is NOT allowed twice, including seven-day history.
Complete the best three by removing unsuitable details and adding accurate general
explanations when needed; record relaxed preferences. Never invent news facts.
One article at a time: correct body, create Easy/Middle details and self-check
together. Save each answer immediately. Do NOT run intermediate Python, search,
change code, call external models, deploy, write databases or delete checkpoints.
Compare the three winners with each other as well as supplied category history.
''' + (FAMILY_SPORTS_PREFERENCE + FUN_SPORTS_LIMIT_RULE if cat == 'Fun' else '') + PROMPT,
                    'selection_schema': {'request_id': '<request_id>', 'order': ['<all five IDs, winners first>'],
                                         'reason': '<selection and any relaxed preferences>'},
                    'article_schema': {'request_id': '<request_id>', 'id': '<candidate ID>',
                                       'value': '<combined object required by prompt>'}}
        if cat == 'Fun':
            material['fun_topic_limits'] = {'tennis': 1, 'swimming': 1}  # Old checkpoints keep their policy.
        material['request_id'] = digest(material)
        material['selection_write_to'] = str(folder / f'{cat}-selection.json')
        material['article_write_to'] = str(folder / 'answers' / f'{cat}-<ID>.json')
        path = folder / f'{cat}-request.json'
        if path.exists() and read(path) != material:
            raise ValueError('Existing group request differs; do not overwrite checkpoint')
        write(path, material)
        pin(root, path)
        files[cat] = str(path)
    # Freeze the source of the requests too: import/pack must use the same
    # cached originals, catalog and history, never a silently edited input.
    for name in ['input.json', 'drafts-for-grok.json', 'autonomous-catalog.json',
                 'shortlist-plan.json'] + [f'raw-batch-{c}-8.json' for c in CATS]:
        pin(root, root / name)
    result = {'version': 1, 'profile': snapshot['test_profile'], 'counts': drafts['counts'],
              'prepared_at': datetime.now(timezone.utc).isoformat(),
              'requests': files, 'next': 'Grok writes three selections and nine combined article answers; then finalize'}
    write(manifest, result)
    pin(root, manifest)
    return result


def import_groups(root):
    """Validate disk answers, preserving ready articles and bounded repair state."""
    from .agent_shadow_batch import validate_fixed_order
    from .agent_shadow_finish import finish, METHOD
    from .news_rss_core import evaluate_rewriter_safety
    verify_answer_hashes(root)
    folder = root / 'groups'
    if not (folder / 'manifest.json').exists():
        raise ValueError('Run prepare first; finalize never fetches or calls DeepSeek')
    snapshot = read(root / 'input.json')
    state_path = root / 'editor-state.json'
    state = read(state_path) if state_path.exists() else {c: {'accepted': [], 'outcomes': [],
                  'order': [], 'pool_ids': [], 'pick_done': False, 'target': 8} for c in CATS}
    for cat in CATS:
        request = read(folder / f'{cat}-request.json')
        selection_path = folder / f'{cat}-selection.json'
        if not selection_path.exists():
            raise GroupNeeded('Write the group selection before finalize', selection_path)
        selection = answer_json(selection_path)
        raw = read(root / f'raw-batch-{cat}-8.json')
        candidates = {b['id']: b for b in raw['originals']}
        ids = [d['id'] for d in raw['result']['drafts']]
        errors = validate_fixed_order(selection, [candidates[sid] for sid in ids],
                                      'Fun' if request.get('fun_topic_limits') else None)
        if selection.get('request_id') != request['request_id']:
            errors.append('request_id must match the frozen group request')
        if not isinstance(selection.get('reason'), str) or not selection['reason'].strip():
            errors.append('Selection reason required')
        if errors:
            raise GroupNeeded('; '.join(errors), selection_path)
        section = state[cat]
        winners = selection['order'][:3]
        refresh = read(folder / 'history-refresh.json') if (folder / 'history-refresh.json').exists() else None
        if refresh and set(winners) & set(refresh['blocked_ids']):
            raise GroupNeeded('Selected ID is blocked by refreshed seven-day history', selection_path)
        accepted = {a['candidate']['id']: a for a in section['accepted']}
        if not set(accepted) <= set(winners):
            raise ValueError('Already accepted article cannot be replaced; preserve it in the three winners')
        section.update(order=selection['order'], pool_ids=selection['order'], pick_done=True)
        write(state_path, state)
        for sid in winners:
            if sid in accepted:
                continue
            answer_path = folder / 'answers' / f'{cat}-{sid}.json'
            checkpoint = folder / f'{cat}-{sid}-consumed.json'
            def disk_answer(_root, key, prompt, material, validate):
                if not answer_path.exists():
                    raise GroupNeeded('Write this combined article answer; no Python/model loop', answer_path)
                envelope = answer_json(answer_path)
                if envelope.get('request_id') != request['request_id'] or envelope.get('id') != sid:
                    raise GroupNeeded('Answer ID/request_id mismatch', answer_path)
                previous = read(checkpoint) if checkpoint.exists() else {}
                current_hash = digest(envelope)
                if previous.get('hash') == current_hash and previous.get('key') != key:
                    repair = {'read': str(answer_path), 'task': key, 'errors': material.get('errors', []),
                              'instruction': 'Fix ONLY this article/failed details and save the same answer file; keep passed body unchanged for detail-only repair'}
                    write(folder / 'repair.json', repair)
                    raise GroupNeeded('; '.join(repair['errors']) or 'Targeted correction required', answer_path)
                value = envelope.get('value')
                if not isinstance(value, dict):
                    raise GroupNeeded('value must be a combined JSON object', answer_path)
                if 'review-detail-fix-' in key or ('review-finish-fix-' in key and 'immutable' in prompt):
                    value = {'details': value.get('details')}
                write(checkpoint, {'key': key, 'hash': current_hash})
                return deepcopy(value)
            b = candidates[sid]
            draft = next(d['article'] for d in raw['result']['drafts'] if d['id'] == sid)
            context = [{'title': a['candidate']['article']['title'],
                        'source_excerpt': a['candidate']['article']['body'][:1200]} for a in section['accepted']]
            result = finish(root, cat, sid, b['article'], draft,
                            refresh['history'][cat] if refresh else snapshot['history'][cat], context, disk_answer)
            if not result['status'].startswith('ready_'):
                if not any(o['id'] == sid and o['status'] == 'gone' for o in section['outcomes']):
                    section['outcomes'].append({'id': sid, 'category': cat, 'status': 'gone',
                        'reason': result['reason'], 'review_method': METHOD,
                        'writer_provider': b.get('writer_provider', 'deepseek')})
                    write(state_path, state)
                raise GroupNeeded('Bounded correction failed; choose a reserve within the SAME five: ' + result['reason'], selection_path)
            review = result['review']
            section['accepted'].append({'candidate': b, 'entry': result['entry'], 'details': result['details'],
                                        'ready_status': result['status']})
            section['outcomes'].append({'id': sid, 'category': cat, 'status': result['status'],
                'review_method': METHOD, 'writer_provider': b.get('writer_provider', 'deepseek'),
                'selection_round': 1, 'warnings': result.get('warnings', []), 'removed': result.get('removed', []),
                'body_repairs': result.get('body_repairs', 0), 'detail_repairs': result.get('detail_repairs', 0),
                'facts_supported': review['facts_supported'], 'event_clear': review['event_clear'],
                'notes': review['notes'], 'safety': evaluate_rewriter_safety({'safety': review['scores']['0']}, category=cat),
                'final_sha256': result['final_sha256']})
            pin(root, answer_path)
            write(state_path, state)
        section['accepted'].sort(key=lambda a: winners.index(a['candidate']['id']))
        write(state_path, state)
        pin(root, selection_path)
    if not (folder / 'imported.json').exists():
        write(folder / 'imported.json', {'counts': {c: len(state[c]['accepted']) for c in CATS},
                                        'imported_at': datetime.now(timezone.utc).isoformat(),
                                        'method': METHOD, 'model_calls': 0})
        pin(root, folder / 'imported.json')
    return {'ok': True, 'counts': {c: len(state[c]['accepted']) for c in CATS}}
