"""人员权限模板与权限 Excel 全量交换接口。

模板不参与运行时鉴权；保存模板时在同一事务中同步关联人员的实际功能权限。
多模板取合集并遵守所属部门上限，项目环节及数据范围保持独立。Excel 导入
仍先完成全量校验，再按工作簿精确替换模板和人员实际权限。
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_file
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from ..extensions import db
from ..report_correction_permissions import STORAGE_CODES as CORRECTION_GRANT_CODES
from ..models import (
    PermissionAppointmentImport,
    PermissionTemplate,
    Project,
    ProjectStep,
    User,
    permission_template_permissions,
    permission_template_project_steps,
    permission_template_users,
    user_action_permissions,
)
from ..personnel_permission_import import (
    PersonnelPermissionImportError,
    apply_personnel_permission_workbook,
    preview_personnel_permission_workbook,
)
from ..platform.audit import add_operation_audit
from ..platform.identity import user_has_org_wide_scope
from ..security import require_auth
from .admin import (
    PROJECT_AUTHORIZATION_STEP_CODES,
    _assignable_permissions,
    _department_authorized_permissions,
    _department_authorized_project_steps,
    _step_matches_permissions,
    _visible_project_steps_query,
    require_admin,
)

bp = Blueprint(
    "permission_templates",
    __name__,
    url_prefix="/api/admin/permission-templates",
)

EXPORT_TYPE = "lims-permission-template-personnel-full-replace"
SCHEMA_VERSION = "2"
LEGACY_SCHEMA_VERSION = "1"
MAX_IMPORT_BYTES = 10 * 1024 * 1024
TEMPLATE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{2,40}$")

SHEET_HEADERS = {
    "权限模板": ["模板编码", "模板名称", "说明", "是否启用"],
    "模板功能权限": ["模板编码", "权限编码", "权限名称"],
    "模板项目环节": [
        "模板编码", "项目内部编码", "项目名称", "环节编码", "环节名称", "项目环节ID",
    ],
    "人员清单": ["账号", "姓名", "部门编码", "部门名称", "角色", "是否启用"],
    "人员实际功能权限": ["账号", "姓名", "部门编码", "权限编码", "权限名称"],
    "人员套用模板": ["账号", "姓名", "部门编码", "模板编码", "模板名称"],
    "人员实际操作权限": ["账号", "姓名", "部门编码", "操作权限编码", "操作权限名称", "授权来源"],
    "人员实际项目环节": [
        "账号", "姓名", "部门编码", "项目内部编码", "项目名称", "环节编码", "环节名称", "项目环节ID",
    ],
    "异常清单": ["异常类型", "人员姓名", "项目编号", "说明", "导入批次", "导入时间"],
}

LEGACY_SHEET_HEADERS = {
    key: value for key, value in SHEET_HEADERS.items()
    if key not in {"人员套用模板", "人员实际操作权限", "异常清单"}
}


class WorkbookValidationError(ValueError):
    pass


def _error(message: str, data=None):
    return jsonify({"code": 1, "message": message, "data": data}), 200


def _template_payload(template: PermissionTemplate):
    return {
        "id": template.id,
        "code": template.code,
        "name": template.name,
        "description": template.description or "",
        "enabled": bool(template.enabled),
        "permissionCodes": sorted(permission.code for permission in template.permissions),
        "projectStepIds": sorted(
            step.id
            for step in template.project_steps
            if step.step_code in PROJECT_AUTHORIZATION_STEP_CODES
        ),
        "assignedUserCount": len(template.users),
        "updatedAt": template.updated_at.isoformat() if template.updated_at else "",
    }


def _template_catalog():
    permissions = _assignable_permissions()
    steps = _visible_project_steps_query().order_by(ProjectStep.project_id, ProjectStep.id).all()
    projects = (
        Project.query.filter_by(active=True)
        .order_by(Project.department_id, Project.name, Project.id)
        .all()
    )
    step_by_project_code = {
        (step.project_id, step.step_code): step.id for step in steps
    }
    from .. import seed_data
    from ..platform.identity import PROJECT_STEP_FUNCTION_PERMISSIONS

    return {
        "permissions": [
            {"code": item.code, "name": item.name, "ptype": item.ptype}
            for item in permissions
        ],
        "projects": [
            {
                "id": project.id,
                "code": project.display_code or project.number_code or project.code,
                "name": project.name,
                "department": project.department.name if project.department else "",
                "location": project.location or "",
                "sourceDepartment": project.source_department or "",
                "stepIds": [
                    step_by_project_code.get((project.id, code))
                    for code, _name in seed_data.PROJECT_AUTHORIZATION_STEPS
                ],
            }
            for project in projects
        ],
        "stepColumns": [
            {
                "code": code,
                "name": name,
                "requiredPermissionCodes": sorted(
                    PROJECT_STEP_FUNCTION_PERMISSIONS.get(code, set())
                ),
            }
            for code, name in seed_data.PROJECT_AUTHORIZATION_STEPS
        ],
        "allowedProjectStepIds": sorted(step.id for step in steps),
    }


def _validated_template_body(body):
    code = str(body.get("code") or "").strip()
    name = str(body.get("name") or "").strip()
    description = str(body.get("description") or "").strip()
    if not TEMPLATE_CODE_PATTERN.fullmatch(code):
        raise ValueError("模板编码须为 2-40 位字母、数字、点、下划线或短横线")
    if not name:
        raise ValueError("模板名称不能为空")
    if len(name) > 80 or len(description) > 300:
        raise ValueError("模板名称或说明超过允许长度")
    permission_codes = {
        str(value).strip() for value in body.get("permissionCodes", []) if str(value).strip()
    }
    step_ids = {
        int(value) for value in body.get("projectStepIds", []) if str(value).isdigit()
    }
    permissions = {item.code: item for item in _assignable_permissions()}
    steps = {item.id: item for item in _visible_project_steps_query().all()}
    if permission_codes - set(permissions):
        raise ValueError("模板包含无效功能权限")
    if step_ids - set(steps):
        raise ValueError("模板包含无效或已停用的项目环节")
    incompatible = {
        step_id for step_id in step_ids
        if not _step_matches_permissions(steps[step_id], permission_codes)
    }
    if incompatible:
        raise ValueError("模板项目环节缺少相应功能权限")
    return {
        "code": code,
        "name": name,
        "description": description,
        "enabled": bool(body.get("enabled", True)),
        "permissions": [permissions[value] for value in sorted(permission_codes)],
        "project_steps": [steps[value] for value in sorted(step_ids)],
    }


@bp.get("")
@require_auth
@require_admin
def list_permission_templates():
    catalog = _template_catalog()
    catalog["rows"] = [
        _template_payload(item)
        for item in PermissionTemplate.query.order_by(
            PermissionTemplate.enabled.desc(), PermissionTemplate.code
        ).all()
    ]
    return jsonify({"code": 0, "message": "ok", "data": catalog})


@bp.post("")
@require_auth
@require_admin
def create_permission_template():
    try:
        values = _validated_template_body(request.get_json(silent=True) or {})
    except ValueError as exc:
        return _error(str(exc))
    if PermissionTemplate.query.filter_by(code=values["code"]).first():
        return _error("模板编码已存在")
    template = PermissionTemplate(
        code=values["code"],
        name=values["name"],
        description=values["description"],
        enabled=values["enabled"],
    )
    template.permissions = values["permissions"]
    template.project_steps = values["project_steps"]
    db.session.add(template)
    db.session.flush()
    add_operation_audit(
        "organization.permission_template.create",
        "permission_template",
        template.id,
        category="admin",
        after=_template_payload(template),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "权限模板已创建", "data": _template_payload(template)})


@bp.put("/<int:template_id>")
@require_auth
@require_admin
def update_permission_template(template_id):
    template = db.session.get(PermissionTemplate, template_id)
    if not template:
        return _error("权限模板不存在")
    try:
        values = _validated_template_body(request.get_json(silent=True) or {})
    except ValueError as exc:
        return _error(str(exc))
    duplicate = PermissionTemplate.query.filter(
        PermissionTemplate.code == values["code"],
        PermissionTemplate.id != template.id,
    ).first()
    if duplicate:
        return _error("模板编码已存在")
    before = _template_payload(template)
    try:
        template.code = values["code"]
        template.name = values["name"]
        template.description = values["description"]
        template.enabled = values["enabled"]
        template.permissions = values["permissions"]
        template.project_steps = values["project_steps"]
        template.updated_at = datetime.utcnow()
        summary = _synchronize_template_members(template, before)
        payload = {**_template_payload(template), "syncSummary": summary}
        add_operation_audit(
            "organization.permission_template.update",
            "permission_template",
            template.id,
            category="admin",
            before=before,
            after=payload,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error("模板及关联人员权限同步失败，事务已回滚，请重试")
    return jsonify({"code": 0, "message": "权限模板及关联人员功能权限已同步保存", "data": payload})


def _synchronize_template_members(template: PermissionTemplate, before: dict):
    """Materialize the union into the existing authorization table, never project grants.

    Legacy rows have no per-permission source column. Codes contributed by the
    previous enabled template are template-managed; actual grants outside that
    set are preserved. Another enabled template keeps a shared code granted.
    Re-saving also reapplies missing codes from the current enabled template union.
    Deletion and full-workbook replacement deliberately retain their own semantics.
    """
    old_codes = set(before["permissionCodes"]) if before["enabled"] else set()
    permission_map = {p.code: p for p in _assignable_permissions()}
    department_caps = {}
    summary = {"assignedUserCount": 0, "updatedUserCount": 0, "departmentLimitedUserCount": 0}
    for user in sorted(template.users, key=lambda item: item.id):
        summary["assignedUserCount"] += 1
        current = {p.code: p for p in user.permissions}
        wanted = {p.code for item in user.permission_templates if item.enabled for p in item.permissions}
        if user_has_org_wide_scope(user):
            allowed = set(permission_map)
        elif user.department is None:
            allowed = set()
        else:
            if user.department_id not in department_caps:
                department_caps[user.department_id] = {
                    p.code for p in _department_authorized_permissions(user.department)
                }
            allowed = department_caps[user.department_id]
        blocked = wanted - allowed
        if blocked:
            summary["departmentLimitedUserCount"] += 1
        new_codes = (set(current) - old_codes) | (wanted & allowed)
        if new_codes == set(current):
            continue
        # Preserve hidden administrator/unrelated direct grants as existing rows.
        user.permissions = [current[code] if code in current else permission_map[code] for code in sorted(new_codes)]
        summary["updatedUserCount"] += 1
        add_operation_audit(
            "organization.permission_template.member_sync", "user", user.id,
            category="admin",
            before={"permissionCodes": sorted(current)},
            after={"permissionCodes": sorted(new_codes), "templateId": template.id,
                   "templateIds": sorted(t.id for t in user.permission_templates),
                   "departmentLimitedPermissionCodes": sorted(blocked),
                   "projectAndDataGrantsUnchanged": True},
        )
    return summary


@bp.delete("/<int:template_id>")
@require_auth
@require_admin
def delete_permission_template(template_id):
    template = db.session.get(PermissionTemplate, template_id)
    if not template:
        return _error("权限模板不存在")
    before = _template_payload(template)
    template.permissions = []
    template.project_steps = []
    db.session.flush()
    db.session.delete(template)
    add_operation_audit(
        "organization.permission_template.delete",
        "permission_template",
        template_id,
        category="admin",
        before=before,
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "权限模板已删除", "data": None})


def _excel_text(value):
    if value is None:
        return ""
    text = str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        return "'" + text
    return text


def _append(ws, values):
    ws.append([_excel_text(value) if isinstance(value, str) else value for value in values])


def _style_sheet(ws):
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="356AE6")
    for column in ws.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 42)
        ws.column_dimensions[column[0].column_letter].width = max(width, 12)


def _allowed_authorizations_for_user(user, *, permission_map=None, visible_steps=None):
    permission_map = permission_map or {
        item.code: item for item in _assignable_permissions()
    }
    visible_steps = visible_steps or _visible_project_steps_query().all()
    if user_has_org_wide_scope(user):
        return permission_map, {item.id: item for item in visible_steps}
    if not user.department:
        return {}, {}
    return (
        {
            item.code: item
            for item in _department_authorized_permissions(user.department)
        },
        {
            item.id: item
            for item in _department_authorized_project_steps(user.department)
        },
    )


@bp.get("/export")
@require_auth
@require_admin
def export_permission_workbook():
    workbook = Workbook()
    meta = workbook.active
    meta.title = "_META"
    meta.append(["键", "值"])
    meta.append(["exportType", EXPORT_TYPE])
    meta.append(["schemaVersion", SCHEMA_VERSION])
    meta.append(["exportedAt", datetime.utcnow().replace(microsecond=0).isoformat() + "Z"])

    sheets = {}
    for title, headers in SHEET_HEADERS.items():
        sheet = workbook.create_sheet(title)
        sheet.append(headers)
        sheets[title] = sheet

    templates = PermissionTemplate.query.order_by(PermissionTemplate.code).all()
    for template in templates:
        _append(sheets["权限模板"], [
            template.code, template.name, template.description or "", "是" if template.enabled else "否",
        ])
        for permission in sorted(template.permissions, key=lambda item: item.code):
            _append(sheets["模板功能权限"], [template.code, permission.code, permission.name])
        for step in sorted(template.project_steps, key=lambda item: (item.project_id, item.id)):
            if step.step_code not in PROJECT_AUTHORIZATION_STEP_CODES:
                continue
            _append(sheets["模板项目环节"], [
                template.code,
                step.project.code,
                step.project.name,
                step.step_code,
                step.step_name,
                step.id,
            ])

    users = User.query.order_by(User.account).all()
    from ..catalog import ACTION_PERMISSIONS, MODULE_IMPLIED_ACTIONS
    action_names = dict(ACTION_PERMISSIONS)
    for user in users:
        department = user.department
        allowed_permissions, allowed_steps = _allowed_authorizations_for_user(user)
        effective_permission_codes = {
            permission.code
            for permission in user.permissions
            if permission.code in allowed_permissions
        }
        _append(sheets["人员清单"], [
            user.account,
            user.name,
            department.code if department else "",
            department.name if department else "",
            user.role_name,
            "是" if user.enabled else "否",
        ])
        for template in sorted(user.permission_templates, key=lambda item: item.code):
            _append(sheets["人员套用模板"], [
                user.account,
                user.name,
                department.code if department else "",
                template.code,
                template.name,
            ])
        explicit_action_codes = {
            str(row.action_code)
            for row in db.session.execute(
                user_action_permissions.select().where(user_action_permissions.c.user_id == user.id)
            ).fetchall()
        }
        for action_code in user.action_codes():
            # Seal authority is appointed separately in organization membership.
            if action_code in ("report.seal.confirm", *CORRECTION_GRANT_CODES):
                continue
            _append(sheets["人员实际操作权限"], [
                user.account,
                user.name,
                department.code if department else "",
                action_code,
                action_names.get(action_code, action_code),
                "显式" if action_code in explicit_action_codes and action_code not in MODULE_IMPLIED_ACTIONS else "功能权限自动包含",
            ])
        for permission in sorted(user.permissions, key=lambda item: item.code):
            if permission.code == "system.user.view" or permission.code not in allowed_permissions:
                continue
            _append(sheets["人员实际功能权限"], [
                user.account,
                user.name,
                department.code if department else "",
                permission.code,
                permission.name,
            ])
        for step in sorted(user.project_steps, key=lambda item: (item.project_id, item.id)):
            if (
                step.step_code not in PROJECT_AUTHORIZATION_STEP_CODES
                or step.id not in allowed_steps
                or not _step_matches_permissions(step, effective_permission_codes)
            ):
                continue
            _append(sheets["人员实际项目环节"], [
                user.account,
                user.name,
                department.code if department else "",
                step.project.code,
                step.project.name,
                step.step_code,
                step.step_name,
                step.id,
            ])

    latest_import = PermissionAppointmentImport.query.order_by(
        PermissionAppointmentImport.id.desc()
    ).first()
    if latest_import:
        for item in latest_import.exceptions or []:
            _append(sheets["异常清单"], [
                item.get("type", ""),
                item.get("person", ""),
                item.get("projectCode", ""),
                item.get("detail", ""),
                latest_import.id,
                latest_import.created_at.isoformat(timespec="seconds") if latest_import.created_at else "",
            ])

    for sheet in workbook.worksheets:
        _style_sheet(sheet)
    content = io.BytesIO()
    workbook.save(content)
    content.seek(0)
    add_operation_audit(
        "organization.permission_template.export",
        "permission_template",
        "all",
        category="admin",
        after={"templateCount": len(templates), "userCount": len(users)},
    )
    db.session.commit()
    filename = f"人员权限模板与实际权限_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return send_file(
        content,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _plain_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > 1 and text[0] == "'" and text[1] in {"=", "+", "-", "@"}:
        return text[1:]
    return text


def _sheet_rows(workbook, title, *, headers=None):
    if title not in workbook.sheetnames:
        raise WorkbookValidationError(f"缺少工作表：{title}")
    sheet = workbook[title]
    actual = [_plain_text(cell.value) for cell in sheet[1]]
    expected = (headers or SHEET_HEADERS)[title]
    if actual != expected:
        raise WorkbookValidationError(f"工作表“{title}”表头不符合导出格式")
    rows = []
    for row_no, cells in enumerate(sheet.iter_rows(min_row=2), start=2):
        if any(cell.data_type == "f" for cell in cells):
            raise WorkbookValidationError(f"工作表“{title}”第 {row_no} 行不允许公式")
        values = [_plain_text(cell.value) for cell in cells[:len(expected)]]
        if any(values):
            rows.append((row_no, values))
    return rows


def _parse_enabled(value, *, location):
    normalized = _plain_text(value).lower()
    if normalized in {"是", "1", "true", "启用", "yes"}:
        return True
    if normalized in {"否", "0", "false", "停用", "no"}:
        return False
    raise WorkbookValidationError(f"{location} 的是否启用值无效")


def _validate_workbook(workbook):
    if "_META" not in workbook.sheetnames:
        raise WorkbookValidationError("缺少 _META 工作表，不能确认文件来源")
    meta_sheet = workbook["_META"]
    meta = {
        _plain_text(row[0].value): _plain_text(row[1].value)
        for row in meta_sheet.iter_rows(min_row=2)
        if len(row) >= 2 and row[0].value
    }
    version = meta.get("schemaVersion")
    if meta.get("exportType") != EXPORT_TYPE or version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise WorkbookValidationError("文件类型或版本不匹配，请使用本页面最新导出的 Excel")
    headers = SHEET_HEADERS if version == SCHEMA_VERSION else LEGACY_SHEET_HEADERS

    template_rows = _sheet_rows(workbook, "权限模板", headers=headers)
    template_specs = {}
    for row_no, row in template_rows:
        code, name, description, enabled = row
        if not TEMPLATE_CODE_PATTERN.fullmatch(code):
            raise WorkbookValidationError(f"权限模板第 {row_no} 行模板编码无效")
        if code in template_specs:
            raise WorkbookValidationError(f"权限模板第 {row_no} 行模板编码重复")
        if not name or len(name) > 80 or len(description) > 300:
            raise WorkbookValidationError(f"权限模板第 {row_no} 行名称或说明无效")
        template_specs[code] = {
            "name": name,
            "description": description,
            "enabled": _parse_enabled(enabled, location=f"权限模板第 {row_no} 行"),
            "permission_codes": set(),
            "step_keys": set(),
        }

    permission_map = {item.code: item for item in _assignable_permissions()}
    for row_no, row in _sheet_rows(workbook, "模板功能权限", headers=headers):
        template_code, permission_code, _permission_name = row
        if template_code not in template_specs:
            raise WorkbookValidationError(f"模板功能权限第 {row_no} 行引用了不存在的模板")
        if permission_code not in permission_map:
            raise WorkbookValidationError(f"模板功能权限第 {row_no} 行权限编码无效")
        template_specs[template_code]["permission_codes"].add(permission_code)

    visible_steps = _visible_project_steps_query().all()
    step_map = {(step.project.code, step.step_code): step for step in visible_steps}
    for row_no, row in _sheet_rows(workbook, "模板项目环节", headers=headers):
        template_code, project_code, _project_name, step_code, _step_name, _step_id = row
        if template_code not in template_specs:
            raise WorkbookValidationError(f"模板项目环节第 {row_no} 行引用了不存在的模板")
        key = (project_code, step_code)
        if key not in step_map:
            raise WorkbookValidationError(f"模板项目环节第 {row_no} 行项目或环节编码无效")
        template_specs[template_code]["step_keys"].add(key)

    for template_code, spec in template_specs.items():
        for key in spec["step_keys"]:
            if not _step_matches_permissions(step_map[key], spec["permission_codes"]):
                raise WorkbookValidationError(
                    f"模板“{template_code}”的项目环节缺少相应功能权限"
                )

    users = {item.account: item for item in User.query.all()}
    roster_accounts = set()
    for row_no, row in _sheet_rows(workbook, "人员清单", headers=headers):
        account, name, department_code, _department_name, _role, _enabled = row
        if account in roster_accounts:
            raise WorkbookValidationError(f"人员清单第 {row_no} 行账号重复")
        user = users.get(account)
        if not user:
            raise WorkbookValidationError(f"人员清单第 {row_no} 行账号不存在")
        actual_department_code = user.department.code if user.department else ""
        if name != user.name or department_code != actual_department_code:
            raise WorkbookValidationError(f"人员清单第 {row_no} 行人员或部门已变化，请重新导出")
        roster_accounts.add(account)
    if roster_accounts != set(users):
        missing = sorted(set(users) - roster_accounts)
        extra = sorted(roster_accounts - set(users))
        detail = "、".join((missing + extra)[:8])
        raise WorkbookValidationError(f"人员清单必须与当前系统全量一致：{detail}")

    user_permissions = {account: set() for account in users}
    for row_no, row in _sheet_rows(workbook, "人员实际功能权限", headers=headers):
        account, name, department_code, permission_code, _permission_name = row
        user = users.get(account)
        if not user or name != user.name or department_code != (user.department.code if user.department else ""):
            raise WorkbookValidationError(f"人员实际功能权限第 {row_no} 行人员信息无效")
        if permission_code not in permission_map:
            raise WorkbookValidationError(f"人员实际功能权限第 {row_no} 行权限编码无效")
        user_permissions[account].add(permission_code)

    user_steps = {account: set() for account in users}
    for row_no, row in _sheet_rows(workbook, "人员实际项目环节", headers=headers):
        account, name, department_code, project_code, _project_name, step_code, _step_name, _step_id = row
        user = users.get(account)
        if not user or name != user.name or department_code != (user.department.code if user.department else ""):
            raise WorkbookValidationError(f"人员实际项目环节第 {row_no} 行人员信息无效")
        key = (project_code, step_code)
        if key not in step_map:
            raise WorkbookValidationError(f"人员实际项目环节第 {row_no} 行项目或环节编码无效")
        user_steps[account].add(key)

    for account, user in users.items():
        allowed_permissions, allowed_steps = _allowed_authorizations_for_user(
            user,
            permission_map=permission_map,
            visible_steps=visible_steps,
        )
        if user_permissions[account] - set(allowed_permissions):
            raise WorkbookValidationError(f"人员“{account}”包含超出所属部门上限的功能权限")
        selected_steps = [step_map[key] for key in user_steps[account]]
        if {item.id for item in selected_steps} - set(allowed_steps):
            raise WorkbookValidationError(f"人员“{account}”包含超出所属部门上限的项目环节")
        for step in selected_steps:
            if not _step_matches_permissions(step, user_permissions[account]):
                raise WorkbookValidationError(f"人员“{account}”的项目环节缺少相应功能权限")

    user_templates = {account: set() for account in users}
    explicit_user_actions = {account: set() for account in users}
    if version == SCHEMA_VERSION:
        for row_no, row in _sheet_rows(workbook, "人员套用模板", headers=headers):
            account, name, department_code, template_code, _template_name = row
            user = users.get(account)
            if not user or name != user.name or department_code != (user.department.code if user.department else ""):
                raise WorkbookValidationError(f"人员套用模板第 {row_no} 行人员信息无效")
            if template_code not in template_specs:
                raise WorkbookValidationError(f"人员套用模板第 {row_no} 行模板编码无效")
            user_templates[account].add(template_code)
        from ..catalog import ACTION_PERMISSIONS, MODULE_IMPLIED_ACTIONS
        known_action_codes = {code for code, _name in ACTION_PERMISSIONS} | set(MODULE_IMPLIED_ACTIONS)
        for row_no, row in _sheet_rows(workbook, "人员实际操作权限", headers=headers):
            account, name, department_code, action_code, _action_name, source = row
            user = users.get(account)
            if not user or name != user.name or department_code != (user.department.code if user.department else ""):
                raise WorkbookValidationError(f"人员实际操作权限第 {row_no} 行人员信息无效")
            if action_code not in known_action_codes:
                raise WorkbookValidationError(f"人员实际操作权限第 {row_no} 行操作权限编码无效")
            if source == "显式" and action_code not in MODULE_IMPLIED_ACTIONS:
                explicit_user_actions[account].add(action_code)
            elif source not in {"显式", "功能权限自动包含"}:
                raise WorkbookValidationError(f"人员实际操作权限第 {row_no} 行授权来源无效")
        # 异常清单是导出证据的一部分，不参与权限写入，但仍必须执行与其余
        # 工作表相同的表头和公式校验，防止“整表校验”存在绕过页。
        _sheet_rows(workbook, "异常清单", headers=headers)

    return {
        "schema_version": version,
        "template_specs": template_specs,
        "permission_map": permission_map,
        "step_map": step_map,
        "users": users,
        "user_permissions": user_permissions,
        "user_steps": user_steps,
        "user_templates": user_templates,
        "explicit_user_actions": explicit_user_actions,
    }


@bp.post("/import")
@require_auth
@require_admin
def import_permission_workbook():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return _error("请选择由本页面导出的 Excel 文件")
    if request.form.get("replace") != "1":
        return _error("必须明确确认全量替换")
    content = uploaded.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        return _error("Excel 文件超过 10MB 限制")
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=False, read_only=False)
        parsed = _validate_workbook(workbook)
    except WorkbookValidationError as exc:
        db.session.rollback()
        return _error(str(exc))
    except Exception:
        db.session.rollback()
        return _error("Excel 无法解析，请使用本页面最新导出的原格式文件")

    try:
        db.session.execute(permission_template_users.delete())
        db.session.execute(permission_template_permissions.delete())
        db.session.execute(permission_template_project_steps.delete())
        PermissionTemplate.query.delete(synchronize_session=False)
        db.session.flush()

        imported_templates = {}
        for code, spec in sorted(parsed["template_specs"].items()):
            template = PermissionTemplate(
                code=code,
                name=spec["name"],
                description=spec["description"],
                enabled=spec["enabled"],
            )
            template.permissions = [
                parsed["permission_map"][permission_code]
                for permission_code in sorted(spec["permission_codes"])
            ]
            template.project_steps = [
                parsed["step_map"][key] for key in sorted(spec["step_keys"])
            ]
            db.session.add(template)
            imported_templates[code] = template
        db.session.flush()

        for account, user in parsed["users"].items():
            hidden_permission = next(
                (item for item in user.permissions if item.code == "system.user.view"),
                None,
            )
            user.permissions = [
                parsed["permission_map"][code]
                for code in sorted(parsed["user_permissions"][account])
            ]
            if hidden_permission and hidden_permission not in user.permissions:
                user.permissions.append(hidden_permission)
            hidden_steps = [
                item for item in user.project_steps
                if item.step_code not in PROJECT_AUTHORIZATION_STEP_CODES
            ]
            user.project_steps = hidden_steps + [
                parsed["step_map"][key]
                for key in sorted(parsed["user_steps"][account])
            ]
            if parsed["schema_version"] == SCHEMA_VERSION:
                user.permission_templates = [
                    imported_templates[code]
                    for code in sorted(parsed["user_templates"][account])
                ]
                STORAGE_CODES = ()
                db.session.execute(user_action_permissions.delete().where(
                    user_action_permissions.c.user_id == user.id,
                    user_action_permissions.c.action_code.notin_((*STORAGE_CODES, "report.seal.confirm", *CORRECTION_GRANT_CODES)),
                ))
                for action_code in sorted(parsed["explicit_user_actions"][account]):
                    db.session.execute(user_action_permissions.insert().values(
                        user_id=user.id,
                        action_code=action_code,
                    ))

        add_operation_audit(
            "organization.permission_template.import_replace",
            "permission_template",
            "all",
            category="admin",
            after={
                "templateCount": len(parsed["template_specs"]),
                "userCount": len(parsed["users"]),
                "permissionAssignmentCount": sum(
                    len(items) for items in parsed["user_permissions"].values()
                ),
                "projectStepAssignmentCount": sum(
                    len(items) for items in parsed["user_steps"].values()
                ),
                "importedBy": g.current_user.account,
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error("全量替换失败，事务已回滚，数据库未发生部分写入")

    return jsonify({
        "code": 0,
        "message": "权限模板及人员实际权限已全量替换",
        "data": {
            "templateCount": len(parsed["template_specs"]),
            "userCount": len(parsed["users"]),
        },
    })


def _uploaded_content():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        raise PersonnelPermissionImportError("请选择人员权限任命表 Excel 文件")
    content = uploaded.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise PersonnelPermissionImportError("Excel 文件超过 10MB 限制")
    return uploaded, content


@bp.post("/appointment-import/preview")
@require_auth
@require_admin
def preview_appointment_import():
    try:
        _uploaded, content = _uploaded_content()
        data = preview_personnel_permission_workbook(content, actor=g.current_user)
    except PersonnelPermissionImportError as exc:
        db.session.rollback()
        return _error(str(exc))
    return jsonify({"code": 0, "message": "任命表预检完成，尚未写入数据库", "data": data})


@bp.post("/appointment-import/apply")
@require_auth
@require_admin
def apply_appointment_import():
    if request.form.get("replaceScope") != "report-managed":
        return _error("必须明确选择仅替换报告相关权限")
    try:
        uploaded, content = _uploaded_content()
        data = apply_personnel_permission_workbook(
            content,
            expected_sha256=request.form.get("sourceSha256") or "",
            filename=uploaded.filename,
            actor=g.current_user,
            preview_token=request.form.get("previewToken") or "",
        )
    except PersonnelPermissionImportError as exc:
        db.session.rollback()
        return _error(str(exc))
    except Exception:
        db.session.rollback()
        return _error("任命表导入失败，事务已回滚，数据库未发生部分写入")
    return jsonify({"code": 0, "message": "人员权限模板和项目环节授权已更新", "data": data})
