import pytest
from app.extensions import db
from app.models import Report
from app.security import issue_token
pytest_plugins=('testkit.fixtures',)

@pytest.fixture()
def voided_client(isolated_client,scenario_factory):
 d=scenario_factory.department(name='VoidScope');project,steps=scenario_factory.project(d)
 u=scenario_factory.user(d,role_key='admin',account='admin',project_steps=steps)
 scenario_factory.grant_action(u,'report.archive.pass')
 for number,voided in [('LIVE',False),('VOID',True)]:
  db.session.add(Report(report_no=number,sample_no=number,status='待合同评审',sample_reg_state='登记完成',department=d.name,project=project.name,voided=voided,detail={'rawSample':{'schemeCode':project.code,'schemeName':project.name}}))
 db.session.commit()
 headers={'Authorization':'Bearer '+issue_token(u)}
 def query(endpoint,view,**extra):
  response=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json=dict(view=view,presentation='registration-sample' if endpoint=='samples' else 'report',serverPage=True,page=1,pageSize=200,**extra))
  assert response.status_code==200
  data=response.get_json();assert data['code']==0,data
  return data['data']
 return query

def test_register_include_voided_restores_visibility(voided_client):
 data=voided_client('samples','register',includeVoided=True)
 assert {r['reportNo'] for r in data['rows']}=={'LIVE','VOID'}
 assert data['total']==2
 assert voided_client('samples','register')['total']==1

def test_archive_voided_is_readonly_recall(voided_client):
 data=voided_client('reports','archive')
 assert {r['reportNo'] for r in data['rows']}=={'LIVE','VOID'}
 assert data['total']==2
 row=next(r for r in data['rows'] if r['reportNo']=='VOID')
 assert row['rowProjection']=='recall'
 assert not row['allowedActions']

def test_contract_review_and_pending_never_include_voided(voided_client):
 for endpoint,view in [('reports','contract_review'),('samples','register'),('reports','archive')]:
  data=voided_client(endpoint,view,includeVoided=True,rowProjection='active')
  assert all(not r['voided'] for r in data['rows'])
 data=voided_client('reports','contract_review',includeVoided=True)
 assert {r['reportNo'] for r in data['rows']}=={'LIVE'}
 assert data['total']==1
