from ..admin_corrections.existing import audited_form, active as correcting
from ..admin_corrections import can_correct_business_data
"""质量接口 — 仪器/资质/标准的状态与按时间点的有效性查询（规格 2.6）。"""
import calendar
import re
from datetime import date, datetime, timedelta
from io import BytesIO

from flask import Blueprint, g, jsonify, request, send_file
from openpyxl import Workbook, load_workbook

from ..preflight_reads import reuse_preflight_reads
from ..platform.audit import add_operation_audit, edit_time_text, records_by_edit_time
from ..platform.identity import synchronize_user_department, user_has_org_wide_scope
from ..extensions import db
from ..edit_concurrency import require_edit_version
from ..forms.reference_data import mask_private_fields
from ..models import (
    CapabilityEntry,
    Department,
    EquipmentCalibrationRecord,
    EquipmentItem,
    EquipmentUsageRecord,
    Instrument,
    Personnel,
    Qualification,
    Report,
    Standard,
    StdLibraryItem,
    User,
)
from ..security import require_auth
from ..platform.identity import can_manage_users, personnel_login
from sqlalchemy.exc import IntegrityError

bp = Blueprint("quality", __name__, url_prefix="/api/quality")

# 可分配的流程权限（人员登记-权限分配）
PERM_OPTIONS = ["委托登记", "样品登记", "合同评审", "样品入出库", "数据录入", "校核", "审核", "批准", "打印发放"]


def _page_args():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        size = min(100, max(1, int(request.args.get("size", 20))))
    except (TypeError, ValueError):
        size = 20
    return page, size


def _edited_page(query, object_type, page, size):
    # Sort and slice identifiers in SQL; never hydrate an entire standard or
    # personnel catalogue merely to display twenty rows. Keep the same latest
    # successful edit / descending ID tie-break as records_by_edit_time.
    from sqlalchemy import String, cast, func
    from ..models import OperationAudit
    model = query.column_descriptions[0]['entity']
    visible_ids = query.order_by(None).with_entities(cast(model.id, String))
    latest = db.session.query(
        OperationAudit.object_id.label('object_id'),
        func.max(OperationAudit.created_at).label('edited_at'),
    ).filter(
        OperationAudit.object_type == object_type,
        OperationAudit.success.is_(True),
        OperationAudit.object_id.in_(visible_ids),
    ).group_by(OperationAudit.object_id).subquery()
    return query.outerjoin(latest, latest.c.object_id == cast(model.id, String)).add_columns(
        latest.c.edited_at,
    ).order_by(None).order_by(latest.c.edited_at.desc(), model.id.desc()).offset(
        (page - 1) * size,
    ).limit(size).all()


def _edited_row(row, edited_at, personnel_context=None):
    data = _personnel_row(row, context=personnel_context) if isinstance(row, Personnel) else row.to_row()
    data["editedAt"] = edit_time_text(edited_at)
    return data


def _linked_personnel_user(person: Personnel) -> User | None:
    account = (person.code or "").strip().lower()
    if not account:
        return None
    return User.query.filter(db.func.lower(db.func.trim(User.account)) == account).one_or_none()


def _personnel_row(person: Personnel, *, full: bool = False, context=None) -> dict:
    row = person.to_row(full=full)
    user = _linked_personnel_user(person) if context is None else context[0].get((person.code or '').strip().lower())
    row.update({
        "linkedUserId": user.id if user else None,
        "accountEnabled": bool(user.enabled) if user else False,
        "accountStatus": "已启用" if user and user.enabled else ("已停用" if user else "未创建账号"),
        "roleName": user.role_name if user else "",
        "departmentId": user.department_id if user else (context[1].get(person.dept) if context is not None else next((d.id for d in Department.query.filter_by(name=person.dept).all()), None)),
    })
    return row


def _visible_personnel_department_names() -> set[str] | None:
    if user_has_org_wide_scope(g.current_user):
        return None
    department_ids = g.current_user.member_visible_department_ids()
    if not department_ids:
        return set()
    return {
        row.name
        for row in Department.query.filter(Department.id.in_(department_ids)).all()
        if row.name
    }


def _personnel_is_visible(person: Personnel) -> bool:
    visible_departments = _visible_personnel_department_names()
    if visible_departments is None:
        return True
    assigned = {item for item in (person.assigned_depts or "").split(";") if item}
    return bool(({person.dept} | assigned) & visible_departments)


def _personnel_target_scope_denied(body, current: Personnel | None = None):
    """Reject moving or assigning a roster row outside the actor's member scope."""

    visible_departments = _visible_personnel_department_names()
    if visible_departments is None:
        return None
    target_department = (body.get("dept") or (current.dept if current else "") or "").strip()
    assigned = body.get("assignedDepts")
    target_departments = {target_department} if target_department else set()
    if isinstance(assigned, list):
        target_departments.update(str(value).strip() for value in assigned if str(value).strip())
    if not target_departments.issubset(visible_departments):
        return jsonify({
            "code": 403,
            "message": "只能维护可管理部门内的人员",
            "data": None,
        }), 200
    return None


def _parse_date(s, default=None):
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return default


def _require_action(code, message="无此项维护权限", fallback_codes=()):
    # Routine master-data updates use normal domain validation/audit, including
    # privileged maintainers who already had this access through correction mode.
    if can_correct_business_data(g.current_user) and code in {
        "quality.standard.update", "quality.master_standard.update",
        "quality.equipment.update", "quality.personnel.update",
    }:
        return None
    if correcting():
        return None
    granted = set(g.current_user.action_codes())
    if code in granted or any(fallback in granted for fallback in fallback_codes):
        return None
    return jsonify({"code": 403, "message": message, "data": None}), 200


def _require_page(code, message="无此项功能查看权限"):
    if can_correct_business_data(g.current_user):
        return None
    """Require the exact quality page before evaluating maintenance actions.

    Action grants are deliberately stored separately from page grants.  A
    stale action grant must therefore never keep a quality-resource endpoint
    available after the owning page has been revoked.
    """

    user = g.current_user
    if user.role_key == "admin" or code in user.permission_codes():
        return None
    return jsonify({"code": 403, "message": message, "data": None}), 200


@bp.get("/instruments")
@require_auth
def instruments():
    rows = Instrument.query.order_by(Instrument.code).all()
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": [{"code": i.code, "name": i.name, "department": i.department, "site": i.site,
                  "controlled": i.controlled} for i in rows],
        "total": len(rows),
    }})


@bp.get("/instruments/<code>/validity")
@require_auth
def instrument_validity(code):
    """以指定时间查询某仪器的有效性。?at=YYYY-MM-DD"""
    ins = Instrument.query.filter_by(code=code).first()
    if not ins:
        return jsonify({"code": 1, "message": "仪器不存在", "data": None}), 200
    when = _parse_date(request.args.get("at"), date.today())
    v = ins.valid_at(when)
    return jsonify({"code": 0, "message": "ok", "data": {
        "code": ins.code, "name": ins.name, "at": when.isoformat(),
        "valid": v is not None,
        "window": (f"{v.valid_from.isoformat()} ~ {v.valid_to.isoformat()}" if v else None),
        "status": (v.status if v else "无有效检定/校准记录"),
    }})


@bp.get("/qualifications/<int:qid>/validity")
@require_auth
def qualification_validity(qid):
    """以指定时间查询资质的有效性（历史快照）。?at=YYYY-MM-DD"""
    qa = Qualification.query.get(qid)
    if not qa:
        return jsonify({"code": 1, "message": "资质不存在", "data": None}), 200
    when = _parse_date(request.args.get("at"), date.today())
    snap = qa.valid_at(when)
    valid = snap is not None and snap.valid_to >= when
    return jsonify({"code": 0, "message": "ok", "data": {
        "kind": qa.kind, "department": qa.department, "at": when.isoformat(),
        "valid": valid,
        "scope": (snap.scope if snap else None),
        "window": (f"{snap.effective_from.isoformat()} ~ {snap.valid_to.isoformat()}" if snap else None),
    }})


@bp.get("/standards")
@require_auth
def standards():
    denied = _require_page("quality.standard_library.view", "无标准基础信息库查看权限")
    if denied:
        return denied
    q = Standard.query.filter(Standard.deleted_at.is_(None))
    keyword = (request.args.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(db.or_(Standard.code.like(like), Standard.name.like(like)))
    category = (request.args.get("category") or "").strip()
    if category:
        q = q.filter(Standard.category == category)
    total = q.count()
    page, size = _page_args()
    rows = _edited_page(q, "standard", page, size)
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": [_edited_row(s, edited_at) for s, edited_at in rows],
        "total": total, "page": page, "size": size,
    }})


def _apply_master_standard(row, body):
    for attr, key in [
        ("code", "code"), ("name", "name"), ("auth_kind", "authKind"),
        ("department", "department"), ("category", "category"), ("status", "status"),
    ]:
        if key in body:
            value = body[key]
            setattr(row, attr, value.strip() if isinstance(value, str) else value)
    if "expired" in body:
        row.expired = bool(body["expired"])


@bp.post("/standards")
@require_auth
def standard_create():
    page_denied = _require_page("quality.standard_library.view", "无标准基础信息库查看权限")
    if page_denied:
        return page_denied
    denied = _require_action("quality.master_standard.create", "无标准主数据新增权限")
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip()
    if not code or not name:
        return jsonify({"code": 1, "message": "标准编号和标准名称为必填项", "data": None}), 200
    existing = Standard.query.filter_by(code=code).first()
    if existing and existing.deleted_at is None:
        return jsonify({"code": 1, "message": "标准编号已存在", "data": None}), 200
    row = existing or Standard()
    before = row.to_row() if existing else None
    row.deleted_at = None
    if existing:
        row.status = "现行"
        row.expired = False
    _apply_master_standard(row, body)
    if not existing:
        db.session.add(row)
    db.session.flush()
    add_operation_audit(
        "quality.master_standard.create",
        "standard",
        row.id,
        before=before,
        after=row.to_row(),
        message="恢复软删除记录" if existing else "",
    )
    db.session.commit()
    message = "标准主数据已恢复" if existing else "标准主数据已新增"
    return jsonify({"code": 0, "message": message, "data": row.to_row()})


@bp.put("/standards/<int:sid>")
@require_auth
@audited_form("standards", "sid")
def standard_update(sid):
    page_denied = _require_page("quality.standard_library.view", "无标准基础信息库查看权限")
    if page_denied:
        return page_denied
    denied = _require_action("quality.master_standard.update", "无标准主数据修改权限")
    if denied:
        return denied
    row = Standard.query.filter_by(id=sid, deleted_at=None).first()
    if not row:
        return jsonify({"code": 1, "message": "标准不存在", "data": None}), 200
    before = row.to_row()
    body = request.get_json(silent=True) or {}
    proposed_code = body.get("code", row.code)
    proposed_name = body.get("name", row.name)
    if (
        not isinstance(proposed_code, str)
        or not proposed_code.strip()
        or not isinstance(proposed_name, str)
        or not proposed_name.strip()
    ):
        return jsonify({"code": 1, "message": "标准编号和标准名称为必填项", "data": None}), 200
    normalized_code = proposed_code.strip()
    duplicate = Standard.query.filter(
        Standard.code == normalized_code,
        Standard.id != row.id,
        Standard.deleted_at.is_(None),
    ).first()
    if duplicate:
        return jsonify({"code": 1, "message": "标准编号已存在", "data": None}), 200
    _apply_master_standard(row, body)
    add_operation_audit("quality.master_standard.update", "standard", row.id, before=before, after=row.to_row())
    db.session.commit()
    return jsonify({"code": 0, "message": "标准主数据已保存", "data": row.to_row()})


