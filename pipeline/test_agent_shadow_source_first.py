"""New source-first profile regression tests. No network/models/production writes."""
from collections import Counter
from dataclasses import asdict
from copy import deepcopy
import random

import pytest
from PIL import Image

from pipeline import agent_shadow as runner
from pipeline.news_sources import NewsSource


def sources(category, count=5):
    return [NewsSource(i, f'{category}-{i}', f'https://p{i}.example/rss',
                      'full', 4, 0, i + 1, True, False) for i in range(count)]


def photo(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.frombytes('RGB', (320, 240), random.Random(7).randbytes(320 * 240 * 3)).save(path, 'WEBP', quality=80)
    return {'width': 320, 'height': 240}


def fake_collection(monkeypatch, bad=None, small=False):
    from pipeline import agent_shadow_source_first as sf
    calls = Counter()
    def feed(source, **kw):
        return [{'title': f'{source.name} story {i}', 'link': f'https://p{source.id}.example/{source.name}/{i}',
                 'summary': 'A current story', 'published': ''} for i in range(12)]
    def original(b):
        calls[b['source']] += 1
        art = {**b, 'body': 'fact ' * 400, 'word_count': 400, 'skip_reason': None,
               'og_image': 'https://photo.example/image', 'evidence_url': b['link']}
        if bad and bad(b):
            art['skip_reason'] = 'unavailable'
        return art
    monkeypatch.setattr(sf, 'fetch_source_entries', feed)
    monkeypatch.setattr(sf, 'fetch_original', original)
    monkeypatch.setattr(sf, 'safe_image', (lambda url, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b'x' * 19999), {'width': 320})[-1]) if small else photo)
    return calls


