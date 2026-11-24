"""用户与权限管理接口 — 超级管理员（拥有 system.user.view）可分配其他用户的权限。

权限不再写死在账号上，而是由超管动态分配：功能授权、审批事项授权、数据授权、部门、角色。
"""
from ..organization_privileges import has_full_platform_authority
import secrets
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, g, jsonify, request

from .. import catalog, seed_data
from ..multi_stage_approval import normalize_stages
from ..applications.customer_service import (
    apply_external_scheme,
    unpublish_external_scheme_for_project,
)
from ..applications.quality_resources import (
    map_capability_entry_departments,
    move_linked_personnel_department,
    synchronize_personnel_record,
)
from ..platform.audit import add_operation_audit
from ..platform.identity import (
    PROJECT_STEP_FUNCTION_PERMISSIONS,
    department_has_org_wide_scope,
    project_for_report,
    project_step_matches_permissions,
    replace_standard_authorizations,
    scoped_standard_items,
    standard_authorization_payload,
    synchronize_user_department,
    user_has_org_wide_scope,
)
from ..admin_corrections.existing import audited_form
from ..extensions import db
from .. import equipment_authorization
from ..platform.identity.login_security import initial_password, reset_initial_password
from ..models import (
    CapabilityEntry,
    CapabilityImportBatch,
    Department,
    ExternalScheme,
    Permission,
    PermissionTemplate,
    Personnel,
    Project,
    ProjectStep,
    Report,
    User,
    department_permissions,
    department_project_permissions,
    department_project_step_permissions,
    user_action_permissions,
    user_data_departments,
    user_data_sites,
    user_standard_denials,
)
from ..project_workflow import (
    PROJECT_WORKFLOW_STEPS,
    advance_skipped_project_steps,
    normalize_skipped_steps,
)
from ..security import hash_password, require_auth

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

EXTERNAL_SCHEME_FIELDS = {
    "externalPublished": "published",
    "externalSlug": "slug",
    "externalPublicTitle": "public_title",
    "externalSubtitle": "subtitle",
    "externalSummary": "summary",
    "externalDescription": "description",
    "externalCategory": "category",
    "externalCoverUrl": "cover_url",
    "externalPriceMode": "price_mode",
    "externalPriceMin": "price_min",
    "externalPriceMax": "price_max",
    "externalPriceUnit": "price_unit",
    "externalOriginalPrice": "original_price",
    "externalServiceCycleText": "service_cycle_text",
    "externalTurnaroundDays": "turnaround_days",
    "externalFeatureTags": "feature_tags",
    "externalDeliverables": "deliverables",
    "externalPricingRules": "pricing_rules",
    "externalDisplayOrder": "display_order",
    # Current ProjectConfigPage contract.
    "title": "public_title",
    "summary": "summary",
    "category": "category",
    "tags": "feature_tags",
    "priceType": "price_mode",
    "priceMin": "price_min",
    "priceMax": "price_max",
    "priceUnit": "price_unit",
    "originalPrice": "original_price",
    "turnaroundDays": "turnaround_days",
    "promotion": "promotion",
    "featured": "featured",
    "sort": "display_order",
    "detail": "detail",
    "sampleRequirements": "sample_requirements",
    "contactPhone": "contact_phone",
}


def _external_values(body):
    nested = body.get("externalDisplay")
    values = dict(nested) if isinstance(nested, dict) else {}
    for flat, field in EXTERNAL_SCHEME_FIELDS.items():
        if flat in body:
            values[field] = body.get(flat)
    return values


def _external_money(value, label):
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label}格式不正确") from None
    if result < 0:
        raise ValueError(f"{label}不能小于 0")
    return result


def _default_external_slug(project):
    source = str(project.display_code or project.number_code or project.code or project.id).lower()
    slug = "-".join(part for part in __import__("re").sub(r"[^a-z0-9]+", "-", source).split("-") if part)
    return slug or f"project-{project.id}"


def _apply_external_scheme(project, body, user):
    return apply_external_scheme(project, body, user)


def _external_project_fields(project):
    row = ExternalScheme.query.filter_by(project_id=project.id).first()
    result = {
        "externalPublished": bool(row.published) if row else False,
        "externalSlug": row.slug if row else "",
        "externalPublicTitle": row.public_title if row else "",
        "externalSubtitle": row.subtitle or "" if row else "",
        "externalSummary": row.summary or "" if row else "",
        "externalDescription": row.description or "" if row else "",
        "externalCategory": row.category or "" if row else "",
        "externalCoverUrl": row.cover_url or "" if row else "",
        "externalPriceMode": row.price_mode or "quote" if row else "quote",
        "externalPriceMin": float(row.price_min) if row and row.price_min is not None else None,
        "externalPriceMax": float(row.price_max) if row and row.price_max is not None else None,
        "externalPriceUnit": row.price_unit or "" if row else "",
        "externalOriginalPrice": float(row.original_price) if row and row.original_price is not None else None,
        "externalServiceCycleText": row.service_cycle_text or "" if row else "",
        "externalTurnaroundDays": row.turnaround_days if row else None,
        "externalFeatureTags": row.feature_tags if row and isinstance(row.feature_tags, list) else [],
        "externalDeliverables": row.deliverables if row and isinstance(row.deliverables, list) else [],
        "externalPricingRules": row.pricing_rules if row and isinstance(row.pricing_rules, (dict, list)) else {},
        "externalDisplayOrder": int(row.display_order or 0) if row else 0,
    }
    result.update({
        "title": row.public_title if row else "",
        "externalTitle": row.public_title if row else "",
        "summary": row.summary or "" if row else "",
        "category": row.category or "" if row else "",
        "tags": row.feature_tags if row and isinstance(row.feature_tags, list) else [],
        "priceType": (
            "negotiable" if not row or row.price_mode == "quote" else row.price_mode
        ),
        "priceMin": float(row.price_min) if row and row.price_min is not None else None,
        "priceMax": float(row.price_max) if row and row.price_max is not None else None,
        "priceUnit": row.price_unit or "" if row else "",
        "originalPrice": float(row.original_price) if row and row.original_price is not None else None,
        "turnaroundDays": row.turnaround_days if row else None,
        "promotion": row.promotion or "" if row else "",
        "featured": bool(row.featured) if row else False,
        "sort": int(row.display_order or 0) if row else 0,
        "detail": row.detail or row.description or "" if row else "",
        "sampleRequirements": row.sample_requirements or "" if row else "",
        "contactPhone": row.contact_phone or "" if row else "",
    })
    return result