@bp.delete("/standards/<int:sid>")
@require_auth
def standard_delete(sid):
    page_denied = _require_page("quality.standard_library.view", "无标准基础信息库查看权限")
    if page_denied:
        return page_denied
    denied = _require_action("quality.master_standard.delete", "无标准主数据移除权限")
    if denied:
        return denied
    row = Standard.query.filter_by(id=sid, deleted_at=None).first()
    if not row:
        return jsonify({"code": 1, "message": "标准不存在", "data": None}), 200
    before = row.to_row()
    row.deleted_at = datetime.utcnow()
    row.status = "已停用"
    add_operation_audit("quality.master_standard.delete", "standard", row.id, before=before, message="软删除")
    db.session.commit()
    return jsonify({"code": 0, "message": "标准已移除，可由数据库管理员恢复", "data": None})


# ========== 部门授权候选 ==========
@bp.get("/dept-options")
@require_auth
def dept_options():
    """使用部门授权网格 + 科室筛选的部门清单（来自院里真实部门）。"""
    depts = [row.name for row in Department.query.order_by(Department.name).all()]
    return jsonify({"code": 0, "message": "ok", "data": {"departments": depts}})


# ========== 人员登记（质量体系）：信息 + 部门分配 + 流程权限分配 ==========
@bp.get("/perm-options")
@require_auth
def perm_options():
    return jsonify({"code": 0, "message": "ok", "data": {"permissions": PERM_OPTIONS}})


@bp.get("/personnel")
@require_auth
def personnel_list():
    denied = _require_page("quality.personnel_registration.view", "无人员登记查看权限")
    if denied:
        return denied
    q = _personnel_filtered_query()
    total = q.count()
    page, size = _page_args()
    items = _edited_page(q, "personnel", page, size)
    accounts = {(p.code or '').strip().lower() for p, _ in items} - {''}
    users = {}
    for user in User.query.filter(db.func.lower(db.func.trim(User.account)).in_(accounts)).all() if accounts else []:
        key = user.account.strip().lower()
        if key in users:
            from sqlalchemy.exc import MultipleResultsFound
            raise MultipleResultsFound('Personnel account resolves to multiple users')
        users[key] = user
    missing_departments = {p.dept for p, _ in items if (p.code or '').strip().lower() not in users}
    departments = {}
    for department in Department.query.filter(Department.name.in_(missing_departments)).all() if missing_departments else []:
        departments.setdefault(department.name, department.id)
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": [_edited_row(p, edited_at, (users, departments)) for p, edited_at in items],
        "total": total, "page": page, "size": size}})


def _personnel_filtered_query():
    q = Personnel.query.filter(Personnel.deleted_at.is_(None))
    visible_departments = _visible_personnel_department_names()
    if visible_departments is not None:
        if not visible_departments:
            q = q.filter(Personnel.id == -1)
        else:
            conditions = [Personnel.dept.in_(visible_departments)]
            for department_name in visible_departments:
                conditions.extend([
                    Personnel.assigned_depts == department_name,
                    Personnel.assigned_depts.like(f"{department_name};%"),
                    Personnel.assigned_depts.like(f"%;{department_name}"),
                    Personnel.assigned_depts.like(f"%;{department_name};%"),
                ])
            q = q.filter(db.or_(*conditions))
    kw = (request.args.get("keyword") or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(db.or_(Personnel.name.like(like), Personnel.code.like(like), Personnel.dept.like(like)))
    dept = (request.args.get("dept") or "").strip()
    if dept:
        # The dropdown filters the displayed affiliation, not cross-department
        # assignments. The visibility scope above remains an independent guard.
        q = q.filter(Personnel.dept == dept)
    return q


@bp.get('/personnel/export')
@bp.get('/personnel/template')
@require_auth
def personnel_export():
    denied=_require_page('quality.personnel_registration.view','无人员登记查看权限')
    if denied: return denied
    from ..applications.personnel_exchange import export_roster
    rows=[] if request.path.endswith('/template') else [_personnel_row(p) for p in _personnel_filtered_query().order_by(Personnel.id).all()]
    return send_file(export_roster(rows),as_attachment=True,download_name='personnel-register.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@bp.post('/personnel/import-preview')
@bp.post('/personnel/import')
@require_auth
def personnel_import():
    denied=_require_page('quality.personnel_registration.view','无人员登记查看权限')
    if denied: return denied
    if not can_manage_users(g.current_user):
        return jsonify({'code':403,'message':'人员及账号批量导入需要用户管理权限','data':None}),200
    for action in ('quality.personnel.create','quality.personnel.update'):
        denied=_require_action(action)
        if denied: return denied
    upload=request.files.get('file')
    if not upload or not (upload.filename or '').lower().endswith('.xlsx'):
        return jsonify({'code':1,'message':'请上传人员登记xlsx文件','data':None}),200
    from ..applications.personnel_exchange import plan_roster, apply_roster
    try:
        content=upload.stream.read(5*1024*1024+1)
        if request.path.endswith('/import'):
            # Acquire SQLite write reservation before validating the preflight state.
            if db.engine.dialect.name=='sqlite':
                db.session.rollback()
                db.session.execute(db.text('BEGIN IMMEDIATE'))
        planned,summary=plan_roster(content,_visible_personnel_department_names())
        if request.path.endswith('/import-preview'):
            db.session.rollback()
            return jsonify({'code':0,'message':'预检完成，尚未写入','data':summary})
        if not summary['valid']: raise ValueError('整表校验未通过，请重新预检')
        if request.form.get('previewToken')!=summary['previewToken']:
            raise ValueError('文件或人员授权已变化，请重新预检后确认')
        apply_roster(g.current_user,planned)
        db.session.commit()
        summary["initialCredentials"] = getattr(g, "initial_credentials", [])
        return jsonify({'code':0,'message':'整表导入完成','data':summary})
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        return jsonify({'code':1,'message':str(exc) if isinstance(exc,ValueError) else '数据冲突，全部撤销，请重新预检','data':None}),200


@bp.get("/personnel/<int:pid>")
@require_auth
def personnel_detail(pid):
    denied = _require_page("quality.personnel_registration.view", "无人员登记查看权限")
    if denied:
        return denied
    p = Personnel.query.filter_by(id=pid, deleted_at=None).first()
    if not p or not _personnel_is_visible(p):
        return jsonify({"code": 1, "message": "人员不存在", "data": None}), 200
    reveal = "quality.personnel.sensitive.view" in g.current_user.action_codes()
    return jsonify({"code": 0, "message": "ok", "data": mask_private_fields(_personnel_row(p, full=True), reveal=reveal)})


def _apply_personnel(p, b):
    for attr, key in [("name", "name"), ("code", "code"), ("gender", "gender"), ("education", "education"),
                      ("title", "title"), ("major", "major"), ("grad_time", "gradTime"), ("position", "position"),
                      ("approval_position", "approvalPosition"),
                      ("test_scope", "testScope"), ("check_scope", "checkScope"), ("remark", "remark"),
                      ("dept", "dept"), ("birth_date", "birthDate"), ("mobile", "mobile"), ("ethnicity", "ethnicity"),
                      ("native_place", "nativePlace"), ("political", "political"), ("school", "school"),
                      ("work_start_time", "workStartTime"), ("join_time", "joinTime")]:
        if key in b:
            value = b[key]
            if attr == "approval_position" and value not in ("", None, "department_director", "institute_leader"):
                continue
            setattr(p, attr, value)
    if isinstance(b.get("assignedDepts"), list):
        p.assigned_depts = ";".join(d for d in b["assignedDepts"] if d)
    if isinstance(b.get("permissions"), list):
        p.permissions = ";".join(x for x in b["permissions"] if x)


@bp.post("/personnel")
@require_auth
def personnel_create():
    page_denied = _require_page("quality.personnel_registration.view", "无人员登记查看权限")
    if page_denied:
        return page_denied
    denied = _require_action("quality.personnel.create", "无人员档案新增权限")
    if denied:
        return denied
    b = request.get_json(silent=True) or {}
    if "departmentId" in b:
        try:
            department = db.session.get(Department, int(b.get("departmentId") or 0))
        except (TypeError, ValueError):
            department = None
        if not department:
            return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
        b["dept"] = department.name
        b.setdefault("assignedDepts", [department.name])
    scope_denied = _personnel_target_scope_denied(b)
    if scope_denied:
        return scope_denied
    if not (b.get("name") or "").strip() or not (b.get("code") or "").strip():
        return jsonify({"code": 1, "message": "姓名和人员编号为必填项", "data": None}), 200
    duplicate = Personnel.query.filter(
        db.func.lower(Personnel.code) == (b.get("code") or "").strip().lower(),
        Personnel.deleted_at.is_(None),
    ).first()
    if duplicate:
        return jsonify({"code": 1, "message": "人员编号已存在", "data": None}), 200
    p = Personnel()
    _apply_personnel(p, b)
    db.session.add(p)
    try:
        if can_manage_users(g.current_user):
            personnel_login(g.current_user,account=p.code,name=p.name,department_name=p.dept)
        db.session.flush()
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        return jsonify({"code":1,"message":str(exc) if isinstance(exc,ValueError) else "编号冲突，请刷新后重试","data":None}),200
    add_operation_audit("quality.personnel.create", "personnel", p.id, after=p.to_row())
    db.session.commit()
    return jsonify({"code": 0, "message": "已新增", "data": {**_personnel_row(p), "initialCredentials": getattr(g, "initial_credentials", [])}})


@bp.put("/personnel/<int:pid>")
@require_auth
@audited_form("personnel", "pid")
def personnel_update(pid):
    page_denied = _require_page("quality.personnel_registration.view", "无人员登记查看权限")
    if page_denied:
        return page_denied
    denied = _require_action("quality.personnel.update", "无人员档案修改权限")
    if denied:
        return denied
    p = Personnel.query.filter_by(id=pid, deleted_at=None).first()
    if not p or not _personnel_is_visible(p):
        return jsonify({"code": 1, "message": "人员不存在", "data": None}), 200
    before = _personnel_row(p, full=True)
    body = request.get_json(silent=True) or {}
    # Older forms echo a masked detail value even when editing an unrelated field.
    if isinstance(body.get("mobile"), str) and "*" in body["mobile"]:
        body.pop("mobile")
    if "departmentId" in body:
        try:
            department = db.session.get(Department, int(body.get("departmentId") or 0))
        except (TypeError, ValueError):
            department = None
        if not department:
            return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
        body["dept"] = department.name
        body.setdefault("assignedDepts", [department.name])
    linked_user = _linked_personnel_user(p)
    proposed_name = body.get("name", p.name)
    proposed_code = body.get("code", p.code)
    if (
        not isinstance(proposed_name, str)
        or not proposed_name.strip()
        or not isinstance(proposed_code, str)
        or not proposed_code.strip()
    ):
        return jsonify({"code": 1, "message": "姓名和人员编号为必填项", "data": None}), 200
    normalized_code = proposed_code.strip()
    if linked_user and "code" in body and normalized_code.lower() != linked_user.account.lower():
        return jsonify({"code": 1, "message": "已创建账号的人员编号不可修改", "data": None}), 200
    scope_denied = _personnel_target_scope_denied(body, p)
    if scope_denied:
        return scope_denied
    if linked_user and (
        "departmentId" in body or "accountEnabled" in body
    ) and "system.user.view" not in g.current_user.permission_codes():
        return jsonify({"code": 403, "message": "调整账号部门或状态需要用户管理权限", "data": None}), 200
    duplicate = Personnel.query.filter(
        Personnel.id != p.id,
        db.func.lower(Personnel.code) == normalized_code.lower(),
        Personnel.deleted_at.is_(None),
    ).first()
    if duplicate:
        return jsonify({"code": 1, "message": "人员编号已存在", "data": None}), 200
    _apply_personnel(p, body)

    if linked_user:
        linked_user.name = (p.name or "").strip()
        if "departmentId" in body:
            try:
                department_id = int(body.get("departmentId") or 0)
            except (TypeError, ValueError):
                department_id = 0
            department = db.session.get(Department, department_id)
            if not department:
                return jsonify({"code": 1, "message": "部门不存在", "data": None}), 200
            if linked_user.department_id != department.id:
                old_department = linked_user.department
                linked_user.department = department
                synchronize_user_department(
                    linked_user,
                    old_department,
                    department,
                    actor=g.current_user,
                )
            p.dept = department.name
        if "roleName" in body and "system.user.view" in g.current_user.permission_codes():
            linked_user.role_name = (body.get("roleName") or "自定义角色").strip()
        if "accountEnabled" in body:
            linked_user.enabled = bool(body.get("accountEnabled"))

    if not linked_user and can_manage_users(g.current_user):
        try:
            personnel_login(g.current_user,account=p.code,name=p.name,department_name=p.dept)
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            return jsonify({"code":1,"message":str(exc) if isinstance(exc,ValueError) else "编号冲突，请刷新后重试","data":None}),200
    after = _personnel_row(p, full=True)
    add_operation_audit("quality.personnel.update", "personnel", p.id, before=before, after=after)
    db.session.commit()
    return jsonify({"code": 0, "message": "已保存", "data": {**_personnel_row(p), "initialCredentials": getattr(g, "initial_credentials", [])}})


@bp.delete("/personnel/<int:pid>")
@require_auth
def personnel_delete(pid):
    page_denied = _require_page("quality.personnel_registration.view", "无人员登记查看权限")
    if page_denied:
        return page_denied
    denied = _require_action("quality.personnel.delete", "无人员档案移除权限")
    if denied:
        return denied
    row = Personnel.query.filter_by(id=pid, deleted_at=None).first()
    if not row or not _personnel_is_visible(row):
        return jsonify({"code": 1, "message": "人员不存在", "data": None}), 200
    linked_user = _linked_personnel_user(row)
    if linked_user and linked_user.id == g.current_user.id:
        return jsonify({"code": 1, "message": "不能移出当前登录账号", "data": None}), 200
    if linked_user and linked_user.role_key == "admin":
        return jsonify({"code": 1, "message": "系统管理员不能从人员名册移出", "data": None}), 200
    before = _personnel_row(row)
    row.deleted_at = datetime.utcnow()
    if linked_user:
        linked_user.enabled = False
    add_operation_audit(
        "quality.personnel.delete",
        "personnel",
        row.id,
        before=before,
        after={"accountDisabled": bool(linked_user)},
        message="软删除人员档案并停用已关联登录账号",
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "人员档案已移除，可由数据库管理员恢复", "data": None})


# ========== 检测标准基础信息库（质量体系，图1） ==========
def _standard_library_access():
    user = g.current_user
    permissions = set(user.permission_codes())
    if can_correct_business_data(user) or user.role_key == "admin" or "quality.standard_library.view" in permissions:
        return "full"
    if "quality.standard_library_department.view" in permissions:
        return "department"
    return ""


def _standard_library_access_denied(full_required=False):
    access = _standard_library_access()
    if access and (not full_required or access == "full"):
        return None
    message = (
        "标准基础信息库[科室]仅支持查看本人所在部门的授权标准"
        if full_required
        else "无标准基础信息库查看权限"
    )
    return jsonify({"code": 403, "message": message, "data": None}), 200


@bp.get("/std-library")
@require_auth
def std_library_list():
    denied = _standard_library_access_denied()
    if denied:
        return denied
    q = _standard_library_query()
    total = q.count()
    page, size = _page_args()
    items = _edited_page(q, "controlled_standard", page, size)
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": [_edited_row(s, edited_at) for s, edited_at in items],
        "total": total, "page": page, "size": size}})


