"""人员报告权限任命表的只读预检与事务导入。"""

from __future__ import annotations

import hashlib
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openpyxl import load_workbook

from . import seed_data
from .extensions import db
from .models import (
    Department,
    Permission,
    PermissionAppointmentImport,
    PermissionTemplate,
    Project,
    ProjectStep,
    User,
    user_data_departments,
    user_project_permissions,
)
from .platform.audit import add_operation_audit
from .permission_import_receipt import issue_receipt, validate_receipt, lock_import_snapshot


class PersonnelPermissionImportError(ValueError):
    pass


DETAIL_SHEET = "权限明细"
DETAIL_HEADERS = ["人员姓名", "所属部门", "报告类别名称", "项目编号", "权限", "地点", "原文备注", "源表行号"]
IGNORED_ROLE = "原始记录审核"
ROLE_TO_STEP = {
    "主检": "data_entry",
    "主检-资深检验员": "data_entry",
    "主检-检验员": "data_entry",
    "主检-见习检验员": "data_entry",
    "合同评审": "entrust_review",
    "检测报告审核": "report_review",
    "批准": "report_approval",
}
ROLE_TO_TEMPLATE = {
    "data_entry": "report-chief-inspector",
    "entrust_review": "contract-reviewer",
    "report_review": "report-reviewer",
    "report_approval": "report-approver",
}
TEMPLATE_SPECS = {
    "business-basic": {
        "name": "普通人员基础",
        "description": "主页、委托/样品新建及委托、样品、检测、原始记录和报告业务查询",
        "permissions": {
            "dashboard.view",
            "entrust.view", "entrust.registration.view", "entrust.sample_register.view", "entrust.query.view",
            "sample.view", "sample.flow_query.view",
            "testing.view", "testing.task_query.view", "testing.original_record_query.view",
            "report.view", "report.query.view",
        },
    },
    "report-chief-inspector": {
        "name": "主检",
        "description": "检测样品领取、检测数据录入/校核/更改及检毕样品处理",
        "permissions": {
            "testing.view", "testing.sample_pickup.view", "testing.data_entry.view",
            "testing.data_check.view", "testing.data_change.view", "testing.completed_sample_handling.view",
        },
    },
    "contract-reviewer": {
        "name": "合同评审",
        "description": "合同评审处理；通过、退回及撤销操作沿用系统既有隐含操作权限",
        "permissions": {"entrust.view", "entrust.contract_review.view"},
    },
    "report-reviewer": {
        "name": "报告审核",
        "description": "报告审核和中间报告处理",
        "permissions": {"report.view", "report.review.view", "report.interim_report.view"},
    },
    "report-approver": {
        "name": "报告批准",
        "description": "报告批准处理",
        "permissions": {"report.view", "report.approval.view"},
    },
}
MANAGED_PERMISSION_CODES = set().union(*(spec["permissions"] for spec in TEMPLATE_SPECS.values()))
MANAGED_STEP_CODES = set(ROLE_TO_TEMPLATE)
NEW_PROJECT_CODES = {
    "LL", "CHP", "BCCHP", "BDCHP", "BHCHP", "CPCHP", "DXCHP", "FSCHP",
    "HRCHP", "MTGCHP", "MYCHP", "PGCHP", "SYCHP", "YQCHP",
}
CODE_SPLIT = re.compile(r"[、,，;；\s]+")


@dataclass(frozen=True)
class GrantRow:
    row_no: int
    person: str
    source_department: str
    report_category: str
    project_code: str
    role: str
    location: str
    source_row: str


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _compact(value: Any) -> str:
    return re.sub(r"[\s　]+", "", _text(value)).lower()


def _code(value: Any) -> str:
    text = _text(value).upper().replace("／", "/")
    return text or "/"


