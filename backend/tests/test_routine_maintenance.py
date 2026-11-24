"""Routine maintenance retains domain validation/audit without correction proof."""
import pytest
from app.extensions import db
from app.models import EquipmentItem, Standard, Personnel, OperationAudit
from test_admin_corrections import workspace, headers
pytest_plugins = ("testkit.fixtures",)

@pytest.mark.parametrize("actor", [0, 1])
@pytest.mark.parametrize("kind", ["equipment", "standards", "std-library", "personnel", "projects"])
def test_routine_update_without_correction_proof(workspace, scenario_factory, actor, kind):
    client, users, rows, _ = workspace
    user = users[actor]
    if kind == "equipment":
        row = EquipmentItem(archive_no="QA-ROUTINE", name="原仪器", dept=user.department.name)
    elif kind == "standards":
        row = Standard(code="QA-STD", name="原标准")
    elif kind == "personnel":
        row = Personnel(code="QA-PERSON", name="原人员", dept=user.department.name)
    elif kind == "projects":
        row, _ = scenario_factory.project(user.department, code="QA-PRJ", name="原项目")
    else:
        row = rows[3]
    db.session.add(row); db.session.commit()
    payload = {"name": "日常维护名称"}
    if kind == "equipment":
        payload["editVersion"] = row.edit_version
    if kind == "projects":
        payload.update(code=row.code, departmentId=user.department_id)
    path = f"/api/admin/project-masters/{row.id}" if kind == "projects" else f"/api/quality/{kind}/{row.id}"
    result = client.put(path, headers=headers(user), json=payload)
    assert result.get_json()["code"] == 0, result.get_json()
    assert row.name == payload["name"]
    assert OperationAudit.query.filter_by(action="admin.business.correct").count() == 0
    audit = OperationAudit.query.filter(OperationAudit.action.like("%.update")).all()
    assert audit and any(a.before_data != a.after_data for a in audit)
    denied = client.put(path, headers=headers(users[2]), json={**payload, "name": "越权修改"})
    assert denied.status_code == 403 or denied.get_json()["code"] == 403
    assert row.name == payload["name"]
    client.application.config["APP_BUSINESS_READ_ONLY"] = True
    denied = client.put(path, headers=headers(user), json={**payload, "name": "只读修改"})
    assert denied.status_code == 423 or denied.get_json()["code"] != 0
    assert row.name == payload["name"]

