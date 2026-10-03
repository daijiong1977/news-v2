import pytest


@pytest.mark.parametrize('title,summary', [
    ('Best Smart Cat Trackers of 2026: Fi Mini vs. Tractive', ''),
    ('31 Best STEM Toys for Kids (2026): Learning Made Fun', ''),
    ('Columbia Promo Codes: 15% Off', ''),
    ('Our headphones review', 'We may earn a commission from affiliate links.'),
    ('New products for families', 'Sponsored content: paid partnership.'),
])
def test_commercial_candidates_are_excluded(title, summary):
    from pipeline.agent_shadow_rank_contract import metadata_exclusion
    assert metadata_exclusion({'title': title, 'summary': summary}, 'Fun') == 'commercial_or_advertorial'


def test_commercial_guard_does_not_ban_news_about_advertising_or_genuine_fun():
    from pipeline.agent_shadow_candidate_quality import commercial_reason
    for title in ('Schools ban advertising to children', 'Sabalenka plays her best tennis',
                  'Robot hand plays a video game', 'New rules protect shoppers from fake reviews'):
        assert not commercial_reason({'title': title})


def test_time_for_kids_contaminated_extraction_is_rejected_not_counted():
    from pipeline.agent_shadow_candidate_quality import extraction_reason
    main='Children practice tennis together and learn to encourage their teammates during the match.'
    related='On June 19 the United States celebrates Juneteenth with festivals concerts and other gatherings around the country.'
    html=f'<div class="article-show__content-article"><p>{main}</p></div><div class="article-show__related-articles"><div class="c-article-preview__content"><p>{related}</p></div></div>'
    assert extraction_reason('https://www.timeforkids.com/g56/story/', html, main+'\n\n'+related) == 'related_articles_in_extracted_body'
    assert not extraction_reason('https://www.timeforkids.com/g56/story/', html, main)


def test_time_for_kids_fetch_marks_contamination_before_photo(monkeypatch):
    from pipeline import agent_shadow_source_first as source
    paragraph='On June 19 the United States celebrates Juneteenth with festivals concerts and other gatherings around the country.'
    html=f'<meta property="og:image" content="https://example.com/photo.jpg"><div class="article-show__content-article"><p>A child friendly story about animals in the park.</p></div><div class="article-show__related-articles"><p>{paragraph}</p></div>'
    monkeypatch.setattr(source, 'fetch_bytes', lambda *a: (html.encode(), 'https://www.timeforkids.com/g56/story/', 'utf-8'))
    result=source.fetch_original({'link':'https://www.timeforkids.com/g56/story/', 'title':'Story'})
    assert result['skip_reason'] == 'related_articles_in_extracted_body'


def test_pokemon_same_championship_removed_despite_different_model_event_keys():
    from pipeline.agent_shadow_candidate_quality import filter_ranked_overlap
    candidates={
        'a': {'title':'Pokémon Fans Unite', 'published':'2026-10-01'},
        'b': {'title':'Pokémon Turns 30', 'published':'2026-10-01'},
        'c': {'title':'New Pokémon Game Announced', 'published':'2026-10-01'},
        'd': {'title':'Interview With A Children’s Author', 'published':'2026-10-01'},
    }
    bodies={'a':{'body':'I attended the 2026 Pokémon World Championships in San Francisco.'},
            'b':{'body':'Pokémon celebrates its anniversary. Fans gathered for the 2026 Pokémon World Championships in San Francisco.'},
            'c':{'body':'A newly announced Pokémon game lets players explore a new island.'},
            'd':{'body':'An author explains how he creates funny characters.'}}
    rows=[{'id':sid,'event_key':sid} for sid in candidates]
    kept,audit=filter_ranked_overlap(rows,candidates,bodies)
    assert [r['id'] for r in kept] == ['a','c','d']
    assert audit == [{'id':'b','reason':'same_reported_event_overlap','kept_id':'a'}]


def test_event_overlap_keeps_different_years_and_different_competitions():
    from pipeline.agent_shadow_candidate_quality import filter_ranked_overlap
    candidates={sid:{'title':sid,'published':'2026-10-01'} for sid in ('a','b','c')}
    bodies={'a':{'body':'Fans attended the 2026 Pokémon World Championships.'},
            'b':{'body':'A history of the 2025 Pokémon World Championships.'},
            'c':{'body':'The 2026 swimming World Championships set new records.'}}
    kept,audit=filter_ranked_overlap([{'id':sid} for sid in candidates],candidates,bodies)
    assert len(kept)==3 and not audit


