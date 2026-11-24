"""Report issuance orchestration and the e签宝 V3 adapter.

The approval transaction only creates an idempotent local task.  Provider calls
are made by an explicit dispatch endpoint/CLI so a third-party outage can never
roll back a valid approval.  Every external call is also gated by deployment
configuration and the global external-side-effect switch.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from itertools import product
from typing import Any

from flask import current_app
from sqlalchemy import func

from ..audit import add_operation_audit, latest_operation_audit
from ..extensions import db
from ..functions.stored_files import persist_bytes, read_file_bytes
from ..models import (
    EsignIdentityBinding,
    EsignReminderLog,
    OperationAudit,
    Personnel,
    Report,
    ReportDocumentVersion,
    ReportEsignFlow,
    ReportEsignSigner,
    User,
)
from ..authorization_scope import project_step_error
from ..esign_access import flow_state_error, manager_flow_error, signer_access_error
from .esign_dispatch_state import definitely_uncreated, set_phase


ROLE_DEFINITIONS = (
    ("chief", "主检", 1),
    ("reviewer", "审核", 2),
    ("approver", "批准", 3),
)
ACTIVE_FLOW_STATUSES = {"binding_required", "ready", "dispatching", "signing"}
COMPLETED_FLOW_STATUSES = {"completed", "verified"}
FLOW_KIND_PERSON = "person_signing"
FLOW_KIND_ORGANIZATION_SEAL = "organization_seal"


class EsignServiceError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _positioning_snapshot(flow: ReportEsignFlow) -> dict[str, Any]:
    try:
        value = json.loads(flow.positioning_json or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _flow_kind(flow: ReportEsignFlow) -> str:
    return str(_positioning_snapshot(flow).get("flowKind") or FLOW_KIND_PERSON)


def _organization_seal_state(flow: ReportEsignFlow) -> dict[str, Any]:
    value = _positioning_snapshot(flow).get("organizationSeal") or {}
    return value if isinstance(value, dict) else {}


def flow_has_organization_seal(flow: ReportEsignFlow) -> bool:
    state = _organization_seal_state(flow)
    if "included" in state:
        return state["included"] is True
    snapshot = _positioning_snapshot(flow)
    positions = snapshot.get("positions") or {}
    # Compatibility with flows created by the earlier implementation, which
    # resolved cover/date only when an organization signer was included.
    return isinstance(positions, dict) and "cover" in positions and "date" in positions


def normalize_psn_account(value: str, kind: str = "mobile") -> str:
    normalized = str(value or "").strip()
    if kind == "mobile":
        normalized = normalized.replace(" ", "").replace("-", "")
        if not (len(normalized) == 11 and normalized.isdigit() and normalized.startswith("1")):
            raise EsignServiceError("invalid_mobile", "手机号必须为11位中国大陆手机号")
    elif kind == "email":
        if "@" not in normalized or len(normalized) > 160:
            raise EsignServiceError("invalid_email", "电子邮箱格式不正确")
    else:
        raise EsignServiceError("invalid_account_kind", "仅支持手机号或电子邮箱作为签署账号")
    return normalized


def _user_from_reference(value: Any) -> User | None:
    if isinstance(value, dict):
        candidates = (
            value.get("userId"), value.get("id"), value.get("account"),
            value.get("code"), value.get("personCode"), value.get("name"),
        )
    else:
        candidates = (value,)
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        if isinstance(candidate, int) or str(candidate).isdigit():
            row = db.session.get(User, int(candidate))
            if row and row.enabled:
                return row
        text = str(candidate).strip()
        row = User.query.filter(func.lower(User.account) == text.lower(), User.enabled.is_(True)).first()
        if row:
            return row
        matches = User.query.filter(User.name == text, User.enabled.is_(True)).all()
        if len(matches) == 1:
            return matches[0]
    return None


def _audit_actor(report_no: str, action: str) -> User | None:
    row = latest_operation_audit("report", report_no, action)
    if not row:
        return None
    if row.user_id:
        user = db.session.get(User, row.user_id)
        if user and user.enabled:
            return user
    return _user_from_reference(row.account or row.user_name)


def _signer_detail(report, version=None):
    frozen = ((version.snapshot or {}).get("report") or {}) if version is not None else {}
    return frozen["detail"] if isinstance(frozen.get("detail"), dict) else (report.detail or {})


def _reference_present(value):
    if isinstance(value, dict):
        return any(str(value.get(key) or "").strip() for key in ("userId", "id", "account", "code", "personCode", "name"))
    return bool(str(value or "").strip())


def _second_chief_reference(report, version=None):
    detail = _signer_detail(report, version)
    ci = detail.get("checkInput") or {}
    people = ci.get("people") or {}
    assigned = ci.get("assignedPeople") or detail.get("assignedPeople") or {}
    return people.get("primaryTester2") if "primaryTester2" in people else assigned.get("primaryTester2")


def report_signer_roles(report, version=None):
    if _reference_present(_second_chief_reference(report, version)):
        return (("chief", "主检", 1), ("chief2", "主检2", 2), ("reviewer", "审核", 3), ("approver", "批准", 4))
    return ROLE_DEFINITIONS


def _reconcile_second_chief(flow, actor=None):
    """Upgrade only untouched local tasks. Never change an upstream signing flow."""
    if _flow_kind(flow) == FLOW_KIND_ORGANIZATION_SEAL:
        source = db.session.get(ReportEsignFlow, _positioning_snapshot(flow).get("sourceFlowId"))
        if not source or _flow_kind(source) != FLOW_KIND_PERSON or source.status not in COMPLETED_FLOW_STATUSES:
            raise EsignServiceError("personal_signing_incomplete", "组织补章缺少已完成的人员签署流程")
        _reconcile_second_chief(source, actor)
        return
    ref = _second_chief_reference(flow.report, flow.document_version)
    second_row = next((s for s in flow.signers if s.role_code == "chief2"), None)
    if not _reference_present(ref):
        if second_row:
            raise EsignServiceError("signer_set_changed", "签署人员与批准版本不一致，请核实后重新准备任务")
        return
    second = _user_from_reference(ref)
    if not second:
        raise EsignServiceError("binding_required", "主检2账号不存在或已停用，请核实批准版本人员")
    chief_row = next((s for s in flow.signers if s.role_code == "chief"), None)
    if chief_row and chief_row.user_id == second.id:
        raise EsignServiceError("duplicate_chief", "主检1和主检2不能选择同一账号")
    orders = {code: order for code, _label, order in report_signer_roles(flow.report, flow.document_version)}
    if second_row and second_row.user_id == second.id and all(s.sign_order == orders.get(s.role_code) for s in flow.signers):
        return
    untouched = (flow.status in {"ready", "binding_required", "failed"}
        and not flow.provider_flow_id and not flow.provider_file_id and not flow.dispatched_at
        and all(s.status in {"pending", "binding_required"} and not s.signed_at for s in flow.signers))
    if not untouched:
        if flow.status in COMPLETED_FLOW_STATUSES:
            raise EsignServiceError("signer_set_changed", "已完成的旧签署流程缺少主检2或顺序不符；请按报告更正和重新审批生成新版本后重新签署，不能修改已签PDF")
        raise EsignServiceError("signer_set_changed", "旧签署流程缺少主检2或顺序不符；请先核实并撤销旧流程，再重新准备签署，不能直接重复发起")
    binding = EsignIdentityBinding.query.filter_by(user_id=second.id).first()
    if second_row is None:
        second_row = ReportEsignSigner(role_code="chief2", role_name="主检2", user_id=second.id, sign_order=2)
        flow.signers.append(second_row)
    second_row.user_id = second.id
    second_row.binding = binding
    second_row.legal_name_snapshot = binding.legal_name if binding else second.name
    second_row.psn_id_snapshot = binding.psn_id if binding else None
    second_row.status = "pending" if binding and binding.status in {"pending", "verified"} else "binding_required"
    for signer in flow.signers:
        if signer.role_code in orders:
            signer.sign_order = orders[signer.role_code]
    flow.signers.sort(key=lambda s:s.sign_order)
    ready = set(orders) == {s.role_code for s in flow.signers} and all(s.binding and s.binding.status in {"pending", "verified"} for s in flow.signers)
    flow.status = "ready" if ready else "binding_required"
    flow.error_code = None if ready else "binding_required"
    flow.error_message = None if ready else "请补齐全部签署人的身份绑定（含主检2）"
    add_operation_audit("report.esign.chief2.reconcile", "report", flow.report_no,
        category="integration", after={"flowId":flow.id,"secondChiefUserId":second.id}, actor=actor,
        message="未发出的本地任务补齐主检2及签署顺序")
    db.session.flush()


def resolve_report_signers(report: Report, version=None) -> tuple[dict[str, User], list[str]]:
    detail = _signer_detail(report, version)
    check_input = detail.get("checkInput") or {}
    people = check_input.get("people") or {}
    assigned = check_input.get("assignedPeople") or detail.get("assignedPeople") or {}
    chief = (
        _user_from_reference(people.get("primaryTester1"))
        or _user_from_reference(assigned.get("primaryTester1"))
        or _user_from_reference(check_input.get("entryStaff"))
        or _user_from_reference(check_input.get("owner"))
        or _user_from_reference(report.owner)
        or _audit_actor(report.report_no, "report.data_entry.complete")
    )
    second_ref = _second_chief_reference(report, version)
    second = _user_from_reference(second_ref) if _reference_present(second_ref) else None
    if second and chief and second.id == chief.id:
        raise EsignServiceError("duplicate_chief", "主检1和主检2不能选择同一账号")
    reviewer = _audit_actor(report.report_no, "report.review.pass")
    approver = _audit_actor(report.report_no, "report.approval.pass")
    rows = {"chief": chief, "reviewer": reviewer, "approver": approver}
    if _reference_present(second_ref):
        rows["chief2"] = second
    errors = [label for code, label, _order in report_signer_roles(report, version) if rows.get(code) is None]
    return {key: value for key, value in rows.items() if value is not None}, errors


def _approved_version(report: Report, actor: User | None = None) -> ReportDocumentVersion:
    report = Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    version_id = report.approved_document_version_id or report.current_document_version_id
    version = db.session.get(ReportDocumentVersion, version_id) if version_id else None
    reusable = (
        version is not None
        and version.report_no == report.report_no
        and version.output_kind == "official"
        and bool(version.pdf_file_id or version.pdf_data)
    )
    from ..report_final_fields import approval_date
    from .. import docparser_field_only
    if docparser_field_only.applies_to(report) or not reusable or (version.snapshot or {}).get("approvalDate") != approval_date(report):
        try:
            from ..report_final_fields import ensure_approved_date_version

            version = ensure_approved_date_version(report, version, actor)
        except Exception as exc:
            raise EsignServiceError(
                "approved_pdf_prepare_failed",
                f"批准版本正式 PDF 生成失败：{str(exc)[:240]}",
            ) from exc
    return version


def ensure_report_esign_flow(report_no: str, actor: User | None = None) -> ReportEsignFlow:
    from ..esign_production import require_ready
    require_ready()
    report = Report.query.filter_by(report_no=report_no).with_for_update().populate_existing().first()
    if not report:
        raise EsignServiceError("report_not_found", "报告不存在")
    from .esign_stages import current_flow
    staged_flow = current_flow(report)
    if staged_flow:
        error = flow_state_error(staged_flow)
        if error:
            raise EsignServiceError('stage_invalid', error)
        return staged_flow
    version = _approved_version(report, actor)
    existing = (
        ReportEsignFlow.query.filter_by(
            report_id=report.id, report_document_version_id=version.id
        )
        .filter(ReportEsignFlow.id >= current_app.config["ESIGN_PROVIDER_FLOW_MIN_ID"])
        .order_by(ReportEsignFlow.attempt_no.desc())
        .first()
    )
    if existing and existing.status == 'cancelling':
        raise EsignServiceError('cancellation_pending', '旧流程撤销结果待核实，暂不能建立新任务')
    if existing and existing.status in ACTIVE_FLOW_STATUSES | COMPLETED_FLOW_STATUSES | {'failed'}:
        existing = ReportEsignFlow.query.filter_by(id=existing.id).with_for_update().populate_existing().first()
        _reconcile_second_chief(existing, actor)
        db.session.commit()
        return existing

    signers, missing_roles = resolve_report_signers(report, version)
    role_definitions = report_signer_roles(report, version)
    bindings: dict[str, EsignIdentityBinding | None] = {}
    missing_bindings: list[str] = []
    for role_code, role_name, _order in role_definitions:
        user = signers.get(role_code)
        binding = EsignIdentityBinding.query.filter_by(user_id=user.id).first() if user else None
        bindings[role_code] = binding
        if user and (not binding or binding.status not in {"pending", "verified"}):
            missing_bindings.append(f"{role_name}（{user.name}）")

    attempt = (
        db.session.query(func.max(ReportEsignFlow.attempt_no))
        .filter_by(report_id=report.id, report_document_version_id=version.id)
        .scalar()
        or 0
    ) + 1
    status = "ready" if not missing_roles and not missing_bindings else "binding_required"
    problems = []
    if missing_roles:
        problems.append("未识别角色：" + "、".join(missing_roles))
    if missing_bindings:
        problems.append("未绑定：" + "、".join(missing_bindings))
    flow = ReportEsignFlow(
        report_id=report.id,
        report_no=report.report_no,
        report_document_version_id=version.id,
        attempt_no=attempt,
        status=status,
        source_sha256=version.sha256,
        error_code="binding_required" if problems else None,
        error_message="；".join(problems) or None,
        positioning_json=json.dumps({
            "flowKind": FLOW_KIND_PERSON,
            "organizationSeal": {
                "included": False,
                "status": "awaiting_personal_signatures",
                "confirmationRequired": True,
                "sealMode": "assigned" if str(current_app.config.get("ESIGN_ORG_SEAL_ID") or "").strip() else "default",
                "normalSealScope": "report_homepage_only",
                "acrossPageMode": "ALL",
            },
        }, ensure_ascii=False, separators=(",", ":"))
        if current_app.config.get("ESIGN_ORG_AUTOSIGN_ENABLED") else None,
        created_by_id=getattr(actor, "id", None),
    )
    db.session.add(flow)
    db.session.flush()
    for role_code, role_name, order in role_definitions:
        user = signers.get(role_code)
        if not user:
            continue
        binding = bindings.get(role_code)
        db.session.add(ReportEsignSigner(
            flow_id=flow.id,
            role_code=role_code,
            role_name=role_name,
            user_id=user.id,
            binding_id=binding.id if binding else None,
            legal_name_snapshot=(binding.legal_name if binding else user.name),
            psn_id_snapshot=(binding.psn_id if binding else None),
            sign_order=order,
            status="pending" if binding else "binding_required",
        ))
    add_operation_audit(
        "report.esign.prepare", "report", report.report_no,
        category="integration", after={"flowId": flow.id, "status": status},
        message=flow.error_message or "电子签发任务已准备", actor=actor,
    )
    db.session.commit()
    return flow


def ensure_organization_seal_flow(
    report_no: str, actor: User | None = None, *, source_flow_id=None, source_sha256=None
) -> ReportEsignFlow:
    """Prepare an idempotent organization-only seal flow over a signed PDF.

    Legacy reports may already contain all three personal signatures while the
    organization signer was disabled.  Their completed PDF is immutable, so a
    new attempt uses that exact signed PDF as its source and adds only the
    report-homepage seal plus an across-page seal.  No person signs again.
    """
    from ..esign_production import require_ready
    require_ready()
    report = Report.query.filter_by(report_no=report_no).first()
    if not report:
        raise EsignServiceError("report_not_found", "报告不存在")
    report = Report.query.filter_by(id=report.id).with_for_update().populate_existing().one()
    from ..esign_seal_confirmation import access_error
    error = access_error(actor, report)
    if error:
        raise EsignServiceError("forbidden", error)
    if not source_flow_id or not source_sha256:
        raise EsignServiceError("seal_confirmation_required", "请刷新当前签发文件后进行签章确认")
    version_id = report.approved_document_version_id or report.current_document_version_id
    if not version_id:
        raise EsignServiceError("approved_pdf_missing", "报告尚无批准版本")
    flows = ReportEsignFlow.query.filter_by(
        report_id=report.id, report_document_version_id=version_id
    ).order_by(ReportEsignFlow.attempt_no.desc(), ReportEsignFlow.id.desc()).all()
    all_attempts = [row.attempt_no for row in flows]
    flows = [row for row in flows if row.id >= current_app.config["ESIGN_PROVIDER_FLOW_MIN_ID"]]
    for row in flows:
        if _flow_kind(row) == FLOW_KIND_ORGANIZATION_SEAL and row.status in (
            ACTIVE_FLOW_STATUSES | COMPLETED_FLOW_STATUSES | {"failed"}
        ):
            state = _organization_seal_state(row)
            confirmation = state.get("confirmation") or {}
            if (row.id != flows[0].id or confirmation.get("sourceFlowId") != source_flow_id
                    or confirmation.get("sourceSha256") != source_sha256):
                raise EsignServiceError("seal_confirmation_stale", "签署文件已变化，请刷新后重新确认")
            return row
    source = next((
        row for row in flows
        if _flow_kind(row) != FLOW_KIND_ORGANIZATION_SEAL
        and row.status in COMPLETED_FLOW_STATUSES
        and row.signed_file_id
        and row.signed_sha256
    ), None)
    if not source:
        raise EsignServiceError(
            "personal_signing_incomplete", "全部人员签署尚未形成有效的最终 PDF，不能补盖组织章"
        )
    if (source.id != source_flow_id or source.signed_sha256 != source_sha256
            or not flows or flows[0].id != source.id):
        raise EsignServiceError("seal_confirmation_stale", "签署文件或流程轮次已变化，请刷新后重新确认")
    expected_roles = {role[0] for role in report_signer_roles(report, source.document_version)}
    if {s.role_code for s in source.signers} != expected_roles or any(s.status != "signed" for s in source.signers):
        raise EsignServiceError("personal_signing_incomplete", "全部人员签字完成后才能确认盖章")
    _reconcile_second_chief(source, actor)
    if flow_has_organization_seal(source):
        raise EsignServiceError("organization_seal_already_included", "该签署流程已经包含组织盖章")
    signed_pdf = read_file_bytes(source.signed_file)
    digest = hashlib.sha256(signed_pdf).hexdigest() if signed_pdf else ""
    if not signed_pdf or digest != source.signed_sha256:
        raise EsignServiceError("signed_source_hash_mismatch", "人员签署 PDF 缺失或哈希不一致")
    attempt = max(all_attempts, default=0) + 1
    flow = ReportEsignFlow(
        report_id=report.id,
        report_no=report.report_no,
        report_document_version_id=version_id,
        attempt_no=attempt,
        status="ready",
        source_sha256=digest,
        positioning_json=json.dumps({
            "flowKind": FLOW_KIND_ORGANIZATION_SEAL,
            "status": "pending",
            "sourceFlowId": source.id,
            "sourceSignedFileId": source.signed_file_id,
            "sourceSha256": digest,
            "organizationSeal": {
                "included": True,
                "status": "ready",
                "confirmationRequired": True,
                "confirmation": {"userId": actor.id, "account": actor.account, "userName": actor.name,
                    "confirmedAt": datetime.utcnow().isoformat(timespec="microseconds"),
                    "documentVersionId": version_id, "sourceFlowId": source.id,
                    "sourceSha256": digest},
                "sealMode": "default" if not str(current_app.config.get("ESIGN_ORG_SEAL_ID") or "").strip() else "assigned",
                "normalSealScope": "report_homepage_only",
                "acrossPageMode": "ALL",
            },
        }, ensure_ascii=False, separators=(",", ":")),
        created_by_id=getattr(actor, "id", None),
    )
    db.session.add(flow)
    db.session.flush()
    add_operation_audit(
        "report.esign.organization_seal.confirm", "report", report.report_no,
        category="integration",
        after={"flowId": flow.id, "sourceFlowId": source.id, "status": flow.status},
        message="签章人已确认当前人员签署文件，准备盖章，人员无需重签", actor=actor,
    )
    db.session.commit()
    return flow


def issuance_blocker(report: Report) -> str | None:
    if not current_app.config.get("ESIGN_REQUIRED_FOR_ISSUANCE"):
        return None
    version_id = report.approved_document_version_id or report.current_document_version_id
    flow = (
        ReportEsignFlow.query.filter_by(report_id=report.id, report_document_version_id=version_id)
        .order_by(ReportEsignFlow.attempt_no.desc()).first()
    ) if version_id else None
    if flow and flow.id < int(current_app.config.get("ESIGN_PROVIDER_FLOW_MIN_ID", 0)):
        return "历史沙箱签署不能作为正式签发依据，请重新准备正式签署任务"
    if not flow:
        return "尚未生成电子签发任务，请先检查主检、审核、批准人员绑定"
    person_flow = flow
    if _flow_kind(flow) == FLOW_KIND_ORGANIZATION_SEAL:
        person_flow = db.session.get(ReportEsignFlow, _positioning_snapshot(flow).get("sourceFlowId"))
    if person_flow:
        second_ref = _second_chief_reference(report, person_flow.document_version)
        if _reference_present(second_ref):
            second = _user_from_reference(second_ref)
            if not second or not any(s.role_code == "chief2" and s.user_id == second.id and s.status == "signed" for s in person_flow.signers):
                return "批准版本选择了主检2，但主检2尚未完成签署，不能确认报告签发"
    if flow.status not in COMPLETED_FLOW_STATUSES:
        return f"电子签署尚未完成（当前：{flow.status}），不能确认报告签发"
    if not flow_has_organization_seal(flow):
        return "人员签署已完成，但组织专用章和骑缝章尚未完成，不能确认报告签发"
    return None


def _content_md5(data: bytes) -> str:
    return base64.b64encode(hashlib.md5(data).digest()).decode("ascii")


class EsignV3Client:
    def __init__(self) -> None:
        from ..esign_production import require_ready
        require_ready()
        self.base_url = str(current_app.config.get("ESIGN_BASE_URL") or "").rstrip("/")
        self.app_id = str(current_app.config.get("ESIGN_APP_ID") or "")
        self.app_secret = str(current_app.config.get("ESIGN_APP_SECRET") or "")
        self.timeout = int(current_app.config.get("ESIGN_HTTP_TIMEOUT_SECONDS") or 30)
        if not self.base_url or not self.app_id or not self.app_secret:
            raise EsignServiceError("provider_not_configured", "e签宝服务端凭据尚未完整配置")

    def _headers(self, method: str, path_and_query: str, body: bytes | None) -> dict[str, str]:
        # Keep the signed Content-Type byte-for-byte identical to the proven
        # e签宝 V3 sandbox request format.
        content_type = "application/json; charset=UTF-8" if body is not None else ""
        content_md5 = _content_md5(body) if body is not None else ""
        canonical = "\n".join([method.upper(), "*/*", content_md5, content_type, "", urllib.parse.unquote(path_and_query)])
        signature = base64.b64encode(hmac.new(
            self.app_secret.encode(), canonical.encode(), hashlib.sha256
        ).digest()).decode("ascii")
        headers = {
            "Accept": "*/*", "X-Tsign-Open-App-Id": self.app_id,
            "X-Tsign-Open-Auth-Mode": "Signature",
            "X-Tsign-Open-Ca-Timestamp": str(int(time.time() * 1000)),
            "X-Tsign-Open-Ca-Signature": signature,
        }
        if body is not None:
            headers.update({"Content-Type": content_type, "Content-MD5": content_md5})
        return headers

    def request(self, method: str, path: str, payload: dict | None = None, query=None) -> dict:
        from ..esign_production import request_payload
        payload = request_payload(method, path, payload)
        pairs = sorted(query or [])
        path_and_query = path + (("?" + urllib.parse.urlencode(pairs)) if pairs else "")
        body = None if payload is None else json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path_and_query, data=body,
            headers=self._headers(method, path_and_query, body), method=method.upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            import socket
            if method == 'POST' and path.endswith('/signers/sign-fields') and (
                    isinstance(getattr(exc, 'reason', None), (ConnectionRefusedError, socket.gaierror))
                    or isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 422}):
                raise EsignServiceError("provider_unavailable", f"追加请求未受理：{exc}", {"notSent": True}) from exc
            raise EsignServiceError("provider_unavailable", f"e签宝接口不可用：{exc}") from exc
        if result.get("code") != 0:
            raise EsignServiceError(str(result.get("code") or "provider_error"), str(result.get("message") or "e签宝调用失败"))
        return result.get("data") or {}

    def upload_pdf(self, name: str, data: bytes) -> str:
        md5_value = _content_md5(data)
        result = self.request("POST", "/v3/files/file-upload-url", {
            "contentMd5": md5_value, "contentType": "application/pdf",
            "convertToPDF": False, "fileName": name, "fileSize": len(data),
        })
        file_id, upload_url = result["fileId"], result["fileUploadUrl"]
        request = urllib.request.Request(
            upload_url, data=data,
            headers={"Content-MD5": md5_value, "Content-Type": "application/pdf"}, method="PUT",
        )
        with urllib.request.urlopen(request, timeout=max(60, self.timeout)) as response:
            upload_result = json.loads(response.read().decode("utf-8"))
        if upload_result.get("errCode") not in (None, 0):
            raise EsignServiceError("upload_failed", "电子签署 PDF 上传失败")
        for _ in range(60):
            state = self.request("GET", f"/v3/files/{file_id}")
            if state.get("fileStatus") in (2, 5):
                return file_id
            if state.get("fileStatus") in (3, 9, 12):
                raise EsignServiceError("upload_processing_failed", "电子签署 PDF 处理失败")
            time.sleep(2)
        raise EsignServiceError("upload_timeout", "电子签署 PDF 上传状态确认超时")

    def keyword_positions(self, file_id: str, keywords: list[str]) -> list[dict[str, Any]]:
        result = self.request(
            "POST", f"/v3/files/{file_id}/keyword-positions", {"keywords": keywords}
        )
        rows = result.get("keywordPositions") or []
        if not isinstance(rows, list):
            raise EsignServiceError("keyword_position_invalid", "e签宝返回的关键字坐标格式无效")
        return [row for row in rows if isinstance(row, dict)]

    def seal_position_url(
        self, file_id: str, custom_biz_num: str, signer_roles: list[str]
    ) -> str:
        payload: dict[str, Any] = {
            "customBizNum": custom_biz_num,
            "fileId": file_id,
            "signerRoles": signer_roles,
            "clientType": "ALL",
            "signFieldType": [1],
            "urlType": 2,
        }
        redirect_url = str(current_app.config.get("ESIGN_POSITIONING_REDIRECT_URL") or "").strip()
        if redirect_url:
            payload["redirectUrl"] = redirect_url
        result = self.request("POST", "/v3/files/get-seal-position-url", payload)
        url = str(result.get("getSealPositionUrl") or "").strip()
        if not url:
            raise EsignServiceError("positioning_url_missing", "e签宝未返回拖章定位页面")
        return url

    def download_signed_pdf(self, provider_flow_id: str) -> bytes:
        result = self.request(
            "POST", f"/v3/sign-flow/{provider_flow_id}/file-download-url",
            {"urlAvailableDate": 3600},
        )
        files = result.get("files") or []
        if not files or not files[0].get("downloadUrl"):
            raise EsignServiceError("signed_file_missing", "e签宝未返回已签署文件")
        try:
            with urllib.request.urlopen(files[0]["downloadUrl"], timeout=max(60, self.timeout)) as response:
                return response.read()
        except urllib.error.URLError as exc:
            raise EsignServiceError("signed_file_download_failed", "已签署文件下载失败") from exc


POSITION_TARGET_LABELS = {
    "chief": "主检",
    "chief2": "主检2",
    "reviewer": "审核",
    "approver": "批准",
    "cover": "企业章",
    "date": "日期章",
}
MANUAL_ROLE_TARGETS = {label: key for key, label in POSITION_TARGET_LABELS.items()}
DEFAULT_POSITION_KEYWORDS = {
    "chief": ["主检", "Chief Tester", "ChiefTester"],
    "reviewer": ["审核", "Verification"],
    "approver": ["批准", "Approval"],
    "cover": ["检验检测专用章", "Seal"],
    "date": ["签发日期", "报告日期", "Date"],
}
REPORT_LAYOUT_KEYWORDS = {
    "zh": {
        "chief": ["主检"],
        "reviewer": ["审核"],
        "approver": ["批准"],
        "cover": ["检验检测专用章"],
        "date": ["签发日期", "报告日期"],
    },
    "en": {
        "chief": ["Chief Tester", "ChiefTester"],
        "reviewer": ["Verification"],
        "approver": ["Approval"],
        "cover": ["Seal"],
        "date": ["Date"],
    },
}
DEFAULT_POSITION_OFFSETS = {
    "chief": {"offsetX": 95, "offsetY": 0},
    "reviewer": {"offsetX": 95, "offsetY": 0},
    "approver": {"offsetX": 95, "offsetY": 0},
    "cover": {"offsetX": 20, "offsetY": -55},
    "date": {"offsetX": 30, "offsetY": 0},
}
# The report homepage is bilingual even when the Chinese anchors win layout
# selection.  A personal sign field is 72 px wide, so the old 70 px offset
# could still let its left edge touch the longer English labels underneath
# (especially "Verification" and "Chief Tester").  Keep a 95 px minimum for
# either anchor language; it clears both label rows while remaining inside
# each of the three signature cells on the standard homepage.
MIN_SIGNATURE_RIGHT_OFFSETS = {"zh": 95.0, "en": 95.0}


def _config_object(name: str, default: dict[str, Any]) -> dict[str, Any]:
    value = current_app.config.get(name) or {}
    if isinstance(value, str):
        try:
            value = json.loads(value) if value else {}
        except json.JSONDecodeError as exc:
            raise EsignServiceError("positioning_config_invalid", f"{name} 不是有效 JSON") from exc
    if not isinstance(value, dict):
        raise EsignServiceError("positioning_config_invalid", f"{name} 必须为 JSON 对象")
    return {**default, **value}


def _required_position_targets(flow: ReportEsignFlow | None = None) -> list[str]:
    if flow is not None and _flow_kind(flow) == FLOW_KIND_ORGANIZATION_SEAL:
        return ["cover", "date"]
    targets = ["chief", "reviewer", "approver"]
    if flow is not None and any(s.role_code == "chief2" for s in getattr(flow, "signers", ())):
        targets.insert(1, "chief2")
    if current_app.config.get("ESIGN_ORG_AUTOSIGN_ENABLED"):
        targets.extend(["cover", "date"])
    return targets


def _valid_position(page: Any, x: Any, y: Any) -> dict[str, Any] | None:
    try:
        page_number = int(page)
        x_value, y_value = float(x), float(y)
    except (TypeError, ValueError):
        return None
    if page_number <= 0 or not math.isfinite(x_value) or not math.isfinite(y_value):
        return None
    return {
        "positionPage": str(page_number),
        "positionX": round(x_value, 3),
        "positionY": round(y_value, 3),
    }


def _coordinates_for_keywords(
    rows: list[dict[str, Any]], keywords: list[str]
) -> list[dict[str, Any]]:
    expected = set(keywords)
    coordinates: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float]] = set()
    for row in rows:
        keyword = str(row.get("keyword") or "")
        if keyword not in expected or not row.get("searchResult"):
            continue
        for position in row.get("positions") or []:
            if not isinstance(position, dict):
                continue
            for coordinate in position.get("coordinates") or []:
                if not isinstance(coordinate, dict):
                    continue
                parsed = _valid_position(
                    position.get("pageNum"), coordinate.get("positionX"), coordinate.get("positionY")
                )
                if parsed:
                    key = (
                        parsed["positionPage"],
                        parsed["positionX"],
                        parsed["positionY"],
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    parsed["keyword"] = keyword
                    for name in ("pdfBounds", "pageSize", "pageRotation"):
                        if name in coordinate:
                            parsed[name] = coordinate[name]
                    coordinates.append(parsed)
    return coordinates


def _report_homepage_layout(
    rows: list[dict[str, Any]], keyword_sets: dict[str, dict[str, list[str]]]
) -> dict[str, Any]:
    """Locate the unique report homepage from five mutually reinforcing anchors.

    The seal/date pair must be above the three horizontally aligned signature
    labels.  This rejects repeated words in fixed notices and body text without
    relying on the homepage always having a hard-coded PDF page number.
    """
    page_candidates: dict[int, list[dict[str, Any]]] = {}
    for language, groups in keyword_sets.items():
        grouped = {
            target: _coordinates_for_keywords(rows, keywords)
            for target, keywords in groups.items()
        }
        common_pages = set.intersection(*(
            {int(row["positionPage"]) for row in coordinates}
            for coordinates in grouped.values()
        )) if grouped else set()
        for page in sorted(common_pages):
            per_page = {
                target: [
                    row for row in coordinates
                    if int(row["positionPage"]) == page
                ]
                for target, coordinates in grouped.items()
            }
            layouts: list[tuple[float, dict[str, dict[str, Any]]]] = []
            for approver, reviewer, chief, cover, date in product(
                per_page["approver"], per_page["reviewer"], per_page["chief"],
                per_page["cover"], per_page["date"],
            ):
                ax, rx, cx = (float(row["positionX"]) for row in (approver, reviewer, chief))
                signature_y = [float(row["positionY"]) for row in (approver, reviewer, chief)]
                cover_x, cover_y = float(cover["positionX"]), float(cover["positionY"])
                date_x, date_y = float(date["positionX"]), float(date["positionY"])
                average_signature_y = sum(signature_y) / 3
                left_gap, right_gap = rx - ax, cx - rx
                if not (left_gap >= 40 and right_gap >= 40):
                    continue
                if max(signature_y) - min(signature_y) > 32:
                    continue
                if not (20 <= cover_y - average_signature_y <= 220):
                    continue
                if cover_x < rx or abs(cover_x - date_x) > 140 or abs(cover_y - date_y) > 80:
                    continue
                score = (
                    (max(signature_y) - min(signature_y)) * 10
                    + abs(left_gap - right_gap)
                    + abs(cover_x - date_x)
                    + abs(cover_y - date_y)
                )
                layouts.append((score, {
                    "approver": approver, "reviewer": reviewer, "chief": chief,
                    "cover": cover, "date": date,
                }))
            if layouts:
                score, anchors = min(layouts, key=lambda item: item[0])
                page_candidates.setdefault(page, []).append({
                    "page": page, "language": language, "score": round(score, 3),
                    "anchors": anchors,
                })
    if not page_candidates:
        raise EsignServiceError(
            "keyword_position_layout_missing",
            "未找到同时满足盖章日期区及批准、审核、主检签字区结构的报告首页，已阻止发起",
        )
    if len(page_candidates) != 1:
        raise EsignServiceError(
            "keyword_position_layout_ambiguous",
            "多个页面同时满足签章结构，无法唯一判断报告首页，已阻止发起",
            {"candidatePages": sorted(page_candidates)},
        )
    page = next(iter(page_candidates))
    # Chinese labels are preferred on bilingual reports; pure-English reports
    # naturally fall back to the English anchor set.
    candidates = sorted(
        page_candidates[page], key=lambda row: (row["language"] != "zh", row["score"])
    )
    return candidates[0]


def _manual_positions(flow: ReportEsignFlow, file_id: str, targets: list[str]) -> dict[str, Any] | None:
    try:
        snapshot = json.loads(flow.positioning_json or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(snapshot, dict) or snapshot.get("mode") != "manual":
        return None
    if snapshot.get("sourceSha256") != flow.source_sha256 or snapshot.get("providerFileId") != file_id:
        return None
    positions = snapshot.get("positions") or {}
    if not isinstance(positions, dict) or any(target not in positions for target in targets):
        return None
    normalized = {target: _valid_position(
        positions[target].get("positionPage"),
        positions[target].get("positionX"),
        positions[target].get("positionY"),
    ) for target in targets if isinstance(positions.get(target), dict)}
    return normalized if len(normalized) == len(targets) and all(normalized.values()) else None


def _resolve_sign_positions(
    client: EsignV3Client, flow: ReportEsignFlow, file_id: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    targets = _required_position_targets(flow)
    initial_snapshot = _positioning_snapshot(flow)
    manual = _manual_positions(flow, file_id, targets)
    if manual:
        snapshot = json.loads(flow.positioning_json)
        snapshot.update({"status": "resolved", "resolvedAt": datetime.utcnow().isoformat(timespec="seconds")})
        return manual, snapshot

    from .calibration_layout import calibration_positions
    pdf = _flow_source_pdf(flow)
    try:
        calibration = calibration_positions(pdf)
    except ValueError as exc:
        raise EsignServiceError("calibration_layout_invalid", str(exc)) from exc
    if calibration:
        positions, layout = calibration
        return positions, {**initial_snapshot, **layout, "mode":"pdf-layout",
            "status":"resolved", "provider":"esign", "providerFileId":file_id,
            "resolvedAt":datetime.utcnow().isoformat(timespec="seconds")}

    configured_keywords = _config_object("ESIGN_POSITION_KEYWORDS", DEFAULT_POSITION_KEYWORDS)
    configured_offsets = _config_object("ESIGN_POSITION_OFFSETS", DEFAULT_POSITION_OFFSETS)
    all_keywords: list[str] = []
    for target in ("chief", "reviewer", "approver", "cover", "date"):
        raw = configured_keywords.get(target) or []
        candidates = raw if isinstance(raw, list) else [raw]
        candidates = [str(value).strip() for value in candidates if str(value or "").strip()]
        if not candidates:
            raise EsignServiceError(
                "positioning_config_invalid", f"{POSITION_TARGET_LABELS[target]}未配置定位关键字"
            )
        for keyword in candidates:
            if keyword not in all_keywords:
                all_keywords.append(keyword)
    # A legacy environment may still override ESIGN_POSITION_KEYWORDS with the
    # old single-keyword configuration.  Layout anchors are mandatory for the
    # joint spatial decision and therefore must always be included in the
    # PDF search; configured values remain additive for compatibility.
    for groups in REPORT_LAYOUT_KEYWORDS.values():
        for keywords in groups.values():
            for keyword in keywords:
                if keyword not in all_keywords:
                    all_keywords.append(keyword)
    from .report_signature_layout import keyword_positions, signature_position
    rows = keyword_positions(pdf, all_keywords)
    selected_layout = _report_homepage_layout(rows, REPORT_LAYOUT_KEYWORDS)
    required_page = int(selected_layout["page"])
    selected_language = str(selected_layout["language"])
    selected_anchors = selected_layout["anchors"]
    resolved: dict[str, dict[str, Any]] = {}
    evidence: dict[str, Any] = {}
    for target in targets:
        if target == "chief2":
            continue
        chosen = selected_anchors[target]
        offset = configured_offsets.get(target) or {}
        if not isinstance(offset, dict):
            raise EsignServiceError("positioning_config_invalid", f"{target} 偏移量配置无效")
        try:
            offset_x = float(offset.get("offsetX") or 0)
            offset_y = float(offset.get("offsetY") or 0)
        except (TypeError, ValueError) as exc:
            raise EsignServiceError("positioning_config_invalid", f"{target} 偏移量必须为数字") from exc
        configured_offset_x = offset_x
        if target in {"chief", "reviewer", "approver"}:
            # Preserve the existing horizontal clearance. The PDF label bounds
            # below also clear wider labels and determine the actual row centre.
            offset_x = max(offset_x, MIN_SIGNATURE_RIGHT_OFFSETS.get(selected_language, 95.0))
        final = {
            "positionPage": chosen["positionPage"],
            "positionX": chosen["positionX"],
            "positionY": chosen["positionY"],
        }
        final["positionX"] = round(float(chosen["positionX"]) + offset_x, 3)
        final["positionY"] = round(float(chosen["positionY"]) + offset_y, 3)
        geometry = None
        if target in {"chief", "reviewer", "approver"}:
            labels = _coordinates_for_keywords(rows, [
                word for groups in REPORT_LAYOUT_KEYWORDS.values() for word in groups[target]
            ])
            next_target = {"approver": "reviewer", "reviewer": "chief"}.get(target)
            next_x = (float(selected_anchors[next_target]["positionX"]) if next_target
                      else float(chosen["pageSize"][2]))
            try:
                final, geometry = signature_position(chosen, labels, next_x, offset_x, offset_y)
            except ValueError as exc:
                raise EsignServiceError("report_signature_layout_invalid", str(exc)) from exc
        resolved[target] = final
        evidence[target] = {
            "label": POSITION_TARGET_LABELS[target],
            "keyword": chosen.get("keyword") or "",
            "providerPosition": chosen,  # Legacy key consumed by organization positioning.
            "configuredOffset": {"offsetX": configured_offset_x, "offsetY": offset_y},
            "offset": {"offsetX": round(final["positionX"] - chosen["positionX"], 3),
                       "offsetY": round(final["positionY"] - chosen["positionY"], 3)},
            "finalPosition": final,
            "geometry": geometry,
        }
    preserved = {
        key: initial_snapshot[key]
        for key in (
            "flowKind", "signingMode", "sourceFlowId", "sourceSignedFileId",
            "sourceSha256", "organizationSeal", "dispatchState",
        )
        if key in initial_snapshot
    }
    snapshot = {
        **preserved,
        "mode": "keyword",
        "method": "pdf-signature-label-bounds-v1",
        "status": "resolved",
        "provider": "esign",
        "providerFileId": file_id,
        "sourceSha256": flow.source_sha256,
        "requiredPage": required_page,
        "layoutLanguage": selected_language,
        "layoutScore": selected_layout["score"],
        "resolvedAt": datetime.utcnow().isoformat(timespec="seconds"),
        "positions": resolved,
        "evidence": evidence,
    }
    return resolved, snapshot


def _sign_field(
    file_id: str, report_no: str, signer: ReportEsignSigner, position: dict[str, Any], size: float = 72
) -> dict:
    return {
        "customBizNum": f"{report_no}-{signer.role_code.upper()}",
        "fileId": file_id,
        "normalSignFieldConfig": {
            "autoSign": False, "signFieldSize": size, "signFieldStyle": 1,
            "psnSealStyles": "0,1", "signFieldPosition": position,
        },
    }


def _organization_signer(
    file_id: str,
    report_no: str,
    positions: dict[str, dict[str, Any]],
    *,
    force: bool = False,
    sign_order: int = 4,
) -> dict | None:
    if not force and not current_app.config.get("ESIGN_ORG_AUTOSIGN_ENABLED"):
        return None
    from .report_seal_layout import HOMEPAGE_SEAL_SIZE, SEAL_SIZE
    org_id = str(current_app.config.get("ESIGN_ORG_ID") or "").strip()
    report_homepage_seal = positions["cover"]
    across_y = float(current_app.config.get("ESIGN_ACROSS_SEAL_POSITION_Y") or 420)
    assigned_seal_id = str(current_app.config.get("ESIGN_ORG_SEAL_ID") or "").strip()
    normal_cfg = {
        "autoSign": True,
        "signFieldSize": HOMEPAGE_SEAL_SIZE,
        "signFieldStyle": 1,
        "signFieldPosition": report_homepage_seal,
    }
    if assigned_seal_id:
        normal_cfg["assignedSealId"] = assigned_seal_id
    if "titleCover" not in positions:
        raise EsignServiceError("cover_seal_missing", "未完成封面公司名称盖章定位，已阻止发起")
    fields = [{
        "customBizNum": f"{report_no}-TITLE-COVER-SEAL",
        "fileId": file_id,
        "normalSignFieldConfig": {**normal_cfg, "signFieldSize": SEAL_SIZE,
                                  "signFieldPosition": positions["titleCover"]},
    }, {
        "customBizNum": f"{report_no}-REPORT-SEAL",
        "fileId": file_id,
        "normalSignFieldConfig": normal_cfg,
    }]
    if positions["titleCover"] == positions["cover"]:
        # Calibration has one combined cover/signature page: one seal only.
        fields = [fields[1]]
    across_cfg = {
        "autoSign": True, "signFieldStyle": 2, "signFieldSize": SEAL_SIZE,
        "signFieldPosition": {"acrossPageMode": "ALL", "positionY": across_y},
    }
    if assigned_seal_id:
        across_cfg["assignedSealId"] = assigned_seal_id
    fields.append({"customBizNum": f"{report_no}-ACROSS-SEAL", "fileId": file_id, "normalSignFieldConfig": across_cfg})
    signer = {
        "signConfig": {"signOrder": sign_order},
        "signerType": 1,
        "signFields": fields,
    }
    # For the AppId owner's own organization, eSign explicitly recommends
    # omitting orgSignerInfo so the provider resolves the authenticated app's
    # enterprise and default seal.  An explicit orgId remains available for a
    # separately authorized organization; orgName is retained only as local
    # display/configuration metadata and is not sent for owner auto-signing.
    if org_id:
        signer["orgSignerInfo"] = {"orgId": org_id}
    return signer


def _flow_source_pdf(flow: ReportEsignFlow) -> bytes:
    if _flow_kind(flow) == FLOW_KIND_ORGANIZATION_SEAL:
        snapshot = _positioning_snapshot(flow)
        try:
            source_flow_id = int(snapshot.get("sourceFlowId"))
            source_file_id = int(snapshot.get("sourceSignedFileId"))
        except (TypeError, ValueError) as exc:
            raise EsignServiceError(
                "organization_seal_source_invalid", "组织补章任务缺少人员签署来源"
            ) from exc
        source = db.session.get(ReportEsignFlow, source_flow_id)
        if (
            not source
            or source.report_id != flow.report_id
            or source.report_document_version_id != flow.report_document_version_id
            or source.status not in COMPLETED_FLOW_STATUSES
            or source.signed_file_id != source_file_id
            or not source.signed_file
        ):
            raise EsignServiceError(
                "organization_seal_source_invalid", "组织补章来源与已完成人员签署文件不一致"
            )
        pdf = read_file_bytes(source.signed_file)
    else:
        version = db.session.get(ReportDocumentVersion, flow.report_document_version_id)
        pdf = read_file_bytes(version.pdf_file, version.pdf_data) if version else b""
    if not pdf or hashlib.sha256(pdf).hexdigest() != flow.source_sha256:
        raise EsignServiceError("source_hash_mismatch", "签署 PDF 文件缺失或哈希与锁定版本不一致")
    return pdf


def _require_dispatch_access(flow, actor):
    from .esign_stages import is_staged
    if is_staged(flow):
        error = flow_state_error(flow)
        if actor is not None:
            from ..esign_access import report_scope_error
            from ..authorization_scope import project_step_error
            error = error or report_scope_error(actor, flow.report) or project_step_error(actor, flow.report, 'data_entry', '主检')
        if error:
            raise EsignServiceError('forbidden', error)
        return
    if _flow_kind(flow) == FLOW_KIND_ORGANIZATION_SEAL:
        from ..esign_seal_confirmation import access_error
        error = access_error(actor, flow.report) or flow_state_error(flow)
        if error:
            raise EsignServiceError("forbidden", error)
        confirmation = _organization_seal_state(flow).get("confirmation") or {}
        if (not confirmation.get("userId") or confirmation.get("documentVersionId") != flow.report_document_version_id
                or confirmation.get("sourceSha256") != flow.source_sha256
                or confirmation.get("sourceFlowId") != _positioning_snapshot(flow).get("sourceFlowId")):
            raise EsignServiceError("seal_confirmation_required", "尚无当前版本的签章确认，不允许自动盖章")
    else:
        error = manager_flow_error(actor, flow) if actor is not None else flow_state_error(flow)
        if error:
            raise EsignServiceError("forbidden", error)


def positioning_url_for_flow(flow_id: int, actor: User | None = None) -> dict[str, Any]:
    from ..esign_production import require_flow
    require_flow(flow_id)
    flow = db.session.get(ReportEsignFlow, flow_id)
    if not flow:
        raise EsignServiceError("flow_not_found", "电子签发任务不存在")
    Report.query.filter_by(id=flow.report_id).with_for_update().populate_existing().one()
    flow = ReportEsignFlow.query.filter_by(id=flow_id).with_for_update().populate_existing().one()
    _require_dispatch_access(flow, actor)
    if flow.status == 'dispatching' or not definitely_uncreated(flow):
        raise EsignServiceError('dispatch_outcome_unknown', '请先核实原签署流程，不能重新校准位置')
    if flow.status in COMPLETED_FLOW_STATUSES | {"signing"}:
        raise EsignServiceError("positioning_not_editable", "已发起或已完成的签署流程不能重新校准位置")
    if not (current_app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED") or current_app.config.get("ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED")):
        raise EsignServiceError("external_side_effects_disabled", "当前环境已关闭真实第三方签署调用")
    if not current_app.config.get("ESIGN_ENABLED"):
        raise EsignServiceError("esign_disabled", "e签宝集成开关尚未启用")
    pdf = _flow_source_pdf(flow)
    client = EsignV3Client()
    file_id = flow.provider_file_id or client.upload_pdf(f"{flow.report_no}.pdf", pdf)
    flow.provider_file_id = file_id
    set_phase(flow, 'preparing')
    custom_biz_num = f"REPORT-POS-{flow.id}-{flow.source_sha256[:12]}"
    roles = [POSITION_TARGET_LABELS[target] for target in _required_position_targets(flow)]
    url = client.seal_position_url(file_id, custom_biz_num, roles)
    existing_snapshot = _positioning_snapshot(flow)
    preserved = {
        key: existing_snapshot[key]
        for key in (
            "flowKind", "signingMode", "sourceFlowId", "sourceSignedFileId",
            "sourceSha256", "organizationSeal", "dispatchState",
        )
        if key in existing_snapshot
    }
    flow.positioning_json = json.dumps({
        **preserved,
        "mode": "manual",
        "status": "awaiting_callback",
        "provider": "esign",
        "providerFileId": file_id,
        "sourceSha256": flow.source_sha256,
        "customBizNum": custom_biz_num,
        "requiredTargets": _required_position_targets(flow),
        "requestedAt": datetime.utcnow().isoformat(timespec="seconds"),
    }, ensure_ascii=False, separators=(",", ":"))
    add_operation_audit(
        "report.esign.positioning.manual.request", "report", flow.report_no,
        category="integration", after={"flowId": flow.id, "customBizNum": custom_biz_num},
        message="已获取e签宝人工拖章校准页面", actor=actor,
    )
    db.session.commit()
    return {"url": url, "customBizNum": custom_biz_num, "expiresInHours": 24}


def store_manual_positioning(body: dict[str, Any]) -> ReportEsignFlow | None:
    custom_biz_num = str(body.get("customBizNum") or "")
    match = re.fullmatch(r"REPORT-POS-(\d+)-([0-9a-fA-F]{12})", custom_biz_num)
    if not match:
        return None
    flow = db.session.get(ReportEsignFlow, int(match.group(1)))
    if not flow or flow.source_sha256[:12].lower() != match.group(2).lower():
        return None
    Report.query.filter_by(id=flow.report_id).with_for_update().populate_existing().one()
    flow = ReportEsignFlow.query.filter_by(id=flow.id).with_for_update().populate_existing().one()
    from ..internal_report_corrections import is_historical_flow
    if is_historical_flow(flow) or flow.status in {'cancelled', 'cancelling'}:
        return flow
    if flow.status in COMPLETED_FLOW_STATUSES | {"signing"}:
        return flow
    if flow.status == 'dispatching' or not definitely_uncreated(flow):
        return flow
    positions: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for component in body.get("components") or []:
        if not isinstance(component, dict) or str(component.get("componentType")) != "6":
            continue
        target = MANUAL_ROLE_TARGETS.get(str(component.get("signerRole") or ""))
        if not target:
            continue
        if target in positions:
            duplicates.add(target)
            continue
        if flow.provider_file_id and str(component.get("fileId") or "") != flow.provider_file_id:
            continue
        raw = component.get("componentPosition") or {}
        parsed = _valid_position(
            raw.get("componentPageNum"), raw.get("componentPositionX"), raw.get("componentPositionY")
        ) if isinstance(raw, dict) else None
        if parsed:
            positions[target] = parsed
    required = _required_position_targets(flow)
    missing = [target for target in required if target not in positions]
    if duplicates or missing:
        labels = [POSITION_TARGET_LABELS[target] for target in sorted(duplicates | set(missing))]
        flow.status = "failed"
        flow.error_code = "manual_position_incomplete"
        flow.error_message = "人工拖章坐标不完整或重复：" + "、".join(labels)
        status = "invalid"
    else:
        flow.status = "ready"
        flow.error_code = None
        flow.error_message = None
        status = "resolved"
    existing_snapshot = _positioning_snapshot(flow)
    preserved = {
        key: existing_snapshot[key]
        for key in (
            "flowKind", "signingMode", "sourceFlowId", "sourceSignedFileId",
            "sourceSha256", "organizationSeal", "dispatchState",
        )
        if key in existing_snapshot
    }
    flow.positioning_json = json.dumps({
        **preserved,
        "mode": "manual",
        "status": status,
        "provider": "esign",
        "providerFileId": flow.provider_file_id,
        "sourceSha256": flow.source_sha256,
        "customBizNum": custom_biz_num,
        "positions": positions,
        "receivedAt": datetime.utcnow().isoformat(timespec="seconds"),
    }, ensure_ascii=False, separators=(",", ":"))
    add_operation_audit(
        "report.esign.positioning.manual.callback", "report", flow.report_no,
        category="integration", after={"flowId": flow.id, "status": status, "targets": sorted(positions)},
        message="已接收e签宝人工拖章坐标",
    )
    db.session.commit()
    return flow


def dispatch_flow(flow_id: int, actor: User | None = None) -> ReportEsignFlow:
    # Serialize identity maintenance and duplicate dispatch before any provider call.
    from ..esign_production import require_flow
    require_flow(flow_id)
    initial = db.session.get(ReportEsignFlow, flow_id)
    if initial:
        Report.query.filter_by(id=initial.report_id).with_for_update().populate_existing().one()
    user_ids = [s.user_id for s in ReportEsignSigner.query.filter_by(flow_id=flow_id).all() if s.user_id]
    initial_flow = db.session.get(ReportEsignFlow, flow_id)
    if initial_flow and _flow_kind(initial_flow) != FLOW_KIND_ORGANIZATION_SEAL:
        second = _user_from_reference(_second_chief_reference(initial_flow.report, initial_flow.document_version))
        if second:
            user_ids.append(second.id)
    if user_ids:
        User.query.filter(User.id.in_(user_ids)).order_by(User.id).with_for_update().populate_existing().all()
    flow = ReportEsignFlow.query.filter_by(id=flow_id).with_for_update().populate_existing().first()
    if flow and flow.status == "dispatching":
        raise EsignServiceError("dispatch_in_progress", "签署已在处理中，请先刷新或核实上游结果，不重复发起")
    if flow and flow.provider_flow_id and flow.status not in COMPLETED_FLOW_STATUSES | {"signing"}:
        raise EsignServiceError("provider_flow_exists", "已有上游签署流程，必须先核实原流程状态；不能重复创建")
    # These errors are proven before create-by-file, or an explicit rejected
    # request. A timeout/crash/unknown provider outcome remains blocked.
    if (flow and not flow.provider_flow_id and flow.status == "failed"
            and not definitely_uncreated(flow)):
        raise EsignServiceError("dispatch_outcome_unknown", "曾上传签署文件但发起结果待核实，请人工核查后重试；不盲目重发")
    if not flow:
        raise EsignServiceError("flow_not_found", "电子签发任务不存在")
    _require_dispatch_access(flow, actor)
    from .esign_stages import is_staged
    staged = is_staged(flow)
    # This includes retries with an uploaded file ID; never reuse an old upload
    # against changed business inputs. Existing signed bytes are not rewritten.
    from .. import docparser_field_only
    if staged or docparser_field_only.applies_to(flow.report):
        from ..report_version_consistency import require_reviewed_document
        try:
            if staged:
                from ..report_version_consistency import require_current_document
                require_current_document(flow.report, flow.document_version)
            if not staged:
                require_reviewed_document(flow.report, flow.document_version, record_legacy=True, actor=actor)
        except ValueError as exc:
            raise EsignServiceError('document_version_stale', str(exc)) from exc
    if _flow_kind(flow) != FLOW_KIND_ORGANIZATION_SEAL and not staged:
        from ..report_issue_dates import prepare_dispatch_date
        try:
            prepare_dispatch_date(flow, actor)
        except ValueError as exc:
            raise EsignServiceError('issue_date_invalid', str(exc)) from exc
    if not staged:
        _reconcile_second_chief(flow, actor)
    if _flow_kind(flow) != FLOW_KIND_ORGANIZATION_SEAL and not staged:
        expected = {r[0] for r in report_signer_roles(flow.report, flow.document_version)}
        if {s.role_code for s in flow.signers} != expected:
            raise EsignServiceError("binding_required", "签署人员不完整，请补齐人员并重新准备任务")
    if flow.status in COMPLETED_FLOW_STATUSES | {"signing"} and flow.provider_flow_id:
        return flow
    if not (current_app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED") or current_app.config.get("ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED")):
        raise EsignServiceError("external_side_effects_disabled", "当前环境已关闭真实第三方签署调用")
    if not current_app.config.get("ESIGN_ENABLED"):
        raise EsignServiceError("esign_disabled", "e签宝集成开关尚未启用")
    organization_only = _flow_kind(flow) == FLOW_KIND_ORGANIZATION_SEAL
    if organization_only and flow.signers:
        raise EsignServiceError("organization_seal_signers_invalid", "组织补章任务不能包含个人签署人")
    if not organization_only:
        for signer in flow.signers:
            binding = EsignIdentityBinding.query.filter_by(user_id=signer.user_id).first()
            if not binding or binding.status not in {"pending", "verified"}:
                raise EsignServiceError("binding_required", f"{signer.role_name}人员尚未完成e签宝身份绑定")
            signer.binding_id = binding.id
            signer.legal_name_snapshot = binding.legal_name
            signer.psn_id_snapshot = binding.psn_id
            signer.status = "pending"
    pdf = _flow_source_pdf(flow)

    flow.status = "dispatching"
    flow.error_code = None
    flow.error_message = None
    set_phase(flow, 'preparing')
    db.session.commit()
    provider_file_id = str(flow.provider_file_id or "")
    create_requested = False
    try:
        client = EsignV3Client()
        provider_file_id = provider_file_id or client.upload_pdf(f"{flow.report_no}.pdf", pdf)
        flow.provider_file_id = provider_file_id
        db.session.commit()
        positions, positioning_snapshot = _resolve_sign_positions(client, flow, provider_file_id)
        if staged:
            from .esign_stages import locate_date
            positioning_snapshot['businessStages'] = _positioning_snapshot(flow)['businessStages']
            positioning_snapshot['businessStages']['datePosition'] = locate_date(flow, positions)
        if any(s.role_code == "chief2" for s in flow.signers):
            from .dual_chief_layout import dual_chief_positions
            try:
                positions, sizes, geometry = dual_chief_positions(
                    pdf, positions, manual=positioning_snapshot.get("mode") == "manual")
            except ValueError as exc:
                raise EsignServiceError("dual_chief_layout_invalid", str(exc)) from exc
            positioning_snapshot.update(positions=positions, fieldSizes=sizes, dualChiefGeometry=geometry)
        if organization_only:
            if positioning_snapshot.get("layoutKind") == "calibration":
                positioning_snapshot["organizationGeometry"] = {"method":"calibration-single-homepage", "normalSealCount":1}
            else:
                from .report_seal_layout import organization_positions
                provider_anchor = ((positioning_snapshot.get("evidence") or {}).get("cover") or {}).get("providerPosition")
                # A manual snapshot has no label evidence. Obtain fresh keyword
                # anchors to validate the two required automatic organization seals.
                if not provider_anchor:
                    anchor_rows = client.keyword_positions(provider_file_id, list(dict.fromkeys(
                        word for groups in REPORT_LAYOUT_KEYWORDS.values() for words in groups.values() for word in words
                    )))
                    provider_anchor = _report_homepage_layout(anchor_rows, REPORT_LAYOUT_KEYWORDS)["anchors"]["cover"]
                try:
                    org_positions, org_evidence = organization_positions(pdf, provider_anchor)
                except Exception as exc:
                    raise EsignServiceError("organization_seal_layout_invalid", "组织盖章定位失败：" + str(exc)) from exc
                positions.update(org_positions)
                positioning_snapshot["positions"] = positions
                positioning_snapshot["organizationGeometry"] = org_evidence
        signers_payload = []
        if not organization_only:
            for signer in flow.signers:
                binding = signer.binding
                psn_info = {"psnId": binding.psn_id} if binding.psn_id else {
                    "psnAccount": binding.psn_account, "psnInfo": {"psnName": binding.legal_name},
                }
                signers_payload.append({
                    "signConfig": {"signOrder": signer.sign_order},
                    "noticeConfig": {"noticeTypes": "1" if current_app.config.get("ESIGN_INITIAL_SMS_ENABLED") else ""},
                    "signerType": 0, "psnSignerInfo": psn_info,
                    "signFields": [_sign_field(
                        provider_file_id, flow.report_no, signer, positions[signer.role_code],
                        (positioning_snapshot.get("fieldSizes") or {}).get(signer.role_code, 72)
                    )],
                })
        organization = _organization_signer(
            provider_file_id,
            flow.report_no,
            positions,
            force=organization_only,
            sign_order=1,
        ) if organization_only else None
        if organization:
            signers_payload.append(organization)
        organization_state = positioning_snapshot.get("organizationSeal") or {}
        if not organization_only:
            organization_state = {"included": False, "status": "awaiting_personal_signatures", "confirmationRequired": True}
        if organization:
            organization_state.update({
                "included": True,
                "status": "signing",
                "sealMode": "assigned" if str(current_app.config.get("ESIGN_ORG_SEAL_ID") or "").strip() else "default",
                "normalSealPage": positions["cover"]["positionPage"],
                "normalSealScope": "title_cover_and_report_homepage",
                "titleCoverSealPage": positions["titleCover"]["positionPage"],
                "acrossPageMode": "ALL",
            })
        positioning_snapshot["flowKind"] = (
            FLOW_KIND_ORGANIZATION_SEAL if organization_only else FLOW_KIND_PERSON
        )
        positioning_snapshot["organizationSeal"] = organization_state
        positioning_snapshot["notificationMode"] = (
            "provider-native-v1" if not organization_only and current_app.config.get("ESIGN_INITIAL_SMS_ENABLED")
            else "manual")
        flow.positioning_json = json.dumps(
            positioning_snapshot, ensure_ascii=False, separators=(",", ":")
        )
        if not organization_only:
            from .esign_unified import MODE
            positioning_snapshot["signingMode"] = MODE
            flow.positioning_json = json.dumps(positioning_snapshot, ensure_ascii=False)
        # Persist policy before create: a timed-out request must not become legacy.
        set_phase(flow, 'preparing')
        db.session.commit()
        payload = {
            "docs": [{"fileId": provider_file_id, "fileName": f"{flow.report_no}.pdf"}],
            "signFlowConfig": {
                "signFlowTitle": (
                    f"{flow.report_no} 确认后组织盖章"
                    if organization_only else f"{flow.report_no} 检测报告签发"
                ),
                "autoStart": True, "autoFinish": organization_only,
                "noticeConfig": {"noticeTypes": ""},
                "notifyUrl": current_app.config.get("ESIGN_CALLBACK_PUBLIC_URL") or None,
            },
            "signers": signers_payload,
        }
        payload["signFlowConfig"] = {k: v for k, v in payload["signFlowConfig"].items() if v is not None}
        # Persist BEFORE the network boundary: a timeout or crash after this
        # point must never be mistaken for a local preparation failure.
        set_phase(flow, 'create_requested')
        db.session.commit()
        create_requested = True
        result = client.request("POST", "/v3/sign-flow/create-by-file", payload)
        flow.provider_file_id = provider_file_id
        flow.provider_flow_id = result["signFlowId"]
        flow.status = "signing"
        flow.dispatched_at = datetime.utcnow()
        set_phase(flow, 'created')
        add_operation_audit(
            "report.esign.organization_seal.dispatch" if organization_only else "report.esign.dispatch",
            "report", flow.report_no, category="integration",
            after={
                "flowId": flow.id,
                "providerFlowId": flow.provider_flow_id,
                "status": flow.status,
                "sealMode": organization_state.get("sealMode") if organization else None,
            },
            actor=actor,
        )
        db.session.commit()
        return flow
    except Exception as exc:
        db.session.rollback()
        flow = db.session.get(ReportEsignFlow, flow_id)
        # A successful create may have been committed by downstream auditing.
        # Never erase evidence of an existing remote flow.
        phase = 'created' if flow.provider_flow_id else ('create_requested' if create_requested else 'preparing')
        if create_requested and isinstance(exc, EsignServiceError) and exc.code == '1435002' and not flow.provider_flow_id:
            phase = 'rejected'
        set_phase(flow, phase)
        if provider_file_id:
            flow.provider_file_id = provider_file_id
        flow.status = "failed"
        error_code = exc.code if isinstance(exc, EsignServiceError) else (
            'dispatch_outcome_unknown' if create_requested else 'dispatch_preparation_failed')
        flow.error_code, flow.error_message = error_code, str(exc)[:500]
        failed_snapshot = _positioning_snapshot(flow)
        if organization_only:
            seal_state = failed_snapshot.get("organizationSeal") or {}
            if not isinstance(seal_state, dict):
                seal_state = {}
            seal_state.update({"included": True, "status": "failed"})
            failed_snapshot["flowKind"] = FLOW_KIND_ORGANIZATION_SEAL
            failed_snapshot["organizationSeal"] = seal_state
        if error_code.startswith("keyword_position") or error_code == "positioning_config_invalid":
            failed_snapshot.update({
                "mode": "keyword",
                "status": "failed",
                "provider": "esign",
                "providerFileId": provider_file_id,
                "sourceSha256": flow.source_sha256,
                "errorCode": error_code,
                "errorMessage": str(exc)[:500],
                "details": getattr(exc, 'details', {}),
                "failedAt": datetime.utcnow().isoformat(timespec="seconds"),
            })
        flow.positioning_json = json.dumps(
            failed_snapshot, ensure_ascii=False, separators=(",", ":")
        )
        db.session.commit()
        raise


def sign_url_for_user(flow: ReportEsignFlow, user: User) -> dict[str, str]:
    from ..esign_production import require_flow
    require_flow(flow.id)
    signers = ReportEsignSigner.query.filter_by(flow_id=flow.id, user_id=user.id).order_by(ReportEsignSigner.sign_order).all()
    signer = next((s for s in signers if s.status in {"pending", "signing"}), None)
    if not signer or signer.status not in {"pending", "signing"}:
        raise EsignServiceError("sign_task_not_found", "当前账号没有该报告的待签任务")
    error = signer_access_error(user, flow, signer, actionable=True)
    if error:
        raise EsignServiceError("project_step_forbidden", error)
    if not flow.provider_flow_id:
        raise EsignServiceError("provider_flow_missing", "电子签署流程尚未发起")
    binding = signer.binding
    operator = {"psnId": binding.psn_id} if binding and binding.psn_id else {
        "psnAccount": binding.psn_account if binding else ""
    }
    data = EsignV3Client().request(
        "POST", f"/v3/sign-flow/{flow.provider_flow_id}/sign-url",
        {"clientType": "ALL", "needLogin": True, "operator": operator, "urlType": 2},
    )
    return {"url": data.get("url") or "", "shortUrl": data.get("shortUrl") or ""}


def batch_sign_url_for_user(
    user: User,
    flow_ids: list[int] | None = None,
    *,
    notify_sms: bool = False,
) -> dict[str, object]:
    query = (
        db.session.query(ReportEsignFlow, ReportEsignSigner)
        .join(ReportEsignSigner, ReportEsignSigner.flow_id == ReportEsignFlow.id)
        .filter(
            ReportEsignSigner.user_id == user.id,
            ReportEsignSigner.status.in_(("pending", "signing")),
            ReportEsignFlow.status == "signing",
            ReportEsignFlow.provider_flow_id.is_not(None),
        )
    )
    if flow_ids:
        query = query.filter(ReportEsignFlow.id.in_(flow_ids))
    rows = query.order_by(ReportEsignFlow.id).limit(1000).all()
    rows = [
        (flow, signer)
        for flow, signer in rows
        if flow.id >= int(current_app.config.get("ESIGN_PROVIDER_FLOW_MIN_ID") or 0)
        and not signer_access_error(user, flow, signer, actionable=True)
    ]
    if not rows:
        raise EsignServiceError("no_pending_tasks", "当前账号没有可批量签署的报告")
    binding = EsignIdentityBinding.query.filter_by(user_id=user.id).first()
    if not binding:
        raise EsignServiceError("binding_required", "当前账号尚未绑定e签宝身份")
    if binding.status not in {"pending", "verified"}:
        raise EsignServiceError("binding_invalid", "绑定已停用或失效，请核实身份")
    if not binding.psn_id or binding.status != "verified":
        identity = EsignV3Client().request(
            "GET", "/v3/persons/identity-info", query=[("psnAccount", binding.psn_account)]
        )
        info = identity.get("psnInfo") or {}
        if (not isinstance(info, dict) or info.get("psnName") != binding.legal_name
                or str(identity.get("realnameStatus")) != "1" or not identity.get("psnId")):
            raise EsignServiceError("identity_not_verified", "尚不能核实名册姓名及实名认证状态，请先同步或完成本人认证")
        binding.psn_id = identity["psnId"]
        binding.last_checked_at = datetime.utcnow()
        binding.status = "verified"
        binding.verified_at = binding.verified_at or datetime.utcnow()
        db.session.commit()
    if not binding.psn_id:
        raise EsignServiceError("psn_id_missing", "e签宝尚未返回该人员的个人账号ID")
    provider_ids = list(dict.fromkeys(flow.provider_flow_id for flow, _signer in rows))
    result = EsignV3Client().request("POST", "/v3/sign-flow/batch-sign-url", {
        "operatorId": binding.psn_id,
        "signFlowIds": provider_ids,
        "noticeTypes": "1" if notify_sms else "",
        "redirectUrl": current_app.config.get("ESIGN_BATCH_REDIRECT_URL") or None,
    })
    return {
        "count": len(provider_ids), "flowIds": list(dict.fromkeys(flow.id for flow, _signer in rows)), "batchSerialId": result.get("batchSerialId") or "",
        "url": result.get("batchSignUrl") or "",
        "shortUrl": result.get("batchSignShortUrl") or "",
    }


def _sequential_sms_channel(flow_id: int, sign_order: int) -> str:
    channel = f"step:{flow_id}:{sign_order}"
    if len(channel) <= 20:
        return channel
    token = hashlib.sha256(f"{flow_id}:{sign_order}".encode()).hexdigest()[:12]
    return f"step:{token}"


def _ordinary_sms_operator(flow, signer, binding, detail):
    # Use the immutable role in THIS flow, not a person-directory lookup.
    error = signer_access_error(signer.user, flow, signer, actionable=True)
    if error:
        raise EsignServiceError("signer_not_actionable", error)
    if (binding.id != signer.binding_id or binding.status not in {"pending", "verified"}
            or binding.legal_name != signer.legal_name_snapshot
            or not signer.user.enabled or binding.legal_name != signer.user.name):
        raise EsignServiceError("signer_binding_changed", "当前人员与发起时的签署身份不一致，请核对人员绑定")
    matches = [p for p in detail.get("signers", [])
        if p.get("signerType") == 0 and str(p.get("signOrder")) == str(signer.sign_order)
        and any(x.get("customBizNum") == flow.report_no + "-" + signer.role_code.upper()
                for x in p.get("signFields", []))]
    if len(matches) != 1:
        raise EsignServiceError("provider_signer_unmatched", "无法唯一匹配当前报告签署人，请先刷新签署状态")
    person = matches[0].get("psnSigner") or {}
    if person.get("psnName") and person["psnName"] != signer.legal_name_snapshot:
        raise EsignServiceError("provider_signer_mismatch", "e签宝流程人员姓名与报告签署人不一致")
    if signer.psn_id_snapshot:
        if person.get("psnId") != signer.psn_id_snapshot or binding.psn_id != signer.psn_id_snapshot:
            raise EsignServiceError("provider_signer_mismatch", "e签宝流程人员身份与报告签署人不一致")
        return {"psnId": signer.psn_id_snapshot}
    account = (person.get("psnAccount") or {}).get("accountMobile")
    if not account or account != binding.psn_account:
        raise EsignServiceError("provider_signer_mismatch", "e签宝流程手机号与绑定信息不一致，请先核对")
    return {"psnAccount": account}


def _ordinary_sms_preflight(flow, signer, binding):
    client = EsignV3Client()
    detail = client.request("GET", f"/v3/sign-flow/{flow.provider_flow_id}/detail")
    if str(detail.get("signFlowStatus")) != "1":
        raise EsignServiceError("provider_not_signing", "e签宝流程已不在签署中，请刷新签署状态")
    operator = _ordinary_sms_operator(flow, signer, binding, detail)
    started = detail.get("signFlowStartTime") or detail.get("signFlowCreateTime")
    if not started:
        raise EsignServiceError("provider_time_missing", "无法核对流程发起时间，请先刷新签署状态")
    wait = 1800 - (time.time() - float(started) / 1000)
    if wait > 0:
        raise EsignServiceError("urge_cooldown", f"e签宝要求发起满30分钟后才可重发短信，约{int(wait / 60) + 1}分钟后再试；本人可先从我的签署进入")
    return client, {"noticeTypes": "1", "urgedOperator": operator}


def send_initial_sms_notifications(
    flow_id: int,
    actor: User | None = None,
    *,
    retry_failed: bool = False,
) -> dict[str, object]:
    """Provider-native initial/sequential SMS; targeted ordinary-flow reminders.

    Reading personal identity information is not a notification prerequisite.
    Provider signing still requires the signer's own verification and consent.
    """
    from ..esign_production import require_flow
    require_flow(flow_id)
    if not current_app.config.get("ESIGN_INITIAL_SMS_ENABLED"):
        raise EsignServiceError("esign_sms_disabled", "e签宝签署短信开关尚未启用")

    flow = db.session.get(ReportEsignFlow, flow_id)
    if not flow:
        raise EsignServiceError("flow_not_found", "电子签发任务不存在")
    if flow.status != "signing" or not flow.provider_flow_id:
        raise EsignServiceError("flow_not_signing", "电子签署流程尚未发起或已结束")
    error = manager_flow_error(actor, flow) if actor is not None else flow_state_error(flow)
    if error:
        raise EsignServiceError("forbidden", error)
    pending_signers = [
        signer for signer in flow.signers
        if signer.status in {"pending", "signing"}
    ]
    next_order = min((signer.sign_order for signer in pending_signers), default=None)
    eligible_signers = [
        signer for signer in pending_signers if signer.sign_order == next_order
    ]
    deferred_signers = [
        signer for signer in pending_signers if signer.sign_order != next_order
    ]

    recipients: dict[int, dict[str, object]] = {}
    for signer in eligible_signers:
        row = recipients.setdefault(signer.user_id, {
            "user": signer.user,
            "userId": signer.user_id,
            "userName": signer.user.name if signer.user else signer.legal_name_snapshot,
            "roles": [],
        })
        row["roles"].append(signer.role_name)

    deferred_users: dict[int, dict[str, object]] = {}
    for signer in deferred_signers:
        row = deferred_users.setdefault(signer.user_id, {
            "userId": signer.user_id,
            "userName": signer.user.name if signer.user else signer.legal_name_snapshot,
            "roles": [],
            "status": "deferred",
            "code": "waiting_previous_signer",
            "message": "前序签署完成后将自动发送有效签署短信",
        })
        row["roles"].append(signer.role_name)

    channel = _sequential_sms_channel(flow.id, int(next_order or 0))
    summary: dict[str, object] = {
        "flowId": flow.id,
        "reportNo": flow.report_no,
        "eligible": len(recipients),
        "nextSignOrder": next_order,
        "sent": 0,
        "skipped": 0,
        "deferred": len(deferred_users),
        "failed": [],
        "recipients": [],
        "providerManaged": 0,
    }
    for row in recipients.values():
        user = row["user"]
        recipient = {
            "userId": row["userId"],
            "userName": row["userName"],
            "roles": row["roles"],
        }
        if not user:
            recipient.update({"status": "failed", "code": "user_not_found", "message": "签署人员账号不存在"})
            summary["failed"].append({"userId": row["userId"], "code": "user_not_found"})
            summary["recipients"].append(recipient)
            continue

        binding = EsignIdentityBinding.query.filter_by(user_id=user.id).first()
        if not binding or binding.psn_account_kind != "mobile":
            recipient.update({"status": "failed", "code": "mobile_binding_required", "message": "未绑定可接收短信的手机号"})
            summary["failed"].append({"userId": user.id, "code": "mobile_binding_required"})
            summary["recipients"].append(recipient)
            continue

        if _positioning_snapshot(flow).get("notificationMode") == "provider-native-v1":
            summary["skipped"] += 1
            summary["providerManaged"] += 1
            recipient.update({"status": "skipped", "code": "provider_managed_notification",
                "message": "已随签署流程配置e签宝顺序短信通知，本次不重复发送；短信送达以e签宝结果为准"})
            summary["recipients"].append(recipient)
            continue

        # Serialize notification claims for this flow before inspecting the log.
        db.session.query(ReportEsignFlow).filter_by(id=flow.id).with_for_update().populate_existing().one()
        existing = EsignReminderLog.query.filter_by(
            user_id=user.id, channel=channel,
        ).order_by(EsignReminderLog.id.desc()).first()
        if existing and (
            existing.status in {"created", "sending", "unknown"}
            or existing.status == "sent"
            or (existing.status == "failed" and not retry_failed)
        ):
            summary["skipped"] += 1
            recipient.update({
                "status": "skipped",
                "code": "already_sent" if existing.status == "sent" else "already_processing",
                "message": "e签宝已受理短信请求" if existing.status == "sent" else "短信正在处理或发送结果待核对，本次不重复发送",
            })
            summary["recipients"].append(recipient)
            continue

        try:
            signer = next(s for s in eligible_signers if s.user_id == user.id)
            client, sms_payload = _ordinary_sms_preflight(flow, signer, binding)
        except EsignServiceError as exc:
            summary["failed"].append({"userId": user.id, "code": exc.code})
            recipient.update({"status": "failed", "code": exc.code, "message": str(exc)})
            summary["recipients"].append(recipient)
            db.session.commit()
            continue

        log = existing or EsignReminderLog(
            user_id=user.id,
            reminder_date=date.today().isoformat(),
            channel=channel,
            pending_count=1,
        )
        log.reminder_date = date.today().isoformat()
        log.pending_count = 1
        log.status = "sending"
        log.error_message = None
        if not existing:
            db.session.add(log)
        db.session.commit()
        try:
            # Provider validates the current turn and enforces its 10-minute cooldown.
            client.request("POST", f"/v3/sign-flow/{flow.provider_flow_id}/urge", sms_payload)
            log.batch_serial_id = None
            log.status = "sent"
            summary["sent"] += 1
            recipient.update({
                "status": "sent",
                "code": "",
                "message": "e签宝已受理短信发送请求",
            })
        except EsignServiceError as exc:
            # A timeout does not prove that SMS was not sent; never auto-retry it.
            log.status = "unknown" if exc.code == "provider_unavailable" else "failed"
            log.error_message = f"{exc.code}: {str(exc)}"[:300]
            summary["failed"].append({"userId": user.id, "code": exc.code})
            recipient.update({"status": "failed", "code": exc.code, "message": str(exc)})
        db.session.commit()
        summary["recipients"].append(recipient)

    summary["recipients"].extend(deferred_users.values())

    add_operation_audit(
        "report.esign.sms.notify_next",
        "report",
        flow.report_no,
        category="integration",
        after={
            "flowId": flow.id,
            "eligible": summary["eligible"],
            "sent": summary["sent"],
            "skipped": summary["skipped"],
            "deferred": summary["deferred"],
            "nextSignOrder": summary["nextSignOrder"],
            "failed": summary["failed"],
        },
        actor=actor,
        message="已通知当前顺序电子签署人员",
    )
    db.session.commit()
    return summary


def signer_project_access_error(user: User, flow: ReportEsignFlow, signer: ReportEsignSigner) -> str:
    """Compatibility entry: current identity, report scope and project role."""
    return signer_access_error(user, flow, signer)


def store_signed_file(flow: ReportEsignFlow, data: bytes, actor: User | None = None) -> None:
    digest = hashlib.sha256(data).hexdigest()
    stored = persist_bytes(
        data, category="esign_report", original_name=f"{flow.report_no}-signed.pdf",
        content_type="application/pdf", created_by=getattr(actor, "account", "esign-callback"),
    )
    flow.signed_file_id = stored.id
    flow.signed_sha256 = digest
    flow.status = "completed"
    flow.completed_at = datetime.utcnow()
    snapshot = _positioning_snapshot(flow)
    seal_state = snapshot.get("organizationSeal") or {}
    if isinstance(seal_state, dict) and not seal_state.get("included"):
        seal_state.update({"included": False, "status": "awaiting_confirmation", "confirmationRequired": True})
        snapshot["organizationSeal"] = seal_state
        flow.positioning_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    if isinstance(seal_state, dict) and seal_state.get("included"):
        seal_state.update({
            "status": "completed",
            "completedAt": flow.completed_at.isoformat(timespec="seconds"),
        })
        snapshot["organizationSeal"] = seal_state
        flow.positioning_json = json.dumps(
            snapshot, ensure_ascii=False, separators=(",", ":")
        )
    for signer in flow.signers:
        signer.status = "signed"
        signer.signed_at = signer.signed_at or datetime.utcnow()
    db.session.flush()
    from ..report_delivery import mark_sealed
    mark_sealed(flow.report, flow, actor)


def verify_callback_signature(raw_body: bytes, headers, query_values: list[str]) -> bool:
    secret = str(current_app.config.get("ESIGN_APP_SECRET") or "")
    app_id = str(current_app.config.get("ESIGN_APP_ID") or "")
    if not secret or not app_id or headers.get("X-Tsign-Open-App-Id") != app_id:
        return False
    timestamp = str(headers.get("X-Tsign-Open-TIMESTAMP") or "")
    signature = str(headers.get("X-Tsign-Open-SIGNATURE") or "")
    try:
        if abs(int(time.time() * 1000) - int(timestamp)) > int(current_app.config.get("ESIGN_CALLBACK_MAX_SKEW_SECONDS", 300)) * 1000:
            return False
    except ValueError:
        return False
    canonical = timestamp.encode() + "".join(query_values).encode() + raw_body
    digest = hmac.new(secret.encode(), canonical, hashlib.sha256).digest()
    # Current eSign callback documentation emits a hexadecimal HMAC-SHA256
    # string.  Older integrations have also returned the same digest as
    # Base64, so accept both encodings while still comparing the exact digest.
    expected_hex = digest.hex()
    expected_base64 = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected_hex, signature.lower()) or hmac.compare_digest(
        expected_base64, signature
    )

# esign-production-v1
