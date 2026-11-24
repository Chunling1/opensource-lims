"""Electronic original-record API used by the independent ELN PWA.

The API deliberately re-authorizes against the inspection-system tables on
every operation.  An ELN session is only an identity assertion; it never
contains durable department/project permissions.
"""
from __future__ import annotations

import hashlib
import io
import json
import secrets
from datetime import UTC, datetime, timedelta
from functools import wraps
from uuid import uuid4

import jwt
from flask import Blueprint, current_app, g, jsonify, request, send_file

from ..applications.report_lifecycle import persist_report_attachment, scoped_report_query
from ..platform.audit import add_operation_audit, latest_operation_audit
from ..platform.identity import (
    project_for_report,
    project_step_error,
    user_has_org_wide_scope,
)
from ..extensions import db
from ..platform.file_vault import persist_bytes, read_file_bytes
from ..models import (
    ElnLaunchCode,
    ElnOriginalRecord,
    ElnProjectConfig,
    ElnRecordRevision,
    ElnRecordTemplate,
    ElnTaskPolicy,
    Project,
    Report,
    ReportAttachment,
    User,
)
from ..security import require_auth, credential_version, credential_matches, authenticated_version
from ..request_validation import json_fields
from ..platform.identity import authenticate_internal_user
from ..platform.identity.login_security import captcha_required

bp = Blueprint("eln", __name__, url_prefix="/api/eln")

EDITABLE_STATUSES = {"检测录入中", "检测更改中", "退回待重传"}
ACTIVE_RECORD_STATUSES = {"DRAFT", "PENDING_REVIEW", "REVIEWING", "REVIEW_REJECTED"}
REVIEW_PERMISSION = "testing.original_record_review.view"
QUERY_PERMISSION = "testing.original_record_query.view"
TEMPLATE_PERMISSION = "testing.original_record_template.view"


def _response(data=None, message="ok", code=0, status=200):
    return jsonify({"code": code, "message": message, "data": data}), status


def _utcnow():
    # Existing tables use naive UTC DateTime for SQLite/DM8 portability.
    return datetime.utcnow()


def _enabled():
    return bool(current_app.config.get("ELN_ENABLED"))


def _require_enabled():
    if not _enabled():
        return _response(None, "电子原始记录功能尚未启用", 503, 503)
    return None


