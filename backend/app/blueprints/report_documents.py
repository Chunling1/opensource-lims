"""结构化报告内容、生成任务、不可变版本和报告审计接口。"""
import hashlib
import json
from urllib.parse import quote

from flask import Blueprint, current_app, g, jsonify, make_response, request

from ..applications.report_lifecycle import (
    get_authorized_report_for_view,
    get_visible_report,
    has_report_feature_access,
    report_content_editable,
    report_data_entry_step_error,
)
from ..covers import is_system_cover_attachment
from ..extensions import db
from ..platform.audit import add_operation_audit
from ..platform.file_vault import read_file_bytes
from ..models import (
    Report,
    OperationAudit,
    ReportAttachment,
    ReportDocumentContent,
    ReportDocumentVersion,
    ReportRenderJob,
    ReportTemplateProfile,
)
from ..report_documents import (
    attachment_is_active,
    attachment_merge_eligible,
    attachment_role,
    content_dict,
    composition_options,
    create_render_job,
    document_preflight,
    select_profile,
    snapshot_hash,
    source_snapshot,
    supports_no_supplement,
)
from ..security import require_auth

bp = Blueprint("report_documents", __name__, url_prefix="/api/reports")
# Batch-3 Q13 (2026-11-07): business confirmed reports may need up to 100 extra pages.
MAX_EXTRA_PAGES = 100


def _report_for_user(report_no):
    if not has_report_feature_access(g.current_user):
        return None
    return get_visible_report(g.current_user, report_no, require_feature=False)


def _report_for_read(report_no):
    view = str(request.args.get("view") or "").strip()
    report, _projection, error = get_authorized_report_for_view(
        g.current_user, report_no, view
    )
    return report, error


def _read_error(message):
    code = 1 if message in {"报告详情入口无效", "报告不存在或不在数据范围内"} else 403
    return _error(message, code)


def _error(message, code=1):
    return jsonify({"code": code, "message": message, "data": None}), 200


def _clean_text(value, max_length=500):
    return str(value or "").strip()[:max_length]


def _clean_result_groups(value):
    if not isinstance(value, list):
        raise ValueError("resultGroups 需为数组")
    if len(value) > 100:
        raise ValueError("检验结果组不能超过 100 组")
    groups = []
    for group in value:
        if not isinstance(group, dict):
            continue
        raw_items = group.get("items") or []
        if not isinstance(raw_items, list) or len(raw_items) > 100:
            raise ValueError("每组检验结果不能超过 100 条")
        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            items.append({
                "name": _clean_text(item.get("name"), 200),
                "condition": _clean_text(item.get("condition"), 300),
                "unit": _clean_text(item.get("unit"), 40),
                "value": _clean_text(item.get("value"), 500),
            })
        groups.append({"name": _clean_text(group.get("name"), 200), "items": items})
    return groups


def _clean_photos(report_no, value):
    if not isinstance(value, list):
        raise ValueError("photos 需为数组")
    if len(value) > 6:
        raise ValueError("标准照片页最多 6 张照片")
    photos = []
    for photo in value:
        if not isinstance(photo, dict):
            continue
        aid = photo.get("attachmentId")
        if aid in (None, ""):
            photos.append({"attachmentId": None, "caption": _clean_text(photo.get("caption"), 80)})
            continue
        try:
            aid = int(aid)
        except (TypeError, ValueError) as exc:
            raise ValueError("照片附件编号无效") from exc
        attachment = ReportAttachment.query.filter_by(id=aid, report_no=report_no).first()
        if not attachment or not (attachment.content_type or "").lower().startswith("image/"):
            raise ValueError(f"附件 {aid} 不是本报告的图片")
        photos.append({"attachmentId": aid, "caption": _clean_text(photo.get("caption"), 80)})
    return photos


