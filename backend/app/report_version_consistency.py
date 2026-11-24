"""Compare immutable report inputs before workflow decisions and provider upload."""
from copy import deepcopy
import hashlib
from datetime import datetime

from .extensions import db
from .models import ReportDocumentVersion


def content_snapshot(snapshot):
    """Ignore only workflow metadata which the field-only PDF does not render.

    Approval date is applied separately to the locked PDF. Reviewer/approver
    signatures are applied by e-signing, not by the field-only template. Keep
    chief selection, all form values, attachment hashes and template inputs.
    """
    value = deepcopy(snapshot or {})
    for key in ('approvalDate', 'issueDateVerification', 'approvalDateBinding'):
        value.pop(key, None)
    detail = (value.get('report') or {}).get('detail')
    if isinstance(detail, dict):
        signatures = detail.get('signatures')
        if isinstance(signatures, dict):
            signatures.pop('审核', None)
            signatures.pop('批准', None)
            if not signatures:
                detail.pop('signatures', None)
        detail.pop('projectWorkflowSkips', None)
        # Acknowledgement bookkeeping is not rendered; actual seal and standard
        # values remain in rawSample/checkInput/template and are still compared.
        detail.pop('complianceResolution', None)
    return value


def confirmed_input_snapshot(snapshot):
    """Compare report inputs, retaining the selected template, not renderer provenance."""
    from .report_date_display import compact_test_date
    value = content_snapshot(snapshot)
    template = value.get('template')
    if not isinstance(template, dict):
        return value
    template.pop('release', None)
    template.pop('originalSource', None)
    if 'files' in template:
        template['files'] = [row for row in template['files']
                             if not row.get('filename', '').endswith(('.py', '.json'))]
    for key in ('TestDate', '检测日期'):
        if key in template.get('fieldValues', {}):
            template['fieldValues'][key] = compact_test_date(template['fieldValues'][key],
                language=template.get('profile', {}).get('language', 'CN'))
    return value


def require_current_document(report, version=None):
    from .report_documents import source_snapshot
    from .platform.file_vault import read_file_bytes
    version = version or (db.session.get(ReportDocumentVersion, report.current_document_version_id)
                          if report.current_document_version_id else None)
    if (not version or version.report_no != report.report_no or version.output_kind != 'official'):
        raise ValueError('尚无当前正式报告，请返回检测录入生成并确认最新完整报告，再重新校核、审核和批准')
    # Old/partial snapshots cannot prove equality and must not silently pass.
    old = version.snapshot or {}
    if not all(key in old for key in ('report', 'template', 'attachments', 'content')):
        raise ValueError('正式报告缺少完整来源记录，请重新生成并确认后再流转')
    if confirmed_input_snapshot(old) != confirmed_input_snapshot(source_snapshot(report)):
        raise ValueError('报告内容或模板已变化，当前预览与正式版本不一致；请返回检测录入生成并确认最新报告，再重新校核、审核和批准')
    raw = read_file_bytes(version.pdf_file, version.pdf_data)
    if not raw or hashlib.sha256(raw).hexdigest() != version.sha256:
        raise ValueError('正式报告文件缺失或完整性校验失败，不能继续审批或送签')
    return version


LOCK_ACTION = 'report.document.review_lock'
LEGACY_LOCK_ACTION = 'report.document.legacy_review_verified'
LOCK_DEPLOYED_AT = datetime(2026, 11, 13, 9, 35, 39)  # UTC, verified deployment receipt.


def business_revision(report):
    """Cheap DB-only change detection; never render or scan template files."""
    from .models import ReportAttachment, ReportDocumentContent
    from .report_documents import snapshot_hash
    detail = content_snapshot({'report': {'detail': report.detail or {}}})['report']['detail']
    content = ReportDocumentContent.query.filter_by(report_no=report.report_no).first()
    rows = ReportAttachment.query.with_entities(ReportAttachment.id, ReportAttachment.name,
        ReportAttachment.source, ReportAttachment.status, ReportAttachment.content_type,
        ReportAttachment.file_id, ReportAttachment.uploaded_at, ReportAttachment.deleted_at
    ).filter_by(report_no=report.report_no).order_by(ReportAttachment.id).all()
    return snapshot_hash(dict(
        report=[report.report_no, report.sample_no, report.entrust_no, report.project,
                report.project_name, report.client, report.department, report.owner, detail],
        content=(content.to_dict() if content else None),
        attachments=[[r.id, r.name, r.source, r.status, r.content_type, r.file_id,
                      str(r.uploaded_at), str(r.deleted_at)] for r in rows]))


def lock_reviewed_document(report, actor=None):
    """Full comparison runs once at successful review, in its transaction."""
    from .platform.audit import add_operation_audit
    from .report_documents import snapshot_hash
    version = require_current_document(report)
    add_operation_audit(LOCK_ACTION, 'report', report.report_no, category='report', actor=actor,
        after=dict(versionId=version.id, pdfHash=version.sha256,
                   snapshotHash=snapshot_hash(content_snapshot(version.snapshot)),
                   businessRevision=business_revision(report)),
        message='审核核对当前完整报告并锁定版本；后续仅补日期及签署')
    return version


