"""报告附件接口 — 文件写入私有目录、数据库只存元数据路径，按权限预览/下载（规格 2.5）。

上传需 report.attachment.upload；预览需 report.pdf.preview；下载需 report.pdf.download。
均受数据授权范围约束（仅本范围内报告）。
"""
import base64
import binascii
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, current_app, g, jsonify, make_response, request

from ..applications.report_lifecycle import (
    get_authorized_report_for_view,
    get_visible_report,
    report_content_editable,
    report_data_entry_step_error,
)
from ..covers import is_system_cover_attachment
from ..extensions import db
from ..platform.audit import add_operation_audit
from ..platform.file_vault import (
    mark_stored_file_deleted,
    persist_bytes,
    persist_stream,
    read_file_bytes,
    safe_content_type,
    safe_file_name,
)
from ..models import Report, ReportAttachment
from ..report_documents import (
    attachment_meta,
    attachment_role,
    build_complete_report_pdf,
    composition_options,
)
from ..security import require_auth
from ..storage import StorageLimitExceeded

bp = Blueprint("attachments", __name__, url_prefix="/api")


def _report_in_scope(user, report_no):
    return get_visible_report(user, report_no)


def _report_for_read(user, report_no):
    """Authorize an artifact read through the exact page that opened it."""

    view = str(request.args.get("view") or "").strip()
    report, _projection, error = get_authorized_report_for_view(
        user, report_no, view
    )
    return report, error


def _read_error(message):
    code = 1 if message in {"报告详情入口无效", "报告不存在或不在数据范围内"} else 403
    return jsonify({"code": code, "message": message, "data": None}), 200


@bp.get("/reports/<report_no>/attachments")
@require_auth
def list_attachments(report_no):
    user = g.current_user
    _report, error = _report_for_read(user, report_no)
    if error:
        return _read_error(error)
    rows = ReportAttachment.query.filter_by(report_no=report_no, deleted_at=None).order_by(ReportAttachment.id).all()
    included = composition_options(_report)["includedOtherAttachmentIds"]
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": [attachment_meta(r, included) for r in rows if not is_system_cover_attachment(r)],
    }})