def _clean_composition_options(report_no, value):
    if value in (None, ""):
        return {"includedOtherAttachmentIds": []}
    if not isinstance(value, dict):
        raise ValueError("compositionOptions 需为对象")
    raw_ids = value.get("includedOtherAttachmentIds") or []
    if not isinstance(raw_ids, list) or len(raw_ids) > 50:
        raise ValueError("选入正式报告的其他附件不能超过 50 个")
    ordered = []
    for raw_id in raw_ids:
        try:
            attachment_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("选入附件编号无效") from exc
        if attachment_id not in ordered:
            ordered.append(attachment_id)
    rows = ReportAttachment.query.filter(
        ReportAttachment.report_no == report_no,
        ReportAttachment.deleted_at.is_(None),
        ReportAttachment.id.in_(ordered or [-1]),
    ).all()
    by_id = {row.id: row for row in rows}
    ordered = [aid for aid in ordered if not (by_id.get(aid) and is_system_cover_attachment(by_id[aid]))]
    for attachment_id in ordered:
        row = by_id.get(attachment_id)
        if (
            not row
            or attachment_role(row) != "other"
            or not attachment_is_active(row)
            or not attachment_merge_eligible(row)
        ):
            raise ValueError(f"附件 {attachment_id} 不能并入正式报告")
    result = {"includedOtherAttachmentIds": ordered}
    if 'noSupplementBody' in value:
        if type(value['noSupplementBody']) is not bool:
            raise ValueError('无补充正文确认需为布尔值')
        result['noSupplementBody'] = value['noSupplementBody']
    if 'preserveUploadedReport' in value:
        if type(value['preserveUploadedReport']) is not bool:
            raise ValueError('保留上传完整报告选项需为布尔值')
        result['preserveUploadedReport'] = value['preserveUploadedReport']
    for key, allowed in (('reportLanguage', ('CN', 'EN')), ('reportTemplateVariant', ('Standard', 'Extended'))):
        if key in value:
            if value[key] not in allowed:
                raise ValueError('报告模板语言或版式无效')
            result[key] = value[key]
    return result


@bp.get("/template-profiles")
@require_auth
def template_profiles():
    if not has_report_feature_access(g.current_user):
        return _error("无报告查看权限", 403)
    rows = ReportTemplateProfile.query.filter_by(active=True).order_by(ReportTemplateProfile.id).all()
    return jsonify({"code": 0, "message": "ok", "data": {"rows": [row.to_dict() for row in rows]}})


@bp.get('/docparser-template-options')
@require_auth
def docparser_template_options():
    if not has_report_feature_access(g.current_user):
        return _error('无报告查看权限', 403)
    from ..document_template_catalog import template_catalog
    return jsonify({'code': 0, 'message': 'ok', 'data': template_catalog()})


@bp.post("/<report_no>/prepare-query")
@require_auth
def prepare_query(report_no):
    """Explicit report-preparation command under existing authoring permissions."""
    from .report_publication import ensure_prepared_query, writable
    from ..models import Report
    user = g.current_user
    if not writable() or 'report.attachment.upload' not in user.action_codes():
        return _error('无报告内容编辑权限或平台处于只读状态', 403)
    report = _report_for_user(report_no)
    if not report:
        return _error('报告不存在或不在数据范围内', 403)
    # Shared row lock with admin rotation: serialize first issuance and recheck state.
    report = Report.query.filter_by(id=report.id).populate_existing().with_for_update().one()
    step_error = report_data_entry_step_error(user, report)
    if step_error or not report_content_editable(report):
        db.session.rollback()
        return _error(step_error or '当前报告已锁定，不能准备新的查询二维码', 403)
    try:
        row, created = ensure_prepared_query(report)
        if created:
            add_operation_audit('report.publication.prepare', 'report', report.report_no,
                actor=user, category='report', after={'prepared': True, 'published': False, 'allowDownload': False},
                message='报告编辑流程自动准备查询二维码；未公开文件、不记录查询凭证')
        db.session.commit()
        return jsonify({'code': 0, 'message': '查询二维码已准备', 'data': {'prepared': True}})
    except ValueError as exc:
        db.session.rollback()
        return _error(str(exc))


@bp.get("/<report_no>/document-preflight")
@require_auth
def preflight(report_no):
    report, error = _report_for_read(report_no)
    if error:
        return _read_error(error)
    kind = request.args.get("kind", "official")
    if kind not in ("official", "audit"):
        return _error("报告类型无效")
    try:
        result = document_preflight(report, kind, render_template=False)
    except ValueError as exc:
        return _error(str(exc))
    return jsonify({"code": 0, "message": "ok", "data": result})


@bp.get("/<report_no>/authoring-template")
@bp.get("/<report_no>/continuation-template")
@require_auth
def continuation_template(report_no):
    """Download a field-filled, byte-audited copy of the original report template."""
    user = g.current_user
    if "report.attachment.upload" not in user.action_codes():
        return _error("无报告正文编辑权限", 403)
    report = _report_for_user(report_no)
    if not report:
        return _error("报告不存在或不在数据范围内")
    step_error = report_data_entry_step_error(user, report)
    if step_error:
        return _error(step_error, 403)
    if not report_content_editable(report):
        return _error(f"报告当前为「{report.status}」，正文模板已锁定")
    from .. import docparser_field_only
    try:
        if not docparser_field_only.applies_to(report):
            return _error("该报告仍使用历史模板")
        blob, audit = docparser_field_only.render_preview(report, authoring=True)
    except ValueError as exc:
        return _error(str(exc))
    name = f"{report_no}-完整报告填写模板.docx"
    response = make_response(blob)
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
    response.set_etag(audit["sha256"])
    response.headers["X-Template-Capacity-Warnings"] = quote(json.dumps([*audit.get("capacityWarnings", []), *audit.get("noticeCodes", [])]))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Template-Selection"] = audit["templateSelection"]["filename"]
    return response


