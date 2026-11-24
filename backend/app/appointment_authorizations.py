from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import seed_data
from .applications.quality_resources import apply_personnel_authorization_projection
from .platform.audit import add_operation_audit
from .platform.identity import (
    user_has_org_wide_scope,
)
from .extensions import db
from .models import (
    Department,
    OperationAudit,
    Permission,
    Personnel,
    Project,
    ProjectStep,
    User,
    user_action_permissions,
    user_data_departments,
    user_project_permissions,
)

DEFAULT_SOURCE_NAME = "appointment_authorizations_20260803.json"
MANAGED_STEPS = ("data_entry", "record_review", "report_review", "report_approval")
STEP_LABELS = {
    "data_entry": "数据录入",
    "record_review": "原始记录审核",
    "report_review": "报告审核",
    "report_approval": "报告批准",
}
PERSONNEL_PERMISSION_LABELS = {
    "data_entry": "数据录入",
    "record_review": "原始记录审核",
    "report_review": "审核",
    "report_approval": "批准",
}
FUNCTION_PERMISSIONS = {
    "data_entry": {"testing.view", "testing.data_entry.view", "report.query.view"},
    "record_review": {"testing.view", "testing.task_query.view", "report.query.view"},
    "report_review": {"report.view", "report.review.view"},
    "report_approval": {"report.view", "report.approval.view"},
}
ACTION_PERMISSIONS = {
    "data_entry": {
        "report.attachment.upload", "report.pdf.merge",
        "report.pdf.preview", "report.pdf.download",
    },
    "record_review": {"report.pdf.preview", "report.pdf.download"},
    "report_review": {
        "report.review.pass", "report.review.return", "report.review.undo",
        "report.pdf.preview", "report.pdf.download",
    },
    "report_approval": {
        "report.approval.pass", "report.approval.return", "report.approval.undo",
        "report.pdf.preview", "report.pdf.download",
    },
}


class AppointmentImportError(ValueError):
    pass


@dataclass
class AppointmentImportSummary:
    source_rows: int = 0
    excluded_rows: int = 0
    projects_in_source: int = 0
    projects_created: int = 0
    projects_updated: int = 0
    legacy_projects_deactivated: int = 0
    custom_projects_reactivated: int = 0
    project_steps_created: int = 0
    matched_people: int = 0
    unmatched_people: list[str] = field(default_factory=list)
    resolved_by_name: list[str] = field(default_factory=list)
    unresolved_people: list[str] = field(default_factory=list)
    missing_accounts: list[str] = field(default_factory=list)
    project_grants_added: int = 0
    project_grants_removed: int = 0
    function_grants_added: int = 0
    action_grants_added: int = 0
    data_grants_added: int = 0
    personnel_records_updated: int = 0
    dry_run: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_appointment_source(path: str | Path) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AppointmentImportError("任命授权源文件无法读取") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("projects"), list):
        raise AppointmentImportError("任命授权源文件格式无效")
    seen = set()
    for index, row in enumerate(payload["projects"], start=1):
        if not isinstance(row, dict):
            raise AppointmentImportError(f"项目第 {index} 条不是对象")
        required = ("sourceKey", "department", "name", "displayCode", "roleAccounts")
        if any(key not in row for key in required):
            raise AppointmentImportError(f"项目第 {index} 条缺少必要字段")
        if row["sourceKey"] in seen:
            raise AppointmentImportError(f"项目来源键重复：{row['sourceKey']}")
        seen.add(row["sourceKey"])
        unknown_steps = set(row["roleAccounts"]) - set(MANAGED_STEPS)
        if unknown_steps:
            raise AppointmentImportError(
                f"项目 {row['name']} 存在未知授权列：{', '.join(sorted(unknown_steps))}"
            )
    return payload


def _merge_semicolon(value: str | None, additions: set[str]) -> tuple[str, bool]:
    items = [part.strip() for part in (value or "").split(";") if part.strip()]
    before = list(items)
    for addition in sorted(additions):
        if addition not in items:
            items.append(addition)
    return ";".join(items), items != before


def _project_for_source(row: dict, department: Department) -> Project | None:
    existing = Project.query.filter_by(source_key=row["sourceKey"]).one_or_none()
    if existing:
        return existing
    display_code = str(row.get("displayCode") or "")
    return (
        Project.query.filter_by(
            department_id=department.id,
            name=row["name"],
            code=display_code,
        ).filter(Project.source_key.is_(None)).one_or_none()
        if display_code
        else None
    )


