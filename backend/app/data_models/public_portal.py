"""Persistent models for the customer-facing service portal.

These tables deliberately do not reuse the internal ``users`` table.  A
public token therefore cannot accidentally become an employee token, and a
public application remains an immutable source record after it is accepted
into the internal workflow.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..extensions import db
from ..models import JSONText


def _money(value):
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else value


def _list(value):
    return value if isinstance(value, list) else []


def _structured(value):
    return value if isinstance(value, (dict, list)) else {}


class ExternalAccount(db.Model):
    __tablename__ = "external_accounts"
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    mobile = db.Column(db.String(40), unique=True, index=True)
    email = db.Column(db.String(160), unique=True, index=True)
    company_name = db.Column(db.String(200))
    unified_social_credit_code = db.Column(db.String(40))
    enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    verified_at = db.Column(db.DateTime)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_public_dict(self):
        return {
            "id": self.id,
            "account": self.account,
            "name": self.name,
            "mobile": self.mobile or "",
            "email": self.email or "",
            "companyName": self.company_name or "",
            "unifiedSocialCreditCode": self.unified_social_credit_code or "",
        }


class ExternalScheme(db.Model):
    __tablename__ = "external_schemes"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), nullable=False, unique=True, index=True
    )
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    public_title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300))
    summary = db.Column(db.Text)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), index=True)
    cover_url = db.Column(db.String(500))
    # Reproducible public projection of the authoritative project, standard
    # and capability libraries. JSONText remains portable to DM8 CLOB.
    object_key = db.Column(db.String(160), index=True)
    object_name = db.Column(db.String(240), index=True)
    object_aliases = db.Column(JSONText)
    capability_snapshot = db.Column(JSONText)
    capability_hash = db.Column(db.String(64), index=True)
    capability_synced_at = db.Column(db.DateTime)
    image_attribution = db.Column(JSONText)
    auto_generated = db.Column(db.Boolean, nullable=False, default=False)
    price_mode = db.Column(db.String(20), nullable=False, default="quote")
    price_min = db.Column(db.Numeric(14, 2))
    price_max = db.Column(db.Numeric(14, 2))
    price_unit = db.Column(db.String(40))
    original_price = db.Column(db.Numeric(14, 2))
    service_cycle_text = db.Column(db.String(120))
    turnaround_days = db.Column(db.Integer)
    promotion = db.Column(db.String(200))
    featured = db.Column(db.Boolean, nullable=False, default=False)
    detail = db.Column(db.Text)
    sample_requirements = db.Column(db.Text)
    contact_phone = db.Column(db.String(60))
    feature_tags = db.Column(JSONText)
    deliverables = db.Column(JSONText)
    pricing_rules = db.Column(JSONText)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=False, default=1)
    published_at = db.Column(db.DateTime)
    updated_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project = db.relationship("Project")

    def to_public_dict(self, *, detail=False):
        project = self.project
        config = project.workflow_config if project and isinstance(project.workflow_config, dict) else {}
        public_title = self.public_title or (project.name if project else "")
        snapshot = self.capability_snapshot if isinstance(self.capability_snapshot, dict) else {}
        common_items = snapshot.get("items") if isinstance(snapshot.get("items"), list) else []
        qualification_tags = (
            snapshot.get("qualificationTags")
            if isinstance(snapshot.get("qualificationTags"), list)
            else []
        )
        image = self.image_attribution if isinstance(self.image_attribution, dict) else {}
        result = {
            "id": self.id,
            "slug": self.slug,
            "projectId": self.project_id,
            "code": (
                project.display_code or project.number_code or project.code
                if project else ""
            ),
            "name": project.name if project else public_title,
            "publicTitle": public_title,
            "subtitle": self.subtitle or "",
            "summary": self.summary or "",
            "category": self.category or "",
            "coverUrl": self.cover_url or "",
            "objectKey": self.object_key or "",
            "objectName": self.object_name or public_title,
            "commonTestItems": common_items[:6],
            "qualificationTags": qualification_tags,
            "standardCount": int(snapshot.get("standardCount") or 0),
            "capabilityUpdatedAt": (
                self.capability_synced_at.isoformat(timespec="seconds")
                if self.capability_synced_at else ""
            ),
            "capabilityHash": self.capability_hash or "",
            "imageAttribution": {
                "author": image.get("author") or "",
                "sourceUrl": image.get("sourceUrl") or "",
                "license": image.get("license") or "",
                "licenseUrl": image.get("licenseUrl") or "",
            },
            "priceMode": self.price_mode or "quote",
            "priceMin": _money(self.price_min),
            "priceMax": _money(self.price_max),
            "priceUnit": self.price_unit or "",
            "originalPrice": _money(self.original_price),
            "serviceCycleText": self.service_cycle_text or "",
            "turnaroundDays": self.turnaround_days,
            "promotion": self.promotion or "",
            "featured": bool(self.featured),
            "featureTags": _list(self.feature_tags),
            "deliverables": _list(self.deliverables),
            "location": (project.location if project else "") or "",
            "department": (
                project.department.name if project and project.department else ""
            ),
            "publishedAt": self.published_at.isoformat(timespec="seconds") if self.published_at else "",
        }
        if detail:
            result.update({
                "description": self.description or "",
                "detail": self.detail or self.description or "",
                "sampleRequirements": self.sample_requirements or "",
                "contactPhone": self.contact_phone or "",
                "pricingRules": _structured(self.pricing_rules),
                "capability": snapshot,
                "imageAttribution": image,
                "projectSnapshot": {
                    "reportTitle": str(config.get("reportTitle") or ""),
                    "testCategory": str(config.get("testCategory") or ""),
                    "reportType": str(config.get("reportType") or config.get("reportFormat") or ""),
                    "testDept": str(config.get("testDept") or result["department"]),
                    "detectionParameters": str(config.get("detectionParameters") or project.name if project else ""),
                    "sampleAmount": str(config.get("sampleAmount") or ""),
                    "sampleStatus": str(config.get("sampleStatus") or ""),
                    "testLocation": str(config.get("testLocation") or result["location"]),
                },
            })
        return result


class ExternalEntrustApplication(db.Model):
    __tablename__ = "external_entrust_applications"
    __table_args__ = (
        db.UniqueConstraint(
            "external_account_id", "idempotency_key",
            name="uq_external_entrust_account_idempotency",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    application_no = db.Column(db.String(40), nullable=False, unique=True, index=True)
    external_account_id = db.Column(
        db.Integer, db.ForeignKey("external_accounts.id"), nullable=False, index=True
    )
    scheme_id = db.Column(db.Integer, db.ForeignKey("external_schemes.id"), index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), index=True)
    scheme_snapshot = db.Column(JSONText)
    quote_snapshot = db.Column(JSONText)
    estimated_amount = db.Column(db.Numeric(14, 2))
    form_version = db.Column(db.String(20), nullable=False, default="1.0")
    form_data = db.Column(JSONText)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    internal_entrust_id = db.Column(db.Integer, db.ForeignKey("entrusts.id"), unique=True)
    internal_entrust_no = db.Column(db.String(40), unique=True, index=True)
    assigned_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    idempotency_key = db.Column(db.String(120))
    review_note = db.Column(db.Text)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewer_name = db.Column(db.String(80))
    submitted_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    converted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    account = db.relationship("ExternalAccount")
    scheme = db.relationship("ExternalScheme")
    project = db.relationship("Project")
    internal_entrust = db.relationship("Entrust")

    def to_public_dict(self):
        form = self.form_data if isinstance(self.form_data, dict) else {}
        return {
            "id": self.id,
            "applicationNo": self.application_no,
            "status": self.status,
            "schemeId": self.scheme_id,
            "schemeSnapshot": self.scheme_snapshot or {},
            "quoteSnapshot": self.quote_snapshot or {},
            "estimatedAmount": _money(self.estimated_amount),
            "formVersion": str(self.form_version or "1.0"),
            "formData": form,
            "submittedAt": self.submitted_at.isoformat(timespec="seconds") if self.submitted_at else "",
            "reviewedAt": self.reviewed_at.isoformat(timespec="seconds") if self.reviewed_at else "",
            "internalEntrustNo": self.internal_entrust_no or "",
            "reviewNote": self.review_note or "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
            "updatedAt": self.updated_at.isoformat(timespec="seconds") if self.updated_at else "",
        }

    def to_admin_dict(self):
        form = self.form_data if isinstance(self.form_data, dict) else {}
        return {
            "id": self.id,
            "applicationNo": self.application_no,
            "status": self.status,
            "customerName": form.get("contactName") or form.get("consignor") or self.account.name,
            "customerPhone": form.get("contactMobile") or form.get("contactPhone") or form.get("phone") or self.account.mobile or "",
            "companyName": form.get("companyName") or form.get("client") or self.account.company_name or "",
            "projectTitle": form.get("projectName") or (self.scheme_snapshot or {}).get("publicTitle") or "",
            "projectCode": (self.scheme_snapshot or {}).get("code") or "",
            "estimatedAmount": _money(self.estimated_amount),
            "submittedAt": self.submitted_at.isoformat(timespec="seconds") if self.submitted_at else "",
            "formData": form,
            "internalEntrustNo": self.internal_entrust_no or "",
            "note": self.review_note or "",
            "reviewedAt": self.reviewed_at.isoformat(timespec="seconds") if self.reviewed_at else "",
            "reviewerName": self.reviewer_name or "",
        }


class ExternalEntrustEvent(db.Model):
    __tablename__ = "external_entrust_events"
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("external_entrust_applications.id"), nullable=False, index=True
    )
    action = db.Column(db.String(40), nullable=False, index=True)
    from_status = db.Column(db.String(20))
    to_status = db.Column(db.String(20))
    actor_kind = db.Column(db.String(20), nullable=False)
    actor_id = db.Column(db.Integer)
    actor_account = db.Column(db.String(80))
    actor_name = db.Column(db.String(80))
    note = db.Column(db.Text)
    snapshot = db.Column(JSONText)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    application = db.relationship(
        "ExternalEntrustApplication",
        backref=db.backref("events", order_by="ExternalEntrustEvent.id"),
    )


class ExternalCustomerDocument(db.Model):
    """Customer-visible delivery file published against one online application.

    Official report PDFs are resolved directly from ``ReportDocumentVersion``
    and are deliberately not copied into this table.  This model holds the
    remaining fulfilment files, such as certificates and electronic invoices.
    """

    __tablename__ = "external_customer_documents"
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer,
        db.ForeignKey("external_entrust_applications.id"),
        nullable=False,
        index=True,
    )
    kind = db.Column(db.String(24), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    document_no = db.Column(db.String(100), index=True)
    report_no = db.Column(db.String(40), index=True)
    stored_file_id = db.Column(
        db.Integer, db.ForeignKey("stored_files.id"), nullable=False, index=True
    )
    status = db.Column(db.String(20), nullable=False, default="published", index=True)
    issued_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    application = db.relationship(
        "ExternalEntrustApplication",
        backref=db.backref("customer_documents", order_by="ExternalCustomerDocument.id"),
    )
    stored_file = db.relationship("StoredFile", foreign_keys=[stored_file_id])


class ExternalShipment(db.Model):
    """A customer-visible delivery shipment and its latest trace snapshot."""

    __tablename__ = "external_shipments"
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer,
        db.ForeignKey("external_entrust_applications.id"),
        nullable=False,
        index=True,
    )
    shipment_type = db.Column(db.String(30), nullable=False, default="report_delivery")
    carrier = db.Column(db.String(80), nullable=False)
    tracking_no = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    latest_event = db.Column(db.String(300))
    events = db.Column(JSONText)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    created_by = db.Column(db.String(80))
    updated_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    application = db.relationship(
        "ExternalEntrustApplication",
        backref=db.backref("shipments", order_by="ExternalShipment.id"),
    )


class ExternalPortalNotification(db.Model):
    """Persistent in-app notification scoped to exactly one external account."""

    __tablename__ = "external_portal_notifications"
    __table_args__ = (
        db.UniqueConstraint(
            "external_account_id",
            "source_key",
            name="uq_external_portal_notification_source",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    external_account_id = db.Column(
        db.Integer, db.ForeignKey("external_accounts.id"), nullable=False, index=True
    )
    application_id = db.Column(
        db.Integer, db.ForeignKey("external_entrust_applications.id"), index=True
    )
    category = db.Column(db.String(30), nullable=False, default="business", index=True)
    title = db.Column(db.String(160), nullable=False)
    content = db.Column(db.String(500))
    link = db.Column(db.String(300))
    source_key = db.Column(db.String(160))
    read_at = db.Column(db.DateTime, index=True)
    published_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    account = db.relationship("ExternalAccount")
    application = db.relationship("ExternalEntrustApplication")
