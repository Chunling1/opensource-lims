"""Correction users' pending sets reuse the ordinary handling view, not all query rows."""
from copy import deepcopy
import pytest
from app.extensions import db
from app.models import Report
from app.security import issue_token
pytest_plugins=('testkit.fixtures',)

@pytest.fixture
def pending_scenario(isolated_app,scenario_factory):
    f=scenario_factory;d=f.department(name='SCOPE');p,steps=f.project(d);blocked,_=f.project(d,authorize_department=False)
    permissions=['testing.data_entry.view','testing.data_change.view','report.query.view']
    normal=f.user(d,account='operator',permissions=permissions,project_steps=steps)
    corrector=f.user(d,account='qa-admin2',role_key='admin',permissions=permissions,project_steps=steps)
    for suffix,status,sample,project,voided in [
        ('2','检测录入中','已领取',p,False),('10','检测录入中','已领取',p,False),
        ('20','检测录入中','已入库',p,False),('30','待审核','已领取',p,False),
        ('40','待打印','已领取',p,False),('50','退回待重传','已领取',p,False),
        ('60','检测更改中','已领取',p,False),('70','检测录入中','已领取',blocked,False),
        ('80','检测录入中','已领取',p,True)]:
        db.session.add(Report(report_no='QA-'+suffix,sample_no='S'+suffix,status=status,sample_status=sample,department=d.name,project=project.name,voided=voided,detail={'dataEntryStarted':True,'rawSample':{'schemeCode':project.code,'schemeName':project.name}}))
    db.session.add(Report(report_no='FOREIGN',sample_no='FOREIGN',status='检测录入中',sample_status='已领取',department='foreign'))
    db.session.commit();isolated_app.config.update(LIST_PAGE_IDS=True,LIST_QUERY_A2=True,LIST_QUERY_PROTOTYPE=False)
    return normal,corrector

def query(client,user,view,**extra):
    body=dict(view=view,serverPage=True,presentation='entry',page=1,pageSize=200,sort='code',direction='asc');body.update(extra)
    response=client.post('/api/reports/query',headers={'Authorization':'Bearer '+issue_token(user)},json=body)
    assert response.status_code==200
    payload=response.get_json();assert payload['code']==0,payload
    return payload['data']

@pytest.mark.parametrize('view',['data_entry','data_change'])
def test_corrector_pending_ids_equal_ordinary_handler(isolated_client,pending_scenario,view):
    normal,corrector=pending_scenario
    expected=query(isolated_client,normal,view,rowProjection='active')
    actual=query(isolated_client,corrector,'query',rowProjection='active',handlingView=view)
    assert actual['total']==expected['total']
    assert [r['reportNo'] for r in actual['rows']]==[r['reportNo'] for r in expected['rows']]
    assert set(r['reportNo'] for r in actual['rows'])==({'QA-2','QA-10'} if view=='data_entry' else {'QA-50','QA-60'})

@pytest.mark.parametrize('view',['data_entry','data_change'])
@pytest.mark.parametrize('direction',['asc','desc'])
def test_pending_search_sort_and_page_stay_inside_handler_ids(isolated_client,pending_scenario,view,direction):
    normal,corrector=pending_scenario
    for page in (1,2,3):
        params=dict(rowProjection='active',searchField='all',contains='QA-',sort='code',direction=direction,page=page,pageSize=1)
        expected=query(isolated_client,normal,view,**params)
        actual=query(isolated_client,corrector,'query',handlingView=view,**params)
        assert actual['total']==expected['total']
        assert [r['reportNo'] for r in actual['rows']]==[r['reportNo'] for r in expected['rows']]

@pytest.mark.parametrize('view',['data_entry','data_change'])
def test_all_and_specific_state_remain_query_scope(isolated_app,isolated_client,pending_scenario,view):
    normal,corrector=pending_scenario
    for state in ('','报告签发中'):
        old=query(isolated_client,corrector,'query',rowProjection='',dataStatus=state)
        actual=query(isolated_client,corrector,'query',rowProjection='',handlingView=view,dataStatus=state)
        assert actual==old
        if not state:assert 'QA-40' in {r['reportNo'] for r in actual['rows']}
    assert query(isolated_client,normal,view,rowProjection='active')['total']==2


def test_full_authority_pending_reuses_its_exact_ordinary_view(isolated_app,isolated_client,pending_scenario):
    normal,corrector=pending_scenario
    corrector.role_key='admin';db.session.commit()
    for view in ('data_entry','data_change'):
        expected=query(isolated_client,corrector,view,rowProjection='active')
        actual=query(isolated_client,corrector,'query',rowProjection='active',handlingView=view)
        assert [r['reportNo'] for r in actual['rows']]==[r['reportNo'] for r in expected['rows']]
        assert actual['total']==expected['total']


def test_handling_hint_cannot_widen_an_ordinary_query_or_change_all_scope(isolated_client,pending_scenario):
    normal,_=pending_scenario
    for hint in ('data_entry','data_change','unknown',{},[]):
        expected=query(isolated_client,normal,'query',rowProjection='active')
        assert query(isolated_client,normal,'query',rowProjection='active',handlingView=hint)==expected
