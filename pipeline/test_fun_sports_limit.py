"""At most one tennis and one swimming story; offline regression."""
import pytest

from pipeline.agent_shadow_batch import validate_fixed_order


def pool(topics):
    return [{'id':str(i), 'topic':t} for i,t in enumerate(topics)]


def test_final_order_rejects_two_tennis_but_allows_tennis_plus_swimming():
    rows=pool(['tennis','tennis','games','swimming','other'])
    assert validate_fixed_order({'order':['0','1','2','3','4']}, rows, 'Fun')
    assert not validate_fixed_order({'order':['0','2','3','1','4']}, rows, 'Fun')
    assert not validate_fixed_order({'order':['0','1','2','3','4']}, rows, 'News')


def test_python_keeps_best_ranked_sport_and_promotes_non_sports_without_ai():
    from pipeline.kidsnews_groups import limit_fun_sports_order
    rows=pool(['tennis','tennis','games','tennis','arts_books'])
    order, moved=limit_fun_sports_order(['0','1','2','3','4'], rows)
    assert order == ['0','2','4','1','3']
    assert moved == ['1','3']
    assert not validate_fixed_order({'order':order}, rows, 'Fun')


def test_all_non_sports_and_legacy_order_unchanged():
    from pipeline.kidsnews_groups import limit_fun_sports_order
    rows=pool(['games','animal_events','arts_books','other','music'])
    assert limit_fun_sports_order(['0','1','2','3','4'], rows)==(['0','1','2','3','4'], [])
    sports=pool(['tennis','swimming','games','other','music'])
    assert not validate_fixed_order({'order':['0','1','2','3','4']}, sports)


def test_insufficient_non_sports_never_silently_relaxes_cap():
    from pipeline.kidsnews_groups import limit_fun_sports_order
    with pytest.raises(ValueError, match='three eligible'):
        limit_fun_sports_order(['0','1','2','3','4'], pool(['tennis','tennis','tennis','tennis','games']))


def test_api_editor_caps_actual_winners_and_resumes_without_calls(tmp_path,monkeypatch):
    from pipeline import agent_shadow as runner
    from pipeline.kidsnews_api_editor import edit_groups
    from pipeline.test_kidsnews_groups import prepared
    from pipeline.test_kidsnews_python import Provider
    prepared(tmp_path,monkeypatch)
    path=tmp_path/'raw-batch-Fun-8.json'
    raw=runner.read(path)
    ids=[d['id'] for d in raw['result']['drafts']]
    topics=dict(zip(ids,['tennis','tennis','games','swimming','arts_books']))
    for row in raw['originals']:
        row['topic']=topics.get(row['id'],'other')
    runner.write(path,raw)
    # This is fixture setup before any answers are accepted, not a runtime edit.
    from pipeline.kidsnews_groups import pin
    pin(tmp_path,path)
    provider=Provider();identity={'type':'fake','model':'offline'}
    edit_groups(tmp_path,provider,identity)
    state=runner.read(tmp_path/'editor-state.json')['Fun']
    assert [a['candidate']['id'] for a in state['accepted']]==[ids[0],ids[2],ids[3]]
    assert state['sports_adjustment']['moved_to_reserves']==[ids[1]]
    before=len(provider.calls)
    edit_groups(tmp_path,provider,identity)
    assert len(provider.calls)==before


def test_new_group_request_has_hard_cap_but_news_science_do_not(tmp_path,monkeypatch):
    from pipeline import agent_shadow as runner
    from pipeline.test_kidsnews_groups import prepared
    prepared(tmp_path,monkeypatch)
    request=runner.read(tmp_path/'groups/Fun-request.json')
    assert request['fun_topic_limits']=={'tennis':1,'swimming':1}
    assert 'HARD LIMIT' in request['prompt']
    assert 'fun_topic_limits' not in runner.read(tmp_path/'groups/Science-request.json')


def test_swimming_has_own_limit_and_no_global_sports_cap():
    from pipeline.kidsnews_groups import limit_fun_sports_order
    rows=pool(['swimming','swimming','tennis','other_sports','games'])
    order,moved=limit_fun_sports_order(['0','1','2','3','4'],rows)
    assert order==['0','2','3','1','4'] and moved==['1']
    assert not validate_fixed_order({'order':order},rows,'Fun')


def test_disk_import_blocks_two_tennis_before_reading_fun_answers(tmp_path,monkeypatch):
    from pipeline import agent_shadow as runner
    from pipeline.kidsnews_groups import import_groups, GroupNeeded, pin
    from pipeline.test_kidsnews_groups import prepared, answers
    prepared(tmp_path,monkeypatch);answers(tmp_path)
    selection=runner.read(tmp_path/'groups/Fun-selection.json')
    path=tmp_path/'raw-batch-Fun-8.json';raw=runner.read(path)
    for b in raw['originals']:
        b['topic']='tennis' if b['id'] in selection['order'][:2] else 'games'
    runner.write(path,raw);pin(tmp_path,path)
    with pytest.raises(GroupNeeded, match='ONE tennis'):
        import_groups(tmp_path)
    assert runner.read(tmp_path/'editor-state.json')['Fun']['accepted']==[]


def test_failed_non_sports_winner_does_not_admit_second_tennis_reserve(tmp_path,monkeypatch):
    from pipeline import agent_shadow as runner, agent_shadow_finish
    from pipeline.kidsnews_groups import pin
    from pipeline.kidsnews_api_editor import edit_groups
    from pipeline.test_kidsnews_groups import prepared
    from pipeline.test_kidsnews_python import Provider
    prepared(tmp_path,monkeypatch)
    path=tmp_path/'raw-batch-Fun-8.json';raw=runner.read(path)
    ids=[d['id'] for d in raw['result']['drafts']]
    topics=dict(zip(ids,['tennis','tennis','games','swimming','arts_books']))
    for b in raw['originals']:b['topic']=topics.get(b['id'],'other')
    runner.write(path,raw);pin(tmp_path,path)
    original=agent_shadow_finish.finish
    called=[]
    def finish(root,cat,sid,*args,**kwargs):
        if cat=='Fun':
            called.append(sid)
            if sid==ids[2]:return {'status':'gone','reason':'unsafe'}
        return original(root,cat,sid,*args,**kwargs)
    monkeypatch.setattr(agent_shadow_finish,'finish',finish)
    edit_groups(tmp_path,Provider(),{'type':'fake'})
    state=runner.read(tmp_path/'editor-state.json')['Fun']
    assert [a['candidate']['id'] for a in state['accepted']]==[ids[0],ids[3],ids[4]]
    assert ids[1] not in called
    assert any(o['id']==ids[1] and o['status']=='not_selected_sports_limit' for o in state['outcomes'])
