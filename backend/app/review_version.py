"""Freeze an already rendered current preview in the completion transaction."""
import hashlib
from sqlalchemy import func
from .extensions import db
from .models import Report, ReportDocumentVersion
from .report_documents import source_snapshot, snapshot_hash, select_profile, report_composition, document_preflight, FALLBACK_PROFILE
from .platform.file_vault import persist_bytes
from .platform.audit import add_operation_audit


def freeze_ready_preview(report, actor):
    # Serialize competing completion requests using the same report aggregate.
    db.session.query(Report.id).filter_by(id=report.id).with_for_update().one()
    check = document_preflight(report, 'official')
    if check['missing']:
        raise ValueError('报告尚未完整：' + '、'.join(check['missing']))
    snapshot = source_snapshot(report)
    fingerprint = snapshot_hash(snapshot)
    from .preview_cache import cached_pdf
    from .report_preview_confirmation import require_confirmation
    raw, state = cached_pdf(report)
    if not raw:
        raise ValueError('请先生成当前完整报告预览，成功后再完成检测。' + str(state.get('message') or ''))
    require_confirmation(report, snapshot, hashlib.sha256(raw).hexdigest())
    current = db.session.get(ReportDocumentVersion, report.current_document_version_id) if report.current_document_version_id else None
    if (current and current.report_no == report.report_no
            and current.output_kind == 'official' and current.source_hash == fingerprint):
        from .platform.file_vault import read_file_bytes
        current_raw = read_file_bytes(current.pdf_file, current.pdf_data)
        if (current_raw and hashlib.sha256(current_raw).hexdigest() == current.sha256
                and current.sha256 == hashlib.sha256(raw).hexdigest()):
            return current
    profile = select_profile(report)
    number = (db.session.query(func.max(ReportDocumentVersion.version_no)).filter_by(
        report_no=report.report_no, output_kind='official').scalar() or 0) + 1
    saved = persist_bytes(raw, category='report_document',
        original_name=f'{report.report_no}-V{number}.pdf', content_type='application/pdf',
        created_by=actor.account, max_bytes=200 * 1024 * 1024)
    version = ReportDocumentVersion(report_no=report.report_no, output_kind='official',
        version_no=number, profile_code=profile.code if profile else FALLBACK_PROFILE['code'],
        composition=report_composition(report, profile), snapshot=snapshot,
        warnings=list(check['warnings']), source_hash=fingerprint,
        sha256=hashlib.sha256(raw).hexdigest(), pdf_file=saved, created_by=actor.account)
    db.session.add(version)
    db.session.flush()
    report.current_document_version_id = version.id
    report.version = f'V{number}'
    add_operation_audit('report.document.freeze_for_review', 'report', report.report_no,
        category='report', after={'versionId':version.id,'sha256':version.sha256},
        actor=actor, message='完成录入时固化当前预览，供审核使用')
    return version
