"""Consistent virtual identity and authorization fixtures for module tests."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count

from app.extensions import db
from app.models import (
    Department,
    Permission,
    Project,
    ProjectStep,
    User,
    user_action_permissions,
    user_data_departments,
)
from app.security import hash_password


def _synthetic_login_value() -> str:
    """Return the fixed virtual-only login value used by the isolated testkit."""

    return "Test-only-password-2026!"


DEFAULT_TEST_PASSWORD = _synthetic_login_value()
DEFAULT_STEPS = (
    ("entrust_review", "委托评审"),
    ("sample_inbound", "样品入库"),
    ("sample_outbound", "样品领取"),
    ("data_entry", "检测数据录入"),
    ("report_review", "报告审核"),
    ("report_approval", "报告批准"),
    ("report_print", "报告打印"),
    ("report_release", "报告发放"),
    ("report_archive", "报告归档"),
)


@dataclass(frozen=True)
class IdentityScenario:
    department: Department
    project: Project
    steps: tuple[ProjectStep, ...]
    permissions: tuple[Permission, ...]
    user: User


class ScenarioFactory:
    """Small factory with defaults that respect the five-layer permission model."""

    def __init__(self) -> None:
        self._sequence = count(1)

    def _next(self) -> int:
        return next(self._sequence)

    def department(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        parent: Department | None = None,
        site: str = "演示实验室",
    ) -> Department:
        number = self._next()
        row = Department(
            code=code or f"TEST-DEPT-{number:04d}",
            name=name or f"虚拟检测部门{number:04d}",
            parent=parent,
            site=site,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def permission(
        self,
        code: str,
        *,
        name: str | None = None,
        ptype: str = "page",
    ) -> Permission:
        row = db.session.get(Permission, code)
        if row is None:
            row = Permission(code=code, name=name or f"测试权限 {code}", ptype=ptype)
            db.session.add(row)
            db.session.flush()
        return row

    def project(
        self,
        department: Department,
        *,
        code: str | None = None,
        name: str | None = None,
        steps: Sequence[tuple[str, str]] = DEFAULT_STEPS,
        authorize_department: bool = True,
    ) -> tuple[Project, tuple[ProjectStep, ...]]:
        number = self._next()
        row = Project(
            code=code or f"TEST-PROJECT-{number:04d}",
            name=name or f"虚拟检测项目{number:04d}",
            department=department,
            active=True,
        )
        db.session.add(row)
        db.session.flush()
        step_rows = tuple(
            ProjectStep(project=row, step_code=step_code, step_name=step_name)
            for step_code, step_name in steps
        )
        db.session.add_all(step_rows)
        db.session.flush()
        if authorize_department:
            if row not in department.projects:
                department.projects.append(row)
            for step in step_rows:
                if step not in department.project_steps:
                    department.project_steps.append(step)
        return row, step_rows

    def user(
        self,
        department: Department,
        *,
        account: str | None = None,
        name: str | None = None,
        login_value: str = DEFAULT_TEST_PASSWORD,
        permissions: Iterable[Permission | str] = (),
        project_steps: Iterable[ProjectStep] = (),
        role_key: str = "operator",
        role_name: str = "虚拟检测人员",
        data_scope_type: str = "department",
        authorize_department: bool = True,
    ) -> User:
        number = self._next()
        permission_rows = tuple(
            self.permission(value) if isinstance(value, str) else value
            for value in permissions
        )
        step_rows = tuple(project_steps)
        if authorize_department:
            for permission in permission_rows:
                if permission not in department.permissions:
                    department.permissions.append(permission)
            for step in step_rows:
                if step not in department.project_steps:
                    department.project_steps.append(step)
        row = User(
            account=account or f"test_user_{number:04d}",
            password_hash=hash_password(login_value),
            name=name or f"虚拟人员{number:04d}",
            role_key=role_key,
            role_name=role_name,
            home_path="/home",
            department=department,
            data_scope_type=data_scope_type,
            enabled=True,
            must_change_password=False,
        )
        row.permissions.extend(permission_rows)
        row.project_steps.extend(step_rows)
        db.session.add(row)
        db.session.flush()
        return row

    def grant_action(self, user: User, action_code: str) -> None:
        db.session.execute(user_action_permissions.insert().values(
            user_id=user.id,
            action_code=action_code,
        ))

    def grant_data_department(
        self,
        user: User,
        department: Department,
        *,
        include_children: bool = False,
        see_data: bool = True,
        see_members: bool = True,
        granted_by: str = "testkit",
    ) -> None:
        db.session.execute(user_data_departments.insert().values(
            user_id=user.id,
            department_id=department.id,
            include_children=include_children,
            see_data=see_data,
            see_members=see_members,
            granted_by=granted_by,
            granted_at=datetime.now(UTC).isoformat(),
        ))

    def identity_scenario(
        self,
        *,
        permission_codes: Sequence[str] = (),
        granted_step_codes: Sequence[str] = (),
    ) -> IdentityScenario:
        department = self.department()
        project, steps = self.project(department)
        step_by_code = {step.step_code: step for step in steps}
        unknown = sorted(set(granted_step_codes) - set(step_by_code))
        if unknown:
            raise ValueError(f"unknown project step codes: {unknown}")
        permissions = tuple(self.permission(code) for code in permission_codes)
        user = self.user(
            department,
            permissions=permissions,
            project_steps=(step_by_code[code] for code in granted_step_codes),
        )
        db.session.commit()
        return IdentityScenario(department, project, steps, permissions, user)


def login_headers(client, account: str, login_value: str = DEFAULT_TEST_PASSWORD) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"account": account, "password": login_value})
    payload = response.get_json()
    assert response.status_code == 200, payload
    assert payload["code"] == 0, payload
    return {"Authorization": f"Bearer {payload['data']['token']}"}


__all__ = [
    "DEFAULT_STEPS",
    "DEFAULT_TEST_PASSWORD",
    "IdentityScenario",
    "ScenarioFactory",
    "login_headers",
]
