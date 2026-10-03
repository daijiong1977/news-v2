"""No real credentials/network/database writes in these regressions."""
from copy import deepcopy
import json

import pytest
import requests
from pipeline.publication_database import TABLES, prepare, commit, rollback
from pipeline.publication_rest import RestClient
from pipeline.test_publication_database import fixture, Client


class Memory(RestClient):
    def __init__(self, scope):
        self.data=Client().snapshot(scope)['rows'];self.calls=[];self.lose=False
    def rows(self,table,filters):
        value=filters['id']
        return [deepcopy(r) for r in self.data[table] if 'eq.'+str(r['id'])==value]
    def snapshot(self,scope):return {'rows':deepcopy(self.data),'columns':{}}
    def verify_archive(self,artifact):pass
    def mutate(self,table,old,new):
        self.calls.append((table,old,new))
        rid=(new or old)['id']
        self.data[table]=[r for r in self.data[table] if r['id']!=rid]
        if new is not None:
            row=deepcopy(new)
            if table=='redesign_search_index':row['doc_tsv']='server derived'
            self.data[table].append(row)
        if self.lose:self.lose=False;raise requests.ReadTimeout('lost response')


def setup(tmp_path,monkeypatch):
    from pipeline.publication_database import load_artifact
    artifact,_,_=fixture(tmp_path,monkeypatch)
    client=Memory(load_artifact(artifact)[0]);state=tmp_path/'private-state'
    return artifact,client,state


def test_rest_apply_resume_and_exact_business_rollback(tmp_path,monkeypatch):
    artifact,client,state=setup(tmp_path,monkeypatch);original=deepcopy(client.data)
    prepare(artifact,state,client)
    assert (state/'apply.sql').exists() and (state/'rollback.sql').exists() and not client.calls
    commit(artifact,state,client);client.verify_database(state)
    count=len(client.calls);commit(artifact,state,client)
    assert len(client.calls)==count
    rollback(state,client)
    assert client.data==original
    count=len(client.calls);rollback(state,client);assert len(client.calls)==count


def test_rest_response_lost_readback_resumes_without_duplicate_write(tmp_path,monkeypatch):
    artifact,client,state=setup(tmp_path,monkeypatch)
    client.lose=True
    with pytest.raises(requests.ReadTimeout):commit(artifact,state,client)
    first=client.calls[0]
    commit(artifact,state,client)
    assert client.calls.count(first)==1
    client.verify_database(state)


def test_rest_sent_but_not_written_stops_uncertain_and_can_rollback(tmp_path,monkeypatch):
    artifact,client,state=setup(tmp_path,monkeypatch);original=deepcopy(client.data)
    def fail(table,old,new):client.calls.append((table,old,new));raise requests.ReadTimeout()
    client.mutate=fail
    with pytest.raises(requests.ReadTimeout):commit(artifact,state,client)
    with pytest.raises(ValueError,match='uncertain'):commit(artifact,state,client)
    assert len(client.calls)==1
    rollback(state,client);assert client.data==original


def test_rest_foreign_writer_blocks_all_mutations_and_rollback(tmp_path,monkeypatch):
    artifact,client,state=setup(tmp_path,monkeypatch)
    prepare(artifact,state,client)
    client.data['redesign_source_configs'][0]['cadence_days']=99
    with pytest.raises(ValueError,match='Changed'):commit(artifact,state,client)
    assert client.calls==[]


def test_rest_guards_project_headers_and_conflicting_insert(monkeypatch):
    from pipeline.publication_database import PROJECT
    with pytest.raises(ValueError,match='project'):RestClient('https://wrong.example','key')
    client=RestClient(key='private-test-value');calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs));response=requests.Response();response.status_code=201;return response
    monkeypatch.setattr(requests,'post',post)
    client.mutate('redesign_stories',None,{'id':'abc','doc_tsv':'omit'})
    assert calls[0][0]==f'https://{PROJECT}.supabase.co/rest/v1/redesign_stories'
    options=calls[0][1]
    assert options['headers']['apikey']=='private-test-value'
    assert 'ignore-duplicates' in options['headers']['Prefer'] and 'doc_tsv' not in options['json']


def test_default_database_transport_reuses_service_role_not_db_password(monkeypatch):
    from pipeline.kidsnews_python import database_client
    monkeypatch.setenv('SUPABASE_SERVICE_KEY','private-test-value')
    monkeypatch.delenv('KIDSNEWS_DATABASE_URL',raising=False)
    assert isinstance(database_client({}),RestClient)
    with pytest.raises(ValueError,match='transport'):database_client({'database_transport':'invalid'})