@bp.post("/std-library/display-names")
@require_auth
def standard_display_names():
    """Labels for already selected standards; no qualification/ownership data."""
    from ..functions.report_standard_text import load_report_standard_names
    body = request.get_json(silent=True) or {}
    codes = body.get('codes') if isinstance(body, dict) else None
    if not isinstance(codes, list) or len(codes) > 200 or any(
        not isinstance(code, str) or not code.strip() or len(code) > 160 for code in codes
    ):
        return jsonify({'code':1, 'message':'标准编号列表格式不正确（最多200项，每项最多160字符）', 'data':None}), 200
    return jsonify({'code':0, 'message':'ok', 'data':load_report_standard_names(list(dict.fromkeys(codes)))}), 200


@bp.get("/std-library/judgment-search")
@require_auth
def judgment_standard_search():
    """Public standard labels for judgement only; never accreditation evidence.

    Authentication matches the existing sample standard search. Deliberately
    return no ownership, capability, scope or authorization metadata.
    """
    keyword = (request.args.get("keyword") or "").strip()
    page, size = _page_args()
    query = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None))
    today = date.today().isoformat()
    # to_row().status conflates out_of_scope with lifecycle; do not use it here.
    query = query.filter(
        db.or_(StdLibraryItem.void_date.is_(None), StdLibraryItem.void_date == '', StdLibraryItem.void_date > today),
        db.or_(StdLibraryItem.impl_date.is_(None), StdLibraryItem.impl_date == '', StdLibraryItem.impl_date <= today),
    )
    if keyword:
        query = query.filter(db.or_(
            StdLibraryItem.code.icontains(keyword, autoescape=True),
            StdLibraryItem.name.icontains(keyword, autoescape=True),
        ))
    total = query.count()
    start = (page - 1) * size
    rows = [{"id": item.id, "code": item.code, "name": item.name, "status": "现行"}
            for item in query.order_by(StdLibraryItem.code, StdLibraryItem.id).offset(start).limit(size).all()]
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": rows, "total": total, "page": page, "size": size,
    }})


@bp.get("/std-library/search")
@require_auth
@reuse_preflight_reads
def std_library_search():
    """检测依据/判定标准分页查询：保留部门授权边界并返回范围元数据。"""
    from ..platform.identity import denied_standard_item_ids, standard_matches_department
    from ..authorization_scope import standard_has_department
    from ..models import CapabilityEntry, CapabilityImportBatch, Department

    kw = (request.args.get("keyword") or "").strip()
    user = g.current_user
    requested_dept = (request.args.get("dept") or "").strip()
    admin = user_has_org_wide_scope(user)
    dept = (
        requested_dept
        if admin
        else (user.department.name if user.department else "")
    )
    capability_only = request.args.get("capabilityOnly") == "1"
    scope_filter = (request.args.get("scopeFilter") or "all").strip().lower()
    if scope_filter not in {"all", "cnas", "cma", "single"}:
        return jsonify({"code": 1, "message": "标准范围筛选值无效", "data": None}), 200
    page, size = _page_args()
    enforce_capability = capability_only
    denied = set() if admin else denied_standard_item_ids(user)
    q = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None))
    # Resolve saved identities through the same authorization and lifecycle filters.
    raw_ids = request.args.get("ids")
    if raw_ids is not None:
        try:
            ids = [int(value) for value in raw_ids.split(',')]
            if not ids or len(ids) > 200 or any(value <= 0 for value in ids):
                raise ValueError()
        except ValueError:
            return jsonify({"code": 1, "message": "标准记录编号格式无效", "data": None}), 200
        q = q.filter(StdLibraryItem.id.in_(ids))
    # Onsite mode changes the actual address, not standard eligibility.
    if kw:
        q = _filter_standard_library_keyword(q, kw)
    items = [
        item
        for item in q.order_by(StdLibraryItem.code, StdLibraryItem.id).all()
        if item.id not in denied and standard_has_department(item)
        and ((admin and not dept) or standard_matches_department(item, dept))
        and item.to_row()["status"] == "现行"
    ]

    # Most picker searches need metadata for one page only. Qualification-only
    # filters still run before pagination because they affect the result count.
    page_total = len(items) if not enforce_capability and scope_filter == 'all' else None
    if page_total is not None:
        items = items[(page - 1) * size:page * size]
    from ..applications.quality_resources.testing_locations import workbook_capability_owners
    capability_owners = workbook_capability_owners()
    capability_query = CapabilityEntry.query.filter(
        CapabilityEntry.standard_item_id.in_([capability_owners.get(item.id, item.id) for item in items] or [-1]))
    capability_by_standard = {}
    for capability in capability_query.all():
        capability_by_standard.setdefault(capability.standard_item_id, []).append(capability)

    rows = []
    for s in items:
        capabilities = capability_by_standard.get(capability_owners.get(s.id, s.id), [])
        if enforce_capability and not capabilities:
            continue
        auth_text = (s.auth_kind or "").upper()
        cma = "CMA" in auth_text and not any(
            marker in auth_text for marker in ("CMA未授权", "非CMA范围", "无CMA")
        )
        cnas = "CNAS" in auth_text and not any(
            marker in auth_text for marker in ("CNAS未授权", "非CNAS范围", "无CNAS")
        )
        single_list = (
            s.to_row()["status"] == "现行"
            and not s.out_of_scope
            and "一单一库" in (s.auth_kind or "")
            and "非一单一库" not in (s.auth_kind or "")
        )
        from ..standard_control import single_list_flag
        single_list = single_list and single_list_flag(s.auth_kind)
        # Parameter search/type/site conditions never revoke standard qualifications.
        row = {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "authKind": s.auth_kind or "",
            "status": s.to_row()["status"],
            "singleList": single_list,
            "cma": cma,
            "cnas": cnas,
            "useDepts": s.to_row()["useDepts"],
            "controlledNo": s.controlled_no or "",
            "capabilityTypes": sorted({row.capability_type for row in capabilities}),
            "isOnsiteStandard": bool(s.is_onsite_standard),
            "sites": sorted({row.site for row in capabilities}),
            "location": s.location or "",
        }
        if scope_filter == "cnas" and not cnas:
            continue
        if scope_filter == "cma" and not cma:
            continue
        if scope_filter == "single" and not single_list:
            continue
        rows.append(row)

    total = len(rows) if page_total is None else page_total
    start = (page - 1) * size
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": rows[start:start + size] if page_total is None else rows,
        "total": total,
        "page": page,
        "size": size,
    }})


