"""One open provider flow: personal signatures -> explicit approval -> seals -> finish.

Only newly dispatched flows carry this marker. Never migrate a live legacy flow.
"""
import json
from datetime import datetime

from flask import current_app

from ..audit import add_operation_audit
from ..extensions import db
from ..models import Report, ReportEsignFlow
from ..esign_access import flow_state_error
from ..esign_seal_confirmation import access_error
from . import esign_service as service

MODE = 'single_flow_confirmation_v1'


def is_unified(flow):
    return bool(flow and service._positioning_snapshot(flow).get('signingMode') == MODE)


def _save(flow, snapshot):
    flow.positioning_json = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'))


def _lock(flow_id):
    flow = db.session.get(ReportEsignFlow, flow_id)
    if not flow:
        raise service.EsignServiceError('flow_missing', '签署流程不存在')
    Report.query.filter_by(id=flow.report_id).with_for_update().populate_existing().one()
    return ReportEsignFlow.query.filter_by(id=flow_id).with_for_update().populate_existing().one()


def _client():
    if not (current_app.config.get('EXTERNAL_SIDE_EFFECTS_ENABLED') or current_app.config.get('ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED')):
        raise service.EsignServiceError('external_side_effects_disabled', '当前环境已关闭第三方签署调用')
    return service.EsignV3Client()


def _fields(detail, signer_type, file_id):
    return {f.get('customBizNum'): f for s in detail.get('signers') or []
            if str(s.get('signerType')) == str(signer_type)
            for f in s.get('signFields') or [] if f.get('fileId') == file_id}


def sync_provider_detail(flow, client):
    """Staged caller owns provider_turn; release SQL locks before the network round trip."""
    flow_id, provider_id = flow.id, flow.provider_flow_id
    db.session.commit()
    detail = client.request('GET', f'/v3/sign-flow/{provider_id}/detail')
    return _sync(_lock(flow_id), client, detail)


def _sync(flow, client, detail):
    """Caller holds report/flow locks. Reading never appends a seal."""
    from .esign_stages import is_staged
    if is_staged(flow):
        error = flow_state_error(flow)
        if error:
            raise service.EsignServiceError('stage_invalid', error)
    snapshot = service._positioning_snapshot(flow)
    seal = snapshot['organizationSeal']
    status = str(detail.get('signFlowStatus'))
    if status in {'3', '5', '7'}:
        flow.status = {'3': 'cancelled', '5': 'expired', '7': 'rejected'}[status]
        db.session.commit()
        return flow
    people = _fields(detail, 0, flow.provider_file_id)
    from .esign_stages import is_staged, reconcile, all_stages_signed
    if is_staged(flow):
        reconcile(flow, detail, snapshot)
        _save(flow, snapshot)
    for signer in flow.signers:
        field = people.get(f'{flow.report_no}-{signer.role_code.upper()}') or {}
        if str(field.get('signFieldStatus')) == '4':
            signer.status = 'signed'
            signer.signed_at = signer.signed_at or datetime.utcnow()
    # Require the upstream evidence on this refresh, not only cached local flags.
    date_signed = not is_staged(flow) or str(people.get(f'{flow.report_no}-APPROVAL-DATE', {}).get('signFieldStatus')) == '4'
    all_people = date_signed and all_stages_signed(flow) and bool(flow.signers) and all(
        str((people.get(f'{flow.report_no}-{s.role_code.upper()}') or {}).get('signFieldStatus')) == '4'
        for s in flow.signers)
    org = _fields(detail, 1, flow.provider_file_id)
    expected = seal.get('expectedFields') or []
    all_seals = bool(expected) and all(str((org.get(k) or {}).get('signFieldStatus')) == '4' for k in expected)
    if org and not seal.get('confirmation'):
        raise service.EsignServiceError('unexpected_seal', '上游出现未经本系统确认的组织签章，请核实流程')
    if expected and all(k in org for k in expected):
        seal.update(included=True, status='signing')
    elif not seal.get('appendRequestedAt'):
        seal['status'] = 'awaiting_confirmation' if all_people else 'awaiting_personal_signatures'
    if status == '2' and not (all_people and all_seals and seal.get('confirmation')):
        raise service.EsignServiceError('unexpected_completion', '上游流程已完结但签字或组织章证据不完整，请核实；未开放签章报告下载')
    if all_people and all_seals and seal.get('confirmation'):
        seal.update(included=True, status='finishing')
        _save(flow, snapshot)
        staged = is_staged(flow)
        flow_id, provider_id, needs_file = flow.id, flow.provider_flow_id, not flow.signed_file_id
        if staged:
            db.session.commit()
        if status == '1':
            client.request('POST', f'/v3/sign-flow/{provider_id}/finish')
            status = str(client.request('GET', f'/v3/sign-flow/{provider_id}/detail').get('signFlowStatus'))
        pdf = client.download_signed_pdf(provider_id) if status == '2' and needs_file else None
        if staged:
            flow = _lock(flow_id)
            error = flow_state_error(flow)
            if error:
                raise service.EsignServiceError('stage_changed', error)
        if status == '2':
            if pdf is not None:
                service.store_signed_file(flow, pdf)
            else:
                flow.status = 'completed'
                seal['status'] = 'completed'
                _save(flow, snapshot)
                from ..report_delivery import mark_sealed
                mark_sealed(flow.report, flow)
        else:
            _save(flow, snapshot)
    else:
        _save(flow, snapshot)
    flow.error_code = flow.error_message = None
    db.session.commit()
    return flow


