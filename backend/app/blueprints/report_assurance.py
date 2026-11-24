"""Read-only artifact resolution and explicitly authorized identity maintenance.

Does not dispatch signing, send SMS, assign permissions, or regenerate documents.
"""
import hashlib
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, current_app, g, jsonify, make_response, request
from ..extensions import db
from ..models import User, Personnel, ReportDocumentVersion, ReportEsignFlow, ReportEsignSigner, EsignIdentityBinding
from ..security import require_auth
from ..audit import add_operation_audit
from ..applications.report_lifecycle import get_authorized_report_for_view
from ..platform.file_vault import read_file_bytes
from ..functions.esign_service import EsignV3Client, EsignServiceError, batch_sign_url_for_user
from .business_supplement import roster_identity

bp = Blueprint('report_assurance', __name__, url_prefix='/api/report-assurance')
COMPLETED = ('completed', 'verified')


def ok(data):
    return jsonify(code=0, message='ok', data=data)


def fail(message, status=409):
    return jsonify(code=status, message=message, data=None), status


def allowed(action):
    return g.current_user.role_key == 'admin' or action in g.current_user.action_codes()


def binding_manager():
    return allowed('quality.personnel.update')


@bp.post('/batch-sign-url')
@require_auth
def batch_entry():
    external = current_app.config.get('EXTERNAL_SIDE_EFFECTS_ENABLED') or current_app.config.get('ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED')
    if (not writable() or not current_app.config.get('ESIGN_ENABLED') or not external
            or current_app.config.get('DEPLOYMENT_ROLE') == 'validation'):
        return fail('平台当前不允许签署', 403)
    body = request.get_json(silent=True)
    ids = body.get('flowIds') if isinstance(body, dict) else None
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(type(i) is not int or i < 1 for i in ids):
        return fail('请明确选择 1–100 份本人待签报告；空列表不会自动选择全部', 400)
    binding = EsignIdentityBinding.query.filter_by(user_id=g.current_user.id).first()
    if not binding or binding.status not in ('pending', 'verified'):
        return fail('请先确认有效的人员绑定')
    try:
        # Existing service checks project scope, current signer order and flow
        # state again; completed flows are excluded. No dispatch or SMS here.
        return ok(batch_sign_url_for_user(g.current_user, list(dict.fromkeys(ids)), notify_sms=False))
    except EsignServiceError:
        return fail('所选报告暂无可签任务或签署入口获取失败；请刷新逐份状态后重试')
    except Exception:
        db.session.rollback()
        return fail('签署服务暂不可用；未重新发起报告签署流程', 502)


def writable():
    return not current_app.config.get('APP_BUSINESS_READ_ONLY', False)


def authorized_report(report_no):
    report, _, error = get_authorized_report_for_view(
        g.current_user, report_no, str(request.args.get('view') or ''))
    return report if not error else None