@bp.get("/<report_no>/document-content")
@require_auth
def get_content(report_no):
    report, error = _report_for_read(report_no)
    if error:
        return _read_error(error)
    return jsonify({"code": 0, "message": "ok", "data": content_dict(report)})


@bp.put("/<report_no>/document-content")
@require_auth
def save_content(report_no):
    user = g.current_user
    if "report.attachment.upload" not in user.action_codes():
        return _error("无报告内容编辑权限", 403)
    report = _report_for_user(report_no)
    if not report:
        return _error("报告不存在或不在数据范围内")
    report = Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    step_error = report_data_entry_step_error(user, report)
    if step_error:
        return _error(step_error, 403)
    if not report_content_editable(report):
        return _error(f"报告当前为「{report.status}」，正文已锁定；请退回检测数据更改环节后修改")
    body = request.get_json(silent=True) or {}
    try:
        groups = _clean_result_groups(body.get("resultGroups") or [])
        photos = _clean_photos(report_no, body.get("photos") or [])
        composition = _clean_composition_options(report_no, body.get("compositionOptions"))
        # Older clients may omit the new optional key; do not erase a saved decision.
        previous = composition_options(report)
        for key in ('noSupplementBody', 'preserveUploadedReport', 'reportLanguage', 'reportTemplateVariant'):
            if key not in composition and key in previous:
                composition[key] = previous[key]
        if (composition.get('preserveUploadedReport') is True) != (previous.get('preserveUploadedReport') is True):
            if not (user.enabled and (user.role_key == 'admin' or user.account == 'admin')):
                return _error('仅管理员可修改保留上传完整报告选项', 403)
        from .. import docparser_field_only
        if any(key in composition for key in ('reportLanguage', 'reportTemplateVariant', 'preserveUploadedReport')):
            if not docparser_field_only.applies_to(report):
                raise ValueError('该历史报告不支持原包模板选项')
            docparser_field_only.profile_for(report, composition=composition)
        if composition.get('preserveUploadedReport') is True and composition.get('noSupplementBody') is True:
            raise ValueError('保留上传完整报告模式不能同时确认无补充正文')
        if composition.get('noSupplementBody') is True:
            from .. import docparser_field_only
            if not docparser_field_only.applies_to(report):
                raise ValueError('该历史报告不支持无补充正文确认')
            if not supports_no_supplement(report):
                raise ValueError('当前模板的结果和签字页需要通过完整报告上传，不能确认无补充正文')
            rows = ReportAttachment.query.filter_by(report_no=report_no, deleted_at=None).all()
            if any(attachment_is_active(row) and attachment_role(row) in {'report_page', 'completed_report'} for row in rows):
                raise ValueError('已有有效完整报告，请先移除补充正文后再确认无补充；其他附件不受影响')
    except ValueError as exc:
        return _error(str(exc))
    extra_pages = body.get("extraPages") or []
    if not isinstance(extra_pages, list) or len(extra_pages) > MAX_EXTRA_PAGES:
        return _error(f"附加页需为数组且不能超过 {MAX_EXTRA_PAGES} 页")
    clean_pages = [{
        "title": _clean_text(page.get("title"), 120),
        "content": _clean_text(page.get("content"), 5000),
    } for page in extra_pages if isinstance(page, dict)]
    row = ReportDocumentContent.query.filter_by(report_no=report_no).first()
    before = content_dict(report, row) if row else None
    profile = select_profile(report)
    if not row:
        row = ReportDocumentContent(report_no=report_no)
        db.session.add(row)
    row.profile_code = profile.code if profile else "STANDARD-COVER-HOME"
    row.result_groups = groups
    row.remarks = _clean_text(body.get("remarks"), 8000)
    row.photos = photos
    row.extra_pages = clean_pages
    row.updated_by = user.name
    detail = dict(report.detail or {})
    detail["reportPages"] = clean_pages
    detail["reportComposition"] = composition
    report.detail = detail
    db.session.flush()
    after = content_dict(report, row)
    add_operation_audit(
        "report.document.content.update", "report", report_no,
        category="report", before=before, after=after, message="更新结构化报告内容",
    )
    db.session.commit()
    from ..preview_cache import schedule_after_save
    schedule_after_save(report)
    return jsonify({"code": 0, "message": "报告内容已保存", "data": document_preflight(report)})


