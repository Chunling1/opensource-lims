"""Business-stage gates for one immutable eSign document and provider flow.

Only an explicit business decision adds a signer. Provider refresh may advance
the business node, but must never authorize the next person to sign.
"""
import json
import threading
try:
    import fcntl
except ImportError:
    fcntl = None
_win_locks = {}
_win_locks_guard = threading.Lock()
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from flask import current_app
from sqlalchemy import JSON, type_coerce
from ..extensions import db
from ..models import Report, ReportEsignFlow, ReportEsignSigner, EsignIdentityBinding, User, OperationAudit
from ..audit import add_operation_audit
from . import esign_service as service

MODE = 'business_stages_v1'
STAGES = {
    'chief': ('检测录入中', '待审核', 'report.data_entry.complete', '主检'),
    'reviewer': ('待审核', '待批准', 'report.review.pass', '审核'),
    'approver': ('待批准', '待打印', 'report.approval.pass', '批准'),
}


def enabled():
    return bool(current_app.config.get('ESIGN_STAGE_WORKFLOW_ENABLED'))


@contextmanager
def provider_turn(flow_id):
    """Serialize this round's provider operations across workers, without a report row lock."""
    directory = Path(current_app.config['STORAGE_ROOT']) / 'esign-round-locks'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / str(flow_id)).open('ab') as handle:
        if fcntl is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise service.EsignServiceError('stage_busy', '本轮签署操作正在处理，请稍后核对状态') from None
            yield
        else:
            with _win_locks_guard:
                lock = _win_locks.setdefault(str(flow_id), threading.Lock())
            if not lock.acquire(blocking=False):
                raise service.EsignServiceError('stage_busy', '本轮签署操作正在处理，请稍后核对状态')
            try:
                yield
            finally:
                lock.release()


def workflow_choice(report, *, lock=False):
    query = OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        action='report.esign.workflow.select', success=True).order_by(OperationAudit.id.desc())
    event = (query.with_for_update() if lock else query).first()
    return event.after_data['mode'] if event else None


def selected(report):
    return workflow_choice(report) == MODE


def staged_mode_filter():
    # positioning_json is TEXT; old rows may be NULL or malformed.
    safe_json = db.case((db.func.json_valid(ReportEsignFlow.positioning_json) == 1,
                         ReportEsignFlow.positioning_json), else_='{}')
    return type_coerce(safe_json, JSON)[('businessStages', 'mode')].as_string() == MODE


def prompt_available():
    return enabled() or db.session.query(ReportEsignFlow.id).filter(
        ReportEsignFlow.status.in_(['ready', 'dispatching', 'signing', 'failed']), staged_mode_filter()).first() is not None


def eligibility_error(report):
    from ..platform.identity import project_for_report
    from ..project_workflow import skipped_steps_for_project
    project = project_for_report(report)
    if project and skipped_steps_for_project(project):
        return '首批新流程不支持跳步项目，请使用原流程'
    if service._reference_present(service._second_chief_reference(report, None)):
        return '首批新流程不支持双主检，请使用原流程'
    plan = (report.detail or {}).get('returnPlan') or {}
    if report.status in {'待校核', '退回待重传'} or plan.get('afterDataChange') in {'data_check', 'report_check'}:
        return '首批新流程不支持校核，请使用原流程'
    if OperationAudit.query.filter_by(object_type='report', object_id=report.report_no, success=True).filter(
            OperationAudit.action.in_(['report.report_check.pass', 'testing.data_check.pass'])).first():
        return '该报告包含校核历史，首批请继续使用原流程'
    return ''


def choose_at_completion(report, actor, mode):
    """Use the first completion to set the report's mode under its existing row lock."""
    if mode is not None and (not isinstance(mode, str) or mode not in {'legacy', MODE}):
        raise service.EsignServiceError('invalid_mode', '未知签署流程')
    fixed = workflow_choice(report, lock=True)
    entry_enabled = enabled()
    if not fixed and (entry_enabled or mode is not None):
        previous = latest_flow(report, lock=True)
        completed = OperationAudit.query.filter_by(object_type='report', object_id=report.report_no, success=True).filter(
            OperationAudit.action.in_(['report.data_entry.complete', 'report.test_change.complete', 'report.data_change.complete',
                                     'report.review.pass', 'report.approval.pass'])).with_for_update().first()
        if previous or completed:
            fixed = MODE if is_staged(previous) else 'legacy'
    if fixed:
        if mode is not None and mode != fixed:
            raise service.EsignServiceError('mode_locked', '该报告已确定签署流程，退回或撤回后仍沿用原选择')
        return fixed
    reason = eligibility_error(report) if entry_enabled else '新流程试用入口尚未开放'
    if reason:
        if mode == MODE:
            raise service.EsignServiceError('stage_unavailable', reason)
        return 'legacy'
    if mode is None:
        return None
    add_operation_audit('report.esign.workflow.select', 'report', report.report_no, actor=actor,
        category='workflow', after={'mode': mode})
    return mode