def _read_detail_rows(content: bytes) -> list[GrantRow]:
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=False, read_only=True)
    except Exception as exc:
        raise PersonnelPermissionImportError("任命表无法解析，请上传原始 xlsx 文件") from exc
    if DETAIL_SHEET not in workbook.sheetnames:
        raise PersonnelPermissionImportError("缺少“权限明细”工作表")
    sheet = workbook[DETAIL_SHEET]
    headers = [_text(cell.value) for cell in sheet[4]][: len(DETAIL_HEADERS)]
    if headers != DETAIL_HEADERS:
        raise PersonnelPermissionImportError("“权限明细”表头与约定格式不一致")
    rows: list[GrantRow] = []
    for row_no, cells in enumerate(sheet.iter_rows(min_row=5, max_col=8), start=5):
        if any(cell.data_type == "f" for cell in cells):
            raise PersonnelPermissionImportError(f"权限明细第 {row_no} 行不允许公式")
        values = [_text(cell.value) for cell in cells]
        if not any(values):
            continue
        # 地点只用于重复编号消歧；原始任命表中合法存在空地点项目，不能因此拒绝整表。
        if not all(values[index] for index in (0, 1, 2, 3, 4)):
            raise PersonnelPermissionImportError(f"权限明细第 {row_no} 行必要字段不完整")
        role = values[4]
        if role != IGNORED_ROLE and role not in ROLE_TO_STEP:
            raise PersonnelPermissionImportError(f"权限明细第 {row_no} 行存在未知权限：{role}")
        rows.append(GrantRow(
            row_no=row_no,
            person=values[0],
            source_department=values[1],
            report_category=values[2],
            project_code=_code(values[3]),
            role=role,
            location=values[5],
            source_row=values[7],
        ))
    if not rows:
        raise PersonnelPermissionImportError("权限明细没有可读取记录")
    return rows


def _project_codes(project: Project) -> set[str]:
    values: list[str] = [project.code, project.display_code, project.number_code]
    aliases = project.code_aliases
    if isinstance(aliases, list):
        values.extend(_text(item) for item in aliases)
    elif isinstance(aliases, str):
        values.append(aliases)
    out = set()
    for value in values:
        text = _text(value)
        if not text:
            continue
        out.add(_code(text))
        out.update(_code(item) for item in CODE_SPLIT.split(text) if _text(item))
    return out


def _base_department(value: str) -> str:
    return re.split(r"\s*/\s*", value, maxsplit=1)[0].strip()


def _project_score(project: Project, row: GrantRow) -> int:
    score = 0
    base_department = _compact(_base_department(row.source_department))
    owner_department = _compact(project.department.name if project.department else "")
    source_department = _compact(project.source_department)
    if owner_department and owner_department == base_department:
        score += 8
    if source_department and (
        source_department == _compact(row.source_department)
        or source_department in _compact(row.source_department)
        or _compact(row.source_department) in source_department
    ):
        score += 7
    category = _compact(row.report_category)
    project_name = _compact(project.name)
    if category and project_name == category:
        score += 10
    elif category and project_name and (category in project_name or project_name in category):
        score += 5
    location = _compact(row.location)
    project_location = _compact(project.location)
    if location and project_location == location:
        score += 5
    elif location and project_location and (location in project_location or project_location in location):
        score += 2
    return score


def _resolve_project(row: GrantRow, projects: list[Project]) -> tuple[Project | None, str]:
    if row.project_code == "/":
        candidates = [project for project in projects if _compact(project.name) == _compact("电气安全")]
    else:
        candidates = [project for project in projects if row.project_code in _project_codes(project)]
    if not candidates:
        return None, "missing"
    if len(candidates) == 1:
        return candidates[0], "matched"
    ranked = sorted(((_project_score(project, row), project.id, project) for project in candidates), reverse=True)
    if ranked[0][0] <= 0 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
        return None, "ambiguous"
    return ranked[0][2], "matched"


def _department_for_source(source_department: str, departments: list[Department]) -> Department | None:
    base = _compact(_base_department(source_department))
    exact = [item for item in departments if _compact(item.name) == base]
    if len(exact) == 1:
        return exact[0]
    contained = [item for item in departments if _compact(item.name) and _compact(item.name) in _compact(source_department)]
    return contained[0] if len(contained) == 1 else None


def _new_project_spec(
    row: GrantRow,
    key: tuple[str, str, str, str],
    departments: list[Department],
) -> dict[str, Any] | None:
    department = _department_for_source(row.source_department, departments)
    if not department:
        return None
    return {
        "projectCode": row.project_code,
        "name": row.report_category,
        "departmentId": department.id,
        "department": department.name,
        "sourceDepartment": row.source_department,
        "location": row.location,
        "sourceKey": "permission-appointment:" + hashlib.sha256(
            "|".join(key).encode("utf-8")
        ).hexdigest()[:24],
    }


