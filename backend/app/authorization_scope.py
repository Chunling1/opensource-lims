"""Department-scoped project selection and per-user standard authorization."""
from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import or_

from .extensions import db
from .models import (
    Department,
    Project,
    ProjectStep,
    StdLibraryItem,
    User,
    user_project_permissions,
    user_standard_denials,
)
from .standard_control import normalize_code
from .workflow_dates import is_super_admin

from .organization_privileges import (
    ROOT_DEPARTMENT_CODE, ROOT_DEPARTMENT_NAME,
    department_has_org_wide_scope, has_full_platform_authority,
)
PROJECT_STEP_FUNCTION_PERMISSIONS = {
    "entrust_register": {"entrust.registration.view"},
    "entrust_review": {
        "entrust.contract_review.view",
        "report.contract_review.view",
    },
    "sample_inbound": {"sample.inbound.view"},
    "sample_outbound": {"sample.outbound.view"},
    "data_entry": {"testing.data_entry.view", "testing.data_change.view"},
    "record_review": {"testing.original_record_review.view"},
    "report_review": {"report.review.view", "report.interim_report.view"},
    "report_approval": {"report.approval.view"},
    "report_print": {"report.print.view"},
    "report_archive": {"report.archive.view"},
}


def project_step_matches_permissions(
    step: ProjectStep,
    permission_codes: set[str],
) -> bool:
    required = PROJECT_STEP_FUNCTION_PERMISSIONS.get(step.step_code, set())
    return not required or bool(required & permission_codes)


def _compact_department(value: str) -> str:
    return re.sub(r"[（）()\s]", "", value or "")


def user_has_org_wide_scope(user: User) -> bool:
    """Explicit all-scope users, admins and the company root are unrestricted.

    User-management permissions are intentionally not considered here.
    """

    from .admin_corrections import can_correct_business_data
    if can_correct_business_data(user):
        return True
    from .platform.identity.department_project_scope import uses_department_project_scope
    if uses_department_project_scope(user):
        return is_super_admin(user)
    return bool(
        is_super_admin(user)
        or str(user.data_scope_type or "").strip() == "all"
        or department_has_org_wide_scope(user.department)
    )


def standard_has_department(item: StdLibraryItem) -> bool:
    """Business pickers never treat an empty assignment as an all-department grant."""
    return any(_compact_department(value) for value in re.split(r"[;；]", item.use_depts or ""))


def standard_matches_department(item: StdLibraryItem, department: str) -> bool:
    """Strict match used for user authorization; unassigned standards are not selectable."""
    wanted = _compact_department(department)
    assigned = [
        _compact_department(value)
        for value in re.split(r"[;；]", item.use_depts or "")
        if value.strip()
    ]
    return bool(wanted and assigned) and any(
        wanted == value or wanted in value or value in wanted for value in assigned
    )


def department_standard_items(department: str) -> list[StdLibraryItem]:
    return [
        item
        for item in StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None))
        .order_by(StdLibraryItem.code, StdLibraryItem.id)
        .all()
        if standard_matches_department(item, department)
    ]


def all_standard_items() -> list[StdLibraryItem]:
    return (
        StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None))
        .order_by(StdLibraryItem.code, StdLibraryItem.id)
        .all()
    )


def scoped_standard_items(
    department: Department | None,
    *,
    org_wide: bool = False,
) -> list[StdLibraryItem]:
    if org_wide or department_has_org_wide_scope(department):
        return all_standard_items()
    return department_standard_items(department.name if department else "")


def denied_standard_item_ids(user: User) -> set[int]:
    rows = db.session.execute(
        user_standard_denials.select().where(user_standard_denials.c.user_id == user.id)
    ).fetchall()
    return {int(row.standard_item_id) for row in rows}


def standard_authorization_payload(user: User) -> dict:
    department = user.department.name if user.department else ""
    org_wide = user_has_org_wide_scope(user)
    items = scoped_standard_items(user.department, org_wide=org_wide)
    denied = set() if org_wide else denied_standard_item_ids(user)
    return {
        "department": "全院全部标准" if org_wide else department,
        "items": [
            {
                "id": item.id,
                "code": item.code or "",
                "name": item.name or "",
                "authKind": item.auth_kind or "",
                "status": item.to_row()["status"],
            }
            for item in items
        ],
        "authorizedItemIds": [item.id for item in items if item.id not in denied],
    }


def replace_standard_authorizations(user: User, authorized_ids: Iterable[int]) -> None:
    org_wide = user_has_org_wide_scope(user)
    eligible = {
        item.id for item in scoped_standard_items(user.department, org_wide=org_wide)
    }
    requested = {int(value) for value in authorized_ids}
    outside = requested - eligible
    if outside:
        raise ValueError("只能授权用户所属部门已分配的标准")
    db.session.execute(
        user_standard_denials.delete().where(user_standard_denials.c.user_id == user.id)
    )
    # 公司根机构和系统管理员固定拥有全院标准，不记录取消授权例外。
    for item_id in sorted(set() if org_wide else eligible - requested):
        db.session.execute(
            user_standard_denials.insert().values(
                user_id=user.id,
                standard_item_id=item_id,
            )
        )


