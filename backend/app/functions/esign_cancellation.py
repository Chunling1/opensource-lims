"""Cancellation of an unsealed signing round by an administrator or report issuer, with immutable history."""
import json
from datetime import datetime

from flask import current_app

from ..audit import add_operation_audit
from ..esign_access import report_scope_error
from ..extensions import db
from ..models import EsignIdentityBinding, Report, ReportEsignFlow, ReportEsignSigner
from .esign_dispatch_state import definitely_uncreated
from .esign_service import (
    COMPLETED_FLOW_STATUSES, EsignServiceError, EsignV3Client,
    _flow_kind, _positioning_snapshot, flow_has_organization_seal,
)


def cancel_actor_error(actor, flow=None):
    """Who may cancel: administrators, or holders of the report-issue action.

    Business decision 2026-11-07 (batch-3 Q7): issuers may cancel an unsealed
    round themselves; a 1-50 character reason and audit remain mandatory.
    Non-admin issuers additionally need the project's report-issue step.
    """
    if not actor or not actor.enabled:
        return '仅管理员或有报告签发权限的人员可以撤销未盖章的签署流程'
    if actor.role_key == 'admin':
        return ''
    if 'report.print.pass' not in actor.action_codes():
        return '仅管理员或有报告签发权限的人员可以撤销未盖章的签署流程'
    if flow is not None and flow.report is not None:
        from ..authorization_scope import project_step_error
        return project_step_error(actor, flow.report, 'report_print', '报告签发') or ''
    return ''


def cancellation_error(actor, flow):
    if not flow:
        return cancel_actor_error(actor) or '电子签发任务不存在'
    error = cancel_actor_error(actor, flow)
    if error:
        return error
    if flow.id < int(current_app.config.get('ESIGN_PROVIDER_FLOW_MIN_ID') or 0):
        return '历史沙箱流程不能作为正式签发任务操作'
    error = report_scope_error(actor, flow.report)
    if error:
        return error
    report = flow.report
    from .esign_stages import is_staged
    if is_staged(flow):
        if report.stamped or flow.status in {'completed', 'verified', 'cancelled'}:
            return '报告已盖章或签署轮次已停止'
        if report.current_document_version_id != flow.report_document_version_id:
            return '签署版本已变化，请核查'
        return ''
    if report.voided or report.stamped or report.status != '待打印':
        return '报告已签发或不在签发环节，不能直接撤销'
    if report.approved_document_version_id != flow.report_document_version_id:
        return '签署流程不是当前批准版本，请刷新签发页面'
    if flow_has_organization_seal(flow) and flow.status in COMPLETED_FLOW_STATUSES:
        return '报告已盖章，不能直接撤销，请按更正申请处理'
    latest = ReportEsignFlow.query.filter_by(report_id=report.id,
        report_document_version_id=flow.report_document_version_id).order_by(ReportEsignFlow.attempt_no.desc()).first()
    if not latest or latest.id != flow.id:
        return '签署流程已被新轮次替代，请刷新签发页面'
    from .esign_unified import is_unified
    if is_unified(flow) and service_seal_state(flow).get('status') in {'finishing'}:
        return '组织盖章请求正在核实，请先刷新状态确认结果后再撤销'
    if flow.status == 'dispatching':
        return '签署流程正在发起，请待发起结果明确后再撤销'
    if flow.status not in {'ready', 'binding_required', 'failed', 'signing', 'completed', 'verified', 'cancelling'}:
        return '当前流程不能撤销'
    if not flow.provider_flow_id:
        if flow.status == 'failed' and not definitely_uncreated(flow):
            return '上次发起结果尚不明确，请先核实上游流程，不能重置签字'
    return ''


def service_seal_state(flow):
    return _positioning_snapshot(flow).get('organizationSeal') or {}


def _has_provider_seal(detail):
    for signer in detail.get('signers') or []:
        if str(signer.get('signerType')) not in {'1', '2'}:
            continue
        fields = signer.get('signFields') or []
        if str(signer.get('signStatus')) == '2' or any(str(f.get('signFieldStatus')) == '4' for f in fields):
            return True
    return False


