"""Sealed artifact access and explicit department release, independent of legacy status."""
from .organization_privileges import has_full_platform_authority

SEALED_DOWNLOAD = 'report.sealed.download'
RELEASE_ACTION = 'report.distribution.complete'
SEALED = '报告已盖章，归档中，未发放'
ARCHIVED = '报告已归档，发放中'
RELEASED = '报告发放完成'


def delivery_released(report):
    record = (report.detail or {}).get('reportDelivery') or {}
    return bool(record.get('released') is True and (record.get('sealedFlowId') or record.get('offlineRelease')) and record.get('versionId') and record.get('versionId') ==
                (report.approved_document_version_id or report.current_document_version_id)
                and report.status == '已发放' and report.archive_state == '归档完成')


def same_department(user, report):
    return bool(user and user.enabled and user.department and report.department
                and user.department.name == report.department)


def sealed_file_access_error(user, report, flow=None):
    if not user or not user.enabled or report.voided:
        return '账号或报告不可用'
    current_id = ((report.detail or {}).get('reportDelivery') or {}).get('sealedFlowId')
    if delivery_released(report) and same_department(user, report) and (flow is None or flow.id == current_id):
        return ''
    from .esign_access import report_scope_error
    error = report_scope_error(user, report)
    if error:
        return error
    if has_full_platform_authority(user) or SEALED_DOWNLOAD in user.action_codes():
        return ''
    return '报告尚未发放或不属于本部门，需要盖章报告下载权限（未发放状态）'


def mark_sealed(report, flow, actor=None):
    """Called inside the signing transaction; no commit or external calls."""
    from .issuance_data_status import flow_label, CONFIRMING
    if (report.voided or report.status != '待打印' or
            flow.report_document_version_id != (report.approved_document_version_id or report.current_document_version_id)
            or flow_label(flow) != CONFIRMING):
        return False
    from .models import ReportEsignFlow
    latest = ReportEsignFlow.query.filter_by(report_id=report.id,
        report_document_version_id=flow.report_document_version_id).order_by(
            ReportEsignFlow.attempt_no.desc(), ReportEsignFlow.id.desc()).first()
    if not latest or latest.id != flow.id:
        return False
    from .audit import add_operation_audit
    report.status = '待发放'
    report.stamped = True
    report.archive_state = ''
    detail = dict(report.detail or {})
    detail['reportDelivery'] = {'released': False, 'versionId': flow.report_document_version_id,
                                'sealedFlowId': flow.id}
    report.detail = detail
    add_operation_audit('report.seal.completed', 'report', report.report_no, category='workflow',
        after={'status': report.status, 'flowId': flow.id, 'dataStatus': SEALED}, actor=actor)
    return True


def sealed_current_flow(report):
    from flask import current_app
    from .models import ReportEsignFlow
    from .issuance_data_status import flow_label
    version_id = report.approved_document_version_id or report.current_document_version_id
    if not version_id:
        return None
    flow = ReportEsignFlow.query.filter_by(report_id=report.id,
        report_document_version_id=version_id).order_by(
        ReportEsignFlow.attempt_no.desc(), ReportEsignFlow.id.desc()).first()
    if (flow and flow.id >= int(current_app.config.get('ESIGN_PROVIDER_FLOW_MIN_ID', 0))
            and flow_label(flow) == SEALED):
        return flow
    return None


def sealed_file_integrity_error(flow):
    import hashlib
    from .platform.file_vault import read_file_bytes
    try:
        raw = read_file_bytes(flow.signed_file) if flow and flow.signed_file else None
    except (OSError, ValueError):
        raw = None
    if not raw or hashlib.sha256(raw).hexdigest() != flow.signed_sha256:
        return '盖章文件缺失或完整性校验失败，请先核查正式文件'
    return ''
