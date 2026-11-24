"""Contract tests for the public report-lifecycle Command boundary."""

from __future__ import annotations

import pytest

from app.applications.report_lifecycle import (
    execute_report_action,
    report_allowed_actions,
)
from app.audit import add_operation_audit
from app.extensions import db
from app.models import OperationAudit, Report

pytest_plugins = ("testkit.fixtures",)


def _released_report(scenario, report_no: str = "TEST-COMMAND-REPORT") -> Report:
    report = Report(
        report_no=report_no,
        sample_no=f"{report_no}-SAMPLE",
        client="虚拟客户",
        project=scenario.project.name,
        department=scenario.department.name,
        owner=scenario.user.name,
        status="已发放",
        sample_status="已出库",
        sample_reg_state="登记完成",
    )
    db.session.add(report)
    db.session.flush()
    import hashlib
    from app.models import ReportDocumentVersion, ReportEsignFlow
    from app.functions.esign_service import store_signed_file
    raw = b'%PDF-1.4 isolated sealed lifecycle fixture'
    version = ReportDocumentVersion(report_no=report_no, output_kind='official', version_no=1,
        status='approved', profile_code='TEST', source_hash='fixture', sha256=hashlib.sha256(raw).hexdigest(), pdf_data=raw)
    db.session.add(version); db.session.flush()
    report.current_document_version_id=report.approved_document_version_id=version.id
    flow=ReportEsignFlow(report_id=report.id,report_no=report_no,report_document_version_id=version.id,
        attempt_no=1,status='signing',source_sha256=version.sha256,
        positioning_json='{"organizationSeal":{"included":true}}')
    db.session.add(flow);db.session.flush();store_signed_file(flow,raw,scenario.user)
    return report


def test_archive_command_succeeds_once_and_rejects_duplicate_without_extra_audit(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=("report.archive.view",),
            granted_step_codes=("report_archive",),
        )
        report = _released_report(scenario)
        db.session.commit()

        first = execute_report_action(
            scenario.user,
            report.report_no,
            "report.archive.pass",
        )
        assert first.code == 0
        assert report.archive_state == "归档完成"
        assert OperationAudit.query.filter_by(
            object_type="report",
            object_id=report.report_no,
            action="report.archive.pass",
        ).count() == 1

        duplicate = execute_report_action(
            scenario.user,
            report.report_no,
            "report.archive.pass",
        )
        assert duplicate.code == 1
        assert report.archive_state == "归档完成"
        assert OperationAudit.query.filter_by(
            object_type="report",
            object_id=report.report_no,
            action="report.archive.pass",
        ).count() == 1


