"""Returned reports must acknowledge again, without losing immutable history."""
from datetime import datetime
import inspect
from flask import g
import pytest

from app import compliance
from app.audit import add_operation_audit
from app.extensions import db
from app.models import CapabilityEntry, CapabilityImportBatch, ComplianceAcknowledgement, Report, StdLibraryItem

pytest_plugins = ("testkit.fixtures",)


@pytest.fixture(params=[False, True], ids=["library", "manual"])
def case(isolated_app, scenario_factory, monkeypatch, request):
    scenario = scenario_factory.identity_scenario(
        permission_codes=("entrust.contract_review.view", "entrust.change.view"),
        granted_step_codes=("entrust_review",),
    )
    scenario_factory.grant_action(scenario.user, "report.contract_review.pass")
    standard = StdLibraryItem(code="TEST-ROUND-2026", name="虚拟标准",
                              auth_kind="CNAS+CMA+一单一库", use_depts=scenario.department.name)
    batch = CapabilityImportBatch(source_name="virtual", source_sha256="a" * 64, status="active")
    db.session.add_all([standard, batch]); db.session.flush()
    entry = CapabilityEntry(batch_id=batch.id, standard_item_id=standard.id,
        capability_type="检测", certificate_no="TEST", site="虚拟场所",
        object_name="虚拟对象", item_name="虚拟参数", standard_code=standard.code,
        source_file="virtual", source_page=1, source_row=1, source_sha256="b" * 64,
        active=True, mapping_status="confirmed")
    report = Report(report_no="TEST-ROUND", sample_no="TEST-SAMPLE", client="虚拟客户",
        project=scenario.project.name, department=scenario.department.name, owner=scenario.user.name,
        status="待合同评审", sample_reg_state="登记完成", sample_status="待合同评审",
        detail={"rawSample":{"seal":"CMA + CNAS", "testBases":[standard.code], "sendDate":"2026-10-22"},
                "checkInput":{"standard":standard.code,"testDate":"2026-10-22"}})
    if request.param:
        report.detail = {**report.detail, 'rawSample': {**report.detail['rawSample'],
            'manualCapabilityItems': ['虚拟库外参数'], 'manualCapabilityReason': '',
            'manualTestLocation': '虚拟实验室完整地址'}}
    db.session.add_all([entry, report]); db.session.commit()
    monkeypatch.setattr(compliance, "compute_report_checks", lambda r: ([{"group":"仪器有效性校验","status":"通过"}],False,""))
    return isolated_app, scenario.user, report


def payload(report, stage):
    result = compliance.build_compliance_preflight(report, stage)
    assert result["required"] and result["ready"] and not result["issues"]
    return {"preflightVersion":result["preflightVersion"], "finalSeal":result["finalSeal"], "acknowledgedIssueIds":[]}


def acknowledge(report, user, stage):
    body = payload(report, stage)
    compliance.validate_and_record_acknowledgement(report, user, stage, body)
    db.session.commit()
    return body


@pytest.mark.parametrize("stage,action", [
    ("contract_review", "report.entrust_change.complete"),
    ("contract_review", "report.contract_review.undo"),
    ("contract_review", "sample.register.complete"),
    ("report_review", "report.test_change.complete"),
    ("report_review", "report.review.undo"),
    ("report_review", "report.data_entry.complete"),
    ("report_approval", "report.approval.undo"),
    ("report_approval", "report.review.pass"),
])
def test_reentry_allows_new_ack_and_keeps_each_round_unique(case, stage, action):
    app, user, report = case
    old = acknowledge(report, user, stage)
    first = ComplianceAcknowledgement.query.one()
    old_history = (first.id, first.preflight_version, first.created_at, first.actor_id)
    with pytest.raises(ValueError, match="不能重复提交"):
        compliance.validate_and_record_acknowledgement(report, user, stage, old)
    for _ in range(2):
        # Even multiple re-entries on the same day must be distinct.
        audit = add_operation_audit(action, "report", report.report_no, actor=user)
        audit.created_at = datetime(2026, 10, 22, 1, 0, 0)
        db.session.commit()
        with pytest.raises(ValueError, match="不能重复提交"):
            compliance.validate_and_record_acknowledgement(report, user, stage, old)
        body = acknowledge(report, user, stage)
        assert body["preflightVersion"] != old["preflightVersion"]
        with pytest.raises(ValueError, match="不能重复提交"):
            compliance.validate_and_record_acknowledgement(report, user, stage, body)
        old = body
    assert ComplianceAcknowledgement.query.count() == 3
    assert (first.id, first.preflight_version, first.created_at, first.actor_id) == old_history


