"""e签宝身份绑定与报告签发状态。

业务报告仍由 ``Report``/``ReportDocumentVersion`` 管理；这里仅保存第三方签署
流程的最小必要元数据。手机号属于敏感标识，任何 ``to_dict`` 输出都只返回掩码。
"""

from __future__ import annotations

import json
from datetime import datetime

from ..extensions import db


def _utcnow() -> datetime:
    return datetime.utcnow()


class EsignIdentityBinding(db.Model):
    __tablename__ = "esign_identity_bindings"
    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_esign_binding_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    personnel_id = db.Column(db.Integer, db.ForeignKey("personnel.id"), index=True)
    legal_name = db.Column(db.String(60), nullable=False)
    psn_account = db.Column(db.String(160), nullable=False)
    psn_account_kind = db.Column(db.String(16), nullable=False, default="mobile")
    psn_id = db.Column(db.String(80), index=True)
    status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    verified_at = db.Column(db.DateTime)
    last_checked_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
    personnel = db.relationship("Personnel", foreign_keys=[personnel_id])

    @property
    def masked_account(self) -> str:
        value = str(self.psn_account or "")
        if self.psn_account_kind == "mobile" and len(value) >= 7:
            return f"{value[:3]}****{value[-4:]}"
        if "@" in value:
            local, domain = value.split("@", 1)
            return f"{local[:2]}***@{domain}"
        return "***" if value else ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "userId": self.user_id,
            "personnelId": self.personnel_id,
            "account": self.user.account if self.user else "",
            "userName": self.user.name if self.user else self.legal_name,
            "legalName": self.legal_name,
            "psnAccountMasked": self.masked_account,
            "psnAccountKind": self.psn_account_kind,
            "psnId": self.psn_id or "",
            "status": self.status,
            "verifiedAt": self.verified_at.isoformat(timespec="seconds") if self.verified_at else "",
            "lastCheckedAt": self.last_checked_at.isoformat(timespec="seconds") if self.last_checked_at else "",
            "updatedAt": self.updated_at.isoformat(timespec="seconds") if self.updated_at else "",
        }


class ReportEsignFlow(db.Model):
    __tablename__ = "report_esign_flows"
    __table_args__ = (
        db.UniqueConstraint(
            "report_id", "report_document_version_id", "attempt_no",
            name="uq_report_esign_flow_attempt",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("reports.id"), nullable=False, index=True)
    report_no = db.Column(db.String(40), nullable=False, index=True)
    report_document_version_id = db.Column(
        db.Integer, db.ForeignKey("report_document_versions.id"), nullable=False, index=True
    )
    attempt_no = db.Column(db.Integer, nullable=False, default=1)
    provider = db.Column(db.String(20), nullable=False, default="esign")
    provider_file_id = db.Column(db.String(80))
    provider_flow_id = db.Column(db.String(80), unique=True, index=True)
    status = db.Column(db.String(32), nullable=False, default="binding_required", index=True)
    source_sha256 = db.Column(db.String(64), nullable=False)
    signed_file_id = db.Column(db.Integer, db.ForeignKey("stored_files.id"), index=True)
    signed_sha256 = db.Column(db.String(64))
    error_code = db.Column(db.String(80))
    error_message = db.Column(db.String(500))
    positioning_json = db.Column(db.Text)
    dispatched_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    report = db.relationship("Report", foreign_keys=[report_id])
    document_version = db.relationship("ReportDocumentVersion", foreign_keys=[report_document_version_id])
    signed_file = db.relationship("StoredFile", foreign_keys=[signed_file_id])
    signers = db.relationship(
        "ReportEsignSigner", back_populates="flow", cascade="all, delete-orphan",
        order_by="ReportEsignSigner.sign_order",
    )

    def to_dict(self) -> dict[str, object]:
        try:
            positioning = json.loads(self.positioning_json or "{}")
        except (TypeError, ValueError):
            positioning = {}
        positioning = positioning if isinstance(positioning, dict) else {}
        organization_seal = positioning.get("organizationSeal") or {}
        if not isinstance(organization_seal, dict):
            organization_seal = {}
        return {
            "id": self.id,
            "reportNo": self.report_no,
            "documentVersionId": self.report_document_version_id,
            "attemptNo": self.attempt_no,
            "provider": self.provider,
            "providerFlowId": self.provider_flow_id or "",
            "status": self.status,
            "sourceSha256": self.source_sha256,
            "signedSha256": self.signed_sha256 or "",
            "errorCode": self.error_code or "",
            "errorMessage": self.error_message or "",
            "flowKind": str(positioning.get("flowKind") or "person_signing"),
            "signingMode": positioning.get("signingMode", "legacy"),
            "organizationSeal": organization_seal,
            "hasSignedFile": bool(self.signed_file_id),
            "positioning": positioning,
            "dispatchedAt": self.dispatched_at.isoformat(timespec="seconds") if self.dispatched_at else "",
            "completedAt": self.completed_at.isoformat(timespec="seconds") if self.completed_at else "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
            "signers": [row.to_dict() for row in self.signers],
        }


class ReportEsignSigner(db.Model):
    __tablename__ = "report_esign_signers"
    __table_args__ = (
        db.UniqueConstraint("flow_id", "role_code", name="uq_report_esign_signer_role"),
    )

    id = db.Column(db.Integer, primary_key=True)
    flow_id = db.Column(db.Integer, db.ForeignKey("report_esign_flows.id"), nullable=False, index=True)
    role_code = db.Column(db.String(20), nullable=False)
    role_name = db.Column(db.String(30), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    binding_id = db.Column(db.Integer, db.ForeignKey("esign_identity_bindings.id"), index=True)
    legal_name_snapshot = db.Column(db.String(60), nullable=False)
    psn_id_snapshot = db.Column(db.String(80))
    sign_order = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    provider_signer_id = db.Column(db.String(80))
    signed_at = db.Column(db.DateTime)
    error_message = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    flow = db.relationship("ReportEsignFlow", back_populates="signers")
    user = db.relationship("User", foreign_keys=[user_id])
    binding = db.relationship("EsignIdentityBinding", foreign_keys=[binding_id])

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "roleCode": self.role_code,
            "roleName": self.role_name,
            "userId": self.user_id,
            "account": self.user.account if self.user else "",
            "userName": self.user.name if self.user else self.legal_name_snapshot,
            "legalName": self.legal_name_snapshot,
            "bindingStatus": self.binding.status if self.binding else "unbound",
            "signOrder": self.sign_order,
            "status": self.status,
            "signedAt": self.signed_at.isoformat(timespec="seconds") if self.signed_at else "",
            "errorMessage": self.error_message or "",
        }


class EsignReminderLog(db.Model):
    __tablename__ = "esign_reminder_logs"
    __table_args__ = (
        db.UniqueConstraint("user_id", "reminder_date", "channel", name="uq_esign_reminder_user_day"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    reminder_date = db.Column(db.String(10), nullable=False, index=True)
    channel = db.Column(db.String(20), nullable=False, default="sms")
    pending_count = db.Column(db.Integer, nullable=False, default=0)
    batch_serial_id = db.Column(db.String(100))
    provider_message_id = db.Column(db.String(100))
    status = db.Column(db.String(24), nullable=False, default="created")
    error_message = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