def _stop_provider(flow, reason):
    if not flow.provider_flow_id:
        prior = (_positioning_snapshot(flow).get('cancellation') or {}).get('previousStatus', flow.status)
        if prior in {'signing', 'completed', 'verified'}:
            raise EsignServiceError('provider_flow_missing', '已发起流程缺少上游编号，请先核实，不能重置签字')
        return {'mode': 'local_unissued'}
    if not (current_app.config.get('EXTERNAL_SIDE_EFFECTS_ENABLED') or current_app.config.get('ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED')):
        raise EsignServiceError('external_side_effects_disabled', '当前环境已关闭真实第三方签署调用')
    client = EsignV3Client()
    path = f'/v3/sign-flow/{flow.provider_flow_id}'
    detail = client.request('GET', path + '/detail')
    if flow_has_organization_seal(flow) and not detail.get('signers'):
        raise EsignServiceError('seal_state_unknown', '上游未返回盖章状态，请先核实，不能重置签字')
    if _has_provider_seal(detail):
        raise EsignServiceError('already_sealed', 'e签宝已完成组织盖章，不能直接撤销，请按更正申请处理')
    status = str(detail.get('signFlowStatus'))
    if status == '1':
        client.request('POST', path + '/revoke', {'revokeReason': reason})
        detail = client.request('GET', path + '/detail')
        if flow_has_organization_seal(flow) and not detail.get('signers'):
            raise EsignServiceError('seal_state_unknown', '撤销后盖章状态未确认，请继续核实')
        status = str(detail.get('signFlowStatus'))
        if _has_provider_seal(detail):
            raise EsignServiceError('already_sealed', '撤销核实时发现组织章已盖，不能重置签字，请按更正申请处理')
    if status == '2':
        from .esign_unified import is_unified
        if is_unified(flow):
            raise EsignServiceError('provider_completed', '上游流程已完结，不能作为撤销处理，请核实后走更正流程')
        # Completed personal-only intermediate PDFs cannot be revoked upstream.
        # Retire this issuance round locally, retaining the provider completion fact.
        signers = detail.get('signers') or []
        if not signers or any(str(s.get('signerType')) != '0' for s in signers) or flow_has_organization_seal(flow):
            raise EsignServiceError('already_sealed', '已完成的盖章流程不能直接撤销，请按更正申请处理')
        return {'mode': 'retired_personal_round', 'providerStatus': status}
    if status not in {'3', '5', '7'}:
        raise EsignServiceError('cancellation_unconfirmed', '尚未确认旧签署流程停止，请稍后点击“继续核实撤销”；当前不会重置签字')
    return {'mode': 'provider_stopped', 'providerStatus': status}


