"""Side-effect-free contract tests for report electronic issuance."""

from __future__ import annotations

import hashlib
from datetime import date

from app import report_documents
from app.functions import esign_service
from app.audit import add_operation_audit
from app.extensions import db
from app.external_side_effects import request_has_external_side_effect
from app.functions.esign_service import (
    ensure_report_esign_flow,
    issuance_blocker,
    normalize_psn_account,
    send_initial_sms_notifications,
)
from app.models import (
    Department,
    EsignIdentityBinding,
    EsignReminderLog,
    OperationAudit,
    Report,
    ReportDocumentVersion,
    ReportEsignFlow,
    ReportEsignSigner,
    User,
)
from testkit.factories import login_headers

pytest_plugins = ("testkit.fixtures",)


import pytest

@pytest.fixture(autouse=True)
def _mock_esign_ready(monkeypatch):
    monkeypatch.setattr("app.esign_production.require_ready", lambda: None)


def _approved_report(report_no: str, department: str, owner: str) -> Report:
    pdf = b"%PDF-1.4\n% isolated e-sign fixture\n%%EOF"
    report = Report(
        report_no=report_no,
        sample_no=f"{report_no}-S",
        project="虚拟电子签发项目",
        client="虚拟客户",
        department=department,
        owner=owner,
        status="待打印",
        detail={},
    )
    db.session.add(report)
    db.session.flush()
    version = ReportDocumentVersion(
        report_no=report_no,
        output_kind="official",
        version_no=1,
        status="approved",
        profile_code="TEST-ESIGN",
        composition=[],
        snapshot={},
        warnings=[],
        source_hash="isolated-source-hash",
        sha256=hashlib.sha256(pdf).hexdigest(),
        pdf_data=pdf,
        created_by="testkit",
    )
    db.session.add(version)
    db.session.flush()
    report.current_document_version_id = version.id
    report.approved_document_version_id = version.id
    return report


def _binding(user, mobile: str) -> EsignIdentityBinding:
    row = EsignIdentityBinding(
        user_id=user.id,
        legal_name=user.name,
        psn_account=mobile,
        psn_account_kind="mobile",
        status="pending",
    )
    db.session.add(row)
    return row