def resolve_artifact(report, *, metadata_only=False, original=False):
    """Signed bytes win, even if current pointer was subsequently changed.

    A cancelled/failed newer flow must not hide an older signed artifact. A
    completed flow with missing bytes must never fall back to unsigned bytes.
    Explicit original reads use the current locked version before e-signing.
    Historical signed versions remain stored for audit; public file routes are retired.
    """
    from ..internal_report_corrections import is_historical_flow
    signed = next((flow for flow in ReportEsignFlow.query.filter_by(report_id=report.id).filter(
        ReportEsignFlow.status.in_(COMPLETED)).order_by(ReportEsignFlow.id.desc()).all()
        if not is_historical_flow(flow)), None)
    if signed and not original:
        from ..functions.esign_service import flow_has_organization_seal
        sealed = flow_has_organization_seal(signed)
        label = "签字签章完成的 PDF" if sealed else "人员已签字，待签章确认的 PDF"
        if metadata_only:
            return dict(kind='signed', flowId=signed.id, versionId=signed.report_document_version_id,
                        sha256=signed.signed_sha256, label=label, sealed=sealed)
        raw = read_file_bytes(signed.signed_file) if signed.signed_file else None
        if not raw or not signed.signed_sha256 or hashlib.sha256(raw).hexdigest() != signed.signed_sha256:
            raise ValueError('签署文件缺失或完整性校验失败；不会生成替代文件，请核查签署文件归档')
        return dict(kind='signed', flowId=signed.id, versionId=signed.report_document_version_id,
                    sha256=signed.signed_sha256, label=label, sealed=sealed, raw=raw)
    # A legacy signed marker without a managed signing artifact cannot prove
    # which unsigned version was signed; fail closed instead of substituting.
    if report.stamped and not original:
        raise ValueError('报告标记为已签章，但未找到可校验的签署文件；不能以未签署版本代替')
    from ..report_preview_revision import frozen_original
    version_id = ((report.approved_document_version_id or report.current_document_version_id)
                  if frozen_original(report) else report.current_document_version_id)
    from sqlalchemy.orm import defer
    version = ReportDocumentVersion.query.options(
        defer(ReportDocumentVersion.pdf_data), defer(ReportDocumentVersion.docx_data),
        defer(ReportDocumentVersion.snapshot),
    ).filter_by(id=version_id, report_no=report.report_no, output_kind='official').first() if version_id else None
    if not version:
        raise ValueError('尚无当前受控正式版本；请在报告制作流程中生成并确认，预览不会自动生成')
    if metadata_only:
        from ..report_generation_notices import is_saved_generation_notice
        return dict(kind='controlled', versionId=version.id, flowId=None, sha256=version.sha256,
                    preview={'notices': [w for w in (version.warnings or []) if is_saved_generation_notice(w)]},
                    label='报告原件（未签字、未盖章）' if original else '当前受控正式版本 V' + str(version.version_no))
    raw = read_file_bytes(version.pdf_file, version.pdf_data)
    if not raw or not version.sha256 or hashlib.sha256(raw).hexdigest() != version.sha256:
        raise ValueError('受控版本文件缺失或完整性校验失败')
    return dict(kind='controlled', versionId=version.id, flowId=None, sha256=version.sha256,
                label='报告原件（未签字、未盖章）' if original else '当前受控正式版本 V' + str(version.version_no), raw=raw)


def pdf_response(artifact, report_no, download=False):
    response = make_response(artifact['raw'])
    response.headers['Content-Type'] = 'application/pdf'
    disposition = 'attachment' if download else 'inline'
    response.headers['Content-Disposition'] = disposition + "; filename*=UTF-8''" + quote(report_no + '-' + artifact['kind'] + '.pdf')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@bp.route('/reports/<report_no>/artifact', methods=['GET', 'POST'])