def _preview(content: bytes) -> dict[str, Any]:
    rows = _read_detail_rows(content)
    source_sha256 = hashlib.sha256(content).hexdigest()
    users_by_name: dict[str, list[User]] = defaultdict(list)
    for user in User.query.order_by(User.id).all():
        users_by_name[_compact(user.name)].append(user)
    projects = Project.query.filter_by(active=True).order_by(Project.id).all()
    departments = Department.query.order_by(Department.id).all()

    people = sorted({row.person for row in rows})
    matched_users: dict[str, User] = {}
    exceptions: list[dict[str, Any]] = []
    for name in people:
        candidates = users_by_name.get(_compact(name), [])
        if len(candidates) == 1:
            matched_users[name] = candidates[0]
        else:
            exceptions.append({
                "type": "人员未匹配" if not candidates else "人员匹配歧义",
                "person": name,
                "detail": "未自动建立账号" if not candidates else "系统存在多个同名账号",
            })

    ignored_rows = [row for row in rows if row.role == IGNORED_ROLE]
    managed_rows = [row for row in rows if row.role != IGNORED_ROLE]
    resolved_projects: dict[tuple[str, str, str, str], Project] = {}
    new_projects: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    project_errors: list[dict[str, Any]] = []
    for row in managed_rows:
        key = (row.project_code, row.report_category, row.source_department, row.location)
        if key in resolved_projects or key in new_projects:
            continue
        spec = _new_project_spec(row, key, departments)
        if spec and any(project.source_key == spec["sourceKey"] for project in projects):
            # Keep importer-created projects in the same acceptance bucket on
            # every rerun.  This makes preview/apply counts stable and allows a
            # repeated import to prove idempotency instead of changing 134+14
            # into 148+0 after the first successful execution.
            new_projects[key] = spec
            continue
        project, status = _resolve_project(row, projects)
        if project:
            resolved_projects[key] = project
            continue
        if status == "missing" and row.project_code in NEW_PROJECT_CODES:
            if not spec:
                project_errors.append({"type": "新增项目部门无效", "projectCode": row.project_code, "detail": row.source_department})
                continue
            new_projects[key] = spec
        else:
            project_errors.append({
                "type": "项目匹配歧义" if status == "ambiguous" else "项目未匹配",
                "projectCode": row.project_code,
                "detail": f"{row.report_category} / {row.source_department} / {row.location}",
            })

    # Stable project identity, never display number, defines an appointment.
    grant_index = {}
    user_roles: dict[int, set[str]] = defaultdict(set)
    for row in managed_rows:
        user = matched_users.get(row.person)
        key = (row.project_code, row.report_category, row.source_department, row.location)
        if not user or key not in resolved_projects and key not in new_projects:
            continue
        step_code = ROLE_TO_STEP[row.role]
        identity = ('existing', resolved_projects[key].id) if key in resolved_projects else ('new', new_projects[key]['sourceKey'])
        grant_index.setdefault((user.id, identity, step_code), key)
        user_roles[user.id].add(step_code)

    grants = {
        (user_id, source_key, step_code)
        for (user_id, _project_code, step_code), source_key in grant_index.items()
    }

    # Do not rewrite shared template definitions behind people absent from this
    # workbook. Such a change needs its own reviewed whole-membership preview.
    matched_ids = {user.id for user in matched_users.values()}
    for template in PermissionTemplate.query.filter(PermissionTemplate.code.in_(TEMPLATE_SPECS)).all():
        spec = TEMPLATE_SPECS[template.code]
        changed = (not template.enabled or template.name != spec['name']
                   or (template.description or '') != spec['description']
                   or {p.code for p in template.permissions} != spec['permissions']
                   or bool(template.project_steps))
        affected = sorted(user.id for user in template.users if user.id not in matched_ids)
        if changed and affected:
            project_errors.append({'type': '共享模板影响表外人员', 'projectCode': '',
                                   'detail': template.code, 'affectedUserIds': affected})

    exceptions.extend(project_errors)
    return {
        "sourceSha256": source_sha256,
        "sourceRows": len(rows),
        "peopleCount": len(people),
        "matchedPeopleCount": len(matched_users),
        "unmatchedPeopleCount": len(people) - len(matched_users),
        "matchedPeople": sorted(matched_users),
        "unmatchedPeople": sorted(name for name in people if name not in matched_users),
        "projectCodeCount": len({row.project_code for row in rows}),
        "matchedProjectCodeCount": len({key[0] for key in resolved_projects}),
        "newProjectCount": len(new_projects),
        "newProjects": sorted(new_projects.values(), key=lambda item: item["projectCode"]),
        "ignoredRowCount": len(ignored_rows),
        "ignoredRole": IGNORED_ROLE,
        "managedRowCount": len(managed_rows),
        "grantCount": len(grants),
        "templateCount": len(TEMPLATE_SPECS),
        "templateAssignments": sum(1 + len(roles) for roles in user_roles.values()) + (len(matched_users) - len(user_roles)),
        "exceptions": exceptions,
        "blockingErrors": project_errors,
        "_rows": rows,
        "_matched_users": matched_users,
        "_resolved_projects": resolved_projects,
        "_new_projects": new_projects,
        "_grants": grants,
        "_user_roles": user_roles,
    }