def is_staged(flow):
    return bool(flow and service._positioning_snapshot(flow).get('businessStages', {}).get('mode') == MODE)


def latest_flow(report, *, lock=False):
    query = ReportEsignFlow.query.filter_by(report_id=report.id).order_by(ReportEsignFlow.id.desc())
    return (query.with_for_update().populate_existing() if lock else query).first()


def current_flow(report, *, lock=False):
    flow = latest_flow(report, lock=lock)
    return flow if is_staged(flow) and not service._positioning_snapshot(flow).get('cancellation', {}).get('completedAt') else None


def cancel_round(flow_id, actor, reason, *, return_action=None, return_mode=""):
    """Stop the provider first, then unlock data and require all decisions anew."""
    with provider_turn(flow_id):
        return _cancel_round(flow_id, actor, reason, return_action, return_mode)


def _cancel_round(flow_id, actor, reason, return_action, return_mode):
    from .esign_unified import _lock
    from .esign_cancellation import _stop_provider
    from ..esign_access import report_scope_error
    flow = _lock(flow_id)
    if not return_action:
        from .esign_cancellation import cancel_actor_error
        error = cancel_actor_error(actor, flow) or report_scope_error(actor, flow.report)
        if error:
            raise service.EsignServiceError('forbidden', error)
    if service._positioning_snapshot(flow).get('cancellation', {}).get('completedAt'):
        return flow
    latest = ReportEsignFlow.query.filter_by(report_id=flow.report_id).order_by(ReportEsignFlow.id.desc()).first()
    if latest.id != flow.id:
        raise service.EsignServiceError('stale_round', '当前已有新签署轮次，请刷新')
    if flow.report.current_document_version_id != flow.report_document_version_id:
        raise service.EsignServiceError('cancel_denied', '签署版本已变化，请核查')
    if not is_staged(flow) or flow.report.stamped or flow.status in {'completed', 'verified'}:
        raise service.EsignServiceError('cancel_denied', '已盖章完结的报告请办理更正')
    reason = str(reason or '').strip()
    if not reason or len(reason) > 50:
        raise service.EsignServiceError('reason_required', '请填写1至50字撤回原因')
    from .esign_dispatch_state import definitely_uncreated
    if flow.status == 'dispatching' or (not flow.provider_flow_id and not definitely_uncreated(flow)):
        raise service.EsignServiceError('outcome_unknown', '发起结果待核实，不能解锁或重建')
    snapshot = service._positioning_snapshot(flow)
    if snapshot.get('organizationSeal', {}).get('appendRequestedAt'):
        raise service.EsignServiceError('seal_pending', '已提交组织盖章，请核实盖章结果后办理更正')
    snapshot['businessStages'].setdefault('returnSourceStatus', flow.report.status)
    snapshot.setdefault('cancellation', {'reason': reason, 'previousStatus': flow.status, 'actorId': actor.id,
        'returnAction': return_action, 'returnMode': return_mode})
    cancellation = snapshot['cancellation']
    flow.positioning_json = json.dumps(snapshot, ensure_ascii=False)
    flow.status = 'cancelling'
    db.session.commit()
    proof = _stop_provider(flow, cancellation['reason'])
    db.session.rollback()  # end the read snapshot taken by _stop_provider
    flow = _lock(flow_id)
    snapshot = service._positioning_snapshot(flow)
    cancellation = snapshot['cancellation']
    if cancellation.get('completedAt'):
        return flow
    if flow.status != 'cancelling' or flow.report.stamped or current_flow(flow.report) != flow or flow.report.current_document_version_id != flow.report_document_version_id:
        raise service.EsignServiceError('stage_changed', '撤销期间轮次或版本已变化，未重置报告')
    flow.status = 'cancelled'
    snapshot['cancellation'].update(proof, completedAt=datetime.utcnow().isoformat())
    flow.positioning_json = json.dumps(snapshot, ensure_ascii=False)
    flow.report.status = '检测录入中'
    flow.report.approved_document_version_id = None
    detail = dict(flow.report.detail or {})
    detail['signatures'] = {k: v for k, v in (detail.get('signatures') or {}).items() if k not in {'审核', '批准'}}
    flow.report.detail = detail
    if (cancellation.get('returnAction') or '').endswith('.return'):
        from ..applications.report_lifecycle.commands import apply_return_plan
        flow.report.status = state(flow)['returnSourceStatus']
        apply_return_plan(flow.report, actor, cancellation['returnAction'], cancellation['reason'], cancellation['returnMode'])
        detail = dict(flow.report.detail)
        detail['returnPlan'] = {**detail['returnPlan'], 'afterDataChange': 'review'}
        if detail['returnPlan'].get('afterContractReview') == 'review':
            detail['returnPlan'].update(afterContractReview='data_change',
                targetLabel='委托更改 → 合同评审 → 检测更改并重新主检签署 → 审核')
        flow.report.detail = detail
    if cancellation.get('returnAction'):
        add_operation_audit(cancellation['returnAction'], 'report', flow.report_no, actor=actor,
            category='workflow', after=flow.report.to_row(), message=cancellation['reason'])
    add_operation_audit('report.esign.stage.cancel', 'report', flow.report_no,
        category='workflow', actor=actor, after={'flowId': flow.id, **proof},
        message='已停止整轮电子签署，保留签名历史和检测数据；重新完成检测后各节点需重新确认签署')
    db.session.commit()
    return flow