STANDARD_LIBRARY_FIELDS = [
    ("controlledNo", "受控号"),
    ("code", "标准编号"),
    ("name", "标准名称"),
    ("parameters", "检测参数"),
    ("authKind", "标准资质类别"),
    ("outOfScope", "是否在资质范围外"),
    ("category", "类别"),
    ("location", "地点"),
    ("issueCount", "发放数量"),
    ("issuer", "发放人"),
    ("useDepts", "使用部门"),
    ("implDate", "实施日期"),
    ("voidDate", "作废日期"),
    ("delayDays", "延期时间(天)"),
    ("replaceNo", "替换标准号"),
    ("isEnglish", "是否英文标准"),
    ("remark", "备注"),
]


def _standard_library_workbook(rows=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "检测标准基础信息库"
    sheet.append([label for _key, label in STANDARD_LIBRARY_FIELDS])
    if rows:
        for row in rows:
            data = row.to_row()
            data["outOfScope"] = "是" if data.get("outOfScope") else "否"
            data["isEnglish"] = "是" if data.get("isEnglish") else "否"
            data["useDepts"] = ";".join(data.get("useDepts") or [])
            sheet.append([data.get(key, "") for key, _label in STANDARD_LIBRARY_FIELDS])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(
            42,
            max(12, max(len(str(cell.value or "")) for cell in column) + 2),
        )
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _standard_library_query():
    q = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None))
    access = _standard_library_access()
    department_scoped = (
        request.args.get("scope") == "department"
        or access == "department"
    )
    if department_scoped:
        department = g.current_user.department
        if not department:
            q = q.filter(db.false())
        elif department.parent_id is not None:
            department_name = department.name
            q = q.filter(db.or_(
                StdLibraryItem.use_depts == department_name,
                StdLibraryItem.use_depts.like(f"{department_name};%"),
                StdLibraryItem.use_depts.like(f"%;{department_name}"),
                StdLibraryItem.use_depts.like(f"%;{department_name};%"),
            ))
    kw = (request.args.get("keyword") or "").strip()
    if kw:
        q = _filter_standard_library_keyword(q, kw)
    dept = (request.args.get("dept") or "").strip()
    if dept and not department_scoped:
        q = q.filter(db.or_(
            StdLibraryItem.use_depts == dept,
            StdLibraryItem.use_depts.like(f"{dept};%"),
            StdLibraryItem.use_depts.like(f"%;{dept}"),
            StdLibraryItem.use_depts.like(f"%;{dept};%"),
        ))
    auth = (request.args.get("authKind") or "").strip()
    if auth:
        q = q.filter(StdLibraryItem.auth_kind.like(f"%{auth}%"))
    return q


def _filter_standard_library_keyword(query, keyword):
    """Search all maintained standard fields and linked capability details."""
    text = (keyword or "").strip()
    if not text:
        return query
    like = f"%{text}%"
    controlled_conditions = [
        column.ilike(like)
        for column in (
            StdLibraryItem.controlled_no,
            StdLibraryItem.code,
            StdLibraryItem.name,
            StdLibraryItem.auth_kind,
            StdLibraryItem.category,
            StdLibraryItem.location,
            StdLibraryItem.issue_count,
            StdLibraryItem.issuer,
            StdLibraryItem.use_depts,
            StdLibraryItem.impl_date,
            StdLibraryItem.void_date,
            StdLibraryItem.delay_days,
            StdLibraryItem.replace_no,
            StdLibraryItem.remark,
        )
    ]
    master_match = db.exists().where(db.and_(
        Standard.id == StdLibraryItem.standard_id,
        db.or_(
            Standard.code.like(like),
            Standard.name.like(like),
            Standard.auth_kind.like(like),
            Standard.department.like(like),
            Standard.category.like(like),
            Standard.status.like(like),
        ),
    ))
    from sqlalchemy import case
    from ..applications.quality_resources.testing_locations import workbook_capability_owners
    aliases = {item: owner for item, owner in workbook_capability_owners().items() if item != owner}
    owner_column = case(aliases, value=StdLibraryItem.id, else_=StdLibraryItem.id) if aliases else StdLibraryItem.id
    capability_match = db.exists().where(db.and_(
        CapabilityEntry.standard_item_id == owner_column,
        db.or_(
            CapabilityEntry.capability_type.like(like),
            CapabilityEntry.certificate_no.like(like),
            CapabilityEntry.site.like(like),
            CapabilityEntry.section_path.like(like),
            CapabilityEntry.object_seq.like(like),
            CapabilityEntry.object_name.like(like),
            CapabilityEntry.item_seq.like(like),
            CapabilityEntry.item_name.like(like),
            CapabilityEntry.standard_code.like(like),
            CapabilityEntry.standard_name.like(like),
            CapabilityEntry.method_clause.like(like),
            CapabilityEntry.restriction.like(like),
            CapabilityEntry.source_file.like(like),
            CapabilityEntry.mapping_status.like(like),
        ),
    ))
    semantic_conditions = []
    normalized = text.casefold()
    if normalized in {"资质范围外", "范围外"}:
        semantic_conditions.append(StdLibraryItem.out_of_scope.is_(True))
    if normalized in {"英文", "英文标准"}:
        semantic_conditions.append(StdLibraryItem.is_english.is_(True))
    if normalized == "已作废":
        semantic_conditions.append(db.and_(
            StdLibraryItem.void_date.is_not(None),
            StdLibraryItem.void_date <= date.today().isoformat(),
        ))
    if normalized == "待实施":
        semantic_conditions.append(StdLibraryItem.impl_date > date.today().isoformat())
    if normalized == "现行":
        semantic_conditions.append(db.and_(
            StdLibraryItem.out_of_scope.is_(False),
            db.or_(
                StdLibraryItem.void_date.is_(None),
                StdLibraryItem.void_date > date.today().isoformat(),
            ),
            db.or_(
                StdLibraryItem.impl_date.is_(None),
                StdLibraryItem.impl_date <= date.today().isoformat(),
            ),
        ))
    if normalized in {"非英文标准", "中文标准"}:
        semantic_conditions.append(StdLibraryItem.is_english.is_(False))
    if normalized in {"资质范围内", "范围内"}:
        semantic_conditions.append(StdLibraryItem.out_of_scope.is_(False))
    return query.filter(db.or_(
        *controlled_conditions,
        master_match,
        capability_match,
        *semantic_conditions,
    ))


@bp.get("/std-library/template")
@require_auth
def std_library_template():
    denied = _standard_library_access_denied(full_required=True)
    if denied:
        return denied
    return send_file(
        _standard_library_workbook(),
        as_attachment=True,
        download_name="standard-library-import-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/std-library/export")
@require_auth
def std_library_export():
    denied = _standard_library_access_denied()
    if denied:
        return denied
    rows = _standard_library_query().order_by(
        StdLibraryItem.controlled_no,
        StdLibraryItem.code,
        StdLibraryItem.id,
    ).all()
    return send_file(
        _standard_library_workbook(rows),
        as_attachment=True,
        download_name=f"standard-library-{date.today().isoformat()}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _standard_import_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是", "有"}


@bp.post("/std-library/import")
@require_auth
def std_library_import():
    access_denied = _standard_library_access_denied(full_required=True)
    if access_denied:
        return access_denied
    for action, message in (
        ("quality.standard.create", "无标准新增权限"),
        ("quality.standard.update", "无标准修改权限"),
        ("quality.standard.authorize", "无标准部门授权维护权限"),
    ):
        denied = _require_action(action, message)
        if denied:
            return denied
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"code": 1, "message": "请选择 Excel 标准信息文件", "data": None}), 200
    try:
        workbook = load_workbook(BytesIO(upload.read()), read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
    except Exception:
        return jsonify({"code": 1, "message": "Excel 文件无法读取，请使用系统模板", "data": None}), 200
    if not values:
        return jsonify({"code": 1, "message": "上传文件没有数据", "data": None}), 200
    header_map = {_cell_text(value): index for index, value in enumerate(values[0])}
    missing = [
        label for key, label in STANDARD_LIBRARY_FIELDS
        if key in {"code", "name"} and label not in header_map
    ]
    if missing:
        return jsonify({
            "code": 1,
            "message": "上传文件缺少必填列：" + "、".join(missing),
            "data": None,
        }), 200
    seen = set()
    created = updated = 0
    for row_number, values_row in enumerate(values[1:], start=2):
        body = {}
        for key, label in STANDARD_LIBRARY_FIELDS:
            index = header_map.get(label)
            if index is not None and index < len(values_row):
                body[key] = _cell_text(values_row[index])
        code = body.get("code", "")
        name = body.get("name", "")
        controlled_no = body.get("controlledNo", "")
        if not code and not name:
            continue
        if not code or not name:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"第 {row_number} 行标准编号和标准名称必须同时填写",
                "data": None,
            }), 200
        key = (controlled_no, code)
        if key in seen:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"上传文件内受控号和标准编号重复：{controlled_no or '无受控号'} / {code}",
                "data": None,
            }), 200
        seen.add(key)
        matches = StdLibraryItem.query.filter(
            StdLibraryItem.code == code,
            db.func.coalesce(StdLibraryItem.controlled_no, "") == controlled_no,
            StdLibraryItem.deleted_at.is_(None),
        ).all()
        if len(matches) > 1:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"线上存在重复标准，需先处理：{controlled_no or '无受控号'} / {code}",
                "data": None,
            }), 200
        standard = matches[0] if matches else StdLibraryItem()
        before = standard.to_row() if matches else None
        body["outOfScope"] = _standard_import_bool(body.get("outOfScope"))
        body["isEnglish"] = _standard_import_bool(body.get("isEnglish"))
        body["useDepts"] = [
            part.strip()
            for part in re.split(r"[;；,，、]", body.get("useDepts", ""))
            if part.strip()
        ]
        _apply_standard(standard, body)
        if not matches:
            db.session.add(standard)
            db.session.flush()
            created += 1
        else:
            updated += 1
        add_operation_audit(
            "quality.standard.import",
            "controlled_standard",
            standard.id,
            before=before,
            after=standard.to_row(),
        )
    db.session.commit()
    return jsonify({
        "code": 0,
        "message": f"标准信息上传完成：新增 {created} 条，更新 {updated} 条",
        "data": {"created": created, "updated": updated},
    })


@bp.get("/std-library/<int:sid>")
@require_auth
def std_library_detail(sid):
    denied = _standard_library_access_denied()
    if denied:
        return denied
    s = _standard_library_query().filter(StdLibraryItem.id == sid).first()
    if not s:
        return jsonify({"code": 1, "message": "标准不存在", "data": None}), 200
    return jsonify({"code": 0, "message": "ok", "data": s.to_row()})