def refresh(flow_id):
    from .esign_stages import is_staged, provider_turn
    if is_staged(db.session.get(ReportEsignFlow, flow_id)):
        with provider_turn(flow_id):
            flow = _lock(flow_id)
            error = flow_state_error(flow)
            if error or not flow.provider_flow_id:
                raise service.EsignServiceError('flow_unavailable', error or '电子签署流程尚未发起')
            if flow.status in service.COMPLETED_FLOW_STATUSES:
                return flow
            return sync_provider_detail(flow, _client())
    flow = _lock(flow_id)
    error = flow_state_error(flow)
    if error or not is_unified(flow) or not flow.provider_flow_id:
        raise service.EsignServiceError('flow_unavailable', error or '当前流程不支持此刷新操作')
    if flow.status in service.COMPLETED_FLOW_STATUSES:
        return flow
    client = _client()
    return _sync(flow, client, client.request('GET', f'/v3/sign-flow/{flow.provider_flow_id}/detail'))


def _organization(flow, client, snapshot):
    pdf = service._flow_source_pdf(flow)
    positions = dict(snapshot.get('positions') or {})
    if snapshot.get('layoutKind') != 'calibration':
        from .report_seal_layout import organization_positions
        anchor = ((snapshot.get('evidence') or {}).get('cover') or {}).get('providerPosition')
        if not anchor:
            rows = client.keyword_positions(flow.provider_file_id, list(dict.fromkeys(
                word for groups in service.REPORT_LAYOUT_KEYWORDS.values() for words in groups.values() for word in words)))
            anchor = service._report_homepage_layout(rows, service.REPORT_LAYOUT_KEYWORDS)['anchors']['cover']
        try:
            org_positions, evidence = organization_positions(pdf, anchor)
        except Exception as exc:
            raise service.EsignServiceError('organization_seal_layout_invalid', '组织章定位失败：' + str(exc)) from exc
        positions.update(org_positions)
        snapshot['organizationGeometry'] = evidence
    snapshot['positions'] = positions
    return service._organization_signer(flow.provider_file_id, flow.report_no, positions,
                                        force=True, sign_order=max(s.sign_order for s in flow.signers) + 1)


