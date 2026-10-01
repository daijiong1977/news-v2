"""Family sports preference must survive every selection handoff; no real models."""
import pytest
from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_batch import setup_batch
from pipeline.test_agent_shadow_review_fixes import run_steps


@pytest.mark.parametrize('profile,expected', [('batch-grok-details', True), ('batch-deepseek', False)])
def test_sports_preference_in_all_new_selection_prompts_only(tmp_path, monkeypatch, profile, expected):
    _, _, _, answer = setup_batch(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot['test_profile'] = profile
    runner.write(tmp_path / 'input.json', snapshot)
    prompts = {}
    def capture(root, key, prompt, *args, **kwargs):
        prompts[key] = prompt
        return answer(root, key, prompt, *args, **kwargs)
    monkeypatch.setattr(runner, 'ask', capture)
    run_steps(tmp_path)
    for key in ('plan', 'rewrite-batch-Fun-8', 'select-batch-Fun-8'):
        assert ('FAMILY SPORTS PREFERENCE' in prompts[key]) is expected
    for cat in ('News', 'Science'):
        for stage in ('rewrite-batch', 'select-batch'):
            assert 'FAMILY SPORTS PREFERENCE' not in prompts[f'{stage}-{cat}-8']