def test_unrelated_failed_and_other_report_audits_do_not_open_new_round(case):
    _, user, report = case
    old = acknowledge(report, user, "contract_review")
    add_operation_audit("report.entrust_change.complete", "report", "OTHER", actor=user)
    add_operation_audit("report.entrust_change.complete", "report", report.report_no, success=False, actor=user)
    add_operation_audit("report.entrust_change.save", "report", report.report_no, actor=user)
    add_operation_audit("report.contract_review.pass", "report", report.report_no, actor=user)
    db.session.commit()
    assert payload(report, "contract_review") == old
    with pytest.raises(ValueError, match="不能重复提交"):
        compliance.validate_and_record_acknowledgement(report, user, "contract_review", old)


def test_reentry_stale_preflight_and_changed_inputs_remain_blocked(case):
    _, user, report = case
    old = payload(report, "contract_review")
    add_operation_audit("report.entrust_change.complete", "report", report.report_no, actor=user)
    db.session.commit()
    with pytest.raises(ValueError, match="已变化"):
        compliance.validate_and_record_acknowledgement(report, user, "contract_review", old)
    fresh = payload(report, "contract_review")
    report.detail = {**report.detail, "rawSample":{**report.detail["rawSample"], "sampleName":"changed"}}
    with pytest.raises(ValueError, match="已变化"):
        compliance.validate_and_record_acknowledgement(report, user, "contract_review", fresh)
    assert ComplianceAcknowledgement.query.count() == 0


def test_contract_review_route_passes_after_return_and_resubmit(case, monkeypatch):
    app, user, report = case
    from app.blueprints import reports
    from app import workflow_hooks as hooks
    from app.applications.report_lifecycle.commands import apply_return_plan
    # Isolate unrelated finance, numbering and date validation. Keep the real
    # review/return/resubmit handlers, row state, authorization and ack storage.
    monkeypatch.setattr(hooks, "blocker", lambda *args: None)
    monkeypatch.setattr(hooks, "capture", lambda *args: None)
    monkeypatch.setattr(reports, "_sample_configuration", lambda *a, **k: {"ready":True})
    monkeypatch.setattr(reports, "sample_party_error", lambda *a, **k: None)
    monkeypatch.setattr(reports, "sample_pricing_error", lambda *a, **k: None)
    monkeypatch.setattr(reports, "sample_price_error", lambda *a, **k: None)
    monkeypatch.setattr(reports, "_validate_sample_detail_dates", lambda u, d, e, **k: (d,None))
    monkeypatch.setattr(reports, "_apply_report_prefix_change", lambda *a: None)
    def pass_review():
        body = {**payload(report,"contract_review"),"action":"pass","cma":True,"cnas":True,
                "items":{key:True for key,_ in reports.CR_ITEMS}}
        with app.test_request_context(json=body):
            g.current_user=user
            response = inspect.unwrap(reports.contract_review)(report.report_no)
            return (response[0] if isinstance(response, tuple) else response).get_json()
    assert pass_review()["code"] == 0
    assert report.status == "待样品入库"
    for _ in range(2):
        report.status="检测录入中"; report.sample_status="已领取"
        apply_return_plan(report,user,"testing.data_entry.return","虚拟退回测试")
        add_operation_audit("testing.data_entry.return","report",report.report_no,actor=user)
        db.session.commit()
        with app.test_request_context(json={"editVersion": report.edit_version}):
            g.current_user=user
            response=inspect.unwrap(reports.change_resubmit)(report.report_no)
            result=(response[0] if isinstance(response,tuple) else response).get_json()
            assert result["code"] == 0, result
        assert report.status == "待合同评审"
        result=pass_review()
        assert result["code"] == 0, result
        assert report.status == "检测录入中" and report.sample_status == "已领取"
    assert ComplianceAcknowledgement.query.count() == 3