def cancel_and_restart(flow_id, actor, reason):
    from .esign_stages import is_staged, cancel_round
    if is_staged(db.session.get(ReportEsignFlow, flow_id)):
        return cancel_round(flow_id, actor, reason)
    reason = str(reason or '').strip()
    if not reason or len(reason) > 50:
        raise EsignServiceError('invalid_reason', '请填写1至50字的撤销原因')
    flow = db.session.get(ReportEsignFlow, flow_id)
    if not flow or cancel_actor_error(actor, flow):
        raise EsignServiceError('forbidden', cancellation_error(actor, flow))
    report = Report.query.filter_by(id=flow.report_id).with_for_update().populate_existing().one()
    flow = ReportEsignFlow.query.filter_by(id=flow_id).with_for_update().populate_existing().one()
    snapshot = _positioning_snapshot(flow)
    cancellation = snapshot.get('cancellation') or {}
    replacement = db.session.get(ReportEsignFlow, cancellation.get('replacementFlowId')) if cancellation.get('replacementFlowId') else None
    if replacement:
        error = report_scope_error(actor, report)
        if error or report.approved_document_version_id != replacement.report_document_version_id:
            raise EsignServiceError('stale_flow', error or '报告批准版本已变化，请刷新')
        latest = ReportEsignFlow.query.filter_by(report_id=report.id,
            report_document_version_id=replacement.report_document_version_id).order_by(ReportEsignFlow.attempt_no.desc()).first()
        if latest.id != replacement.id:
            raise EsignServiceError('stale_flow', '撤销已完成，当前已进入后续轮次，请刷新')
        return replacement
    error = cancellation_error(actor, flow)
    if error:
        raise EsignServiceError('cancellation_denied', error)
    source = flow
    if _flow_kind(flow) == 'organization_seal':
        source = db.session.get(ReportEsignFlow, snapshot.get('sourceFlowId'))
    if not source or not source.signers or source.report_id != report.id or source.report_document_version_id != flow.report_document_version_id:
        raise EsignServiceError('source_missing', '原签署人员记录不完整，不能重建任务')
    if not cancellation:
        cancellation = {'requestedBy': actor.id, 'requestedByName': actor.name, 'reason': reason,
            'requestedAt': datetime.utcnow().isoformat(), 'previousStatus': flow.status}
        snapshot['cancellation'] = cancellation
        flow.positioning_json = json.dumps(snapshot, ensure_ascii=False)
        flow.status = 'cancelling'
        add_operation_audit('report.esign.cancel.request', 'report', flow.report_no,
            category='integration', actor=actor, after={'flowId': flow.id, **cancellation})
        db.session.commit()
    # Serialize retries, callbacks, dispatch and seal confirmation on this report.
    report = Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    flow = ReportEsignFlow.query.filter_by(id=flow_id).with_for_update().populate_existing().one()
    snapshot = _positioning_snapshot(flow)
    cancellation = snapshot['cancellation']
    if cancellation.get('replacementFlowId'):
        return db.session.get(ReportEsignFlow, cancellation['replacementFlowId'])
    try:
        provider_result = _stop_provider(flow, cancellation['reason'])
        version = flow.document_version
        attempt = db.session.query(db.func.max(ReportEsignFlow.attempt_no)).filter_by(
            report_id=report.id, report_document_version_id=version.id).scalar() + 1
        new = ReportEsignFlow(report_id=report.id, report_no=report.report_no,
            report_document_version_id=version.id, attempt_no=attempt, status='ready', source_sha256=version.sha256,
            created_by_id=actor.id, positioning_json=json.dumps({'flowKind': 'person_signing', 'restartOfFlowId': flow.id,
                'organizationSeal': {'included': False, 'status': 'awaiting_personal_signatures', 'confirmationRequired': True,
                    'sealMode': 'assigned' if current_app.config.get('ESIGN_ORG_SEAL_ID') else 'default',
                    'normalSealScope': 'report_homepage_only', 'acrossPageMode': 'ALL'}}))
        db.session.add(new); db.session.flush()
        for old in source.signers:
            binding = EsignIdentityBinding.query.filter_by(user_id=old.user_id).first()
            ready = bool(binding and binding.status in {'pending', 'verified'})
            new.signers.append(ReportEsignSigner(user_id=old.user_id, role_code=old.role_code, role_name=old.role_name,
                sign_order=old.sign_order, binding_id=binding.id if binding else None,
                legal_name_snapshot=old.legal_name_snapshot, psn_id_snapshot=binding.psn_id if binding else None,
                status='pending' if ready else 'binding_required'))
            if not ready:
                new.status = 'binding_required'
                new.error_code, new.error_message = 'binding_required', '请补齐签署人员身份绑定后发起签署'
        cancellation.update(provider_result, replacementFlowId=new.id, completedAt=datetime.utcnow().isoformat())
        snapshot['cancellation'] = cancellation
        flow.positioning_json = json.dumps(snapshot, ensure_ascii=False)
        flow.status, flow.error_code, flow.error_message = 'cancelled', None, None
        if source.id != flow.id:
            source_snapshot = _positioning_snapshot(source)
            source_snapshot['cancellation'] = {**cancellation, 'cancelledWithFlowId': flow.id, 'mode': 'retired_personal_round'}
            source.positioning_json = json.dumps(source_snapshot, ensure_ascii=False)
            source.status = 'cancelled'
        add_operation_audit('report.esign.cancel.restart', 'report', report.report_no, category='integration', actor=actor,
            after={'flowId': flow.id, 'replacementFlowId': new.id, **provider_result},
            message=f'{"管理员" if actor.role_key == "admin" else "签发人员"}撤销未盖章签署轮次（原因：{cancellation["reason"]}）；保留历史文件及签字，原批准版本重新建立全员待签任务')
        db.session.commit()
        return new
    except Exception as exc:
        db.session.rollback()
        from .esign_unified import is_unified
        if is_unified(flow) and isinstance(exc, EsignServiceError) and exc.code in {'already_sealed', 'provider_completed'}:
            # A definitive seal/completion result is not an unknown revoke.
            # Reopen reconciliation so an approved seal can finish/download.
            Report.query.filter_by(id=flow.report_id).with_for_update().populate_existing().one()
            flow = ReportEsignFlow.query.filter_by(id=flow_id).with_for_update().populate_existing().one()
            snapshot = _positioning_snapshot(flow)
            attempt = snapshot.pop('cancellation', {})
            snapshot['lastDeniedCancellation'] = {**attempt, 'errorCode': exc.code}
            flow.status = attempt.get('previousStatus', 'signing')
            flow.positioning_json = json.dumps(snapshot, ensure_ascii=False)
            add_operation_audit('report.esign.cancel.denied', 'report', flow.report_no, category='integration', actor=actor,
                after={'flowId': flow.id, 'errorCode': exc.code}, message=str(exc))
            db.session.commit()
        # Keep the durable cancellation gate closed until provider outcome is known.
        raise
