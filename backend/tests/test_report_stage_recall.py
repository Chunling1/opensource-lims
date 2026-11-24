"""Real recall endpoint against synthetic reports in an isolated temporary DB."""
import pytest
from app.audit import add_operation_audit
from app.extensions import db
from app.models import Report, OperationAudit
from testkit.factories import login_headers

pytest_plugins=('testkit.fixtures',)


@pytest.mark.parametrize('stage,before,after,removed',[
    ('review','待批准','待审核',('审核','批准')),
    ('approval','待打印','待批准',('批准',)),
])
def test_recall_persists_state_clears_signatures_and_rejects_repeat(
    isolated_client,scenario_factory,stage,before,after,removed
):
    scenario=scenario_factory.identity_scenario(
        permission_codes=(f'report.{stage}.view',),
        granted_step_codes=('report_review' if stage=='review' else 'report_approval',))
    user=scenario.user
    scenario_factory.grant_action(user,f'report.{stage}.undo')
    report=Report(report_no='TEST-RECALL-001',sample_no='TEST-RECALL-S',status=before,
        department=scenario.department.name,project=scenario.project.name,owner=user.name,
        sample_reg_state='登记完成',sample_status='已领取',
        detail={'signatures':{role:{'name':user.name,'date':'2026-10-23'} for role in ('主检','审核','批准')}})
    db.session.add(report)
    db.session.flush()
    add_operation_audit(f'report.{stage}.pass','report',report.report_no,category='workflow',actor=user)
    db.session.commit()
    headers=login_headers(isolated_client,user.account)
    response=isolated_client.post(f'/api/reports/{report.report_no}/action',headers=headers,json={'action':f'report.{stage}.undo'})
    assert response.json['code']==0, response.json
    db.session.expire_all()
    saved=Report.query.filter_by(report_no='TEST-RECALL-001').one()
    assert saved.status==after
    assert '主检' in saved.detail['signatures']
    assert all(role not in saved.detail['signatures'] for role in removed)
    if stage=='approval': assert '审核' in saved.detail['signatures']
    repeat=isolated_client.post(f'/api/reports/{report.report_no}/action',headers=headers,json={'action':f'report.{stage}.undo'})
    assert repeat.json['code']!=0
    assert OperationAudit.query.filter_by(action=f'report.{stage}.undo',object_id=report.report_no).count()==1
