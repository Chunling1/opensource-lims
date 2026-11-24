"""Resolve combinations against live grants/ledger; never write report selections."""
import json
from datetime import date

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Department, EquipmentItem, EquipmentScheme, Project, Report
from ..security import require_auth
from ..organization_privileges import has_full_platform_authority
from ..equipment_authorization import usable_department_names
from ..equipment_eligibility import evaluate_intervals
from ..authorization_scope import project_for_report
from ..audit import add_operation_audit

bp = Blueprint("equipment_schemes", __name__, url_prefix="/api/equipment-schemes")


def result(data=None, code=0, message="ok"):
    return jsonify(code=code, message=message, data=data)


def can_manage(user, department):
    return has_full_platform_authority(user) or (
        user.department_id == department.id and bool(set(user.permission_codes()) & {
            "quality.equipment_ledger.view", "quality.equipment_ledger_department.view",
        }))


def context():
    user = g.current_user
    number = request.args.get("reportNo")
    report = project = None
    if number:
        from .reports import _scope_filter
        report = _scope_filter(Report.query, user).filter_by(report_no=number).first()
        if not report or not (has_full_platform_authority(user) or set(user.permission_codes()) & {
            "testing.data_entry.view", "testing.data_change.view",
        }):
            return None
        project = project_for_report(report)
        department = project.department if project else Department.query.filter_by(name=report.department).first()
    else:
        department = db.session.get(Department, request.args.get("departmentId", type=int) or user.department_id)
    if not department:
        return None
    # Department schemes never grant cross-department visibility of their own.
    if user.department_id != department.id and not has_full_platform_authority(user):
        return None
    if not number and not can_manage(user, department):
        return None
    return department, report, project


def equipment_row(row):
    value = row.to_row(full=True)
    for key in ("buyDate", "buyPrice", "useRecord", "manual", "acceptDoc"):
        value.pop(key, None)
    return value


@bp.get("")
@require_auth
def catalogue():
    ctx = context()
    if not ctx:
        return result(code=403, message="无当前部门仪器方案权限")
    department, report, project = ctx
    user = g.current_user
    manage = can_manage(user, department)
    rows = EquipmentScheme.query.filter_by(department_id=department.id).order_by(EquipmentScheme.name, EquipmentScheme.id).all()
    departments = usable_department_names(user)
    equipment = EquipmentItem.query.filter(EquipmentItem.deleted_at.is_(None))
    if departments is not None:
        equipment = equipment.filter(EquipmentItem.dept.in_(departments))
    return result(dict(departmentId=department.id, department=department.name, canManage=manage,
        departments=[dict(id=d.id, name=d.name) for d in (Department.query.order_by(Department.name).all()
                     if has_full_platform_authority(user) else [department])],
        projectId=project.id if project else None,
        schemes=[dict(row.to_row(), recommended=bool(project and project.id in (row.project_ids or [])))
                 for row in rows if row.enabled or manage],
        projects=[dict(id=p.id, name=p.name, code=p.display_code or p.number_code or p.code)
                  for p in Project.query.filter_by(department_id=department.id, active=True).order_by(Project.name).all()],
        equipment=[equipment_row(row) for row in equipment.order_by(EquipmentItem.archive_no, EquipmentItem.id).all()] if manage else []))


def positive_ids(value, label):
    if not isinstance(value, list) or len(value) > 1000 or any(type(v) is not int or v <= 0 for v in value):
        raise ValueError(label + "格式无效")
    return list(dict.fromkeys(value))


