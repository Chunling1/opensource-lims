"""Electronic original-record bounded context.

The employee, department, project and report tables remain authoritative.  ELN
rows only persist configuration, immutable record revisions and short-lived SSO
state; they must never be used as a second permission database.
"""
from __future__ import annotations

from datetime import datetime

from ..extensions import db
from ..models import JSONText


class ElnProjectConfig(db.Model):
    __tablename__ = "eln_project_configs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), nullable=False, unique=True, index=True
    )
    enabled = db.Column(db.Boolean, nullable=False, default=False, index=True)
    effective_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    apply_to_existing = db.Column(db.Boolean, nullable=False, default=False)
    required_templates = db.Column(JSONText)
    min_finalized_records = db.Column(db.Integer, nullable=False, default=1)
    config_version = db.Column(db.Integer, nullable=False, default=1)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ElnRecordTemplate(db.Model):
    __tablename__ = "eln_record_templates"
    __table_args__ = (
        db.UniqueConstraint(
            "project_id", "code", "version", name="uq_eln_template_project_version"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    code = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    version = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="DRAFT", index=True)
    field_schema = db.Column(JSONText)
    config_hash = db.Column(db.String(64), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    published_at = db.Column(db.DateTime)


class ElnLaunchCode(db.Model):
    __tablename__ = "eln_launch_codes"

    id = db.Column(db.Integer, primary_key=True)
    code_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    report_no = db.Column(db.String(40), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ElnTaskPolicy(db.Model):
    __tablename__ = "eln_task_policies"

    id = db.Column(db.Integer, primary_key=True)
    report_no = db.Column(db.String(40), nullable=False, unique=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    required = db.Column(db.Boolean, nullable=False, default=False, index=True)
    config_version = db.Column(db.Integer, nullable=False)
    required_templates = db.Column(JSONText)
    min_finalized_records = db.Column(db.Integer, nullable=False, default=1)
    activated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ElnOriginalRecord(db.Model):
    __tablename__ = "eln_original_records"
    __table_args__ = (
        db.UniqueConstraint("external_id", name="uq_eln_original_record_external_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(64), nullable=False, index=True)
    report_no = db.Column(db.String(40), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("eln_record_templates.id"), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="DRAFT", index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    current_revision_no = db.Column(db.Integer, nullable=False, default=1)
    task_revision = db.Column(db.String(64), nullable=False, index=True)
    pdf_attachment_id = db.Column(db.Integer, db.ForeignKey("report_attachments.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    finalized_at = db.Column(db.DateTime)
    canceled_at = db.Column(db.DateTime)


class ElnRecordRevision(db.Model):
    __tablename__ = "eln_record_revisions"
    __table_args__ = (
        db.UniqueConstraint("record_id", "revision_no", name="uq_eln_record_revision"),
    )

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(
        db.Integer, db.ForeignKey("eln_original_records.id"), nullable=False, index=True
    )
    revision_no = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, default="DRAFT", index=True)
    field_values = db.Column(JSONText)
    result_summary = db.Column(JSONText)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    review_comment = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)

