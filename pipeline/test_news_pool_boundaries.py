from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_source_first import sources, fake_collection, full_fixture


def test_fun_never_enters_news_and_long_news_survives(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_editor import SourceFirstEditor
    snapshot, *_ = full_fixture(tmp_path, monkeypatch)
    bodies = runner.read(tmp_path/'bodies.json')
    ids = [c['id'] for c in snapshot['candidates'] if c['category']=='News']
    sid = ids[0]
    bodies[sid]['body'] = 'fact ' * 1800
    bodies[sid]['word_count'] = 1800
    bodies[sid].pop('evidence_sha256',None)
    runner.write(tmp_path/'bodies.json',bodies)
    editor = SourceFirstEditor(tmp_path,snapshot,None,None,False)
    editor.catalog = {'News':[{'id':c['id'],'importance':3,'initial_risk':0,
        'history_status':'clear','history_confidence':1,'topic':'community'} for c in snapshot['candidates']],
        'Science':[],'Fun':[]}
    rows = editor.originals('News',limit=None)
    assert sid in {c['id'] for c in rows}
    assert not any(next(c for c in snapshot['candidates'] if c['id']==r['id'])['category']=='Fun' for r in rows)


def test_pbs_hard_exclusions_do_not_fill_four_passes(tmp_path,monkeypatch):
    from pipeline import agent_shadow_source_first as sf
    fake_collection(monkeypatch)
    titles = ['Alleged gang rape','Failed execution of inmate','Suspected plot preparing terrorist acts',
              'Co-pilot attacked captain with axe','FBI releases policy report','Space station cooperation',
              'Judge halts border wall construction','How voting ballots are counted']
    monkeypatch.setattr(sf,'fetch_source_entries',lambda *a,**k:[
        {'title':t,'summary':t,'link':f'https://pbs.org/story/{i}','published':'2026-10-03'}
        for i,t in enumerate(titles)])
    rows = sf.collect(tmp_path,{'News':sources('News',1)},'2026-10-03')
    assert [r['title'] for r in rows] == titles[4:]


def test_two_thousand_source_collects_but_larger_rejected(tmp_path,monkeypatch):
    from pipeline import agent_shadow_source_first as sf
    fake_collection(monkeypatch)
    monkeypatch.setattr(sf,'fetch_source_entries',lambda *a,**k:[
        {'title':f'Current report {i}','link':f'https://pbs.org/{i}','published':'2026-10-03'} for i in range(2)])
    monkeypatch.setattr(sf,'fetch_original',lambda c:{**c,'body':'fact '*(2000 if c['link'].endswith('/0') else 2001),
        'og_image':'https://photo.example/image','evidence_url':c['link']})
    rows=sf.collect(tmp_path,{'News':sources('News',1)},'2026-10-03')
    assert len(rows)==1 and rows[0]['mechanical']['words']==2000
