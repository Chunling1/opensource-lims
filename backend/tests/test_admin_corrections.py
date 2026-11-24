"""Only explicit business correctors bypass ordinary edit scope; no external IO."""
from testkit.forms import loaded_form
from copy import deepcopy

import pytest

from app.extensions import db
from app.models import Agreement, Entrust, Report, OperationAudit, StdLibraryItem
from app.security import issue_token
from app.admin_corrections.source import SourceCorrection, effective

pytest_plugins = ("testkit.fixtures",)


@pytest.fixture()
def workspace(isolated_app, scenario_factory, monkeypatch):
    # This suite verifies saved values and audit; PDF workers must not outlive its temporary DB.
    monkeypatch.setattr("app.sample_preview_warmup.schedule_after_save", lambda report: None)
    f = scenario_factory
    dept = f.department(name="测试本部门")
    admin = f.user(dept, account="admin-qa", role_key="admin")
    tang = f.user(dept, account="qa-admin2", role_key="admin")
    ordinary = f.user(dept, account="ordinary", name="普通测试员", role_key="user")
    agreement = Agreement(agreement_no="QA-001", client="原甲方", status="已登记",
                          project_name="跨部门合同", department="其他部门", erp_type="不回传外部ERP合同",
                          info={"fromErp": ""})
    entrust = Entrust(entrust_no="QA-WT", contract_no="QA-001", client="原甲方",
                      department="其他部门", status="委托完成", info={"contractPartyA": "原甲方"})
    report = Report(report_no="QA-R", sample_no="QA-S", entrust_no="QA-WT", client="原甲方",
                    department="其他部门", status="已发放", sample_reg_state="登记完成",
                    detail={"rawSample": {"testLocation": "旧地点"}, "checkInput": {"result": "旧值"}})
    standard = StdLibraryItem(code="TEST 1", name="原标准", use_depts="其他部门")
    db.session.add_all([agreement, entrust, report, standard])
    db.session.commit()
    import app.workflow_hooks as hooks
    original = {"code": "QA-C", "name": "原客户", "enabled": "1", "addr": "原地址"}
    def customer_search(term="", page=1, size=20, **kwargs):
        rows = effective("customers", [dict(original), {"code": "QA-CA", "name": "库内目标甲方", "enabled": "1"}], "code")
        rows = [r for r in rows if not term or term in r["code"] or term in r["name"]]
        return dict(rows=rows, total=len(rows), page=page, size=size)
    monkeypatch.setattr(hooks, "empty_customer_search", customer_search)
    return isolated_app.test_client(), [admin, tang, ordinary], [agreement, entrust, report, standard], original


def headers(user):
    return {"Authorization": "Bearer " + issue_token(user)}


def url(kind, row):
    return f"/api/admin-corrections/{kind}/{row.id}"


def save(client, user, path, changes, **extra):
    record = client.get(path, headers=headers(user)).get_json()["data"]
    return client.put(path, headers=headers(user), json=dict(
        revision=record["revision"], changes=changes, reason="本地验收修订", confirmed=True, **extra))


@pytest.mark.parametrize("actor_index", [0, 1])
@pytest.mark.parametrize("kind,index,changes", [
    ("entrusts", 1, {"client": "修订单位", "info": {"contractPartyA": "修订甲方"}}),
    ("reports", 2, {"detail": {"rawSample": {"testLocation": "新地点"}, "checkInput": {"result": "新值"}}}),
    ("standard-library", 3, {"name": "修订标准", "use_depts": "测试本部门"}),
])
def test_privileged_cross_department_locked_records_can_be_corrected(workspace, actor_index, kind, index, changes):
    client, actors, records, _ = workspace
    user, row = actors[actor_index], records[index]
    old_status = getattr(row, "status", None)
    result = save(client, user, url(kind, row), changes)
    assert result.status_code == 200, result.get_json()
    assert "已保存管理员修订" in result.get_json()["data"]["message"]
    db.session.refresh(row)
    for key, value in changes.items():
        if isinstance(value, dict):
            assert all(getattr(row, key)[k] == v for k, v in value.items())
        else:
            assert getattr(row, key) == value
    assert getattr(row, "status", None) == old_status
    audit = OperationAudit.query.filter_by(action="admin.business.correct").one()
    assert audit.account == user.account
    assert audit.before_data != audit.after_data
    assert "管理员权限" in audit.message


