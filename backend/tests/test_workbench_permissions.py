"""Workspace permission matrix and ordinary-user recent completion events."""
import pytest
from app.extensions import db
from app.models import Report, OperationAudit
from app.app_workspace import dashboard_data

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('role,permissions,allowed',[
    ('admin',[],{'general','admin','analyst','reviewer','approver'}),
    ('operator',[],{'general'}),
    ('operator',['testing.data_entry.view'],{'general','analyst'}),
    ('operator',['report.review.view'],{'general','reviewer'}),
    ('operator',['report.approval.view'],{'general','approver'}),
    ('operator',['entrust.contract_review.view'],{'general'}),
])
def test_workbench_access(isolated_app,scenario_factory,role,permissions,allowed):
    dept=scenario_factory.department()
    user=scenario_factory.user(dept,role_key=role,permissions=permissions)
    for board in ['general','admin','analyst','reviewer','approver']:
        if board in allowed: assert dashboard_data(user,{'workbench':board})['pending']==0
        else:
            with pytest.raises(PermissionError): dashboard_data(user,{'workbench':board})


def test_regular_user_recent_seal_and_release_without_query_permission(isolated_app,scenario_factory):
    dept=scenario_factory.department()
    user=scenario_factory.user(dept,permissions=['report.print.view','report.release.view'])
    db.session.add(Report(report_no='RECENT',department=dept.name,status='待发放'))
    for action in ['report.seal.completed','report.distribution.complete']:
        db.session.add(OperationAudit(object_type='report',object_id='RECENT',action=action,success=True,user_id=user.id))
    db.session.commit()
    data=dashboard_data(user,{'workbench':'general'})
    assert {r['to'].split('?')[0] for r in data['recent']} == {'/inspection/report/print','/inspection/report/release'}


def test_contract_reviewer_tasks_keep_department_and_action_scope(isolated_app,scenario_factory):
    dept=scenario_factory.department()
    project,steps=scenario_factory.project(dept)
    user=scenario_factory.user(dept,permissions=['entrust.contract_review.view'],project_steps=steps)
    scenario_factory.grant_action(user,'report.contract_review.pass')
    for no,department,status in [('OWN',dept.name,'待合同评审'),('FOREIGN','其他部门','待合同评审'),('LATER',dept.name,'待审核')]:
        db.session.add(Report(report_no=no,department=department,project=project.name,status=status,sample_status='待入库',sample_reg_state='登记完成',detail={'rawSample':{'schemeCode':project.code,'schemeName':project.name}}))
    db.session.commit()
    data=dashboard_data(user,{'workbench':'general'})
    assert [r['id'] for r in data['items']] == ['OWN']
    assert data['items'][0]['status']=='合同评审中'
