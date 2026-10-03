from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_source_first import sources, fake_collection


def fixed(root):
    runner.write(root/'prepare-context.json',{'selection_policy':'twelve-five-three-v1'})


def test_news_six_per_source_eighteen_then_stop_resume_no_fetch(tmp_path,monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    calls=fake_collection(monkeypatch)
    fixed(tmp_path)
    rows=collect(tmp_path,{'News':sources('News',5)},'2026-10-01')
    assert len(rows)==18
    assert calls=={'News-0':6,'News-1':6,'News-2':6}
    assert collect(tmp_path,{},'2026-10-01')==rows
    assert sum(calls.values())==18


def test_news_short_source_goes_fourth_stops_exactly_eighteen(tmp_path,monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    calls=fake_collection(monkeypatch,bad=lambda c:c['source']=='News-0' and int(c['link'].rsplit('/',1)[1])>=4)
    fixed(tmp_path)
    rows=collect(tmp_path,{'News':sources('News',5)},'2026-10-01')
    assert len(rows)==18
    assert calls=={'News-0':12,'News-1':6,'News-2':6,'News-3':2}


def test_other_categories_unchanged_and_legacy_limits_frozen(tmp_path,monkeypatch):
    from pipeline.agent_shadow_source_first import collect
    calls=fake_collection(monkeypatch)
    fixed(tmp_path)
    rows=collect(tmp_path,{'Science':sources('Science',5),'Fun':sources('Fun',5)},'2026-10-01')
    assert len(rows)==24 and all(v==4 for v in calls.values())
    legacy=tmp_path/'legacy'; legacy.mkdir(); fixed(legacy)
    # Journal created by the previous collector retains its frozen4/12 policy.
    from dataclasses import asdict
    src=sources('News',5)
    runner.write(legacy/'source-collection.json',{'version':1,'date':'2026-10-01',
        'sections':{'News':{'sources':[{'source':asdict(s),'publisher':s.name,'results':[],
            'windows':[],'status':'pending'} for s in src],'complete':False}},
        'limits':{'per_source':12,'pass_target':4,'min_groups':0,'min_good':12,'max_unique_articles':60},
        'unique_attempts':0})
    assert len(collect(legacy,{},'2026-10-01'))==12