def test_flow_uses_actual_chief_reviewer_and_approver_and_is_idempotent(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        chief = scenario.user
        reviewer = scenario_factory.user(
            scenario.department, account="test_reviewer", name="虚拟审核员"
        )
        approver = scenario_factory.user(
            scenario.department, account="test_approver", name="虚拟批准员"
        )
        report = _approved_report("TEST-ESIGN-001", scenario.department.name, chief.name)
        report.detail = {"checkInput": {"people": {"primaryTester1": {"userId": chief.id}}}}
        add_operation_audit(
            "report.review.pass", "report", report.report_no,
            category="workflow", actor=reviewer,
        )
        add_operation_audit(
            "report.approval.pass", "report", report.report_no,
            category="workflow", actor=approver,
        )
        _binding(chief, "13800000001")
        _binding(reviewer, "13800000002")
        _binding(approver, "13800000003")
        db.session.commit()

        first = ensure_report_esign_flow(report.report_no, approver)
        second = ensure_report_esign_flow(report.report_no, approver)

        assert first.id == second.id
        assert first.status == "ready"
        assert ReportEsignFlow.query.count() == 1
        assert [(row.role_code, row.user_id, row.sign_order) for row in first.signers] == [
            ("chief", chief.id, 1),
            ("reviewer", reviewer.id, 2),
            ("approver", approver.id, 3),
        ]
        assert OperationAudit.query.filter_by(
            object_type="report", object_id=report.report_no,
            action="report.esign.prepare",
        ).count() == 1


def test_prepare_converts_word_only_approved_report_to_new_complete_pdf_version(
    isolated_app, scenario_factory, monkeypatch
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        chief = scenario.user
        reviewer = scenario_factory.user(
            scenario.department, account="test_word_reviewer", name="虚拟Word审核员"
        )
        approver = scenario_factory.user(
            scenario.department, account="test_word_approver", name="虚拟Word批准员"
        )
        report = _approved_report("TEST-ESIGN-WORD-001", scenario.department.name, chief.name)
        old_version = db.session.get(ReportDocumentVersion, report.approved_document_version_id)
        old_version.docx_data = b"PK\x03\x04 approved Word report"
        old_version.pdf_data = None
        old_version.sha256 = hashlib.sha256(old_version.docx_data).hexdigest()
        report.detail = {"checkInput": {"people": {"primaryTester1": {"userId": chief.id}}}}
        add_operation_audit(
            "report.review.pass", "report", report.report_no,
            category="workflow", actor=reviewer,
        )
        add_operation_audit(
            "report.approval.pass", "report", report.report_no,
            category="workflow", actor=approver,
        )
        _binding(chief, "13700000001")
        _binding(reviewer, "13700000002")
        _binding(approver, "13700000003")
        db.session.commit()
        old_version_id = old_version.id
        pdf = b"%PDF-1.4\n% complete report generated by WPS\n%%EOF"
        monkeypatch.setattr(
            report_documents,
            "document_preflight",
            lambda _report, _kind="official": {"missing": [], "content": {}, "warnings": []},
        )
        monkeypatch.setattr(report_documents, "build_document", lambda *_args, **_kwargs: b"PK\x03\x04 final Word")
        monkeypatch.setattr(report_documents, "build_complete_report_pdf", lambda _report: (pdf, []))

        flow = ensure_report_esign_flow(report.report_no, approver)
        db.session.refresh(report)
        new_version = db.session.get(ReportDocumentVersion, report.approved_document_version_id)

        assert flow.status == "ready"
        assert new_version.id != old_version_id
        assert new_version.status == "approved"
        assert new_version.pdf_file_id is not None
        assert new_version.docx_file_id is not None
        assert new_version.sha256 == hashlib.sha256(pdf).hexdigest()
        assert flow.report_document_version_id == new_version.id
        assert flow.source_sha256 == new_version.sha256
        assert db.session.get(ReportDocumentVersion, old_version_id).pdf_file_id is None
        assert OperationAudit.query.filter_by(
            object_type="report", object_id=report.report_no,
            action="report.esign.pdf.materialize",
        ).count() == 1


def test_prepare_builds_complete_pdf_when_approved_report_has_no_version_pointer(
    isolated_app, scenario_factory, monkeypatch
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        chief = scenario.user
        reviewer = scenario_factory.user(
            scenario.department, account="test_noversion_reviewer", name="虚拟无版本审核员"
        )
        approver = scenario_factory.user(
            scenario.department, account="test_noversion_approver", name="虚拟无版本批准员"
        )
        report = _approved_report("TEST-ESIGN-NOVERSION-001", scenario.department.name, chief.name)
        report.current_document_version_id = None
        report.approved_document_version_id = None
        report.detail = {"checkInput": {"people": {"primaryTester1": {"userId": chief.id}}}}
        add_operation_audit(
            "report.review.pass", "report", report.report_no,
            category="workflow", actor=reviewer,
        )
        add_operation_audit(
            "report.approval.pass", "report", report.report_no,
            category="workflow", actor=approver,
        )
        _binding(chief, "13600000001")
        _binding(reviewer, "13600000002")
        _binding(approver, "13600000003")
        db.session.commit()
        pdf = b"%PDF-1.4\n% complete report generated without prior version\n%%EOF"
        monkeypatch.setattr(
            report_documents,
            "document_preflight",
            lambda _report, _kind="official": {"missing": [], "content": {}, "warnings": []},
        )
        monkeypatch.setattr(report_documents, "build_document", lambda *_args, **_kwargs: b"PK\x03\x04 final Word")
        monkeypatch.setattr(report_documents, "build_complete_report_pdf", lambda _report: (pdf, []))

        flow = ensure_report_esign_flow(report.report_no, approver)
        db.session.refresh(report)
        version = db.session.get(ReportDocumentVersion, report.approved_document_version_id)

        assert flow.status == "ready"
        assert version.status == "approved"
        assert version.pdf_file_id is not None
        assert version.docx_file_id is not None
        assert version.sha256 == hashlib.sha256(pdf).hexdigest()
        assert flow.report_document_version_id == version.id


def test_missing_binding_fails_closed_and_issuance_gate_waits_for_completion(
    isolated_app, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        chief = scenario.user
        reviewer = scenario_factory.user(
            scenario.department, account="test_reviewer_missing", name="虚拟审核员乙"
        )
        approver = scenario_factory.user(
            scenario.department, account="test_approver_missing", name="虚拟批准员乙"
        )
        report = _approved_report("TEST-ESIGN-002", scenario.department.name, chief.name)
        add_operation_audit(
            "report.review.pass", "report", report.report_no,
            category="workflow", actor=reviewer,
        )
        add_operation_audit(
            "report.approval.pass", "report", report.report_no,
            category="workflow", actor=approver,
        )
        _binding(chief, "13900000001")
        _binding(reviewer, "13900000002")
        db.session.commit()

        flow = ensure_report_esign_flow(report.report_no, approver)

        assert flow.status == "binding_required"
        assert "批准" in (flow.error_message or "")
        approver_signer = ReportEsignSigner.query.filter_by(
            flow_id=flow.id, role_code="approver"
        ).one()
        assert approver_signer.status == "binding_required"
        isolated_app.config["ESIGN_REQUIRED_FOR_ISSUANCE"] = True
        assert "尚未完成" in issuance_blocker(report)
        flow.status = "completed"
        db.session.commit()
        assert issuance_blocker(report) is None


def test_initial_sms_sends_each_distinct_signer_once_and_keeps_daily_channel_separate(
    isolated_app, scenario_factory, monkeypatch
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        chief = scenario.user
        reviewer = scenario_factory.user(
            scenario.department, account="test_sms_reviewer", name="虚拟短信审核员"
        )
        approver = scenario_factory.user(
            scenario.department, account="test_sms_approver", name="虚拟短信批准员"
        )
        report = _approved_report("TEST-ESIGN-SMS-001", scenario.department.name, chief.name)
        report.detail = {"checkInput": {"people": {"primaryTester1": {"userId": chief.id}}}}
        add_operation_audit(
            "report.review.pass", "report", report.report_no,
            category="workflow", actor=reviewer,
        )
        add_operation_audit(
            "report.approval.pass", "report", report.report_no,
            category="workflow", actor=approver,
        )
        _binding(chief, "13500000001")
        _binding(reviewer, "13500000002")
        _binding(approver, "13500000003")
        db.session.commit()
        flow = ensure_report_esign_flow(report.report_no, approver)
        flow.status = "signing"
        flow.provider_flow_id = "sandbox-flow-sms-001"
        # A scheduled reminder for the same user/day must not suppress the
        # per-flow initial notification.
        db.session.add(EsignReminderLog(
            user_id=chief.id,
            reminder_date=date.today().isoformat(),
            channel="sms",
            pending_count=1,
            status="sent",
        ))
        db.session.commit()

        calls = []

        def fake_batch(user, flow_ids=None, *, notify_sms=False):
            calls.append((user.id, tuple(flow_ids or ()), notify_sms))
            return {"batchSerialId": f"batch-{user.id}"}

        monkeypatch.setattr(esign_service, "batch_sign_url_for_user", fake_batch)
        first = send_initial_sms_notifications(flow.id, actor=approver)
        second = send_initial_sms_notifications(flow.id, actor=approver)

        assert first["sent"] == 3
        assert first["failed"] == []
        assert second["sent"] == 0
        assert second["skipped"] == 3
        assert len(calls) == 3
        assert all(item[1] == (flow.id,) and item[2] is True for item in calls)
        assert EsignReminderLog.query.filter(
            EsignReminderLog.channel.like("initial:%"),
            EsignReminderLog.status == "sent",
        ).count() == 3


def test_initial_sms_failure_is_audited_without_changing_signing_flow(
    isolated_app, scenario_factory, monkeypatch
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        chief = scenario.user
        reviewer = scenario_factory.user(
            scenario.department, account="test_sms_fail_reviewer", name="虚拟失败审核员"
        )
        approver = scenario_factory.user(
            scenario.department, account="test_sms_fail_approver", name="虚拟失败批准员"
        )
        report = _approved_report("TEST-ESIGN-SMS-FAIL", scenario.department.name, chief.name)
        report.detail = {"checkInput": {"people": {"primaryTester1": {"userId": chief.id}}}}
        add_operation_audit("report.review.pass", "report", report.report_no, category="workflow", actor=reviewer)
        add_operation_audit("report.approval.pass", "report", report.report_no, category="workflow", actor=approver)
        _binding(chief, "13400000001")
        _binding(reviewer, "13400000002")
        _binding(approver, "13400000003")
        db.session.commit()
        flow = ensure_report_esign_flow(report.report_no, approver)
        flow.status = "signing"
        flow.provider_flow_id = "sandbox-flow-sms-fail"
        db.session.commit()

        def fail_one(user, flow_ids=None, *, notify_sms=False):
            if user.id == reviewer.id:
                raise esign_service.EsignServiceError("sandbox_sms_rejected", "沙箱短信拒绝")
            return {"batchSerialId": f"batch-{user.id}"}

        monkeypatch.setattr(esign_service, "batch_sign_url_for_user", fail_one)
        result = send_initial_sms_notifications(flow.id, actor=approver)

        assert result["sent"] == 2
        assert result["failed"] == [{"userId": reviewer.id, "code": "sandbox_sms_rejected"}]
        assert db.session.get(ReportEsignFlow, flow.id).status == "signing"
        assert EsignReminderLog.query.filter_by(status="failed").count() == 1


def test_invalid_mobile_is_rejected_without_persisting_binding(
    isolated_app, isolated_client, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        admin = scenario_factory.user(
            scenario.department,
            account="test_esign_admin",
            name="虚拟电子签署管理员",
            role_key="admin",
        )
        db.session.commit()
        target_id = scenario.user.id
        admin_account = admin.account

    headers = login_headers(isolated_client, admin_account)
    response = isolated_client.put(
        f"/api/esign/admin/bindings/{target_id}",
        headers=headers,
        json={"legalName": "虚拟人员", "psnAccountKind": "mobile", "psnAccount": "123"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == "invalid_mobile"
    with isolated_app.app_context():
        assert EsignIdentityBinding.query.filter_by(user_id=target_id).count() == 0


def test_admin_can_unbind_identity_and_unsent_flow_requires_binding_again(
    isolated_app, isolated_client, scenario_factory
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        admin = scenario_factory.user(
            scenario.department,
            account="test_esign_unbind_admin",
            name="虚拟解绑管理员",
            role_key="admin",
        )
        target = scenario.user
        report = _approved_report("TEST-ESIGN-UNBIND-001", scenario.department.name, target.name)
        binding = _binding(target, "13800000000")
        db.session.flush()
        flow = ReportEsignFlow(
            report_id=report.id,
            report_no=report.report_no,
            report_document_version_id=report.approved_document_version_id,
            attempt_no=1,
            status="failed",
            source_sha256="0" * 64,
        )
        db.session.add(flow)
        db.session.flush()
        signer = ReportEsignSigner(
            flow_id=flow.id,
            role_code="chief",
            role_name="主检",
            user_id=target.id,
            binding_id=binding.id,
            legal_name_snapshot=target.name,
            sign_order=1,
            status="pending",
        )
        db.session.add(signer)
        db.session.commit()
        target_id = target.id
        flow_id = flow.id
        signer_id = signer.id
        admin_account = admin.account

    response = isolated_client.delete(
        f"/api/esign/admin/bindings/{target_id}",
        headers=login_headers(isolated_client, admin_account),
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["data"]["status"] == "unbound"
    with isolated_app.app_context():
        assert EsignIdentityBinding.query.filter_by(user_id=target_id).count() == 0
        assert db.session.get(ReportEsignSigner, signer_id).binding_id is None
        assert db.session.get(ReportEsignSigner, signer_id).status == "binding_required"
        assert db.session.get(ReportEsignFlow, flow_id).status == "failed"
        assert OperationAudit.query.filter_by(
            object_type="user", object_id=str(target_id), action="esign.identity.unbind"
        ).count() == 1


def test_mobile_normalization_accepts_mainland_number_only():
    assert normalize_psn_account("138 0000-0000", "mobile") == "13800000000"


def test_all_provider_mutations_are_classified_as_external_side_effects():
    assert request_has_external_side_effect("POST", "/api/esign/flows/12/dispatch")
    assert request_has_external_side_effect("POST", "/api/esign/tasks/12/sign-url")
    assert request_has_external_side_effect("POST", "/api/esign/tasks/batch-sign-url")
    assert request_has_external_side_effect("POST", "/api/esign/callback")


def test_protected_import_can_create_explicitly_mapped_missing_signer(
    isolated_app, scenario_factory, tmp_path
):
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario()
        department_name = scenario.department.name
        assert Department.query.filter_by(name=department_name).count() == 1

    source = tmp_path / "bindings.json"
    credentials = tmp_path / "credentials.json"
    source.write_text(
        '[{"name":"虚拟新增签署人","mobile":"13800000009"}]',
        encoding="utf-8",
    )
    runner = isolated_app.test_cli_runner()
    result = runner.invoke(
        args=[
            "esign-bindings-import",
            "--source", str(source),
            "--create-missing",
            "--missing-account", "虚拟新增签署人=test_new_signer",
            "--department", department_name,
            "--credentials-out", str(credentials),
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"errors": []' in result.output
    assert credentials.exists()
    with isolated_app.app_context():
        user = User.query.filter_by(account="test_new_signer").one()
        assert user.department.name == department_name
        assert user.must_change_password is True
        assert user.home_path == "/inspection/testing/data_entry"
        assert {
            "testing.data_entry.view",
            "report.review.view",
            "report.view",
        }.issubset(set(user.permission_codes()))
        assert {
            "report.review.pass",
            "report.pdf.preview",
        }.issubset(set(user.action_codes()))
        assert all(
            step.step_code in {"data_entry", "report_review"}
            for step in user.project_steps
        )
        assert EsignIdentityBinding.query.filter_by(user_id=user.id).count() == 1