def _legacy_review_proof(report):
    from .models import OperationAudit
    from .report_documents import source_snapshot, snapshot_hash
    from .platform.file_vault import read_file_bytes
    review = OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        action='report.review.pass', success=True).order_by(OperationAudit.id.desc()).first()
    error = '报告与原审核版本不一致或缺少可核验的历史审核记录，请重新预览确认并提交审核'
    if not review or review.created_at >= LOCK_DEPLOYED_AT:
        raise ValueError(error)
    root_id = (review.after_data or {}).get('currentDocumentVersionId')
    root = db.session.get(ReportDocumentVersion, root_id) if root_id else None
    if (not root or root.report_no != report.report_no or root.output_kind != 'official'
            or root.created_at > review.created_at):
        raise ValueError(error)
    old = confirmed_input_snapshot(root.snapshot)
    if not all(key in old for key in ('report', 'template', 'attachments', 'content')):
        raise ValueError(error)
    current = confirmed_input_snapshot(source_snapshot(report))
    # A later template file release must not invalidate an already reviewed PDF.
    # Keep template selection, all business fields and attachment hashes exact.
    for snapshot in (old, current):
        snapshot['template'].pop('files', None)
        if isinstance(snapshot['template'].get('originalSource'), dict):
            snapshot['template']['originalSource'].pop('files', None)
    if old != current:
        raise ValueError('历史报告业务数据、正文或附件与原审核版本不一致，请重新预览确认并提交审核')
    raw = read_file_bytes(root.pdf_file, root.pdf_data)
    if not raw or hashlib.sha256(raw).hexdigest() != root.sha256:
        raise ValueError('历史审核PDF缺失或完整性校验失败，不能批准或送签')
    approval = OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        action='report.approval.pass', success=True).filter(OperationAudit.id > review.id).order_by(OperationAudit.id.desc()).first()
    if approval and (approval.after_data or {}).get('approvedDocumentVersionId') != root.id:
        raise ValueError('历史批准版本与原审核版本不一致，请核实后重新审核')
    if OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        action='report.approval.undo', success=True).filter(OperationAudit.id > review.id).first():
        raise ValueError('历史批准已撤回，请按当前流程重新审核')
    return review, dict(versionId=root.id, pdfHash=root.sha256,
        snapshotHash=snapshot_hash(content_snapshot(root.snapshot)), businessRevision=business_revision(report),
        originalReviewAuditId=review.id, originalApprovalAuditId=approval.id if approval else None,
        verificationPolicy='legacy-review-v1')


def require_reviewed_document(report, version=None, *, record_legacy=False, actor=None):
    """Validate review lineage, database revision and PDF integrity, not templates."""
    from .models import OperationAudit
    from .report_documents import snapshot_hash
    from .platform.file_vault import read_file_bytes
    version = version or (db.session.get(ReportDocumentVersion, report.current_document_version_id)
                          if report.current_document_version_id else None)
    if not version or version.report_no != report.report_no or version.output_kind != 'official':
        raise ValueError('尚无当前正式报告，请重新预览确认并提交审核')
    lock = OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        success=True).filter(OperationAudit.action.in_([LOCK_ACTION, LEGACY_LOCK_ACTION])).order_by(OperationAudit.id.desc()).first()
    proof = (lock.after_data or {}) if lock else {}
    error = '当前报告与审核锁定版本不一致或缺少审核锁定记录，请重新预览确认并提交审核'
    if not lock:
        lock, proof = _legacy_review_proof(report)
    if not proof.get('businessRevision'):
        raise ValueError(error)
    revoked = OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        success=True).filter(OperationAudit.id > lock.id, OperationAudit.action.in_([
            'report.review.undo', 'report.review.return', 'report.approval.return',
            'report.correction.internal.approved'])).first()
    if revoked or proof['businessRevision'] != business_revision(report):
        raise ValueError(error)
    if version.id != report.current_document_version_id:
        raise ValueError(error)
    root = db.session.get(ReportDocumentVersion, proof.get('versionId'))
    if (not root or root.report_no != report.report_no or root.sha256 != proof.get('pdfHash')
            or snapshot_hash(content_snapshot(root.snapshot)) != proof.get('snapshotHash')
            or snapshot_hash(content_snapshot(version.snapshot)) != proof.get('snapshotHash')):
        raise ValueError(error)
    # A dated successor must have been created by the controlled date finalizer.
    cursor = version
    visited = set()
    events = OperationAudit.query.filter_by(action='report.issue_date.finalize',
        object_type='report', object_id=report.report_no, success=True).all()
    while cursor.id != root.id:
        if cursor.id in visited:
            raise ValueError(error)
        visited.add(cursor.id)
        stamp = (cursor.snapshot or {}).get('issueDateVerification') or {}
        if not any((e.after_data or {}).get('versionId') == cursor.id
                   and (e.after_data or {}).get('sha256') == cursor.sha256
                   and (e.before_data or {}).get('versionId') == stamp.get('sourceVersionId') for e in events):
            raise ValueError(error)
        cursor = db.session.get(ReportDocumentVersion, stamp.get('sourceVersionId'))
        if not cursor or cursor.report_no != report.report_no:
            raise ValueError(error)
    raw = read_file_bytes(version.pdf_file, version.pdf_data)
    if not raw or hashlib.sha256(raw).hexdigest() != version.sha256:
        raise ValueError('审核锁定报告文件缺失或哈希不一致，不能批准或送签')
    if record_legacy and lock.action == 'report.review.pass':
        from .platform.audit import add_operation_audit
        add_operation_audit(LEGACY_LOCK_ACTION, 'report', report.report_no, category='report', actor=actor,
            after=proof, message='本次核验历史审核版本、当前业务输入及补日期链一致；保留原审核时间和已审核PDF')
    return version