def confirm(flow_id, actor, source_sha256, report_no):
    from .esign_stages import is_staged, provider_turn
    if is_staged(db.session.get(ReportEsignFlow, flow_id)):
        with provider_turn(flow_id):
            return _confirm(flow_id, actor, source_sha256, report_no, staged=True)
    return _confirm(flow_id, actor, source_sha256, report_no, staged=False)


def _confirm(flow_id, actor, source_sha256, report_no, *, staged):
    flow = _lock(flow_id)
    error = access_error(actor, flow.report) or flow_state_error(flow)
    if error:
        raise service.EsignServiceError('forbidden', error)
    if not is_unified(flow) or flow.report_no != report_no or source_sha256 != flow.source_sha256:
        raise service.EsignServiceError('stale_confirmation', '当前签署文件已变化，请刷新后重新核对')
    if flow.status in service.COMPLETED_FLOW_STATUSES:
        return flow
    if flow.status != 'signing' or not flow.provider_flow_id:
        raise service.EsignServiceError('not_signing', '当前流程不能进行签章确认')
    client = _client()
    if staged:
        sync_provider_detail(flow, client)
    if not staged:
        _sync(flow, client, client.request('GET', f'/v3/sign-flow/{flow.provider_flow_id}/detail'))
    # _sync commits; reacquire the same lock before deciding to append.
    flow = _lock(flow_id)
    error = access_error(actor, flow.report) or flow_state_error(flow)
    if error:
        raise service.EsignServiceError('forbidden', error)
    snapshot = service._positioning_snapshot(flow)
    seal = snapshot['organizationSeal']
    if seal.get('appendRequestedAt'):
        # Unknown POST outcome must be reconciled by refresh, never by a second append.
        if seal.get('status') == 'appending':
            raise service.EsignServiceError('append_pending', '盖章请求结果待核实，请刷新状态；不会重复追加组织章')
        return flow
    if flow.status != 'signing' or seal.get('status') != 'awaiting_confirmation':
        raise service.EsignServiceError('signatures_incomplete', '所有人员签字完成后才能确认盖章')
    if staged:
        db.session.commit()
    organization = _organization(flow, client, snapshot)
    if staged:
        db.session.rollback()
        flow = _lock(flow_id)
        error = access_error(actor, flow.report) or flow_state_error(flow)
        if error or flow.status != 'signing':
            raise service.EsignServiceError('flow_changed', error or '流程状态已变化，未追加组织章')
    seal.update(status='appending', appendRequestedAt=datetime.utcnow().isoformat(),
                expectedFields=[f['customBizNum'] for f in organization['signFields']],
                confirmation={'userId': actor.id, 'userName': actor.name,
                    'confirmedAt': datetime.utcnow().isoformat(), 'documentVersionId': flow.report_document_version_id,
                    'sourceFlowId': flow.id, 'sourceSha256': flow.source_sha256},
                sealMode='assigned' if current_app.config.get('ESIGN_ORG_SEAL_ID') else 'default')
    _save(flow, snapshot)
    add_operation_audit('report.esign.unified.confirm', 'report', flow.report_no, category='integration', actor=actor,
                        after={'flowId': flow.id, 'providerFlowId': flow.provider_flow_id, 'sourceSha256': flow.source_sha256})
    # Durable gate survives timeout/crash and serializes confirmation vs cancellation.
    provider_id = flow.provider_flow_id
    db.session.commit()
    if staged:
        client.request('POST', f'/v3/sign-flow/{provider_id}/signers/sign-fields', {'signers': [organization]})
        return sync_provider_detail(flow, client)
    flow = _lock(flow_id)
    error = flow_state_error(flow)
    if error or flow.status != 'signing':
        raise service.EsignServiceError('flow_changed', error or '流程状态已变化，未追加组织章')
    try:
        client.request('POST', f'/v3/sign-flow/{flow.provider_flow_id}/signers/sign-fields', {'signers': [organization]})
        return _sync(flow, client, client.request('GET', f'/v3/sign-flow/{flow.provider_flow_id}/detail'))
    except Exception:
        db.session.rollback()
        raise
