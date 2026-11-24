"""Same-number internal corrections; immutable evidence stays in the audit ledger.

All mutations share the caller's transaction. This module never calls eSign or
rewrites a controlled/signed file.
"""
import copy
import json

from .extensions import db
from .models import (Report, ReportDocumentVersion,
                     ReportAttachment, ReportEsignFlow, OperationAudit)
from .audit import add_operation_audit

HISTORY_ACTION = 'report.correction.internal.history'


def history_for(request_id):
    return OperationAudit.query.filter_by(action=HISTORY_ACTION,
        object_type='report_correction', object_id=str(request_id), success=True).first()


def is_historical_flow(flow):
    try:
        return bool(json.loads(flow.positioning_json or '{}').get('internalCorrectionHistory'))
    except (ValueError, TypeError, AttributeError):
        return False


def blocks_new_request(row, report=None):
    if row.status == 'rejected':
        return False
    if row.status != 'approved' or row.correction_type != 'internal' or row.correction_report_no != row.main_report_no:
        return True
    report = report or Report.query.filter_by(report_no=row.main_report_no).first()
    if not report or report.status not in {'待打印', '待发放', '已发放'}:
        return True
    # A completed same-number revision must have a newly approved version;
    # current pointers are cleared when the correction starts.
    audit = history_for(row.id)
    if not audit:
        return True
    previous = (audit.before_data or {}).get('versions', []) if audit else []
    if not report.approved_document_version_id or report.approved_document_version_id in [v['id'] for v in previous]:
        return True
    return False


def begin_internal_correction(report, request_row, actor):
    from .applications.report_lifecycle.commands import apply_return_plan
    from .report_documents import content_dict
    if history_for(request_row.id):
        raise ValueError('本次内部更正已建立历史，不能重复执行')
    from .report_correction_dates import freeze_original_date
    original_date = freeze_original_date(report, request_row.id)
    flows = ReportEsignFlow.query.filter_by(report_id=report.id).with_for_update().all()
    for flow in flows:
        if is_historical_flow(flow):
            continue
        if flow.status == 'cancelling' or ((flow.provider_flow_id or flow.provider_file_id or flow.dispatched_at)
                and flow.status not in {'completed', 'verified', 'cancelled', 'expired', 'rejected'}):
            raise ValueError('报告仍有未结束的电子签署流程，请先撤销未盖章流程，再审批内部更正')
    versions = ReportDocumentVersion.query.filter_by(report_no=report.report_no).order_by(ReportDocumentVersion.id).all()
    attachments = ReportAttachment.query.filter_by(report_no=report.report_no, deleted_at=None).all()
    snapshot = {
        'report': copy.deepcopy(report.to_row()), 'detail': copy.deepcopy(report.detail or {}),
        'content': copy.deepcopy(content_dict(report)),
        'versions': [v.meta() for v in versions],
        'attachments': [a.meta() for a in attachments],
        'flows': [{'id': f.id, 'documentVersionId': f.report_document_version_id,
                   'status': f.status, 'hasSignedFile': bool(f.signed_file_id),
                   'signedSha256': f.signed_sha256, 'sourceSha256': f.source_sha256} for f in flows],
    }
    add_operation_audit(HISTORY_ACTION, 'report_correction', request_row.id,
        category='report', before=snapshot,
        after={'reportNo': report.report_no, 'requestId': request_row.id},
        actor=actor, message='内部更正沿用原编号，更正前业务快照及文件引用留存')
    for flow in flows:
        if not is_historical_flow(flow):
            positioning = json.loads(flow.positioning_json or '{}')
            positioning['internalCorrectionHistory'] = {'requestId': request_row.id}
            flow.positioning_json = json.dumps(positioning, ensure_ascii=False)
    apply_return_plan(report, actor, 'report.approval.return', request_row.reason, request_row.return_mode)
    detail = copy.deepcopy(report.detail or {})
    detail.update(changeRound=True, correctionRequestId=request_row.id,
                  correctionReason=request_row.reason, internalCorrectionRevision=request_row.id)
    detail['correctionOriginalIssueDate'] = original_date
    detail['returnInfo']['source'] = '内部更正审批通过'
    detail['returnPlan']['sourceAction'] = 'report.correction.internal.approved'
    dates = dict(detail.get('workflowDates') or {})
    for key in ('review', 'approval', 'issue', 'distribution', 'archive'):
        dates.pop(key, None)
    detail['workflowDates'] = dates
    # Completion marks must not leak into the editable revision.
    for key in ('sealConfirmation', 'organizationSeal'):
        detail.pop(key, None)
    report.detail = detail
    report.sign = ''
    report.stamped = False
    report.archive_state = ''
    report.current_document_version_id = None
    report.approved_document_version_id = None
    request_row.correction_report_no = report.report_no
    add_operation_audit('report.correction.internal.approved', 'report', report.report_no,
        category='workflow', after={'requestId': request_row.id}, actor=actor,
        message='内部更正开启新轮次，原批准仅保留在历史中')
    return report


