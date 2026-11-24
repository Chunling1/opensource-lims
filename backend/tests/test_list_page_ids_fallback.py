"""HTTP fault injection for the default ID-first path (network-free fixtures)."""
import logging
import pytest
from app.extensions import db
from app.models import Report,Entrust
from app.security import issue_token
pytest_plugins=('testkit.fixtures',)

@pytest.mark.parametrize('endpoint',['reports','samples','entrust'])
@pytest.mark.parametrize('direction',['asc','desc'])
def test_select_ids_failure_rolls_back_and_returns_exact_legacy_response(isolated_app,isolated_client,scenario_factory,monkeypatch,caplog,endpoint,direction):
    from app import list_query_prototype
    d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
    for i in (1,2,10,20):
        db.session.add(Report(report_no='QA-'+str(i),sample_no='S'+str(i),department=d.name,status='检测录入中',sample_status='已领取',detail={'dataEntryStarted':True}))
        db.session.add(Entrust(entrust_no='WT-'+str(i),department=d.name,status='委托完成',info={}))
    db.session.commit();headers={'Authorization':'Bearer '+issue_token(u)}
    body=dict(serverPage=True,view='flow_query' if endpoint=='samples' else 'query',page=2,pageSize=2,sort='code',direction=direction)
    isolated_app.config.update(LIST_PAGE_IDS=False,LIST_QUERY_A2=True,LIST_QUERY_PROTOTYPE=False)
    expected=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json=body).get_json()
    isolated_app.config['LIST_PAGE_IDS']=True
    calls=[];original_rollback=db.session.rollback
    def rolled_back():calls.append('rollback');return original_rollback()
    monkeypatch.setattr(db.session,'rollback',rolled_back)
    def fail(*args,**kwargs):
        db.session.add(Report(report_no='UNCOMMITTED-FAULT'))
        db.session.flush()
        raise RuntimeError('private SQL and client text must never be logged')
    monkeypatch.setattr(list_query_prototype,'select_ids',fail)
    with caplog.at_level(logging.WARNING):
        response=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json=body)
    assert response.status_code==200
    assert response.get_json()==expected
    assert calls and Report.query.filter_by(report_no='UNCOMMITTED-FAULT').count()==0
    logs=[r.getMessage() for r in caplog.records if 'list page ids fallback:' in r.getMessage()]
    assert logs==['list page ids fallback: RuntimeError']
    assert 'private SQL' not in caplog.text


from test_list_query_prototype import prototype_mysql_app,mysql_server

@pytest.mark.parametrize('endpoint',['reports','samples','entrust'])
def test_a2_hydration_failure_retries_true_legacy_without_id_page(prototype_mysql_app,monkeypatch,caplog,endpoint):
    from testkit.factories import ScenarioFactory
    from app import list_projection
    with prototype_mysql_app.app_context():
        f=ScenarioFactory();d=f.department();u=f.user(d,role_key='admin',account='admin')
        db.session.add(Report(report_no='QA-FALLBACK',sample_no='S1',department=d.name,status='检测录入中',sample_status='已领取',detail={'rawSample':{'sampleName':'needle'}}))
        db.session.add(Entrust(entrust_no='WT-FALLBACK',department=d.name,info={'remark':'needle'}));db.session.commit()
        headers={'Authorization':'Bearer '+issue_token(u)};client=prototype_mysql_app.test_client()
        body=dict(view='flow_query' if endpoint=='samples' else 'query',presentation='commission' if endpoint=='entrust' else 'report',serverPage=True,page=1,pageSize=10,searchField='all',contains='needle')
        prototype_mysql_app.config.update(LIST_PAGE_IDS=False,LIST_QUERY_A2=False,LIST_QUERY_PROTOTYPE=False)
        old=client.post('/api/'+endpoint+'/query',headers=headers,json=body).get_json()
        prototype_mysql_app.config.update(LIST_PAGE_IDS=True,LIST_QUERY_A2=True)
        name='list_entrusts' if endpoint=='entrust' else 'list_reports';original=getattr(list_projection,name)
        def hydrate(query,*,page_ids=None):
            if page_ids is not None:raise RuntimeError('never repeat the broken ID hydration')
            return original(query)
        monkeypatch.setattr(list_projection,name,hydrate)
        response=client.post('/api/'+endpoint+'/query',headers=headers,json=body)
        assert response.status_code==200 and response.get_json()==old
        assert 'list query prototype fallback: RuntimeError' in caplog.text
        assert 'never repeat' not in caplog.text