def preview_personnel_permission_workbook(content: bytes, *, actor: User | None = None) -> dict[str, Any]:
    preview = _preview(content)
    result = {key: value for key, value in preview.items() if not key.startswith("_")}
    result['previewToken'] = issue_receipt(preview, actor) if actor is not None else ''
    return result


def _ensure_templates(permission_map: dict[str, Permission]) -> dict[str, PermissionTemplate]:
    missing = sorted(MANAGED_PERMISSION_CODES - set(permission_map))
    if missing:
        raise PersonnelPermissionImportError("系统缺少权限点：" + "、".join(missing))
    templates: dict[str, PermissionTemplate] = {}
    for code, spec in TEMPLATE_SPECS.items():
        template = PermissionTemplate.query.filter_by(code=code).one_or_none()
        if not template:
            template = PermissionTemplate(code=code)
            db.session.add(template)
        template.name = spec["name"]
        template.description = spec["description"]
        template.enabled = True
        template.permissions = [permission_map[item] for item in sorted(spec["permissions"])]
        template.project_steps = []
        templates[code] = template
    db.session.flush()
    return templates


def _create_project(spec: dict[str, Any]) -> Project:
    project = Project.query.filter_by(source_key=spec["sourceKey"]).one_or_none()
    if not project:
        internal_code = "PERM-" + spec["sourceKey"].split(":", 1)[1].upper()
        project = Project(code=internal_code, source_key=spec["sourceKey"])
        db.session.add(project)
    project.name = spec["name"]
    project.department_id = spec["departmentId"]
    project.display_code = spec["projectCode"]
    project.number_code = spec["projectCode"]
    project.location = spec["location"]
    project.source_department = spec["sourceDepartment"]
    project.active = True
    db.session.flush()
    existing = {step.step_code: step for step in project.steps}
    for step_code, step_name in seed_data.STANDARD_STEPS:
        if step_code not in existing:
            db.session.add(ProjectStep(project_id=project.id, step_code=step_code, step_name=step_name))
        else:
            existing[step_code].step_name = step_name
    db.session.flush()
    return project