def state(flow):
    return service._positioning_snapshot(flow).get('businessStages') or {}


def save_state(flow, value):
    snapshot = service._positioning_snapshot(flow)
    snapshot['businessStages'] = value
    flow.positioning_json = json.dumps(snapshot, ensure_ascii=False)


def content_blocker(report):
    if current_flow(report):
        return '当前报告已锁定电子签署文件；请先撤回本轮签署，再修改并重新确认完整报告'
    return ''


def access_error(user, flow, signer):
    if not is_staged(flow):
        return ''
    value = state(flow)
    role = signer.role_code
    decision = (value.get('decisions') or {}).get(role)
    if not decision or signer.role_code not in decision.get('roles', []):
        return '本系统尚未完成对应业务节点，不能开放签署'
    if flow.report.current_document_version_id != flow.report_document_version_id:
        return '签署文件已被其他版本替代'
    if signer.status != 'signed' and flow.report.status != decision.get('sourceStatus', STAGES[role][0]):
        return '报告当前节点与签署任务不一致'
    return ''


def all_stages_signed(flow):
    if not is_staged(flow):
        return True
    value = state(flow)
    return all((value.get('decisions') or {}).get(role, {}).get('completedAt')
               for role in ('chief', 'reviewer', 'approver'))


def _add_signer(flow, user, role, order):
    binding = EsignIdentityBinding.query.filter_by(user_id=user.id).first()
    if not binding or binding.status not in {'pending', 'verified'}:
        raise service.EsignServiceError('binding_required', f'{user.name}尚未绑定有效e签宝身份')
    row = ReportEsignSigner(user_id=user.id, role_code=role,
        role_name=STAGES[role][3],
        legal_name_snapshot=binding.legal_name, binding_id=binding.id,
        psn_id_snapshot=binding.psn_id, sign_order=order, status='pending')
    flow.signers.append(row)
    return row