def test_source_stops_immediately_at_four_and_resumes_without_fetch(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    calls = fake_collection(monkeypatch)
    selected = {'News': sources('News')}
    result = collect(tmp_path, selected, '2026-10-01')
    assert len(result) == 12
    assert calls == {'News-0': 4, 'News-1': 4, 'News-2': 4}
    assert collect(tmp_path, selected, '2026-10-01') == result
    assert sum(calls.values()) == 12


def test_six_bad_suspend_feed_and_fourth_source_fills_ten(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    calls = fake_collection(monkeypatch, bad=lambda b: b['source'] == 'News-0')
    result = collect(tmp_path, {'News': sources('News')}, '2026-10-01')
    assert len(result) == 12 and calls['News-0'] == 6
    assert calls['News-3'] == 4 and not calls['News-4']
    state = runner.read(tmp_path / 'source-collection.json')
    assert state['sections']['News']['sources'][0]['status'] == 'suspended'


def test_source_windows_6_3_3_and_twelve_max(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    calls = fake_collection(monkeypatch, bad=lambda b: int(b['link'].rsplit('/', 1)[1]) not in (5, 8, 10, 11))
    result = collect(tmp_path, {'News': sources('News', 3)}, '2026-10-01')
    assert len(result) == 12 and list(calls.values()) == [12, 12, 12]
    rows = runner.read(tmp_path / 'source-collection.json')['sections']['News']['sources']
    assert rows[0]['windows'] == [6, 3, 3]


def test_small_compressed_photo_drops_whole_candidate_without_alternate(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    calls = fake_collection(monkeypatch, small=True)
    assert collect(tmp_path, {'Fun': sources('Fun', 3)}, '2026-10-01') == []
    assert list(calls.values()) == [6, 6, 6]
    records = runner.read(tmp_path / 'source-collection.json')['sections']['Fun']['sources'][0]['results']
    assert all(r['reason'] == 'image_below_20000' for r in records)


def test_science_groups_round_robin_preserve_primary_backup_and_due():
    from pipeline.agent_shadow_source_first import group_sources
    a = sources('Science', 5)
    a[0].rss_url = a[1].rss_url = 'https://sciencedaily.com/rss'
    a[4].is_backup = True
    a[3].next_pickup_at = '2026-10-02'
    assert [s.name for s in group_sources(a, '2026-10-01')] == ['Science-0', 'Science-2', 'Science-1', 'Science-4', 'Science-3']


def test_npr_written_story_not_audio_transcript_or_default_image():
    from pipeline.agent_shadow_source_first import extract_npr
    base = '<h1>Story</h1><div class="storytext"><p>Written report</p></div><meta property="og:image" content="https://media.npr.org/photo.jpg">'
    assert extract_npr('https://npr.org/2026/story', base)['cleaned_body'] == 'Written report'
    for cls in ('is-DACS-only', 'is-tiny-desk'):
        assert extract_npr('https://npr.org/2026/story', f'<body class="{cls}">{base}</body>')['skip_reason']
    assert extract_npr('https://npr.org/2026/story', base.replace('storytext', 'transcript'))['skip_reason']
    assert extract_npr('https://npr.org/2026/story', base.replace('photo.jpg', 'default-something.png'))['skip_reason']


def test_high_importance_must_be_drafted_or_explicitly_skipped():
    from pipeline.agent_shadow_source_first import validate_priority_batch
    pool = [{'id': str(i), 'importance': i, 'article': {'word_count': 400}} for i in range(8)]
    rows = [{'id': str(i), 'reason': 'Good', 'article': {}} for i in range(5)]
    assert validate_priority_batch({'drafts': rows}, pool, 'News')
    assert not validate_priority_batch({'drafts': rows, 'skipped': [{'id': '7', 'reason': 'Cannot responsibly explain this source'}]}, pool, 'News')


def combined_answer():
    from pipeline.test_agent_shadow_review_fixes import draft, extra
    from pipeline.news_rss_core import SAFETY_DIMS
    return {'corrected_article': draft(), 'details': extra(),
            'scores': {'0': {d: 0 for d in SAFETY_DIMS}}, 'event_clear': True,
            'facts_supported': False, 'notes': 'Attribution remains uncertain'}


def test_fact_false_warning_not_reject_and_detail_degrade_preserves_other_level():
    from pipeline.agent_shadow_finish import body_errors, sanitize_details
    value = combined_answer()
    assert not body_errors(value, 'News', 400)
    value['details']['0_middle']['questions'] = []
    slots, removed = sanitize_details(value['details'], value['corrected_article'])
    assert set(slots) == {'0_easy'} and removed
    value['scores']['0']['bias'] = 3
    assert body_errors(value, 'News', 400)
    value['scores']['0']['bias'] = 0
    value['event_clear'] = False
    assert body_errors(value, 'News', 400)


def test_detail_extra_fix_never_changes_passed_body(tmp_path, monkeypatch):
    from pipeline.agent_shadow_finish import finish
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    bad = combined_answer()
    bad['details']['0_middle']['questions'] = []
    tasks = []
    def ask(root, key, prompt, material, validate, **kw):
        tasks.append(key)
        if 'detail-fix' in key:
            return {'details': deepcopy(bad['details'])}
        return deepcopy(bad)
    art = {'word_count': 400, 'body': 'fact ' * 400, 'link': 'https://example.org/story'}
    result = finish(tmp_path, 'News', 'c1', art, bad['corrected_article'], [], [], ask)
    assert result['status'] == 'ready_degraded' and result['entry'] == bad['corrected_article']
    assert len(tasks) == 3 and 'detail-fix' in tasks[-1]
    before = list(tasks)
    assert finish(tmp_path, 'News', 'c1', art, bad['corrected_article'], [], [], ask) == result
    assert tasks == before


def full_fixture(root, monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    from pipeline.test_agent_shadow_review_fixes import draft
    from pipeline.news_topics import TOPICS_BY_CATEGORY
    calls = fake_collection(monkeypatch)
    selected = {c: sources(c) for c in runner.CATS}
    candidates = collect(root, selected, '2026-10-01')
    snapshot = {'date': '2026-10-01', 'candidates': candidates,
                'sources': {s.name: asdict(s) for rows in selected.values() for s in rows},
                'history': {c: [{'category': c, 'source_url': 'https://old.example/story', 'source_title': 'Old other event'}] for c in runner.CATS},
                'editor_mode': 'autonomous', 'test_profile': 'source-first-grok', 'active_categories': list(runner.CATS)}
    runner.write(root / 'input.json', snapshot)
    runner.write(root / 'metrics.json', {'steps': [], 'body_fetches': sum(calls.values())})
    tasks = []
    def ask(root, key, prompt, material, validate, **kw):
        tasks.append(key)
        if key == 'plan' or key.startswith('plan-source-refill'):
            value = {'catalog': {cat: [{'id': b['id'], 'topic': list(TOPICS_BY_CATEGORY[cat])[i % len(TOPICS_BY_CATEGORY[cat])],
                      'importance': 4 if i == 0 else 1, 'initial_risk': 0, 'history_status': 'clear', 'history_confidence': 1}
                      for i, b in enumerate(material['candidates']) if b['category'] == cat] for cat in runner.CATS}}
        elif key.startswith('rewrite-batch'):
            value = {'drafts': [{'id': b['id'], 'reason': 'Good current event', 'article': draft()} for b in material['candidates'][:5]]}
        elif key.startswith('select-batch'):
            value = {'order': [b['id'] for b in material['drafts']]}
        elif key.startswith('review-finish'):
            value = combined_answer()
        else:
            pytest.fail('Unexpected model call: ' + key)
        assert not validate(value), (key, validate(value))
        return value
    monkeypatch.setattr(runner, 'ask', ask)
    return snapshot, calls, tasks, ask


def test_source_first_full_nine_zip_warning_policy_no_refetch(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_review_fixes import run_steps
    from pipeline import publication_bundle as bundle
    snapshot, calls, tasks, _ = full_fixture(tmp_path, monkeypatch)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    assert 'publication_bundle build' in result['next'] and 'get approval' in result['next']
    assert len([k for k in tasks if k.startswith('review-finish')]) == 9
    assert len(set(k for k in tasks if k.startswith('rewrite-batch'))) == 3
    assert not any(k.startswith('details-') or k.startswith('review-details-') for k in tasks)
    assert sum(calls.values()) == 36
    publication = bundle.build(tmp_path, tmp_path / 'publication.zip')
    files, manifest = bundle.unpack((tmp_path / 'publication.zip').read_bytes())
    assert manifest['facts_policy'] == 'warning_only'
    assert len(result['warnings']) >= 9
    assert runner.advance(tmp_path)['already_done']
    assert sum(calls.values()) == 36
    # The same uncertainty is forbidden under an old/strict package contract.
    manifest.pop('facts_policy')
    with pytest.raises(ValueError, match='Unqualified'):
        bundle.validate_contents(files, manifest)


def test_detail_only_failures_extra_repair_and_zip_degrade_not_replace_article(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_review_fixes import run_steps
    from pipeline import publication_bundle as bundle
    _, calls, tasks, answer = full_fixture(tmp_path, monkeypatch)
    def bad(root, key, prompt, material, validate, **kw):
        if key.startswith('review-detail-fix'):
            return {'details': {'0_easy': combined_answer()['details']['0_easy'], '0_middle': {'questions': []}}}
        value = answer(root, key, prompt, material, validate, **kw)
        if key.startswith('review-finish'):
            value['details']['0_middle']['questions'] = []
        return value
    monkeypatch.setattr(runner, 'ask', bad)
    result = run_steps(tmp_path)
    assert result['counts']['news'] == 3
    body = runner.read(tmp_path / 'site/article_payloads/payload_2026-10-01-news-1/middle.json')
    assert body['detail_status'] == 'omitted' and body['questions'] == [] and body['summary'].strip()
    bundle.build(tmp_path, tmp_path / 'publication.zip')
    assert sum(calls.values()) == 36
    from pipeline.website_release import build_reader, check_reader
    from pipeline.test_source_first_reader import template
    shell = tmp_path / 'shell'
    shell.mkdir()
    (shell / 'index.html').write_text('<script src="article.jsx"></script>')
    (shell / 'article.jsx').write_text(template())
    reader = build_reader((tmp_path / 'publication.zip').read_bytes(), shell, 'a' * 40)
    public = check_reader(reader['zip'], reader['manifest'])
    assert reader['manifest']['template_adapter'] == 'source-first-detail-availability-v2'
    assert b"detail.detail_status !== 'omitted' && tab === 'quiz'" in public['article.jsx']
    assert not any(n.startswith('finished-articles/') for n in public)


def test_source_first_refill_only_fun_preserves_news_requests_and_cached_photos(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_review_fixes import run_steps
    _, calls, tasks, answer = full_fixture(tmp_path, monkeypatch)
    def reject(root, key, prompt, material, validate, **kw):
        value = answer(root, key, prompt, material, validate, **kw)
        if key.startswith('review-finish-Fun-'):
            source_name = runner.read(root / 'bodies.json')[key.split('Fun-', 1)[1]]['source']
            if source_name != 'Fun-3':
                value['event_clear'] = False
        if key.startswith('review-finish-fix-Fun-') and material['previous']['event_clear'] is False:
            value['event_clear'] = False
        return value
    monkeypatch.setattr(runner, 'ask', reject)
    result = run_steps(tmp_path)
    assert result['counts']['fun'] == 3
    assert sum(v for k, v in calls.items() if k.startswith('News')) == 12
    assert sum(v for k, v in calls.items() if k.startswith('Science')) == 12
    assert calls['Fun-3'] == 4
    assert len(set(k for k in tasks if k.startswith('rewrite-batch-News'))) == 1
    assert len([k for k in tasks if k.startswith('review-finish-News')]) == 3


def test_incremental_plan_exit_two_reuses_checkpoint_not_next_feed(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_editor import SourceFirstEditor
    from pipeline.ai_providers import AgentNeeded
    snapshot, calls, _, answer = full_fixture(tmp_path, monkeypatch)
    runner.write(tmp_path / 'editor-state.json', {c: {'accepted': []} for c in runner.CATS})
    policy = SourceFirstEditor(tmp_path, snapshot, answer, runner.boundary, False)
    policy.plan()
    runner.write(tmp_path / 'batch-Fun-8.json', {'pool': [], 'drafts': [], 'considered': [b['id'] for b in policy.catalog['Fun']]})
    def handoff(*args, **kw):
        raise AgentNeeded('test', tmp_path / 'request.json', tmp_path / 'answer.json', [])
    policy.ask = handoff
    with pytest.raises(AgentNeeded):
        policy.extend('Fun', 8, {'accepted': []})
    before = deepcopy(calls)
    policy.ask = answer
    assert policy.extend('Fun', 8, {'accepted': []}) == 16
    assert calls == before and calls['Fun-3'] == 4 and not calls['Fun-4']
    assert runner.read(tmp_path / 'pending-source-plan-Fun.json')['applied']


def test_short_feed_and_interrupt_never_repeat_reserved_article(tmp_path, monkeypatch):
    from pipeline import agent_shadow_source_first as sf
    calls = fake_collection(monkeypatch)
    original_feed = sf.fetch_source_entries
    monkeypatch.setattr(sf, 'fetch_source_entries', lambda *a, **kw: original_feed(*a, **kw)[:2])
    sf.collect(tmp_path, {'News': sources('News', 3)}, '2026-10-01')
    assert sum(calls.values()) == 6
    state = runner.read(tmp_path / 'source-collection.json')
    record = state['sections']['News']['sources'][0]['results'][0]
    record.update(status='attempting', qualified=False)
    state['sections']['News']['sources'][0]['status'] = 'pending'
    state['sections']['News']['complete'] = False
    runner.write(tmp_path / 'source-collection.json', state)
    sf.collect(tmp_path, {}, '2026-10-01')
    assert sum(calls.values()) == 6
    assert runner.read(tmp_path / 'source-collection.json')['sections']['News']['sources'][0]['results'][0]['reason'] == 'interrupted_attempt_not_refunded'


def test_rerouted_short_original_reuses_cache_but_obeys_final_category_band(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_editor import SourceFirstEditor
    snapshot, calls, _, answer = full_fixture(tmp_path, monkeypatch)
    policy = SourceFirstEditor(tmp_path, snapshot, answer, runner.boundary, False)
    policy.plan()
    sid = policy.catalog['Science'][0]['id']
    bodies = runner.read(tmp_path / 'bodies.json')
    bodies[sid].update(body='fact ' * 250, word_count=250)
    runner.write(tmp_path / 'bodies.json', bodies)
    assert sid not in {b['id'] for b in policy.originals('Science')}
    policy.catalog['Fun'].insert(0, {**policy.catalog['Science'][0], 'topic': 'animal_events'})
    assert sid in {b['id'] for b in policy.originals('Fun')}
    assert sum(calls.values()) == 36


@pytest.mark.parametrize('change', [lambda v: v.update(scores='bad'), lambda v: v['corrected_article'].update(easy_en='bad'), lambda v: v.update(facts_supported=0)])
def test_malformed_combined_fields_are_bounded_rejections_not_exceptions(change):
    from pipeline.agent_shadow_finish import body_errors
    value = combined_answer()
    change(value)
    assert body_errors(value, 'News', 400)


def test_body_fix_exhausted_gone_and_optional_cleanup_needs_no_ai_retry(tmp_path):
    from pipeline.agent_shadow_finish import finish
    art = {'word_count': 400, 'body': 'fact ' * 400, 'link': 'https://example.org/story'}
    tasks = []
    def bad(root, key, prompt, material, validate, **kw):
        tasks.append(key)
        value = combined_answer()
        value['corrected_article']['middle_en']['body'] = 'fact ' * 254
        return value
    result = finish(tmp_path, 'News', 'bad', art, {}, [], [], bad)
    assert result['status'] == 'gone' and len(tasks) == 2
    tasks.clear()
    def optional(root, key, prompt, material, validate, **kw):
        tasks.append(key)
        value = combined_answer()
        value['details']['0_easy']['keywords'] = [{'term': 'notinbody', 'explanation': 'Wrong'}]
        value['details']['0_middle']['perspectives'] = [None]
        return value
    result = finish(tmp_path, 'News', 'optional', art, {}, [], [], optional)
    assert result['status'] == 'ready_full' and result['removed'] and len(tasks) == 1


def test_quote_mismatch_is_ready_warning_without_extra_repair(tmp_path):
    from pipeline.agent_shadow_finish import finish
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    value = combined_answer()
    value['corrected_article']['easy_en']['body'] += ' He said "a sentence never in the source".'
    calls = []
    def answer(*args, **kwargs):
        calls.append(args[1])
        return deepcopy(value)
    art = {'word_count': 400, 'body': 'fact ' * 400, 'link': 'https://example.org/story'}
    result = finish(tmp_path, 'News', 'quote', art, {}, [], [], answer)
    assert result['status'] == 'ready_full' and len(calls) == 1
    assert any('Unsupported quoted sentence' in w for w in result['warnings'])