@require_auth
def report_artifact(report_no):
    from ..models import Report
    from ..report_delivery import delivery_released, same_department, sealed_file_access_error, sealed_current_flow
    from ..platform.identity import has_function_permission
    view = str(request.args.get('view') or '')
    signed = request.args.get('signed') == '1'
    download = request.args.get('download') == '1'
    file_request = request.args.get('file') == '1'
    if request.method == 'POST' and signed:
        return fail('签章文件不通过预览生成', 405)
    if signed and (view not in {'query', 'release', 'print'} or request.args.get('original') == '1'):
        return fail('签字盖章版仅在报告签发、报告查询或报告发放中下载', 403)
    report = authorized_report(report_no)
    # Own-department release provides file access only, never arbitrary report details.
    if not report and view in {'query', 'release'} and has_function_permission(g.current_user, f'report.{view}.view'):
        candidate = Report.query.filter_by(report_no=report_no, voided=False).first()
        if candidate and delivery_released(candidate) and same_department(g.current_user, candidate):
            report = candidate
    if not report:
        return fail('无当前报告预览或下载权限', 403)
    if signed:
        from ..organization_privileges import has_full_platform_authority
        from ..report_delivery import SEALED_DOWNLOAD
        if view == 'print' and not (has_full_platform_authority(g.current_user) or SEALED_DOWNLOAD in g.current_user.action_codes()):
            return fail('报告签发下载签字盖章版需要盖章报告下载权限', 403)
        error = sealed_file_access_error(g.current_user, report)
        flow = sealed_current_flow(report)
        if error:
            return fail(error, 403)
        if not flow:
            return fail('当前报告尚无完整的签字盖章版本', 409)
        if delivery_released(report) and flow.id != (report.detail.get('reportDelivery') or {}).get('sealedFlowId'):
            return fail('当前盖章文件与发放版本不一致，请核查', 409)
        if file_request and not download:
            return fail('请使用下载签字盖章版；预览当前报告显示未签章原件', 403)
        artifact = dict(kind='signed', flowId=flow.id, versionId=flow.report_document_version_id,
                        sealed=True, sha256=flow.signed_sha256, label='签字盖章版', canDownload=True, canPreview=False)
        if file_request:
            from ..report_delivery import sealed_file_integrity_error
            error = sealed_file_integrity_error(flow)
            if error:
                return fail(error, 409)
            artifact['raw'] = read_file_bytes(flow.signed_file)
    else:
        from ..report_preview_revision import frozen_original
        if not frozen_original(report) and report.status not in {'待校核', '待审核', '待批准'}:
            can_preview, can_download = allowed('report.pdf.preview'), allowed('report.pdf.download')
            if (file_request or request.method == 'POST') and not (can_download if download else can_preview):
                return fail('无报告原件预览或下载权限', 403)
            from ..preview_cache import status, prepare, cached_pdf
            if request.method == 'POST':
                return ok(prepare(report, retry=(request.get_json(silent=True) or {}).get('retry') is True))
            if file_request:
                raw, state = cached_pdf(report)
                if raw is None:
                    return jsonify(code=202, message=state.get('message'), data=state), 202
                return pdf_response(dict(kind='current-preview', raw=raw), report_no, download)
            state = status(report) if can_preview or can_download else {}
            return ok(dict(kind='preview', versionId=None, flowId=None, label='当前内容（未签章）',
                canPreview=can_preview, canDownload=can_download, preview=state))
        if request.method == 'POST':
            return fail('报告已进入审批流程，请读取已确认的正式原件', 409)
        try:
            artifact = resolve_artifact(report, metadata_only=not file_request, original=True)
        except ValueError as exc:
            return fail(str(exc))
        artifact['canPreview'] = allowed('report.pdf.preview')
        artifact['canDownload'] = allowed('report.pdf.download')
        if file_request and not artifact['canDownload' if download else 'canPreview']:
            return fail('无报告原件预览或下载权限', 403)
    return pdf_response(artifact, report_no, download) if file_request else ok(artifact)


@bp.get('/reports/<report_no>/signing-history')
@require_auth
def signing_history(report_no):
    report = authorized_report(report_no)
    if not report:
        return fail('无当前报告查看权限', 403)
    rows = ReportEsignFlow.query.filter_by(report_id=report.id).order_by(ReportEsignFlow.id.desc()).all()
    return ok({'rows': [dict(id=f.id, versionId=f.report_document_version_id, status=f.status,
        attempt=f.attempt_no, hasSignedFile=bool(f.signed_file_id), sha256=f.signed_sha256 or '',
        createdAt=f.created_at.isoformat(), completedAt=f.completed_at.isoformat() if f.completed_at else '',
        error=f.error_message or '', signers=[dict(role=s.role_name, name=s.legal_name_snapshot,
            status=s.status, signedAt=s.signed_at.isoformat() if s.signed_at else '') for s in f.signers]) for f in rows]})


@bp.get('/reports/<report_no>/signing-history/<int:flow_id>/file')
@require_auth
def history_file(report_no, flow_id):
    return fail('历史签署文件下载入口已停用，请到报告签发、报告查询或报告发放下载当前签字盖章版', 410)


