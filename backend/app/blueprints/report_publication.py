"""Opaque, revocable report-query capabilities; no business IDs in query URLs.

New tokens are 32 random hexadecimal characters used directly in /s/v1/.
The existing digest column indexes lookups; no encryption or signing is applied
to new URL tokens. Previously printed HMAC path and fragment URLs remain valid.
"""
from app.organization_privileges import has_full_platform_authority
import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlsplit
from flask import Blueprint, current_app, g, make_response, request
from ..extensions import db
from ..models import Report, ReportDocumentVersion, ReportEsignFlow, ReportCorrectionRequest
from ..security import require_auth
from ..audit import add_operation_audit
from .report_assurance import ok, fail, writable, authorized_report, resolve_artifact

bp = Blueprint('report_publication', __name__, url_prefix='/api/report-publication')
short_bp = Blueprint('report_shortlink', __name__, url_prefix='/s/v1')


class QueryLimiter:
    """Bounded per-worker fallback; perimeter Nginx limits remain required.

    Only hashed socket/proxy-validated addresses are retained, never tokens.
    A full cache rejects new addresses rather than allowing eviction bypass.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = OrderedDict()
        self.global_window = -1
        self.global_count = 0

    def accept(self, address, download=False):
        window = int(time.monotonic() // 60)
        key = hashlib.sha256(str(address or 'unknown').encode()).digest()
        with self.lock:
            if window != self.global_window:
                self.global_window, self.global_count = window, 0
                self.clients.clear()
            if self.global_count >= 600:
                return False
            self.global_count += 1
            if key not in self.clients and len(self.clients) >= 4096:
                return False
            row = self.clients.setdefault(key, [0, 0])
            row[0] += 1
            row[1] += int(download)
            return row[0] <= 90 and row[1] <= 6


@bp.before_request
@short_bp.before_request
def secure_query_transport():
    # Configure the existing trusted reverse proxy correctly; do not trust an
    # arbitrary X-Forwarded-Proto header here or process bearer tokens on HTTP.
    public_request = request.blueprint == 'report_shortlink' or request.endpoint in (
        'report_publication.public_lookup', 'report_publication.public_download', 'report_publication.query_page')
    if public_request and not request.is_secure:
        return fail('报告查询仅接受 HTTPS；80 端口只应跳转到 HTTPS 入口', 400)
    if public_request:
        limiter = current_app.extensions.setdefault('report_query_limiter', QueryLimiter())
        if not limiter.accept(request.remote_addr, request.endpoint.endswith('public_download')):
            response = make_response(fail('查询频率过高，请稍后重试', 429))
            response.headers['Retry-After'] = '60'
            return response


class ReportPublication(db.Model):
    __tablename__ = 'report_publications'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=False, index=True)
    nonce = db.Column(db.String(64), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    revoked_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    version_id = db.Column(db.Integer, db.ForeignKey('report_document_versions.id'))
    flow_id = db.Column(db.Integer, db.ForeignKey('report_esign_flows.id'))
    artifact_sha256 = db.Column(db.String(64))
    published_at = db.Column(db.DateTime)
    allow_download = db.Column(db.Boolean, nullable=False, default=False)
    withdrawn_reason = db.Column(db.String(120))


def token_for(nonce):
    if re.fullmatch(r'[0-9a-f]{32}', nonce):
        return nonce
    # Historical 64-character nonces still reproduce their printed capability.
    key = current_app.config.get('REPORT_QUERY_SECRET') or current_app.config.get('JWT_SECRET') or ''
    if not isinstance(key, str) or len(key) < 32:
        raise ValueError('报告查询密钥未安全配置')
    raw = hmac.new(key.encode(), b'report-publication-v1\0' + bytes.fromhex(nonce), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def public_base():
    base = str(current_app.config.get('REPORT_QUERY_ORIGIN') or 'https://lab.example.com.cn').rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise ValueError('报告查询必须使用配置的可信 HTTPS 站点源地址')
    return base + '/s/v1/'


def current_publication(report_id):
    return ReportPublication.query.filter_by(report_id=report_id, revoked_at=None).order_by(ReportPublication.id.desc()).first()


def issue(report):
    nonce = secrets.token_hex(16)
    token = token_for(nonce)
    row = ReportPublication(report_id=report.id, nonce=nonce, token_hash=hashlib.sha256(token.encode()).hexdigest())
    db.session.add(row)
    db.session.flush()
    return row


def ensure_prepared_query(report):
    """Caller holds report row lock and has checked edit permission. No commit.

    Never reactivate a revoked entry or silently replace a signed/controlled QR.
    Preparing an entry does not publish or enable any file download.
    """
    row = current_publication(report.id)
    if row:
        report_qr_url(report)  # Validate the stored capability before reuse.
        # A published QR stays attached to its signed original. A new editable
        # correction gets another entry; the old entry remains queryable.
        if (row.published_at or query_artifact(row)[0]) and not report.approved_document_version_id:
            public_base()
            return issue(report), True
        return row, False
    if ReportPublication.query.filter_by(report_id=report.id).first():
        raise ValueError('此报告查询入口已停用，请联系管理员处理；系统不会自动恢复旧二维码')
    from ..models import ReportDocumentVersion
    if (ReportDocumentVersion.query.filter_by(report_no=report.report_no).first()
            or ReportEsignFlow.query.filter_by(report_id=report.id).first()):
        raise ValueError('此报告已有受控或签署文件，请联系管理员核查原二维码后处理')
    public_base()  # Validate configuration before creating the row.
    return issue(report), True


def report_qr_url(report):
    """Renderer reads an explicitly prepared token. No implicit DB writes.

    Do not regenerate a signed PDF to add or replace this QR. Existing signed
    bytes remain immutable; new controlled versions use the newly issued URL.
    """
    row = current_publication(report.id)
    if not row:
        raise ValueError('请在检测数据录入中保存报告信息，系统将自动准备查询二维码')
    token = token_for(row.nonce)
    if hashlib.sha256(token.encode()).hexdigest() != row.token_hash:
        raise ValueError('报告查询配置已变更，请联系管理员核查查询链接；已有签署文件不会自动修改')
    path_token = token if len(token) == 32 else base64.urlsafe_b64decode(token + '=').hex()
    return public_base() + path_token


def metadata(row):
    return dict(id=row.id, revoked=bool(row.revoked_at), published=bool(row.published_at),
        versionId=row.version_id, flowId=row.flow_id, allowDownload=row.allow_download,
        createdAt=row.created_at.isoformat(), publishedAt=row.published_at.isoformat() if row.published_at else None)


@bp.route('/reports/<report_no>', methods=['GET', 'POST'])
@require_auth
def manage_publication(report_no):
    report = authorized_report(report_no)
    if not report or not has_full_platform_authority(g.current_user):
        return fail('报告公开查询入口由有数据访问权限的管理员维护', 403)
    if request.method == 'GET':
        row = current_publication(report.id)
        try:
            url = report_qr_url(report) if row else None
        except ValueError as exc:
            return fail(str(exc))
        return ok({'rows': [metadata(r) for r in ReportPublication.query.filter_by(report_id=report.id).order_by(ReportPublication.id.desc()).all()],
                   'url': url, 'publication': metadata(row) if row else None})
    if not writable():
        return fail('平台为只读状态', 403)
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get('confirmed') is not True:
        return fail('请确认公开范围及操作', 400)
    # Serialize issuance/rotation per report, including when no token exists.
    Report.query.filter_by(id=report.id).with_for_update().first()
    action = body.get('action')
    row = current_publication(report.id)
    url = None
    if action in ('issue', 'rotate'):
        if action == 'rotate' and row:
            row.revoked_at = datetime.utcnow()
        if not row or action == 'rotate':
            row = issue(report)
        try:
            url = report_qr_url(report)
        except ValueError as exc:
            db.session.rollback()
            return fail(str(exc))
    elif action == 'revoke':
        if row:
            row.revoked_at = datetime.utcnow()
    elif action == 'withdraw':
        if not row:
            return fail('查询入口不存在')
        reason = str(body.get('reason') or '').strip()
        if reason not in ('报告已撤销', '报告更正中', '报告已更正', '暂停公开'):
            return fail('请选择公开状态原因', 400)
        row.withdrawn_reason = reason
        row.allow_download = False
    elif action == 'publish':
        if not row or report.voided or row.withdrawn_reason:
            return fail('入口不存在、报告已作废或已停止公开，请核查')
        try:
            artifact = resolve_artifact(report)
        except ValueError as exc:
            return fail(str(exc))
        if artifact['kind'] != 'signed' or artifact['versionId'] != report.approved_document_version_id:
            return fail('仅能公开当前批准版本的实际签署文件')
        if type(body.get('allowDownload')) is not bool:
            return fail('请明确是否允许持令牌者下载报告', 400)
        if row.published_at and (row.version_id != artifact['versionId'] or row.flow_id != artifact['flowId'] or row.artifact_sha256 != artifact['sha256']):
            return fail('已公开入口已绑定历史签署文件，请更换令牌；不会悄悄替换旧链接内容')
        row.version_id, row.flow_id, row.artifact_sha256 = artifact['versionId'], artifact['flowId'], artifact['sha256']
        row.published_at = row.published_at or datetime.utcnow()
        row.allow_download = body['allowDownload']
    else:
        return fail('操作无效', 400)
    add_operation_audit('report.publication.' + action, 'report', report.report_no, actor=g.current_user,
        category='configuration', after=metadata(row) if row else {}, message='维护报告公开查询；不记录令牌、不改写已签署文件')
    db.session.commit()
    return ok({'publication': metadata(row) if row else None, 'url': url})


def lookup():
    if not request.is_json or request.content_length is None or request.content_length > 1024:
        return None
    body = request.get_json(silent=True)
    token = body.get('token') if isinstance(body, dict) else None
    if not isinstance(token, str):
        return None
    if re.fullmatch(r'[0-9a-f]{64}', token):
        token = base64.urlsafe_b64encode(bytes.fromhex(token)).decode().rstrip('=')
    elif not re.fullmatch(r'(?:[0-9a-f]{32}|[A-Za-z0-9_-]{43})', token):
        return None
    return ReportPublication.query.filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest(), revoked_at=None).first()


def query_artifact(row):
    """Resolve the QR's original signed version without changing published data.

    Prepared legacy entries have no explicit publication binding. Preserve the
    first signed version after preparation, never substitute a later correction.
    A previously signed flow changing status must not silently select another.
    """
    if row.version_id or row.published_at:
        version = db.session.get(ReportDocumentVersion, row.version_id) if row.version_id else None
        flow = db.session.get(ReportEsignFlow, row.flow_id) if row.flow_id else None
        return version, flow
    flow = ReportEsignFlow.query.filter_by(report_id=row.report_id).filter(
        ReportEsignFlow.created_at >= row.created_at,
        ReportEsignFlow.signed_file_id.isnot(None),
        ReportEsignFlow.signed_sha256.isnot(None)).order_by(
            ReportEsignFlow.created_at, ReportEsignFlow.id).first()
    version = db.session.get(ReportDocumentVersion, flow.report_document_version_id) if flow else None
    return version, flow


def public_state(row, binding=None):
    report = db.session.get(Report, row.report_id)
    if not report:
        return None, '查询入口不可用'
    if row.withdrawn_reason:
        return report, row.withdrawn_reason
    derived = Report.query.filter(Report.main_report_no == report.report_no,
        Report.voided.is_(False), Report.report_kind.in_(('correction', 'replacement'))).all()
    for corrected in derived:
        final = ReportEsignFlow.query.filter_by(report_id=corrected.id,
            report_document_version_id=corrected.approved_document_version_id).filter(
            ReportEsignFlow.status.in_(('completed', 'verified'))).first() if corrected.approved_document_version_id else None
        if final and final.signed_sha256:
            return report, '已有更正版本，原版本已被替代，请向出具机构获取更正报告'
    if report.voided:
        return report, '报告已作废'
    from ..internal_report_corrections import blocks_new_request
    corrections = ReportCorrectionRequest.query.filter_by(main_report_no=report.report_no).filter(
        ReportCorrectionRequest.status.in_(('pending_approval', 'pending_director', 'pending_leader', 'approved'))).all()
    correction = next((item for item in corrections if blocks_new_request(item, report)), None)
    if correction:
        return report, '报告更正中' if correction.status != 'approved' else '报告更正已批准，更正版本办理中'
    # Fail closed for a changed approved pointer, even before a new signature.
    version, flow = binding if binding is not None else query_artifact(row)
    bound_version_id = row.version_id or (version.id if version else None)
    if bound_version_id and report.approved_document_version_id != bound_version_id:
        return report, '已有更新版本，当前二维码对应原版本，请向出具机构核实更正报告'
    derived = Report.query.filter(Report.main_report_no == report.report_no, Report.voided.is_(False),
        Report.report_kind.in_(('correction', 'replacement'))).first()
    if derived:
        return report, '报告存在更正流程，请联系出具机构核实'
    # Electronic issuance is complete once the signed organization-seal file
    # exists. The later print/distribution transition is not a QR prerequisite.
    from ..functions.esign_service import flow_has_organization_seal
    electronic_complete = bool(flow and flow.status in ('completed', 'verified')
        and flow.signed_file_id and flow.signed_sha256 and flow_has_organization_seal(flow))
    if not report.stamped and not electronic_complete:
        return report, '尚未正式签发'
    if (not version or version.report_no != report.report_no or version.output_kind != 'official'
            or not flow or flow.report_id != report.id or flow.report_document_version_id != version.id
            or flow.status not in ('completed', 'verified') or not flow.signed_file_id or not flow.signed_sha256
            or (row.published_at and flow.signed_sha256 != row.artifact_sha256)):
        return report, '签署文件状态异常，请联系出具机构核实'
    from ..functions.esign_service import issuance_blocker
    if issuance_blocker(report):
        return report, '签发状态待核实，请联系出具机构核实'
    return report, '有效'


@bp.post('/lookup')
def public_lookup():
    row = lookup()
    if not row:
        return fail('无效二维码，无对应报告', 404)
    version, flow = query_artifact(row)
    report, status = public_state(row, (version, flow))
    if not report:
        return fail(status, 404)
    from ..report_final_fields import public_facts, redact_public_project_name
    from ..workflow_dates import business_date
    facts = {}
    if (version and version.report_no == report.report_no and flow and flow.report_id == report.id
            and flow.report_document_version_id == version.id and flow.status in ('completed', 'verified')
            and (row.published_at or (not row.withdrawn_reason and not report.voided))):
        # Freeze displayed business fields to the queried version. Never read
        # the current editable form for a historical report's key fields.
        from ..models import OperationAudit
        approved = OperationAudit.query.filter_by(category='workflow', object_type='report',
            object_id=report.report_no, action='report.approval.pass', success=True)
        approved = approved.filter(OperationAudit.created_at <= flow.created_at).order_by(
            OperationAudit.created_at.desc(), OperationAudit.id.desc()).first() if flow and flow.created_at else None
        date = business_date(approved.created_at).isoformat() if approved else ''
        facts = redact_public_project_name(report.report_no,
            public_facts(version.snapshot, version.version_no, date))
    return ok(dict(reportNo=report.report_no, validity='正式报告' if status == '有效' else status, facts=facts,
        signingStatus='已签署' if facts else '未公开确认',
        publishedAt=row.published_at.isoformat() if row.published_at else None,
        downloadAllowed=False))


@bp.post('/download')
def public_download():
    return fail('二维码仅用于核验，正式报告请在系统报告签发、报告查询或报告发放中下载', 403)


@bp.after_request
@short_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@short_bp.get('/<token>')
def short_query_page(token):
    if not re.fullmatch(r'(?:[0-9a-f]{32}|[0-9a-f]{64})', token):
        return fail('无效二维码，无对应报告', 404)
    return query_page()


@bp.get('/query')
def query_page():
    nonce = secrets.token_urlsafe(24)
    html = '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="referrer" content="no-referrer"><title>报告信息核验</title>\n\n<style nonce="NONCE">:root { font-family: system-ui, "Microsoft YaHei", sans-serif; color: #1e293b; background: #f1f5f9; }\n* { box-sizing: border-box; }\nbody { margin: 0; padding: 24px 16px; }\nmain { max-width: 820px; margin: 0 auto; padding: 28px; background: white; border: 1px solid #dbe3ee; border-radius: 12px; }\nh1 { font-size: 26px; margin: 0 0 20px; line-height: 1.4; }\n#result { margin: 0 0 20px; padding: 12px 16px; border-radius: 6px; background: #eff6ff; color: #23456d; line-height: 1.6; }\n#result[data-kind="error"] { background: #fff7ed; color: #9a3412; }\ndl { display: grid; grid-template-columns: 132px minmax(0, 1fr); margin: 0 0 24px; border: 1px solid #cbd5e1; border-bottom: 0; }\ndl[hidden], button[hidden] { display: none; }\ndt, dd { margin: 0; padding: 13px 16px; border-bottom: 1px solid #cbd5e1; line-height: 1.65; overflow-wrap: anywhere; }\ndt { background: #edf5fa; color: #23456d; font-weight: 600; border-right: 1px solid #cbd5e1; }\ndd { min-width: 0; white-space: pre-wrap; font-variant-numeric: tabular-nums; }\nbutton { padding: 11px 18px; border: 0; border-radius: 6px; color: white; background: #2458b7; font: inherit; cursor: pointer; }\nbutton:hover { background: #194695; }\nbutton:disabled { opacity: .65; cursor: wait; }\nbutton:focus-visible { outline: 3px solid #1e40af; outline-offset: 3px; }\n::selection { background: #cde3fb; color: #152c49; }\n.notice { margin: 24px 0 0; border-top: 1px solid #e2e8f0; padding-top: 16px; color: #526174; line-height: 1.7; font-size: 13px; }\n@media (max-width: 540px) { body { padding: 12px; } main { padding: 20px 14px; } h1 { font-size: 23px; } dl { grid-template-columns: 98px minmax(0, 1fr); } dt, dd { padding: 11px 10px; font-size: 14px; } }\n</style></head>\n<body><main><h1 id="page-title">报告信息核验</h1><p id="result" role="status" aria-live="polite">正在核验报告信息，请稍候……</p>\n<dl id="details" hidden></dl><button id="download" hidden>下载实际签署 PDF</button>\n<p class="notice">请核对以上信息与您持有的报告是否一致。本页不替代 PDF 电子签名有效性验证。</p>\n<noscript>请启用浏览器 JavaScript 后重新扫描二维码。</noscript></main><script nonce="NONCE">(async function () {\n  \'use strict\';\n  const result = document.getElementById(\'result\');\n  const details = document.getElementById(\'details\');\n  const button = document.getElementById(\'download\');\n  const shortMatch = location.pathname.match(/^\\/s\\/v1\\/([0-9a-f]{32}|[0-9a-f]{64})$/);\n  const legacyMode = location.pathname === \'/api/report-publication/query\';\n  const tokenMode = Boolean(shortMatch) || legacyMode;\n  const token = shortMatch ? shortMatch[1] : legacyMode ? location.hash.slice(1) : \'\';\n  if (legacyMode) history.replaceState(null, \'\', location.pathname);\n  const fail = (message) => { result.textContent = message; result.dataset.kind = \'error\'; };\n  const notFound = \'无效二维码，无对应报告。请核对二维码或联系出具机构。\';\n  let reportNo = \'\';\n  try {\n    if (tokenMode) {\n      if (!/^(?:[0-9a-f]{32}|[A-Za-z0-9_-]{43}|[0-9a-f]{64})$/.test(token)) throw Error(\'invalid token\');\n    } else {\n      const match = location.pathname.match(/^\\/service\\/reports\\/([^/]+)\\/?$/);\n      reportNo = match ? decodeURIComponent(match[1]) : \'\';\n      if (!reportNo || reportNo.length > 40 || /[\\x00-\\x1f\\x7f]/.test(reportNo)) throw Error(\'invalid number\');\n    }\n  } catch (_) { fail(notFound); return; }\n  async function call(path, signal) {\n    return fetch(\'/api/report-publication/\' + path, {\n      method: \'POST\', credentials: \'omit\', cache: \'no-store\', signal,\n      headers: { \'Content-Type\': \'application/json\' }, body: JSON.stringify({ token })\n    });\n  }\n  const controller = new AbortController();\n  const timer = setTimeout(() => controller.abort(), 15000);\n  try {\n    const response = tokenMode ? await call(\'lookup\', controller.signal) : await fetch(\n      \'/api/public/v1/reports/query?reportNo=\' + encodeURIComponent(reportNo), {\n        method: \'GET\', credentials: \'omit\', cache: \'no-store\', signal: controller.signal,\n        headers: { Accept: \'application/json\' }\n      });\n    if (response.status === 404) { fail(notFound); return; }\n    if (response.status === 429) { fail(\'查询过于频繁，请稍后重新扫描。\'); return; }\n    if (!response.ok) throw Error(\'request failed\');\n    const body = await response.json();\n    const data = body.data;\n    if (body.code !== 0 || !data || (!tokenMode && data.reportNo !== reportNo)) throw Error(\'unexpected response\');\n    const facts = tokenMode ? data.facts : data;\n    result.textContent = tokenMode ? data.validity : data.verificationStatus;\n    if (!facts || (tokenMode && !Object.keys(facts).length)) return;\n    const calibration = facts.reportKind === \'calibration\';\n    document.getElementById(\'page-title\').textContent = calibration ? \'校准证书信息核验\' : \'报告信息核验\';\n    const rows = [\n      [calibration ? \'证书编号\' : \'报告编号\', data.reportNo],\n      [calibration ? \'证书标题\' : \'报告标题\', facts.reportTitle],\n      [\'委托单位\', facts.client], [\'工程名称\', facts.projectName],\n      [calibration ? \'计量器具名称\' : \'样品名称\', facts.sampleName],\n      [\'规格型号\', tokenMode ? facts.model : facts.specification],\n      [\'数量\', facts.quantity],\n      [calibration ? \'校准项目\' : \'检验项目\', facts.testItems],\n      [calibration ? \'签发日期\' : \'报告日期\', tokenMode ? facts.issueDate : facts.reportDate]\n    ];\n    for (const [label, value] of rows) {\n      const term = document.createElement(\'dt\'); term.textContent = label;\n      const entry = document.createElement(\'dd\');\n      entry.textContent = typeof value === \'string\' && value ? value : \'—\';\n      details.append(term, entry);\n    }\n    details.hidden = false;\n    if (button) button.hidden = !(tokenMode && data.downloadAllowed === true);\n  } catch (_) { fail(\'暂时无法连接报告核验服务，请稍后重新扫描。\'); }\n  finally { clearTimeout(timer); }\n  if (button) button.onclick = async () => {\n    button.disabled = true;\n    try {\n      const response = await call(\'download\');\n      if (!response.ok || !response.headers.get(\'Content-Type\')?.includes(\'application/pdf\')) throw Error(\'not available\');\n      const blob = await response.blob(), url = URL.createObjectURL(blob), link = document.createElement(\'a\');\n      link.href = url; link.download = \'signed-report.pdf\'; link.click();\n      setTimeout(() => URL.revokeObjectURL(url), 1000);\n    } catch (_) { fail(\'当前签署文件不可下载，请联系出具机构。\'); }\n    finally { button.disabled = false; }\n  };\n}());\n</script></body></html>'.replace('NONCE', nonce)
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Content-Security-Policy'] = "default-src 'none'; script-src 'nonce-" + nonce + "'; style-src 'nonce-" + nonce + "'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    return response
