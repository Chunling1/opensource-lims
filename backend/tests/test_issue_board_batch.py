import pytest
from app.platform.workflow.visibility import report_projection
from app.sample_pricing import price_error, completion_error

@pytest.mark.parametrize('status', ['待合同评审','检测录入中','待审核','待批准','待打印','待发放','已发放'])
def test_archive_all_statuses_are_readable(status):
    row={'status':status, 'archiveState':'归档完成', 'allowedActions':[]}
    assert report_projection(row,'archive') == 'recall'
    assert row['allowedActions'] == []

def test_archive_pending_keeps_active_projection():
    assert report_projection({'status':'待打印','dataStatus':'报告已盖章，归档中，未发放','allowedActions':['report.archive.pass']},'archive')=='active'
    assert report_projection({'status':'待打印','dataStatus':'报告签发中'},'archive')=='recall'

@pytest.mark.parametrize('key', ['amount','receivedAmount'])
@pytest.mark.parametrize('value', ['', ' ', None, 'NaN', '1.234'])
def test_amounts_required_on_draft_and_completion(key,value):
    row={'projectName':'P','dept':'D','businessCategory':'B','paymentDescription':'约定','amount':'0','receivedAmount':'0'}
    row[key]=value
    d={'rawSample':{'stdPrice':'0','subItems':[row]}}
    label='子项金额' if key=='amount' else '收款金额'
    assert label in price_error(d)
    assert label in completion_error(d)

pytest_plugins=('testkit.fixtures',)

def test_archive_query_and_detail_respect_data_and_module_scope(isolated_app, isolated_client, scenario_factory):
    from app.extensions import db
    from app.models import Report
    from app.security import issue_token
    from app.applications.report_lifecycle.queries import get_authorized_report_for_view, report_allowed_actions
    f=scenario_factory
    dept=f.department(name='虚拟归档部门')
    other=f.department(name='虚拟其他部门')
    user=f.user(dept, permissions=['report.archive.view'])
    local=[Report(report_no='ARCHIVE-'+str(i),department=dept.name,status=status,sample_reg_state='登记完成') for i,status in enumerate(['待合同评审','检测录入中','待审核','待批准','待打印','已发放'])]
    foreign=Report(report_no='ARCHIVE-FOREIGN',department=other.name,status='待审核')
    db.session.add_all([*local,foreign]);db.session.commit()
    headers={'Authorization':'Bearer '+issue_token(user)}
    response=isolated_client.post('/api/reports/query',headers=headers,json={'view':'archive','pageSize':100}).get_json()
    assert response['code']==0,response
    assert {r['reportNo'] for r in response['data']['rows']}=={r.report_no for r in local}
    for row in local:
        found,projection,error=get_authorized_report_for_view(user,row.report_no,'archive')
        assert found==row and not error
        assert 'report.archive.pass' not in report_allowed_actions(user,row)
    assert get_authorized_report_for_view(user,foreign.report_no,'archive')[2]
    user.permissions=[];db.session.commit()
    assert isolated_client.post('/api/reports/query',headers=headers,json={'view':'archive'}).get_json()['code']!=0
