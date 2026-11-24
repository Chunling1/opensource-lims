"""Bind an unsigned PDF to the latest effective approval event."""
import copy
import hashlib
from sqlalchemy import func
from .extensions import db
from .models import Report, ReportDocumentVersion, ReportEsignFlow, OperationAudit
from .workflow_dates import business_date


def approval_event(report):
    event=OperationAudit.query.filter_by(object_type='report',object_id=report.report_no,
        category='workflow',success=True).filter(OperationAudit.action.in_([
        'report.approval.pass','report.approval.undo','report.approval.return',
        'report.review.undo','report.review.return','report.correction.internal.approved'])).order_by(
        OperationAudit.created_at.desc(),OperationAudit.id.desc()).first()
    return event if event and event.action=='report.approval.pass' else None


def finalize_approved_version(report, version, actor=None):
    from .document_module import finalize_issue_date
    from .docparser_field_only import profile_for
    from .functions.stored_files import read_file_bytes, persist_bytes
    from .report_documents import snapshot_hash
    from .pdf_issue_date import POLICY
    from .audit import add_operation_audit
    Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    event=approval_event(report)
    if event is None:
        raise ValueError('本轮尚无有效批准记录，未填写报告日期')
    day=business_date(event.created_at).isoformat()
    if (not version or version.report_no!=report.report_no
            or version.id!=report.approved_document_version_id or version.output_kind!='official'):
        raise ValueError('缺少当前批准PDF版本，未填写报告日期')
    flows=ReportEsignFlow.query.filter_by(report_id=report.id,report_document_version_id=version.id).all()
    if any((f.provider_file_id or f.provider_flow_id or f.dispatched_at)
           and f.status not in {'cancelled', 'expired', 'rejected'} for f in flows):
        if (version.snapshot or {}).get('approvalDate') not in ('',None,day):
            raise ValueError('原批准版本已进入电子签署且日期与本次批准不同，请先按流程处理旧签署并生成更正版本')
        return version
    raw=read_file_bytes(version.pdf_file,version.pdf_data)
    if not raw or hashlib.sha256(raw).hexdigest()!=version.sha256:
        raise ValueError('批准PDF缺失或哈希不一致，未填写报告日期')
    old=version.snapshot or {}
    stamp=old.get('issueDateVerification') or {}
    if (stamp.get('policy')==POLICY and stamp.get('approvalEventId')==event.id
            and stamp.get('outputSha256')==version.sha256 and stamp.get('approvalDate')==day):
        return version
    profile=(old.get('template') or {}).get('profile') or profile_for(report)
    final,audit=finalize_issue_date(raw,day,category=profile['kind'].title(),language=profile['language'],
                                  extended=profile['variant']=='Extended')
    proof=audit['issueDate'];proof.update(approvalEventId=event.id,sourceVersionId=version.id)
    snapshot=copy.deepcopy(old)
    snapshot.update(approvalDate=day,issueDateVerification=proof)
    snapshot.pop('approvalDateBinding',None)
    number=(db.session.query(func.max(ReportDocumentVersion.version_no)).filter_by(
        report_no=report.report_no,output_kind='official').scalar() or 0)+1
    created_by=getattr(actor,'account',None) or 'report-date-system'
    file=(persist_bytes(final,category='report_document',original_name=f'{report.report_no}-V{number}.pdf',
        content_type='application/pdf',created_by=created_by) if final!=raw else version.pdf_file)
    result=ReportDocumentVersion(report_no=report.report_no,output_kind='official',version_no=number,
        status='approved',profile_code=version.profile_code,composition=copy.deepcopy(version.composition),
        snapshot=snapshot,source_hash=snapshot_hash(snapshot),sha256=hashlib.sha256(final).hexdigest(),
        pdf_file=file,pdf_data=(final if file is None else None),
        docx_file_id=version.docx_file_id,docx_data=version.docx_data,
        warnings=[w for w in (version.warnings or []) if '正文日期未自动改写' not in w]+[
            '报告日期已按本次批准日期核查；原PDF及审核批准历史保留'],created_by=created_by)
    db.session.add(result);db.session.flush()
    report.current_document_version_id=report.approved_document_version_id=result.id
    report.version=f'V{number}'
    add_operation_audit('report.issue_date.finalize','report',report.report_no,category='report',actor=actor,
        before={'versionId':version.id,'sha256':version.sha256},
        after={'versionId':result.id,'sha256':result.sha256,'approvalEventId':event.id,'approvalDate':day,
               'changed':proof['changed'],'page':proof['page']},message='批准后核查并更新PDF报告日期，保留原版本')
    return result


def prepare_dispatch_date(flow, actor=None):
    """Upgrade a local-only prepared task before its first provider upload."""
    from . import docparser_field_only
    if (flow.provider_file_id or flow.provider_flow_id or flow.dispatched_at
            or not docparser_field_only.applies_to(flow.report)):
        return
    from .report_final_fields import ensure_approved_date_version
    from .audit import add_operation_audit
    previous = flow.report_document_version_id
    version = ensure_approved_date_version(flow.report, flow.document_version, actor)
    if previous == version.id:
        return
    flow.document_version = version
    flow.source_sha256 = version.sha256
    flow.attempt_no = (db.session.query(func.max(ReportEsignFlow.attempt_no)).filter(
        ReportEsignFlow.report_id == flow.report_id,
        ReportEsignFlow.report_document_version_id == version.id,
        ReportEsignFlow.id != flow.id).scalar() or 0) + 1
    add_operation_audit('report.issue_date.dispatch_bind', 'report', flow.report_no,
        category='report', actor=actor, before={'flowId': flow.id, 'versionId': previous},
        after={'flowId': flow.id, 'versionId': version.id, 'sha256': version.sha256},
        message='首次上传签署文件前核查报告日期并关联核查后的版本')