def _ensure_project(row: dict, department: Department, summary: AppointmentImportSummary) -> Project:
    project = _project_for_source(row, department)
    if project is None:
        project = Project(
            code=f"APPT-{row['sourceKey']}",
            name=row["name"],
            department_id=department.id,
        )
        db.session.add(project)
        summary.projects_created += 1
    else:
        summary.projects_updated += 1
    project.name = row["name"]
    project.department_id = department.id
    project.display_code = str(row.get("displayCode") or "")
    project.number_code = str(row.get("numberCode") or "")
    project.location = str(row.get("location") or "")
    project.source_department = "；".join(row.get("sourceDepartments") or [])
    project.source_key = row["sourceKey"]
    project.active = True
    db.session.flush()

    existing_steps = {step.step_code: step for step in project.steps}
    for step_code, step_name in seed_data.STANDARD_STEPS:
        step = existing_steps.get(step_code)
        if step is None:
            db.session.add(
                ProjectStep(
                    project_id=project.id,
                    step_code=step_code,
                    step_name=step_name,
                )
            )
            summary.project_steps_created += 1
        else:
            step.step_name = step_name
    db.session.flush()
    return project


def _sync_project_grants(
    desired: set[tuple[int, int]],
    appointment_project_ids: set[int],
    summary: AppointmentImportSummary,
) -> None:
    protected_user_ids = {
        user.id for user in User.query.all() if user_has_org_wide_scope(user)
    }
    managed_step_ids = {
        step.id
        for step in ProjectStep.query.filter(
            ProjectStep.project_id.in_(appointment_project_ids),
            ProjectStep.step_code.in_(MANAGED_STEPS),
        ).all()
    }
    current = {
        (int(row.user_id), int(row.project_step_id))
        for row in db.session.execute(
            user_project_permissions.select().where(
                user_project_permissions.c.project_step_id.in_(managed_step_ids)
            )
        ).fetchall()
    } if managed_step_ids else set()
    # 任命文件用于追加本批次授权，不能据此判断既有授权是否应撤销。
    # 人工授权、历史任命及其他来源授权均原样保留。

    # 历史版本可能已经误删过管理员/根机构账号的部分步骤；每次导入均幂等补齐。
    all_step_ids = {int(step.id) for step in ProjectStep.query.all()}
    for user_id in sorted(protected_user_ids):
        current_step_ids = {
            int(row.project_step_id)
            for row in db.session.execute(
                user_project_permissions.select().where(
                    user_project_permissions.c.user_id == user_id
                )
            ).fetchall()
        }
        for step_id in sorted(all_step_ids - current_step_ids):
            db.session.execute(
                user_project_permissions.insert().values(
                    user_id=user_id,
                    project_step_id=step_id,
                )
            )
            summary.project_grants_added += 1

    for user_id, step_id in sorted(desired - current):
        if user_id in protected_user_ids:
            continue
        db.session.execute(
            user_project_permissions.insert().values(
                user_id=user_id,
                project_step_id=step_id,
            )
        )
        summary.project_grants_added += 1


def _resolve_role_accounts(
    row: dict,
    users_by_account: dict[str, User],
    users_by_name: dict[str, list[User]],
    personnel_accounts_by_name: dict[str, set[str]],
    summary: AppointmentImportSummary,
) -> dict[str, list[str]]:
    """Resolve reviewed names against the live database without inventing accounts."""
    resolved: dict[str, list[str]] = {}
    for step_code in MANAGED_STEPS:
        accounts = {
            str(account).strip().lower()
            for account in row.get("roleAccounts", {}).get(step_code, [])
            if str(account).strip()
        }
        mapped_names = {
            user.name for account in accounts
            if (user := users_by_account.get(account)) is not None
        }
        for name in row.get("roleNames", {}).get(step_code, []):
            clean_name = str(name).strip()
            if not clean_name or clean_name in mapped_names:
                continue
            candidates = users_by_name.get(clean_name, [])
            if len(candidates) == 1:
                account = candidates[0].account.lower()
            else:
                personnel_accounts = personnel_accounts_by_name.get(clean_name, set())
                live_accounts = sorted(personnel_accounts & set(users_by_account))
                account = live_accounts[0] if len(live_accounts) == 1 else ""
            if account:
                accounts.add(account)
                if clean_name not in summary.resolved_by_name:
                    summary.resolved_by_name.append(clean_name)
            elif clean_name not in summary.unresolved_people:
                summary.unresolved_people.append(clean_name)
        resolved[step_code] = sorted(accounts)
    return resolved