@bp.post("")
@bp.put("/<int:scheme_id>")
@require_auth
def save(scheme_id=None):
    body = request.get_json(silent=True) or {}
    scheme = db.session.get(EquipmentScheme, scheme_id) if scheme_id else None
    if scheme_id and not scheme:
        return result(code=404, message="仪器方案不存在")
    department_id = scheme.department_id if scheme else body.get("departmentId")
    if type(department_id) is not int:
        return result(code=1, message="请选择所属部门")
    department = db.session.get(Department, department_id)
    if not department or not can_manage(g.current_user, department):
        return result(code=403, message="只能维护有权限的部门仪器方案")
    try:
        name = str(body.get("name") or "").strip()
        if not name or len(name) > 100:
            raise ValueError("方案名称必填且不超过100字")
        ids = positive_ids(body.get("equipmentIds"), "仪器列表")
        project_ids = positive_ids(body.get("projectIds", []), "关联检测项目")
        if not ids:
            raise ValueError("方案至少保留一台仪器")
        if type(body.get("enabled", True)) is not bool:
            raise ValueError("启用状态无效")
        projects = Project.query.filter(Project.id.in_(project_ids), Project.department_id == department.id, Project.active.is_(True)).all()
        if len(projects) != len(project_ids):
            raise ValueError("只能关联本部门现行检测项目")
        # Preserve removed/unavailable existing references until a maintainer explicitly replaces them.
        new_ids = set(ids) - set(scheme.equipment_ids if scheme else [])
        equipment = EquipmentItem.query.filter(EquipmentItem.id.in_(new_ids), EquipmentItem.deleted_at.is_(None)).all()
        allowed = usable_department_names(g.current_user)
        if len(equipment) != len(new_ids) or any(allowed is not None and row.dept not in allowed for row in equipment):
            raise ValueError("新增仪器不存在或不在当前授权范围内")
    except (TypeError, ValueError) as exc:
        return result(code=1, message=str(exc))
    before = scheme.to_row() if scheme else None
    values = dict(name=name, equipment_ids=ids, project_ids=project_ids, enabled=body.get("enabled", True))
    if scheme:
        version = body.get("version")
        if type(version) is not int or version != scheme.version:
            return result(code=409, message="方案已被修改，请刷新后重新编辑")
        try:
            updated = EquipmentScheme.query.filter_by(id=scheme.id, version=version).update(dict(values, version=version + 1), synchronize_session=False)
        except IntegrityError:
            db.session.rollback()
            return result(code=1, message="本部门已有同名仪器方案，请使用其他名称")
        if updated != 1:
            db.session.rollback()
            return result(code=409, message="方案已被修改，请刷新后重新编辑")
        db.session.expire(scheme)
    else:
        scheme = EquipmentScheme(department_id=department.id, version=1, **values)
        db.session.add(scheme)
    try:
        db.session.flush()
        after = scheme.to_row()
        add_operation_audit("equipment.scheme.save", "equipment_scheme", str(scheme.id),
                            category="quality", before=before, after=after)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return result(code=1, message="本部门已有同名仪器方案，请使用其他名称")
    return result(after)


@bp.get("/<int:scheme_id>/resolve")
@require_auth
def resolve(scheme_id):
    ctx = context()
    if not ctx or not ctx[1]:
        return result(code=403, message="无当前报告仪器方案权限")
    department, report, project = ctx
    scheme = EquipmentScheme.query.filter_by(id=scheme_id, department_id=department.id, enabled=True).first()
    if not scheme:
        return result(code=404, message="方案已停用或不存在，请刷新")
    try:
        intervals = json.loads(request.args.get("intervals", "[]"))
        if not isinstance(intervals, list) or not intervals or len(intervals) > 100 or any(not isinstance(v, dict) for v in intervals):
            raise ValueError()
        for interval in intervals:
            start, end = interval.get("start"), interval.get("end")
            if not isinstance(start, str) or not isinstance(end, str) or len(start) != 10 or len(end) != 10 or date.fromisoformat(start) > date.fromisoformat(end):
                raise ValueError()
    except (ValueError, TypeError):
        return result(code=1, message="请先填写完整试验日期，再套用仪器方案")
    allowed = usable_department_names(g.current_user)
    records = {r.id: r for r in EquipmentItem.query.filter(EquipmentItem.id.in_(scheme.equipment_ids)).all()}
    eligible, skipped = [], []
    for eid in scheme.equipment_ids:
        row = records.get(eid)
        reason = "仪器不存在或已删除" if not row or row.deleted_at else ""
        visible = row is not None and (allowed is None or row.dept in allowed)
        if row and not visible:
            reason = "仪器所属部门未授权使用"
        verdict = evaluate_intervals(row, intervals) if row and not reason else None
        if verdict and not verdict["selectable"]:
            reason = verdict["message"]
        if reason:
            skipped.append(dict(id=str(eid), code=row.archive_no if visible else str(eid),
                                name=row.name if visible else "不可用仪器", reason=reason))
        else:
            eligible.append(dict(equipment_row(row), eligibility=verdict))
    return result(dict(schemeId=scheme.id, version=scheme.version, rows=eligible, skipped=skipped))
