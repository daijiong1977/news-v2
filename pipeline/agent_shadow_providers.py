"""Shadow-only role routing. Native files default; compatible HTTP is opt-in.

Credentials are environment-variable references, never request/answer content.
Search uses native Agent tools; a text-only HTTP backend cannot silently browse.
"""
import hashlib
import json
import os
import time
from urllib.parse import urlsplit

from .ai_providers.transport import AgentFilesProvider, AgentNeeded, OpenAICompatibleProvider, _atomic_json

MAX_TASKS = 120
MAX_HTTP_CALLS = 120
MAX_RUN_SECONDS = 3600


def validate_config(config):
    if not isinstance(config, dict) or set(config) != {'roles'} or not isinstance(config['roles'], dict):
        raise ValueError('Provider config must contain only a roles mapping; no credentials')
    for role, choice in config['roles'].items():
        if role not in {'editor', 'write', 'review', 'details', 'discovery'} or not isinstance(choice, dict):
            raise ValueError('Unknown provider role/config')
        required = {'type'} if choice.get('type') == 'native' else {'type', 'model', 'endpoint', 'key_env'}
        if set(choice) != required or choice.get('type') not in {'native', 'http'}:
            raise ValueError('Only native or HTTP environment-reference configuration allowed; no secrets')
        if any(not isinstance(v, str) or not v for v in choice.values()):
            raise ValueError('Provider fields must be nonempty strings')
        if role == 'discovery' and choice['type'] != 'native':
            raise ValueError('Discovery requires a native Agent with search tools')


def task_role(key):
    if key.startswith('discover-'):
        return 'discovery'
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
        self.choice = self.config.get('roles', {}).get(self.role, {'type': 'native'})

    def prepare_payload(self, payload):
        if self.choice.get('type') == 'http':
            return {**payload, 'model': self.choice['model']}
        return payload

    def complete(self, payload, timeout):
        payload = self.prepare_payload(payload)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        rid = hashlib.sha256(canonical.encode()).hexdigest()
        audit_path = self.root / 'provider-audit.json'
        config_hash = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest()
        audit = json.loads(audit_path.read_text()) if audit_path.exists() else {
            'config_sha256': config_hash, 'task_count': 0, 'http_calls': 0, 'requests': {},
            'started_unix': time.time(), 'deadline_seconds': MAX_RUN_SECONDS}
        if audit['config_sha256'] != config_hash:
            raise ValueError('Provider configuration changed during run; use a fresh directory')
        token = f'{self.key}:{rid}'
        if token not in audit['requests']:
            if time.time() - audit['started_unix'] >= MAX_RUN_SECONDS:
                raise ValueError('Shadow run deadline exhausted; use a fresh directory')
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
        if not isinstance(key_env, str) or not os.environ.get(key_env):
            raise ValueError('Configured provider credential environment variable is missing')
        errors_path = directory / 'validation-errors.json'
        errors = json.loads(errors_path.read_text()) if errors_path.exists() else []
        if len(errors) > 1:
            raise ValueError('HTTP task correction budget exhausted')
        revision = hashlib.sha256(json.dumps(errors, sort_keys=True).encode()).hexdigest()
        state_path = directory / 'http-attempt.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        if state and state['revision'] == revision:
            if state['status'] != 'complete':
                raise ValueError('HTTP attempt outcome uncertain; do not auto-retry, use a fresh run')
            if needed:
                raise needed
            return envelope
        if envelope is not None and not errors:
            return envelope
        if audit['http_calls'] >= MAX_HTTP_CALLS:
            raise ValueError('Shadow HTTP call budget exhausted')
        if time.time() - audit['started_unix'] >= MAX_RUN_SECONDS:
            raise ValueError('Shadow run deadline exhausted before HTTP call')
        audit['http_calls'] += 1
        _atomic_json(audit_path, audit)
        _atomic_json(state_path, {'revision': revision, 'status': 'attempting'})
        sent = payload
        if errors:
            sent = {**payload, 'messages': payload['messages'] + [{'role': 'user',
                    'content': 'Correct your previous answer once: ' + json.dumps(errors[-1])}]}
        started = time.monotonic()
        try:
            result = OpenAICompatibleProvider(endpoint=endpoint, api_key=os.environ[key_env]).complete(sent, 120)
            choice = result['choices'][0]
            _atomic_json(directory / 'answer.json', {'request_id': rid, 'content': choice['message']['content'],
                                                    'finish_reason': choice['finish_reason']})
        except Exception as exc:
            raise RuntimeError(f'HTTP task failed ({type(exc).__name__}); do not blindly retry') from None
        audit['requests'][token].update({'seconds': round(time.monotonic()-started, 3),
                                          'usage': result.get('usage', {}), 'model': payload['model']})
        _atomic_json(audit_path, audit)
        _atomic_json(state_path, {'revision': revision, 'status': 'complete'})
        return self.files.complete(payload, 0)