@bp.get('/bindings')
@require_auth
def bindings():
    if not binding_manager():
        return fail('无人员绑定管理权限', 403)
    try:
        page = max(1, min(int(request.args.get('page', '1')), 100000))
    except ValueError:
        return fail('分页参数无效', 400)
    query = db.session.query(User, EsignIdentityBinding).outerjoin(
        EsignIdentityBinding, EsignIdentityBinding.user_id == User.id)
    keyword = str(request.args.get('keyword') or '').strip()[:80]
    if keyword:
        query = query.filter(db.or_(User.account.contains(keyword, autoescape=True), User.name.contains(keyword, autoescape=True)))
    status = request.args.get('status')
    if status not in (None, '', 'unbound', 'pending', 'verified', 'disabled', 'invalid', 'no_account'):
        return fail('绑定状态筛选无效', 400)
    if status == 'unbound':
        query = query.filter(EsignIdentityBinding.id.is_(None))
    elif status in ('pending', 'verified', 'disabled', 'invalid'):
        query = query.filter(EsignIdentityBinding.status == status)
    missing = Personnel.query.filter(~db.session.query(User.id).filter(
        db.func.lower(User.account) == db.func.lower(Personnel.code)).exists())
    if keyword:
        missing = missing.filter(db.or_(Personnel.code.contains(keyword, autoescape=True), Personnel.name.contains(keyword, autoescape=True)))
    account_count = 0 if status == 'no_account' else query.count()
    missing_count = missing.count() if status in (None, '', 'unbound', 'no_account') else 0
    count = account_count + missing_count
    rows = []
    offset = (page - 1) * 50
    account_rows = query.order_by(User.id).offset(offset).limit(50).all() if account_count else []
    for user, binding in account_rows:
        row = binding.to_dict() if binding else dict(userId=user.id, account=user.account,
            userName=user.name, legalName=user.name, status='unbound', psnAccountMasked='')
        row.pop('psnId', None)
        row['enabled'] = user.enabled
        # This is a display, never an assignment of role/action/project rights.
        row['permissionManagedSeparately'] = True
        row['rowKey'] = 'user-' + str(user.id)
        rows.append(row)
    if missing_count and len(rows) < 50:
        for person in missing.order_by(Personnel.id).offset(max(0, offset - account_count)).limit(50 - len(rows)).all():
            rows.append(dict(userId=0, personnelId=person.id, rowKey='personnel-' + str(person.id),
                account=person.code, userName=person.name, legalName=person.name, status='no_account',
                enabled=False, psnAccountMasked='', permissionManagedSeparately=True))
    return ok(dict(rows=rows, total=count, page=page, pageSize=50))


def active_signatures(user_id):
    return db.session.query(ReportEsignFlow.id).join(ReportEsignSigner).filter(
        ReportEsignSigner.user_id == user_id,
        ReportEsignFlow.status.notin_(('completed', 'verified', 'cancelled', 'expired', 'rejected')),
        db.or_(ReportEsignFlow.status.in_(('dispatching', 'signing')),
            db.and_(ReportEsignFlow.provider_flow_id.is_not(None), ReportEsignFlow.provider_flow_id != ''),
            db.and_(ReportEsignFlow.provider_file_id.is_not(None), ReportEsignFlow.provider_file_id != ''),
            ReportEsignFlow.dispatched_at.is_not(None))).first()


def reconnect_unsent(user_id, binding):
    """Reconnect current-platform unsent tasks; never edit historical actor IDs."""
    flow_ids = db.session.query(ReportEsignSigner.flow_id).filter_by(user_id=user_id)
    flows = ReportEsignFlow.query.filter(
        ReportEsignFlow.id.in_(flow_ids),
        ReportEsignFlow.id >= int(current_app.config.get('ESIGN_PROVIDER_FLOW_MIN_ID') or 0),
        ReportEsignFlow.status.in_(('binding_required', 'ready')),
        db.or_(ReportEsignFlow.provider_flow_id.is_(None), ReportEsignFlow.provider_flow_id == ''),
        db.or_(ReportEsignFlow.provider_file_id.is_(None), ReportEsignFlow.provider_file_id == ''),
        ReportEsignFlow.dispatched_at.is_(None)).order_by(ReportEsignFlow.id).with_for_update().all()
    db.session.flush()
    for flow in flows:
        for signer in flow.signers:
            if signer.user_id == user_id and signer.status in ('binding_required', 'pending') and not signer.signed_at:
                signer.binding = binding
                signer.status = 'pending' if binding.status in ('pending', 'verified') else 'binding_required'
        ready = flow.signers and all(s.binding and s.binding.status in ('pending', 'verified') for s in flow.signers)
        roles = {s.role_code for s in flow.signers}
        from ..functions.esign_service import report_signer_roles
        required = {r[0] for r in report_signer_roles(flow.report, flow.document_version)}
        flow.status = 'ready' if ready and required == roles else 'binding_required'
        if flow.status == 'ready':
            flow.error_code = flow.error_message = None


