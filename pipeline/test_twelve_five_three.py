"""Quantity goals relax variety, never event history or fixed membership."""
from copy import deepcopy

from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_source_first import sources, fake_collection


def test_twelve_target_stops_with_one_publisher_and_resume_keeps_budget(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    feeds = sources('Science', 5)
    for s in feeds:
        s.rss_url = 'https://sciencedaily.com/rss/' + s.name
    runner.write(tmp_path / 'prepare-context.json', {'selection_policy': 'twelve-five-three-v1'})
    calls = fake_collection(monkeypatch)
    result = collect(tmp_path, {'Science': feeds}, '2026-10-02')
    assert len(result) == 12 and len(calls) == 3
    state = runner.read(tmp_path / 'source-collection.json')
    assert state['limits']['min_good'] == 12 and state['limits']['min_groups'] == 0
    assert state['sections']['Science']['attempted_groups'] == 1
    assert state['sections']['Science']['shortfall'] == 0
    assert collect(tmp_path, {}, '2026-10-02') == result
    assert sum(calls.values()) == 12


def test_new_target_collects_twelfth_instead_of_stopping_at_ten(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    runner.write(tmp_path / 'prepare-context.json', {'selection_policy': 'twelve-five-three-v1'})
    # First three feeds provide 4+3+3 = ten, requiring the fourth feed.
    calls = fake_collection(monkeypatch, bad=lambda b: b['source'] in ('Fun-1', 'Fun-2')
                            and int(b['link'].rsplit('/', 1)[1]) >= 3)
    result = collect(tmp_path, {'Fun': sources('Fun')}, '2026-10-02')
    assert len(result) >= 12 and calls['Fun-3'] == 4 and not calls['Fun-4']


def test_five_goal_relaxes_variety_but_keeps_duplicate_events_out():
    from pipeline.agent_shadow_rank_contract import rank_prompt, normalize_rank
    from pipeline.agent_shadow_batch import batch_prompt
    from pipeline.test_shortlist_contract import row
    snapshot = {'selection_policy': 'twelve-five-three-v1'}
    assert 'FIVE to EIGHT' in rank_prompt(snapshot, 'Science')
    assert 'Repeated publishers and disciplines are allowed' in batch_prompt(snapshot, 'Science')
    value = {'ranked': [row(i, topic='biology', event_key='same-study' if i in (1, 2) else f'event-{i}')
                        for i in range(1, 7)]}
    # Find the real taxonomy label rather than inventing it.
    from pipeline.news_topics import TOPICS_BY_CATEGORY
    for r in value['ranked']:
        r['topic'] = next(iter(TOPICS_BY_CATEGORY['Science']))
    result = normalize_rank(value, {i: str(i) for i in range(1, 7)}, 'Science')
    assert len(result['catalog']['Science']) == 5
    assert [r['id'] for r in result['catalog']['Science']] == ['1', '3', '4', '5', '6']
    assert result['shortlist_audit'][0]['reason'] == 'same_event_in_shortlist'


def test_shortfall_expands_only_science_before_handoff_and_never_replays(tmp_path, monkeypatch):
    from pipeline.test_source_first_deepseek import fixture
    from pipeline.agent_shadow_shortlist import DeepSeekSourceEditor
    from pipeline import agent_shadow_source_first as collection
    snapshot, _, _, _, _ = fixture(tmp_path, monkeypatch)
    snapshot['selection_policy'] = 'twelve-five-three-v1'
    counts = {c: 0 for c in runner.CATS}
    expanded = []
    seed = deepcopy(next(b for b in snapshot['candidates'] if b['category'] == 'Science'))
    def rank(self, cat, target):
        counts[cat] += 1
        n = 2 if cat == 'Science' and not expanded else 5
        return [{'id': f'{cat}-{i}'} for i in range(n)]
    def collect(root, selected, today, *, expand):
        assert expand == 'Science'
        state = runner.read(root / 'source-collection.json')
        pending = next(s for s in state['sections'][expand]['sources'] if s['status'] == 'pending')
        pending['status'] = 'complete'
        runner.write(root / 'source-collection.json', state)
        expanded.append(expand)
        return snapshot['candidates'] + [{**seed, 'id': 'fresh-science'}]
    monkeypatch.setattr(DeepSeekSourceEditor, '_rank', rank)
    monkeypatch.setattr(collection, 'collect', collect)
    policy = DeepSeekSourceEditor(tmp_path, snapshot, None, runner.boundary, False)
    policy.plan()
    assert counts == {'News': 1, 'Science': 2, 'Fun': 1} and expanded == ['Science']
    restored = DeepSeekSourceEditor(tmp_path, snapshot, None, runner.boundary, False)
    restored.plan()
    assert counts == {'News': 1, 'Science': 2, 'Fun': 1}
    assert 'fresh-science' in {b['id'] for b in restored.snapshot['candidates']}


def test_one_science_publisher_and_topic_still_finishes_three(tmp_path, monkeypatch):
    from pipeline.test_source_first_deepseek import fixture
    from pipeline.agent_shadow_shortlist import build_drafts
    from pipeline.kidsnews_groups import prepare_groups, import_groups
    from pipeline.test_kidsnews_groups import answers
    snapshot, _, _, _, _ = fixture(tmp_path, monkeypatch)
    snapshot['selection_policy'] = 'twelve-five-three-v1'
    runner.write(tmp_path / 'input.json', snapshot)
    bodies = runner.read(tmp_path / 'bodies.json')
    for sid, body in bodies.items():
        if body['category'] == 'Science':
            body['_publisher_key'] = 'sciencedaily.com'
    runner.write(tmp_path / 'bodies.json', bodies)
    build_drafts(tmp_path)
    raw = runner.read(tmp_path / 'raw-batch-Science-8.json')
    topic = raw['originals'][0]['topic']
    for item in raw['originals']:
        item['topic'] = topic
    runner.write(tmp_path / 'raw-batch-Science-8.json', raw)
    prepare_groups(tmp_path)
    request = runner.read(tmp_path / 'groups/Science-request.json')
    assert 'all\nthree from one publisher and one discipline' in request['prompt']
    answers(tmp_path)
    assert import_groups(tmp_path)['counts'] == {c: 3 for c in runner.CATS}
    assert runner.advance(tmp_path)['counts'] == {'news': 3, 'science': 3, 'fun': 3}