def test_name_or_forged_payload_does_not_grant_privilege(workspace):
    client, actors, records, _ = workspace
    user = actors[2]
    assert user.name == "普通测试员"
    for path in ["/api/admin-corrections/catalog", "/api/admin-corrections/entrusts", url("entrusts", records[1])]:
        assert client.get(path, headers=headers(user)).status_code == 403
    response = client.put(url("entrusts", records[1]), headers=headers(user),
                          json={"role": "admin", "account": "qa-admin2", "confirmed": True, "changes": {"client": "伪造"}})
    assert response.status_code == 403
    assert records[1].client == "原甲方"
    assert OperationAudit.query.count() == 0


def test_confirmation_revision_and_readonly_are_enforced(workspace):
    client, actors, records, _ = workspace
    user, row = actors[0], records[1]
    path = url("entrusts", row)
    original = client.get(path, headers=headers(user)).get_json()["data"]
    body = dict(revision=original["revision"], changes={"client": "变更"}, reason="测试原因")
    assert client.put(path, headers=headers(user), json=body).status_code == 409
    body["confirmed"] = True
    row.client = "另一人修改"
    db.session.commit()
    assert client.put(path, headers=headers(user), json=body).status_code == 409
    body["revision"] = client.get(path, headers=headers(user)).get_json()["data"]["revision"]
    client.application.config["APP_BUSINESS_READ_ONLY"] = True
    assert client.put(path, headers=headers(user), json=body).status_code == 423
    assert row.client == "另一人修改"
    assert OperationAudit.query.count() == 0


def test_rejects_unregistered_modules_and_storage_identity_changes(workspace):
    client, actors, records, _ = workspace
    user = actors[0]
    assert client.get("/api/admin-corrections/users", headers=headers(user)).status_code == 404
    assert save(client, user, url("entrusts", records[1]), {"id": 999}).status_code == 400
    assert OperationAudit.query.count() == 0


def test_catalog_and_paged_search_are_accessible_to_explicit_accounts(workspace):
    client, actors, _, _ = workspace
    for user in actors[:2]:
        result = client.get("/api/admin-corrections/catalog", headers=headers(user)).get_json()["data"]
        for module in result["modules"]:
            response = client.get(f"/api/admin-corrections/{module['key']}?keyword=不存在&page=1", headers=headers(user))
            assert response.status_code == 200, (module, response.get_json())
            assert response.get_json()["data"]["rows"] == []
        profile = client.get("/api/auth/profile", headers=headers(user)).get_json()["data"]
        assert profile["features"]["businessDataCorrection"] is True
    assert client.get("/api/auth/profile", headers=headers(actors[2])).get_json()["data"]["features"]["businessDataCorrection"] is False


@pytest.mark.parametrize("detail", [[], {"rawSample": []}, {"entrustSnapshot": "错误"}, {"summary": [{} , {"fields": [["错误"]]}]}])
def test_invalid_detail_shapes_rollback_without_audit(workspace, detail):
    client, actors, rows, _ = workspace
    report = rows[2]
    before = deepcopy(report.detail)
    response = save(client, actors[0], url("reports", report), {"detail": detail})
    assert response.status_code == 400
    assert report.detail == before
    assert OperationAudit.query.count() == 0


def test_inconsistent_aliases_are_rejected_atomically(workspace):
    client, actors, rows, _ = workspace
    response = save(client, actors[0], url("entrusts", rows[1]), {"client": "甲", "info": {"client": "乙"}})
    assert response.status_code == 400
    assert rows[1].client == "原甲方"
    assert OperationAudit.query.count() == 0




def test_entrusting_customer_accepts_manual_directory_and_clear(workspace):
    client, actors, rows, source = workspace
    rows[0].erp_type = "标准合同"
    db.session.commit()
    path = url("entrusts", rows[1])
    assert save(client, actors[1], path, {"client": "随意手写"}).status_code == 200
    assert save(client, actors[1], path, {"client": source["name"]}).status_code == 200
    assert save(client, actors[1], path, {"client": ""}).status_code == 200


def test_number_change_updates_references_and_preserves_audit_evidence(workspace):
    client, actors, rows, _ = workspace
    entrust, report = rows[1:3]
    report.detail = dict(report.detail, entrustSnapshot={"entrustNo": entrust.entrust_no, "sourceEntrustNo": entrust.entrust_no}, note=entrust.entrust_no)
    db.session.commit()
    response = save(client, actors[1], url("entrusts", entrust), {"entrust_no": "WT-2026-0199"})
    assert response.status_code == 200, response.get_json()
    db.session.refresh(report)
    assert report.entrust_no == report.detail["entrustSnapshot"]["entrustNo"] == "WT-2026-0199"
    assert report.detail["note"] == "QA-WT"  # prose/history is not blanket-replaced
    audit = OperationAudit.query.filter_by(action="admin.business.correct").one()
    assert audit.before_data["entrust_no"] == "QA-WT"
    assert audit.after_data["entrust_no"] == "WT-2026-0199"


