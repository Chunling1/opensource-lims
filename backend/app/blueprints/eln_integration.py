"""Protocol boundary for the standalone electronic laboratory notebook (ELN).

The ELN owns its users, templates, data entry and PDF generation.  This
blueprint only exposes the current user's assigned data-entry tasks and accepts
the completed original-record PDF back into the report attachment store.
"""
from __future__ import annotations
from app.organization_privileges import has_full_platform_authority

import hashlib
import hmac
import json
import re
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func

from ..applications.report_lifecycle import scoped_report_query
from ..applications.testing_records import submit_original_record
from ..platform.identity import project_step_error
from ..models import CapabilityEntry, Report, User

bp = Blueprint("eln_integration", __name__, url_prefix="/api/integrations/eln/v1")

EDITABLE_STATUSES = {"检测录入中", "检测更改中", "退回待重传"}


def _response(data=None, message="ok", code=0, status=200):
    return jsonify({"code": code, "message": message, "data": data}), status


def _require_service(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_app.config.get("ELN_LEGACY_INTEGRATION_ENABLED"):
            return _response(None, "旧版外接 ELN 协议已停用", 410, 410)
        expected = str(current_app.config.get("ELN_SHARED_SECRET") or "").strip()
        if not expected:
            return _response(None, "ELN 接口尚未配置共享密钥", 503, 503)
        authorization = str(request.headers.get("Authorization") or "")
        supplied = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        supplied = supplied or str(request.headers.get("X-ELN-Token") or "").strip()
        if not supplied or not hmac.compare_digest(supplied, expected):
            return _response(None, "ELN 服务认证失败", 401, 401)
        return view(*args, **kwargs)

    return wrapped


def _integration_user():
    identity = str(request.headers.get("X-ELN-User") or request.args.get("username") or "").strip()
    if not identity:
        return None, "缺少同名用户标识 X-ELN-User"
    lowered = identity.lower()
    user = User.query.filter(func.lower(User.account) == lowered, User.enabled.is_(True)).first()
    if user:
        return user, ""
    matches = User.query.filter(User.name == identity, User.enabled.is_(True)).all()
    if len(matches) == 1:
        return matches[0], ""
    if len(matches) > 1:
        return None, "检测系统存在重名人员，请使用双方一致的账号而不是姓名"
    return None, f"检测系统不存在启用中的同名账号：{identity}"


def _has_data_entry_permission(user):
    return bool(
        has_full_platform_authority(user)
        or "testing.data_entry.view" in user.permission_codes()
    )


def _report_assigned_to(user, report):
    if has_full_platform_authority(user):
        return True
    detail = report.detail or {}
    check_input = detail.get("checkInput") or {}
    people = check_input.get("people") or {}
    assigned = detail.get("assigned") or {}
    values = {str(report.owner or "").strip()}
    for value in (
        check_input.get("entryStaff"),
        people.get("primaryTester1"),
        people.get("primaryTester2"),
        assigned.get("primaryTester1"),
        assigned.get("primaryTester2"),
    ):
        if isinstance(value, dict):
            values.update(str(value.get(key) or "").strip() for key in ("account", "code", "name"))
        elif value:
            values.add(str(value).strip())
    values.discard("")
    return user.account in values or user.name in values


def _summary_value(detail, section, *keys):
    for row in detail.get("summary") or []:
        if row.get("title") != section:
            continue
        fields = dict(row.get("fields") or [])
        for key in keys:
            if str(fields.get(key) or "").strip():
                return str(fields[key]).strip()
    return ""


def _split_items(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[、,，;；\n]+", str(value or "")) if part.strip()]


def _task_payload(report, user):
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    capability_ids = []
    for value in raw.get("capabilityEntryIds") or []:
        try:
            capability_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    capability_rows = []
    if capability_ids:
        by_id = {
            row.id: row
            for row in CapabilityEntry.query.filter(CapabilityEntry.id.in_(capability_ids)).all()
        }
        capability_rows = [by_id[value].to_row() for value in capability_ids if value in by_id]
    items = [
        {
            "id": f"capability:{row['id']}",
            "name": row.get("itemName") or "",
            "objectName": row.get("objectName") or "",
            "standardCode": row.get("standardCode") or "",
            "methodClause": row.get("methodClause") or "",
            "unit": "",
            "requirement": row.get("restriction") or row.get("methodClause") or "",
            "source": "capability",
        }
        for row in capability_rows
    ]
    for name in _split_items(raw.get("manualCapabilityItems")):
        items.append({
            "id": f"manual:{len(items) + 1}",
            "name": name,
            "objectName": str(raw.get("sampleName") or ""),
            "standardCode": "",
            "methodClause": "",
            "unit": "",
            "requirement": str(raw.get("manualCapabilityReason") or "库外项目"),
            "source": "manual",
        })
    if not items:
        fallback = _split_items(raw.get("projectList") or raw.get("project") or report.project)
        items = [
            {
                "id": f"project:{index}",
                "name": name,
                "objectName": str(raw.get("sampleName") or ""),
                "standardCode": "",
                "methodClause": "",
                "unit": "",
                "requirement": "按检测依据及检测方案执行",
                "source": "sample",
            }
            for index, name in enumerate(fallback, start=1)
        ]
    standards = _split_items(raw.get("testBases") or raw.get("testBasis"))
    template_code = str(
        raw.get("originalRecordTemplateCode")
        or raw.get("elnTemplateCode")
        or raw.get("schemeCode")
        or "generic"
    ).strip()
    sample_name = str(
        raw.get("sampleName")
        or raw.get("name")
        or _summary_value(detail, "送样信息", "样品名称", "样品/工程名称")
        or report.project_name
        or report.project
        or ""
    ).strip()
    payload = {
        "id": report.report_no,
        "reportNo": report.report_no,
        "sampleNo": report.sample_no or "",
        "entrustNo": report.entrust_no or "",
        "status": report.status,
        "client": report.client or "",
        "department": report.department or "",
        "owner": report.owner or "",
        "operator": {"account": user.account, "name": user.name},
        "sample": {
            "name": sample_name,
            "code": report.sample_no or "",
            "spec": str(raw.get("spec") or raw.get("model") or ""),
            "batch": str(raw.get("batchNo") or raw.get("factoryNo") or ""),
            "objectName": items[0].get("objectName") if items else "",
        },
        "project": {
            "name": report.project or report.project_name or "",
            "projectName": report.project_name or "",
            "schemeCode": str(raw.get("schemeCode") or ""),
            "schemeName": str(raw.get("schemeName") or ""),
            "standards": standards,
            "items": items,
        },
        "originalRecordTemplate": {
            "code": template_code,
            "version": str(raw.get("originalRecordTemplateVersion") or "V1.0"),
        },
        "existingOriginalRecord": (detail.get("elnIntegration") or {}).get("latest") or None,
    }
    revision_source = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["revision"] = hashlib.sha256(revision_source.encode("utf-8")).hexdigest()
    return payload


def _available_reports(user):
    if not _has_data_entry_permission(user):
        return []
    rows = scoped_report_query(Report.query, user).filter(
        Report.status.in_(EDITABLE_STATUSES),
        Report.voided.is_(False),
    ).order_by(Report.report_no.desc()).all()
    return [
        report for report in rows
        if _report_assigned_to(user, report)
        and not project_step_error(user, report, "data_entry", "数据录入")
    ]


@bp.get("/health")
@_require_service
def health():
    return _response({"status": "up", "protocol": "lims-eln/v1"})


@bp.get("/tasks")
@_require_service
def tasks():
    user, error = _integration_user()
    if error:
        return _response(None, error, 404, 404)
    if not _has_data_entry_permission(user):
        return _response(None, "同名账号没有检测数据录入权限", 403, 403)
    rows = [_task_payload(report, user) for report in _available_reports(user)]
    return _response({
        "system": {"id": "OPEN-LIMS", "name": "LIMS 实验室信息管理系统"},
        "user": {"account": user.account, "name": user.name},
        "rows": rows,
        "total": len(rows),
    })


@bp.get("/tasks/<report_no>")
@_require_service
def task_detail(report_no):
    user, error = _integration_user()
    if error:
        return _response(None, error, 404, 404)
    report = next((row for row in _available_reports(user) if row.report_no == report_no), None)
    if report is None:
        return _response(None, "任务不存在、已离开数据录入节点或不属于该同名用户", 404, 404)
    return _response(_task_payload(report, user))


@bp.post("/tasks/<report_no>/original-record")
@_require_service
def receive_original_record(report_no):
    user, error = _integration_user()
    if error:
        return _response(None, error, 404, 404)
    report = next((row for row in _available_reports(user) if row.report_no == report_no), None)
    if report is None:
        return _response(None, "任务已离开数据录入节点，拒绝接收原始记录", 409, 409)
    uploaded = request.files.get("file")
    if uploaded is None:
        return _response(None, "缺少原始记录 PDF 文件", 400, 400)
    raw_pdf = uploaded.read()
    max_bytes = int(current_app.config.get("MAX_FILE_BYTES", 30 * 1024 * 1024))
    if not raw_pdf.startswith(b"%PDF-"):
        return _response(None, "回传文件不是有效的 PDF", 400, 400)
    if len(raw_pdf) > max_bytes:
        return _response(None, "原始记录 PDF 超过允许大小", 413, 413)
    record_id = str(request.form.get("recordId") or "").strip()[:100]
    task_revision = str(request.form.get("taskRevision") or "").strip()[:64]
    idempotency_key = str(request.headers.get("Idempotency-Key") or record_id or "").strip()[:160]
    result = submit_original_record(
        user,
        report_no,
        raw_pdf=raw_pdf,
        original_name=uploaded.filename or "",
        record_id=record_id,
        task_revision=task_revision,
        idempotency_key=idempotency_key,
        max_bytes=max_bytes,
    )
    return _response(result.data, result.message, result.code, result.http_status)