@bp.post("/<report_no>/document-jobs")
@require_auth
def create_job(report_no):
    user = g.current_user
    if "report.pdf.merge" not in user.action_codes():
        return _error("无报告生成权限", 403)
    report = _report_for_user(report_no)
    if not report:
        return _error("报告不存在或不在数据范围内")
    step_error = report_data_entry_step_error(user, report)
    if step_error:
        return _error(step_error, 403)
    if not report_content_editable(report):
        return _error(
            f"报告当前为「{report.status}」，只能在检测数据录入或检测更改阶段重新生成"
        )
    body = request.get_json(silent=True) or {}
    kind = body.get("outputKind") or "official"
    if kind not in ("official", "audit"):
        return _error("outputKind 仅支持 official 或 audit")
    check = document_preflight(report, kind)
    if check["missing"]:
        return _error("缺少必填字段：" + "、".join(check["missing"]))
    job = create_render_job(current_app._get_current_object(), report, kind, user)
    return jsonify({"code": 0, "message": "报告已进入生成队列", "data": job.to_dict()})


@bp.get("/<report_no>/document-jobs/<job_id>")
@require_auth
def job_status(report_no, job_id):
    report, error = _report_for_read(report_no)
    if error:
        return _read_error(error)
    job = ReportRenderJob.query.filter_by(id=job_id, report_no=report_no).first()
    if not job:
        return _error("生成任务不存在")
    data = job.to_dict()
    if job.version_id:
        version = db.session.get(ReportDocumentVersion, job.version_id)
        if version:
            data["version"] = version.meta()
    return jsonify({"code": 0, "message": "ok", "data": data})


@bp.get("/<report_no>/document-versions")
@require_auth
def versions(report_no):
    report, error = _report_for_read(report_no)
    if error:
        return _read_error(error)
    from sqlalchemy.orm import defer
    rows = ReportDocumentVersion.query.options(
        defer(ReportDocumentVersion.pdf_data), defer(ReportDocumentVersion.docx_data),
        defer(ReportDocumentVersion.snapshot),
    ).filter_by(report_no=report_no).order_by(
        ReportDocumentVersion.created_at.desc(), ReportDocumentVersion.id.desc(),
    ).all()
    hashes, verification_error = {}, ''
    try:
        for kind in ('official', 'audit'):
            hashes[kind] = snapshot_hash(source_snapshot(report, output_kind=kind))
    except ValueError as exc:
        # Listing immutable history must work even when a fresh render cannot be prepared.
        verification_error = str(exc)
    version_rows = []
    for row in rows:
        meta = row.meta(hashes.get(row.output_kind, ''))
        meta['sourceVerification'] = 'unavailable' if verification_error else 'verified'
        meta['sourceVerificationError'] = verification_error
        if verification_error:
            meta['stale'] = None  # unknown is not a successful fresh-source comparison
        version_rows.append(meta)
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": version_rows,
        "sourceVerificationError": verification_error,
        "currentVersionId": report.current_document_version_id,
        "approvedVersionId": report.approved_document_version_id,
    }})


@bp.get("/<report_no>/document-versions/<int:version_id>/file")
@require_auth
def version_file(report_no, version_id):
    report, error = _report_for_read(report_no)
    if error:
        return _read_error(error)
    version = ReportDocumentVersion.query.filter_by(id=version_id, report_no=report_no).first()
    if not version:
        return _error("报告版本不存在")
    fmt = request.args.get("format", "pdf").lower()
    download = request.args.get("download") == "1"
    need = "report.pdf.download" if download else "report.pdf.preview"
    if need not in g.current_user.action_codes():
        return _error("无报告预览/下载权限", 403)
    if fmt == "docx":
        raw, content_type, suffix = read_file_bytes(version.docx_file, version.docx_data), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    else:
        raw, content_type, suffix = read_file_bytes(version.pdf_file, version.pdf_data), "application/pdf", "pdf"
    if not raw:
        return _error(f"该版本没有 {suffix.upper()} 文件")
    label = "正式报告" if version.output_kind == "official" else "内部审核包"
    name = f"{report_no}-{label}-V{version.version_no}.{suffix}"
    response = make_response(raw)
    response.headers["Content-Type"] = content_type
    disposition = "attachment" if download else "inline"
    response.headers["Content-Disposition"] = f"{disposition}; filename*=UTF-8''{quote(name)}"
    response.set_etag(hashlib.sha256(raw).hexdigest())
    return response


@bp.get("/<report_no>/document-audits")
@require_auth
def document_audits(report_no):
    report, error = _report_for_read(report_no)
    if error:
        return _read_error(error)
    rows = OperationAudit.query.filter_by(object_type="report", object_id=report_no).order_by(
        OperationAudit.created_at.desc(), OperationAudit.id.desc(),
    ).limit(100).all()
    return jsonify({"code": 0, "message": "ok", "data": {"rows": [row.to_dict() for row in rows]}})
