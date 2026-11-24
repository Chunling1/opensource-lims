"""Real organization, selector and save endpoints with isolated identities/data."""
import pytest
from app.extensions import db
from app.models import EquipmentItem, Report, OperationAudit
from app.security import issue_token
from app.edit_concurrency import test_form_version as form_version
from app.equipment_authorization import granted_department_ids

pytest_plugins = ("testkit.fixtures",)


def headers(user):
    return {"Authorization": "Bearer " + issue_token(user)}


@pytest.fixture
def case(isolated_client, scenario_factory, monkeypatch):
    monkeypatch.setattr("app.preview_cache.schedule_after_save", lambda *args: None)
    f = scenario_factory
    identity = f.identity_scenario(permission_codes=("testing.data_entry.view",), granted_step_codes=("data_entry",))
    own, user = identity.department, identity.user
    other = f.department(name="借用仪器部门")
    child = f.department(name="借用部门下属部门", parent=other)
    admin = f.user(own, role_key="admin")
    rows = [EquipmentItem(archive_no="SAME", name=f"仪器{i}", dept=dept.name, status="可用", period="长期")
            for i, dept in enumerate([own, other, child])]
    report = Report(report_no="QA-EQUIPMENT-GRANTS", department=own.name, project=identity.project.name,
                    owner=user.name, status="检测录入中", sample_status="已领取",
                    sample_pickup={"pickupTime": "2026-09-30"}, detail={})
    hidden = Report(report_no="QA-HIDDEN", department=other.name, project="", detail={})
    db.session.add_all([*rows, report, hidden]); db.session.commit()
    url = f"/api/admin/departments/{own.id}/members/{user.id}/authorizations"
    def grant(value, actor=admin):
        payload = isolated_client.get(url, headers=headers(admin)).get_json()["data"]
        return isolated_client.put(url, headers=headers(actor), json={
            "permissionCodes": payload["selectedPermissionCodes"], "projectStepIds": payload["selectedProjectStepIds"],
            "equipmentDepartmentIds": value,
        }).get_json()
    def options(actor=user, report_no=report.report_no):
        return isolated_client.get(f"/api/reports/{report_no}/equipment-options", headers=headers(actor)).get_json()
    def save(ids, complete=False):
        return isolated_client.put(f"/api/reports/{report.report_no}/testinfo", headers=headers(user), json={
            "testEditVersion": form_version(report), "equipmentIds": ids, "validateForCompletion": complete,
            "testIntervals": [{"start": "2026-10-01", "end": "2026-10-02"}], "resultStatus": "不判定",
        }).get_json()
    return isolated_client, user, admin, own, other, rows, report, url, grant, options, save


def test_grant_selection_save_revoke_and_history(case):
    client, user, admin, own, other, rows, report, url, grant, options, save = case
    scope_before = user.data_scope()
    assert [row["id"] for row in options()["data"]["rows"]] == [rows[0].id]
    assert save([rows[1].id])["code"] == 403
    assert grant([other.id])["code"] == 0
    assert user.data_scope() == scope_before
    assert {row["id"] for row in options()["data"]["rows"]} == {rows[0].id, rows[1].id}
    assert "buyPrice" not in options()["data"]["rows"][0]
    assert save([rows[1].id])["code"] == 0
    assert report.detail["checkInput"]["equipmentIds"] == [rows[1].id]
    assert grant([])["code"] == 0
    assert save([rows[1].id])["code"] == 0  # Persisted report is not destroyed by later revocation.
    assert rows[1].id in {row["id"] for row in options()["data"]["rows"]}
    assert save([])["code"] == 0
    assert rows[1].id not in {row["id"] for row in options()["data"]["rows"]}
    assert save([rows[1].id])["code"] == 403
    assert OperationAudit.query.filter_by(action="organization.member.equipment_authorize").count() == 2


@pytest.mark.parametrize("value", [None, "1", [True], ["1"], [-1], [999999]])
def test_invalid_grants_are_atomic(case, value):
    *_, grant, options, save = case
    user, other = case[1], case[4]
    assert grant([other.id])["code"] == 0
    assert grant(value)["code"] == 1
    assert granted_department_ids(user) == [other.id]