def begin(report, version, actor, *, mode=None):
    """Prepare only the chief stage; caller owns commit and provider dispatch."""
    prior = current_flow(report, lock=True)
    if prior:
        error = service.flow_state_error(prior)
        if error:
            raise service.EsignServiceError('stage_invalid', error)
        return prior
    if (mode if mode is not None else workflow_choice(report)) != MODE:
        raise service.EsignServiceError('stage_not_selected', '该报告仍使用原流程')
    error = eligibility_error(report)
    if error:
        raise service.EsignServiceError('stage_unsupported', error)
    latest = latest_flow(report, lock=True)
    if latest and latest.status not in {'cancelled', 'expired', 'rejected'}:
        raise service.EsignServiceError('existing_round', '已有签署轮次，不能切换流程')
    if report.status not in {STAGES['chief'][0], '检测更改中'} or version.id != report.current_document_version_id:
        raise service.EsignServiceError('stage_invalid', '只有当前完整报告在主检完成时可以建立分节点签署')
    chief = service.resolve_report_signers(report, version)[0].get('chief')
    if not chief:
        raise service.EsignServiceError('chief_missing', '未明确主检人员')
    attempt = (db.session.query(db.func.max(ReportEsignFlow.attempt_no)).filter_by(
        report_id=report.id, report_document_version_id=version.id).scalar() or 0) + 1
    from .esign_unified import MODE as UNIFIED
    flow = ReportEsignFlow(report_id=report.id, report_no=report.report_no,
        report_document_version_id=version.id, source_sha256=version.sha256,
        attempt_no=attempt, status='ready', created_by_id=actor.id,
        positioning_json=json.dumps({'signingMode': UNIFIED, 'flowKind': 'person_signing',
            'organizationSeal': {'included': False, 'status': 'awaiting_personal_signatures', 'confirmationRequired': True}}))
    db.session.add(flow)
    _add_signer(flow, chief, 'chief', 1)
    save_state(flow, {'mode': MODE, 'datePolicy': 'provider_approval_date',
        'decisions': {'chief': {'actorId': actor.id, 'confirmedAt': datetime.utcnow().isoformat(), 'roles': ['chief'], 'sourceStatus': report.status}}})
    db.session.flush()
    service._flow_source_pdf(flow)
    add_operation_audit('report.esign.stage.chief.confirm', 'report', report.report_no,
        category='workflow', actor=actor, after={'flowId': flow.id, 'versionId': version.id})
    return flow


def response(flow, actor=None):
    """Business confirmation is durable even if provider dispatch is unavailable."""
    error = ''
    try:
        if flow.provider_flow_id:
            append_confirmed(flow.id)
        if not flow.provider_flow_id:
            service.dispatch_flow(flow.id, actor)
    except (service.EsignServiceError, OSError, ValueError) as exc:
        db.session.rollback()
        error = str(exc)[:300]
    return {'reportNo': flow.report_no, 'status': flow.report.status,
            'esignFlow': flow.to_dict(), 'esignPending': True, 'esignPrepareError': error,
            'message': '本节点已确认，请由本人完成电子签署后流转' + (f'；签署准备未完成：{error}' if error else '')}


def confirm_stage(report, actor, role):
    """Called after normal authorization, version and compliance validation."""
    flow = current_flow(report)
    if not flow or role not in {'reviewer', 'approver'}:
        raise service.EsignServiceError('stage_missing', '当前分节点签署流程不存在')
    error = service.flow_state_error(flow)
    if error:
        raise service.EsignServiceError('stage_invalid', error)
    value = state(flow)
    previous = 'chief' if role == 'reviewer' else 'reviewer'
    if report.status != STAGES[role][0] or not value['decisions'].get(previous, {}).get('completedAt'):
        raise service.EsignServiceError('stage_not_ready', '前一节点尚未签完，不能确认当前节点')
    if value['decisions'].get(role):
        decision = value['decisions'][role]
        if decision['actorId'] != actor.id:
            raise service.EsignServiceError('stage_actor_changed', '当前节点已由其他人员确认，不能替换签署人')
        return flow
    service._flow_source_pdf(flow)
    row = _add_signer(flow, actor, role, max(s.sign_order for s in flow.signers) + 1)
    value['decisions'][role] = {'actorId': actor.id, 'confirmedAt': datetime.utcnow().isoformat(), 'roles': [role]}
    save_state(flow, value)
    add_operation_audit(f'report.esign.stage.{role}.confirm', 'report', report.report_no,
        category='workflow', actor=actor, after={'flowId': flow.id, 'role': row.role_code})
    return flow


def append_confirmed(flow_id):
    with provider_turn(flow_id):
        return _append_confirmed(flow_id)