def _issue_session(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "iss": "lims-inspection",
        "aud": "lims-eln",
        "sub": str(user.id),
        "account": user.account,
        "cv": authenticated_version(user),
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["ELN_SESSION_EXPIRES_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["ELN_SESSION_SECRET"], algorithm="HS256")


def _eln_user_payload(user: User) -> dict:
    permissions = set(user.permission_codes())
    return {
        "id": user.id,
        "account": user.account,
        "name": user.name,
        "department": user.department.name if user.department else "",
        "roleName": user.role_name,
        "capabilities": {
            "dataEntry": "testing.data_entry.view" in permissions,
            "query": QUERY_PERMISSION in permissions,
            "review": REVIEW_PERMISSION in permissions,
            "template": TEMPLATE_PERMISSION in permissions and user_has_org_wide_scope(user),
        },
    }


def _can_open_workspace(user: User) -> bool:
    return any(_eln_user_payload(user)["capabilities"].values())


def _set_session_cookie(response, user: User):
    response.set_cookie(
        current_app.config["ELN_SESSION_COOKIE_NAME"],
        _issue_session(user),
        max_age=current_app.config["ELN_SESSION_EXPIRES_SECONDS"],
        secure=bool(current_app.config.get("PROD")),
        httponly=True,
        samesite="Strict",
        path=current_app.config["ELN_SESSION_COOKIE_PATH"],
    )
    return response


def _require_eln_session(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        disabled = _require_enabled()
        if disabled:
            return disabled
        authorization = str(request.headers.get("Authorization") or "")
        token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        token = token or str(request.cookies.get(current_app.config["ELN_SESSION_COOKIE_NAME"]) or "")
        if not token:
            return _response(None, "缺少ELN访问令牌", 401, 401)
        try:
            payload = jwt.decode(
                token,
                current_app.config["ELN_SESSION_SECRET"],
                algorithms=["HS256"],
                issuer="lims-inspection",
                audience="lims-eln",
            )
        except jwt.ExpiredSignatureError:
            return _response(None, "ELN会话已过期，请从检测系统重新进入", 401, 401)
        except jwt.InvalidTokenError:
            return _response(None, "ELN访问令牌无效", 401, 401)
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal() or len(subject) > 19:
            return _response(None, "ELN访问令牌无效", 401, 401)
        user = db.session.get(User, int(subject))
        if not user or not user.enabled or user.must_change_password or user.account != payload.get("account") or not credential_matches(user, payload.get("cv")):
            return _response(None, "账号不存在、已禁用或会话身份已变化", 401, 401)
        # Never trust relationship collections loaded by an earlier request in
        # a long-lived worker. Permission and project-step revocation must take
        # effect before this request performs any business query.
        db.session.expire(user, ["permissions", "project_steps", "department"])
        g.current_user = user
        g.eln_session = payload
        return view(*args, **kwargs)

    return wrapped


def _scoped_report(user: User, report_no: str):
    return scoped_report_query(Report.query, user).filter(
        Report.report_no == report_no,
        Report.voided.is_(False),
    ).first()


def _person_code(value):
    if isinstance(value, dict):
        return str(value.get("code") or value.get("account") or "").strip().lower()
    return str(value or "").strip().lower()


def _primary_accounts(report: Report) -> set[str]:
    detail = report.detail or {}
    check_input = detail.get("checkInput") or {}
    people = check_input.get("people") or {}
    assigned = detail.get("assigned") or {}
    values = {
        _person_code(people.get("primaryTester1")),
        _person_code(people.get("primaryTester2")),
        _person_code(assigned.get("primaryTester1")),
        _person_code(assigned.get("primaryTester2")),
    }
    values.discard("")
    return values


def _entry_error(user: User, report: Report) -> str:
    if "testing.data_entry.view" not in user.permission_codes():
        return "当前账号没有检测数据录入功能权限"
    if report.status not in EDITABLE_STATUSES:
        return f"报告当前为「{report.status}」，不在检测数据录入节点"
    project = project_for_report(report)
    if project is None:
        return "报告尚未关联稳定的检测项目，不能创建电子原始记录"
    grant_error = project_step_error(user, report, "data_entry", "数据录入")
    if grant_error:
        return grant_error
    accounts = _primary_accounts(report)
    if not accounts:
        return "请先在检测数据录入表单选择主检1或主检2并保存草稿"
    if user.account.lower() not in accounts:
        return "只有主系统已保存的主检1或主检2可以录入本任务原始记录"
    return ""


def _review_error(user: User, report: Report, creator_id: int) -> str:
    if user.id == creator_id:
        return "原始记录录入人与审核人不能是同一账号"
    if REVIEW_PERMISSION not in user.permission_codes():
        return "当前账号没有电子原始记录审核功能权限"
    if report.status not in EDITABLE_STATUSES:
        return f"报告当前为「{report.status}」，不能审核原始记录"
    return project_step_error(user, report, "record_review", "原始记录审核")


def _task_context(report: Report) -> dict:
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    project = project_for_report(report)
    payload = {
        "reportNo": report.report_no,
        "sampleNo": report.sample_no or "",
        "entrustNo": report.entrust_no or "",
        "status": report.status or "",
        "sampleStatus": report.sample_status or "",
        "client": report.client or "",
        "department": report.department or "",
        "project": {
            "id": project.id if project else None,
            "code": (
                project.display_code or project.number_code or project.code
                if project else ""
            ),
            "name": project.name if project else (report.project or report.project_name or ""),
        },
        "sample": {
            "name": str(raw.get("sampleName") or raw.get("name") or ""),
            "spec": str(raw.get("spec") or raw.get("model") or ""),
            "batchNo": str(raw.get("batchNo") or raw.get("factoryNo") or ""),
        },
        "standards": raw.get("testBases") or raw.get("testBasis") or [],
        "capabilityEntryIds": raw.get("capabilityEntryIds") or [],
        "manualCapabilityItems": raw.get("manualCapabilityItems") or [],
        "primaryAccounts": sorted(_primary_accounts(report)),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["revision"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def _config_for(report: Report):
    project = project_for_report(report)
    if project is None:
        return None, None
    return project, ElnProjectConfig.query.filter_by(project_id=project.id).first()


def _template_availability(report: Report):
    """Describe ELN readiness without hiding an otherwise authorized task."""
    project, config = _config_for(report)
    if project is None:
        message = "报告尚未关联稳定的检测项目，不能创建电子原始记录"
        return project, config, [], {
            "ready": False,
            "code": "PROJECT_UNRESOLVED",
            "label": "项目未关联",
            "message": message,
        }
    templates = ElnRecordTemplate.query.filter_by(
        project_id=project.id,
        status="PUBLISHED",
    ).order_by(ElnRecordTemplate.name, ElnRecordTemplate.version).all()
    if not templates:
        message = "该检测项目尚未创建并发布电子原始记录模板，请联系模板管理员创建后再录入"
        return project, config, templates, {
            "ready": False,
            "code": "TEMPLATE_MISSING",
            "label": "未创建模板",
            "message": message,
        }
    if config is None or not config.enabled:
        message = "该检测项目尚未启用电子原始记录，请联系模板管理员启用后再录入"
        return project, config, templates, {
            "ready": False,
            "code": "PROJECT_DISABLED",
            "label": "项目未启用",
            "message": message,
        }
    return project, config, templates, {
        "ready": True,
        "code": "READY",
        "label": "可以录入",
        "message": "",
    }


def _data_entry_started_at(report: Report):
    rows = [
        latest_operation_audit("report", report.report_no, "sample.out_warehouse.sign"),
        latest_operation_audit("report", report.report_no, "report.data_entry.save"),
    ]
    dates = [row.created_at for row in rows if row and row.created_at]
    return min(dates) if dates else None


def _ensure_policy(report: Report, *, persist=False):
    policy = ElnTaskPolicy.query.filter_by(report_no=report.report_no).first()
    if policy:
        return policy
    project, config = _config_for(report)
    if project is None or config is None or not config.enabled:
        return None
    started = _data_entry_started_at(report)
    required = bool(
        config.apply_to_existing
        or (started is not None and started >= config.effective_at)
    )
    policy = ElnTaskPolicy(
        report_no=report.report_no,
        project_id=project.id,
        required=required,
        config_version=config.config_version,
        required_templates=config.required_templates or [],
        min_finalized_records=max(1, int(config.min_finalized_records or 1)),
    )
    db.session.add(policy)
    if persist:
        db.session.commit()
    else:
        db.session.flush()
    return policy


def _latest_revision(record: ElnOriginalRecord):
    return ElnRecordRevision.query.filter_by(
        record_id=record.id, revision_no=record.current_revision_no
    ).first()


def _record_payload(record: ElnOriginalRecord, *, include_values=False):
    revision = _latest_revision(record)
    template = db.session.get(ElnRecordTemplate, record.template_id)
    creator = db.session.get(User, record.creator_id)
    reviewer = db.session.get(User, record.reviewer_id) if record.reviewer_id else None
    data = {
        "id": record.external_id,
        "reportNo": record.report_no,
        "projectId": record.project_id,
        "status": record.status,
        "revisionNo": record.current_revision_no,
        "taskRevision": record.task_revision,
        "template": {
            "id": template.id if template else None,
            "code": template.code if template else "",
            "name": template.name if template else "",
            "version": template.version if template else "",
            "configHash": template.config_hash if template else "",
        },
        "creator": {"id": record.creator_id, "account": creator.account if creator else "", "name": creator.name if creator else ""},
        "reviewer": ({"id": reviewer.id, "account": reviewer.account, "name": reviewer.name} if reviewer else None),
        "reviewComment": revision.review_comment if revision else "",
        "pdfAttachmentId": record.pdf_attachment_id,
        "createdAt": record.created_at.isoformat(timespec="seconds") if record.created_at else "",
        "updatedAt": record.updated_at.isoformat(timespec="seconds") if record.updated_at else "",
        "finalizedAt": record.finalized_at.isoformat(timespec="seconds") if record.finalized_at else "",
    }
    if include_values and revision:
        data["fieldValues"] = revision.field_values or {}
        data["resultSummary"] = revision.result_summary or {}
        data["contentHash"] = revision.content_hash
    return data


def _reviewer_payloads(report: Report, creator_id=None):
    project = project_for_report(report)
    if project is None:
        return []
    rows = []
    for user in User.query.filter(User.enabled.is_(True)).order_by(User.name, User.account).all():
        if creator_id and user.id == creator_id:
            continue
        if _scoped_report(user, report.report_no) is None:
            continue
        if _review_error(user, report, creator_id or -1):
            continue
        rows.append({"id": user.id, "account": user.account, "name": user.name, "department": user.department.name if user.department else ""})
    return rows


def _content_hash(field_values, result_summary):
    canonical = json.dumps(
        {"fieldValues": field_values or {}, "resultSummary": result_summary or {}},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validated_record_values(template: ElnRecordTemplate, body: dict):
    field_values = body.get("fieldValues") if isinstance(body.get("fieldValues"), dict) else {}
    result_summary = body.get("resultSummary") if isinstance(body.get("resultSummary"), dict) else {}
    fields = field_values.get("fields") if isinstance(field_values.get("fields"), dict) else {}
    rows = field_values.get("rows") if isinstance(field_values.get("rows"), list) else []
    if len(rows) > 500:
        return None, None, "原始数据行不能超过 500 行"
    required = []
    for item in template.field_schema or []:
        if not isinstance(item, dict) or not item.get("required"):
            continue
        key = str(item.get("key") or "").strip()
        if key and not str(fields.get(key) if fields.get(key) is not None else "").strip():
            required.append(str(item.get("label") or key))
    if required:
        return None, None, "原始记录必填项未填写：" + "、".join(required)
    canonical = json.dumps(
        {"fieldValues": field_values, "resultSummary": result_summary},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(canonical.encode("utf-8")) > 512 * 1024:
        return None, None, "单份原始记录结构化数据不能超过 512KB"
    return field_values, result_summary, ""


def _render_record_pdf(record, revision, report, template):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.pdfmetrics import registerFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("服务器未安装 reportlab，无法生成电子原始记录PDF") from exc

    registerFont(UnicodeCIDFont("STSong-Light"))
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, title=f"电子原始记录-{report.report_no}")
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("eln-normal", parent=styles["BodyText"], fontName="STSong-Light", fontSize=9, leading=14)
    title = ParagraphStyle("eln-title", parent=normal, fontSize=16, leading=24, alignment=TA_CENTER)
    story = [Paragraph("电子原始记录", title), Spacer(1, 10)]
    metadata = [
        ["报告编号", report.report_no], ["样品编号", report.sample_no or ""],
        ["检测项目", report.project or report.project_name or ""],
        ["模板", f"{template.name} {template.version}"],
        ["记录修订", str(revision.revision_no)], ["数据校验", revision.content_hash],
    ]
    table = Table([[Paragraph(str(a), normal), Paragraph(str(b), normal)] for a, b in metadata], colWidths=[85, 390])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .5, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f6fa"))]))
    story.extend([table, Spacer(1, 12), Paragraph("原始记录数据", normal)])
    rows = [["字段", "值"]]
    for key, value in (revision.field_values or {}).items():
        rows.append([str(key), json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")])
    for key, value in (revision.result_summary or {}).items():
        rows.append([str(key), json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")])
    values = Table([[Paragraph(str(a), normal), Paragraph(str(b), normal)] for a, b in rows], colWidths=[140, 335], repeatRows=1)
    values.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .5, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f0ff")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(values)
    document.build(story)
    return buffer.getvalue()


def eln_completion_error(report: Report) -> str:
    """Return a user-facing blocker without advancing any business state."""
    if not _enabled():
        return ""
    policy = _ensure_policy(report)
    if policy is None or not policy.required:
        return ""
    records = ElnOriginalRecord.query.filter_by(
        report_no=report.report_no, status="FINALIZED", task_revision=_task_context(report)["revision"]
    ).all()
    required_codes = {str(value).strip() for value in (policy.required_templates or []) if str(value).strip()}
    found_codes = {
        template.code
        for template in (db.session.get(ElnRecordTemplate, row.template_id) for row in records)
        if template
    }
    missing = sorted(required_codes - found_codes)
    if missing:
        return "电子原始记录尚未完成必需模板审核：" + "、".join(missing)
    if len(records) < int(policy.min_finalized_records or 1):
        return f"电子原始记录需至少 {policy.min_finalized_records} 份审核通过，当前为 {len(records)} 份"
    return ""


@bp.post("/launch")
@require_auth
@json_fields("reportNo")
def launch():
    disabled = _require_enabled()
    if disabled:
        return disabled
    report_no = str((request.get_json(silent=True) or {}).get("reportNo") or "").strip()
    if not report_no:
        permissions = set(g.current_user.permission_codes())
        if not permissions.intersection({QUERY_PERMISSION, REVIEW_PERMISSION, TEMPLATE_PERMISSION}):
            return _response(None, "当前账号没有电子原始记录工作台权限", 403, 403)
        raw_code = secrets.token_urlsafe(32) + "." + credential_version(g.current_user)
        row = ElnLaunchCode(
            code_hash=hashlib.sha256(raw_code.encode("utf-8")).hexdigest(),
            user_id=g.current_user.id,
            report_no="",
            expires_at=_utcnow() + timedelta(seconds=current_app.config["ELN_LAUNCH_EXPIRES_SECONDS"]),
        )
        db.session.add(row)
        add_operation_audit("eln.workspace.launch", "user", g.current_user.id, category="integration")
        db.session.commit()
        base = current_app.config["ELN_BASE_URL"]
        return _response({"url": f"{base}?code={raw_code}", "expiresIn": current_app.config["ELN_LAUNCH_EXPIRES_SECONDS"]})
    report = _scoped_report(g.current_user, report_no)
    if report is None:
        return _response(None, "报告不存在或不在当前账号数据范围内", 404, 404)
    error = _entry_error(g.current_user, report)
    if error:
        return _response(None, error, 403, 403)
    project, config = _config_for(report)
    if config is None or not config.enabled:
        return _response(None, "该检测项目尚未启用电子原始记录", 409, 409)
    _ensure_policy(report)
    raw_code = secrets.token_urlsafe(32) + "." + credential_version(g.current_user)
    row = ElnLaunchCode(
        code_hash=hashlib.sha256(raw_code.encode("utf-8")).hexdigest(),
        user_id=g.current_user.id,
        report_no=report.report_no,
        expires_at=_utcnow() + timedelta(seconds=current_app.config["ELN_LAUNCH_EXPIRES_SECONDS"]),
    )
    db.session.add(row)
    add_operation_audit("eln.launch", "report", report.report_no, category="integration", after={"projectId": project.id if project else None})
    db.session.commit()
    base = current_app.config["ELN_BASE_URL"]
    return _response({"url": f"{base}?code={raw_code}", "expiresIn": current_app.config["ELN_LAUNCH_EXPIRES_SECONDS"]})


@bp.post("/session/login")
@json_fields("account", "password", "captchaId", "captcha")
@captcha_required
def direct_login():
    """Use the inspection-system account and password without a second user DB."""
    disabled = _require_enabled()
    if disabled:
        return disabled
    body = request.get_json(silent=True) or {}
    user, code, message = authenticate_internal_user(
        body.get("account"), body.get("password")
    )
    if code:
        status = 423 if code == 2 else 403 if code == 3 else 401
        return _response(None, message, code, status)
    if user is None:
        current_app.logger.error("ELN authentication succeeded without a user")
        return _response(None, "登录状态异常，请稍后重试", 1, 500)
    db.session.expire(user, ["permissions", "project_steps", "department"])
    if not _can_open_workspace(user):
        return _response(None, "当前账号未开通电子原始记录权限", 403, 403)
    add_operation_audit(
        "eln.session.login",
        "user",
        str(user.id),
        category="security",
        after={"account": user.account, "method": "inspection_credentials"},
        actor=user,
    )
    db.session.commit()
    response, status = _response({"user": _eln_user_payload(user), "reportNo": ""})
    return _set_session_cookie(response, user), status


@bp.post("/session/exchange")
@json_fields("code")
def exchange_session():
    disabled = _require_enabled()
    if disabled:
        return disabled
    code = str((request.get_json(silent=True) or {}).get("code") or "").strip()
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest() if code else ""
    row = ElnLaunchCode.query.filter_by(code_hash=digest).first()
    if row is None or row.used_at is not None or row.expires_at < _utcnow():
        return _response(None, "单点登录码无效或已过期，请从检测系统重新进入", 401, 401)
    user = db.session.get(User, row.user_id)
    if not user or not user.enabled or user.must_change_password:
        return _response(None, "账号已禁用，请重新登录检测系统", 403, 403)
    version = code.rsplit(".", 1)[-1] if "." in code else None
    if not credential_matches(user, version):
        return _response(None, "登录凭据已更新，请重新进入", 401, 401)
    user._authenticated_credential_version = version
    report = _scoped_report(user, row.report_no) if row.report_no else None
    if row.report_no and (report is None or _entry_error(user, report)):
        return _response(None, "任务权限已变化，请从检测系统重新进入", 403, 403)
    row.used_at = _utcnow()
    db.session.commit()
    response, status = _response({"user": _eln_user_payload(user), "reportNo": report.report_no if report else ""})
    return _set_session_cookie(response, user), status


@bp.get("/session")
@_require_eln_session
def current_session():
    user = g.current_user
    return _response({"user": _eln_user_payload(user)})


@bp.post("/session/logout")
def end_session():
    response, status = _response(None, "ELN会话已退出")
    response.delete_cookie(
        current_app.config["ELN_SESSION_COOKIE_NAME"],
        path=current_app.config["ELN_SESSION_COOKIE_PATH"],
        secure=bool(current_app.config.get("PROD")),
        httponly=True,
        samesite="Strict",
    )
    return response, status


@bp.get("/tasks")
@_require_eln_session
def tasks():
    rows = []
    reports = scoped_report_query(Report.query, g.current_user).filter(
        Report.status.in_(EDITABLE_STATUSES), Report.voided.is_(False)
    ).order_by(Report.report_no.desc()).all()
    for report in reports:
        if _entry_error(g.current_user, report):
            continue
        _project, _config, _templates, availability = _template_availability(report)
        records = ElnOriginalRecord.query.filter_by(report_no=report.report_no).all()
        rows.append({
            **_task_context(report),
            "availability": availability,
            "records": [_record_payload(item) for item in records],
        })
    return _response({"rows": rows, "total": len(rows)})


@bp.get("/tasks/<report_no>")
@_require_eln_session
def task_detail(report_no):
    report = _scoped_report(g.current_user, report_no)
    if report is None:
        return _response(None, "任务不存在或不在当前账号数据范围内", 404, 404)
    entry_error = _entry_error(g.current_user, report)
    can_review = not _review_error(g.current_user, report, -1)
    if entry_error and not can_review and QUERY_PERMISSION not in g.current_user.permission_codes():
        return _response(None, "当前账号无权访问该任务", 403, 403)
    project, config, templates, availability = _template_availability(report)
    if project is None:
        return _response(None, availability["message"], 409, 409)
    records = ElnOriginalRecord.query.filter_by(report_no=report.report_no).order_by(ElnOriginalRecord.created_at.desc()).all()
    visible = [row for row in records if row.creator_id == g.current_user.id or row.reviewer_id == g.current_user.id or QUERY_PERMISSION in g.current_user.permission_codes()]
    policy = _ensure_policy(report) if availability["ready"] else None
    return _response({
        "task": _task_context(report),
        "canCreate": not bool(entry_error) and availability["ready"],
        "entryBlocker": entry_error or availability["message"],
        "availability": availability,
        "policy": {
            "required": bool(policy and policy.required),
            "requiredTemplates": config.required_templates or [] if config else [],
            "minFinalizedRecords": config.min_finalized_records if config else 1,
        },
        "templates": [{"id": item.id, "code": item.code, "name": item.name, "version": item.version, "fieldSchema": item.field_schema or []} for item in templates],
        "reviewers": _reviewer_payloads(report, g.current_user.id),
        "records": [_record_payload(item, include_values=True) for item in visible],
    })


@bp.post("/tasks/<report_no>/records")
@_require_eln_session
def create_record(report_no):
    report = _scoped_report(g.current_user, report_no)
    if report is None:
        return _response(None, "任务不存在或不在当前账号数据范围内", 404, 404)
    error = _entry_error(g.current_user, report)
    if error:
        return _response(None, error, 403, 403)
    project, config, templates, availability = _template_availability(report)
    if not availability["ready"]:
        return _response(None, availability["message"], 409, 409)
    body = request.get_json(silent=True) or {}
    template = db.session.get(ElnRecordTemplate, body.get("templateId"))
    if not template or template not in templates:
        return _response(None, "请选择该项目已发布的原始记录模板", 409, 409)
    conflict = ElnOriginalRecord.query.filter(
        ElnOriginalRecord.report_no == report.report_no,
        ElnOriginalRecord.status.in_(ACTIVE_RECORD_STATUSES),
        ElnOriginalRecord.creator_id != g.current_user.id,
    ).first()
    if conflict:
        return _response(None, "该任务已有其他主检的活动录入会话，请先撤销或完成", 409, 409)
    context = _task_context(report)
    field_values, result_summary, validation_error = _validated_record_values(template, body)
    if validation_error:
        return _response(None, validation_error, 400, 400)
    record = ElnOriginalRecord(
        external_id=f"ELN-{uuid4().hex.upper()}", report_no=report.report_no,
        project_id=project.id, template_id=template.id, creator_id=g.current_user.id,
        task_revision=context["revision"], status="DRAFT",
    )
    db.session.add(record)
    db.session.flush()
    revision = ElnRecordRevision(
        record_id=record.id, revision_no=1, status="DRAFT",
        field_values=field_values, result_summary=result_summary,
        content_hash=_content_hash(field_values, result_summary), created_by_id=g.current_user.id,
    )
    db.session.add(revision)
    add_operation_audit("eln.record.create", "eln_record", record.external_id, category="eln", after={"reportNo": report.report_no, "templateId": template.id})
    db.session.commit()
    return _response(_record_payload(record, include_values=True), "原始记录草稿已创建", 0, 201)


@bp.put("/records/<external_id>")
@_require_eln_session
def update_record(external_id):
    record = ElnOriginalRecord.query.filter_by(external_id=external_id).first()
    if record is None:
        return _response(None, "原始记录不存在", 404, 404)
    report = _scoped_report(g.current_user, record.report_no)
    if report is None or record.creator_id != g.current_user.id:
        return _response(None, "只有创建人可以修改该原始记录", 403, 403)
    error = _entry_error(g.current_user, report)
    if error:
        return _response(None, error, 403, 403)
    if record.status not in {"DRAFT", "REVIEW_REJECTED"}:
        return _response(None, "当前记录状态不可修改", 409, 409)
    context = _task_context(report)
    if record.task_revision != context["revision"]:
        return _response(None, "检测任务信息已变化，请创建更正修订", 409, 409)
    body = request.get_json(silent=True) or {}
    template = db.session.get(ElnRecordTemplate, record.template_id)
    if template is None:
        return _response(None, "原始记录模板已不存在", 409, 409)
    field_values, result_summary, validation_error = _validated_record_values(template, body)
    if validation_error:
        return _response(None, validation_error, 400, 400)
    revision = _latest_revision(record)
    if record.status == "REVIEW_REJECTED":
        record.current_revision_no += 1
        revision = ElnRecordRevision(record_id=record.id, revision_no=record.current_revision_no, status="DRAFT", created_by_id=g.current_user.id)
        db.session.add(revision)
    revision.field_values = field_values
    revision.result_summary = result_summary
    revision.content_hash = _content_hash(field_values, result_summary)
    revision.status = "DRAFT"
    record.status = "DRAFT"
    record.reviewer_id = None
    add_operation_audit("eln.record.save", "eln_record", record.external_id, category="eln", after={"revisionNo": record.current_revision_no, "contentHash": revision.content_hash})
    db.session.commit()
    return _response(_record_payload(record, include_values=True), "原始记录草稿已保存")


@bp.post("/records/<external_id>/submit")
@_require_eln_session
def submit_record(external_id):
    record = ElnOriginalRecord.query.filter_by(external_id=external_id).first()
    if record is None:
        return _response(None, "原始记录不存在", 404, 404)
    report = _scoped_report(g.current_user, record.report_no)
    if report is None or record.creator_id != g.current_user.id:
        return _response(None, "只有创建人可以提交该原始记录", 403, 403)
    error = _entry_error(g.current_user, report)
    if error:
        return _response(None, error, 403, 403)
    if record.status != "DRAFT":
        return _response(None, "只有草稿可以提交审核", 409, 409)
    if record.task_revision != _task_context(report)["revision"]:
        return _response(None, "检测任务信息已变化，请刷新后创建更正修订", 409, 409)
    body = request.get_json(silent=True) or {}
    reviewer = db.session.get(User, body.get("reviewerId"))
    if reviewer is None or not reviewer.enabled:
        return _response(None, "请选择有效的原始记录审核人", 400, 400)
    reviewer_report = _scoped_report(reviewer, report.report_no)
    error = "审核人无该报告数据权限" if reviewer_report is None else _review_error(reviewer, report, record.creator_id)
    if error:
        return _response(None, error, 403, 403)
    revision = _latest_revision(record)
    record.reviewer_id = reviewer.id
    record.status = "PENDING_REVIEW"
    revision.status = "PENDING_REVIEW"
    revision.submitted_at = _utcnow()
    add_operation_audit("eln.record.submit", "eln_record", record.external_id, category="eln", after={"reviewerId": reviewer.id, "revisionNo": revision.revision_no})
    db.session.commit()
    return _response(_record_payload(record, include_values=True), "原始记录已提交交叉审核")


@bp.get("/reviews")
@_require_eln_session
def review_queue():
    rows = []
    records = ElnOriginalRecord.query.filter_by(reviewer_id=g.current_user.id).filter(ElnOriginalRecord.status.in_({"PENDING_REVIEW", "REVIEWING"})).order_by(ElnOriginalRecord.updated_at).all()
    for record in records:
        report = _scoped_report(g.current_user, record.report_no)
        if report is None or _review_error(g.current_user, report, record.creator_id):
            continue
        rows.append(_record_payload(record, include_values=True))
    return _response({"rows": rows, "total": len(rows)})


@bp.post("/records/<external_id>/review")
@_require_eln_session
def review_record(external_id):
    record = ElnOriginalRecord.query.filter_by(external_id=external_id).first()
    if record is None:
        return _response(None, "原始记录不存在", 404, 404)
    report = _scoped_report(g.current_user, record.report_no)
    if report is None or record.reviewer_id != g.current_user.id:
        return _response(None, "该原始记录未分派给当前审核人", 403, 403)
    error = _review_error(g.current_user, report, record.creator_id)
    if error:
        return _response(None, error, 403, 403)
    if record.status not in {"PENDING_REVIEW", "REVIEWING"}:
        return _response(None, "当前记录不在待审核状态", 409, 409)
    if record.task_revision != _task_context(report)["revision"]:
        return _response(None, "检测任务信息已变化，不能审核旧任务版本", 409, 409)
    body = request.get_json(silent=True) or {}
    decision = str(body.get("decision") or "").strip().lower()
    comment = str(body.get("comment") or "").strip()[:500]
    revision = _latest_revision(record)
    revision.reviewed_by_id = g.current_user.id
    revision.reviewed_at = _utcnow()
    revision.review_comment = comment
    if decision == "reject":
        if not comment:
            return _response(None, "退回原始记录必须填写原因", 400, 400)
        record.status = "REVIEW_REJECTED"
        revision.status = "REVIEW_REJECTED"
        add_operation_audit("eln.record.reject", "eln_record", record.external_id, category="eln", after={"revisionNo": revision.revision_no, "comment": comment})
        db.session.commit()
        return _response(_record_payload(record, include_values=True), "原始记录已退回录入人")
    if decision != "approve":
        return _response(None, "审核决定必须为 approve 或 reject", 400, 400)
    template = db.session.get(ElnRecordTemplate, record.template_id)
    try:
        raw_pdf = _render_record_pdf(record, revision, report, template)
        name = f"电子原始记录-{report.report_no}-{record.external_id[-8:]}.pdf"
        attachment = persist_report_attachment(
            report,
            raw_pdf,
            category="report_attachment",
            name=name,
            content_type="application/pdf",
            kind="PDF",
            source="电子原始记录",
            status="审核定稿",
            uploaded_by=f"ELN · {g.current_user.name or g.current_user.account}",
            created_by=f"ELN/{g.current_user.account}",
            max_bytes=current_app.config.get("MAX_FILE_BYTES"),
        )
        stored_file = attachment.stored_file
        record.pdf_attachment_id = attachment.id
        record.status = "FINALIZED"
        record.finalized_at = _utcnow()
        revision.status = "FINALIZED"
        add_operation_audit("eln.record.approve", "eln_record", record.external_id, category="eln", after={"reportNo": report.report_no, "revisionNo": revision.revision_no, "attachmentId": attachment.id, "sha256": stored_file.sha256})
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("ELN record PDF finalization failed")
        return _response(None, str(exc), 500, 500)
    return _response(_record_payload(record, include_values=True), "原始记录审核通过并已回传检测系统")


@bp.get("/records/<external_id>/pdf")
@_require_eln_session
def record_pdf(external_id):
    record = ElnOriginalRecord.query.filter_by(external_id=external_id, status="FINALIZED").first()
    if record is None or not record.pdf_attachment_id:
        return _response(None, "正式原始记录PDF不存在", 404, 404)
    report = _scoped_report(g.current_user, record.report_no)
    can_view = record.creator_id == g.current_user.id or record.reviewer_id == g.current_user.id or QUERY_PERMISSION in g.current_user.permission_codes()
    if report is None or not can_view:
        return _response(None, "无权查看该原始记录", 403, 403)
    attachment = db.session.get(ReportAttachment, record.pdf_attachment_id)
    if attachment is None or attachment.deleted_at is not None:
        return _response(None, "正式原始记录PDF已不存在", 404, 404)
    payload = read_file_bytes(attachment.stored_file, attachment.data)
    response = send_file(io.BytesIO(payload), mimetype="application/pdf", as_attachment=False, download_name=attachment.name)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.get("/reports/<report_no>/status")
@require_auth
def report_eln_status(report_no):
    report = _scoped_report(g.current_user, report_no)
    if report is None:
        return _response(None, "报告不存在或不在当前账号数据范围内", 404, 404)
    project, config = _config_for(report)
    policy = _ensure_policy(report) if config and config.enabled else None
    records = ElnOriginalRecord.query.filter_by(report_no=report.report_no).order_by(ElnOriginalRecord.created_at.desc()).all()
    return _response({
        "enabled": bool(_enabled() and config and config.enabled),
        "projectId": project.id if project else None,
        "required": bool(policy and policy.required),
        "blocker": eln_completion_error(report),
        "records": [_record_payload(item) for item in records],
        "canLaunch": not bool(_entry_error(g.current_user, report)) if config and config.enabled else False,
    })


@bp.get("/reports/<report_no>/draft")
@require_auth
def report_eln_draft(report_no):
    report = _scoped_report(g.current_user, report_no)
    if report is None:
        return _response(None, "报告不存在或不在当前账号数据范围内", 404, 404)
    error = _entry_error(g.current_user, report)
    if error:
        return _response(None, error, 403, 403)
    record = ElnOriginalRecord.query.filter_by(report_no=report.report_no, status="FINALIZED").order_by(ElnOriginalRecord.finalized_at.desc()).first()
    if record is None:
        return _response({"recordId": None, "patches": []})
    revision = _latest_revision(record)
    summary = revision.result_summary or {}
    allowed = {"recordNo", "result", "conclusion", "resultStatus", "unqualifiedParams", "remark"}
    patches = [{"path": key, "value": summary[key], "source": record.external_id, "revisionNo": revision.revision_no} for key in allowed if key in summary]
    return _response({"recordId": record.external_id, "contentHash": revision.content_hash, "patches": patches})


def _template_admin_error(user: User):
    if TEMPLATE_PERMISSION not in user.permission_codes():
        return "当前账号没有电子原始记录模板管理权限"
    if not user_has_org_wide_scope(user):
        return "电子原始记录项目配置仅允许根机构授权管理员维护"
    return ""


@bp.get("/admin/projects")
@_require_eln_session
def admin_projects():
    error = _template_admin_error(g.current_user)
    if error:
        return _response(None, error, 403, 403)
    rows = []
    configs = {row.project_id: row for row in ElnProjectConfig.query.all()}
    for project in Project.query.order_by(Project.name, Project.id).all():
        config = configs.get(project.id)
        rows.append({"id": project.id, "code": project.display_code or project.number_code or project.code, "name": project.name, "department": project.department.name if project.department else "", "eln": {"enabled": bool(config and config.enabled), "effectiveAt": config.effective_at.isoformat(timespec="seconds") if config else "", "requiredTemplates": config.required_templates or [] if config else [], "minFinalizedRecords": config.min_finalized_records if config else 1, "configVersion": config.config_version if config else 0}})
    return _response({"rows": rows})


@bp.put("/admin/projects/<int:project_id>/config")
@_require_eln_session
def save_project_config(project_id):
    error = _template_admin_error(g.current_user)
    if error:
        return _response(None, error, 403, 403)
    project = db.session.get(Project, project_id)
    if project is None:
        return _response(None, "检测项目不存在", 404, 404)
    body = request.get_json(silent=True) or {}
    required_templates = list(dict.fromkeys(
        str(value).strip() for value in body.get("requiredTemplates") or [] if str(value).strip()
    ))
    if required_templates:
        published_codes = {
            row.code for row in ElnRecordTemplate.query.filter(
                ElnRecordTemplate.project_id == project.id,
                ElnRecordTemplate.status == "PUBLISHED",
                ElnRecordTemplate.code.in_(required_templates),
            ).all()
        }
        missing_templates = [value for value in required_templates if value not in published_codes]
        if missing_templates:
            return _response(None, "必需模板尚未在该项目发布：" + "、".join(missing_templates), 409, 409)
    minimum = max(1, min(20, int(body.get("minFinalizedRecords") or 1)))
    config = ElnProjectConfig.query.filter_by(project_id=project.id).first()
    before = {"enabled": bool(config.enabled), "configVersion": config.config_version} if config else None
    if config is None:
        config = ElnProjectConfig(project_id=project.id, effective_at=_utcnow())
        db.session.add(config)
    config.enabled = bool(body.get("enabled"))
    config.apply_to_existing = False
    config.required_templates = required_templates
    config.min_finalized_records = minimum
    config.config_version = int(config.config_version or 0) + 1
    config.updated_by_id = g.current_user.id
    if config.enabled and (not before or not before["enabled"]):
        config.effective_at = _utcnow()
    add_operation_audit("eln.project_config.update", "project", project.id, category="eln", before=before, after={"enabled": config.enabled, "configVersion": config.config_version, "requiredTemplates": required_templates, "minFinalizedRecords": minimum})
    db.session.commit()
    return _response({"projectId": project.id, "enabled": config.enabled, "configVersion": config.config_version})


@bp.get("/admin/templates")
@_require_eln_session
def admin_templates():
    error = _template_admin_error(g.current_user)
    if error:
        return _response(None, error, 403, 403)
    project_id = request.args.get("projectId", type=int)
    query = ElnRecordTemplate.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    rows = query.order_by(ElnRecordTemplate.project_id, ElnRecordTemplate.code, ElnRecordTemplate.version).all()
    return _response({"rows": [{"id": row.id, "projectId": row.project_id, "code": row.code, "name": row.name, "version": row.version, "status": row.status, "fieldSchema": row.field_schema or [], "configHash": row.config_hash} for row in rows]})


@bp.post("/admin/templates")
@_require_eln_session
def create_template():
    error = _template_admin_error(g.current_user)
    if error:
        return _response(None, error, 403, 403)
    body = request.get_json(silent=True) or {}
    project = db.session.get(Project, body.get("projectId"))
    code = str(body.get("code") or "").strip()[:80]
    name = str(body.get("name") or "").strip()[:160]
    version = str(body.get("version") or "").strip()[:40]
    schema = body.get("fieldSchema") if isinstance(body.get("fieldSchema"), list) else []
    if project is None or not code or not name or not version:
        return _response(None, "项目、模板代码、名称和版本均为必填", 400, 400)
    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    row = ElnRecordTemplate(project_id=project.id, code=code, name=name, version=version, status="DRAFT", field_schema=schema, config_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(), created_by_id=g.current_user.id)
    db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _response(None, "同一项目的模板代码和版本不能重复", 409, 409)
    return _response({"id": row.id, "configHash": row.config_hash}, "模板草稿已创建", 0, 201)


@bp.post("/admin/templates/<int:template_id>/publish")
@_require_eln_session
def publish_template(template_id):
    error = _template_admin_error(g.current_user)
    if error:
        return _response(None, error, 403, 403)
    row = db.session.get(ElnRecordTemplate, template_id)
    if row is None:
        return _response(None, "模板不存在", 404, 404)
    row.status = "PUBLISHED"
    row.published_at = row.published_at or _utcnow()
    add_operation_audit("eln.template.publish", "eln_template", row.id, category="eln", after={"projectId": row.project_id, "code": row.code, "version": row.version, "configHash": row.config_hash})
    db.session.commit()
    return _response({"id": row.id, "status": row.status}, "模板已发布")


__all__ = ["bp", "eln_completion_error"]
