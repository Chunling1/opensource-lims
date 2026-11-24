import pytest
from app.extensions import db
from app.models import Report
from app.security import issue_token
pytest_plugins=('testkit.fixtures',)

CASES=[('samples','register','registration-sample'),('samples','inbound','inbound'),('samples','outbound','outbound'),
 ('reports','contract_review','registration-sample'),('reports','data_entry','entry'),('reports','data_change','entry'),
 ('reports','review','report'),('reports','approval','report'),('reports','print','report'),('reports','archive','report'),('reports','release','report')]

@pytest.mark.parametrize('endpoint,view,presentation',CASES)
def test_handling_active_all_global_status_and_search(isolated_client,scenario_factory,endpoint,view,presentation):
 d=scenario_factory.department(name='StatusScope');project,steps=scenario_factory.project(d)
 u=scenario_factory.user(d,role_key='admin',account='admin',project_steps=steps)
 for action in ['report.report_check.undo','report.review.undo','report.approval.undo','sample.return_stock','report.archive.pass']:
  scenario_factory.grant_action(u,action)
 states=[('待合同评审','待入库',''),('待样品入库','待入库',''),('待样品领取','已入库',''),('检测录入中','已领取',''),('待审核','已领取',''),('待批准','已领取',''),('待打印','已领取',''),('待发放','已领取',''),('待发放','已领取','归档完成'),('已发放','已领取','归档完成'),('退回待重传','已领取',''),('检测更改中','已领取','')]
 for state_idx,(status,sample,archive) in enumerate(states):
  for i in range(12):
   db.session.add(Report(report_no=f'ST-{state_idx:02}-{i:02}',sample_no=f'S-{state_idx:02}-{i:02}',status=status,sample_status=sample,archive_state=archive,department=d.name,project=project.name,sample_reg_state='登记完成',detail={'rawSample':{'schemeCode':project.code,'schemeName':project.name},'dataEntryStarted':False}))
 db.session.add(Report(report_no='VOID',status='待合同评审',voided=True,department=d.name,project=project.name))
 db.session.commit();h={'Authorization':'Bearer '+issue_token(u)}
 base=dict(view=view,presentation=presentation,serverPage=True,page=1,pageSize=200,sort='reportNo',direction='asc')
 def request(**extra):
  payload=isolated_client.post('/api/'+endpoint+'/query',headers=h,json={**base,**extra}).get_json()
  assert payload['code']==0,payload
  return payload['data']
 before=isolated_client.post('/api/reports/query',headers=h,json={'view':'dashboard'}).get_json()
 allrows=request()['rows'];assert allrows
 expected=[x for x in allrows if x['rowProjection']=='active']
 if view=='register':expected=[x for x in allrows if x['status']=='待合同评审']
 if view=='inbound':expected=[x for x in allrows if x['status']=='待样品入库']
 active=request(rowProjection='active',pageSize=10)
 assert active['total']==len(expected)
 assert [x['reportNo'] for x in active['rows']]==[x['reportNo'] for x in expected[:10]]
 assert request(rowProjection='')['total']==len(allrows)
 # Select an item beyond the first page. Status must be applied before LIMIT,
 # and the selected identifier must remain discoverable together with status.
 first_labels={x['dataStatus'] for x in allrows[:10]}
 offpage=[x for x in allrows[10:] if x['dataStatus'] not in first_labels]
 if len({x['dataStatus'] for x in allrows})>1:
  assert offpage, 'Fixture must contain a status absent from page one'
 target=(offpage or allrows[12:])[0];label=target['dataStatus']
 if offpage:assert label not in first_labels
 matched=[x for x in allrows if x['dataStatus']==label]
 filtered=request(status=label,pageSize=10)
 assert filtered['total']==len(matched)
 exact=request(status=label,contains=target['reportNo'],searchField='reportNo')
 assert [x['reportNo'] for x in exact['rows']]==[target['reportNo']]
 assert all(x['reportNo']!='VOID' for x in active['rows'])
 if view=='archive':assert next(x for x in allrows if x['reportNo']=='VOID')['rowProjection']=='recall'
 else:assert all(x['reportNo']!='VOID' for x in allrows)
 assert isolated_client.post('/api/reports/query',headers=h,json={'view':'dashboard'}).get_json()==before
