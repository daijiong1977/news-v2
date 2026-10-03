"""Python-owned fixed-five editor; any completion provider is JSON in/out.

No interactive agent/file handoff, DB or publishing tools. Completed answers
and provider configuration are pinned; uncertain model sends are never repeated.
"""
import json
from pathlib import Path
import time

from .agent_shadow import CATS, read, write, run_lock, verify_answer_hashes
from .kidsnews_groups import digest, pin, prepare_groups, limit_fun_sports_order
from .publication_bundle import sha


class CachedJSON:
    def __init__(self, root, provider, identity):
        self.root, self.provider, self.identity = Path(root), provider, identity
        path = self.root / 'api-editor-provider.json'
        if path.exists() and read(path) != identity:
            raise ValueError('Frozen Agent provider changed; use a new directory')
        if not path.exists():
            write(path, identity); pin(self.root, path)

    def __call__(self, root, key, prompt, material, validate):
        from .agent_shadow import AnswerRejected
        payload = {'messages': [{'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)}]}
        rid = digest({'key': key, 'payload': payload, 'provider': self.identity})
        folder = self.root / 'api-tasks' / key / rid
        request, answer, attempt = (folder / n for n in ('request.json', 'answer.json', 'attempt.json'))
        if not request.exists():
            write(request, {'request_id': rid, 'task': payload}); pin(self.root, request)
        if not answer.exists():
            if attempt.exists():
                raise ValueError('Agent outcome uncertain; preserve API task, do not resend blindly: ' + key)
            if len(list((self.root/'api-tasks').glob('*/*/attempt.json'))) >= 120:
                raise ValueError('Agent API call budget exhausted; preserve state')
            write(attempt, {'status': 'attempting', 'request_id': rid})
            started = time.monotonic()
            result = self.provider.complete(payload, 600)
            choice = result['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('Agent answer incomplete: ' + key)
            from .cursor_json import parse_object
            value = parse_object(choice['message']['content'])
            write(answer, {'request_id': rid, 'value': value, 'usage': result.get('usage', {}),
                           'model': result.get('model'),
                           'seconds': round(time.monotonic()-started, 3)})
            pin(self.root, answer)
        saved = read(answer)
        self.last_metadata = {k:saved.get(k) for k in ('usage','model','seconds')}
        if saved.get('request_id') != rid:
            raise ValueError('API answer identity mismatch')
        errors = validate(saved['value'])
        if errors:
            raise AnswerRejected('; '.join(errors))
        return saved['value']


def edit_groups(root, provider, identity):
    from .agent_shadow_batch import validate_fixed_order
    from .agent_shadow_finish import finish, METHOD
    if (Path(root)/'all-ai-providers.json').exists():
        METHOD = 'Codex 同模型精修、详情生成并自检（非独立审核）'
    from .news_rss_core import evaluate_rewriter_safety
    root = Path(root)
    with run_lock(root):
        verify_answer_hashes(root)
        prepare_groups(root)
        ask = CachedJSON(root, provider, identity)
        state_path = root / 'editor-state.json'
        state = read(state_path) if state_path.exists() else {c: {'accepted': [], 'outcomes': [],
                 'order': [], 'pool_ids': [], 'pick_done': False, 'target': 8} for c in CATS}
        snapshot = read(root / 'input.json')
        refresh_path = root / 'groups/history-refresh.json'
        refresh = read(refresh_path) if refresh_path.exists() else None
        for cat in CATS:
            request = read(root / 'groups' / f'{cat}-request.json')
            raw = read(root / f'raw-batch-{cat}-8.json')
            candidates = {b['id']: b for b in raw['originals']}
            if (root/'all-ai-providers.json').exists():
                for candidate in candidates.values():
                    candidate['writer_provider'] = identity['type']
            ids = [r['id'] for r in raw['result']['drafts']]
            section = state[cat]
            sports_limit = cat == 'Fun' and bool(request.get('fun_topic_limits'))
            if not section['pick_done']:
                # Selection only; ONE article per subsequent completion.
                prompt = request['prompt'].split('One article at a time:')[0] + '\nReturn ONLY {order:[all five IDs],reason:string}.'
                material = {'category': cat, 'history': request['history'], 'candidates': request['candidates']}
                def validate_order(v):
                    errors = validate_fixed_order(v, [candidates[sid] for sid in ids])
                    if not isinstance(v.get('reason'), str) or not v['reason'].strip():
                        errors.append('Selection reason required')
                    return errors
                from .agent_shadow import AnswerRejected
                try:
                    selection = ask(root, 'group-order-'+cat, prompt, material, validate_order)
                except AnswerRejected as exc:
                    selection = ask(root, 'group-order-fix-'+cat, prompt,
                                    {**material, 'errors': str(exc)}, validate_order)
                if sports_limit:
                    original_order = selection['order'][:]
                    order, moved = limit_fun_sports_order(original_order, [candidates[sid] for sid in ids])
                    selection = {**selection, 'order': order}
                    section['sports_adjustment'] = {'original_order': original_order,
                        'moved_to_reserves': moved, 'limits': request['fun_topic_limits'],
                        'reason': 'Keep highest-ranked story per tennis/swimming; promote others in model ranking order'}
                section.update(order=selection['order'], pool_ids=selection['order'], pick_done=True)
                section['selection_reason'] = selection['reason']; write(state_path, state)
            for sid in section['order']:
                if len(section['accepted']) == 3:
                    break
                if any(a['candidate']['id'] == sid for a in section['accepted']) or any(
                    o['id'] == sid and o['status'] == 'gone' for o in section['outcomes']):
                    continue
                if refresh and sid in refresh['blocked_ids']:
                    section['outcomes'].append({'id':sid,'category':cat,'status':'gone',
                        'reason':'Duplicate/uncertain under refreshed history','review_method':METHOD})
                    write(state_path,state);continue
                candidate = candidates[sid]
                if sports_limit:
                    from .agent_shadow_batch import FUN_SPORTS_TOPICS
                    if (candidate.get('topic') in FUN_SPORTS_TOPICS and any(
                            a['candidate'].get('topic') == candidate['topic'] for a in section['accepted'])):
                        if not any(o['id'] == sid and o['status'] == 'not_selected_sports_limit' for o in section['outcomes']):
                            section['outcomes'].append({'id': sid, 'category': cat,
                                'status': 'not_selected_sports_limit', 'reason': 'One '+candidate['topic']+' story already ready'})
                            write(state_path, state)
                        continue
                draft = next(d['article'] for d in raw['result']['drafts'] if d['id'] == sid)
                accepted = [{'title': a['candidate']['article']['title'],
                             'source_excerpt': a['candidate']['article']['body'][:1200]}
                            for a in section['accepted']]
                result = finish(root, cat, sid, candidate['article'], draft,
                                refresh['history'][cat] if refresh else snapshot['history'][cat], accepted, ask)
                if not result['status'].startswith('ready_'):
                    section['outcomes'].append({'id': sid, 'category': cat, 'status': 'gone',
                                               'reason': result['reason'], 'review_method': METHOD})
                    write(state_path, state); continue
                review = result['review']
                section['accepted'].append({'candidate': candidate, 'entry': result['entry'],
                                            'details': result['details'], 'ready_status': result['status']})
                section['outcomes'].append({'id': sid, 'category': cat, 'status': result['status'],
                    'review_method': METHOD, 'writer_provider': identity['type'] if (root/'all-ai-providers.json').exists() else candidate.get('writer_provider', 'deepseek'),
                    'selection_round': 1, 'warnings': result.get('warnings', []),
                    'removed': result.get('removed', []), 'body_repairs': result.get('body_repairs', 0),
                    'detail_repairs': result.get('detail_repairs', 0),
                    'facts_supported': review['facts_supported'], 'event_clear': review['event_clear'],
                    'notes': review['notes'], 'safety': evaluate_rewriter_safety(
                        {'safety': review['scores']['0']}, category=cat), 'final_sha256': result['final_sha256']})
                write(state_path, state)
            if len(section['accepted']) != 3:
                raise ValueError(cat+': fixed five exhausted; cannot fabricate safe/unique stories')
        imported = root / 'groups/imported.json'
        if not imported.exists():
            write(imported, {'counts': {c: 3 for c in CATS}, 'provider': identity,
                             'method': METHOD, 'api_editor': True})
            pin(root, imported)
        return {'ok': True, 'counts': {c: 3 for c in CATS}}
