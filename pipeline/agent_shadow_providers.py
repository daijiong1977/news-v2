"""Shadow-only role routing. Native files default; compatible HTTP is opt-in.

Credentials are environment-variable references, never request/answer content.
Search uses native Agent tools; a text-only HTTP backend cannot silently browse.
"""
import hashlib
import json
import os
import time
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from .ai_providers.transport import AgentFilesProvider, AgentNeeded, OpenAICompatibleProvider, _atomic_json

MAX_TASKS = 120
MAX_HTTP_CALLS = 120
MAX_RUN_SECONDS = 3600
MAX_TRANSPORT_RETRIES = 3


def transport_failure(exc):
    """Conservative: a reset is NOT proof that the server never received a POST."""
    response = getattr(exc, 'response', None)
    status = response.status_code if response is not None else None
    before_send = isinstance(exc, requests.ConnectTimeout)
    chain = repr(exc)
    before_send |= isinstance(exc, requests.ConnectionError) and any(
        marker in chain for marker in ('NewConnectionError', 'NameResolutionError',
                                      'Failed to establish a new connection', 'Connection refused'))
    known = (isinstance(exc, requests.HTTPError) and response is not None) or before_send
    delay = 0
    if status == 429:
        raw = response.headers.get('Retry-After', '0')
        try:
            delay = float(raw)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError):
                delay = 0
    return {'status': 'failed_not_executed' if known else 'outcome_uncertain',
            'error_class': type(exc).__name__, 'http_status': status,
            'retry_after': max(0, min(120, delay))}


def rebuild_audit(root, config_hash):
    """Answer is the commit record; audit is a recoverable index, not authority."""
    path = root / 'provider-audit.json'
    audit = json.loads(path.read_text()) if path.exists() else {
        'config_sha256': config_hash, 'task_count': 0, 'http_calls': 0,
        'fallback_tasks': 0, 'requests': {}, 'started_unix': time.time()}
    if audit['config_sha256'] != config_hash:
        raise ValueError('Provider configuration changed during run; use a fresh directory')
    for request in (root / 'tasks').glob('*/*/request.json'):
        directory = request.parent
        token = f'{directory.parent.name}:{directory.name}'
        entry = audit['requests'].setdefault(token, {'role': task_role(directory.parent.name)})
        state_path, answer_path = directory / 'http-attempt.json', directory / 'answer.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if state.get('status') in ('fallback_pending', 'fallback_native'):
            entry.update(fallback='native', original_failure=state.get('original_failure'))
        audit['http_calls'] = max(audit['http_calls'], state.get('http_call_number', 0))
        for saved in directory.glob('answer*.json'):
            try:
                data = json.loads(saved.read_text())
            except (ValueError, OSError):
                continue
            if data.get('request_id') != directory.name or 'revision' not in data:
                continue
            attempt = {k: data.get(k) for k in ('revision', 'attempt_id', 'usage', 'seconds', 'model')}
            attempts = entry.setdefault('attempts', [])
            if not any(a.get('attempt_id') == attempt['attempt_id'] for a in attempts):
                attempts.append(attempt)
            entry.update({k: data.get(k) for k in ('usage', 'seconds', 'model')})
            audit['http_calls'] = max(audit['http_calls'], data.get('http_call_number', 0))
    audit['fallback_tasks'] = sum(e.get('fallback') == 'native' for e in audit['requests'].values())
    audit['task_count'] = max(audit['task_count'], len(audit['requests']) + audit['fallback_tasks'])
    return audit


