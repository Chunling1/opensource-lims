import pytest
from sqlalchemy import text
from app.extensions import db
from app.models import Report
from app import list_paging, list_projection, list_query_prototype
pytest_plugins=('testkit.fixtures',)

@pytest.mark.parametrize('endpoint,view,presentation',[
 ('reports','query','report'),('samples','register','registration-sample')])
@pytest.mark.parametrize('failure',['select','hydrate'])
def test_prototype_failure_returns_complete_legacy_response(isolated_app,isolated_client,scenario_factory,monkeypatch,caplog,endpoint,view,presentation,failure):
 d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
 for i in range(4):db.session.add(Report(report_no='FALL-'+str(i),sample_no='S'+str(i),department=d.name,status='待合同评审',sample_reg_state='登记完成'))
 db.session.commit()
 from app.security import issue_token
 headers={'Authorization':'Bearer '+issue_token(u)};body=dict(view=view,presentation=presentation,serverPage=True,page=2,pageSize=2)
 if failure=='materialize':body.update(contains='FALL',searchField='all')
 baseline=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json=body).get_json()
 def broken(*a,**kw):raise RuntimeError('sensitive sentinel must not appear in logs')
 if failure=='select':monkeypatch.setattr(list_query_prototype,'select_ids',broken)
 elif failure=='hydrate':
  original=list_projection.list_reports
  def hydrate(q,*,page_ids=None):
   if page_ids is not None:return broken()
   return original(q)
  monkeypatch.setattr(list_projection,'list_reports',hydrate)
 else:
  from app import list_query_values
  monkeypatch.setattr(list_query_values,'materialize_fields',broken)
  isolated_app.config['LIST_QUERY_A2']=True
 isolated_app.config['LIST_QUERY_PROTOTYPE']=True
 actual=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json=body)
 assert actual.status_code==200 and actual.get_json()==baseline
 assert 'list query prototype fallback: RuntimeError' in caplog.text
 assert 'sensitive sentinel' not in caplog.text


def test_report_page_direct_call_falls_back(isolated_app,scenario_factory,monkeypatch):
 d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
 db.session.add(Report(report_no='DIRECT'));db.session.commit()
 isolated_app.config['LIST_QUERY_PROTOTYPE']=True
 monkeypatch.setattr(list_query_prototype,'joined_sources',lambda q:(_ for _ in ()).throw(RuntimeError('failure')))
 q,m=list_paging.report_page(Report.query,u,'query',{})
 assert m['total']==1 and [r.report_no for r in q.all()]==['DIRECT']


def test_explicit_order_survives_query_clone(isolated_app,scenario_factory):
 d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
 for i in (1,2,10):db.session.add(Report(report_no='R'+str(i),sample_no='S'+str(i)))
 db.session.commit();isolated_app.config['LIST_QUERY_PROTOTYPE']=True
 q,m=list_paging.report_page(Report.query,u,'query',{'sort':'sampleNo','direction':'desc'})
 assert not hasattr(q,'_list_page_ids')
 assert [r.sample_no for r in list_projection.list_reports(q.filter(Report.id>0),page_ids=m.page_ids)]==['S10','S2','S1']
 assert set(m)=={'total','page','pageSize'}


from test_list_query_prototype import prototype_mysql_app,mysql_server

@pytest.mark.parametrize('endpoint,view,presentation',[
 ('reports','query','report'),('samples','register','registration-sample')])
def test_a2_materialize_failure_mysql(prototype_mysql_app,monkeypatch,caplog,endpoint,view,presentation):
 from testkit.factories import ScenarioFactory
 # The legacy all-fields SQL exceeds SQLite parser depth; keep the exact
 # full-response assertion and execute both paths on the deployment dialect.
 with prototype_mysql_app.app_context():
  test_prototype_failure_returns_complete_legacy_response(prototype_mysql_app,prototype_mysql_app.test_client(),ScenarioFactory(),monkeypatch,caplog,endpoint,view,presentation,'materialize')