def standard_is_authorized(
    user: User,
    value: str,
    requested_department: str = "",
) -> bool:
    wanted = normalize_code(value)
    if not wanted:
        return False
    org_wide = user_has_org_wide_scope(user)
    department = user.department.name if user.department else ""
    if org_wide:
        items = all_standard_items()
    elif department:
        items = department_standard_items(department)
    else:
        return False
    denied = set() if org_wide else denied_standard_item_ids(user)
    for item in items:
        code = normalize_code(item.code)
        if item.id in denied or not standard_has_department(item):
            continue
        if requested_department and not standard_matches_department(item, requested_department):
            continue
        if wanted == code or (code and wanted.startswith(code)):
            return True
    return False


def department_projects(user: User) -> list[Project]:
    if user_has_org_wide_scope(user):
        return (
            Project.query.filter_by(active=True)
            .order_by(Project.department_id, Project.name, Project.number_code, Project.id)
            .all()
        )
    if not user.department_id:
        return []
    return (
        Project.query.filter_by(department_id=user.department_id, active=True)
        .order_by(Project.name, Project.number_code, Project.id)
        .all()
    )


def validate_project_department(
    user: User,
    requested_department: str = "",
) -> str:
    """Validate the account's department boundary independently of item names."""
    org_wide = user_has_org_wide_scope(user)
    if not user.department and not org_wide:
        return "当前账号未分配部门，不能选择检测项目"
    if (
        not org_wide
        and requested_department
        and _compact_department(requested_department)
        != _compact_department(user.department.name)
    ):
        return f"只能选择本人所属部门「{user.department.name}」的检测项目"
    return ""


def validate_project_selection(
    user: User,
    project_values: str | Iterable[str],
    requested_department: str = "",
) -> str:
    org_wide = user_has_org_wide_scope(user)
    department_error = validate_project_department(user, requested_department)
    if department_error:
        return department_error
    if org_wide and requested_department:
        wanted_department = _compact_department(requested_department)
        allowed = [
            project
            for project in Project.query.filter_by(active=True)
            .join(Department, Department.id == Project.department_id)
            .all()
            if project.department
            and _compact_department(project.department.name) == wanted_department
        ]
    else:
        allowed = department_projects(user)
    allowed_names = {project.name for project in allowed}
    allowed_codes = {
        value
        for project in allowed
        for value in (project.display_code, project.number_code, project.code)
        if value
    }
    if isinstance(project_values, str):
        raw = project_values.strip()
        if raw in allowed_names or raw in allowed_codes:
            values = [raw]
        else:
            values = [part.strip() for part in re.split(r"[；;\n]+", raw) if part.strip()]
            if len(values) == 1 and "、" in raw:
                values = [part.strip() for part in raw.split("、") if part.strip()]
    else:
        values = [str(value or "").strip() for value in project_values if str(value or "").strip()]
    if not values:
        return "请选择检测项目"
    invalid = [value for value in values if value not in allowed_names and value not in allowed_codes]
    if invalid:
        return (
            f"项目「{'、'.join(invalid)}」不属于本人所在的「{user.department.name}」，"
            "请从部门项目库重新选择"
        )
    return ""


def project_for_report(report) -> Project | None:
    from .preflight_reads import read_once
    raw = (report.detail or {}).get('rawSample') or {}
    key = ('list-project', report.department, str(raw.get('schemeCode') or ''),
           str(raw.get('schemeName') or ''), str(report.project or ''),
           report.report_no, report.main_report_no, report.report_kind, report.entrust_no,
           str((report.detail or {}).get('derivedFrom') or ''),
           str(raw.get('baseReportNo') or ''))
    return read_once(key, lambda: (read_once(('list-project-identity', *key[1:5]),
                                 lambda: _project_for_report_uncached(report))
                                 or _derived_source_project(report)))


