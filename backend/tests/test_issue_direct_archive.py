"""Issuance is followed by archive; historical release records remain readable."""
import pytest
from app.applications.report_lifecycle import execute_report_action, report_allowed_actions
from app.applications.report_lifecycle.dashboard import report_todo_view
from app.platform.workflow import report_projection
from app.extensions import db
from app.models import Report, OperationAudit
from app.status_machine import report_data_status
from app.project_workflow import normalize_skipped_steps, advance_skipped_project_steps
from app.catalog import all_action_codes, all_permission_codes
from app.report_date_rules import validate_date_order

pytest_plugins=('testkit.fixtures',)

def setup(scenario_factory, status='待打印'):
    scenario=scenario_factory.identity_scenario(permission_codes=('report.print.view','report.archive.view'),granted_step_codes=('report_print','report_archive'))
    report=Report(report_no='TEST-DIRECT-ARCHIVE',sample_no='QA-SAMPLE',client='虚拟客户',project=scenario.project.name,department=scenario.department.name,owner=scenario.user.name,status=status,sample_status='已领取',sample_reg_state='登记完成')
    db.session.add(report);db.session.commit()
    return scenario,report

def test_legacy_confirm_does_not_release_or_allow_archive_without_sealed_file(isolated_app,scenario_factory,monkeypatch):
    with isolated_app.app_context():
        scenario,report=setup(scenario_factory)
        monkeypatch.setattr('app.functions.esign_service.issuance_blocker',lambda report:'')
        assert execute_report_action(scenario.user,report.report_no,'report.print.pass').code==0
        assert report.status=='待发放' and report.sample_status=='已领取'
        assert execute_report_action(scenario.user,report.report_no,'report.archive.pass').code!=0
        assert not report.archive_state
        assert OperationAudit.query.filter_by(action='report.distribution.complete').count()==0


def test_unfinished_signing_cannot_issue_or_archive(isolated_app,scenario_factory,monkeypatch):
    with isolated_app.app_context():
        scenario,report=setup(scenario_factory)
        monkeypatch.setattr('app.functions.esign_service.issuance_blocker',lambda report:'请先确认签章')
        assert execute_report_action(scenario.user,report.report_no,'report.print.pass').code!=0
        assert execute_report_action(scenario.user,report.report_no,'report.archive.pass').code!=0
        assert report.status=='待打印'

@pytest.mark.parametrize('status',['待发放','已发放'])
def test_existing_release_records_can_archive_without_reissue_or_relabeling_history(isolated_app,scenario_factory,status):
    with isolated_app.app_context():
        scenario,report=setup(scenario_factory,status)
        from app.audit import add_operation_audit
        if status == '已发放':
            add_operation_audit('report.release.pass','report',report.report_no,category='workflow',actor=scenario.user)
            db.session.commit()
        old_events = [(a.id,a.action,a.user_id,a.created_at) for a in OperationAudit.query.all()]
        assert report_data_status(status,'已领取')=='报告已盖章，归档中，未发放'
        assert report_todo_view(scenario.user,report)=='archive'
        assert execute_report_action(scenario.user,report.report_no,'report.archive.pass').code!=0
        assert report.status==status  # preserve historical storage/evidence
        assert OperationAudit.query.filter_by(action='report.release.pass').count()==int(status=='已发放')
        assert [(a.id,a.action,a.user_id,a.created_at) for a in OperationAudit.query.filter(OperationAudit.action!='report.archive.pass').all()] == old_events

@pytest.mark.parametrize('action',['report.release.pass','report.release.return','report.release.undo'])
def test_retired_actions_are_rejected_even_with_stale_grants(isolated_app,scenario_factory,action):
    with isolated_app.app_context():
        scenario,report=setup(scenario_factory,'待发放')
        scenario_factory.grant_action(scenario.user,action);db.session.commit()
        result=execute_report_action(scenario.user,report.report_no,action,{'note':'旧入口'})
        assert result.code!=0 and '旧版发放接口已停用' in result.message
        assert report.status=='待发放'
        assert OperationAudit.query.filter_by(action=action).count()==0

def test_project_skips_issue_into_archive_without_a_release_node(isolated_app,scenario_factory):
    with isolated_app.app_context():
        scenario,report=setup(scenario_factory)
        scenario.project.workflow_config={'skippedSteps':['report_print','report_release']}
        db.session.commit()
        assert advance_skipped_project_steps(report)==[]
        assert report.to_row()['dataStatus']=='报告签发中'
        assert report.sample_status=='已领取'
        assert report.archive_state in (None,'')

def test_catalog_and_dates_do_not_require_release():
    assert 'report_release' not in normalize_skipped_steps(['report_release','report_archive'])
    assert 'report.release.view' in all_permission_codes()
    assert 'report.distribution.complete' in all_action_codes()
    assert not any(code.startswith('report.release.') for code in all_action_codes())
    assert validate_date_order({'issue':'2026-10-28','archive':'2026-10-27'},through='archive')
    assert not validate_date_order({'issue':'2026-10-28','archive':'2026-10-28'},through='archive')


def test_customer_document_publish_uses_issue_permission_and_project_scope(monkeypatch):
    from types import SimpleNamespace
    from app.blueprints import public_portal as portal
    project = object()
    user = SimpleNamespace(role_key='operator',action_codes=lambda:['report.print.pass'])
    monkeypatch.setattr(portal,'project_for_report',lambda report:project)
    monkeypatch.setattr(portal,'user_has_project_step',lambda u,p,step:p is project and step=='report_print')
    assert portal._has_customer_document_publish_access(user,'certificate',None,related_report=object())
    assert not portal._has_customer_document_publish_access(user,'certificate',None)
    monkeypatch.setattr(portal,'user_has_project_step',lambda *args:False)
    assert not portal._has_customer_document_publish_access(user,'certificate',None,related_report=object())
    user.action_codes=lambda:['report.release.pass']
    assert not portal._has_customer_document_kind_access(user,'certificate')