def history_pdf(audit, kind, identity):
    """Only immutable files referenced by this revision may be downloaded."""
    import hashlib
    from .functions.stored_files import read_file_bytes
    snapshot = audit.before_data or {}
    if kind == 'version':
        item = next((v for v in snapshot.get('versions', []) if v['id'] == identity), None)
        row = db.session.get(ReportDocumentVersion, identity) if item else None
        raw = (read_file_bytes(row.pdf_file) if row.pdf_file_id else row.pdf_data) if row else None
        expected = item.get('sha256') if item else None
    elif kind == 'signed':
        item = next((f for f in snapshot.get('flows', []) if f['id'] == identity), None)
        row = db.session.get(ReportEsignFlow, identity) if item else None
        raw = read_file_bytes(row.signed_file) if row and row.signed_file_id else None
        expected = item.get('signedSha256') if item else None
    else:
        raise ValueError('历史文件类型无效')
    if not raw or not expected or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('历史文件不存在或哈希不一致')
    return raw


def consolidate_legacy_internal(request_id, actor, *, main_id, derivative_id):
    """Explicit maintenance of an unsigned legacy GZ; caller backs up/commits.

    Preserve its completed editing steps and business changes. Unknown new
    files/versions stop consolidation rather than discarding work.
    """
    from .models import ReportCorrectionRequest, ReportDocumentContent
    row = ReportCorrectionRequest.query.filter_by(id=request_id).with_for_update().one()
    main = Report.query.filter_by(id=main_id).with_for_update().one()
    old = Report.query.filter_by(id=derivative_id).with_for_update().one()
    if (row.status != 'approved' or row.correction_type != 'internal'
            or row.main_report_no != main.report_no or row.correction_report_no != old.report_no
            or old.main_report_no != main.report_no or old.report_kind != 'correction'
            or old.status not in {'委托更改中', '检测更改中'} or old.voided
            or main.status not in {'待打印', '待发放', '已发放'}):
        raise ValueError('原报告或旧 GZ 状态已变化，未归并')
    if (ReportDocumentVersion.query.filter_by(report_no=old.report_no).first()
            or ReportEsignFlow.query.filter_by(report_id=old.id).first()
            or Report.query.filter_by(main_report_no=old.report_no).first()):
        raise ValueError('旧 GZ 已有受控版本、签署或派生记录，不能按未签署方案归并')
    from .blueprints.report_publication import ReportPublication
    if ReportPublication.query.filter_by(report_id=old.id).first():
        raise ValueError('旧 GZ 已有二维码，需要单独核对文件关联')
    mapping = {}
    originals = ReportAttachment.query.filter_by(report_no=main.report_no, deleted_at=None).all()
    for attachment in ReportAttachment.query.filter_by(report_no=old.report_no, deleted_at=None).all():
        match = next((a for a in originals if a.source == attachment.source and
            ((a.file_id and a.file_id == attachment.file_id) or
             (not a.file_id and not attachment.file_id and a.data == attachment.data))), None)
        if not match:
            raise ValueError('旧 GZ 有新增或不同附件，须先核对并保留这些修改')
        mapping[attachment.id] = match.id
    old_snapshot = copy.deepcopy(old.to_row())
    old_detail = copy.deepcopy(old.detail or {})
    composition = copy.deepcopy((main.detail or {}).get('reportComposition') or {})
    begin_internal_correction(main, row, actor)
    # Old GZ attachments are exact copies; rewrite only attachment identity fields.
    def remap(value, key=''):
        if isinstance(value, dict):
            return {k: remap(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v, key) for v in value]
        if key in {'attachmentId', 'fileId'} and isinstance(value, int):
            return mapping.get(value, value) if key == 'attachmentId' else value
        if value == old.report_no:
            return main.report_no
        return value
    detail = remap(old_detail)
    for key in ('derivedFrom', 'mainReportNo', 'reportKind', 'reportSuffix'):
        detail.pop(key, None)
    detail['reportCategory'] = '普通'
    detail['reportComposition'] = {**composition, **(detail.get('reportComposition') or {})}
    detail.update(internalCorrectionRevision=row.id, correctionRequestId=row.id, correctionReason=row.reason)
    detail['signatures'] = {k: v for k, v in (detail.get('signatures') or {}).items() if k not in {'审核', '批准'}}
    detail['workflowDates'] = (main.detail or {}).get('workflowDates', {})
    for key in ('sealConfirmation', 'organizationSeal'):
        detail.pop(key, None)
    main.detail = detail
    for field in ('project', 'project_name', 'client', 'template', 'deadline', 'department', 'owner',
                  'out_of_scope', 'out_of_scope_note', 'entrust_no', 'status', 'sample_status', 'sample_pickup'):
        setattr(main, field, copy.deepcopy(getattr(old, field)))
    source = ReportDocumentContent.query.filter_by(report_no=old.report_no).first()
    if source:
        target = ReportDocumentContent.query.filter_by(report_no=main.report_no).first()
        if target is None:
            target = ReportDocumentContent(report_no=main.report_no); db.session.add(target)
        for field in ('profile_code', 'result_groups', 'remarks', 'photos', 'extra_pages', 'updated_by'):
            setattr(target, field, remap(copy.deepcopy(getattr(source, field))))
    old.report_kind = 'correction_history'
    old.voided = True
    add_operation_audit('report.correction.internal.consolidate', 'report', main.report_no,
        category='workflow', before={'legacyReport': old_snapshot, 'legacyDetail': old_detail},
        after={'requestId': row.id, 'archivedReportId': old.id, 'currentReportId': main.id}, actor=actor,
        message='旧内部 GZ 归并回原编号；原行、附件及操作记录保留为历史')
    return main