def require_admin(fn):
    """需具备用户管理权限（system.user.view），即超级管理员。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from ..admin_corrections.existing import active as correcting
        if not correcting("projects") and "system.user.view" not in g.current_user.permission_codes():
            return jsonify({"code": 403, "message": "无用户管理权限", "data": None}), 200
        return fn(*args, **kwargs)

    return wrapper


def require_project_maintenance(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from ..admin_corrections import can_correct_business_data
        if can_correct_business_data(g.current_user):
            return fn(*args, **kwargs)
        return require_admin(fn)(*args, **kwargs)
    return wrapper


def _user_brief(u: User):
    return {
        "id": u.id,
        "account": u.account,
        "name": u.name,
        "roleKey": u.role_key,
        "roleName": u.role_name,
        "department": u.department.name if u.department else "",
        "departmentId": u.department_id,
        "dataScope": u.data_scope(),
        "permissionCount": len(u.permissions),
        "actionCount": len(u.action_codes()),
        "enabled": u.enabled,
    }


def _user_grants(u: User):
    """数据授权明细（含 看数据/看成员/含子部门/留痕）。"""
    rows = db.session.execute(
        user_data_departments.select().where(user_data_departments.c.user_id == u.id)
    ).fetchall()
    name_by_id = {d.id: d.name for d in Department.query.all()}
    return [{
        "departmentId": r.department_id, "departmentName": name_by_id.get(r.department_id, ""),
        "seeData": bool(r.see_data), "seeMembers": bool(r.see_members),
        "includeChildren": bool(r.include_children), "grantedBy": r.granted_by, "grantedAt": r.granted_at,
    } for r in rows]


def _user_detail(u: User):
    return {
        **_user_brief(u),
        "homePath": u.home_path,
        "eSignature": u.e_signature or "",
        "permissions": u.permission_codes(),
        "actionPermissions": u.action_codes(),
        # 项目授权（已授权的项目步骤 id）
        "projectStepIds": u.project_step_ids(),
        # 标准按所属部门默认全部授权，仅返回管理员取消后的有效集合。
        "standardAuthorization": standard_authorization_payload(u),
        # 数据授权（跨部门的部门 id 集合 + 站点集合）
        "dataDepartmentIds": [d.id for d in u.data_departments],
        "dataGrants": _user_grants(u),
        "dataSites": u.data_site_names(),
    }


PERSONNEL_PROFILE_FIELDS = {
    "gender": "gender",
    "education": "education",
    "title": "title",
    "major": "major",
    "gradTime": "grad_time",
    "position": "position",
    "testScope": "test_scope",
    "checkScope": "check_scope",
    "remark": "remark",
    "birthDate": "birth_date",
    "mobile": "mobile",
    "ethnicity": "ethnicity",
    "nativePlace": "native_place",
    "political": "political",
    "school": "school",
    "workStartTime": "work_start_time",
    "joinTime": "join_time",
}


def _synchronize_personnel_record(user: User, profile: dict | None = None) -> Personnel:
    return synchronize_personnel_record(user, profile)


def _project_master_row(project: Project) -> dict:
    config = project.workflow_config if isinstance(project.workflow_config, dict) else {}
    skipped = set(normalize_skipped_steps(config.get("skippedSteps")))
    department_name = project.department.name if project.department else ""
    test_location = str(config.get("testLocation") or project.location or "").strip()
    return {
        "id": project.id,
        "code": project.display_code or project.number_code or project.code,
        "name": project.name,
        "departmentId": project.department_id,
        "department": department_name,
        "location": test_location,
        "reportTitle": str(config.get("reportTitle") or "").strip(),
        "centerPrefix": str(config.get("centerPrefix") or "").strip(),
        "testCategory": str(config.get("testCategory") or "").strip(),
        "reportType": str(config.get("reportType") or config.get("reportFormat") or "").strip(),
        "testDept": str(config.get("testDept") or department_name).strip(),
        "detectionParameters": str(config.get("detectionParameters") or project.name or "").strip(),
        "sampleAmount": str(config.get("sampleAmount") or "").strip(),
        "sampleStatus": str(config.get("sampleStatus") or "").strip(),
        "testLocation": test_location,
        "active": bool(project.active),
        "skippedSteps": [
            item["code"] for item in PROJECT_WORKFLOW_STEPS if item["code"] in skipped
        ],
        "workflowSteps": [
            {**item, "skipped": item["code"] in skipped}
            for item in PROJECT_WORKFLOW_STEPS
        ],
        "reviewStages": normalize_stages(config.get("reviewStages"), "审核", "reviewer"),
        "approvalStages": normalize_stages(config.get("approvalStages"), "批准", "approver"),
        **_external_project_fields(project),
    }


def _project_code_conflict(code: str, *, exclude_id: int | None = None) -> bool:
    wanted = code.strip().upper()
    for project in Project.query.all():
        if exclude_id is not None and project.id == exclude_id:
            continue
        values = {
            str(value or "").strip().upper()
            for value in (
                project.code,
                project.display_code,
                project.number_code,
                *(project.code_aliases or []),
            )
            if value
        }
        if wanted in values:
            return True
    return False


def _ensure_project_steps(project: Project) -> None:
    by_code = {step.step_code: step for step in project.steps}
    for step_code, step_name in seed_data.STANDARD_STEPS:
        if step_code not in by_code:
            project.steps.append(ProjectStep(step_code=step_code, step_name=step_name))


def _grant_new_project_to_root(project: Project) -> None:
    root_departments = Department.query.filter(
        (Department.code == "ROOT") | (Department.name == "示例检测机构")
    ).all()
    for department in root_departments:
        if project not in department.projects:
            department.projects.append(project)
        for step in project.steps:
            if step not in department.project_steps:
                department.project_steps.append(step)
    for user in User.query.all():
        if user_has_org_wide_scope(user):
            for step in project.steps:
                if step not in user.project_steps:
                    user.project_steps.append(step)


def _apply_project_workflow_to_current_reports(project: Project) -> int:
    advanced_count = 0
    for report in Report.query.filter(Report.voided.is_(False)).all():
        matched = project_for_report(report)
        if matched is None or matched.id != project.id:
            continue
        before = report.to_row()
        skipped = advance_skipped_project_steps(report)
        if not skipped:
            continue
        advanced_count += 1
        add_operation_audit(
            "system.project.workflow.apply",
            "report",
            report.report_no,
            category="workflow",
            before=before,
            after=report.to_row(),
            message=f"项目流程自动跳过：{'、'.join(skipped)}",
        )
    return advanced_count


@bp.get("/project-masters")
@require_auth
def list_project_masters():
    from ..admin_corrections import can_correct_business_data
    if not can_correct_business_data(g.current_user) and "system.user.view" not in g.current_user.permission_codes():
        return jsonify(code=403, message="无检测项目查看权限", data=None), 403
    keyword = str(request.args.get("keyword") or "").strip().lower()
    include_inactive = str(request.args.get("includeInactive") or "").lower() in {
        "1", "true", "yes",
    }
    query = Project.query
    if not include_inactive:
        query = query.filter(Project.active.is_(True))
    rows = query.order_by(Project.active.desc(), Project.department_id, Project.name, Project.id).all()
    if keyword:
        rows = [
            project
            for project in rows
            if keyword in (
                f"{project.display_code or project.number_code or project.code} "
                f"{project.name} {project.department.name if project.department else ''}"
            ).lower()
        ]
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "rows": [_project_master_row(project) for project in rows],
            "workflowSteps": PROJECT_WORKFLOW_STEPS,
            "departments": [
                {"id": department.id, "name": department.name}
                for department in Department.query.order_by(Department.id).all()
            ],
        },
    })


@bp.get("/portal-service-catalog/diagnostics")
@require_auth
@require_admin
def portal_service_catalog_diagnostics():
    from ..functions.service_catalog import public_catalog_diagnostics

    return jsonify({"code": 0, "message": "ok", "data": public_catalog_diagnostics()})


@bp.post("/portal-service-catalog/sync")
@require_auth
@require_admin
def portal_service_catalog_sync():
    from ..functions.service_catalog import sync_catalog

    body = request.get_json(silent=True) or {}
    apply_changes = bool(body.get("apply"))
    result = sync_catalog(apply_changes=apply_changes, actor=g.current_user)
    return jsonify({
        "code": 0,
        "message": "目录同步完成" if apply_changes else "目录分析完成",
        "data": result,
    })


@bp.post("/project-masters")
@require_auth
@require_admin
def create_project_master():
    body = request.get_json(silent=True) or {}
    code = str(body.get("code") or "").strip().upper()
    name = str(body.get("name") or "").strip()
    department = db.session.get(Department, body.get("departmentId"))
    if not code or not name or department is None:
        return jsonify({"code": 1, "message": "项目编号、项目名称和所属部门均为必填", "data": None}), 200
    if _project_code_conflict(code):
        return jsonify({"code": 1, "message": f"项目编号「{code}」已使用，不能重复", "data": None}), 200
    project = Project(
        code=code,
        display_code=code,
        number_code=code,
        name=name,
        department=department,
        source_department=department.name,
        source_key=f"custom:{uuid.uuid4().hex}",
        location=str(body.get("testLocation") or body.get("location") or "").strip(),
        workflow_config={
            "skippedSteps": normalize_skipped_steps(body.get("skippedSteps")),
            "reviewStages": normalize_stages(body.get("reviewStages"), "审核", "reviewer"),
            "approvalStages": normalize_stages(body.get("approvalStages"), "批准", "approver"),
            "reportTitle": str(body.get("reportTitle") or "").strip(),
            "centerPrefix": str(body.get("centerPrefix") or "").strip(),
            "testCategory": str(body.get("testCategory") or "").strip(),
            "reportType": str(body.get("reportType") or body.get("reportFormat") or "").strip(),
            "testDept": department.name,
            "detectionParameters": str(body.get("detectionParameters") or "").strip(),
            "sampleAmount": str(body.get("sampleAmount") or "").strip(),
            "sampleStatus": str(body.get("sampleStatus") or "").strip(),
            "testLocation": str(body.get("testLocation") or body.get("location") or "").strip(),
        },
        code_aliases=[],
        active=True,
    )
    db.session.add(project)
    _ensure_project_steps(project)
    db.session.flush()
    try:
        _apply_external_scheme(project, body, g.current_user)
        db.session.flush()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    _grant_new_project_to_root(project)
    add_operation_audit(
        "system.project.create", "project", str(project.id),
        category="system", after=_project_master_row(project),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "检测项目已新增", "data": _project_master_row(project)})


@bp.put("/project-masters/<int:project_id>")
@require_auth
@audited_form("projects", "project_id")
@require_project_maintenance
def update_project_master(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return jsonify({"code": 1, "message": "检测项目不存在", "data": None}), 200
    body = request.get_json(silent=True) or {}
    code = str(body.get("code") or "").strip().upper()
    name = str(body.get("name") or "").strip()
    department = db.session.get(Department, body.get("departmentId"))
    if not code or not name or department is None:
        return jsonify({"code": 1, "message": "项目编号、项目名称和所属部门均为必填", "data": None}), 200
    if _project_code_conflict(code, exclude_id=project.id):
        return jsonify({"code": 1, "message": f"项目编号「{code}」已使用，不能重复", "data": None}), 200
    before = _project_master_row(project)
    old_visible = project.display_code or project.number_code or project.code
    aliases = [str(value) for value in (project.code_aliases or []) if value]
    if old_visible and old_visible != code and old_visible not in aliases:
        aliases.append(old_visible)
    project.code_aliases = aliases
    project.display_code = code
    project.number_code = code
    project.name = name
    project.department = department
    project.source_department = department.name
    project.location = str(body.get("testLocation") or body.get("location") or "").strip()
    project.workflow_config = {
        "skippedSteps": normalize_skipped_steps(body.get("skippedSteps")),
        "reviewStages": normalize_stages(body.get("reviewStages"), "审核", "reviewer"),
        "approvalStages": normalize_stages(body.get("approvalStages"), "批准", "approver"),
        "reportTitle": str(body.get("reportTitle") or "").strip(),
        "centerPrefix": str(body.get("centerPrefix") or "").strip(),
        "testCategory": str(body.get("testCategory") or "").strip(),
        "reportType": str(body.get("reportType") or body.get("reportFormat") or "").strip(),
        "testDept": department.name,
        "detectionParameters": str(body.get("detectionParameters") or "").strip(),
        "sampleAmount": str(body.get("sampleAmount") or "").strip(),
        "sampleStatus": str(body.get("sampleStatus") or "").strip(),
        "testLocation": project.location,
    }
    project.active = bool(body.get("active", True))
    _ensure_project_steps(project)
    db.session.flush()
    if project.active:
        _grant_new_project_to_root(project)
    try:
        _apply_external_scheme(project, body, g.current_user)
        db.session.flush()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    advanced_report_count = (
        _apply_project_workflow_to_current_reports(project)
        if project.active else 0
    )
    add_operation_audit(
        "system.project.update", "project", str(project.id),
        category="system", before=before, after=_project_master_row(project),
    )
    db.session.commit()
    message = "检测项目已保存"
    if advanced_report_count:
        message += f"，并按新流程推进 {advanced_report_count} 份在办报告"
    return jsonify({"code": 0, "message": message, "data": _project_master_row(project)})


@bp.delete("/project-masters/<int:project_id>")
@require_auth
@require_admin
def delete_project_master(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return jsonify({"code": 1, "message": "检测项目不存在", "data": None}), 200
    before = _project_master_row(project)
    project.active = False
    unpublish_external_scheme_for_project(project.id, g.current_user)
    add_operation_audit(
        "system.project.delete", "project", str(project.id),
        category="system", before=before, after=_project_master_row(project),
    )
    db.session.commit()
    return jsonify({
        "code": 0,
        "message": "检测项目已删除；历史单据和审计记录已保留",
        "data": _project_master_row(project),
    })


def _assignable_permissions():
    """用户管理已下线；其旧权限点仅保留给系统管理员做接口鉴权。"""
    return [
        permission
        for permission in Permission.query.order_by(Permission.code).all()
        if permission.code not in {"system.user.view", "report.release.view"}
    ]


def _department_authorized_permissions(department: Department):
    if department_has_org_wide_scope(department):
        return _assignable_permissions()
    return [
        permission
        for permission in department.permissions
        if permission.code not in {"system.user.view", "report.release.view"}
    ]


def _department_authorized_projects(department: Department):
    query = Project.query.filter_by(active=True)
    if department_has_org_wide_scope(department):
        return query.order_by(Project.department_id, Project.name, Project.id).all()
    authorized_ids = {project.id for project in department.projects}
    return [
        project
        for project in query.order_by(Project.department_id, Project.name, Project.id).all()
        if project.id in authorized_ids
    ]


PROJECT_AUTHORIZATION_STEP_CODES = {
    code for code, _ in seed_data.PROJECT_AUTHORIZATION_STEPS
}


def _step_matches_permissions(step: ProjectStep, permission_codes: set[str]) -> bool:
    return project_step_matches_permissions(step, permission_codes)


def _visible_project_steps_query():
    return (
        ProjectStep.query.join(Project)
        .filter(
            Project.active.is_(True),
            ProjectStep.step_code.in_(PROJECT_AUTHORIZATION_STEP_CODES),
        )
    )


def _department_authorized_project_steps(department: Department):
    query = _visible_project_steps_query()
    if department_has_org_wide_scope(department):
        return query.order_by(ProjectStep.project_id, ProjectStep.id).all()
    department_permission_codes = {
        permission.code for permission in _department_authorized_permissions(department)
    }
    authorized_project_ids = {
        project.id for project in department.projects if project.active
    }
    return [
        step
        for step in query.order_by(ProjectStep.project_id, ProjectStep.id).all()
        if (
            step.project_id in authorized_project_ids
            and _step_matches_permissions(step, department_permission_codes)
        )
    ]


def _authorization_catalog_payload(
    department: Department,
    *,
    user: User | None = None,
):
    org_wide_user = bool(user and user_has_org_wide_scope(user))
    # 编辑部门时目录必须始终完整，当前部门授权仅决定“已选项”；
    # 编辑人员时才以部门授权作为可选上限。
    if user is None or org_wide_user:
        allowed_permissions = _assignable_permissions()
        allowed_projects = (
            Project.query.filter_by(active=True)
            .order_by(Project.department_id, Project.name, Project.id)
            .all()
        )
        allowed_project_steps = _visible_project_steps_query().all()
    else:
        allowed_permissions = _department_authorized_permissions(department)
        allowed_projects = _department_authorized_projects(department)
        allowed_project_steps = _department_authorized_project_steps(department)
    selected_permissions = (
        sorted(
            {
                code
                for code in user.permission_codes()
                if code in {permission.code for permission in allowed_permissions}
            }
        )
        if user
        else sorted(
            permission.code
            for permission in (
                _assignable_permissions()
                if department_has_org_wide_scope(department)
                else _department_authorized_permissions(department)
            )
        )
    )
    allowed_step_ids = {step.id for step in allowed_project_steps}
    selected_project_step_ids = (
        sorted(
            {step.id for step in user.project_steps}
            & allowed_step_ids
        )
        if user
        else sorted(
            step.id
            for step in (
                _visible_project_steps_query().all()
                if department_has_org_wide_scope(department)
                else _department_authorized_project_steps(department)
            )
        )
    )
    if user:
        selected_project_ids = sorted({
            step.project_id
            for step in ProjectStep.query.filter(
                ProjectStep.id.in_(selected_project_step_ids)
            ).all()
        }) if selected_project_step_ids else []
    else:
        selected_project_ids = sorted(
            project.id
            for project in (
                Project.query.filter_by(active=True).all()
                if department_has_org_wide_scope(department)
                else department.projects
            )
            if project.active
        )
    step_columns = [
        {
            "code": code,
            "name": name,
            "requiredPermissionCodes": sorted(
                PROJECT_STEP_FUNCTION_PERMISSIONS.get(code, set())
            ),
        }
        for code, name in seed_data.PROJECT_AUTHORIZATION_STEPS
    ]
    return {
        "department": {"id": department.id, "name": department.name},
        "permissions": [
            {
                "code": permission.code,
                "name": permission.name,
                "ptype": permission.ptype,
            }
            for permission in allowed_permissions
        ],
        "projects": [
            {
                "id": project.id,
                "code": project.display_code or project.number_code or project.code,
                "name": project.name,
                "department": project.department.name if project.department else "",
                "stepIds": [
                    next(
                        (
                            step.id
                            for step in project.steps
                            if step.step_code == code
                        ),
                        None,
                    )
                    for code, _ in seed_data.PROJECT_AUTHORIZATION_STEPS
                ],
            }
            for project in allowed_projects
        ],
        "stepColumns": step_columns,
        "allowedProjectStepIds": sorted(allowed_step_ids),
        "selectedPermissionCodes": selected_permissions,
        "selectedProjectIds": selected_project_ids,
        "selectedProjectStepIds": selected_project_step_ids,
        "orgWide": department_has_org_wide_scope(department) or org_wide_user,
    }


from ..list_reads import reuse_list_reads, prime_identifiers


@bp.get("/users")
@require_auth
@require_admin
@reuse_list_reads
def list_users():
    from sqlalchemy.orm import selectinload
    users = User.query.options(selectinload(User.permissions), selectinload(User.department)).order_by(User.id).all()
    prime_identifiers('user', (user.id for user in users))
    return jsonify({"code": 0, "message": "ok", "data": {"rows": [_user_brief(u) for u in users]}})


@bp.get("/users/<int:uid>")
@require_auth
@require_admin
def get_user(uid):
    u = User.query.get(uid)
    if not u:
        return jsonify({"code": 1, "message": "用户不存在", "data": None}), 200
    return jsonify({"code": 0, "message": "ok", "data": _user_detail(u)})


@bp.get("/catalog")
@require_auth
@require_admin
def get_catalog():
    """权限点目录 + 操作权限 + 部门 + 数据范围类型，供前端渲染分配界面。"""
    # 项目授权目录：标准步骤为列，每个项目为行（cell = project_step id）
    step_cols = [{"code": c, "name": n} for c, n in seed_data.STANDARD_STEPS]
    projects = []
    for p in Project.query.filter_by(active=True).order_by(Project.department_id, Project.name, Project.id).all():
        steps_by_code = {s.step_code: s.id for s in p.steps}
        projects.append({
            "id": p.id,
            "code": p.display_code or p.number_code or p.code,
            "numberCode": p.number_code or "",
            "name": p.name,
            "department": p.department.name if p.department else "",
            "departmentId": p.department_id,
            "location": p.location or "",
            # 与 step_cols 对齐的 project_step id 列表
            "stepIds": [steps_by_code.get(c) for c, _ in seed_data.STANDARD_STEPS],
        })
    return jsonify({"code": 0, "message": "ok", "data": {
        "permissions": [{"code": c, "name": n, "ptype": t} for c, n, t in catalog.all_permission_catalog()],
        "actions": [
            {"code": c, "name": n}
            for c, n in catalog.assignable_action_permissions()
        ],
        "departments": [{"id": d.id, "name": d.name} for d in Department.query.order_by(Department.id).all()],
        "sites": seed_data.SITES,
        "stepColumns": step_cols,
        "projects": projects,
        "scopeTypes": [
            {"value": "all", "label": "全部数据"},
            {"value": "department", "label": "指定部门（可跨部门）"},
            {"value": "self", "label": "仅本人"},
            {"value": "authorization", "label": "授权范围（待批准）"},
            {"value": "department_project", "label": "本部门＋授权部门＋授权项目"},
        ],
    }})


@bp.get("/standard-catalog")
@require_auth
@require_admin
def get_standard_catalog():
    """Return standards eligible for a department or an org-wide target user."""
    try:
        department_id = int(request.args.get("departmentId") or 0)
    except ValueError:
        department_id = 0
    department = db.session.get(Department, department_id)
    if not department:
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    try:
        user_id = int(request.args.get("userId") or 0)
    except ValueError:
        user_id = 0
    target_user = db.session.get(User, user_id) if user_id else None
    org_wide = bool(
        department_has_org_wide_scope(department)
        or (target_user and user_has_org_wide_scope(target_user))
    )
    items = scoped_standard_items(department, org_wide=org_wide)
    return jsonify({"code": 0, "message": "ok", "data": {
        "department": "全院全部标准" if org_wide else department.name,
        "items": [{
            "id": item.id,
            "code": item.code or "",
            "name": item.name or "",
            "authKind": item.auth_kind or "",
            "status": item.to_row()["status"],
        } for item in items],
        "authorizedItemIds": [item.id for item in items],
    }})


def _synchronize_user_department(
    user: User,
    old_department: Department | None,
    department: Department,
) -> None:
    synchronize_user_department(
        user,
        old_department,
        department,
        actor=g.current_user,
    )


@bp.put("/users/<int:uid>")
@require_auth
@require_admin
def update_user(uid):
    u = User.query.get(uid)
    if not u:
        return jsonify({"code": 1, "message": "用户不存在", "data": None}), 200
    before = _user_detail(u)
    body = request.get_json(silent=True) or {}

    old_department = u.department
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"code": 1, "message": "姓名不能为空", "data": None}), 200
        u.name = name
    if "departmentId" in body:
        department_id = int(body.get("departmentId") or 0)
        department = db.session.get(Department, department_id)
        if not department:
            return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
        u.department = department
        _synchronize_user_department(u, old_department, department)

    if "permissions" in body:
        codes = set(body.get("permissions") or [])
        u.permissions = Permission.query.filter(Permission.code.in_(codes)).all() if codes else []

    if "actionPermissions" in body:
        actions = set(body.get("actionPermissions") or [])
        valid = set(catalog.all_action_codes())
        STORAGE_CODES = ()
        from ..report_correction_permissions import STORAGE_CODES as correction_codes
        db.session.execute(user_action_permissions.delete().where(
            user_action_permissions.c.user_id == u.id,
            user_action_permissions.c.action_code.notin_((*STORAGE_CODES, "report.seal.confirm", *correction_codes)),
        ))
        for a in actions & valid:
            db.session.execute(user_action_permissions.insert().values(user_id=u.id, action_code=a))

    if "projectStepIds" in body:
        ids = set(body.get("projectStepIds") or [])
        u.project_steps = (
            ProjectStep.query.filter(
                ProjectStep.id.in_(ids),
                ProjectStep.project.has(Project.active.is_(True)),
            ).all()
            if ids else []
        )

    if "standardItemIds" in body:
        try:
            replace_standard_authorizations(u, body.get("standardItemIds") or [])
        except (TypeError, ValueError) as error:
            return jsonify({"code": 1, "message": str(error), "data": None}), 200

    if "dataDepartmentIds" in body:
        ids = set(body.get("dataDepartmentIds") or [])
        u.data_departments = Department.query.filter(Department.id.in_(ids)).all() if ids else []

    if "dataSites" in body:
        sites = set(body.get("dataSites") or [])
        db.session.execute(user_data_sites.delete().where(user_data_sites.c.user_id == u.id))
        for s in sites:
            db.session.execute(user_data_sites.insert().values(user_id=u.id, site=s))

    if "dataScopeType" in body:
        u.data_scope_type = (
            "all"
            if department_has_org_wide_scope(u.department) and body.get("dataScopeType") != 'department_project'
            else body.get("dataScopeType") or "department"
        )
    if "dataScopeDesc" in body:
        u.data_scope_desc = body.get("dataScopeDesc") or ""
    if "eSignature" in body:
        u.e_signature = (body.get("eSignature") or "").strip()
    if body.get("roleName"):
        u.role_name = body["roleName"]
    if body.get("homePath"):
        u.home_path = body["homePath"]
    if "enabled" in body:
        u.enabled = bool(body["enabled"])

    if department_has_org_wide_scope(u.department) and u.data_scope_type != 'department_project':
        # 根机构始终表示全院范围，不能被同一次表单提交中的旧范围覆盖。
        u.data_scope_type = "all"
        u.data_scope_desc = "示例检测机构：可查看全院数据"
        u.data_departments = [u.department]

    person = _synchronize_personnel_record(u, body.get("personnel"))
    db.session.flush()

    add_operation_audit(
        "organization.user.update",
        "user",
        u.id,
        category="admin",
        before=before,
        after={**_user_detail(u), "personnelId": person.id},
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "保存成功", "data": _user_detail(u)})


@bp.post("/users")
@require_auth
@require_admin
def create_user():
    body = request.get_json(silent=True) or {}
    account = (body.get("account") or "").strip()
    name = (body.get("name") or "").strip()
    if not account or not name:
        return jsonify({"code": 1, "message": "账号和姓名必填", "data": None}), 200
    if User.query.filter_by(account=account).first():
        return jsonify({"code": 1, "message": "账号已存在", "data": None}), 200
    department_id = int(body["departmentId"]) if body.get("departmentId") else None
    department = db.session.get(Department, department_id) if department_id else None
    if department_id and not department:
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    # 未指定则随机临时口令（避免 123456 这类可猜口令被抢先改密接管）
    temp = initial_password(account)
    u = User(
        account=account,
        name=name,
        password_hash=hash_password(temp),
        role_key=body.get("roleKey") or "custom",
        role_name=body.get("roleName") or "自定义角色",
        home_path=body.get("homePath") or "/inspection/dashboard",
        department_id=department_id,
        data_scope_type=(
            "all"
            if department_has_org_wide_scope(department) and body.get("dataScopeType") != 'department_project'
            else body.get("dataScopeType") or "department"
        ),
        data_scope_desc=(
            "示例检测机构：可查看全院数据"
            if department_has_org_wide_scope(department) and body.get("dataScopeType") != 'department_project'
            else body.get("dataScopeDesc") or ""
        ),
        e_signature=(body.get("eSignature") or "").strip(),
        enabled=True,
        must_change_password=True,  # 新账户首次登录强制改密（流程图 #1）
    )
    # 新注册用户默认无任何权限，需超管分配（规格 2.1）
    db.session.add(u)
    db.session.flush()
    if department:
        db.session.execute(
            user_data_departments.insert().values(
                user_id=u.id,
                department_id=department.id,
                include_children=department_has_org_wide_scope(department),
                see_data=True,
                see_members=True,
                granted_by=g.current_user.account,
                granted_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
        )
    person = _synchronize_personnel_record(u, body.get("personnel"))
    db.session.flush()
    add_operation_audit(
        "organization.user.create",
        "user",
        u.id,
        category="admin",
        after={**_user_detail(u), "personnelId": person.id},
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "创建成功，请分配权限", "data": {
        "user": _user_detail(u), "tempPassword": temp, "personnelId": person.id,
    }})


@bp.post("/users/<int:uid>/reset-password")
@require_auth
@require_admin
def reset_password(uid):
    """生成独立随机初始密码，强制下次登录修改。"""
    u = User.query.filter_by(id=uid).populate_existing().with_for_update().first()
    if not u:
        return jsonify({"code": 1, "message": "用户不存在", "data": None}), 200
    temp = reset_initial_password(u)
    add_operation_audit(
        "organization.user.reset_password",
        "user",
        u.id,
        category="security",
        after={"account": u.account, "mustChangePassword": True},
        message="管理员重置密码；审计记录不保存密码或密码哈希",
    )
    db.session.commit()
    return jsonify({"code": 0, "message": f"已重置 {u.account} 密码，该账户下次登录需改密", "data": {
        "tempPassword": temp,
    }})


# ====================== 组织机构 ======================

@bp.get("/departments/tree")
@require_auth
@require_admin
def departments_tree():
    """组织机构树（含每个部门成员数），供组织机构管理双栏页左侧渲染。"""
    depts = Department.query.order_by(Department.id).all()
    counts = {}
    for (did,) in db.session.query(User.department_id).filter(User.department_id.isnot(None)).all():
        counts[did] = counts.get(did, 0) + 1
    nodes = {d.id: {"id": d.id, "code": d.code, "name": d.name, "parentId": d.parent_id,
                    "site": d.site or "", "memberCount": counts.get(d.id, 0), "children": []} for d in depts}
    roots = []
    for d in depts:
        if d.parent_id and d.parent_id in nodes:
            nodes[d.parent_id]["children"].append(nodes[d.id])
        else:
            roots.append(nodes[d.id])
    return jsonify({"code": 0, "message": "ok", "data": {"tree": roots}})


@bp.get("/departments/<int:did>/members")
@require_auth
@require_admin
def department_members(did):
    """某部门的成员（含其数据授权明细），供右栏展示与授权。"""
    d = Department.query.get(did)
    if not d:
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    users = User.query.filter_by(department_id=did).order_by(User.id).all()
    return jsonify({"code": 0, "message": "ok", "data": {
        "department": {"id": d.id, "name": d.name},
        "rows": [{**_user_brief(u), "dataGrants": _user_grants(u)} for u in users],
    }})


@bp.get("/departments/<int:did>/authorizations")
@require_auth
@require_admin
def get_department_authorizations(did):
    """部门功能及整项目授权；人员再在部门项目范围内细分业务环节。"""
    department = db.session.get(Department, did)
    if not department:
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": _authorization_catalog_payload(department),
    })


@bp.put("/departments/<int:did>/authorizations")
@require_auth
@require_admin
def update_department_authorizations(did):
    department = db.session.get(Department, did)
    if not department:
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    if department_has_org_wide_scope(department):
        before = {
            "permissionCodes": sorted(permission.code for permission in department.permissions),
            "projectIds": sorted(project.id for project in department.projects),
            "projectStepIds": sorted(step.id for step in department.project_steps),
        }
        department.permissions = Permission.query.all()
        department.projects = Project.query.filter_by(active=True).all()
        department.project_steps = (
            ProjectStep.query.join(Project)
            .filter(Project.active.is_(True))
            .all()
        )
        add_operation_audit(
            "organization.department.authorize",
            "department",
            department.id,
            category="admin",
            before=before,
            after={
                "permissionCodes": sorted(permission.code for permission in department.permissions),
                "projectIds": sorted(project.id for project in department.projects),
                "projectStepIds": sorted(step.id for step in department.project_steps),
                "scope": "organization-wide",
            },
        )
        db.session.commit()
        return jsonify({
            "code": 0,
            "message": "公司根机构固定拥有全院全部权限",
            "data": _authorization_catalog_payload(department),
        })

    body = request.get_json(silent=True) or {}
    permission_codes = {
        str(code)
        for code in body.get("permissionCodes", [])
        if str(code) != "system.user.view"
    }
    requested_project_ids = {
        int(project_id)
        for project_id in body.get("projectIds", [])
        if str(project_id).isdigit()
    }
    # 兼容短期上线过的“部门项目子功能”请求：折叠回整项目授权。
    if "projectIds" not in body:
        legacy_step_ids = {
            int(step_id)
            for step_id in body.get("projectStepIds", [])
            if str(step_id).isdigit()
        }
        requested_project_ids = {
            step.project_id
            for step in ProjectStep.query.filter(
                ProjectStep.id.in_(legacy_step_ids)
            ).all()
        } if legacy_step_ids else set()
    valid_permissions = {
        permission.code: permission for permission in _assignable_permissions()
    }
    valid_projects = {
        project.id: project
        for project in Project.query.filter_by(active=True).all()
    }
    valid_steps = {
        step.id: step
        for step in _visible_project_steps_query().all()
    }
    invalid_permissions = permission_codes - set(valid_permissions)
    invalid_projects = requested_project_ids - set(valid_projects)
    if invalid_permissions or invalid_projects:
        return jsonify({
            "code": 1,
            "message": "包含无效或已停用的功能/项目授权",
            "data": None,
        }), 200

    department.permissions = [
        valid_permissions[code] for code in sorted(permission_codes)
    ]
    department.projects = [
        valid_projects[project_id] for project_id in sorted(requested_project_ids)
    ]
    # 部门只选择整项目；后台按部门功能上限自动展开可供人员选择的项目子功能。
    compatible_step_ids = {
        step.id
        for step in valid_steps.values()
        if (
            step.project_id in requested_project_ids
            and _step_matches_permissions(step, permission_codes)
        )
    }
    hidden_department_steps = [
        step
        for step in department.project_steps
        if step.step_code not in PROJECT_AUTHORIZATION_STEP_CODES
    ]
    department.project_steps = hidden_department_steps + [
        valid_steps[step_id] for step_id in sorted(compatible_step_ids)
    ]
    # 部门授权是人员授权上限；收回部门授权或功能权限时同步裁剪普通成员。
    for user in User.query.filter_by(department_id=department.id).all():
        if user_has_org_wide_scope(user):
            continue
        user.permissions = [
            permission
            for permission in user.permissions
            if permission.code in permission_codes
        ]
        user.project_steps = [
            step
            for step in user.project_steps
            if (
                step.step_code not in PROJECT_AUTHORIZATION_STEP_CODES
                or (
                    step.id in compatible_step_ids
                    and _step_matches_permissions(
                        step,
                        set(user.permission_codes()),
                    )
                )
            )
        ]

    add_operation_audit(
        "organization.department.authorize",
        "department",
        department.id,
        category="admin",
        after={
            "permissionCodes": sorted(permission_codes),
            "projectIds": sorted(requested_project_ids),
            "projectMode": "whole-project",
        },
    )
    db.session.commit()
    return jsonify({
        "code": 0,
        "message": "部门授权已保存，成员越权授权已同步收回",
        "data": _authorization_catalog_payload(department),
    })


@bp.get("/departments/<int:did>/members/<int:uid>/authorizations")
@require_auth
@require_admin
def get_department_member_authorizations(did, uid):
    department = db.session.get(Department, did)
    user = db.session.get(User, uid)
    if not department or not user or user.department_id != department.id:
        return jsonify({"code": 1, "message": "部门或人员不存在", "data": None}), 200
    payload = _authorization_catalog_payload(department, user=user)
    payload["user"] = {
        "id": user.id,
        "account": user.account,
        "name": user.name,
    }
    payload["selectedTemplateIds"] = sorted(template.id for template in user.permission_templates)
    from ..workflow_hooks import empty_authorization_payload as authorization_payload
    payload["erpAuthorization"] = authorization_payload(user, g.current_user)
    from ..esign_seal_confirmation import has_permission
    payload["sealConfirmation"] = has_permission(user)
    from ..report_correction_permissions import authorization_payload as correction_authorization
    payload.update(correction_authorization(user))
    from ..report_delivery_grants import authorization_payload as delivery_authorization_payload
    payload.update(delivery_authorization_payload(user))
    payload.update(equipment_authorization.authorization_payload(user))
    return jsonify({"code": 0, "message": "ok", "data": payload})


@bp.put("/departments/<int:did>/members/<int:uid>/authorizations")
@require_auth
@require_admin
def update_department_member_authorizations(did, uid):
    department = db.session.get(Department, did)
    user = db.session.get(User, uid)
    if not department or not user or user.department_id != department.id:
        return jsonify({"code": 1, "message": "部门或人员不存在", "data": None}), 200
    body = request.get_json(silent=True) or {}
    erp_permissions = None
    equipment_departments = None
    if "equipmentDepartmentIds" in body:
        try:
            equipment_departments = equipment_authorization.validate_department_ids(body["equipmentDepartmentIds"])
        except ValueError as exc:
            return jsonify(code=1, message=str(exc), data=None), 200
    if "sealConfirmation" in body and type(body["sealConfirmation"]) is not bool:
        return jsonify(code=1, message="签章确认权限必须为布尔值", data=None), 200
    from ..report_correction_permissions import FIELDS as correction_fields, assign as assign_correction, authorization_payload as correction_authorization
    for field in correction_fields:
        if field in body and type(body[field]) is not bool:
            return jsonify(code=1, message="报告更改审批权限必须为布尔值", data=None), 200
    from ..report_delivery_grants import FIELDS as delivery_fields, assign_authorizations
    for field in delivery_fields:
        if field in body and type(body[field]) is not bool:
            return jsonify(code=1, message="报告下载及发放权限必须为布尔值", data=None), 200
    erp_roles = None
    erp_before = None
    if "erpPermissions" in body:
        if not erp_permissions.is_admin(g.current_user):
            return jsonify(code=403, message="仅管理员可分配外部ERP回传权限", data=None), 200
        try:
            erp_roles = erp_permissions.validate_roles(body["erpPermissions"])
        except ValueError as exc:
            return jsonify(code=1, message=str(exc), data=None), 200
        erp_before = erp_permissions.effective_roles(user)
        if erp_permissions.is_admin(user):
            # Inherited authority must not become a permanent personal grant.
            erp_roles = None
    expand_project_scope = body.get("expandProjectScope") is True
    requested_template_ids = {
        int(template_id)
        for template_id in body.get("templateIds", [])
        if str(template_id).isdigit()
    } if "templateIds" in body else None
    if requested_template_ids is not None:
        templates = PermissionTemplate.query.filter(
            PermissionTemplate.id.in_(requested_template_ids)
        ).all() if requested_template_ids else []
        if {template.id for template in templates} != requested_template_ids:
            return jsonify({"code": 1, "message": "人员授权包含不存在的权限模板", "data": None}), 200
    permission_codes = {
        str(code)
        for code in body.get("permissionCodes", [])
        if str(code) != "system.user.view"
    }
    requested_step_ids = {
        int(step_id)
        for step_id in body.get("projectStepIds", [])
        if str(step_id).isdigit()
    }
    legacy_project_ids = {
        int(project_id)
        for project_id in body.get("projectIds", [])
        if str(project_id).isdigit()
    } if "projectStepIds" not in body else set()

    if user_has_org_wide_scope(user):
        allowed_permissions = {
            permission.code: permission for permission in _assignable_permissions()
        }
        allowed_steps = {
            step.id: step
            for step in _visible_project_steps_query().all()
        }
    else:
        allowed_permissions = {
            permission.code: permission
            for permission in _department_authorized_permissions(department)
        }
        allowed_steps = {
            step.id: step
            for step in (
                _visible_project_steps_query().all()
                if expand_project_scope
                else _department_authorized_project_steps(department)
            )
        }
    if legacy_project_ids:
        requested_step_ids = {
            step.id
            for step in allowed_steps.values()
            if step.project_id in legacy_project_ids
        }
    if (
        permission_codes - set(allowed_permissions)
        or requested_step_ids - set(allowed_steps)
    ):
        return jsonify({
            "code": 1,
            "message": "人员功能授权只能从所属部门上限中选择，项目环节必须来自有效项目目录",
            "data": None,
        }), 200

    # 管理员旧鉴权权限不在新界面展示，保存人员授权时继续保留。
    hidden_admin_permission = next(
        (
            permission
            for permission in user.permissions
            if permission.code == "system.user.view"
        ),
        None,
    )
    user.permissions = [
        allowed_permissions[code] for code in sorted(permission_codes)
    ]
    if hidden_admin_permission and hidden_admin_permission not in user.permissions:
        user.permissions.append(hidden_admin_permission)
    compatible_step_ids = {
        step_id
        for step_id in requested_step_ids
        if _step_matches_permissions(allowed_steps[step_id], permission_codes)
    }
    expanded_project_ids: set[int] = set()
    expanded_data_department_ids: set[int] = set()
    if expand_project_scope and not user_has_org_wide_scope(user):
        known_department_step_ids = {step.id for step in department.project_steps}
        known_department_project_ids = {project.id for project in department.projects}
        for step_id in sorted(compatible_step_ids):
            step = allowed_steps[step_id]
            if step.id not in known_department_step_ids:
                department.project_steps.append(step)
                known_department_step_ids.add(step.id)
            if step.project_id not in known_department_project_ids:
                department.projects.append(step.project)
                known_department_project_ids.add(step.project_id)
                expanded_project_ids.add(step.project_id)
            if step.project.department_id:
                expanded_data_department_ids.add(step.project.department_id)

        current_data_department_ids = {
            int(row.department_id)
            for row in db.session.execute(
                user_data_departments.select().where(
                    user_data_departments.c.user_id == user.id
                )
            ).fetchall()
        }
        for department_id in sorted(
            expanded_data_department_ids - current_data_department_ids
        ):
            db.session.execute(user_data_departments.insert().values(
                user_id=user.id,
                department_id=department_id,
                include_children=False,
                see_data=True,
                see_members=False,
                granted_by=str(g.current_user.account or "admin")[:40],
                granted_at=datetime.utcnow().isoformat(timespec="seconds"),
            ))
    hidden_user_steps = [
        step
        for step in user.project_steps
        if step.step_code not in PROJECT_AUTHORIZATION_STEP_CODES
    ]
    user.project_steps = hidden_user_steps + [
        allowed_steps[step_id] for step_id in sorted(compatible_step_ids)
    ]
    if requested_template_ids is not None:
        user.permission_templates = sorted(templates, key=lambda item: item.id)
    assign_authorizations(user, body)
    if equipment_departments is not None:
        equipment_authorization.assign(user, equipment_departments)
    correction_changes = {field: body[field] for field in correction_fields if field in body}
    if correction_changes:
        before_correction = correction_authorization(user)
        for field, enabled in correction_changes.items():
            assign_correction(user, field, enabled)
        add_operation_audit("organization.member.correction_authorize", "user", user.id,
            category="security", before={field: before_correction[field] for field in correction_changes},
            after=correction_changes)
    if "sealConfirmation" in body:
        from ..esign_seal_confirmation import assign, has_permission
        previous_seal_permission = has_permission(user)
        assign(user, body["sealConfirmation"])
        add_operation_audit("organization.member.seal_authorize", "user", user.id,
            category="security", before={"sealConfirmation": previous_seal_permission},
            after={"sealConfirmation": body["sealConfirmation"]})
    if erp_roles is not None:
        erp_permissions.assign_roles(user, erp_roles)
        add_operation_audit(
            "organization.member.erp_authorize", "user", user.id,
            category="security", before={"roles": erp_before},
            after={"roles": erp_roles},
        )
    add_operation_audit(
        "organization.member.authorize",
        "user",
        user.id,
        category="admin",
        after={
            "departmentId": department.id,
            "permissionCodes": sorted(permission_codes),
            "projectStepIds": sorted(compatible_step_ids),
            "templateIds": sorted(requested_template_ids) if requested_template_ids is not None else sorted(
                template.id for template in user.permission_templates
            ),
            "projectMode": "project-step",
            "expandedDepartmentProjectIds": sorted(expanded_project_ids),
            "expandedDataDepartmentIds": sorted(expanded_data_department_ids),
        },
    )
    db.session.commit()
    payload = _authorization_catalog_payload(department, user=user)
    payload["user"] = {"id": user.id, "account": user.account, "name": user.name}
    payload["selectedTemplateIds"] = sorted(template.id for template in user.permission_templates)
    from ..workflow_hooks import empty_authorization_payload as authorization_payload
    payload["erpAuthorization"] = authorization_payload(user, g.current_user)
    from ..esign_seal_confirmation import has_permission
    payload["sealConfirmation"] = has_permission(user)
    payload.update(correction_authorization(user))
    from ..report_delivery_grants import authorization_payload as delivery_authorization_payload
    payload.update(delivery_authorization_payload(user))
    payload.update(equipment_authorization.authorization_payload(user))
    return jsonify({"code": 0, "message": "人员授权已保存", "data": payload})


@bp.post("/departments")
@require_auth
@require_admin
def create_department():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"code": 1, "message": "部门名称必填", "data": None}), 200
    pid = body.get("parentId")
    if pid and not Department.query.get(int(pid)):
        return jsonify({"code": 1, "message": "上级部门不存在", "data": None}), 200
    code = "D" + secrets.token_hex(4)
    while Department.query.filter_by(code=code).first():
        code = "D" + secrets.token_hex(4)
    d = Department(code=code, name=name, parent_id=int(pid) if pid else None, site=(body.get("site") or "").strip())
    db.session.add(d)
    db.session.commit()
    return jsonify({"code": 0, "message": "已添加", "data": {"id": d.id, "name": d.name}})


@bp.put("/departments/<int:did>")
@require_auth
@require_admin
def update_department(did):
    d = Department.query.get(did)
    if not d:
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    body = request.get_json(silent=True) or {}
    if body.get("name"):
        d.name = body["name"].strip()
    if "site" in body:
        d.site = (body.get("site") or "").strip()
    if "parentId" in body:
        pid = body.get("parentId")
        if pid:
            pid = int(pid)
            node = Department.query.get(pid)
            while node is not None:  # 防止移动到自身或自己的子孙下（成环）
                if node.id == did:
                    return jsonify({"code": 1, "message": "不能移动到自身或其子部门下", "data": None}), 200
                node = node.parent
            d.parent_id = pid
        else:
            d.parent_id = None
    db.session.commit()
    return jsonify({"code": 0, "message": "已修改", "data": {"id": d.id, "name": d.name}})


@bp.delete("/departments/<int:did>")
@require_auth
@require_admin
def delete_department(did):
    d = Department.query.get(did)
    if not d:
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    if Department.query.filter_by(parent_id=did).first():
        return jsonify({"code": 1, "message": "该部门下有子部门，请先处理子部门", "data": None}), 200
    if User.query.filter_by(department_id=did).first():
        return jsonify({"code": 1, "message": "该部门下有成员，无法删除", "data": None}), 200
    db.session.execute(user_data_departments.delete().where(user_data_departments.c.department_id == did))
    from ..models import user_equipment_departments
    db.session.execute(user_equipment_departments.delete().where(user_equipment_departments.c.department_id == did))
    db.session.execute(department_permissions.delete().where(
        department_permissions.c.department_id == did
    ))
    db.session.execute(department_project_permissions.delete().where(
        department_project_permissions.c.department_id == did
    ))
    db.session.execute(department_project_step_permissions.delete().where(
        department_project_step_permissions.c.department_id == did
    ))
    db.session.delete(d)
    db.session.commit()
    return jsonify({"code": 0, "message": "已删除", "data": None})


# ---------- 数据授权（看数据 / 看成员 / 含子部门，管理员显式授权 + 留痕）----------

@bp.post("/users/<int:uid>/grants")
@require_auth
@require_admin
def set_grant(uid):
    u = User.query.get(uid)
    if not u:
        return jsonify({"code": 1, "message": "用户不存在", "data": None}), 200
    body = request.get_json(silent=True) or {}
    dept_id = body.get("departmentId")
    if not dept_id or not Department.query.get(int(dept_id)):
        return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
    dept_id = int(dept_id)
    db.session.execute(user_data_departments.delete().where(
        (user_data_departments.c.user_id == uid) & (user_data_departments.c.department_id == dept_id)))
    db.session.execute(user_data_departments.insert().values(
        user_id=uid, department_id=dept_id,
        see_data=bool(body.get("seeData", True)), see_members=bool(body.get("seeMembers", True)),
        include_children=bool(body.get("includeChildren", False)),
        granted_by=g.current_user.account, granted_at=datetime.now().strftime("%Y-%m-%d %H:%M")))
    db.session.commit()
    return jsonify({"code": 0, "message": "授权已保存", "data": _user_grants(u)})


@bp.delete("/users/<int:uid>/grants/<int:dept_id>")
@require_auth
@require_admin
def revoke_grant(uid, dept_id):
    if not User.query.get(uid):
        return jsonify({"code": 1, "message": "用户不存在", "data": None}), 200
    db.session.execute(user_data_departments.delete().where(
        (user_data_departments.c.user_id == uid) & (user_data_departments.c.department_id == dept_id)))
    db.session.commit()
    return jsonify({"code": 0, "message": "授权已收回", "data": None})


# ---------- CNAS 能力导入批次与待确认部门映射 ----------

@bp.get("/cnas/batches")
@require_auth
@require_admin
def cnas_batches():
    rows = []
    for batch in CapabilityImportBatch.query.order_by(
        CapabilityImportBatch.id.desc()
    ).all():
        entry_count = CapabilityEntry.query.filter_by(batch_id=batch.id).count()
        pending_count = CapabilityEntry.query.filter_by(batch_id=batch.id).filter(
            db.or_(
                CapabilityEntry.mapping_status != "confirmed",
                ~CapabilityEntry.departments.any(),
            )
        ).count()
        rows.append({
            "id": batch.id,
            "sourceName": batch.source_name,
            "sourceSha256": batch.source_sha256,
            "status": batch.status,
            "attachmentCount": batch.attachment_count,
            "chinesePageCount": batch.chinese_page_count,
            "entryCount": entry_count,
            "pendingCount": pending_count,
            "anomalyCount": int((batch.summary or {}).get("anomalyCount") or 0),
            "createdAt": batch.created_at.isoformat() if batch.created_at else "",
            "activatedAt": batch.activated_at.isoformat() if batch.activated_at else "",
        })
    return jsonify({"code": 0, "message": "ok", "data": {"rows": rows}})


@bp.get("/cnas/batches/<int:batch_id>/entries")
@require_auth
@require_admin
def cnas_batch_entries(batch_id):
    if not db.session.get(CapabilityImportBatch, batch_id):
        return jsonify({"code": 1, "message": "能力批次不存在", "data": None}), 200
    query = CapabilityEntry.query.filter_by(batch_id=batch_id)
    mapping_status = (request.args.get("mappingStatus") or "").strip()
    if mapping_status == "pending":
        query = query.filter(db.or_(
            CapabilityEntry.mapping_status != "confirmed",
            ~CapabilityEntry.departments.any(),
        ))
    elif mapping_status:
        query = query.filter(CapabilityEntry.mapping_status == mapping_status)
    keyword = (request.args.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(db.or_(
            CapabilityEntry.standard_code.like(like),
            CapabilityEntry.standard_name.like(like),
            CapabilityEntry.object_name.like(like),
            CapabilityEntry.item_name.like(like),
        ))
    try:
        page = max(1, int(request.args.get("page", 1)))
        size = min(200, max(1, int(request.args.get("size", 50))))
    except (TypeError, ValueError):
        page, size = 1, 50
    total = query.count()
    entries = query.order_by(
        CapabilityEntry.source_file,
        CapabilityEntry.source_page,
        CapabilityEntry.source_row,
    ).offset((page - 1) * size).limit(size).all()
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": [entry.to_row() for entry in entries],
        "total": total,
        "page": page,
        "size": size,
    }})


@bp.put("/cnas/entries/<int:entry_id>/departments")
@require_auth
@require_admin
def update_cnas_entry_departments(entry_id):
    entry = db.session.get(CapabilityEntry, entry_id)
    if not entry:
        return jsonify({"code": 1, "message": "能力记录不存在", "data": None}), 200
    body = request.get_json(silent=True) or {}
    try:
        ids = sorted({int(value) for value in body.get("departmentIds") or []})
    except (TypeError, ValueError):
        return jsonify({"code": 1, "message": "部门编号格式无效", "data": None}), 200
    departments = Department.query.filter(Department.id.in_(ids)).all() if ids else []
    if len(departments) != len(ids):
        return jsonify({"code": 1, "message": "包含不存在的部门", "data": None}), 200
    before = entry.to_row()
    map_capability_entry_departments(entry, departments)
    add_operation_audit(
        "cnas.capability.map_departments",
        "capability_entry",
        entry.id,
        category="quality",
        before=before,
        after=entry.to_row(),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "部门映射已保存", "data": entry.to_row()})


@bp.post("/cnas/batches/<int:batch_id>/activate")
@require_auth
@require_admin
def activate_cnas_batch(batch_id):
    from ..cnas_capabilities import activate_capability_batch

    try:
        batch = activate_capability_batch(batch_id)
        add_operation_audit(
            "cnas.capability.activate_batch",
            "capability_import_batch",
            batch.id,
            category="quality",
            after={
                "sourceName": batch.source_name,
                "sourceSha256": batch.source_sha256,
                "status": batch.status,
            },
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    return jsonify({"code": 0, "message": "CNAS 能力批次已激活", "data": {
        "id": batch.id,
        "status": batch.status,
    }})