def fallback_run(root, *, register_only=False):
    """Cross-directory circuit breaker. Ledger is runtime state, never a credential."""
    import fcntl
    parent = root.parent.parent if len(root.parent.name) == 10 and root.parent.name[4:5] == '-' else root.parent
    path = parent / '.http-fallback-runs.json'
    with (parent / '.http-fallback-runs.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        runs = json.loads(path.read_text()) if path.exists() else []
        name = str(root.resolve())
        if not any(r['run'] == name for r in runs):
            runs.append({'run': name, 'fallback': False})
        current = next(r for r in runs if r['run'] == name)
        index = runs.index(current)
        if not register_only and index and runs[index-1]['fallback']:
            raise ValueError('Two consecutive fallback runs: stop and check API key/account manually')
        if not register_only:
            current['fallback'] = True
        _atomic_json(path, runs)


def validate_config(config):
    if not isinstance(config, dict) or set(config) != {'roles'} or not isinstance(config['roles'], dict):
        raise ValueError('Provider config must contain only a roles mapping; no credentials')
    for role, choice in config['roles'].items():
        if role not in {'rank', 'editor', 'write', 'review', 'details', 'detail_review', 'discovery', 'image_review'} or not isinstance(choice, dict):
            raise ValueError('Unknown provider role/config')
        required = {'type'} if choice.get('type') == 'native' else {'type', 'model', 'endpoint', 'key_env'}
        if set(choice) != required or choice.get('type') not in {'native', 'http'}:
            raise ValueError('Only native or HTTP environment-reference configuration allowed; no secrets')
        if any(not isinstance(v, str) or not v for v in choice.values()):
            raise ValueError('Provider fields must be nonempty strings')
        if role in {'discovery', 'image_review'} and choice['type'] != 'native':
            raise ValueError('Discovery/photo review requires a native Agent with search/vision tools')


def task_role(key):
    if key.startswith('rank-shortlist-'):
        return 'rank'
    if key.startswith('review-image-'):
        return 'image_review'
    if key.startswith('discover-'):
        return 'discovery'
    if key.startswith('review-details-'):
        return 'detail_review'
    if key.startswith('review-'):
        return 'review'
    if key.startswith('rewrite-'):
        return 'write'
    if key.startswith('details-'):
        return 'details'
    return 'editor'


class TaskRouter:
    def __init__(self, root, key):
        self.root, self.key = root, key
        self.files = AgentFilesProvider(root / 'tasks' / key)
        self.work_dir = self.files.work_dir
        self.role = task_role(key)
        path = root / 'providers.json'
        self.config = json.loads(path.read_text()) if path.exists() else {'roles': {}}
        validate_config(self.config)
        roles = self.config.get('roles', {})
        fallback = roles.get('review', {'type': 'native'}) if self.role == 'detail_review' else {'type': 'native'}
        self.choice = roles.get(self.role, fallback)

    def prepare_payload(self, payload):
        if self.choice.get('type') == 'http':
            return {**payload, 'model': self.choice['model']}
        return payload

    def complete(self, payload, timeout):
        fallback_run(self.root, register_only=True)
        payload = self.prepare_payload(payload)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        rid = hashlib.sha256(canonical.encode()).hexdigest()
        audit_path = self.root / 'provider-audit.json'
        config_hash = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest()
        audit = rebuild_audit(self.root, config_hash)
        if audit['config_sha256'] != config_hash:
            raise ValueError('Provider configuration changed during run; use a fresh directory')
        token = f'{self.key}:{rid}'
        if token not in audit['requests']:
            if audit['task_count'] >= MAX_TASKS:
                raise ValueError('Shadow task budget exhausted')
            audit['requests'][token] = {'role': self.role, 'type': self.choice.get('type', 'native')}
            audit['task_count'] += 1
            _atomic_json(audit_path, audit)
        try:
            envelope = self.files.complete(payload, 0)
            needed = None
        except AgentNeeded as exc:
            needed, envelope = exc, None
        directory = self.work_dir / rid
        if self.choice.get('type', 'native') == 'native':
            if needed:
                if self.role == 'discovery':
                    data = json.loads(needed.request.read_text())
                    data['instructions'] = ('Discovery only: use native public search/browser tools within task limits. '
                        'No credentials, code changes, registry writes or publishing. Follow task.messages and schema; '
                        'if tools are unavailable return articles: []. Write answer.json then rerun.')
                    _atomic_json(needed.request, data)
                raise needed
            return envelope
        if self.choice.get('type') != 'http':
            raise ValueError('Provider type must be native or http')
        if self.role == 'discovery':
            raise ValueError('Discovery requires a native Agent with search tools, not text-only HTTP')
        endpoint = self.choice.get('endpoint', '')
        parts = urlsplit(endpoint)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
            raise ValueError('HTTP provider endpoint must be credential-free HTTPS')
        key_env = self.choice.get('key_env')
        errors_path = directory / 'validation-errors.json'
        errors = json.loads(errors_path.read_text()) if errors_path.exists() else []
        snapshot = self.root / 'input.json'
        from .agent_shadow_profiles import is_hybrid
        hybrid = snapshot.exists() and is_hybrid(json.loads(snapshot.read_text()))
        if len(errors) > (2 if hybrid else 1):
            raise ValueError('HTTP task correction budget exhausted')
        revision = hashlib.sha256(json.dumps(errors, sort_keys=True).encode()).hexdigest()
        state_path = directory / 'http-attempt.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        answer_path = directory / 'answer.json'
        data = json.loads(answer_path.read_text()) if envelope is not None else {}
        falling_back = state and state.get('status') in ('fallback_pending', 'fallback_native')
        if (envelope is not None and data.get('request_id') == rid and data.get('revision') == revision
                and (not falling_back or data.get('fallback') == 'native')):
            _atomic_json(audit_path, audit)
            return {**envelope, 'usage': data.get('usage', {})}
        snapshot_data = json.loads(snapshot.read_text()) if snapshot.exists() else {}
        def native_fallback(failure):
            nonlocal state, needed, envelope
            if not state or state.get('status') not in ('fallback_pending', 'fallback_native'):
                if audit['task_count'] >= MAX_TASKS:
                    raise ValueError('Shadow fallback task budget exhausted')
                fallback_run(self.root)
                audit['task_count'] += 1
                audit['fallback_tasks'] = audit.get('fallback_tasks', 0) + 1
                audit['requests'][token].update(fallback='native', original_failure=failure)
                # Pending is durable BEFORE quarantine: every crash point resumes
                # cleanup rather than relabelling an older HTTP answer as native.
                state = {**(state or {}), 'status': 'fallback_pending', 'revision': revision,
                         'original_failure': failure}
                _atomic_json(state_path, state)
                envelope = None
                needed = AgentNeeded(rid, directory / 'request.json', answer_path,
                                     ['Transport fallback: write native answer.json in this directory.'])
            if answer_path.exists():
                saved = json.loads(answer_path.read_text())
                if 'revision' in saved and saved.get('fallback') != 'native':
                    # Also repair the old fallback_native crash window. Native
                    # handoff answers have no revision until provenance is pinned.
                    _atomic_json(directory / 'answer.before-fallback.json', saved)
                    answer_path.unlink()
                    envelope = None
                    needed = AgentNeeded(rid, directory / 'request.json', answer_path,
                                         ['Transport fallback: write a NEW native answer.json.'])
            _atomic_json(audit_path, audit)
            request_path = directory / 'request.json'
            request = json.loads(request_path.read_text())
            request['instructions'] = ('NATIVE TRANSPORT FALLBACK. Same request_id and validation. '
                'Use supplied sources only. Batch writing: write FOUR drafts (3+1), not five. '
                'No transport max_tokens limit. Preserve reviewed work; do not resend the group. '
                'This is same-model writing/self-check, NOT a second-model audit. '
                'Write answer.json and rerun in the SAME directory.')
            request['task'].pop('max_tokens', None)
            if self.key.startswith('rewrite-batch-'):
                override = ('NATIVE FALLBACK BATCH OVERRIDE: write at most FOUR drafts (3+1), '
                            'or fewer if fewer eligible candidates. This overrides any five-draft instruction.')
                messages = request['task'].setdefault('messages', [])
                if not any(m.get('content') == override for m in messages):
                    messages.append({'role': 'user', 'content': override})
            request['fallback'] = 'native'
            _atomic_json(request_path, request)
            state = {**state, 'status': 'fallback_native'}
            _atomic_json(state_path, state)
            if needed:
                raise needed
            # Pin provenance only after the native agent has delivered its answer.
            native_answer = json.loads(answer_path.read_text())
            native_answer.update(revision=revision, attempt_id=state.get('attempt_id'),
                                 fallback='native', original_failure=state.get('original_failure'),
                                 usage={}, writer_provider='native')
            if native_answer != json.loads(answer_path.read_text()):
                _atomic_json(answer_path, native_answer)
            return envelope
        if falling_back:
            return native_fallback(state.get('original_failure'))
        if state and state.get('revision') == revision and state.get('status') == 'response_invalid':
            raise ValueError('HTTP response_invalid; not a transport failure, native fallback forbidden')
        if state and state.get('revision') == revision and state['status'] in ('attempting', 'outcome_uncertain'):
            failure = {**state, 'status': 'outcome_uncertain'}
            _atomic_json(state_path, failure)
            if snapshot_data.get('http_fallback') == 'native':
                return native_fallback(failure)
            raise ValueError('HTTP attempt outcome uncertain; preserve directory, do not resend this task')
        if envelope is not None and not errors and 'revision' not in data:
            # Legacy already-completed native/HTTP answers remain usable.
            return envelope
        if not isinstance(key_env, str) or not os.environ.get(key_env):
            raise ValueError('Configured provider credential environment variable is missing')
        sent = payload
        if errors:
            correction = 'Correct your previous answer once: ' + json.dumps(errors[-1])
            previous_messages = []
            if hybrid:
                from .agent_shadow_errors import correction_kind
                if correction_kind(errors[-1]) == 'format':
                    correction = ('Repair JSON format only. Preserve wording, values, attribution and facts; '
                                  'return only the complete JSON object, no fences or commentary. Errors: ' + json.dumps(errors[-1]))
                else:
                    correction = ('Fix only the listed schema/word-count errors using the supplied source; '
                                  'preserve other fields and do not invent facts. Return complete JSON. Errors: ' + json.dumps(errors[-1]))
                if envelope is not None:
                    previous_messages = [{'role': 'assistant', 'content': envelope['choices'][0]['message']['content']}]
            sent = {**payload, 'messages': payload['messages'] + previous_messages + [{'role': 'user', 'content': correction}]}
        if errors and answer_path.exists() and not (directory / 'answer.attempt-1.json').exists():
            _atomic_json(directory / 'answer.attempt-1.json', json.loads(answer_path.read_text()))
        for retry in range(MAX_TRANSPORT_RETRIES):
            if audit['http_calls'] >= MAX_HTTP_CALLS:
                raise ValueError('Shadow HTTP call budget exhausted')
            audit['http_calls'] += 1
            _atomic_json(audit_path, audit)
            attempt_id = f'{rid}:{audit["http_calls"]}'
            state = {'revision': revision, 'attempt_id': attempt_id, 'status': 'attempting',
                     'http_call_number': audit['http_calls']}
            _atomic_json(state_path, state)
            started = time.monotonic()
            try:
                result = OpenAICompatibleProvider(endpoint=endpoint, api_key=os.environ[key_env]).complete(sent, 120)
            except requests.exceptions.JSONDecodeError as exc:
                _atomic_json(state_path, {**state, 'status': 'response_invalid', 'error_class': type(exc).__name__})
                raise ValueError('HTTP response_invalid; not a transport failure') from None
            except (requests.RequestException, TimeoutError, ConnectionResetError) as exc:
                failure = {**state, **transport_failure(exc)}
                _atomic_json(state_path, failure)
                uncertain = failure['status'] == 'outcome_uncertain'
                if uncertain or retry == MAX_TRANSPORT_RETRIES - 1:
                    if snapshot_data.get('http_fallback') == 'native':
                        return native_fallback(failure)
                    raise RuntimeError(f'HTTP task {failure["status"]} ({failure["error_class"]}); preserve run directory') from None
                delay = failure['retry_after']
                while delay > 0:
                    part = min(delay, 60)
                    time.sleep(part)
                    delay -= part
                continue
            # Content/schema errors are NOT transport failures and never trigger fallback.
            try:
                choice = result['choices'][0]
                if not isinstance(choice['message']['content'], str) or choice['finish_reason'] not in ('stop', 'length'):
                    raise ValueError('invalid completion envelope')
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                _atomic_json(state_path, {**state, 'status': 'response_invalid', 'error_class': type(exc).__name__})
                raise ValueError('HTTP response_invalid; not a transport failure') from None
            answer = {'request_id': rid, 'attempt_id': attempt_id, 'revision': revision,
                      'usage': result.get('usage', {}), 'model': payload['model'],
                      'seconds': round(time.monotonic()-started, 3), 'http_call_number': audit['http_calls'],
                      'content': choice['message']['content'], 'finish_reason': choice['finish_reason']}
            _atomic_json(answer_path, answer)
            _atomic_json(audit_path, rebuild_audit(self.root, config_hash))
            return {**self.files.complete(payload, 0), 'usage': answer['usage']}
