"""Authenticated internal endpoints for report electronic issuance."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from ..audit import add_operation_audit
from ..extensions import db
from ..functions.esign_service import (
    COMPLETED_FLOW_STATUSES,
    EsignServiceError,
    EsignV3Client,
    batch_sign_url_for_user,
    dispatch_flow,
    ensure_organization_seal_flow,
    ensure_report_esign_flow,
    flow_has_organization_seal,
    normalize_psn_account,
    positioning_url_for_flow,
    send_initial_sms_notifications,
    sign_url_for_user,
    store_manual_positioning,
    store_signed_file,
    signer_project_access_error,
    verify_callback_signature,
)
from ..models import (
    EsignIdentityBinding,
    Personnel,
    Report,
    ReportEsignFlow,
    ReportEsignSigner,
    User,
)
from ..applications.report_lifecycle import scoped_report_query
from ..security import require_auth
from ..esign_access import manager_report_error, manager_flow_error

bp = Blueprint("esign", __name__, url_prefix="/api/esign")


def _ok(data=None, message="ok"):
    return jsonify({"code": 0, "message": message, "data": data})


def _error(exc: EsignServiceError, status=200):
    return jsonify({"code": exc.code, "message": str(exc), "data": None}), status


def _can_manage_bindings(user: User) -> bool:
    return user.role_key == "admin" or "quality.personnel.update" in user.action_codes()


def _can_manage_flow(user: User) -> bool:
    return user.role_key == "admin" or "report.print.view" in user.permission_codes()


@bp.get("/status")
@require_auth
def integration_status():
    return _ok({
        "enabled": bool(current_app.config.get("ESIGN_ENABLED")),
        "workflowEnabled": bool(current_app.config.get("ESIGN_WORKFLOW_ENABLED")),
        "requiredForIssuance": bool(current_app.config.get("ESIGN_REQUIRED_FOR_ISSUANCE")),
        "providerEnvironment": current_app.config.get("ESIGN_ENVIRONMENT", "disabled"),
        "externalSideEffectsEnabled": bool(current_app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED") or current_app.config.get("ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED")),
        "organizationAutoSealEnabled": bool(current_app.config.get("ESIGN_ORG_AUTOSIGN_ENABLED")),
        "organizationSealMode": "assigned" if str(current_app.config.get("ESIGN_ORG_SEAL_ID") or "").strip() else "default",
    })


@bp.get("/me")
@require_auth
def my_binding():
    row = EsignIdentityBinding.query.filter_by(user_id=g.current_user.id).first()
    return _ok(row.to_dict() if row else {
        "userId": g.current_user.id,
        "account": g.current_user.account,
        "userName": g.current_user.name,
        "status": "unbound",
    })


@bp.get("/tasks")
@require_auth
def my_tasks():
    rows = (
        db.session.query(ReportEsignFlow, ReportEsignSigner)
        .join(ReportEsignSigner, ReportEsignSigner.flow_id == ReportEsignFlow.id)
        .filter(ReportEsignSigner.user_id == g.current_user.id)
        .order_by(ReportEsignFlow.created_at.desc())
        .limit(200).all()
    )
    rows = [
        (flow, signer)
        for flow, signer in rows
        if not signer_project_access_error(g.current_user, flow, signer)
    ]
    from ..esign_access import signer_access_error
    return _ok({"rows": [{**flow.to_dict(), "myRole": signer.role_name, "myStatus": signer.status,
        'canSign': not signer_access_error(g.current_user, flow, signer, actionable=True)} for flow, signer in rows]})


@bp.post("/tasks/<int:flow_id>/sign-url")
@require_auth
def task_sign_url(flow_id):
    flow = db.session.get(ReportEsignFlow, flow_id)
    if not flow:
        return _error(EsignServiceError("flow_not_found", "电子签发任务不存在"), 404)
    try:
        return _ok(sign_url_for_user(flow, g.current_user))
    except EsignServiceError as exc:
        return _error(exc)


@bp.get('/tasks/stage-pending')
@require_auth
def pending_stages():
    from ..functions.esign_stages import staged_mode_filter, access_error
    rows = (db.session.query(ReportEsignFlow, ReportEsignSigner)
        .join(ReportEsignSigner, ReportEsignSigner.flow_id == ReportEsignFlow.id)
        .filter(ReportEsignSigner.user_id == g.current_user.id, ReportEsignSigner.status.in_(['pending', 'signing']),
                ReportEsignFlow.status.in_(['ready', 'failed', 'signing']), staged_mode_filter())
        .order_by(ReportEsignFlow.id.desc()).all())
    return _ok({'rows': [dict(id=flow.id, reportNo=flow.report_no, myRole=signer.role_name,
        providerFlowId=flow.provider_flow_id, errorMessage=flow.error_message)
        for flow, signer in rows if not signer_project_access_error(g.current_user, flow, signer)
        and not access_error(g.current_user, flow, signer)]})


@bp.post("/tasks/batch-sign-url")
@require_auth
def task_batch_sign_url():
    raw_ids = (request.get_json(silent=True) or {}).get("flowIds") or []
    try:
        ids = [int(value) for value in raw_ids][:1000]
        return _ok(batch_sign_url_for_user(g.current_user, ids or None))
    except (TypeError, ValueError):
        return _error(EsignServiceError("invalid_flow_ids", "签署任务编号格式错误"))
    except EsignServiceError as exc:
        return _error(exc)


@bp.post('/tasks/<int:flow_id>/resume-stage')
@require_auth
def resume_stage_task(flow_id):
    from ..functions.esign_stages import is_staged, response, access_error
    from ..esign_access import signer_access_error
    flow = db.session.get(ReportEsignFlow, flow_id)
    if not is_staged(flow):
        return _error(EsignServiceError('stage_missing', '分节点签署任务不存在'), 404)
    mine = next((s for s in flow.signers if s.user_id == g.current_user.id and s.status != 'signed'), None)
    if not mine or signer_access_error(g.current_user, flow, mine) or access_error(g.current_user, flow, mine):
        return _error(EsignServiceError('forbidden', '没有本节点已确认的本人签署任务'), 403)
    return _ok(response(flow, g.current_user))


@bp.post('/tasks/<int:flow_id>/refresh')
@require_auth
def refresh_my_task(flow_id):
    from ..esign_access import signer_access_error
    from ..functions.esign_unified import refresh
    flow = db.session.get(ReportEsignFlow, flow_id)
    if not flow or not any(s.user_id == g.current_user.id and not signer_access_error(g.current_user, flow, s)
                           for s in flow.signers):
        return _error(EsignServiceError('forbidden', '没有该报告的本人签署任务'), 403)
    try:
        return _ok(refresh(flow.id).to_dict())
    except EsignServiceError as exc:
        db.session.rollback()
        return _error(exc, 409)


@bp.get("/reports/<path:report_no>")
@require_auth
def report_flow(report_no):
    report = scoped_report_query(Report.query, g.current_user).filter_by(report_no=report_no).first()
    if not report:
        return _error(EsignServiceError("report_not_found", "报告不存在或无权查看"))
    query = ReportEsignFlow.query.filter_by(report_id=report.id)
    version_id = report.approved_document_version_id or report.current_document_version_id
    if not version_id and (report.detail or {}).get("internalCorrectionRevision"):
        return _ok(None)
    if version_id:
        query = query.filter_by(report_document_version_id=version_id)
    row = query.order_by(ReportEsignFlow.attempt_no.desc(), ReportEsignFlow.id.desc()).first()
    if not row:
        return _ok(None)
    from ..esign_seal_confirmation import access_error
    data = row.to_dict()
    data["canConfirmSeal"] = not access_error(g.current_user, report)
    data['canDownloadSealed'] = False  # signing is not a signed-file download entry
    from ..functions.esign_cancellation import cancellation_error
    data['canCancel'] = not cancellation_error(g.current_user, row) and bool(
        row.provider_flow_id or row.status == 'cancelling' or data.get('flowKind') == 'organization_seal'
        or any(s.status == 'signed' for s in row.signers))
    return _ok(data)


@bp.post('/flows/<int:flow_id>/cancel')
@require_auth
def cancel_report_flow(flow_id):
    from ..functions.esign_cancellation import cancel_actor_error, cancel_and_restart
    actor_error = cancel_actor_error(g.current_user, db.session.get(ReportEsignFlow, flow_id))
    if actor_error:
        return _error(EsignServiceError('forbidden', actor_error), 403)
    body = request.get_json(silent=True) or {}
    if body.get('confirmed') is not True:
        return _error(EsignServiceError('confirmation_required', '请确认撤销当前签署轮次'), 400)
    try:
        flow = cancel_and_restart(flow_id, g.current_user, body.get('reason'))
        from ..functions.esign_stages import is_staged
        return _ok(flow.to_dict(), '旧流程已撤回，请重新完成检测并逐节点确认签署' if is_staged(flow) else '旧流程已撤销，已建立全员待签的新任务')
    except EsignServiceError as exc:
        db.session.rollback()
        return _error(exc, 409)


@bp.post("/reports/<path:report_no>/prepare")
@require_auth
def prepare_report_flow(report_no):
    report = scoped_report_query(Report.query, g.current_user).filter_by(report_no=report_no).first()
    if not report or not _can_manage_flow(g.current_user):
        return _error(EsignServiceError("forbidden", "无报告签发任务管理权限"), 403)
    error = manager_report_error(g.current_user, report)
    if error:
        return _error(EsignServiceError("forbidden", error), 403)
    try:
        return _ok(ensure_report_esign_flow(report_no, g.current_user).to_dict(), "签发任务已准备")
    except EsignServiceError as exc:
        return _error(exc)


@bp.post("/reports/<path:report_no>/organization-seal")
@require_auth
def organization_seal_report(report_no):
    report = scoped_report_query(Report.query, g.current_user).filter_by(report_no=report_no).first()
    from ..esign_seal_confirmation import access_error
    error = access_error(g.current_user, report)
    if error:
        return _error(EsignServiceError("forbidden", error), 403)
    try:
        body = request.get_json(silent=True) or {}
        if body.get("confirmed") is not True or type(body.get("sourceFlowId")) is not int:
            return _error(EsignServiceError("seal_confirmation_required", "请明确确认当前签署文件"), 400)
        from ..functions.esign_unified import is_unified, confirm
        source = db.session.get(ReportEsignFlow, body["sourceFlowId"])
        if is_unified(source):
            return _ok(confirm(source.id, g.current_user, body.get("sourceSha256"), report_no).to_dict())
        flow = ensure_organization_seal_flow(report_no, g.current_user,
            source_flow_id=body.get("sourceFlowId"), source_sha256=body.get("sourceSha256"))
        if flow.status in {"ready", "failed"}:
            flow = dispatch_flow(flow.id, g.current_user)
        return _ok(flow.to_dict(), "签章确认已记录，盖章流程已发起")
    except EsignServiceError as exc:
        return _error(exc)


@bp.post("/flows/<int:flow_id>/refresh")
@require_auth
def refresh_report_flow(flow_id):
    from ..functions.esign_unified import refresh
    from ..esign_seal_confirmation import access_error
    flow = db.session.get(ReportEsignFlow, flow_id)
    if not flow or (manager_flow_error(g.current_user, flow) and access_error(g.current_user, flow.report)):
        return _error(EsignServiceError('forbidden', '无权刷新该签署流程'), 403)
    try:
        return _ok(refresh(flow_id).to_dict())
    except EsignServiceError as exc:
        db.session.rollback()
        return _error(exc, 409)


@bp.post("/flows/<int:flow_id>/dispatch")
@require_auth
def dispatch_report_flow(flow_id):
    target_flow = db.session.get(ReportEsignFlow, flow_id)
    from ..esign_seal_confirmation import access_error
    error = (access_error(g.current_user, target_flow.report) if target_flow and target_flow.to_dict().get("flowKind") == "organization_seal"
             else manager_flow_error(g.current_user, target_flow))
    if error:
        return _error(EsignServiceError("forbidden", error), 403)
    try:
        return _ok(dispatch_flow(flow_id, g.current_user).to_dict(), "电子签署流程已发起")
    except EsignServiceError as exc:
        return _error(exc)


@bp.get("/flows/<int:flow_id>/signed-pdf")
@require_auth
def signed_report_pdf(flow_id):
    return _error(EsignServiceError('download_entry_retired',
        '签章下载已移至报告签发、报告查询和报告发放，请使用对应页面下载签字盖章版'), 410)


@bp.post("/flows/<int:flow_id>/positioning-url")
@require_auth
def positioning_url(flow_id):
    if not _can_manage_flow(g.current_user):
        return _error(EsignServiceError("forbidden", "无报告签发任务管理权限"), 403)
    error = manager_flow_error(g.current_user, db.session.get(ReportEsignFlow, flow_id))
    if error:
        return _error(EsignServiceError("forbidden", error), 403)
    try:
        return _ok(positioning_url_for_flow(flow_id, g.current_user), "已获取人工拖章校准页面")
    except EsignServiceError as exc:
        return _error(exc)


@bp.get("/admin/bindings")
@require_auth
def binding_list():
    if not _can_manage_bindings(g.current_user):
        return _error(EsignServiceError("forbidden", "无人员电子签署绑定维护权限"), 403)
    keyword = str(request.args.get("keyword") or "").strip()
    query = EsignIdentityBinding.query.join(User, User.id == EsignIdentityBinding.user_id)
    if keyword:
        query = query.filter(db.or_(User.account.like(f"%{keyword}%"), User.name.like(f"%{keyword}%")))
    rows = query.order_by(User.account).limit(500).all()
    return _ok({"rows": [row.to_dict() for row in rows]})


@bp.get("/admin/bindings/<int:user_id>")
@require_auth
def binding_detail(user_id):
    if not _can_manage_bindings(g.current_user):
        return _error(EsignServiceError("forbidden", "无人员电子签署绑定维护权限"), 403)
    user = db.session.get(User, user_id)
    if not user:
        return _error(EsignServiceError("user_not_found", "人员账号不存在"))
    row = EsignIdentityBinding.query.filter_by(user_id=user_id).first()
    return _ok(row.to_dict() if row else {
        "userId": user.id, "account": user.account, "userName": user.name,
        "legalName": user.name, "psnAccountMasked": "", "psnId": "", "status": "unbound",
    })


@bp.put("/admin/bindings/<int:user_id>")
@require_auth
def binding_update(user_id):
    from .report_assurance import legacy_binding_update
    return legacy_binding_update(user_id)


@bp.post("/callback")
def callback():
    raw = request.get_data(cache=True)
    query_values = [value for key, value in sorted(request.args.items())]
    # Every callback action, including GET_SEAL_POSITION, must pass the same
    # AppId/timestamp/HMAC verification before any flow or coordinate is read.
    if not verify_callback_signature(raw, request.headers, query_values):
        return jsonify({"code": 401, "message": "invalid callback signature"}), 401
    body = request.get_json(silent=True) or {}
    action = str(body.get("action") or "")
    provider_id = str(body.get("signFlowId") or body.get("flowId") or "")
    previous = ReportEsignFlow.query.filter_by(provider_flow_id=provider_id).first() if provider_id else None
    if previous and previous.id < int(current_app.config.get("ESIGN_PROVIDER_FLOW_MIN_ID") or 0):
        return jsonify({"code": 0, "message": "historical flow ignored"})
    if action == "GET_SEAL_POSITION":
        flow = store_manual_positioning(body)
        return jsonify({"code": 0, "message": "success" if flow else "ignored"})
    provider_flow_id = str(body.get("signFlowId") or body.get("flowId") or "")
    flow = ReportEsignFlow.query.filter_by(provider_flow_id=provider_flow_id).first()
    if not flow:
        return jsonify({"code": 0, "message": "ignored"})
    Report.query.filter_by(id=flow.report_id).with_for_update().populate_existing().one()
    flow = ReportEsignFlow.query.filter_by(id=flow.id).with_for_update().populate_existing().one()
    from ..internal_report_corrections import is_historical_flow
    if is_historical_flow(flow) or flow.status in {'cancelled', 'cancelling'}:
        add_operation_audit('report.esign.callback.retired', 'report', flow.report_no, category='integration',
            after={'flowId': flow.id, 'action': action, 'status': flow.status,
                'providerStatus': body.get('signFlowStatus') or body.get('flowStatus'),
                'signOrder': body.get('signOrder') or body.get('order'), 'signResult': body.get('signResult')},
            message='已撤销或正在撤销的历史流程回调已留存，不恢复当前签署轮次')
        db.session.commit()
        return jsonify({'code': 0, 'message': 'retired flow recorded'})
    from ..functions.esign_unified import is_unified, refresh
    if is_unified(flow):
        try:
            refresh(flow.id)
            add_operation_audit('report.esign.callback', 'report', flow.report_no, category='integration',
                after={'flowId': flow.id, 'action': action, 'status': flow.status})
            db.session.commit()
        except EsignServiceError as exc:
            db.session.rollback()
            return _error(exc, 503)
        if action in {"SIGN_MISSON_COMPLETE", "SIGN_MISSION_COMPLETE"}:
            try:
                send_initial_sms_notifications(flow.id, retry_failed=True)
            except Exception:
                current_app.logger.exception('unified flow next-signer notification failed')
        return jsonify({'code': 0, 'message': 'success'})
    signer = None
    if action in {"SIGN_MISSON_COMPLETE", "SIGN_MISSION_COMPLETE"}:
        order = body.get("signOrder") or body.get("order")
        signer = ReportEsignSigner.query.filter_by(flow_id=flow.id, sign_order=int(order)).first() if str(order).isdigit() else None
        if signer:
            signer.status = "signed" if int(body.get("signResult") or 2) == 2 else "failed"
            signer.signed_at = datetime.utcnow() if signer.status == "signed" else None
    if action in {"SIGN_FLOW_COMPLETE", "SIGN_FLOW_FINISH"}:
        provider_status = str(body.get("signFlowStatus") or body.get("flowStatus") or "2")
        if provider_status == "2":
            # Provider callbacks can be retried.  Do not create another stored
            # file after the signed PDF has already been persisted.
            if not flow.signed_file_id:
                signed_pdf = EsignV3Client().download_signed_pdf(flow.provider_flow_id)
                store_signed_file(flow, signed_pdf)
            else:
                flow.status = "completed"
                from ..report_delivery import mark_sealed
                mark_sealed(flow.report, flow)
        else:
            terminal = {
                "3": ("cancelled", "provider_cancelled", "e签宝签署流程已撤销"),
                "5": ("expired", "provider_expired", "e签宝签署流程已过期"),
                "7": ("rejected", "provider_rejected", "签署人已拒签"),
            }.get(provider_status, ("failed", "provider_failed", "e签宝签署流程异常结束"))
            flow.status, flow.error_code, default_message = terminal
            flow.error_message = str(body.get("statusDescription") or default_message)[:500]
            for signer in flow.signers:
                if signer.status != "signed":
                    signer.status = "failed"
                    signer.error_message = flow.error_message[:300]
    add_operation_audit(
        "report.esign.callback", "report", flow.report_no, category="integration",
        after={"flowId": flow.id, "action": action, "status": flow.status},
        message="e签宝签署回调已接收",
    )
    db.session.commit()
    if (
        action in {"SIGN_FLOW_COMPLETE", "SIGN_FLOW_FINISH"}
        and flow.status in COMPLETED_FLOW_STATUSES
        and current_app.config.get("ESIGN_ORG_AUTOSIGN_ENABLED")
        and bool(flow.signers)
        and not flow_has_organization_seal(flow)
    ):
        # Flows already in progress when organization auto-seal is enabled do
        # not contain the fourth signer. Continue them from the immutable
        # three-person signed PDF without asking those people to sign again.
        try:
            organization_flow = ensure_organization_seal_flow(flow.report_no)
            if organization_flow.status in {"ready", "failed"}:
                dispatch_flow(organization_flow.id)
        except Exception:
            # The personal-signature callback has already been durably saved.
            # Keep returning success so eSign does not retry that callback;
            # the failed/ready supplement remains visible for safe retry.
            current_app.logger.exception(
                "failed to continue organization auto-seal flow report_no=%s source_flow_id=%s",
                flow.report_no,
                flow.id,
            )
    if action in {"SIGN_MISSON_COMPLETE", "SIGN_MISSION_COMPLETE"} and signer and signer.status == "signed":
        # A batch link only contains tasks actionable when the link is created.
        # Notify the newly-unlocked next signer after persisting this callback.
        # SMS failure must not turn a completed signature into a failed callback.
        try:
            send_initial_sms_notifications(flow.id, retry_failed=True)
        except Exception:
            current_app.logger.exception(
                "failed to notify next sequential eSign signer flow_id=%s order=%s",
                flow.id,
                signer.sign_order,
            )
    return jsonify({"code": 0, "message": "success"})
