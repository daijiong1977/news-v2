"""Frozen, credential-free per-stage JSON routing for the Python pipeline."""
from .agent_shadow import read, write
from .kidsnews_groups import pin

STAGES = ('pickup', 'batch_write', 'selection', 'review', 'repair', 'format_fix', 'history_review')


def stage_for(key):
    if key.startswith('stage:'):
        return key.split(':', 2)[1]
    if key.startswith('review-finish-fix-') or key.startswith('review-detail-fix-'):
        return 'repair'
    if key.startswith('group-order-fix-'):
        return 'format_fix'
    if key.startswith('group-order-'):
        return 'selection'
    if key.startswith('history-refresh-'):
        return 'history_review'
    if key.startswith('review-finish-'):
        return 'review'
    raise ValueError('Unmapped AI task: '+key)


class StageProviders:
    def __init__(self, root, config, factory):
        choices = config['ai_stages']
        if not isinstance(choices, dict) or set(choices)-set(STAGES):
            raise ValueError('ai_stages keys must be '+', '.join(STAGES))
        default = config.get('agent_provider', {'type':'codex','model':'gpt-6.1-sol','reasoning':'medium'})
        self.choices = {}
        for stage in STAGES:
            value = choices.get(stage, choices.get('review', default) if stage == 'repair' else default)
            value = {'type':value} if isinstance(value,str) else value
            if not isinstance(value,dict) or value.get('type') not in {'deepseek','grok','codex','claude','cursor','http'}:
                raise ValueError('Invalid provider for '+stage)
            allowed = {'type','model','reasoning','binary','endpoint','key_env'}
            if set(value)-allowed or any(not isinstance(v,str) or not v for v in value.values()):
                raise ValueError('Stage providers accept nonempty settings and key_env references, never credentials')
            self.choices[stage] = value
        path = root/'ai-stages.json'
        if path.exists() and read(path) != self.choices:
            raise ValueError('Frozen ai_stages changed; use a new run directory')
        # Resolve only after validating the entire map, before any model call.
        self.backends = {s:factory({'agent_provider':v}) for s,v in self.choices.items()}
        if not path.exists():
            write(path,self.choices); pin(root,path)
        self.identity = {'type':'stage-router','stages':{s:i for s,(_,i) in self.backends.items()}}

    def for_task(self, key):
        stage = stage_for(key)
        return stage, *self.backends[stage]

    def complete(self, payload, timeout):
        raise ValueError('Stage router requires an explicit task key')