def _append_confirmed(flow_id):
    """Reconcile first; persist intent before POST, never blindly retry append."""
    from .esign_unified import _lock, _client, sync_provider_detail
    flow = _lock(flow_id)
    error = service.flow_state_error(flow)
    if error or not is_staged(flow) or flow.status != 'signing':
        raise service.EsignServiceError('stage_invalid', error or '当前流程不能追加签署人')
    client = _client()
    sync_provider_detail(flow, client)
    flow = _lock(flow_id)
    value = state(flow)
    snapshot = service._positioning_snapshot(flow)
    for role in ('reviewer', 'approver'):
        decision = value['decisions'].get(role)
        if not decision or decision.get('providerIncluded') or decision.get('completedAt'):
            continue
        if decision.get('appendRequestedAt'):
            raise service.EsignServiceError('append_pending', '追加结果待核实；请刷新。若上游确认未受理，请管理员核实本次请求后解锁重试')
        if flow.report.status != decision.get('sourceStatus', STAGES[role][0]):
            raise service.EsignServiceError('stage_changed', '报告节点已变化，不能追加')
        row = next(s for s in flow.signers if s.role_code == role)
        error = access_error(row.user, flow, row)
        if error:
            raise service.EsignServiceError('stage_invalid', error)
        service._flow_source_pdf(flow)
        binding = row.binding
        if not binding or binding.status not in {'pending', 'verified'}:
            raise service.EsignServiceError('binding_required', '签署身份已停用')
        person = {'psnId': binding.psn_id} if binding.psn_id else {'psnAccount': binding.psn_account, 'psnInfo': {'psnName': binding.legal_name}}
        payload = {'signers': [{'signerType': 0, 'psnSignerInfo': person,
            'signConfig': {'signOrder': row.sign_order, 'agreeSkipWillingness': bool(current_app.config.get('ESIGN_AGREE_SKIP_WILLINGNESS'))},
            'noticeConfig': {'noticeTypes': ''},
            'signFields': [service._sign_field(flow.provider_file_id, flow.report_no, row,
                snapshot['positions'][role], (snapshot.get('fieldSizes') or {}).get(role, 72))]}]}
        if role == 'approver':
            payload['signers'][0]['signFields'].append(date_field(flow, snapshot['businessStages']['datePosition']))
        decision['appendRequestedAt'] = datetime.utcnow().isoformat()
        save_state(flow, value)
        provider_id = flow.provider_flow_id
        db.session.commit()
        try:
            client.request('POST', f'/v3/sign-flow/{provider_id}/signers/sign-fields', payload)
        except service.EsignServiceError as exc:
            if exc.details.get('notSent'):
                flow = _lock(flow_id)
                value = state(flow)
                value['decisions'][role].pop('appendRequestedAt')
                save_state(flow, value)
                db.session.commit()
            raise
        return sync_provider_detail(flow, client)
    return flow


def release_unreceived(flow_id, role, requested_at, evidence):
    """Operator has confirmed non-acceptance with provider; never sends a POST."""
    from .esign_unified import _client, _lock
    with provider_turn(flow_id):
        flow = _lock(flow_id)
        decision = state(flow).get('decisions', {}).get(role, {})
        if (flow.status != 'signing' or service.flow_state_error(flow) or not requested_at
                or decision.get('appendRequestedAt') != requested_at or decision.get('completedAt')):
            raise service.EsignServiceError('stale_request', '轮次、节点或请求时间不匹配')
        provider_id, file_id = flow.provider_flow_id, flow.provider_file_id
        names = {f'{flow.report_no}-{role.upper()}'}
        if role == 'approver':
            names.add(f'{flow.report_no}-APPROVAL-DATE')
        previous = {f'{flow.report_no}-{s.role_code.upper()}' for s in flow.signers if s.role_code != role}
        db.session.commit()
        detail = _client().request('GET', f'/v3/sign-flow/{provider_id}/detail')
        signers = detail.get('signers')
        if (str(detail.get('signFlowStatus')) != '1' or not signers
                or not previous.issubset({f.get('customBizNum') for s in signers for f in s.get('signFields', [])
                                         if f.get('fileId') == file_id and str(f.get('signFieldStatus')) == '4'})
                or any(f.get('customBizNum') in names for s in signers for f in s.get('signFields', []))):
            raise service.EsignServiceError('append_not_absent', '上游详情不能证明本节点字段全部不存在，未解锁')
        flow = _lock(flow_id)
        value = state(flow)
        if service.flow_state_error(flow) or value['decisions'][role].get('appendRequestedAt') != requested_at:
            raise service.EsignServiceError('stale_request', '流程已变化，未解锁')
        del value['decisions'][role]['appendRequestedAt']
        save_state(flow, value)
        add_operation_audit('report.esign.stage.release_unreceived', 'report', flow.report_no,
            category='integration', after={'flowId': flow_id, 'role': role, 'requestedAt': requested_at, 'evidence': evidence})
        db.session.commit()