def legacy_binding_update(user_id):
    """Compatibility entry: the old personnel form cannot bypass identity guards."""
    if not binding_manager() or not writable():
        return fail('需要人员绑定管理权限且平台可写', 403)
    user = User.query.filter_by(id=user_id).with_for_update().populate_existing().first()
    if not user or not user.enabled:
        return fail('账号不存在或已停用', 404)
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get('status', 'pending') not in ('pending', 'disabled'):
        return fail('仅可提交待认证身份或停用；不能自行设置实名状态', 400)
    try:
        person, mobile = roster_identity(user)
    except ValueError as exc:
        return fail(str(exc))
    if (str(body.get('legalName') or user.name).strip() != person.name
            or str(body.get('psnAccount') or '').strip() != mobile
            or body.get('psnAccountKind', 'mobile') != 'mobile'):
        return fail('身份必须与唯一人员名册的姓名和手机号一致，请先核实名册')
    row = EsignIdentityBinding.query.filter_by(user_id=user_id).with_for_update().populate_existing().first()
    unchanged = row and row.legal_name == person.name and row.psn_account == mobile and row.psn_account_kind == 'mobile'
    if unchanged and row.status in ('pending', 'verified') and body.get('status', 'pending') == 'pending':
        # Saving an unrelated personnel field must not erase a verified identity.
        return ok(row.to_dict())
    if active_signatures(user_id):
        return fail('存在在途或结果待核实的签署流程，不能改写签署身份')
    if not row:
        row = EsignIdentityBinding(user_id=user_id, created_by_id=g.current_user.id)
        db.session.add(row)
    row.personnel_id, row.legal_name, row.psn_account = person.id, person.name, mobile
    row.psn_account_kind, row.psn_id, row.status = 'mobile', None, body.get('status', 'pending')
    row.verified_at = row.last_checked_at = None
    row.updated_by_id = g.current_user.id
    reconnect_unsent(user_id, row)
    add_operation_audit('esign.identity.safe_maintenance', 'user', user_id, actor=g.current_user,
        after={'status': row.status}, category='integration', message='核实名册身份；未修改权限或历史签署快照')
    db.session.commit()
    return ok(row.to_dict())


@bp.post('/bindings/<int:user_id>/rebind')
@require_auth
def rebind(user_id):
    if not binding_manager() or not writable():
        return fail('需要人员绑定管理权限且平台可写', 403)
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get('confirmed') is not True:
        return fail('请明确确认重新使用名册身份；不更改任何签署权限', 400)
    user = User.query.filter_by(id=user_id).with_for_update().first()
    if not user or not user.enabled:
        return fail('账号不存在或已停用', 404)
    if active_signatures(user_id):
        return fail('存在已发起且未终结的签署流程，先完成或人工核实处理，不改写在途签署身份')
    try:
        person, mobile = roster_identity(user)
    except ValueError as exc:
        return fail(str(exc))
    row = EsignIdentityBinding.query.filter_by(user_id=user_id).with_for_update().first()
    before = {'status': row.status} if row else None
    if row is None:
        row = EsignIdentityBinding(user_id=user.id, created_by_id=g.current_user.id)
        db.session.add(row)
    row.personnel_id, row.legal_name, row.psn_account = person.id, person.name, mobile
    row.psn_account_kind, row.psn_id, row.status = 'mobile', None, 'pending'
    row.verified_at = row.last_checked_at = None
    row.updated_by_id = g.current_user.id
    # Existing historical signer snapshots and role permissions are untouched.
    reconnect_unsent(user_id, row)
    add_operation_audit('esign.identity.rebind_roster', 'user', user_id, actor=g.current_user,
        before=before, after={'status': 'pending'}, category='integration', message='重新绑定名册身份；未授予权限，未发短信')
    db.session.commit()
    return ok({'status': row.status, 'userId': user_id})