@bp.post("/reports/<report_no>/attachments")
@require_auth
def upload_attachment(report_no):
    # Large files use multipart; keep the legacy JSON/base64 route bounded.
    request.max_content_length = (502 if request.mimetype == 'multipart/form-data' else 102) * 1024 * 1024
    user = g.current_user
    if "report.attachment.upload" not in user.action_codes():
        return jsonify({"code": 403, "message": "无上传权限", "data": None}), 200
    report = _report_in_scope(user, report_no)
    if not report:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    report = Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    step_error = report_data_entry_step_error(user, report)
    if step_error:
        return jsonify({"code": 403, "message": step_error, "data": None}), 200
    if not report_content_editable(report):
        return jsonify({
            "code": 1,
            "message": f"报告当前为「{report.status}」，附件已锁定；请退回检测数据更改环节后修改",
            "data": None,
        }), 200
    uploaded = request.files.get("file")
    body = request.get_json(silent=True) or {}
    attachment_category = (
        request.form.get("category") if uploaded else body.get("category")
    ) or "other"
    source_labels = {
        "completed_report": "完整报告正文",
        "report_page": "报告后续页",
        "raw_record": "原始记录",
        "other": "其他附件",
    }
    if attachment_category not in source_labels:
        return jsonify({"code": 1, "message": "附件分类无效", "data": None}), 200
    name = ((uploaded.filename if uploaded else body.get("name")) or "").strip()
    if not name:
        return jsonify({"code": 1, "message": "缺少文件名", "data": None}), 200
    max_bytes = 500 * 1024 * 1024
    try:
        name = safe_file_name(name, max_length=200)
        lower_name = name.lower()
        if attachment_category in {"completed_report", "report_page", "raw_record"} and not lower_name.endswith((".pdf", ".doc", ".docx")):
            return jsonify({"code": 1, "message": "完整报告、报告后续页和原始记录仅支持 Word 或 PDF", "data": None}), 200
        content_type = safe_content_type(
            uploaded.mimetype if uploaded else body.get("contentType"),
            max_length=120,
        )
        from .. import docparser_field_only
        strict_completed_template = (
            attachment_category in {"completed_report", "report_page"}
            and docparser_field_only.applies_to(report)
        )
        if uploaded:
            if strict_completed_template:
                raw = uploaded.stream.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise StorageLimitExceeded()
                preserve = composition_options(report).get('preserveUploadedReport') is True
                docparser_field_only.validate_completed_template_source(raw, name, report_no,
                    allow_guide_pages=not preserve, preserve_uploaded=preserve)
                stored_file = persist_bytes(
                    raw, category="report_attachment", original_name=name,
                    content_type=content_type, created_by=user.name, max_bytes=max_bytes,
                )
            else:
                stored_file = persist_stream(
                    uploaded.stream,
                    category="report_attachment",
                    original_name=name,
                    content_type=content_type,
                    created_by=user.name,
                    max_bytes=max_bytes,
                )
        else:
            b64 = body.get("dataBase64") or ""
            if not b64:
                return jsonify({"code": 1, "message": "缺少文件内容", "data": None}), 200
            raw = base64.b64decode(b64.split(",")[-1], validate=True)
            if strict_completed_template:
                preserve = composition_options(report).get('preserveUploadedReport') is True
                docparser_field_only.validate_completed_template_source(raw, name, report_no,
                    allow_guide_pages=not preserve, preserve_uploaded=preserve)
            stored_file = persist_bytes(
                raw,
                category="report_attachment",
                original_name=name,
                content_type=content_type,
                created_by=user.name,
                max_bytes=max_bytes,
            )
    except binascii.Error:
        return jsonify({"code": 1, "message": "文件内容编码无效", "data": None}), 200
    except StorageLimitExceeded:
        return jsonify({"code": 1, "message": "单个文件不能超过 500MB", "data": None}), 200
    except ValueError as exc:
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    if lower_name.endswith(".pdf"):
        kind = "PDF"
    elif content_type.lower().startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        kind = "图片"
    else:
        kind = "Word"
    try:
        att = ReportAttachment(
            report_no=report_no,
            name=name,
            content_type=content_type,
            kind=kind,
            source=source_labels[attachment_category],
            status="已上传",
            stored_file=stored_file,
            data=None,
            uploaded_by=user.name,
        )
        db.session.add(att)
        db.session.flush()
        superseded = []
        if strict_completed_template:
            detail = dict(report.detail or {})
            composition = dict(detail.get('reportComposition') or {})
            if composition.get('noSupplementBody') is True:
                composition['noSupplementBody'] = False
                detail['reportComposition'] = composition
                report.detail = detail
        if attachment_category == "completed_report":
            for previous in ReportAttachment.query.filter_by(
                report_no=report_no, deleted_at=None,
            ).filter(ReportAttachment.id != att.id).order_by(ReportAttachment.id).all():
                if attachment_role(previous) in {"completed_report", "report_page"} and previous.status != "已替代":
                    previous.status = "已替代"
                    superseded.append(previous.id)
        add_operation_audit(
            "report.attachment.upload", "report", report_no,
            category="report", after={**attachment_meta(att), "supersededIds": superseded},
            message=f"上传附件：{name}",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("attachment metadata commit failed")
        return jsonify({"code": 1, "message": "附件保存失败", "data": None}), 500
    from ..preview_cache import schedule_after_save
    if attachment_category != 'raw_record':
        schedule_after_save(report)
    return jsonify({"code": 0, "message": "ok", "data": attachment_meta(att)})


@bp.route('/reports/<report_no>/complete-preview-state', methods=['GET', 'POST'])
@require_auth
def complete_preview_state(report_no):
    user = g.current_user
    if 'report.pdf.preview' not in user.action_codes():
        return jsonify({'code': 403, 'message': '无报告预览权限', 'data': None}), 200
    report, error = _report_for_read(user, report_no)
    if error:
        return _read_error(error)
    from ..preview_cache import prepare, status
    try:
        value = (prepare(report, retry=(request.get_json(silent=True) or {}).get('retry') is True)
                 if request.method == 'POST' else status(report))
        return jsonify({'code': 0, 'message': 'ok', 'data': value})
    except Exception:
        current_app.logger.exception('preview state read failed')
        return jsonify({'code': 1, 'message': '预览状态读取失败，请重试', 'data': None}), 200


@bp.get("/reports/<report_no>/complete-preview")
@require_auth
def complete_report_preview(report_no):
    """Authorized cache read only; generation is never performed in this GET."""
    user = g.current_user
    if "report.pdf.preview" not in user.action_codes():
        return jsonify({"code": 403, "message": "无报告预览权限", "data": None}), 200
    report, error = _report_for_read(user, report_no)
    if error:
        return _read_error(error)
    try:
        from ..preview_cache import cached_pdf
        pdf, preview = cached_pdf(report)
    except Exception as exc:
        current_app.logger.exception("complete report preview failed")
        return jsonify({"code": 1, "message": f"完整报告生成失败：{exc}", "data": None}), 200
    if pdf is None:
        return jsonify({
            "code": 1,
            "message": preview.get('message') or '当前版本预览尚未就绪',
            "data": preview,
        }), 200
    download = request.args.get("download") == "1"
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    disposition = "attachment" if download else "inline"
    response.headers["Content-Disposition"] = (
        f"{disposition}; filename*=UTF-8''{quote(report_no + '-完整报告.pdf')}"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers['Cache-Control'] = 'private, no-store'
    if not download and report_content_editable(report):
        from ..report_preview_confirmation import receipt
        response.headers['X-Report-Preview-Receipt'] = receipt(report, user, preview)
    return response


@bp.post('/reports/<report_no>/complete-preview-confirm')
@require_auth
def confirm_complete_report_preview(report_no):
    user = g.current_user
    if 'report.pdf.preview' not in user.action_codes():
        return jsonify(code=403, message='无报告预览权限', data=None), 200
    report = _report_in_scope(user, report_no)
    if report is None:
        return jsonify(code=403, message='报告不存在或无权限', data=None), 200
    report = Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    error = report_data_entry_step_error(user, report)
    if error or report.voided or not report_content_editable(report):
        return jsonify(code=1, message=error or '当前阶段不能重新确认报告填写', data=None), 200
    try:
        from ..report_preview_confirmation import confirm
        result = confirm(report, user, (request.get_json(silent=True) or {}).get('receipt'))
        db.session.commit()
        return jsonify(code=0, message='最新完整报告预览已确认', data=result)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(code=1, message=str(exc), data=None), 200


@bp.get("/attachments/<int:aid>")
@require_auth
def get_attachment(aid):
    user = g.current_user
    att = ReportAttachment.query.filter_by(id=aid, deleted_at=None).first()
    if not att:
        return jsonify({"code": 1, "message": "附件不存在", "data": None}), 200
    _report, error = _report_for_read(user, att.report_no)
    if error:
        return _read_error(error)
    download = request.args.get("download") == "1"
    need = "report.pdf.download" if download else "report.pdf.preview"
    if need not in user.action_codes():
        return jsonify({"code": 403, "message": "无预览/下载权限", "data": None}), 200
    raw = read_file_bytes(att.stored_file, att.data)
    if not raw:
        return jsonify({"code": 1, "message": "附件文件缺失", "data": None}), 200
    resp = make_response(raw)
    resp.headers["Content-Type"] = att.content_type
    safe_inline_types = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}
    disposition = "inline" if not download and (att.content_type or "").lower() in safe_inline_types else "attachment"
    resp.headers["Content-Disposition"] = f"{disposition}; filename*=UTF-8''{quote(att.name)}"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self' data:"
    return resp


@bp.delete("/attachments/<int:aid>")
@require_auth
def delete_attachment(aid):
    user = g.current_user
    if "report.attachment.upload" not in user.action_codes():
        return jsonify({"code": 403, "message": "无附件删除权限", "data": None}), 200
    att = db.session.get(ReportAttachment, aid)
    if not att or att.deleted_at:
        return jsonify({"code": 1, "message": "附件不存在", "data": None}), 200
    if not _report_in_scope(user, att.report_no):
        return jsonify({"code": 1, "message": "附件不在数据范围内", "data": None}), 200
    report = _report_in_scope(user, att.report_no)
    report = Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    step_error = report_data_entry_step_error(user, report)
    if step_error:
        return jsonify({"code": 403, "message": step_error, "data": None}), 200
    if not report_content_editable(report):
        return jsonify({
            "code": 1,
            "message": f"报告当前为「{report.status}」，附件已锁定；请退回检测数据更改环节后修改",
            "data": None,
        }), 200
    from ..models import ReportCorrectionRequest
    if ReportCorrectionRequest.query.filter(db.or_(
        ReportCorrectionRequest.application_attachment_id == att.id,
        ReportCorrectionRequest.receipt_attachment_id == att.id,
    )).first():
        return jsonify(code=1, message="更正申请附件属于审批历史记录，不能删除", data=None), 200
    before = att.meta()
    try:
        if att.stored_file:
            mark_stored_file_deleted(att.stored_file)
        att.deleted_at = datetime.utcnow()
        att.status = "已移除"
        detail = dict(report.detail or {})
        report_composition = dict(detail.get("reportComposition") or {})
        included = report_composition.get("includedOtherAttachmentIds") or []
        report_composition["includedOtherAttachmentIds"] = [
            value for value in included if str(value) != str(att.id)
        ]
        detail["reportComposition"] = report_composition
        report.detail = detail
        add_operation_audit(
            "report.attachment.delete", "report", att.report_no,
            category="report", before=before, message=f"移除附件：{att.name}",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("attachment deletion commit failed")
        return jsonify({"code": 1, "message": "附件移除失败", "data": None}), 500
    from ..preview_cache import schedule_after_save
    schedule_after_save(report)
    return jsonify({"code": 0, "message": "附件已移入回收区", "data": None})
