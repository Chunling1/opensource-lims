"""补充、英文、分项与签发后更正报告的隔离流程测试。"""

from __future__ import annotations

from io import BytesIO

import pytest

from app.blueprints import reports as report_routes
from app.extensions import db
from app.models import Report, ReportCorrectionRequest, ReportDocumentContent
from app.report_correction_permissions import assign
from testkit.factories import login_headers


pytest_plugins = ("testkit.fixtures",)


def _main_report(report_no: str, department: str) -> Report:
    row = Report(
        report_no=report_no,
        sample_no=f"{report_no}-S",
        project="TEST-PROJECT",
        project_name="虚拟派生报告项目",
        client="虚拟客户",
        template="REPORT_TEMPLATE",
        version="V1.0",
        status="待打印",
        sign="已批准",
        department=department,
        owner="虚拟主检",
        detail={
            "summary": [{"title": "检测信息", "fields": [["参数", "原始值"]]}],
            "signatures": {"主检": {"name": "虚拟主检"}, "审核": {"name": "虚拟审核"}, "批准": {"name": "虚拟批准"}},
        },
        sample_status="已领取",
        sample_reg_state="登记完成",
        report_kind="main",
    )
    db.session.add(row)
    db.session.flush()
    db.session.add(
        ReportDocumentContent(
            report_no=report_no,
            profile_code="TEST-PROFILE",
            result_groups=[{"name": "结果组", "rows": [{"value": "1.0"}]}],
            remarks="主报告备注",
            photos=[],
            extra_pages=[],
            updated_by="testkit",
        )
    )
    return row


def _actor(factory, department, *, account: str, name: str):
    user = factory.user(
        department,
        account=account,
        name=name,
        permissions=("report.change_request.view",),
    )
    factory.grant_action(user, "report.change.request")
    return user


def test_unused_derivatives_endpoint_is_removed(isolated_app, isolated_client, scenario_factory):
    """Batch-3 Q4 (2026-11-07): derived reports are created only through the
    registration path (POST /api/reports + /api/reports/derivable). The unused
    /<report_no>/derivatives endpoint, which required main-report approval, is gone."""
    with isolated_app.app_context():
        department = scenario_factory.department(name="虚拟声学检测部")
        actor = _actor(scenario_factory, department, account="derivative_actor", name="虚拟派生申请人")
        _main_report("LAB-2026LQ-9001", department.name)
        db.session.commit()
        actor_account = actor.account
        assert not any(rule.rule.endswith("/derivatives") for rule in isolated_app.url_map.iter_rules())
    headers = login_headers(isolated_client, actor_account)
    for method in ("post", "get"):
        response = getattr(isolated_client, method)(
            "/api/reports/LAB-2026LQ-9001/derivatives", json={"kind": "supplement"}, headers=headers)
        assert response.status_code in (404, 405)
    with isolated_app.app_context():
        assert Report.query.filter_by(report_no="LAB-2026LQ-9001BC").count() == 0


def test_legacy_correction_keeps_evidence_and_two_level_approval_before_uppercase_gz(
    isolated_app, isolated_client, scenario_factory, monkeypatch
):
    with isolated_app.app_context():
        department = scenario_factory.department(name="虚拟净化空调检测部")
        applicant = _actor(
            scenario_factory,
            department,
            account="correction_applicant",
            name="虚拟更正申请人",
        )
        director = scenario_factory.user(
            department,
            account="correction_director",
            name="虚拟部门主任",
            permissions=("report.change_request.view",),
        )
        leader = scenario_factory.user(
            department,
            account="correction_leader",
            name="虚拟院领导",
            permissions=("report.change_request.view",),
        )
        assign(director, "correctionApprovalLevel1", True)
        assign(leader, "correctionApprovalLevel2", True)
        main = _main_report("LAB-2026LQ-9002", department.name)
        main.archive_state = "归档完成"
        db.session.commit()
        applicant_account = applicant.account
        director_account = director.account
        leader_account = leader.account

    applicant_headers = login_headers(isolated_client, applicant_account)
    director_headers = login_headers(isolated_client, director_account)
    leader_headers = login_headers(isolated_client, leader_account)

    # Existing stored applications retain their two-level route. New applications
    # are covered by test_report_correction_approval and require a correctionType.
    with isolated_app.app_context():
        from app.applications.report_lifecycle import persist_report_attachment
        main = Report.query.filter_by(report_no="LAB-2026LQ-9002").one()
        attachment = persist_report_attachment(main, b"%PDF-1.4 legacy evidence", category="correction_application",
            name="correction.pdf", content_type="application/pdf", kind="PDF", source="更正申请扫描件",
            status="待审批", uploaded_by="testkit", created_by="testkit")
        row = ReportCorrectionRequest(main_report_no=main.report_no, return_mode="entrust_and_data",
            reason="委托字段和检测数据均需更正", application_attachment_id=attachment.id, status="pending_director",
            applicant_account=applicant_account, applicant_name="测试申请人", department=main.department)
        db.session.add(row); db.session.commit(); request_id = row.id
        assert row.correction_type is None

    out_of_order = isolated_client.post(
        f"/api/reports/correction-requests/{request_id}/decision",
        json={"stage": "pending_director", "decision": "approve", "note": "不应越级"},
        headers=leader_headers,
    ).get_json()
    assert out_of_order["code"] == 403

    director_result = isolated_client.post(
        f"/api/reports/correction-requests/{request_id}/decision",
        json={"stage": "pending_director", "decision": "approve", "note": "部门主任同意"},
        headers=director_headers,
    ).get_json()
    assert director_result["code"] == 0, director_result
    assert director_result["data"]["status"] == "pending_leader"

    leader_result = isolated_client.post(
        f"/api/reports/correction-requests/{request_id}/decision",
        json={"stage": "pending_leader", "decision": "approve", "note": "院领导同意"},
        headers=leader_headers,
    ).get_json()
    assert leader_result["code"] == 0, leader_result
    assert leader_result["data"]["status"] == "approved"
    assert leader_result["data"]["correctionReportNo"] == "LAB-2026LQ-9002GZ"

    with isolated_app.app_context():
        main = Report.query.filter_by(report_no="LAB-2026LQ-9002").one()
        correction = Report.query.filter_by(report_no="LAB-2026LQ-9002GZ").one()
        request_row = db.session.get(ReportCorrectionRequest, request_id)
        assert main.status == "待打印"
        assert main.archive_state == "归档完成"
        assert correction.main_report_no == main.report_no
        assert correction.report_kind == "correction"
        assert correction.report_suffix == "GZ"
        assert correction.status == "委托更改中"
        assert (correction.detail or {})["returnPlan"]["mode"] == "entrust_and_data"
        assert (correction.detail or {})["correctionRequestId"] == request_id
        assert request_row.application_attachment.source == "更正申请扫描件"