@bp.get('/std-library/parameter-catalog')
@require_auth
def parameter_standard_search():
    denied = _standard_library_access_denied(full_required=True)
    if denied:
        return denied
    keyword = (request.args.get('keyword') or '').strip()
    if len(keyword) > 200:
        return jsonify({'code': 1, 'message': '搜索内容过长', 'data': None}), 200
    query = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None))
    for term in keyword.split():
        like = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(db.or_(StdLibraryItem.code.ilike(like, escape='\\'),
                                   StdLibraryItem.name.ilike(like, escape='\\')))
    page, size = _page_args()
    total = query.count()
    rows = query.order_by(StdLibraryItem.id.desc()).offset((page - 1) * size).limit(size).all()
    return jsonify({'code': 0, 'message': 'ok', 'data': {
        'rows': [{'id': s.id, 'code': s.code, 'name': s.name, 'controlledNo': s.controlled_no} for s in rows],
        'total': total, 'page': page, 'size': size}})


@bp.route('/std-library/<int:sid>/parameters', methods=['GET', 'POST'])
@bp.put('/std-library/<int:sid>/parameters/<int:entry_id>')
@require_auth
@reuse_preflight_reads
def standard_parameters(sid, entry_id=None):
    from ..applications.quality_resources.standard_parameters import (
        owner_id, shared_source, parameter_row, validate_values, create_parameter, update_parameter,
    )
    from sqlalchemy.orm import selectinload
    denied = _standard_library_access_denied(full_required=True)
    if denied:
        return denied
    standard = StdLibraryItem.query.filter_by(id=sid, deleted_at=None).first()
    if not standard:
        return jsonify({'code': 1, 'message': '标准不存在', 'data': None}), 200
    query = CapabilityEntry.query.filter_by(standard_item_id=owner_id(standard))
    if request.method == 'GET':
        keyword = (request.args.get('keyword') or '').strip()
        if len(keyword) > 200:
            return jsonify({'code': 1, 'message': '搜索内容过长', 'data': None}), 200
        for term in keyword.split():
            like = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            query = query.filter(db.or_(CapabilityEntry.item_name.ilike(like, escape='\\'),
                CapabilityEntry.object_name.ilike(like, escape='\\'), CapabilityEntry.site.ilike(like, escape='\\')))
        page, size = _page_args()
        total = query.count()
        rows = query.options(selectinload(CapabilityEntry.departments)).order_by(
            CapabilityEntry.id.desc()).offset((page - 1) * size).limit(size).all()
        return jsonify({'code': 0, 'message': 'ok', 'data': {
            'rows': [parameter_row(e) for e in rows], 'total': total, 'page': page, 'size': size,
            'departments': [d for d in (standard.use_depts or '').split(';') if d],
            'sharedSource': shared_source(standard),
        }})
    denied = _require_action('quality.standard.update' if entry_id else 'quality.standard.create')
    if denied:
        return denied
    entry = query.filter_by(id=entry_id).with_for_update().first() if entry_id else None
    if entry_id and not entry:
        return jsonify({'code': 1, 'message': '参数不存在或不属于该标准', 'data': None}), 200
    body = request.get_json(silent=True) or {}
    try:
        values = validate_values(body, standard, entry=entry)
        copied = None
        if body.get('copyFromId') is not None:
            if entry or type(body['copyFromId']) is not int:
                raise ValueError('复制来源无效')
            copied = db.session.get(CapabilityEntry, body['copyFromId'])
            if not copied or not copied.standard_item or copied.standard_item.deleted_at:
                raise ValueError('复制来源不存在')
        before = parameter_row(entry) if entry else None
        saved = update_parameter(entry, values) if entry else create_parameter(standard, values, copied=copied)
        after = parameter_row(saved)
        add_operation_audit('quality.standard.parameter.update' if entry else 'quality.standard.parameter.create',
            'standard_parameter', saved.id, before=before, after=after, message=values[-1])
        db.session.commit()
        return jsonify({'code': 0, 'message': '参数已保存', 'data': after})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'code': 1, 'message': str(exc), 'data': None}), 200


def _apply_standard(s, body):
    for attr, key in [("controlled_no", "controlledNo"), ("code", "code"), ("name", "name"),
                      ("parameters", "parameters"),
                      ("auth_kind", "authKind"), ("category", "category"), ("location", "location"),
                      ("issue_count", "issueCount"), ("issuer", "issuer"), ("impl_date", "implDate"),
                      ("void_date", "voidDate"), ("delay_days", "delayDays"), ("replace_no", "replaceNo"),
                      ("remark", "remark")]:
        if key in body:
            setattr(s, attr, (body[key] or "").strip() if isinstance(body[key], str) else body[key])
    if "outOfScope" in body:
        s.out_of_scope = bool(body["outOfScope"])
    if "isEnglish" in body:
        s.is_english = bool(body["isEnglish"])
    if "isOnsiteStandard" in body:
        if type(body["isOnsiteStandard"]) is not bool:
            raise ValueError("是否现场标准必须为布尔值")
        s.is_onsite_standard = body["isOnsiteStandard"]
    if isinstance(body.get("useDepts"), list):
        s.use_depts = ";".join(d.strip() for d in body["useDepts"] if isinstance(d, str) and d.strip())


@bp.get("/guard-notices")
@require_auth
def guard_notices():
    denied = _standard_library_access_denied(full_required=True)
    if denied:
        return denied
    from ..models import OperationAudit
    from ..applications.report_lifecycle import scoped_report_query
    visible = scoped_report_query(Report.query, g.current_user).with_entities(Report.report_no)
    rows = OperationAudit.query.filter_by(action='quality.guard_notice').filter(OperationAudit.object_id.in_(visible)).order_by(OperationAudit.id.desc()).limit(100).all()
    return jsonify(code=0, message='ok', data={'rows': [dict(id=r.id, reportNo=r.object_id, message=r.message,
        time=r.created_at.isoformat(), evidence=r.after_data) for r in rows]})


@bp.get("/std-library/<int:sid>/identity-impact")
@require_auth
def standard_identity_impact(sid):
    denied = _standard_library_access_denied(full_required=True)
    if denied:
        return denied
    row = db.session.get(StdLibraryItem, sid)
    if not row or row.deleted_at:
        return jsonify(code=1, message='标准不存在', data=None), 200
    from ..standard_resolution import affected_reports, resolution_choices, identity_revision
    reports = affected_reports(row.code, g.current_user)
    return jsonify(code=0, message='ok', data={'rows': [dict(reportNo=r.report_no, department=r.department,
        status=r.status, revision=identity_revision(r), choices=resolution_choices(r)) for r in reports], 'total': len(reports)})


@bp.post("/std-library/<int:sid>/resolve-report-identities")
@require_auth
def standard_bulk_resolution(sid):
    denied = _standard_library_access_denied(full_required=True) or _require_action('quality.standard.update')
    if denied:
        return denied
    from ..standard_resolution import affected_reports, resolve_identities, identity_revision
    row = db.session.get(StdLibraryItem, sid)
    if not row or row.deleted_at:
        return jsonify(code=1, message='标准不存在', data=None), 200
    body = request.get_json(silent=True) or {}
    changes = body.get('reports')
    if not isinstance(changes, list) or not changes or len(changes) > 100:
        return jsonify(code=1, message='请选择1至100份在途报告', data=None), 200
    affected = {r.report_no:r for r in affected_reports(row.code, g.current_user)}
    try:
        for change in changes:
            report = affected.get(change.get('reportNo')) if isinstance(change, dict) else None
            if not report:
                raise ValueError('在途报告范围已变化，请刷新后重选')
            db.session.refresh(report, with_for_update=True)
            if identity_revision(report) != change.get('revision'):
                raise ValueError('报告内容已变化，请刷新后重新确认')
            resolve_identities(report, g.current_user, change.get('selections'), body.get('reason'))
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(code=1, message=str(exc), data=None), 200
    return jsonify(code=0, message='已确认所选报告标准关联，请在各流程重新校核', data={'count':len(changes)})


@bp.post("/std-library")
@require_auth
def std_library_create():
    access_denied = _standard_library_access_denied(full_required=True)
    if access_denied:
        return access_denied
    denied = _require_action("quality.standard.create")
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    if "isOnsiteStandard" in body and type(body["isOnsiteStandard"]) is not bool:
        return jsonify({"code": 1, "message": "是否现场标准必须为布尔值", "data": None}), 200
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip()
    if not code or not name:
        return jsonify({"code": 1, "message": "标准编号和标准名称为必填项", "data": None}), 200
    controlled_no = (body.get("controlledNo") or "").strip()
    matching = StdLibraryItem.query.filter(
        StdLibraryItem.code == code,
        db.func.coalesce(StdLibraryItem.controlled_no, "") == controlled_no,
    )
    active = matching.filter(StdLibraryItem.deleted_at.is_(None)).first()
    if active:
        return jsonify({"code": 1, "message": "相同受控号和标准编号已存在", "data": None}), 200
    row = matching.filter(StdLibraryItem.deleted_at.is_not(None)).order_by(StdLibraryItem.id.desc()).first()
    before = row.to_row() if row else None
    if row:
        row.deleted_at = None
    else:
        row = StdLibraryItem()
        db.session.add(row)
    row.controlled_no = controlled_no
    _apply_standard(row, body)
    db.session.flush()
    add_operation_audit(
        "quality.standard.create",
        "controlled_standard",
        row.id,
        before=before,
        after=row.to_row(),
        message="恢复软删除记录" if before else "",
    )
    db.session.commit()
    message = "受控标准已恢复" if before else "受控标准已新增"
    from ..standard_resolution import affected_reports
    affected = affected_reports(row.code, g.current_user)
    return jsonify({"code": 0, "message": message, "data": {**row.to_row(), 'identityImpactCount': len(affected)}})


@bp.put("/std-library/<int:sid>")
@require_auth
@audited_form("standard-library", "sid")
def std_library_update(sid):
    access_denied = _standard_library_access_denied(full_required=True)
    if access_denied:
        return access_denied
    denied = _require_action("quality.standard.update")
    if denied:
        return denied
    s = StdLibraryItem.query.filter_by(id=sid, deleted_at=None).first()
    if not s:
        return jsonify({"code": 1, "message": "标准不存在", "data": None}), 200
    before = s.to_row()
    b = request.get_json(silent=True) or {}
    if "isOnsiteStandard" in b and type(b["isOnsiteStandard"]) is not bool:
        return jsonify({"code": 1, "message": "是否现场标准必须为布尔值", "data": None}), 200
    if "useDepts" in b and "quality.standard.authorize" not in g.current_user.action_codes():
        return jsonify({"code": 403, "message": "无标准部门授权维护权限", "data": None}), 200
    _apply_standard(s, b)
    if not (s.code or "").strip() or not (s.name or "").strip():
        return jsonify({"code": 1, "message": "标准编号和标准名称为必填项", "data": None}), 200
    duplicate = StdLibraryItem.query.filter(
        StdLibraryItem.id != s.id,
        StdLibraryItem.code == s.code,
        db.func.coalesce(StdLibraryItem.controlled_no, "") == (s.controlled_no or "").strip(),
        StdLibraryItem.deleted_at.is_(None),
    ).first()
    from ..applications.quality_resources.testing_locations import workbook_item_ids
    imported_ids = workbook_item_ids()
    retained_identity = (s.id in imported_ids and duplicate is not None and duplicate.id in imported_ids
        and s.code == before['code'] and (s.controlled_no or '') == (before.get('controlledNo') or ''))
    if duplicate and not retained_identity:
        return jsonify({"code": 1, "message": "相同受控号和标准编号已存在", "data": None}), 200
    if 'isOnsiteStandard' in b and s.id in imported_ids:
        # One standard-level onsite flag; language/date records are not separate
        # permissions to perform onsite work. History stays untouched.
        for sibling in StdLibraryItem.query.filter(StdLibraryItem.standard_id == s.standard_id,
                StdLibraryItem.deleted_at.is_(None), StdLibraryItem.id != s.id).all():
            if sibling.id in imported_ids and sibling.is_onsite_standard != s.is_onsite_standard:
                sibling_before = sibling.to_row()
                sibling.is_onsite_standard = s.is_onsite_standard
                add_operation_audit('quality.standard.update', 'controlled_standard', sibling.id,
                    before=sibling_before, after=sibling.to_row(), message='同标准现场属性同步')
    add_operation_audit("quality.standard.update", "controlled_standard", s.id, before=before, after=s.to_row())
    db.session.commit()
    return jsonify({"code": 0, "message": "已保存", "data": s.to_row()})


