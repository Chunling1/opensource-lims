"""Sort all matching IDs before pagination, using the displayed dated facts."""
from datetime import datetime
import pytest
from app.extensions import db
from app.models import Report, Entrust, OperationAudit
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('path', ['legacy','ids','a2'])
@pytest.mark.parametrize('endpoint,presentation', [('reports','report'),('reports','entry'),('samples','registration-sample')])
def test_headers_sort_global_results_and_displayed_values(isolated_app,isolated_client,scenario_factory,path,endpoint,presentation):
    isolated_app.config.update(LIST_PAGE_IDS=path!='legacy',LIST_QUERY_A2=path=='a2',LIST_QUERY_PROTOTYPE=False)
    d=scenario_factory.department()
    u=scenario_factory.user(d,role_key='admin',account='admin')
    stages={'contractReviewedAt':'report.contract_review.pass','dataSavedAt':'report.data_entry.save',
        'dataCompletedAt':'report.data_entry.complete','reportCheckedAt':'report.report_check.pass',
        'reportReviewedAt':'report.review.pass','reportApprovedAt':'report.approval.pass',
        'reportIssuedAt':'report.print.pass','reportArchivedAt':'report.archive.pass','reportReleasedAt':'report.distribution.complete'}
    for n,day in [(10,1),(2,3),(1,2)]:
        date=f'2026-11-{day:02}'
        e=Entrust(entrust_no=f'WT-{n}',department=d.name,info={'entrustDate':date})
        r=Report(report_no=f'SORT-{n}',sample_no=f'S-{n}',entrust_no=e.entrust_no,department=d.name,status='待批准',sample_status='已领取',
            detail={'sampleRegisteredAt':date,'rawSample':{'sendDate':date,'sampleTime':date,'produceDate':date},
                    'checkInput':{'testStartDate':date,'testDate':date},'workflowDates':{'sampleInboundAt':date}},
            sample_pickup={'outTime':date,'pickupTime':date,'signed':True})
        db.session.add_all([e,r])
        for action in stages.values():
            db.session.add(OperationAudit(object_type='report',object_id=r.report_no,action=action,success=True,created_at=datetime(2026,11,day)))
            db.session.add(OperationAudit(object_type='report',object_id=r.report_no,action=action,success=False,created_at=datetime(2026,12,day)))
    db.session.commit()
    headers={'Authorization':'Bearer '+issue_token(u)}
    keys=['reportCode','commissionCode','code','commissionDate','sendDate','samplingTime']
    if presentation=='report':keys+=list(stages)+['sampleInboundDate','sampleOutboundDate','samplePickupDate','productionDate','testStartDate','testEndDate','checkDate','auditDate','approvalDate','printDate','archiveDate','distributionDate']
    elif presentation=='entry':keys+=['dataSavedAt','dataCompletedAt','testStartDate','testEndDate']
    else:keys+=['contractReviewedAt','sampleRegisteredAt']
    for key in keys:
        for direction in ['asc','desc']:
            body=dict(view='flow_query' if endpoint=='samples' else 'query',serverPage=True,presentation=presentation,page=2,pageSize=1,sort=key,direction=direction,searchField='reportCode',contains='SORT-')
            payload=isolated_client.post('/api/'+endpoint+'/query',json=body,headers=headers).get_json()
            assert payload['code']==0,(key,payload)
            assert payload['data']['total']==3,(key,payload)
            row=payload['data']['rows'][0]
            assert row['reportNo']==('SORT-2' if key in ['code','reportCode','commissionCode'] else 'SORT-1'),(key,row['reportNo'])
            if key in stages:assert row[key].startswith('2026-11-02'),(key,row.get(key))
            body['page']=1
            first_payload=isolated_client.post('/api/'+endpoint+'/query',json=body,headers=headers).get_json()
            assert first_payload['code']==0,(key,direction,first_payload)
            first=first_payload['data']['rows'][0]
            expected=('SORT-1' if direction=='asc' else 'SORT-10') if key in ['code','reportCode','commissionCode'] else ('SORT-10' if direction=='asc' else 'SORT-2')
            assert first['reportNo']==expected,(key,direction,first['reportNo'])
    # A selective filter still applies before ordering and pagination.
    body.update(contains='SORT-10',page=1)
    payload=isolated_client.post('/api/'+endpoint+'/query',json=body,headers=headers).get_json()
    assert payload['data']['total']==1 and payload['data']['rows'][0]['reportNo']=='SORT-10'