def test_overlap_uses_cached_publication_year_when_compact_metadata_omits_it():
    from pipeline.agent_shadow_candidate_quality import filter_ranked_overlap
    candidates={'a':{'title':'Pokémon Fans Unite'},'b':{'title':'Pokémon Turns 30'}}
    bodies={'a':{'published':'Wed, 30 Sep 2026 13:26:31 +0000',
                 'body':'In August, Adam attended the Pokémon World Championships in San Francisco.'},
            'b':{'published':'Wed, 30 Sep 2026 13:26:11 +0000',
                 'body':'Fans attended the 2026 Pokémon World Championships during anniversary celebrations.'}}
    kept,audit=filter_ranked_overlap([{'id':'a'},{'id':'b'}],candidates,bodies)
    assert [r['id'] for r in kept]==['a'] and audit[0]['kept_id']=='a'


def test_named_event_guard_does_not_drop_author_for_related_card_mention():
    from pipeline.agent_shadow_candidate_quality import filter_ranked_overlap
    candidates={'a':{'title':'Pokémon Fans Unite','published':'2026-10-01'},
                'b':{'title':'8 Questions for Aaron Blabey','summary':'A children’s author interview.','published':'2026-10-01'}}
    bodies={'a':{'body':'Fans attended the 2026 Pokémon World Championships.'},
            'b':{'body':'Aaron discusses his new book and funny drawings.\nRelated: fans attended the 2026 Pokémon World Championships.'}}
    kept,audit=filter_ranked_overlap([{'id':'a'},{'id':'b'}],candidates,bodies)
    assert len(kept)==2 and not audit


def test_rank_overlap_gate_keeps_next_reserve_without_another_llm_call(tmp_path, monkeypatch):
    from pipeline import agent_shadow as runner
    from pipeline.agent_shadow_shortlist import DeepSeekSourceEditor
    candidates=[{'id':sid,'category':'Fun','title':title,'summary':'A report about this event.', 'published':'2026-10-01'}
                for sid,title in [('a','Pokémon Fans Unite'),('b','Pokémon Turns 30'),('c','Author Interview')]]
    snapshot={'candidates':candidates,'date':'2026-10-02','history':{c:[] for c in runner.CATS},'shortlist_contract':'indices-v1'}
    policy=DeepSeekSourceEditor(tmp_path,snapshot,None,runner.boundary,False)
    policy.catalog={c:[] for c in runner.CATS}
    bodies={'a':{'body':'Fans attended the 2026 Pokémon World Championships.'},
            'b':{'body':'The anniversary report also covers the 2026 Pokémon World Championships.'},
            'c':{'body':'An author discusses his new book.'}}
    runner.write(tmp_path/'bodies.json',bodies)
    monkeypatch.setattr(policy,'originals',lambda *a,**kw:[{'id':c['id'],'article':bodies[c['id']]} for c in candidates])
    calls=[]
    def answer(root,key,prompt,material,validate,**kw):
        calls.append(key)
        value={'ranked':[{'id':i,'topic':'games','importance':2,'initial_risk':0,'history_status':'clear',
                        'history_confidence':.9,'event_key':str(i)} for i in range(1,4)]}
        return kw['normalize'](value)
    policy.ask=answer
    assert [r['id'] for r in policy._rank('Fun',8)] == ['a','c']
    assert len(calls)==1
    assert runner.read(tmp_path/'shortlist-Fun-8.json')['filtered'][-1]['kept_id']=='a'


def test_collection_does_not_count_ads_or_contaminated_body_or_fetch_their_photos(tmp_path, monkeypatch):
    from pipeline import agent_shadow_source_first as source
    from pipeline import agent_shadow as runner
    from pipeline.test_agent_shadow_source_first import sources
    selected=sources('Fun',1)
    entries=[{'title':'Best Smart Cat Trackers of 2026','summary':'Compare products.',
              'link':'https://example.com/trackers','published':'2026-10-02'},
             {'title':'Youth Olympics Preview','summary':'Young athletes gather.',
              'link':'https://www.timeforkids.com/g56/story/','published':'2026-10-02'}]
    monkeypatch.setattr(source,'fetch_source_entries',lambda *a,**kw:entries)
    fetched=[]
    def original(candidate):
        fetched.append(candidate['title'])
        return {**candidate,'body':'word '*300,'skip_reason':'related_articles_in_extracted_body'}
    monkeypatch.setattr(source,'fetch_original',original)
    monkeypatch.setattr(source,'safe_image',lambda *a,**kw:pytest.fail('Rejected candidates must not fetch images'))
    assert source.collect(tmp_path,{'Fun':selected},'2026-10-02')==[]
    assert fetched==['Youth Olympics Preview']
    results=runner.read(tmp_path/'source-collection.json')['sections']['Fun']['sources'][0]['results']
    assert [r['reason'] for r in results]==['commercial_or_advertorial','related_articles_in_extracted_body']
    assert not any(r.get('qualified') or r.get('photo_attempted') for r in results)
