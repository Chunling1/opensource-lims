"""Public identity Command for moving an account between departments."""

from __future__ import annotations

from datetime import datetime

from ... import seed_data
from ...applications.quality_resources import move_linked_personnel_department
from ...extensions import db
from ...models import (
    Department,
    Permission,
    Project,
    ProjectStep,
    User,
    user_data_departments,
    user_standard_denials,
)
from app.platform.audit import add_operation_audit
from .service import (
    department_has_org_wide_scope,
    project_step_matches_permissions,
    user_has_org_wide_scope,
)


PROJECT_AUTHORIZATION_STEP_CODES = {
    code for code, _ in seed_data.PROJECT_AUTHORIZATION_STEPS
}


def _assignable_permissions():
    return [
        permission
        for permission in Permission.query.order_by(Permission.code).all()
        if permission.code != "system.user.view"
    ]


def _department_authorized_permissions(department: Department):
    if department_has_org_wide_scope(department):
        return _assignable_permissions()
    return [
        permission
        for permission in department.permissions
        if permission.code != "system.user.view"
    ]


def _department_authorized_project_steps(department: Department):
    query = ProjectStep.query.join(Project).filter(
        Project.active.is_(True),
        ProjectStep.step_code.in_(PROJECT_AUTHORIZATION_STEP_CODES),
    )
    if department_has_org_wide_scope(department):
        return query.order_by(ProjectStep.project_id, ProjectStep.id).all()
    permission_codes = {
        permission.code for permission in _department_authorized_permissions(department)
    }
    project_ids = {project.id for project in department.projects if project.active}
    return [
        step
        for step in query.order_by(ProjectStep.project_id, ProjectStep.id).all()
        if step.project_id in project_ids
        and project_step_matches_permissions(step, permission_codes)
    ]


def synchronize_user_department(
    user: User,
    old_department: Department | None,
    department: Department,
    *,
    actor,
) -> None:
    """Move identity grants and the quality roster in one transaction.

    The caller remains responsible for committing the surrounding edit.
    """

    if old_department and old_department.id == department.id:
        return
    old_department_id = old_department.id if old_department else None
    if old_department_id:
        db.session.execute(user_data_departments.delete().where(
            (user_data_departments.c.user_id == user.id)
            & (user_data_departments.c.department_id == old_department_id)
        ))
    db.session.execute(user_data_departments.delete().where(
        (user_data_departments.c.user_id == user.id)
        & (user_data_departments.c.department_id == department.id)
    ))
    db.session.execute(user_data_departments.insert().values(
        user_id=user.id,
        department_id=department.id,
        include_children=department_has_org_wide_scope(department),
        see_data=True,
        see_members=True,
        granted_by=getattr(actor, "account", "") or "",
        granted_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    ))
    db.session.expire(user, ["data_departments"])
    db.session.execute(user_standard_denials.delete().where(
        user_standard_denials.c.user_id == user.id
    ))
    move_linked_personnel_department(user, department)

    if not user_has_org_wide_scope(user):
        allowed_permission_codes = {
            permission.code for permission in _department_authorized_permissions(department)
        }
        allowed_step_ids = {
            step.id for step in _department_authorized_project_steps(department)
        }
        user.permissions = [
            permission for permission in user.permissions
            if permission.code in allowed_permission_codes
        ]
        user.project_steps = [
            step for step in user.project_steps
            if step.step_code not in PROJECT_AUTHORIZATION_STEP_CODES
            or (
                step.id in allowed_step_ids
                and project_step_matches_permissions(step, set(user.permission_codes()))
            )
        ]

    if department_has_org_wide_scope(department) and user.data_scope_type != 'department_project':
        user.data_scope_type = "all"
        user.data_scope_desc = "示例检测机构：可查看全院数据"
    elif (
        old_department
        and department_has_org_wide_scope(old_department)
        and user.role_key != "admin"
        and user.data_scope_type == "all"
    ):
        user.data_scope_type = "department"
        user.data_scope_desc = "仅查看本人所属部门数据"

    add_operation_audit(
        "organization.member.move_department",
        "user",
        user.id,
        category="admin",
        actor=actor,
        before={
            "departmentId": old_department_id,
            "department": old_department.name if old_department else "",
        },
        after={
            "departmentId": department.id,
            "department": department.name,
            "personnelSynchronized": True,
            "standardAuthorizationReset": "department-default-all",
        },
    )