@bp.post('/bindings/<int:user_id>/sync')
@require_auth
def sync_binding(user_id):
    if not binding_manager() or not writable():
        return fail('需要人员绑定管理权限且平台可写', 403)
    if not current_app.config.get('ESIGN_ENABLED'):
        return fail('电子签署服务未启用')
    # Same lock ordering as dispatch and rebind: users, then bindings/flows.
    User.query.filter_by(id=user_id).with_for_update().populate_existing().first()
    row = EsignIdentityBinding.query.filter_by(user_id=user_id).with_for_update().first()
    if not row or row.status == 'disabled' or not row.user or not row.user.enabled:
        return fail('请先为启用的账号建立或重新确认绑定')
    before = {'status': row.status}
    try:
        identity = EsignV3Client().request('GET', '/v3/persons/identity-info', query=[('psnAccount', row.psn_account)])
    except Exception:
        db.session.rollback()
        # Never echo provider payload, account, signature, URL or credentials.
        return fail('上游身份查询失败；保留原状态，请稍后重试', 502)
    info = identity.get('psnInfo') or {}
    provider_name = info.get('psnName') if isinstance(info, dict) else None
    provider_id = identity.get('psnId')
    if not provider_name or provider_name != row.legal_name:
        db.session.rollback()
        return fail('上游姓名未获授权返回或与名册不一致；不能确认实名，请人工核实')
    if row.psn_id and provider_id != row.psn_id and active_signatures(user_id):
        db.session.rollback()
        return fail('上游身份发生变化且有在途签署；请核实，未改写绑定')
    row.psn_id = str(provider_id) if provider_id else None
    verified = bool(provider_id) and str(identity.get('realnameStatus')) == '1'
    row.status = 'verified' if verified else ('invalid' if row.status in ('verified', 'invalid') else 'pending')
    row.last_checked_at = datetime.utcnow()
    row.verified_at = (row.verified_at or row.last_checked_at) if row.status == 'verified' else None
    row.updated_by_id = g.current_user.id
    add_operation_audit('esign.identity.sync', 'user', user_id, actor=g.current_user,
        before=before, after={'status': row.status}, category='integration', message='同步上游实名状态；权限及历史签署快照未修改')
    db.session.commit()
    return ok({'userId': user_id, 'status': row.status, 'lastCheckedAt': row.last_checked_at.isoformat()})


@bp.get('/released')
@require_auth
def released_department_reports():
    """Minimal department download index; never grants workflow/detail access."""
    from ..models import Report
    from ..report_delivery import delivery_released
    from ..list_projection import list_reports, _source
    user = g.current_user
    if not user.enabled or not user.department:
        return ok({'rows': [], 'total': 0})
    page = max(1, request.args.get('page', 1, type=int) or 1)
    query = Report.query.filter(Report.department == user.department.name,
        Report.voided.is_(False), Report.status == '已发放', Report.archive_state == '归档完成')
    keyword = str(request.args.get('keyword') or '').strip()[:100]
    if keyword:
        query = query.filter(Report.report_no.contains(keyword, autoescape=True))
    # Only the version-bound explicit release marker qualifies, never old status alone.
    release_value = db.func.json_extract(_source(Report.detail), '$.reportDelivery.released')
    release_version = db.func.json_extract(_source(Report.detail), '$.reportDelivery.versionId')
    query = query.filter(db.cast(release_value, db.String).in_(['1', 'true']),
        db.cast(release_version, db.Integer) == db.func.coalesce(Report.approved_document_version_id, Report.current_document_version_id),
        db.or_(Report.report_kind.is_(None), Report.report_kind != 'correction_history'))
    total = query.count()
    reports = [r for r in list_reports(query.order_by(Report.id.desc()).offset((page-1)*20).limit(20)) if delivery_released(r)]
    return ok({'rows': [{'reportNo': r.report_no, 'sampleNo': r.sample_no,
                        'department': r.department} for r in reports],
               'total': total})