def _restore_accidentally_deactivated_custom_project(project: Project) -> bool:
    """恢复被旧版任命同步误停用、但没有人工删除的自定义项目。"""
    if project.active or not str(project.source_key or "").startswith("custom:"):
        return False
    latest_audit = (
        OperationAudit.query.filter_by(
            object_type="project",
            object_id=str(project.id),
        )
        .order_by(OperationAudit.id.desc())
        .first()
    )
    latest_after = (
        latest_audit.after_data
        if latest_audit and isinstance(latest_audit.after_data, dict)
        else {}
    )
    if (
        latest_audit is None
        or latest_audit.action == "system.project.delete"
        or latest_after.get("active") is not True
    ):
        return False
    project.active = True
    return True


def import_appointment_authorizations(
    source_path: str | Path,
    *,
    apply_changes: bool = False,
) -> AppointmentImportSummary:
    payload = load_appointment_source(source_path)
    summary = AppointmentImportSummary(
        source_rows=int(payload.get("sourceTableRows") or 0),
        excluded_rows=len(payload.get("excludedSourceRows") or []),
        projects_in_source=len(payload["projects"]),
        matched_people=int(payload.get("matchedPersonCount") or 0),
        unmatched_people=list(payload.get("unmatchedPeople") or []),
        dry_run=not apply_changes,
    )
    departments = {row.name: row for row in Department.query.all()}
    unknown_departments = sorted({
        row["department"] for row in payload["projects"]
        if row["department"] not in departments
    })
    if unknown_departments:
        raise AppointmentImportError("系统缺少部门：" + "、".join(unknown_departments))

    all_users = User.query.all()
    users = {user.account.lower(): user for user in all_users}
    users_by_name: dict[str, list[User]] = {}
    for user in all_users:
        users_by_name.setdefault(str(user.name or "").strip(), []).append(user)
    personnel_accounts_by_name: dict[str, set[str]] = {}
    for personnel in Personnel.query.filter_by(deleted_at=None).all():
        if personnel.name and personnel.code:
            personnel_accounts_by_name.setdefault(
                personnel.name.strip(), set()
            ).add(personnel.code.strip().lower())
    resolved_role_accounts = {
        row["sourceKey"]: _resolve_role_accounts(
            row,
            users,
            users_by_name,
            personnel_accounts_by_name,
            summary,
        )
        for row in payload["projects"]
    }
    summary.resolved_by_name.sort()
    summary.unresolved_people.sort()
    referenced_accounts = {
        str(account).lower()
        for row in payload["projects"]
        for accounts in resolved_role_accounts[row["sourceKey"]].values()
        for account in accounts
    }
    summary.missing_accounts = sorted(referenced_accounts - set(users))
    if summary.missing_accounts:
        raise AppointmentImportError(
            "任命人员账号尚未导入：" + "、".join(summary.missing_accounts)
        )
    permission_by_code = {row.code: row for row in Permission.query.all()}
    needed_permission_codes = set().union(*FUNCTION_PERMISSIONS.values())
    missing_permissions = sorted(needed_permission_codes - set(permission_by_code))
    if missing_permissions:
        raise AppointmentImportError(
            "系统缺少功能权限点：" + "、".join(missing_permissions)
        )

    try:
        projects_by_key: dict[str, Project] = {}
        for row in payload["projects"]:
            project = _ensure_project(row, departments[row["department"]], summary)
            projects_by_key[row["sourceKey"]] = project

        target_keys = set(projects_by_key)
        seed_codes = {row["code"] for row in seed_data.PROJECTS}
        imported_project_ids = {project.id for project in projects_by_key.values()}
        for project in Project.query.all():
            # 自定义项目由“检测项目自定义”模块维护，不属于任命文件的同步范围。
            # 旧逻辑会把 custom:* 误判成已从任命文件移除的项目，并在每次发布时停用。
            if str(project.source_key or "").startswith("custom:"):
                if _restore_accidentally_deactivated_custom_project(project):
                    summary.custom_projects_reactivated += 1
                continue
            obsolete_appointment = bool(project.source_key and project.source_key not in target_keys)
            obsolete_seed = (
                project.id not in imported_project_ids
                and project.source_key is None
                and project.code in seed_codes
            )
            if project.active and (obsolete_appointment or obsolete_seed):
                project.active = False
                summary.legacy_projects_deactivated += 1

        db.session.flush()
        desired_grants: set[tuple[int, int]] = set()
        user_roles: dict[int, set[str]] = {}
        user_departments: dict[int, set[int]] = {}
        for row in payload["projects"]:
            project = projects_by_key[row["sourceKey"]]
            steps = {
                step.step_code: step
                for step in ProjectStep.query.filter_by(project_id=project.id).all()
            }
            for step_code, accounts in resolved_role_accounts[row["sourceKey"]].items():
                step = steps[step_code]
                for account in accounts:
                    user = users[str(account).lower()]
                    desired_grants.add((user.id, step.id))
                    user_roles.setdefault(user.id, set()).add(step_code)
                    user_departments.setdefault(user.id, set()).add(project.department_id)

        _sync_project_grants(desired_grants, imported_project_ids, summary)

        # 任命文件是人员项目步骤授权的权威来源；同步把这些步骤补入人员所属部门的
        # 授权上限，避免出现“人员已有任命，但被部门上限意外拦截”的矛盾。
        desired_step_ids_by_user: dict[int, set[int]] = {}
        for user_id, step_id in desired_grants:
            desired_step_ids_by_user.setdefault(user_id, set()).add(step_id)
        for user_id, step_ids in desired_step_ids_by_user.items():
            user = db.session.get(User, user_id)
            if not user or not user.department:
                continue
            known_department_step_ids = {
                step.id for step in user.department.project_steps
            }
            for step_id in sorted(step_ids - known_department_step_ids):
                step = db.session.get(ProjectStep, step_id)
                if step:
                    user.department.project_steps.append(step)
                    if step.project not in user.department.projects:
                        user.department.projects.append(step.project)

        for user_id, roles in user_roles.items():
            user = db.session.get(User, user_id)
            current_permissions = {permission.code for permission in user.permissions}
            grant_permissions = set().union(*(FUNCTION_PERMISSIONS[role] for role in roles))
            for code in sorted(grant_permissions - current_permissions):
                user.permissions.append(permission_by_code[code])
                summary.function_grants_added += 1
            if user.department:
                department_permission_codes = {
                    permission.code for permission in user.department.permissions
                }
                for code in sorted(grant_permissions - department_permission_codes):
                    user.department.permissions.append(permission_by_code[code])

            current_actions = {
                row.action_code
                for row in db.session.execute(
                    user_action_permissions.select().where(
                        user_action_permissions.c.user_id == user.id
                    )
                ).fetchall()
            }
            grant_actions = set().union(*(ACTION_PERMISSIONS[role] for role in roles))
            for action in sorted(grant_actions - current_actions):
                db.session.execute(
                    user_action_permissions.insert().values(
                        user_id=user.id,
                        action_code=action,
                    )
                )
                summary.action_grants_added += 1

            personnel = Personnel.query.filter_by(
                code=user.account, deleted_at=None
            ).order_by(Personnel.id).first()
            if personnel:
                labels = {PERSONNEL_PERMISSION_LABELS[role] for role in roles}
                department_names = {
                    db.session.get(Department, department_id).name
                    for department_id in user_departments.get(user.id, set())
                }
                permissions_changed, departments_changed = (
                    apply_personnel_authorization_projection(
                        personnel,
                        permission_labels=labels,
                        department_names=department_names,
                    )
                )
                if permissions_changed or departments_changed:
                    summary.personnel_records_updated += 1

            current_department_grants = {
                int(row.department_id)
                for row in db.session.execute(
                    user_data_departments.select().where(
                        user_data_departments.c.user_id == user.id
                    )
                ).fetchall()
            }
            for department_id in sorted(
                user_departments.get(user.id, set()) - current_department_grants
            ):
                db.session.execute(
                    user_data_departments.insert().values(
                        user_id=user.id,
                        department_id=department_id,
                        include_children=False,
                        see_data=True,
                        see_members=False,
                        granted_by="appointment-import",
                        granted_at=datetime.now(UTC).isoformat(timespec="seconds"),
                    )
                )
                summary.data_grants_added += 1

        # 本导入器不清理组织机构或人员已有授权；撤权必须由管理员明确操作。

        if not apply_changes:
            db.session.rollback()
            return summary

        add_operation_audit(
            "system.appointment_authorizations.import",
            "appointment_authorization_batch",
            Path(source_path).name,
            category="system",
            after=summary.as_dict(),
            message=(
                f"任命授权导入：项目 {summary.projects_in_source}，"
                f"人员 {summary.matched_people}"
            ),
        )
        db.session.commit()
        return summary
    except Exception:
        db.session.rollback()
        raise


__all__ = [
    "AppointmentImportError",
    "AppointmentImportSummary",
    "DEFAULT_SOURCE_NAME",
    "import_appointment_authorizations",
    "load_appointment_source",
]