def test_sample_number_updates_derived_report_number_and_rolls_back_collisions(workspace):
    client, actors, rows, _ = workspace
    report = rows[2]
    report.report_no, report.sample_no = "LAB-2026VAV-0013", "2026VAV-0013"
    report.detail = dict(report.detail, rawSample={"sampleNo": report.sample_no, "reportNo": report.report_no})
    child = Report(report_no=report.report_no + "BC", main_report_no=report.report_no, sample_no=report.sample_no, detail={})
    db.session.add(child); db.session.commit()
    response = save(client, actors[1], url("reports", report), {"sample_no": "2026VAV-0014"})
    assert response.status_code == 200, response.get_json()
    db.session.refresh(report); db.session.refresh(child)
    assert report.report_no == "LAB-2026VAV-0014"
    assert child.report_no == "LAB-2026VAV-0014BC" and child.main_report_no == report.report_no
    assert report.detail["rawSample"]["reportNo"] == report.report_no
    collision = Report(report_no="LAB-2026VAV-0015", sample_no="different")
    db.session.add(collision); db.session.commit()
    assert save(client, actors[1], url("reports", report), {"sample_no": "2026VAV-0015"}).status_code == 400
    assert report.sample_no == "2026VAV-0014"


def test_existing_standard_form_preserves_domain_validation_and_audit(workspace):
    client, actors, rows, _ = workspace
    user, std = actors[1], rows[3]
    record = client.get(url("standard-library", std), headers=headers(user)).get_json()["data"]
    body = {"name": "按原表单修订标准", "adminCorrection": {"revision": record["revision"], "confirmed": True, "reason": "修订标准名称"}}
    result = client.put(f"/api/quality/std-library/{std.id}", headers=headers(user), json=body)
    assert result.status_code == 200 and result.get_json()["code"] == 0, result.get_json()
    assert std.name == body["name"]
    assert OperationAudit.query.filter_by(action="admin.business.correct").count() == 1
    assert client.put(f"/api/quality/std-library/{std.id}", headers=headers(user), json=body).status_code == 409
    assert client.put(f"/api/quality/std-library/{std.id}", headers=headers(actors[2]), json=body).status_code == 403


def test_corrector_can_open_original_query_detail_without_review_privilege(workspace):
    from app.applications.report_lifecycle.queries import get_authorized_report_for_view
    _, actors, rows, _ = workspace
    report, _, error = get_authorized_report_for_view(actors[1], rows[2].report_no, "query")
    assert report == rows[2] and not error
    _, _, denied = get_authorized_report_for_view(actors[2], rows[2].report_no, "query")
    assert denied




def test_existing_testing_form_corrects_locked_record_without_advancing_workflow(workspace):
    client, actors, rows, _ = workspace
    user, report = actors[1], rows[2]
    record = client.get(url("reports", report), headers=headers(user)).get_json()["data"]
    result = client.put(f"/api/reports/{report.report_no}/testinfo", headers=headers(user), json=loaded_form(client, f"/api/reports/{report.report_no}/testinfo", {
        "result": "修订后的实测结果", "remark": "本地合成验收", "adminCorrection": {
            "revision": record["revision"], "confirmed": True, "reason": "核对实测结果"}}))
    assert result.status_code == 200 and result.get_json()["code"] == 0, result.get_json()
    assert report.detail["checkInput"]["result"] == "修订后的实测结果"
    assert report.status == "已发放"
    assert OperationAudit.query.filter_by(action="admin.business.correct").count() == 1



def test_report_number_only_correction_synchronizes_linked_derivative(workspace):
    client, actors, rows, _ = workspace
    report = rows[2]
    child = Report(report_no="QA-RBC", main_report_no="QA-R", sample_no=report.sample_no)
    db.session.add(child); db.session.commit()
    result = save(client, actors[1], url("reports", report), {"report_no": "QA-R-NEW"})
    assert result.status_code == 200, result.get_json()
    db.session.refresh(child)
    assert child.report_no == "QA-R-NEWBC" and child.main_report_no == "QA-R-NEW"
    assert result.get_json()["data"]["reportNo"] == "QA-R-NEW"
    assert OperationAudit.query.filter_by(action="admin.business.correct").one().after_data["report_no"] == "QA-R-NEW"