def test_archive_command_rejects_missing_action_permission_without_mutation(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        report = _released_report(scenario, "TEST-COMMAND-DENIED")
        db.session.commit()

        result = execute_report_action(
            scenario.user,
            report.report_no,
            "report.archive.pass",
        )

        assert result.code == 403
        assert report.archive_state in (None, "")
        assert OperationAudit.query.filter_by(
            object_type="report",
            object_id=report.report_no,
        ).count() == 0


def test_archive_command_rejects_wrong_state_without_partial_write(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=("report.archive.view",),
            granted_step_codes=("report_archive",),
        )
        report = _released_report(scenario, "TEST-COMMAND-WRONG-STATE")
        report.status = "待批准"
        db.session.commit()

        result = execute_report_action(
            scenario.user,
            report.report_no,
            "report.archive.pass",
        )

        assert result.code == 1
        assert report.status == "待批准"
        assert report.archive_state in (None, "")
        assert OperationAudit.query.filter_by(
            object_type="report",
            object_id=report.report_no,
        ).count() == 0


@pytest.mark.parametrize(
    (
        "action_code",
        "completion_action",
        "permission_code",
        "step_code",
        "status",
        "archive_state",
        "expected_status",
    ),
    (
        (
            "report.print.undo",
            "report.print.pass",
            "report.print.view",
            "report_print",
            "待发放",
            "",
            "待打印",
        ),
        (
            "report.print.undo",
            "report.print.pass",
            "report.print.view",
            "report_print",
            "已发放",
            "",
            "待打印",
        ),
        (
            "report.archive.undo",
            "report.archive.pass",
            "report.archive.view",
            "report_archive",
            "已发放",
            "归档完成",
            "已发放",
        ),
    ),
)
def test_undo_requires_current_step_and_original_completer_even_in_same_department(
    isolated_app,
    scenario_factory,
    action_code,
    completion_action,
    permission_code,
    step_code,
    status,
    archive_state,
    expected_status,
):
    with isolated_app.app_context():
        department = scenario_factory.department()
        project, steps = scenario_factory.project(department)
        step = next(row for row in steps if row.step_code == step_code)
        permission = scenario_factory.permission(permission_code)
        completer = scenario_factory.user(
            department,
            account=f"complete_{step_code}",
            permissions=(permission,),
            project_steps=(step,),
        )
        same_department_other = scenario_factory.user(
            department,
            account=f"other_{step_code}",
            permissions=(permission,),
            project_steps=(step,),
        )
        report = Report(
            report_no=f"TEST-OWNER-{step_code}",
            sample_no=f"TEST-OWNER-{step_code}-S",
            client="虚拟客户",
            project=project.name,
            department=department.name,
            owner=completer.name,
            status=status,
            sample_status="已出库" if status == "已发放" else "已领取",
            sample_reg_state="登记完成",
            archive_state=archive_state,
            stamped=action_code == "report.print.undo",
        )
        db.session.add(report)
        db.session.flush()
        add_operation_audit(
            completion_action,
            "report",
            report.report_no,
            category="workflow",
            actor=completer,
        )
        db.session.commit()

        denied = execute_report_action(
            same_department_other, report.report_no, action_code
        )
        assert denied.code == 403
        assert "完成人" in denied.message
        assert report.status == status
        assert report.archive_state == archive_state

        allowed = execute_report_action(completer, report.report_no, action_code)
        assert allowed.code == 0
        assert report.status == expected_status
        if action_code == "report.archive.undo":
            assert report.archive_state == ""
        audit = OperationAudit.query.filter_by(
            object_type="report",
            object_id=report.report_no,
            action=action_code,
        ).one()
        assert audit.user_id == completer.id


def test_undo_rejects_original_completer_after_project_step_revocation(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=("report.print.view",),
            granted_step_codes=("report_print",),
        )
        report = Report(
            report_no="TEST-REVOKED-PRINT-STEP",
            sample_no="TEST-REVOKED-PRINT-STEP-S",
            client="虚拟客户",
            project=scenario.project.name,
            department=scenario.department.name,
            owner=scenario.user.name,
            status="待发放",
            sample_status="已领取",
            sample_reg_state="登记完成",
            stamped=True,
        )
        db.session.add(report)
        db.session.flush()
        add_operation_audit(
            "report.print.pass",
            "report",
            report.report_no,
            category="workflow",
            actor=scenario.user,
        )
        scenario.user.project_steps.clear()
        db.session.commit()

        result = execute_report_action(
            scenario.user, report.report_no, "report.print.undo"
        )

        assert result.code == 403
        assert "报告签发授权" in result.message
        assert report.status == "待发放"
        assert "report.print.undo" not in report_allowed_actions(
            scenario.user, report
        )


def test_data_entry_return_requires_feature_step_and_recorded_handler(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        department = scenario_factory.department()
        project, steps = scenario_factory.project(department)
        step = next(row for row in steps if row.step_code == "data_entry")
        permission = scenario_factory.permission("testing.data_entry.view")
        handler = scenario_factory.user(
            department,
            account="recorded_data_handler",
            permissions=(permission,),
            project_steps=(step,),
        )
        same_department_other = scenario_factory.user(
            department,
            account="same_department_data_user",
            permissions=(permission,),
            project_steps=(step,),
        )
        scenario_factory.grant_action(handler, "testing.data_entry.return")
        scenario_factory.grant_action(
            same_department_other, "testing.data_entry.return"
        )
        report = Report(
            report_no="TEST-DATA-ENTRY-RETURN-OWNER",
            sample_no="TEST-DATA-ENTRY-RETURN-OWNER-S",
            client="虚拟客户",
            project=project.name,
            department=department.name,
            owner=handler.name,
            status="检测录入中",
            sample_status="已领取",
            sample_reg_state="登记完成",
        )
        db.session.add(report)
        db.session.flush()
        add_operation_audit(
            "sample.out_warehouse.sign",
            "report",
            report.report_no,
            category="workflow",
            actor=handler,
        )
        db.session.commit()

        denied = execute_report_action(
            same_department_other,
            report.report_no,
            "testing.data_entry.return",
            {"note": "虚拟退回原因"},
        )
        assert denied.code == 403
        assert "当前检测任务" in denied.message
        assert report.status == "检测录入中"

        allowed = execute_report_action(
            handler,
            report.report_no,
            "testing.data_entry.return",
            {"note": "虚拟退回原因"},
        )
        assert allowed.code == 0
        assert report.status == "委托更改中"
        audit = OperationAudit.query.filter_by(
            object_type="report",
            object_id=report.report_no,
            action="testing.data_entry.return",
        ).one()
        assert audit.user_id == handler.id


def test_data_entry_return_rejects_legacy_action_without_function_permission(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=(),
            granted_step_codes=("data_entry",),
        )
        scenario_factory.grant_action(scenario.user, "testing.data_entry.return")
        report = Report(
            report_no="TEST-DATA-ENTRY-NO-FEATURE",
            sample_no="TEST-DATA-ENTRY-NO-FEATURE-S",
            client="虚拟客户",
            project=scenario.project.name,
            department=scenario.department.name,
            owner=scenario.user.name,
            status="检测录入中",
            sample_status="已领取",
            sample_reg_state="登记完成",
            detail={
                "checkInput": {
                    "entryStaff": {"account": scenario.user.account},
                }
            },
        )
        db.session.add(report)
        db.session.commit()

        result = execute_report_action(
            scenario.user,
            report.report_no,
            "testing.data_entry.return",
            {"note": "虚拟原因"},
        )

        assert result.code == 403
        # Missing function scope already removes the legacy action permission.
        assert result.message == "无此操作权限"
        assert report.status == "检测录入中"
        assert OperationAudit.query.filter_by(
            object_type="report", object_id=report.report_no,
            action="testing.data_entry.return",
        ).count() == 0


def test_data_entry_return_rejects_recorded_handler_without_project_step(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=("testing.data_entry.view",),
            granted_step_codes=(),
        )
        scenario_factory.grant_action(scenario.user, "testing.data_entry.return")
        report = Report(
            report_no="TEST-DATA-ENTRY-NO-STEP",
            sample_no="TEST-DATA-ENTRY-NO-STEP-S",
            client="虚拟客户",
            project=scenario.project.name,
            department=scenario.department.name,
            owner=scenario.user.name,
            status="检测录入中",
            sample_status="已领取",
            sample_reg_state="登记完成",
            detail={
                "checkInput": {
                    "entryStaff": {"account": scenario.user.account},
                }
            },
        )
        db.session.add(report)
        db.session.commit()

        result = execute_report_action(
            scenario.user,
            report.report_no,
            "testing.data_entry.return",
            {"note": "虚拟原因"},
        )

        assert result.code == 403
        assert "检测数据录入授权" in result.message
        assert report.status == "检测录入中"


def test_report_command_rejects_voided_sample_without_mutation(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=("report.archive.view",),
            granted_step_codes=("report_archive",),
        )
        report = _released_report(scenario, "TEST-VOIDED-REPORT-COMMAND")
        report.voided = True
        report.sample_reg_state = "已作废"
        db.session.commit()

        result = execute_report_action(
            scenario.user, report.report_no, "report.archive.pass"
        )

        assert result.code == 1
        assert "已作废" in result.message
        assert report.archive_state in (None, "")
        assert OperationAudit.query.filter_by(
            object_type="report", object_id=report.report_no
        ).count() == 0


def test_report_command_rolls_back_state_and_audit_when_commit_fails(
    isolated_app, scenario_factory, monkeypatch
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=("report.archive.view",),
            granted_step_codes=("report_archive",),
        )
        report = _released_report(scenario, "TEST-REPORT-COMMIT-ROLLBACK")
        db.session.commit()

        def fail_commit():
            raise RuntimeError("synthetic commit failure")

        monkeypatch.setattr(db.session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            execute_report_action(
                scenario.user, report.report_no, "report.archive.pass"
            )

        db.session.expire_all()
        reloaded = Report.query.filter_by(report_no=report.report_no).one()
        assert reloaded.archive_state in (None, "")
        assert OperationAudit.query.filter_by(
            object_type="report", object_id=report.report_no
        ).count() == 0
