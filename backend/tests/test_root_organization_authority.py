"""Company-root membership grants full authority without changing stored roles."""
import pytest
from app.extensions import db
from app.models import Agreement, Project
from app.security import issue_token
from app.catalog import all_permission_codes, all_action_codes
from app.authorization_scope import department_projects, user_has_project_step, user_has_org_wide_scope
from app.admin_corrections import can_correct_business_data

pytest_plugins = ("testkit.fixtures",)


@pytest.fixture()
def actors(isolated_client, scenario_factory):
    f = scenario_factory
    root = f.department(code="ROOT", name="示例检测科技有限公司")
    lab = f.department(name="检测甲部", parent=root)
    other = f.department(name="检测乙部", parent=root)
    staff = f.user(root, data_scope_type="department_project")
    ordinary = f.user(lab, permissions=["entrust.registration.view"])
    admin = f.user(lab, role_key="admin")
    project, steps = f.project(other)
    db.session.commit()
    return isolated_client, f, root, lab, other, staff, ordinary, admin, project, steps


def headers(user):
    return {"Authorization": "Bearer " + issue_token(user)}


def test_root_effective_permissions_cover_functions_actions_projects_and_data(actors):
    client, f, root, lab, other, staff, ordinary, admin, project, steps = actors
    from app.platform.identity.access import has_function_permission, has_action_permission, has_org_wide_business_scope
    assert set(all_permission_codes()).issubset(staff.permission_codes())
    assert set(all_action_codes()).issubset(staff.action_codes())
    assert has_function_permission(staff, "system.user.view")
    assert has_action_permission(staff, "report.contract_review.pass")
    assert can_correct_business_data(staff)
    assert user_has_org_wide_scope(staff) and has_org_wide_business_scope(staff)
    assert staff.data_scope()["scopeType"] == "all"
    assert staff.data_department_ids() == {root.id, lab.id, other.id}
    assert staff.member_visible_department_ids() == {root.id, lab.id, other.id}
    assert project.id in {p.id for p in department_projects(staff)}
    assert {s.id for s in steps}.issubset(staff.project_step_ids())
    for step in steps:
        assert user_has_project_step(staff, project, step.step_code)
    assert not user_has_project_step(staff, project, "not-a-real-step")
    assert staff.role_key == "operator" and staff.permissions == [] and staff.project_steps == []
    response = client.get("/api/auth/profile", headers=headers(staff)).get_json()["data"]
    assert response["dataScope"]["scopeType"] == "all"
    assert response["features"]["businessDataCorrection"]
    assert response["features"]["fullPlatformAuthority"]
    assert set(all_permission_codes()).issubset(response["permissions"])
    assert {s.step_name for s in steps}.issubset({p["step"] for p in response["projectPermissions"]})
    # New project codes inherit authority on demand, without adding stored grants.
    new_project, new_steps = f.project(lab)
    db.session.commit()
    assert new_project.id in {p.id for p in department_projects(staff)}
    assert user_has_project_step(staff, new_project, "report_approval")
    new_project.active = False
    db.session.commit()
    assert new_project.id not in {p.id for p in department_projects(staff)}
    assert user_has_project_step(staff, new_project, "report_approval")


def test_subordinate_department_and_matching_display_name_do_not_grant_full_authority(actors):
    client, f, root, lab, other, staff, ordinary, admin, project, steps = actors
    ordinary.name = "管理员"
    ordinary.data_scope_type = "all"
    db.session.commit()
    assert not can_correct_business_data(ordinary)
    assert "system.user.view" not in ordinary.permission_codes()
    assert not user_has_project_step(ordinary, project, "report_approval")


def test_root_departure_removes_inherited_authority(actors):
    client, f, root, lab, other, staff, ordinary, admin, project, steps = actors
    from app.platform.identity.department_sync import synchronize_user_department
    token = headers(staff)
    assert can_correct_business_data(staff)
    staff.department = lab
    synchronize_user_department(staff, root, lab, actor=admin)
    db.session.commit()
    assert not can_correct_business_data(staff)
    assert not user_has_org_wide_scope(staff)
    assert "system.user.view" not in staff.permission_codes()
    assert not user_has_project_step(staff, project, "report_approval")
    payload = client.get("/api/auth/profile", headers=token).get_json()["data"]
    assert not payload["features"]["businessDataCorrection"]
    assert not payload["features"]["fullPlatformAuthority"]
    assert payload["dataScope"]["scopeType"] != "all"


def test_disabled_root_cannot_use_full_authority(actors):
    client, f, root, lab, other, staff, ordinary, admin, project, steps = actors
    token = headers(staff)
    staff.enabled = False
    db.session.commit()
    assert not can_correct_business_data(staff)
    assert not user_has_project_step(staff, project, "report_approval")
    assert "system.user.view" not in staff.permission_codes()
    response = client.get("/api/auth/profile", headers=token)
    assert response.status_code == 401 or response.get_json()["code"] != 0


@pytest.mark.parametrize("path", [
    "/api/business-supplement/subprojects?all=1",
    "/api/technical-subprojects?all=1",
    "/api/technical-subprojects/options",
])
def test_admin_only_configuration_reads_accept_root_but_reject_ordinary(actors, path):
    client, f, root, lab, other, staff, ordinary, admin, project, steps = actors
    response = client.get(path, headers=headers(staff))
    assert response.status_code == 200 and response.get_json()["code"] == 0, response.get_json()
    response = client.get(path, headers=headers(ordinary))
    assert response.status_code == 403 or response.get_json()["code"] == 403


def test_root_report_action_projection_matches_admin_without_skipping_workflow_status(actors):
    from app.models import Report
    from app.applications.report_lifecycle.queries import report_allowed_actions, data_entry_return_allowed
    from app.platform.identity.access import is_platform_administrator
    client, f, root, lab, other, staff, ordinary, admin, project, steps = actors
    report = Report(report_no="QA-ROOT-01", department=other.name, project=project.name,
                    status="待批准", detail={})
    db.session.add(report); db.session.commit()
    assert is_platform_administrator(staff)
    assert data_entry_return_allowed(staff, report)
    assert report_allowed_actions(staff, report) == report_allowed_actions(admin, report)
    assert "report.approval.pass" in report_allowed_actions(staff, report)
    assert "report.print.pass" not in report_allowed_actions(staff, report)
    assert not data_entry_return_allowed(ordinary, report)