def reconcile(flow, detail, snapshot):
    """Runs under the report lock, never adds provider signers or approvals."""
    error = service.flow_state_error(flow)
    if error:
        raise service.EsignServiceError('stage_invalid', error)
    if str(detail.get('signFlowStatus')) != '1' and not all_stages_signed(flow):
        raise service.EsignServiceError('stage_provider_closed', '人员节点未全部完成，上游流程已非进行中，未流转')
    service._flow_source_pdf(flow)
    value = snapshot['businessStages']
    fields = {f.get('customBizNum'): f for s in detail.get('signers') or [] if str(s.get('signerType')) == '0'
              for f in s.get('signFields') or [] if f.get('fileId') == flow.provider_file_id}
    expected = {f'{flow.report_no}-{s.role_code.upper()}' for s in flow.signers}
    if 'approver' in value['decisions']:
        expected.add(f'{flow.report_no}-APPROVAL-DATE')
    personal = {f.get('customBizNum') for s in detail.get('signers') or [] if str(s.get('signerType')) == '0'
                for f in s.get('signFields') or []}
    if personal - expected:
        raise service.EsignServiceError('unexpected_signer', '上游存在未获本系统节点确认的签署任务')
    for role, decision in value['decisions'].items():
        names = [f'{flow.report_no}-{r.upper()}' for r in decision['roles']]
        if role == 'approver':
            names.append(f'{flow.report_no}-APPROVAL-DATE')
        decision['providerIncluded'] = all(n in fields for n in names)
        if decision.get('completedAt') or not all(str(fields.get(n, {}).get('signFieldStatus')) == '4' for n in names):
            continue
        previous, target, action, label = STAGES[role]
        if flow.report.status != decision.get('sourceStatus', previous) or flow.report.current_document_version_id != flow.report_document_version_id:
            raise service.EsignServiceError('stage_changed', '签署回执与本系统当前节点或版本不一致，未流转')
        if role == 'chief' and decision['sourceStatus'] == '检测更改中':
            action = 'report.test_change.complete'
        flow.report.status = target
        if role in {'reviewer', 'approver'}:
            detail_data = dict(flow.report.detail or {})
            actor = db.session.get(User, decision['actorId'])
            detail_data['signatures'] = {**(detail_data.get('signatures') or {}), label: (actor.e_signature or actor.name).strip()}
            flow.report.detail = detail_data
        if role == 'approver':
            flow.report.approved_document_version_id = flow.report_document_version_id
            from ..workflow_hooks import capture
            capture(flow.report, 'REPORT_ISSUANCE_STARTED', db.session.get(User, decision['actorId']))
        decision['completedAt'] = datetime.utcnow().isoformat()
        add_operation_audit(action, 'report', flow.report_no, category='workflow',
            actor=db.session.get(User, decision['actorId']),
            after={'flowId': flow.id, 'providerFlowId': flow.provider_flow_id, 'status': target},
            message=f'{label}业务确认及本人电子签署均完成，流转下一节点')
    snapshot['businessStages'] = value


def locate_date(flow, positions):
    from ..pdf_issue_date import locate
    from ..vendor_docparser_20260911.pdf_helper import PdfMaker
    from ..docparser_field_only import profile_for
    profile = (flow.document_version.snapshot.get('template') or {}).get('profile') or profile_for(flow.report)
    maker = PdfMaker(profile['kind'].title(), profile['language'], profile['variant'] == 'Extended')
    page = int(positions['approver']['positionPage'])
    maker._issue_pages = [page - 1, page]
    point = locate(service._flow_source_pdf(flow), maker, profile['language'])
    if point['oldDate']:
        raise service.EsignServiceError('date_not_blank', '报告日期已填写，请使用无日期的完整报告后再开始新流程')
    return {'page': point['page'] + 1, 'x': point['anchor']['x1'] + 2,
        'y': point['height'] - point['anchor']['bottom'],
        'format': 'yyyy-MM-dd' if profile['language'] == 'EN' else 'yyyy年MM月dd日',
        'fontSize': 12 if profile['kind'] == 'calibration' else 11}


def date_field(flow, point):
    return {'fileId': flow.provider_file_id, 'customBizNum': f'{flow.report_no}-APPROVAL-DATE',
        'signFieldType': 2, 'dateSignFieldConfig': {'autoSign': False, 'dateFormat': point['format'],
            'fontSize': point['fontSize'], 'signDatePositionPage': str(point['page']),
            'signDatePositionX': point['x'], 'signDatePositionY': point['y']}}