def _project_for_report_uncached(report) -> Project | None:
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    scheme_code = str(raw.get("schemeCode") or "").strip()
    scheme_name = str(raw.get("schemeName") or "").strip()
    # 已停用项目仍需服务历史报告的授权、审计和流转配置。
    query = Project.query
    if report.department:
        query = query.join(Project.department).filter(
            Project.department.has(name=report.department)
        )
    if scheme_code:
        code_match = or_(
            Project.number_code == scheme_code,
            Project.display_code == scheme_code,
            Project.code == scheme_code,
        )
        rows = query.filter(code_match).order_by(Project.id).all()
        if scheme_name:
            named = [row for row in rows if row.name == scheme_name]
            if rows:
                return named[0] if len(named) == 1 else None
        if rows:
            return rows[0] if len(rows) == 1 else None
        alias_rows = [
            project
            for project in query.order_by(Project.id).all()
            if scheme_code in {
                str(value or "").strip()
                for value in (project.code_aliases or [])
            }
        ]
        if scheme_name:
            named = [row for row in alias_rows if row.name == scheme_name]
            if alias_rows:
                return named[0] if len(named) == 1 else None
        if alias_rows:
            return alias_rows[0] if len(alias_rows) == 1 else None
        # A supplied but unknown identifier must not silently become another project.
        return None
    if scheme_name:
        rows = query.filter(Project.name == scheme_name).limit(2).all()
        return rows[0] if len(rows) == 1 else None
    project_text = str(report.project or "").strip()
    rows = query.filter(Project.name == project_text).limit(2).all() if project_text else []
    return rows[0] if len(rows) == 1 else None



def _derived_source_project(report) -> Project | None:
    """Resolve a missing legacy scheme name from an unambiguous saved parent.

    Never replace a supplied scheme name, choose the first duplicate code, or
    inherit permissions. The caller still authorizes the resolved project.
    """
    from types import SimpleNamespace
    from .models import Report
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    if report.report_kind not in {"english", "supplement", "itemized"}:
        return None
    if str(raw.get("schemeName") or "").strip():
        return None
    code = str(raw.get("schemeCode") or "").strip()
    parent_no = str(report.main_report_no or "").strip()
    if not code or not parent_no or parent_no == report.report_no or not report.department:
        return None
    references = (detail.get("derivedFrom"), raw.get("baseReportNo"))
    if any(str(value).strip() != parent_no for value in references if value):
        return None
    # Only the first-generation main report is authoritative; no recursive
    # fallback through derived chains or a parent with missing identity.
    source = Report.query.filter_by(report_no=parent_no).first()
    if (source is None or source.voided or source.report_kind not in {None, "", "main"}
            or source.department != report.department
            or not report.entrust_no or source.entrust_no != report.entrust_no):
        return None
    project = _project_for_report_uncached(source)
    if project is None:
        return None
    candidate = SimpleNamespace(department=report.department, project=report.project,
        detail={"rawSample": {**raw, "schemeName": project.name}})
    matched = _project_for_report_uncached(candidate)
    return project if matched is not None and matched.id == project.id else None


def user_has_project_step(user: User, project: Project, step_code: str) -> bool:
    if has_full_platform_authority(user):
        # Disabled projects remain available to historical-report workflows;
        # department_projects excludes them from new registration choices.
        return bool(project and ProjectStep.query.filter_by(
            project_id=project.id, step_code=step_code,
        ).first())
    from .platform.identity.department_project_scope import (
        BASIC_STEPS, project_is_visible, uses_department_project_scope,
    )
    if uses_department_project_scope(user):
        if not user.enabled or step_code == 'record_review':
            return False
        if step_code in BASIC_STEPS:
            required = PROJECT_STEP_FUNCTION_PERMISSIONS[step_code]
            return bool(required.intersection(user.permission_codes()) and project_is_visible(user, project))
    step_row = db.session.execute(
        user_project_permissions.select()
        .join(ProjectStep, ProjectStep.id == user_project_permissions.c.project_step_id)
        .where(
            user_project_permissions.c.user_id == user.id,
            ProjectStep.project_id == project.id,
            ProjectStep.step_code == step_code,
        )
    ).first()
    if step_row is None:
        return False
    step = db.session.get(ProjectStep, step_row.project_step_id)
    if step is None or not project_step_matches_permissions(
        step,
        set(user.permission_codes()),
    ):
        return False
    if user_has_org_wide_scope(user):
        return True
    return bool(
        user.department
        and any(
            department_step.id == step.id
            for department_step in user.department.project_steps
        )
    )


def project_step_error(user: User, report, step_code: str, label: str) -> str:
    project = project_for_report(report)
    if project is None:
        return "报告项目无法唯一识别，请核对项目归属后再处理"
    from .preflight_reads import read_once
    if read_once(('list-project-step', user.id, project.id, step_code),
                 lambda: user_has_project_step(user, project, step_code)):
        return ""
    return f"当前账号未取得项目「{project.name}（{project.display_code or project.number_code or project.code}）」的{label}授权"


__all__ = [
    "all_standard_items",
    "department_has_org_wide_scope",
    "department_projects",
    "department_standard_items",
    "denied_standard_item_ids",
    "project_for_report",
    "project_step_matches_permissions",
    "project_step_error",
    "replace_standard_authorizations",
    "scoped_standard_items",
    "standard_authorization_payload",
    "standard_is_authorized",
    "standard_matches_department",
    "user_has_org_wide_scope",
    "user_has_project_step",
    "validate_project_department",
    "validate_project_selection",
]