@bp.put("/std-library/<int:sid>/departments")
@require_auth
def std_library_update_departments(sid):
    access_denied = _standard_library_access_denied(full_required=True)
    if access_denied:
        return access_denied
    denied = _require_action("quality.standard.authorize", "无标准部门授权维护权限")
    if denied:
        return denied
    standard = StdLibraryItem.query.filter_by(id=sid, deleted_at=None).first()
    if not standard:
        return jsonify({"code": 1, "message": "标准不存在", "data": None}), 200
    body = request.get_json(silent=True) or {}
    departments = body.get("departments")
    if not isinstance(departments, list):
        return jsonify({"code": 1, "message": "授权部门格式无效", "data": None}), 200
    valid_names = {row.name for row in Department.query.all()}
    normalized = []
    for name in departments:
        text = str(name or "").strip()
        if text and text not in normalized:
            if text not in valid_names:
                return jsonify({
                    "code": 1,
                    "message": f"部门不存在或已停用：{text}",
                    "data": None,
                }), 200
            normalized.append(text)
    before = standard.to_row()
    standard.use_depts = ";".join(normalized)
    add_operation_audit(
        "quality.standard.authorize",
        "controlled_standard",
        standard.id,
        before=before,
        after=standard.to_row(),
        message="更新标准授权部门",
    )
    db.session.commit()
    return jsonify({
        "code": 0,
        "message": "标准授权部门已保存",
        "data": standard.to_row(),
    })


@bp.delete("/std-library/<int:sid>")
@require_auth
def std_library_delete(sid):
    access_denied = _standard_library_access_denied(full_required=True)
    if access_denied:
        return access_denied
    denied = _require_action("quality.standard.delete", "无受控标准移除权限")
    if denied:
        return denied
    row = StdLibraryItem.query.filter_by(id=sid, deleted_at=None).first()
    if not row:
        return jsonify({"code": 1, "message": "标准不存在", "data": None}), 200
    before = row.to_row()
    row.deleted_at = datetime.utcnow()
    add_operation_audit(
        "quality.standard.delete",
        "controlled_standard",
        row.id,
        before=before,
        message="软删除",
    )
    db.session.commit()
    return jsonify({"code": 0, "message": "受控标准已移除", "data": None})


@bp.post("/std-library/<int:sid>/void")
@require_auth
def std_library_void(sid):
    access_denied = _standard_library_access_denied(full_required=True)
    if access_denied:
        return access_denied
    denied = _require_action("quality.standard.void")
    if denied:
        return denied
    s = StdLibraryItem.query.filter_by(id=sid, deleted_at=None).first()
    if not s:
        return jsonify({"code": 1, "message": "标准不存在", "data": None}), 200
    body = request.get_json(silent=True) or {}
    void_date = (body.get("voidDate") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not _parse_date(void_date):
        return jsonify({"code": 1, "message": "请输入有效的作废日期", "data": None}), 200
    if not reason:
        return jsonify({"code": 1, "message": "作废标准必须填写原因", "data": None}), 200
    before = s.to_row()
    s.void_date = void_date
    s.replace_no = (body.get("replaceNo") or "").strip()
    s.remark = f"{s.remark + '；' if s.remark else ''}作废原因：{reason}"
    add_operation_audit("quality.standard.void", "controlled_standard", s.id, before=before, after=s.to_row(), message=reason)
    db.session.commit()
    return jsonify({"code": 0, "message": "标准已作废", "data": s.to_row()})


# ========== 设备台账（质量体系，图4） ==========
EQUIPMENT_FIELDS = [
    ("archiveNo", "档案号"),
    ("name", "仪器设备名称"),
    ("spec", "规格型号"),
    ("factoryNo", "出厂编号"),
    ("maker", "生产厂家"),
    ("dept", "所属科室"),
    ("keeper", "仪器设备管理员"),
    ("manualStatus", "人工状态"),
    ("actualCalDate", "本次校准日期"),
    ("planCalDate", "校准有效期至"),
    ("period", "校准周期"),
    ("calUnit", "检定/校准单位"),
    ("certificateNo", "证书编号"),
    ("place", "放置地点"),
    ("range", "量程"),
    ("accuracy", "准确度"),
    ("equipType", "设备类型"),
    ("remark", "备注"),
]
EQUIPMENT_BATCH_FIELDS = {
    "dept", "keeper", "manualStatus", "status", "lastCalDate",
    "actualCalDate", "validUntil", "certificateNo", "planCalDate", "period", "calUnit", "place",
}
EQUIPMENT_CALIBRATION_FIELDS = {
    "actualCalDate", "lastCalDate", "planCalDate", "validUntil", "period", "calUnit", "certificateNo",
}


def _manual_equipment_status(value):
    text = str(value or "").strip()
    if any(token in text for token in ("停用", "报废", "失效", "维修")):
        return "停用/报废"
    return "可用"


def _normalize_equipment_date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"[年月/.]", "-", text).replace("日", "").strip("- ")
    if re.fullmatch(r"\d{8}", compact):
        compact = f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", compact)
    if not match:
        raise ValueError(f"日期“{text}”格式无效，请输入如 2026-03-04")
    try:
        parsed = date(*(int(part) for part in match.groups()))
    except ValueError as exc:
        raise ValueError(f"日期“{text}”不是有效日期") from exc
    return parsed.isoformat()


def _calibration_period_months(value):
    text = str(value or "").strip().lower().replace(" ", "")
    if not text or any(token in text for token in ("长期", "永久", "不定期")):
        return None
    if text == "半年":
        return 6
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return max(1, round(float(text) * 12))
    years = re.search(r"(\d+(?:\.\d+)?)年", text)
    months = re.search(r"(\d+)个?月", text)
    if not years and not months:
        return None
    year_months = round(float(years.group(1)) * 12) if years else 0
    extra_months = int(months.group(1)) if months else 0
    return max(1, year_months + extra_months)


def _add_calibration_period(start_text, period):
    months = _calibration_period_months(period)
    if not start_text or months is None:
        return ""
    start = datetime.strptime(start_text, "%Y-%m-%d").date()
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return (date(year, month, day) - timedelta(days=1)).isoformat()


def _equipment_natural_text_key(value):
    parts = re.split(r"(\d+)", str(value or "").strip().casefold())
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in parts
        if part
    )


def _equipment_stable_pairs(records):
    pairs = records_by_edit_time(records, "equipment", lambda record: record.id)
    return sorted(
        pairs,
        key=lambda pair: (
            str(pair[0].dept or "").strip().casefold(),
            _equipment_natural_text_key(pair[0].archive_no),
            pair[0].id,
        ),
    )


def _equipment_change_record(row, before, source, changed_keys, mode="correction"):
    from ..equipment_calibration import FIELDS, MARKER, maintenance_snapshot
    after = row.to_row(full=True)
    tracked = sorted(key for key in FIELDS if before.get(key, "") != after.get(key, ""))
    if not tracked:
        return
    saved = maintenance_snapshot(row, before, after, mode) if before else []
    db.session.add(EquipmentCalibrationRecord(
        equipment_id=row.id, source=source, changed_fields=tracked,
        before_data={key: before.get(key, "") for key in FIELDS},
        after_data={**{key: after.get(key, "") for key in FIELDS}, MARKER: saved,
                    '_maintenanceMode': mode if before else 'initial'},
        changed_by_account=g.current_user.account,
        changed_by_name=g.current_user.name,
    ))


def _equipment_ledger_access():
    user = g.current_user
    permissions = set(user.permission_codes())
    if can_correct_business_data(user) or user.role_key == "admin" or "quality.equipment_ledger.view" in permissions:
        return "full"
    if "quality.monthly_calibration_plan.view" in permissions:
        return "plan"
    if "quality.equipment_ledger_department.view" in permissions:
        return "department"
    # 检测录入/更改只需要读取本人科室的设备候选，不能因此要求设备台账页面权限。
    if permissions.intersection({"testing.data_entry.view", "testing.data_change.view"}):
        return "department"
    return ""


def _equipment_ledger_access_denied(full_required=False):
    access = _equipment_ledger_access()
    if access and (not full_required or access == "full"):
        return None
    message = (
        "设备台账[科室]仅支持查看本人所在部门设备"
        if full_required and access == "department"
        else "无设备台账查看权限"
    )
    return jsonify({"code": 403, "message": message, "data": None}), 200


def _equipment_query():
    q = EquipmentItem.query.filter(EquipmentItem.deleted_at.is_(None))
    user = g.current_user
    access = _equipment_ledger_access()
    department_scope = request.args.get("scope") == "department"
    requested_department = (request.args.get("dept") or "").strip()
    if access == "department":
        # Department-only users must never escape their own department, even
        # when a caller supplies another report department in the query.
        department = user.department.name if user.department else ""
        q = q.filter(EquipmentItem.dept == department)
    elif department_scope:
        # Full-access users (for example an administrator entering data for a
        # report owned by another department) need the report department, not
        # the user's home department.  Previously both filters were applied and
        # their intersection was empty.
        department = requested_department or (user.department.name if user.department else "")
        if department:
            q = q.filter(EquipmentItem.dept == department)
    kw = (request.args.get("keyword") or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(db.or_(
            EquipmentItem.archive_no.like(like),
            EquipmentItem.name.like(like),
            EquipmentItem.keeper.like(like),
        ))
    if requested_department and (access == "department" or not department_scope):
        q = q.filter(EquipmentItem.dept == requested_department)
    return q


def _equipment_master_page_denied():
    if correcting("equipment"):
        return None
    return _equipment_ledger_access_denied(full_required=True)


def _equipment_visible_query():
    query = EquipmentItem.query.filter(EquipmentItem.deleted_at.is_(None))
    user = g.current_user
    if (
        request.args.get("scope") == "department"
        or _equipment_ledger_access() == "department"
    ):
        department = user.department.name if user.department else ""
        query = query.filter(EquipmentItem.dept == department)
    return query


@bp.get("/equipment")
@require_auth
def equipment_list():
    denied = _equipment_ledger_access_denied()
    if denied:
        return denied
    q = _equipment_query()
    status = (request.args.get("status") or "").strip()
    full = str(request.args.get("full") or "").lower() in ("1", "true", "yes")
    page, size = _page_args()
    if full:
        page, size = 1, 5000
    ordered = _equipment_stable_pairs(q.all())
    if status:
        normalized = "停用/报废" if any(token in status for token in ("停用", "报废")) else status
        ordered = [
            (equipment, edited_at)
            for equipment, edited_at in ordered
            if equipment.effective_status() == normalized
        ]
    total = len(ordered)
    items = ordered[(page - 1) * size:page * size]
    rows = []
    for equipment, edited_at in items:
        row = equipment.to_row(full=full)
        row["editedAt"] = edit_time_text(edited_at)
        rows.append(row)
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": rows,
        "total": total, "page": page, "size": size}})


