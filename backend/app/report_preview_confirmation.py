"""Bind an explicit user confirmation to PDF bytes actually delivered for preview."""
from itsdangerous import URLSafeTimedSerializer, BadSignature
from flask import current_app
from .models import OperationAudit
from .report_documents import source_snapshot, snapshot_hash

ACTION = 'report.preview.confirm'


def serializer():
    return URLSafeTimedSerializer(current_app.config['JWT_SECRET'], salt='report-preview-confirm-v1')


def receipt(report, user, state):
    return serializer().dumps(dict(report=report.report_no, user=user.id,
        source=state['sourceHash'], pdf=state['pdfHash']))


def confirm(report, user, token):
    from .preview_cache import cached_pdf
    from .platform.audit import add_operation_audit
    if not isinstance(token, str) or not token:
        raise ValueError('请重新打开完整报告预览后确认')
    try:
        proof = serializer().loads(token, max_age=7200)
    except (BadSignature, TypeError):
        raise ValueError('预览确认已失效，请重新打开完整报告预览后确认')
    raw, state = cached_pdf(report)
    if (not raw or proof != dict(report=report.report_no, user=user.id,
                                source=state.get('sourceHash'), pdf=state.get('pdfHash'))):
        raise ValueError('报告已修改，请重新打开最新完整报告预览后确认')
    value = dict(sourceHash=snapshot_hash(source_snapshot(report)), pdfHash=state['pdfHash'])
    add_operation_audit(ACTION, 'report', report.report_no, category='report', after=value,
        actor=user, message='已打开并确认当前完整报告预览')
    return value


def require_confirmation(report, snapshot, pdf_hash):
    audit = OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        action=ACTION, success=True).order_by(OperationAudit.id.desc()).first()
    proof = (audit.after_data or {}) if audit else {}
    if proof.get('sourceHash') != snapshot_hash(snapshot) or proof.get('pdfHash') != pdf_hash:
        raise ValueError('当前报告尚未确认最新预览；修改数据、正文或附件后，请重新打开完整报告预览并点击“报告确认”，再完成填写')