def test_grants_cannot_expand_data_ledger_or_child_scope(case):
    client, user, admin, own, other, rows, report, url, grant, options, save = case
    assert grant([other.id], actor=user)["code"] == 403
    assert grant([other.id])["code"] == 0
    assert options(report_no="QA-HIDDEN")["code"] == 403
    assert rows[2].id not in {row["id"] for row in options()["data"]["rows"]}
    assert save([rows[2].id])["code"] == 403
    assert {row["id"] for row in client.get('/api/quality/equipment?full=1', headers=headers(user)).get_json()["data"]["rows"]} == {rows[0].id}
    assert client.put(f'/api/quality/equipment/{rows[1].id}', headers=headers(user), json={"name":"bad"}).get_json()["code"] == 403
    assert rows[1].name == "仪器1"


def test_omitted_grants_preserved_and_admin_global_access(case):
    client, user, admin, own, other, rows, report, url, grant, options, save = case
    assert grant([other.id, other.id])["code"] == 0
    payload = client.get(url, headers=headers(admin)).get_json()["data"]
    assert payload["equipmentDepartmentIds"] == [other.id]
    result = client.put(url, headers=headers(admin), json={"permissionCodes": payload["selectedPermissionCodes"],
                        "projectStepIds": payload["selectedProjectStepIds"]}).get_json()
    assert result["code"] == 0
    assert result["data"]["equipmentDepartmentIds"] == [other.id]
    assert {row["id"] for row in options(admin)["data"]["rows"]} == {row.id for row in rows}


def test_grant_does_not_bypass_validity(case):
    *_, grant, options, save = case
    other, rows = case[4], case[5]
    assert grant([other.id])["code"] == 0
    rows[1].status = "维修中"; db.session.commit()
    result = save([rows[1].id], complete=True)
    assert result["code"] != 0 and "不覆盖全部试验区间" in result["message"]


def test_completion_and_review_preserve_authorized_use(case, scenario_factory):
    from app.checks import compute_report_checks
    from app.models import StdLibraryItem
    client, user, admin, own, other, rows, report, url, grant, options, save = case
    standard = StdLibraryItem(code="QA-STANDARD", name="虚拟标准", use_depts=own.name)
    db.session.add(standard); db.session.commit()
    assert grant([other.id])["code"] == 0
    result = client.put(f"/api/reports/{report.report_no}/testinfo", headers=headers(user), json={
        "testEditVersion": form_version(report), "equipmentIds": [rows[1].id], "validateForCompletion": True,
        "standards": [standard.code], "resultStatus": "不判定",
        "testIntervals": [{"start": "2026-10-01", "end": "2026-10-02"}],
    }).get_json()
    assert result["code"] == 0, result
    assert grant([])["code"] == 0
    reviewer = scenario_factory.user(own, permissions=["report.review.view"])
    db.session.commit()
    assert rows[1].id in {row["id"] for row in options(reviewer)["data"]["rows"]}
    assert compute_report_checks(report)[0][1]["status"] == "通过"


def test_data_all_is_not_equipment_all_and_transfer_uses_new_home(case, scenario_factory):
    client, user, admin, own, other, rows, report, url, grant, options, save = case
    user.data_scope_type = "all"; db.session.commit()
    assert {row["id"] for row in options()["data"]["rows"]} == {rows[0].id}
    user.department = other; db.session.commit()
    assert {row["id"] for row in options()["data"]["rows"]} == {rows[1].id}


def test_deleting_department_cleans_only_equipment_grant(case):
    client, user, admin, own, other, rows, report, url, grant, options, save = case
    # Leaf department with no members can be removed without dangling FK grants.
    from app.models import Department
    leaf = Department.query.filter_by(parent_id=other.id).one()
    assert grant([leaf.id])["code"] == 0
    result = client.delete(f"/api/admin/departments/{leaf.id}", headers=headers(admin)).get_json()
    assert result["code"] == 0
    assert granted_department_ids(user) == []


def test_additive_migration_preserves_existing_data(isolated_app, scenario_factory):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.models import user_equipment_departments
    own = scenario_factory.department()
    db.session.commit()
    user_equipment_departments.drop(db.engine)
    path = Path(__file__).parents[1] / 'migrations/versions/a182e0112026_equipment_department_grants.py'
    spec = importlib.util.spec_from_file_location('equipment_migration', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    with db.engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
    assert db.session.get(type(own), own.id).name == own.name
    assert list(db.session.execute(user_equipment_departments.select())) == []