def test_original_personnel_form_synchronizes_linked_account_name(workspace):
    from app.models import Personnel
    client, actors, _, _ = workspace
    person = Personnel(code=actors[2].account, name=actors[2].name, dept="其他部门")
    db.session.add(person); db.session.commit()
    record = client.get(url("personnel", person), headers=headers(actors[1])).get_json()["data"]
    response = client.put(f"/api/quality/personnel/{person.id}", headers=headers(actors[1]), json={
        "name": "同步后的测试姓名", "adminCorrection": {"revision": record["revision"], "confirmed": True, "reason": "核对人员姓名"}})
    assert response.status_code == 200 and response.get_json()["code"] == 0, response.get_json()
    db.session.refresh(actors[2])
    assert person.name == actors[2].name == "同步后的测试姓名"
    assert actors[2].role_key == "user"


def test_audit_failure_rolls_back_number_and_all_references(workspace, monkeypatch):
    from app.admin_corrections import web
    client, actors, rows, _ = workspace
    def broken(*a, **kw): raise RuntimeError("合成审计失败")
    monkeypatch.setattr(web, "add_operation_audit", broken)
    result = save(client, actors[1], url("entrusts", rows[1]), {"entrust_no": "WT-2026-0888"})
    assert result.status_code == 503
    db.session.refresh(rows[1]); db.session.refresh(rows[2])
    assert rows[1].entrust_no == rows[2].entrust_no == "QA-WT"
    assert OperationAudit.query.count() == 0


@pytest.mark.parametrize("actor_index", [0, 1])
def test_admin_financial_edit_keeps_local_balance_and_audit(workspace, actor_index):
    from test_sample_pricing import detail
    client, actors, records, _ = workspace
    sample = records[2]
    sample.detail = detail("100", ("100",))
    db.session.commit()
    result = save(client, actors[actor_index], url("reports", sample),
                  {"detail": detail("10000", ("9999",))})
    assert result.status_code == 400 and "差额 1.00" in result.get_json()["message"]
    assert OperationAudit.query.count() == 0
    db.session.refresh(sample)
    assert sample.detail["rawSample"]["stdPrice"] == "100"
    result = save(client, actors[actor_index], url("reports", sample),
                  {"detail": detail("10000", ("4000", "6000"))})
    assert result.status_code == 200, result.get_json()
    db.session.expire_all()
    assert sample.detail["rawSample"]["stdPrice"] == "10000"
    assert OperationAudit.query.filter_by(action="admin.business.correct").count() == 1









def test_normal_admin_testinfo_save_does_not_create_correction_audit(workspace, scenario_factory):
    client, actors, rows, _ = workspace
    report = rows[2]
    project, _ = scenario_factory.project(actors[0].department)
    report.project = project.name
    report.department = actors[0].department.name
    report.status = "检测录入中"
    report.sample_status = "已领取"
    db.session.commit()
    result = client.put(f"/api/reports/{report.report_no}/testinfo",
                        headers=headers(actors[0]), json=loaded_form(client, f"/api/reports/{report.report_no}/testinfo", {"result": "普通录入草稿"}))
    assert result.get_json()["code"] == 0, result.get_json()
    assert report.detail["checkInput"]["result"] == "普通录入草稿"
    assert report.status == "检测录入中"
    assert OperationAudit.query.filter_by(action="admin.business.correct").count() == 0


def test_privileged_testinfo_without_explicit_correction_keeps_state_lock(workspace, scenario_factory):
    client, actors, rows, _ = workspace
    report = rows[2]
    project, _ = scenario_factory.project(actors[0].department)
    report.project = project.name
    report.department = actors[0].department.name
    report.sample_status = "已领取"
    db.session.commit()
    before = deepcopy(report.detail)
    result = client.put(f"/api/reports/{report.report_no}/testinfo",
                        headers=headers(actors[0]), json=loaded_form(client, f"/api/reports/{report.report_no}/testinfo", {"result": "不可隐式修订"}))
    assert result.get_json()["code"] != 0
    assert "不在检测数据录入节点" in result.get_json()["message"]
    assert report.detail == before
    assert report.status == "已发放"
    assert OperationAudit.query.filter_by(action="admin.business.correct").count() == 0