def apply_personnel_permission_workbook(
    content: bytes,
    *,
    expected_sha256: str,
    filename: str,
    actor: User,
    preview_token: str = '',
) -> dict[str, Any]:
    if not preview_token:
        raise PersonnelPermissionImportError("缺少有效预检凭证，请重新预检")
    try:
        lock_import_snapshot()
    except ValueError as exc:
        raise PersonnelPermissionImportError(str(exc)) from exc
    preview = _preview(content)
    if preview["sourceSha256"] != _text(expected_sha256).lower():
        raise PersonnelPermissionImportError("文件哈希与预检结果不一致，请重新预检")
    if not validate_receipt(preview_token, preview, actor):
        raise PersonnelPermissionImportError("预检已过期或人员、项目、授权配置发生变化，请重新预检")
    if preview["blockingErrors"]:
        raise PersonnelPermissionImportError("存在项目匹配歧义或未知项目，禁止部分写入")

    permission_map = {item.code: item for item in Permission.query.all()}
    templates = _ensure_templates(permission_map)
    project_by_key = dict(preview["_resolved_projects"])
    for key, spec in preview["_new_projects"].items():
        project_by_key[key] = _create_project(spec)

    step_by_project_code = {
        (step.project_id, step.step_code): step
        for step in ProjectStep.query.filter(
            ProjectStep.project_id.in_({project.id for project in project_by_key.values()}),
            ProjectStep.step_code.in_(MANAGED_STEP_CODES),
        ).all()
    }
    desired_by_user: dict[int, set[int]] = defaultdict(set)
    project_departments_by_user: dict[int, set[int]] = defaultdict(set)
    for user_id, key, step_code in preview["_grants"]:
        project = project_by_key[key]
        step = step_by_project_code.get((project.id, step_code))
        if not step:
            raise PersonnelPermissionImportError(f"项目 {project.name} 缺少环节 {step_code}")
        desired_by_user[user_id].add(step.id)
        if project.department_id:
            project_departments_by_user[user_id].add(project.department_id)

    matched_users = list(preview["_matched_users"].values())
    matched_user_ids = {user.id for user in matched_users}
    managed_current_rows = db.session.execute(
        user_project_permissions.select()
        .join(ProjectStep, ProjectStep.id == user_project_permissions.c.project_step_id)
        .where(
            user_project_permissions.c.user_id.in_(matched_user_ids),
            ProjectStep.step_code.in_(MANAGED_STEP_CODES),
        )
    ).fetchall() if matched_user_ids else []
    for row in managed_current_rows:
        db.session.execute(user_project_permissions.delete().where(
            user_project_permissions.c.user_id == int(row.user_id),
            user_project_permissions.c.project_step_id == int(row.project_step_id),
        ))

    for user in matched_users:
        roles = preview["_user_roles"].get(user.id, set())
        template_codes = {"business-basic"} | {ROLE_TO_TEMPLATE[role] for role in roles}
        preserved_templates = [template for template in user.permission_templates if template.code not in TEMPLATE_SPECS]
        user.permission_templates = preserved_templates + [templates[code] for code in sorted(template_codes)]
        wanted_permissions = set(TEMPLATE_SPECS["business-basic"]["permissions"])
        for role in roles:
            wanted_permissions.update(TEMPLATE_SPECS[ROLE_TO_TEMPLATE[role]]["permissions"])
        preserved = [permission for permission in user.permissions if permission.code not in MANAGED_PERMISSION_CODES]
        user.permissions = preserved + [permission_map[code] for code in sorted(wanted_permissions)]

        for step_id in sorted(desired_by_user.get(user.id, set())):
            db.session.execute(user_project_permissions.insert().values(user_id=user.id, project_step_id=step_id))
            step = db.session.get(ProjectStep, step_id)
            if user.department and step:
                if step not in user.department.project_steps:
                    user.department.project_steps.append(step)
                if step.project not in user.department.projects:
                    user.department.projects.append(step.project)
        if user.department:
            department_permission_codes = {permission.code for permission in user.department.permissions}
            for code in sorted(wanted_permissions - department_permission_codes):
                user.department.permissions.append(permission_map[code])

        current_data_departments = {
            int(row.department_id)
            for row in db.session.execute(user_data_departments.select().where(
                user_data_departments.c.user_id == user.id
            )).fetchall()
        }
        for department_id in sorted(project_departments_by_user.get(user.id, set()) - current_data_departments):
            db.session.execute(user_data_departments.insert().values(
                user_id=user.id,
                department_id=department_id,
                include_children=False,
                see_data=True,
                see_members=False,
                granted_by="personnel-permission-import",
                granted_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            ))

    public_summary = {key: value for key, value in preview.items() if not key.startswith("_")}
    batch = PermissionAppointmentImport(
        source_sha256=preview["sourceSha256"],
        source_name=_text(filename)[:255],
        summary=public_summary,
        exceptions=preview["exceptions"],
        applied_by_id=actor.id,
    )
    db.session.add(batch)
    db.session.flush()
    add_operation_audit(
        "organization.permission_appointment.import_replace",
        "permission_appointment_import",
        batch.id,
        category="admin",
        actor=actor,
        after={
            "sourceSha256": preview["sourceSha256"],
            "matchedPeopleCount": preview["matchedPeopleCount"],
            "grantCount": preview["grantCount"],
            "newProjectCount": preview["newProjectCount"],
            "ignoredRowCount": preview["ignoredRowCount"],
        },
    )
    db.session.commit()
    return {**public_summary, "batchId": batch.id}


__all__ = [
    "MANAGED_PERMISSION_CODES",
    "MANAGED_STEP_CODES",
    "PersonnelPermissionImportError",
    "TEMPLATE_SPECS",
    "apply_personnel_permission_workbook",
    "preview_personnel_permission_workbook",
]