@bp.get("/equipment/<int:eid>")
@require_auth
def equipment_detail(eid):
    denied = _equipment_ledger_access_denied()
    if denied:
        return denied
    e = _equipment_visible_query().filter(EquipmentItem.id == eid).first()
    if not e:
        return jsonify({"code": 1, "message": "设备不存在", "data": None}), 200
    return jsonify({"code": 0, "message": "ok", "data": e.to_row(full=True)})


def _apply_equipment(e, b):
    values = dict(b)
    if "certificateNo" in values:
        values["certificateNo"] = str(values["certificateNo"] or "").strip()
        if len(values["certificateNo"]) > 160:
            raise ValueError("证书编号不能超过160个字符")
    for key in ("actualCalDate", "lastCalDate", "planCalDate", "validUntil", "buyDate"):
        if key in values:
            values[key] = _normalize_equipment_date(values[key])
    if set(values) & {"actualCalDate", "lastCalDate", "period"}:
        start = values.get("actualCalDate", values.get("lastCalDate", e.actual_cal_date or e.last_cal_date or ''))
        values.update(actualCalDate=start, lastCalDate=start)
    if (set(values) & {"actualCalDate", "lastCalDate", "period"}
            and not set(values) & {"planCalDate", "validUntil"}):
        start = values.get("actualCalDate", e.actual_cal_date or e.last_cal_date)
        period = values.get("period", e.period)
        derived = _add_calibration_period(start, period)
        if derived:
            values["planCalDate"] = derived
    if "planCalDate" in values or "validUntil" in values:
        end = values["planCalDate"] if "planCalDate" in values else values["validUntil"]
        values.update(planCalDate=end, validUntil=end)
    for attr, key in [("archive_no", "archiveNo"), ("name", "name"), ("spec", "spec"),
                      ("factory_no", "factoryNo"), ("maker", "maker"), ("cal_unit", "calUnit"),
                      ("dept", "dept"), ("place", "place"), ("last_cal_date", "lastCalDate"),
                      ("period", "period"), ("plan_cal_date", "planCalDate"), ("actual_cal_date", "actualCalDate"),
                      ("meas_range", "range"), ("accuracy", "accuracy"), ("keeper", "keeper"),
                      ("buy_date", "buyDate"), ("buy_price", "buyPrice"), ("use_record", "useRecord"),
                      ("manual", "manual"), ("cert", "cert"), ("accept_doc", "acceptDoc"),
                      ("certificate_no", "certificateNo"),
                      ("status", "status"), ("equip_type", "equipType"), ("cal_person", "calPerson"),
                      ("valid_until", "validUntil"), ("remark", "remark")]:
        if key in values:
            setattr(e, attr, values[key])
    if "manualStatus" in values:
        e.status = _manual_equipment_status(values["manualStatus"])
    elif "status" in values:
        e.status = _manual_equipment_status(values["status"])
    if "planCalDate" in values:
        e.valid_until = values["planCalDate"]


@bp.post("/equipment")
@require_auth
def equipment_create():
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action("quality.equipment.create", "无设备台账新增权限")
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    if not (body.get("archiveNo") or "").strip() or not (body.get("name") or "").strip():
        return jsonify({"code": 1, "message": "档案号和设备名称为必填项", "data": None}), 200
    row = EquipmentItem()
    try:
        _apply_equipment(row, body)
    except ValueError as exc:
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    db.session.add(row)
    db.session.flush()
    _equipment_change_record(row, {}, "create", body.keys())
    add_operation_audit("quality.equipment.create", "equipment", row.id, after=row.to_row(full=True))
    db.session.commit()
    return jsonify({"code": 0, "message": "设备已新增", "data": row.to_row(full=True)})


@bp.put("/equipment/<int:eid>")
@require_auth
@audited_form("equipment", "eid")
def equipment_update(eid):
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action("quality.equipment.update", "无设备台账修改权限")
    if denied:
        return denied
    e = EquipmentItem.query.filter_by(id=eid, deleted_at=None).with_for_update().first()
    if not e:
        return jsonify({"code": 1, "message": "设备不存在", "data": None}), 200
    before = e.to_row(full=True)
    body = request.get_json(silent=True) or {}
    if require_edit_version(e, body):
        db.session.rollback()
        return jsonify(code=409, message="该仪器刚被其他窗口修改保存过，请刷新核对最新内容后再修改，避免覆盖他人改动。", data=None), 409
    try:
        _apply_equipment(e, body)
    except ValueError as exc:
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    if not (e.archive_no or "").strip() or not (e.name or "").strip():
        return jsonify({"code": 1, "message": "档案号和设备名称为必填项", "data": None}), 200
    try:
        _equipment_change_record(e, before, "single_update", body.keys(), body.get("calibrationMode", "correction"))
    except ValueError as exc:
        db.session.rollback()
        return jsonify(code=1, message=str(exc), data=None), 200
    add_operation_audit("quality.equipment.update", "equipment", e.id, before=before, after=e.to_row(full=True))
    db.session.commit()
    return jsonify({"code": 0, "message": "已保存", "data": e.to_row(full=True)})


@bp.delete("/equipment/<int:eid>")
@require_auth
def equipment_delete(eid):
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action("quality.equipment.delete", "无设备台账移除权限")
    if denied:
        return denied
    row = EquipmentItem.query.filter_by(id=eid, deleted_at=None).first()
    if not row:
        return jsonify({"code": 1, "message": "设备不存在", "data": None}), 200
    before = row.to_row(full=True)
    row.deleted_at = datetime.utcnow()
    row.status = "停用/报废"
    add_operation_audit("quality.equipment.delete", "equipment", row.id, before=before, message="软删除")
    db.session.commit()
    return jsonify({"code": 0, "message": "设备已移除，可由数据库管理员恢复", "data": None})


def _equipment_ids(body):
    raw = body.get("ids") or []
    try:
        ids = sorted({int(value) for value in raw})
    except (TypeError, ValueError):
        return []
    return [value for value in ids if value > 0]


@bp.post("/equipment/batch-update")
@require_auth
def equipment_batch_update():
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action(
        "quality.equipment.batch_update",
        "无设备批量修改权限",
        ("quality.equipment.update",),
    )
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    ids = _equipment_ids(body)
    changes = body.get("changes") or {}
    changes = {key: value for key, value in changes.items() if key in EQUIPMENT_BATCH_FIELDS}
    if not ids or not changes:
        return jsonify({"code": 1, "message": "请选择设备并勾选至少一个批量修改字段", "data": None}), 200
    rows = EquipmentItem.query.filter(
        EquipmentItem.id.in_(ids),
        EquipmentItem.deleted_at.is_(None),
    ).with_for_update().all()
    if len(rows) != len(ids):
        return jsonify({"code": 1, "message": "所选设备中包含不存在或已删除的记录", "data": None}), 200
    for row in rows:
        before = row.to_row(full=True)
        try:
            _apply_equipment(row, changes)
        except ValueError as exc:
            db.session.rollback()
            return jsonify({"code": 1, "message": str(exc), "data": None}), 200
        try:
            _equipment_change_record(row, before, "batch_update", changes.keys(), body.get("calibrationMode", "correction"))
        except ValueError as exc:
            db.session.rollback()
            return jsonify(code=1, message=str(exc), data=None), 200
        add_operation_audit(
            "quality.equipment.batch_update",
            "equipment",
            row.id,
            before=before,
            after=row.to_row(full=True),
        )
    db.session.commit()
    return jsonify({"code": 0, "message": f"已批量修改 {len(rows)} 台设备", "data": {"updated": len(rows)}})


@bp.post("/equipment/batch-delete")
@require_auth
def equipment_batch_delete():
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action(
        "quality.equipment.batch_delete",
        "无设备批量删除权限",
        ("quality.equipment.delete",),
    )
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    ids = _equipment_ids(body)
    if not ids:
        return jsonify({"code": 1, "message": "请选择需要删除的设备", "data": None}), 200
    rows = EquipmentItem.query.filter(
        EquipmentItem.id.in_(ids),
        EquipmentItem.deleted_at.is_(None),
    ).all()
    for row in rows:
        before = row.to_row(full=True)
        row.deleted_at = datetime.utcnow()
        row.status = "停用/报废"
        add_operation_audit(
            "quality.equipment.batch_delete",
            "equipment",
            row.id,
            before=before,
            message="批量软删除",
        )
    db.session.commit()
    return jsonify({"code": 0, "message": f"已批量删除 {len(rows)} 台设备", "data": {"deleted": len(rows)}})


