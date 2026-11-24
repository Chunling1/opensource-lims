import pytest
from app.extensions import db
from app.models import Entrust,Report,OperationAudit
from app import list_paging as paging,list_query_prototype as proto,list_projection as projection,list_query_values as values
from test_list_query_prototype import prototype_mysql_app,mysql_server
pytest_plugins=('testkit.fixtures',)

@pytest.mark.parametrize('a,a2,body,expected',[
 (False,False,{'contains':'yp'},'legacy'),(False,True,{'contains':'yp'},'a2'),
 (False,True,{'contains':'  '},'legacy'),(False,True,{'contains':'yp','searchField':'reportNo'},'legacy'),
 (True,True,{},'a'),(True,True,{'keyword':'yp','searchField':'all'},'a2'),
 (True,False,{'contains':'yp'},'a'),(False,True,{'code':'yp'},'legacy'),
 (True,True,{'contains':'yp','code':'id'},'a'),
 (True,True,{'contains':'yp','searchField':'reportNo'},'legacy')])
def test_request_only_routing(isolated_app,a,a2,body,expected):
 isolated_app.config.update(LIST_QUERY_PROTOTYPE=a,LIST_QUERY_A2=a2)
 with isolated_app.app_context():assert paging.query_path(body)==expected

@pytest.mark.parametrize('route',['a','a2'])
@pytest.mark.parametrize('target',['reports','samples','entrust'])
@pytest.mark.parametrize('failure',['select','hydrate','materialize'])
def test_each_path_falls_back(prototype_mysql_app,monkeypatch,caplog,route,target,failure):
 if route=='a' and failure=='materialize':return
 from testkit.factories import ScenarioFactory
 from app.security import issue_token
 with prototype_mysql_app.app_context():
  f=ScenarioFactory();d=f.department();u=f.user(d,role_key='admin',account='admin')
  db.session.add(Entrust(entrust_no='YP-E',info={'remark':'yp'}));db.session.add(Report(report_no='YP-R'));db.session.commit()
  headers={'Authorization':'Bearer '+issue_token(u)};body={'view':'register' if target=='samples' else 'query','presentation':{'reports':'report','samples':'registration-sample','entrust':'commission'}[target],'serverPage':True,'contains':'yp','searchField':'all'}
  c=prototype_mysql_app.test_client();prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=False,LIST_QUERY_A2=False)
  old=c.post('/api/'+target+'/query',headers=headers,json=body).get_json()
  def broken(*a,**kw):raise RuntimeError('private test marker')
  if failure=='select':monkeypatch.setattr(proto,'select_ids',broken)
  elif failure=='materialize':monkeypatch.setattr(values,'materialize_fields',broken)
  else:
   name='list_entrusts' if target=='entrust' else 'list_reports';original=getattr(projection,name)
   def hydrate(q,*,page_ids=None):
    if page_ids is not None:broken()
    return original(q)
   monkeypatch.setattr(projection,name,hydrate)
  prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=route=='a',LIST_QUERY_A2=route=='a2')
  new=c.post('/api/'+target+'/query',headers=headers,json=body)
  assert new.status_code==200 and new.get_json()==old
  assert 'list query prototype fallback: RuntimeError' in caplog.text
  assert 'private test marker' not in caplog.text

def test_entrust_a2_fields_and_order(prototype_mysql_app,caplog):
 with prototype_mysql_app.app_context():
  for i in (2,10,1):db.session.add(Entrust(entrust_no='E'+str(i),info={'entrustDate':'2026年1月2日','clientAddress':'yp','handler':'owner'}))
  db.session.commit()
  for body in ({'contains':'yp','searchField':'all'},{'contains':'yp','searchField':'all','adapter':'platform'},{'sort':'entrustNo','pageSize':2,'page':2},{'dateField':'commissionDate','from':'2026-01-01'}):
   results=[]
   for a,a2 in ((False,False),(True,False),(False,True)):
    prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=a,LIST_QUERY_A2=a2)
    rows,meta=paging.load_entrust_page(Entrust.query,body)
    results.append((meta,[(r.id,r.entrust_no,r.info) for r in rows]))
   assert results[0]==results[1]==results[2]
  assert 'list query prototype fallback:' not in caplog.text

def test_audit_summary_excludes_non_candidates(prototype_mysql_app):
 from sqlalchemy import select
 with prototype_mysql_app.app_context():
  db.session.add_all([Report(report_no='KEEP',entrust_no='E'),Report(report_no='OTHER',entrust_no='X')])
  for kind,identity in [('report','KEEP'),('report','OTHER'),('entrust','E'),('entrust','X')]:
   db.session.add(OperationAudit(object_type=kind,object_id=identity,action='sample.inbound.confirm',success=True))
  db.session.commit()
  q,a,c,edited=proto.joined_sources(Report.query.filter(Report.report_no=='KEEP'))
  assert q.with_entities(Report.report_no,a('report',Report.report_no,['sample.inbound.confirm','sample.mobile.inbound.confirm'],'id')).count()==1
  sql=str(q.statement.compile(db.engine,compile_kwargs={'literal_binds':True}))
  assert 'list_candidate_audit_keys' in sql and 'list_candidates' in sql and "'KEEP'" in sql

  from sqlalchemy.sql import visitors
  from sqlalchemy.sql.selectable import CTE
  aggregate=next(node for node in visitors.iterate(q.statement) if isinstance(node,CTE) and node.name=='list_audit_summary')
  identities=set(db.session.execute(select(aggregate.c.kind,aggregate.c.identity)).all())
  assert identities=={('report','KEEP'),('entrust','E')}

@pytest.mark.parametrize('view',['data_change', 'review', 'approval', 'print', 'release'])
def test_active_routing_keeps_all_search_on_a2(isolated_app,view):
 isolated_app.config.update(LIST_QUERY_PROTOTYPE=True,LIST_QUERY_A2=True)
 with isolated_app.app_context():
  body={'view':view,'rowProjection':'active'}
  assert paging.query_path(body)=='legacy'
  assert paging.query_path(dict(body,contains='yp',searchField='all'))=='a2'