def _equipment_workbook(rows=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "仪器设备台账"
    fields = [("id", "记录ID"), *EQUIPMENT_FIELDS, ("calibrationMode", "校准维护方式")]
    sheet.append([label for _, label in fields])
    if rows:
        for row in rows:
            data = row.to_row(full=True)
            data['actualCalDate'] = row.actual_cal_date or row.last_cal_date or ''
            data['planCalDate'] = row.valid_until or row.plan_cal_date or ''
            sheet.append([data.get(key, "") for key, _ in fields])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(
            35,
            max(12, max(len(str(cell.value or "")) for cell in column) + 2),
        )
    instructions = workbook.create_sheet("导入说明")
    instructions.append(["新增仪器：记录ID留空，系统生成独立ID；允许同档案号中英文仪器共存。"])
    instructions.append(["更新仪器：先导出台账，保留目标仪器的记录ID再修改；不得填写档案号代替ID。"])
    instructions.append(["旧表没有记录ID列时，全部作为新增，不会按档案号覆盖原仪器。"])
    instructions.append(["更新时，未提供的列和普通空白格保持原值；只有填写 / 或 [清空] 才清空该字段。每个记录ID在一份文件中只能出现一次。"])
    instructions.append(["校准维护方式：新增一次校准 / 纠正本期信息；空白按纠正处理，不会保留错误日期用于放行。"])
    instructions.append(["新增校准须核对原有效期，填写本次校准日期、校准有效期至和证书编号，并确认符合使用要求；保留上一期，空档不放行。"])
    instructions.column_dimensions["A"].width = 110
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


@bp.get("/equipment/template")
@require_auth
def equipment_template():
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action(
        "quality.equipment.import",
        "无设备导入权限",
        ("quality.equipment.update",),
    )
    if denied:
        return denied
    return send_file(
        _equipment_workbook(),
        as_attachment=True,
        download_name="equipment-import-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/equipment/export")
@require_auth
def equipment_export():
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action(
        "quality.equipment.export",
        "无设备导出权限",
        ("quality.equipment.update",),
    )
    if denied:
        return denied
    query = _equipment_query()
    raw_ids = request.args.get("ids")
    if raw_ids is not None:
        tokens = raw_ids.split(",")
        if not all(re.fullmatch(r"[1-9][0-9]*", token) for token in tokens):
            return jsonify({"code": 1, "message": "请选择有效的仪器记录ID", "data": None}), 200
        query = query.filter(EquipmentItem.id.in_([int(token) for token in tokens]))
    rows = [equipment for equipment, _edited_at in _equipment_stable_pairs(query.all())]
    status = (request.args.get("status") or "").strip()
    if status:
        normalized = "停用/报废" if any(token in status for token in ("停用", "报废")) else status
        rows = [row for row in rows if row.effective_status() == normalized]
    return send_file(
        _equipment_workbook(rows),
        as_attachment=True,
        download_name=f"equipment-ledger-{date.today().isoformat()}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _cell_text(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


@bp.post("/equipment/import")
@require_auth
def equipment_import():
    scope_denied = _equipment_master_page_denied()
    if scope_denied:
        return scope_denied
    denied = _require_action(
        "quality.equipment.import",
        "无设备导入权限",
        ("quality.equipment.update",),
    )
    if denied:
        return denied
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"code": 1, "message": "请选择 Excel 导入文件", "data": None}), 200
    try:
        workbook = load_workbook(BytesIO(upload.read()), read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
    except Exception:
        return jsonify({"code": 1, "message": "Excel 文件无法读取，请使用系统模板", "data": None}), 200
    if not values:
        return jsonify({"code": 1, "message": "导入文件没有数据", "data": None}), 200
    header_map = {_cell_text(value): index for index, value in enumerate(values[0])}
    missing = [label for key, label in EQUIPMENT_FIELDS[:2] if label not in header_map]
    if missing:
        return jsonify({"code": 1, "message": "导入文件缺少必填列：" + "、".join(missing), "data": None}), 200
    seen_ids = set()
    created = updated = unchanged = 0
    preview = request.form.get('dryRun', '').lower() in ('true', '1') or request.form.get('mode') == 'preview'
    changes = []
    aliases = {'actualCalDate': ('本次校准日期', '实际校准日期', '计划校准日期'),
               'planCalDate': ('校准有效期至', '下次校准日期')}
    for row_number, values_row in enumerate(values[1:], start=2):
        body = {}
        for key, label in EQUIPMENT_FIELDS:
            index = next((header_map[name] for name in aliases.get(key, (label,)) if name in header_map and header_map[name] < len(values_row)
                          and _cell_text(values_row[header_map[name]]) != ''), None)
            if index is not None and index < len(values_row):
                body[key] = _cell_text(values_row[index])
        archive_no = body.get("archiveNo", "")
        name = body.get("name", "")
        id_index = header_map.get("记录ID")
        record_id = _cell_text(values_row[id_index]) if id_index is not None and id_index < len(values_row) else ""
        if not archive_no and not name and not record_id:
            continue
        if not archive_no or not name:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"第 {row_number} 行档案号和设备名称必须同时填写", "data": None}), 200
        if record_id:
            if not re.fullmatch(r"[1-9][0-9]*", record_id):
                db.session.rollback()
                return jsonify({"code": 1, "message": f"第 {row_number} 行记录ID必须为正整数；新增仪器请留空", "data": None}), 200
            equipment_id = int(record_id)
            if equipment_id in seen_ids:
                db.session.rollback()
                return jsonify({"code": 1, "message": f"第 {row_number} 行记录ID重复：{record_id}", "data": None}), 200
            seen_ids.add(equipment_id)
            query = EquipmentItem.query.filter_by(id=equipment_id, deleted_at=None)
            equipment = (query if preview else query.with_for_update()).first()
            if equipment is None:
                db.session.rollback()
                return jsonify({"code": 1, "message": f"第 {row_number} 行记录ID不存在或已删除：{record_id}；请重新导出台账核对", "data": None}), 200
        else:
            equipment = EquipmentItem()
        before = equipment.to_row(full=True) if record_id else {}
        body = {key: '' if value in ('/', '[清空]') else value for key, value in body.items()
                if not record_id or value != ''}
        try:
            for key in ('actualCalDate', 'planCalDate'):
                if key in body:
                    body[key] = _normalize_equipment_date(body[key])
        except ValueError as exc:
            db.session.rollback()
            return jsonify(code=1, message=f"第 {row_number} 行：{exc}", data=None), 200
        if record_id:
            visible = {**before, 'actualCalDate': equipment.actual_cal_date or equipment.last_cal_date or '',
                       'planCalDate': equipment.valid_until or equipment.plan_cal_date or ''}
            body = {key: value for key, value in body.items() if value != (visible.get(key) or '')}
            if not body:
                unchanged += 1
                continue
        # Compare detached values so preview and unchanged imports never flush writes.
        candidate = EquipmentItem(**{column.key: getattr(equipment, column.key)
                                     for column in EquipmentItem.__table__.columns})
        try:
            _apply_equipment(candidate, body)
        except ValueError as exc:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"第 {row_number} 行：{exc}",
                "data": None,
            }), 200
        after = candidate.to_row(full=True)
        delta = {key: {'before': before.get(key) or '', 'after': value or ''}
                 for key, value in after.items() if key not in ('id', 'editVersion', 'status')
                 and (before.get(key) or '') != (value or '')}
        if record_id and not delta:
            unchanged += 1
            continue
        mode_index = header_map.get("校准维护方式")
        mode_text = _cell_text(values_row[mode_index]) if mode_index is not None and mode_index < len(values_row) else ""
        mode = {"": "correction", "纠正本期信息": "correction", "新增一次校准": "renewal"}.get(mode_text, mode_text)
        try:
            from ..equipment_calibration import FIELDS, maintenance_snapshot
            if record_id and set(delta) & FIELDS:
                maintenance_snapshot(equipment, before, after, mode)
        except ValueError as exc:
            db.session.rollback()
            return jsonify(code=1, message=f"第 {row_number} 行：{exc}", data=None), 200
        created += int(not record_id)
        updated += int(bool(record_id))
        changes.append(dict(id=equipment.id, archiveNo=candidate.archive_no, name=candidate.name,
                            fields=delta, clearingFields=[key for key, value in delta.items()
                                                        if value['before'] and not value['after']]))
        if preview:
            continue
        _apply_equipment(equipment, body)
        if not record_id:
            db.session.add(equipment)
        db.session.flush()
        _equipment_change_record(equipment, before, "import", body.keys(), mode)
        add_operation_audit(
            "quality.equipment.import",
            "equipment",
            equipment.id,
            before=before or None,
            after=equipment.to_row(full=True),
        )
    if preview:
        db.session.rollback()
    if not preview:
        db.session.commit()
    return jsonify(code=0, message=f"{'预览' if preview else '导入完成'}：新增 {created} 台，修改 {updated} 台，跳过 {unchanged} 台",
                   data=dict(created=created, updated=updated, createdCount=created, updatedCount=updated,
                             unchangedCount=unchanged, changes=changes))


@bp.get("/equipment/<int:eid>/history")
@require_auth
def equipment_history(eid):
    denied = _equipment_ledger_access_denied()
    if denied:
        return denied
    equipment = _equipment_visible_query().filter(EquipmentItem.id == eid).first()
    if not equipment:
        return jsonify({"code": 1, "message": "设备不存在", "data": None}), 200
    usage_by_report = {
        row.report_no: row.to_row()
        for row in EquipmentUsageRecord.query.filter_by(equipment_id=eid)
        .order_by(EquipmentUsageRecord.used_to.desc(), EquipmentUsageRecord.id.desc()).all()
    }
    # Compatibility backfill for reports saved before the dedicated history table existed.
    for report in Report.query.order_by(Report.id.desc()).all():
        check_input = (report.detail or {}).get("checkInput") or {}
        if eid not in [int(value) for value in (check_input.get("equipmentIds") or []) if str(value).isdigit()]:
            continue
        if report.report_no in usage_by_report:
            continue
        intervals = check_input.get("testIntervals") or []
        usage_by_report[report.report_no] = {
            "id": 0,
            "reportNo": report.report_no,
            "sampleNo": report.sample_no or "",
            "project": report.project or report.project_name or "",
            "usedFrom": min((str(item.get("start") or "") for item in intervals), default=check_input.get("testStartDate") or ""),
            "usedTo": max((str(item.get("end") or "") for item in intervals), default=check_input.get("testDate") or ""),
            "usedByAccount": ((check_input.get("entryStaff") or {}).get("account") or ""),
            "usedByName": ((check_input.get("entryStaff") or {}).get("name") or report.owner or ""),
            "statusAtUse": "历史记录",
            "createdAt": "",
            "updatedAt": "",
        }
    usage = sorted(
        usage_by_report.values(),
        key=lambda item: (item.get("usedTo") or "", item.get("reportNo") or ""),
        reverse=True,
    )
    calibration = [
        row.to_row()
        for row in EquipmentCalibrationRecord.query.filter_by(equipment_id=eid)
        .order_by(EquipmentCalibrationRecord.changed_at.desc(), EquipmentCalibrationRecord.id.desc()).all()
    ]
    from ..equipment_calibration import retained_periods, period
    projects = sorted({item["project"] for item in usage if item.get("project")})
    return jsonify({"code": 0, "message": "ok", "data": {
        "usage": usage,
        "validPeriods": retained_periods(equipment) + ([period(equipment.to_row(full=True))] if period(equipment.to_row(full=True)) else []),
        "calibration": calibration,
        "reports": usage,
        "projects": projects,
    }})


@bp.post("/equipment/<int:eid>/calibration-history")
@require_auth
def equipment_backfill_calibration(eid):
    denied = _equipment_master_page_denied() or _require_action(
        'quality.equipment.update', '无设备台账修改权限')
    if denied:
        return denied
    equipment = EquipmentItem.query.filter_by(id=eid, deleted_at=None).with_for_update().first()
    if not equipment:
        return jsonify(code=1, message='设备不存在', data=None), 200
    from ..equipment_calibration import FIELDS, MARKER, backfill_period, retained_periods
    payload = request.get_json(silent=True)
    try:
        saved = backfill_period(equipment, payload)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(code=1, message=str(exc), data=None), 200
    current = equipment.to_row(full=True)
    before = {**{k: current.get(k, '') for k in FIELDS}, MARKER: retained_periods(equipment)}
    after = {**before, MARKER: saved, '_maintenanceMode': 'historical_backfill',
             'historicalStart': saved[-1]['start'], 'historicalEnd': saved[-1]['end'],
             'historicalCertificateNo': saved[-1]['certificateNo'], 'backfillReason': saved[-1]['reason']}
    db.session.add(EquipmentCalibrationRecord(
        equipment_id=eid, source='historical_backfill',
        changed_fields=['historicalStart', 'historicalEnd', 'historicalCertificateNo', 'backfillReason'],
        before_data=before, after_data=after, changed_by_account=g.current_user.account,
        changed_by_name=g.current_user.name))
    add_operation_audit('quality.equipment.calibration.backfill', 'equipment', eid,
                        before=before, after=after, message=saved[-1]['reason'])
    db.session.commit()
    return jsonify(code=0, message='历史校准已补录，当前校准信息未改变', data={'validPeriods': saved})
