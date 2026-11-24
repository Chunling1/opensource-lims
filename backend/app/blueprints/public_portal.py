"""Customer-facing portal APIs and the internal external-application queue."""
from __future__ import annotations
from ..workflow_dates import business_today

import base64
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from flask import Blueprint, current_app, g, jsonify, make_response, request
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from ..applications.customer_service import (
    PROCESS_ACTION_GRANTS,
    accept_external_application,
    has_internal_process_access,
    internal_scope_allows,
)
from ..platform.audit import add_operation_audit
from ..platform.identity import (
    project_for_report,
    user_has_org_wide_scope,
    user_has_project_step,
)
from ..extensions import db
from ..functions import ai_provider
from ..functions.portal_assistant import search_customer_resources
from ..functions.service_catalog import public_image_credits
from ..platform.file_vault import persist_stream, read_file_bytes
from ..models import (
    Entrust,
    ExternalAccount,
    ExternalCustomerDocument,
    ExternalEntrustApplication,
    ExternalEntrustEvent,
    ExternalPortalNotification,
    ExternalScheme,
    ExternalShipment,
    FinanceBill,
    OperationAudit,
    Project,
    Report,
    ReportDocumentVersion,
)
from ..platform.numbering import (
    allocate_external_application_number,
)
from ..public_security import issue_external_token, require_external_auth
from ..report_documents import report_values
from ..security import hash_password, needs_rehash, require_auth, verify_password
from ..platform.workflow import report_data_status
from ..storage import StoredFileNotFound

public_bp = Blueprint("public_portal", __name__, url_prefix="/api/public/v1")
admin_external_bp = Blueprint(
    "admin_external_entrustments",
    __name__,
    url_prefix="/api/admin/external-entrustments",
)

ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.@+-]{4,80}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PUBLIC_EDITABLE_STATUSES = {"draft", "rejected"}
PUBLIC_CANCELLABLE_STATUSES = {"draft", "submitted", "rejected"}
INTERNAL_PROCESS_ACTIONS = PROCESS_ACTION_GRANTS
# A report becomes publicly verifiable as soon as the internal approval step
# has completed.  Printing and release are downstream fulfilment steps, so
# restricting public lookup to ``已发放`` incorrectly hides valid approved
# reports while they are waiting to be printed or released.
PUBLIC_REPORT_QUERYABLE_STATUSES = ("待打印", "待发放", "已发放")
PUBLIC_REPORT_WORKFLOW_LABELS = {
    "sample.register.complete": "样品登记完成",
    "report.contract_review.pass": "合同评审通过",
    "sample.inbound.confirm": "样品入库完成",
    "sample.out_warehouse.sign": "样品出库领取完成",
    "report.data_entry.complete": "检测数据录入完成",
    "report.review.pass": "报告审核通过",
    "report.approval.pass": "报告批准通过",
    "report.print.pass": "报告签发完成",
    "report.release.pass": "报告已发放",
    "report.archive.pass": "报告归档完成",
}
PUBLIC_REPORT_WORKFLOW_UNDO = {
    "sample.inbound.undo": "sample.inbound.confirm",
    "sample.register.undo": "sample.register.complete",
    "report.contract_review.undo": "report.contract_review.pass",
    "sample.out_warehouse.return": "sample.out_warehouse.sign",
    "sample.return_stock": "sample.out_warehouse.sign",
    "report.report_check.undo": "report.data_entry.complete",
    "report.review.undo": "report.review.pass",
    "report.approval.undo": "report.approval.pass",
    "report.print.undo": "report.print.pass",
    "report.release.undo": "report.release.pass",
    "report.archive.undo": "report.archive.pass",
}


@public_bp.get("/system/status")
def public_system_status():
    """Expose only non-sensitive UI feature flags to the public portal."""
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "businessReadOnly": bool(
                current_app.config.get("APP_BUSINESS_READ_ONLY")
            ),
            "deploymentRole": current_app.config.get(
                "DEPLOYMENT_ROLE", "standard"
            ),
            "environmentLabel": current_app.config.get(
                "ENVIRONMENT_LABEL", "开源标准版"
            ),
            "releaseId": current_app.config.get("RELEASE_ID", "local"),
        },
    })
PUBLIC_EXTERNAL_EVENT_LABELS = {
    "create": "委托申请已创建",
    "update": "委托资料已更新",
    "submit": "委托申请已提交",
    "resubmit": "委托申请已重新提交",
    "accept": "委托申请已受理",
    "reject": "委托申请已退回",
    "cancel": "委托申请已取消",
}
PUBLIC_DOCUMENT_KINDS = {
    "certificate": "证书文件",
    "invoice": "电子发票",
    "other": "交付文件",
}
PUBLIC_SHIPMENT_STATUS_LABELS = {
    "pending": "待寄出",
    "shipped": "已寄出",
    "in_transit": "运输中",
    "delivering": "派送中",
    "delivered": "已签收",
    "exception": "物流异常",
}
PUBLIC_NOTIFICATION_ACTIONS = {
    "submit": ("委托已提交", "您的委托申请已提交，业务人员将在受理后反馈院内委托编号。"),
    "resubmit": ("委托已重新提交", "补充后的委托资料已重新提交。"),
    "accept": ("委托已受理", "您的在线委托已受理，并已进入院内检测流程。"),
    "reject": ("委托需补充资料", "业务人员已退回该委托，请查看处理意见并补充资料。"),
    "cancel": ("委托已取消", "该在线委托申请已取消。"),
}
CUSTOMER_DOCUMENT_MAX_BYTES = 32 * 1024 * 1024
CUSTOMER_DOCUMENT_ALLOWED_APPLICATION_STATUSES = {"accepted", "processing", "completed"}
CUSTOMER_ASSISTANT_AUDIO_TYPES = {
    "audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/ogg",
}


def _ok(data=None, message="ok"):
    return jsonify({"code": 0, "message": message, "data": data})


def _error(message, status=400, code=1):
    return jsonify({"code": code, "message": message, "data": None}), status


def _customer_assistant_voice_enabled():
    return bool(
        current_app.config.get("AI_ENABLED")
        and current_app.config.get("AI_VOICE_ENABLED")
        and current_app.config.get("AI_BASE_URL")
        and current_app.config.get("AI_API_KEY")
    )


def _customer_assistant_rate_limited(maximum=10):
    since = datetime.utcnow() - timedelta(minutes=1)
    count = OperationAudit.query.filter(
        OperationAudit.account == g.external_account.account,
        OperationAudit.action == "external_portal.ai.transcribe",
        OperationAudit.created_at >= since,
    ).count()
    return count >= maximum


def _text(value):
    return str(value or "").strip()


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _first_value(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, tuple, dict)) and not value:
            continue
        return value.strip() if isinstance(value, str) else value
    return ""


def _iso(value):
    return value.isoformat(timespec="seconds") if value else ""


def _parse_datetime(value):
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _read_customer_file(file_row, legacy=None):
    """Read a customer delivery file without exposing storage failures as 500s."""
    try:
        return read_file_bytes(file_row, legacy)
    except StoredFileNotFound:
        return b""


def _customer_upload_content_type(upload):
    """Validate extension and file signature, returning a canonical media type."""
    name = _text(getattr(upload, "filename", "")).lower()
    expected = (
        (".pdf", b"%PDF-", "application/pdf"),
        (".png", b"\x89PNG\r\n\x1a\n", "image/png"),
        (".jpg", b"\xff\xd8\xff", "image/jpeg"),
        (".jpeg", b"\xff\xd8\xff", "image/jpeg"),
    )
    matched = next((row for row in expected if name.endswith(row[0])), None)
    if not matched:
        return ""
    try:
        head = upload.stream.read(max(len(row[1]) for row in expected))
        upload.stream.seek(0)
    except (AttributeError, OSError, ValueError):
        return ""
    return matched[2] if head.startswith(matched[1]) else ""


def _portal_notification_payload(row):
    return {
        "id": row.id,
        "applicationNo": row.application.application_no if row.application else "",
        "category": row.category or "business",
        "title": row.title or "",
        "content": row.content or "",
        "link": row.link or "",
        "read": bool(row.read_at),
        "readAt": _iso(row.read_at),
        "publishedAt": _iso(row.published_at),
    }


def _customer_document_payload(row):
    file_row = row.stored_file
    application_no = row.application.application_no if row.application else ""
    return {
        "id": f"customer:{row.id}",
        "kind": row.kind,
        "kindLabel": PUBLIC_DOCUMENT_KINDS.get(row.kind, "交付文件"),
        "title": row.title,
        "documentNo": row.document_no or "",
        "reportNo": row.report_no or "",
        "applicationNo": application_no,
        "fileName": file_row.original_name if file_row else "",
        "contentType": file_row.content_type if file_row else "application/octet-stream",
        "sizeBytes": file_row.size_bytes if file_row else 0,
        "sha256": file_row.sha256 if file_row else "",
        "status": "available" if row.status == "published" else row.status,
        "issuedAt": _iso(row.issued_at),
        "publishedAt": _iso(row.published_at),
        "downloadUrl": f"/documents/{row.id}/download" if row.status == "published" else "",
    }


def _shipment_payload(row):
    application_no = row.application.application_no if row.application else ""
    return {
        "id": row.id,
        "applicationNo": application_no,
        "shipmentType": row.shipment_type or "report_delivery",
        "carrier": row.carrier or "",
        "trackingNo": row.tracking_no or "",
        "status": row.status or "pending",
        "statusLabel": PUBLIC_SHIPMENT_STATUS_LABELS.get(row.status, row.status or "待更新"),
        "latestEvent": row.latest_event or "",
        "events": row.events if isinstance(row.events, list) else [],
        "shippedAt": _iso(row.shipped_at),
        "deliveredAt": _iso(row.delivered_at),
        "updatedAt": _iso(row.updated_at),
    }


def _official_report_document_payload(application, report, version):
    file_row = version.pdf_file if version else None
    available = bool(
        version
        and version.output_kind == "official"
        and (version.pdf_file_id or version.pdf_data)
        and _public_report_is_queryable(report)
    )
    return {
        "id": f"report:{report.report_no}",
        "kind": "report",
        "kindLabel": "检测报告",
        "title": f"{report.report_no} 检测报告",
        "documentNo": report.report_no,
        "reportNo": report.report_no,
        "applicationNo": application.application_no,
        "fileName": (
            file_row.original_name
            if file_row
            else f"{report.report_no}-正式报告.pdf"
        ),
        "contentType": "application/pdf",
        "sizeBytes": file_row.size_bytes if file_row else len(version.pdf_data or b"") if version else 0,
        "sha256": version.sha256 if version else "",
        "status": "available" if available else "preparing",
        "issuedAt": _iso(version.created_at) if version else "",
        "publishedAt": _iso(version.created_at) if version else "",
        "downloadUrl": (
            f"/documents/reports/{quote(report.report_no, safe='')}/download"
            if available
            else ""
        ),
    }


def _owned_workspace_rows(account_id):
    return (
        ExternalEntrustApplication.query.filter_by(external_account_id=account_id)
        .order_by(ExternalEntrustApplication.updated_at.desc(), ExternalEntrustApplication.id.desc())
        .all()
    )


def _workspace_report_documents(applications):
    by_entrust = {
        row.internal_entrust_no: row
        for row in applications
        if row.internal_entrust_no
    }
    if not by_entrust:
        return []
    reports = (
        Report.query.filter(Report.entrust_no.in_(list(by_entrust)))
        .order_by(Report.id.desc())
        .all()
    )
    version_ids = [
        row.approved_document_version_id
        for row in reports
        if row.approved_document_version_id
    ]
    versions = {
        row.id: row
        for row in ReportDocumentVersion.query.filter(
            ReportDocumentVersion.id.in_(version_ids)
        ).all()
    } if version_ids else {}
    return [
        _official_report_document_payload(
            by_entrust[report.entrust_no],
            report,
            versions.get(report.approved_document_version_id),
        )
        for report in reports
        if _public_report_is_queryable(report)
    ]


def _workspace_customer_documents(application_ids):
    if not application_ids:
        return []
    rows = (
        ExternalCustomerDocument.query.filter(
            ExternalCustomerDocument.application_id.in_(application_ids),
            ExternalCustomerDocument.status == "published",
        )
        .order_by(
            ExternalCustomerDocument.published_at.desc(),
            ExternalCustomerDocument.id.desc(),
        )
        .all()
    )
    return [_customer_document_payload(row) for row in rows]


def _workspace_invoices(applications, customer_documents):
    application_by_entrust = {
        row.internal_entrust_no: row
        for row in applications
        if row.internal_entrust_no
    }
    if not application_by_entrust:
        return []
    invoice_documents = defaultdict(list)
    for document in customer_documents:
        if document.get("kind") == "invoice":
            invoice_documents[document.get("applicationNo")].append(document)
    rows = (
        FinanceBill.query.filter(FinanceBill.entrust_no.in_(list(application_by_entrust)))
        .order_by(FinanceBill.updated_at.desc(), FinanceBill.id.desc())
        .all()
    )
    result = []
    for row in rows:
        application = application_by_entrust[row.entrust_no]
        documents = invoice_documents.get(application.application_no, [])
        result.append({
            "id": row.id,
            "applicationNo": application.application_no,
            "entrustNo": row.entrust_no,
            "billNo": row.bill_no,
            "status": row.status,
            "amountDue": FinanceBill._money(row.amount_due),
            "amountReceived": FinanceBill._money(row.amount_received),
            "amountInvoiced": FinanceBill._money(row.amount_invoiced),
            "invoiceNo": row.invoice_no or "",
            "invoiceType": row.invoice_type or "",
            "invoiceDate": row.invoice_date or "",
            "documents": documents,
            "downloadAvailable": bool(documents),
            "updatedAt": _iso(row.updated_at),
        })
    return result


def _report_internal_status(report):
    from ..data_entry_state import report_data_entry_started
    return report_data_status(
        report.status,
        report.sample_status,
        report.sample_reg_state,
        report.archive_state,
        report.voided,
        report_data_entry_started(report),
    )


def _public_report_is_queryable(report) -> bool:
    """Return whether a report may be exposed through the public portal.

    Statuses before approval, reports returned for changes, and voided reports
    deliberately remain indistinguishable from missing report numbers to
    prevent enumeration of internal records.
    """
    return (
        not bool(report.voided)
        and report.status in PUBLIC_REPORT_QUERYABLE_STATUSES
    )


def _report_workflow(report, audits=None):
    """Return customer-safe completed milestones from the immutable audit log.

    A later undo removes the corresponding milestone.  If the step is
    completed again, the newest successful completion is used.  Operator
    accounts, comments and audit snapshots are deliberately not exposed.
    """
    if audits is None:
        audits = (
            OperationAudit.query.filter_by(
                object_type="report", object_id=report.report_no, success=True
            )
            .filter(
                OperationAudit.action.in_(
                    tuple(PUBLIC_REPORT_WORKFLOW_LABELS)
                    + tuple(PUBLIC_REPORT_WORKFLOW_UNDO)
                )
            )
            .order_by(OperationAudit.created_at, OperationAudit.id)
            .all()
        )
    milestones = {}
    for audit in sorted(
        audits,
        key=lambda item: (item.created_at or datetime.min, item.id or 0),
    ):
        completed_action = PUBLIC_REPORT_WORKFLOW_UNDO.get(audit.action)
        if completed_action:
            milestones.pop(completed_action, None)
        elif audit.action in PUBLIC_REPORT_WORKFLOW_LABELS:
            milestones[audit.action] = audit
    return [
        {
            "key": audit.action,
            "label": PUBLIC_REPORT_WORKFLOW_LABELS[audit.action],
            "status": "completed",
            "occurredAt": _iso(audit.created_at),
            "completed": True,
        }
        for audit in sorted(
            milestones.values(),
            key=lambda item: (item.created_at or datetime.min, item.id or 0),
        )
    ]


def _public_report_payload(report, audits=None):
    values = report_values(report)
    detail = _mapping(report.detail)
    raw_sample = _mapping(detail.get("rawSample"))
    check_input = _mapping(detail.get("checkInput"))
    entrust_snapshot = _mapping(detail.get("entrustSnapshot"))
    workflow = _report_workflow(report, audits)
    release_time = next(
        (
            step.get("occurredAt", "")
            for step in reversed(workflow)
            if step.get("key") == "report.release.pass"
        ),
        "",
    )
    from ..report_business_date import report_date as approved_report_date
    report_date = approved_report_date(report) or "—"
    test_items = _first_value(
        raw_sample.get("projectList"),
        raw_sample.get("projects"),
        raw_sample.get("project"),
        values.get("testItems"),
        report.project,
    )
    queryable = _public_report_is_queryable(report)
    return {
        "reportNo": report.report_no or "",
        "legalEntity": _first_value(
            detail.get("legalEntity"),
            raw_sample.get("legalEntity"),
            raw_sample.get("issuingEntity"),
            raw_sample.get("reportEntity"),
            "示例检测机构",
        ),
        "client": _first_value(values.get("client"), report.client),
        "projectName": _first_value(
            report.project_name,
            raw_sample.get("projectName"),
            entrust_snapshot.get("projectName"),
        ),
        "sampleName": _first_value(
            raw_sample.get("sampleName"),
            raw_sample.get("sampleOrProjectName"),
            values.get("productName"),
            report.project_name,
        ),
        "specification": _first_value(
            raw_sample.get("specification"),
            raw_sample.get("spec"),
            raw_sample.get("model"),
            values.get("specification"),
        ),
        "quantity": _first_value(
            raw_sample.get("sampleAmount"),
            raw_sample.get("sampleQuantity"),
            raw_sample.get("quantity"),
            values.get("quantity"),
        ),
        "testItems": test_items,
        "reportDate": report_date,
        "department": _first_value(
            report.department,
            raw_sample.get("testDept"),
            raw_sample.get("testDepartment"),
        ),
        "status": report.status or "",
        "verificationStatus": (
            "有效"
            if report.status in {"待发放", "已发放"} and queryable
            else "已批准"
            if queryable
            else "办理中"
        ),
        "workflow": workflow,
        "verificationUrl": (
            f"/reports/{quote(report.report_no or '', safe='')}"
            if queryable
            else ""
        ),
    }


def _external_event_workflow(events):
    rows = []
    for event in events:
        label = PUBLIC_EXTERNAL_EVENT_LABELS.get(event.action)
        if not label:
            continue
        rows.append({
            "key": f"external:{event.id}:{event.action}",
            "label": label,
            "status": "completed",
            "note": event.note or "" if event.action == "reject" else "",
            "occurredAt": _iso(event.created_at),
            "completed": True,
        })
    return rows


def _external_application_payloads(applications):
    """Bulk-resolve owned portal applications to their internal progress."""
    applications = list(applications)
    if not applications:
        return []

    application_ids = [row.id for row in applications]
    events_by_application = defaultdict(list)
    for event in (
        ExternalEntrustEvent.query.filter(
            ExternalEntrustEvent.application_id.in_(application_ids)
        )
        .order_by(ExternalEntrustEvent.created_at, ExternalEntrustEvent.id)
        .all()
    ):
        events_by_application[event.application_id].append(event)

    entrust_numbers = [
        row.internal_entrust_no for row in applications if row.internal_entrust_no
    ]
    reports_by_entrust = defaultdict(list)
    reports = []
    if entrust_numbers:
        reports = (
            Report.query.filter(Report.entrust_no.in_(entrust_numbers))
            .order_by(Report.id)
            .all()
        )
        for report in reports:
            reports_by_entrust[report.entrust_no].append(report)

    audits_by_report = defaultdict(list)
    report_numbers = [report.report_no for report in reports]
    if report_numbers:
        for audit in (
            OperationAudit.query.filter(
                OperationAudit.object_type == "report",
                OperationAudit.object_id.in_(report_numbers),
                OperationAudit.success.is_(True),
                OperationAudit.action.in_(
                    tuple(PUBLIC_REPORT_WORKFLOW_LABELS)
                    + tuple(PUBLIC_REPORT_WORKFLOW_UNDO)
                ),
            )
            .order_by(OperationAudit.created_at, OperationAudit.id)
            .all()
        ):
            audits_by_report[audit.object_id].append(audit)

    entrusts_by_number = {}
    if entrust_numbers:
        entrusts_by_number = {
            row.entrust_no: row
            for row in Entrust.query.filter(
                Entrust.entrust_no.in_(entrust_numbers)
            ).all()
        }

    payloads = []
    for application in applications:
        payload = application.to_public_dict()
        linked_reports = reports_by_entrust.get(application.internal_entrust_no, [])
        report_payloads = [
            _public_report_payload(
                report, audits_by_report.get(report.report_no, [])
            )
            for report in linked_reports
        ]
        internal_statuses = [
            _report_internal_status(report) for report in linked_reports
        ]
        if internal_statuses:
            distinct_statuses = list(dict.fromkeys(internal_statuses))
            internal_status = (
                distinct_statuses[0]
                if len(distinct_statuses) == 1
                else (
                    "多份报告办理中（"
                    f"{sum(_public_report_is_queryable(r) for r in linked_reports)}"
                    f"/{len(linked_reports)}份已批准可查询）"
                )
            )
        else:
            entrust = entrusts_by_number.get(application.internal_entrust_no)
            internal_status = (
                entrust.to_row().get("dataStatus", "") if entrust else ""
            )

        workflow = _external_event_workflow(
            events_by_application.get(application.id, [])
        )
        for report_payload in report_payloads:
            for step in report_payload.get("workflow", []):
                report_step = dict(step)
                report_step["key"] = (
                    f"report:{report_payload['reportNo']}:{step.get('key', '')}"
                )
                report_step["label"] = (
                    f"{report_payload['reportNo']} · {step.get('label', '')}"
                )
                workflow.append(report_step)
        workflow.sort(key=lambda item: item.get("occurredAt") or "")

        payload.update({
            "internalStatus": internal_status,
            "workflow": workflow,
            "reports": report_payloads,
        })
        payloads.append(payload)
    return payloads


def _published_scheme_query():
    return (
        ExternalScheme.query.join(Project, ExternalScheme.project_id == Project.id)
        .filter(ExternalScheme.published.is_(True), Project.active.is_(True))
    )


def _scheme_from_body(body):
    scheme_id = body.get("schemeId")
    slug = _text(body.get("slug"))
    query = _published_scheme_query()
    if scheme_id not in (None, ""):
        try:
            return query.filter(ExternalScheme.id == int(scheme_id)).first()
        except (TypeError, ValueError):
            return None
    return query.filter(ExternalScheme.slug == slug).first() if slug else None


def _quote_for(scheme, body):
    form_data = body.get("formData") if isinstance(body.get("formData"), dict) else {}
    # Price calculation is based only on server-parsed business inputs.  A
    # browser supplied quoteId/quote snapshot is intentionally ignored.
    raw_quantity = (
        form_data.get("quantity")
        or form_data.get("sampleQuantity")
        or body.get("quantity")
        or 1
    )
    try:
        quantity = max(1, int(raw_quantity))
    except (TypeError, ValueError):
        quantity = 1
    mode = scheme.price_mode or "quote"
    minimum = scheme.price_min
    maximum = scheme.price_max
    amount_min = minimum * quantity if minimum is not None else None
    amount_max = maximum * quantity if maximum is not None else None
    if mode == "fixed":
        amount = amount_min if amount_min is not None else amount_max
        amount_min = amount_max = amount
    elif mode == "from":
        amount_max = None
    elif mode == "quote":
        amount_min = amount_max = None
    estimated = amount_min
    generated_at = datetime.utcnow()
    quote_key = (
        f"{scheme.id}:{scheme.version}:{quantity}:"
        f"{amount_min}:{amount_max}:{generated_at.strftime('%Y%m%d')}"
    )
    return {
        "quoteId": "Q-" + hashlib.sha256(quote_key.encode("utf-8")).hexdigest()[:20],
        "schemeId": scheme.id,
        "slug": scheme.slug,
        "priceMode": mode,
        "quantity": quantity,
        "estimatedAmount": float(estimated) if estimated is not None else None,
        "priceMin": float(amount_min) if amount_min is not None else None,
        "priceMax": float(amount_max) if amount_max is not None else None,
        "priceUnit": scheme.price_unit or "",
        "currency": "CNY",
        "isEstimate": True,
        "pricingRules": scheme.pricing_rules if isinstance(scheme.pricing_rules, (dict, list)) else {},
        "breakdown": ([{"label": "检测服务预估", "amount": float(estimated)}] if estimated is not None else []),
        "validUntil": (generated_at + timedelta(days=7)).date().isoformat(),
        "schemeSnapshot": scheme.to_public_dict(),
        "notice": "本结果为预估价格，最终价格以受理后的正式委托为准。",
    }


def _create_portal_notification(
    application,
    *,
    category,
    title,
    content,
    link="",
    source_key=None,
):
    row = ExternalPortalNotification(
        external_account_id=application.external_account_id,
        application_id=application.id,
        category=category,
        title=_text(title)[:160],
        content=_text(content)[:500],
        link=_text(link)[:300] or f"/account/entrusts/{application.application_no}",
        source_key=_text(source_key)[:160] or None,
    )
    db.session.add(row)
    return row


def _event(application, action, from_status, to_status, actor, *, kind, note=""):
    form_data = application.form_data if isinstance(application.form_data, dict) else {}
    form_hash = hashlib.sha256(
        json.dumps(form_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    row = ExternalEntrustEvent(
        application=application,
        action=action,
        from_status=from_status,
        to_status=to_status,
        actor_kind=kind,
        actor_id=getattr(actor, "id", None),
        actor_account=getattr(actor, "account", "") or "",
        actor_name=getattr(actor, "name", "") or "",
        note=note or "",
        # Keep the immutable event useful without duplicating customer phone,
        # tax and delivery-address values into every history row.
        snapshot={
            "applicationNo": application.application_no,
            "status": application.status,
            "formVersion": application.form_version,
            "formDataHash": form_hash,
            "internalEntrustNo": application.internal_entrust_no or "",
            "reviewNote": application.review_note or "",
        },
    )
    db.session.add(row)
    notification = PUBLIC_NOTIFICATION_ACTIONS.get(action)
    if notification:
        title, default_content = notification
        _create_portal_notification(
            application,
            category="entrust",
            title=title,
            content=note or default_content,
        )
    return row


def _owned_application(application_no):
    return ExternalEntrustApplication.query.filter_by(
        application_no=application_no,
        external_account_id=g.external_account.id,
    ).first()


def _validate_submission(application):
    form = application.form_data if isinstance(application.form_data, dict) else {}
    account = application.account
    values = {
        "委托单位": form.get("companyName") or form.get("client") or account.company_name,
        "联系人": form.get("contactName") or form.get("consignor") or form.get("contactPerson") or account.name,
        "联系电话": form.get("contactMobile") or form.get("contactPhone") or form.get("consignorPhone") or form.get("phone") or account.mobile,
        "项目名称": form.get("projectName"),
        "样品/检测对象": form.get("sampleName"),
    }
    missing = [label for label, value in values.items() if not _text(value)]
    try:
        if Decimal(str(form.get("quantity") or 0)) <= 0:
            missing.append("有效的样品数量")
    except (InvalidOperation, TypeError, ValueError):
        missing.append("有效的样品数量")
    if "邮寄" in _text(form.get("reportDeliveryMethod")) and not _text(form.get("mailingAddress")):
        missing.append("报告邮寄地址")
    invoice_type = _text(form.get("invoiceType"))
    if invoice_type and invoice_type != "暂不需要":
        if not _text(form.get("invoiceTitle")):
            missing.append("开票名称")
        if not _text(form.get("taxpayerId")):
            missing.append("纳税人识别号")
    return missing


def _validated_form_data(body):
    value = body.get("formData")
    if value is None:
        return {}, ""
    if not isinstance(value, dict):
        return None, "委托表单格式不正确"
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return None, "委托表单包含不支持的数据"
    if len(encoded.encode("utf-8")) > 64 * 1024:
        return None, "委托表单内容过大"
    for key, item in value.items():
        if len(str(key)) > 80:
            return None, "委托表单字段名称过长"
        if isinstance(item, str) and len(item) > (2000 if key == "notes" else 500):
            return None, f"{key} 内容过长"
    return value, ""


def _canonical_selected_test_items(scheme, form_data, *, require_current_hash=False):
    """Validate customer selections against the server-owned public snapshot."""
    if not isinstance(form_data, dict):
        return form_data, ""
    raw = form_data.get("selectedTestItems")
    if scheme is None:
        if raw not in (None, []):
            return None, "当前委托未关联可选检测方案，不能提交结构化检测项目"
        result = dict(form_data)
        result["selectedTestItems"] = []
        result["selectedCapabilityHash"] = ""
        return result, ""
    if raw in (None, []):
        result = dict(form_data)
        result["selectedTestItems"] = []
        result["selectedCapabilityHash"] = scheme.capability_hash or ""
        return result, ""
    if not isinstance(raw, list) or len(raw) > 20:
        return None, "检测项目选择格式不正确"
    snapshot = scheme.capability_snapshot if isinstance(scheme.capability_snapshot, dict) else {}
    available = {
        str(item.get("key") or ""): item
        for item in snapshot.get("items") or []
        if isinstance(item, dict) and item.get("key")
    }
    submitted_hash = _text(form_data.get("selectedCapabilityHash"))
    if require_current_hash and submitted_hash and submitted_hash != (scheme.capability_hash or ""):
        return None, "检测能力或执行标准已更新，请重新确认所选检测项目"
    canonical = []
    seen = set()
    for value in raw:
        key = _text(value.get("key") if isinstance(value, dict) else value)
        if not key or key in seen or key not in available:
            return None, "所选检测项目不属于当前检测对象，请重新选择"
        seen.add(key)
        item = available[key]
        canonical.append({
            "key": key,
            "name": _text(item.get("name")),
            "standards": [
                {
                    "code": _text(standard.get("code")),
                    "name": _text(standard.get("name")),
                    "qualificationTags": standard.get("qualificationTags") or [],
                }
                for standard in item.get("standards") or []
                if isinstance(standard, dict)
            ],
        })
    result = dict(form_data)
    result["selectedTestItems"] = canonical
    result["selectedCapabilityHash"] = scheme.capability_hash or ""
    return result, ""


@public_bp.get("/schemes")
def list_public_schemes():
    keyword = _text(request.args.get("keyword")).lower()
    category = _text(request.args.get("category"))
    standard_keyword = _text(request.args.get("standard")).lower()
    item_keyword = _text(request.args.get("item")).lower()
    qualification = _text(request.args.get("qualification")).upper()
    try:
        page = max(1, int(request.args.get("page") or 1))
        size = min(100, max(1, int(request.args.get("pageSize") or request.args.get("size") or 12)))
    except (TypeError, ValueError):
        page, size = 1, 12
    query = _published_scheme_query()
    if category:
        query = query.filter(ExternalScheme.category == category)
    ordered = query.order_by(
            ExternalScheme.featured.desc(),
            ExternalScheme.display_order.desc(),
            ExternalScheme.published_at.desc(),
            ExternalScheme.id.desc(),
        ).all()

    def matches(row):
        payload = row.to_public_dict()
        items = payload.get("commonTestItems") or []
        standards = [
            standard
            for item in items if isinstance(item, dict)
            for standard in item.get("standards") or [] if isinstance(standard, dict)
        ]
        if keyword:
            haystack = " ".join(str(value or "") for value in (
                payload.get("publicTitle"), payload.get("objectName"), payload.get("summary"),
                payload.get("department"), payload.get("code"),
                " ".join(str(item.get("name") or "") for item in items if isinstance(item, dict)),
                " ".join(f"{standard.get('code', '')} {standard.get('name', '')}" for standard in standards),
            )).lower()
            if keyword not in haystack:
                return False
        if item_keyword and not any(
            item_keyword in str(item.get("name") or "").lower()
            for item in items if isinstance(item, dict)
        ):
            return False
        if standard_keyword and not any(
            standard_keyword in f"{standard.get('code', '')} {standard.get('name', '')}".lower()
            for standard in standards
        ):
            return False
        if qualification and qualification not in set(payload.get("qualificationTags") or []):
            return False
        return True

    filtered = [row for row in ordered if matches(row)]
    total = len(filtered)
    rows = filtered[(page - 1) * size:page * size]
    categories = [
        value[0]
        for value in db.session.query(ExternalScheme.category)
        .join(Project, ExternalScheme.project_id == Project.id)
        .filter(
            ExternalScheme.published.is_(True),
            Project.active.is_(True),
            ExternalScheme.category.is_not(None),
            ExternalScheme.category != "",
        )
        .distinct()
        .order_by(ExternalScheme.category)
        .all()
    ]
    return _ok({
        "rows": [row.to_public_dict() for row in rows],
        "total": total,
        "page": page,
        "pageSize": size,
        "categories": categories,
    })


@public_bp.get("/schemes/<string:slug>")
def get_public_scheme(slug):
    row = _published_scheme_query().filter(ExternalScheme.slug == slug).first()
    return _ok(row.to_public_dict(detail=True)) if row else _error("检测方案不存在或未发布", 404)


@public_bp.get("/schemes/image-credits")
def get_public_scheme_image_credits():
    return _ok({"rows": public_image_credits()})


@public_bp.get("/reports/query")
def query_public_report():
    """Verify one exact, approved report number without exposing search APIs."""
    report_no = _text(request.args.get("reportNo"))
    if not report_no:
        return _error("请填写报告编号")
    if len(report_no) > 40:
        return _error("未查询到已批准的有效报告", 404)
    report = Report.query.filter(
        Report.report_no == report_no,
        Report.status.in_(PUBLIC_REPORT_QUERYABLE_STATUSES),
        or_(Report.voided.is_(False), Report.voided.is_(None)),
    ).first()
    if not report:
        # A missing report and an existing but unapproved report deliberately
        # share one response so internal report numbers cannot be enumerated.
        return _error("未查询到已批准的有效报告", 404)
    payload = _public_report_payload(report)
    from ..report_final_fields import public_facts, approval_date, redact_public_project_name
    version = db.session.get(ReportDocumentVersion, report.approved_document_version_id) if report.approved_document_version_id else None
    snapshot = version.snapshot if version and version.report_no == report.report_no else {
        'report': {'reportNo': report.report_no, 'client': report.client,
                   'project': report.project, 'detail': report.detail or {}}}
    facts = redact_public_project_name(report.report_no,
        public_facts(snapshot, version.version_no if version else 0, approval_date(report)))
    payload.update(reportTitle=facts['reportTitle'], reportKind=facts['reportKind'],
        client=facts['client'], projectName=facts['projectName'], sampleName=facts['sampleName'],
        specification=facts['model'], quantity=facts['quantity'],
        testItems=facts['testItems'], reportDate=facts['issueDate'])
    response = _ok(payload)
    response.headers["Cache-Control"] = "no-store"
    return response


@public_bp.post("/quotes/estimate")
def estimate_public_quote():
    body = request.get_json(silent=True) or {}
    scheme = _scheme_from_body(body)
    return _ok(_quote_for(scheme, body)) if scheme else _error("请选择有效的外部检测方案")


@public_bp.post("/auth/register")
def register_external_account():
    body = request.get_json(silent=True) or {}
    account_name = _text(body.get("account")).lower()
    submitted_password = str(body.get("password") or "")
    name = _text(body.get("name"))
    mobile = _text(body.get("mobile")) or None
    email = _text(body.get("email")).lower() or None
    if not ACCOUNT_RE.fullmatch(account_name):
        return _error("账号须为 4-80 位字母、数字或 ._@+-")
    if len(submitted_password) < 8:
        return _error("密码至少 8 位")
    if not name:
        return _error("请填写联系人姓名")
    if ExternalAccount.query.filter_by(account=account_name).first():
        return _error("账号已存在", 409)
    if mobile and ExternalAccount.query.filter_by(mobile=mobile).first():
        return _error("手机号已注册", 409)
    if email and ExternalAccount.query.filter_by(email=email).first():
        return _error("邮箱已注册", 409)
    row = ExternalAccount(
        account=account_name,
        password_hash=hash_password(submitted_password),
        name=name,
        mobile=mobile,
        email=email,
        company_name=_text(body.get("companyName")),
        unified_social_credit_code=_text(body.get("unifiedSocialCreditCode")),
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("账号、手机号或邮箱已注册", 409)
    return _ok({"token": issue_external_token(row), "user": row.to_public_dict()}, "注册成功")


@public_bp.post("/auth/login")
def login_external_account():
    body = request.get_json(silent=True) or {}
    account_name = _text(body.get("account")).lower()
    submitted_password = str(body.get("password") or "")
    # Serialize the whole credential/lock transition, including successful resets.
    # SQLite ignores FOR UPDATE; its write transaction must begin before reading.
    if db.session.get_bind().dialect.name == 'sqlite':
        from sqlalchemy import text
        db.session.execute(text('BEGIN IMMEDIATE'))
    row = ExternalAccount.query.filter_by(account=account_name).populate_existing().with_for_update().first()
    now = datetime.utcnow()
    if row and row.locked_until and row.locked_until > now:
        db.session.rollback()
        return _error("连续登录失败次数过多，请稍后再试", 423)
    if not row or not row.enabled or not verify_password(submitted_password, row.password_hash):
        if row:
            row.failed_attempts = int(row.failed_attempts or 0) + 1
            if row.failed_attempts >= 5:
                row.locked_until = now + timedelta(minutes=30)
            db.session.commit()
        else:
            db.session.rollback()
        return _error("账号或密码错误", 401)
    if needs_rehash(row.password_hash):
        row.password_hash = hash_password(submitted_password)
    row.failed_attempts = 0
    row.locked_until = None
    row.last_login_at = now
    db.session.commit()
    return _ok({"token": issue_external_token(row), "user": row.to_public_dict()}, "登录成功")


@public_bp.get("/auth/me")
@require_external_auth
def external_me():
    return _ok({"user": g.external_account.to_public_dict()})


@public_bp.get("/workspace")
@require_external_auth
def customer_workspace():
    """Return one account-scoped customer workbench without internal-only data."""
    applications = _owned_workspace_rows(g.external_account.id)
    application_ids = [row.id for row in applications]
    customer_documents = _workspace_customer_documents(application_ids)
    documents = _workspace_report_documents(applications) + customer_documents
    documents.sort(
        key=lambda item: item.get("publishedAt") or item.get("issuedAt") or "",
        reverse=True,
    )
    invoices = _workspace_invoices(applications, customer_documents)
    shipments = []
    if application_ids:
        shipments = [
            _shipment_payload(row)
            for row in ExternalShipment.query.filter(
                ExternalShipment.application_id.in_(application_ids)
            )
            .order_by(ExternalShipment.updated_at.desc(), ExternalShipment.id.desc())
            .all()
        ]
    notification_query = ExternalPortalNotification.query.filter_by(
        external_account_id=g.external_account.id
    )
    unread_count = notification_query.filter(
        ExternalPortalNotification.read_at.is_(None)
    ).count()
    notifications = [
        _portal_notification_payload(row)
        for row in notification_query.order_by(
            ExternalPortalNotification.published_at.desc(),
            ExternalPortalNotification.id.desc(),
        ).limit(50).all()
    ]
    status_counts = Counter(row.status for row in applications)
    active_count = sum(
        status_counts.get(status, 0)
        for status in ("submitted", "accepted", "processing")
    )
    response = _ok({
        "summary": {
            "orders": len(applications),
            "needsAction": status_counts.get("draft", 0) + status_counts.get("rejected", 0),
            "active": active_count,
            "availableDocuments": sum(item.get("status") == "available" for item in documents),
            "invoiceDownloads": sum(bool(item.get("downloadAvailable")) for item in invoices),
            "shipmentsInTransit": sum(
                item.get("status") in {"shipped", "in_transit", "delivering"}
                for item in shipments
            ),
            "unreadNotifications": unread_count,
        },
        "recentOrders": _external_application_payloads(applications[:8]),
        "documents": documents[:100],
        "invoices": invoices[:100],
        "shipments": shipments[:100],
        "notifications": notifications,
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response


@public_bp.get("/assistant/status")
@require_external_auth
def customer_assistant_status():
    response = _ok({
        "searchEnabled": True,
        "voiceEnabled": _customer_assistant_voice_enabled(),
        "maxAudioSeconds": int(current_app.config.get("AI_AUDIO_MAX_SECONDS", 90)),
        "maxAudioBytes": int(current_app.config.get("AI_AUDIO_MAX_BYTES", 8 * 1024 * 1024)),
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response


@public_bp.post("/assistant/search")
@require_external_auth
def customer_assistant_search():
    body = request.get_json(silent=True) or {}
    query = _text(body.get("query"))
    if len(query) < 2:
        return _error("请至少输入 2 个字符")
    if len(query) > 120:
        return _error("搜索内容不能超过 120 个字符")
    try:
        limit = max(1, min(int(body.get("limit") or 20), 30))
    except (TypeError, ValueError):
        limit = 20

    applications = _owned_workspace_rows(g.external_account.id)
    application_ids = [row.id for row in applications]
    customer_documents = _workspace_customer_documents(application_ids)
    documents = _workspace_report_documents(applications) + customer_documents
    invoices = _workspace_invoices(applications, customer_documents)
    shipments = []
    if application_ids:
        shipments = [
            _shipment_payload(row)
            for row in ExternalShipment.query.filter(
                ExternalShipment.application_id.in_(application_ids)
            ).order_by(ExternalShipment.updated_at.desc(), ExternalShipment.id.desc()).all()
        ]
    notifications = [
        _portal_notification_payload(row)
        for row in ExternalPortalNotification.query.filter_by(
            external_account_id=g.external_account.id
        ).order_by(
            ExternalPortalNotification.published_at.desc(),
            ExternalPortalNotification.id.desc(),
        ).limit(100).all()
    ]
    schemes = [
        row.to_public_dict(detail=True)
        for row in _published_scheme_query().order_by(
            ExternalScheme.featured.desc(),
            ExternalScheme.display_order.desc(),
            ExternalScheme.id.desc(),
        ).limit(200).all()
    ]
    rows = search_customer_resources(
        query,
        schemes=schemes,
        applications=_external_application_payloads(applications),
        documents=documents,
        invoices=invoices,
        shipments=shipments,
        notifications=notifications,
        limit=limit,
    )
    response = _ok({"query": query, "rows": rows, "total": len(rows)})
    response.headers["Cache-Control"] = "private, no-store"
    return response


@public_bp.post("/assistant/transcriptions")
@require_external_auth
def customer_assistant_transcription():
    if not _customer_assistant_voice_enabled():
        return _error("语音搜索服务尚未启用", 503)
    if _customer_assistant_rate_limited(10):
        return _error("语音请求过于频繁，请稍后再试", 429)
    upload = request.files.get("audio")
    if not upload:
        return _error("缺少音频文件")
    media_type = (upload.mimetype or "").lower().partition(";")[0].strip()
    if media_type not in CUSTOMER_ASSISTANT_AUDIO_TYPES:
        return _error("不支持该音频格式")
    try:
        duration = float(request.form.get("durationSeconds") or 0)
    except (TypeError, ValueError):
        return _error("录音时长无效")
    max_seconds = int(current_app.config.get("AI_AUDIO_MAX_SECONDS", 90))
    max_bytes = int(current_app.config.get("AI_AUDIO_MAX_BYTES", 8 * 1024 * 1024))
    if duration <= 0 or duration > max_seconds:
        return _error(f"单次录音必须在 {max_seconds} 秒以内")
    audio = upload.read(max_bytes + 1)
    if len(audio) > max_bytes:
        return _error("录音文件过大", 413)

    started = time.monotonic()
    data_uri = f"data:{media_type};base64,{base64.b64encode(audio).decode('ascii')}"
    try:
        transcript = ai_provider.transcribe(data_uri)
    except ai_provider.AiProviderError as exc:
        add_operation_audit(
            "external_portal.ai.transcribe",
            "external_ai_session",
            hashlib.sha256(f"{g.external_account.id}:{time.time_ns()}".encode()).hexdigest()[:16],
            category="ai",
            after={
                "durationSeconds": round(duration, 2),
                "elapsedMs": round((time.monotonic() - started) * 1000),
                "model": current_app.config.get("AI_ASR_MODEL", ""),
            },
            success=False,
            message="provider_error",
            actor=g.external_account,
        )
        db.session.commit()
        return _error(str(exc), 502)
    finally:
        audio = b""
        data_uri = ""
    elapsed_ms = round((time.monotonic() - started) * 1000)
    add_operation_audit(
        "external_portal.ai.transcribe",
        "external_ai_session",
        hashlib.sha256(f"{g.external_account.id}:{time.time_ns()}".encode()).hexdigest()[:16],
        category="ai",
        after={
            "durationSeconds": round(duration, 2),
            "elapsedMs": elapsed_ms,
            "model": current_app.config.get("AI_ASR_MODEL", ""),
        },
        actor=g.external_account,
    )
    db.session.commit()
    response = _ok({"text": transcript})
    response.headers["Cache-Control"] = "private, no-store"
    return response


@public_bp.get("/documents/reports/<string:report_no>/download")
@require_external_auth
def download_customer_report(report_no):
    report = Report.query.filter_by(report_no=report_no).first()
    if not report or not _public_report_is_queryable(report) or not report.entrust_no:
        return _error("文件不存在或尚未开放下载", 404)
    application = ExternalEntrustApplication.query.filter_by(
        external_account_id=g.external_account.id,
        internal_entrust_no=report.entrust_no,
    ).first()
    if not application or not report.approved_document_version_id:
        return _error("文件不存在或尚未开放下载", 404)
    version = ReportDocumentVersion.query.filter_by(
        id=report.approved_document_version_id,
        report_no=report.report_no,
        output_kind="official",
    ).first()
    if not version:
        return _error("文件不存在或尚未开放下载", 404)
    raw = _read_customer_file(version.pdf_file, version.pdf_data)
    if not raw:
        return _error("文件不存在或尚未开放下载", 404)
    if not current_app.config.get("APP_BUSINESS_READ_ONLY"):
        add_operation_audit(
            "external_portal.report.download",
            "report",
            report.report_no,
            category="security",
            after={"applicationNo": application.application_no, "versionId": version.id},
            actor=g.external_account,
        )
        db.session.commit()
    name = f"{report.report_no}-正式报告.pdf"
    response = make_response(raw)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name, safe='')}"
    response.headers["Cache-Control"] = "private, no-store"
    response.set_etag(version.sha256 or hashlib.sha256(raw).hexdigest())
    return response


@public_bp.get("/documents/<int:document_id>/download")
@require_external_auth
def download_customer_document(document_id):
    row = (
        ExternalCustomerDocument.query.join(
            ExternalEntrustApplication,
            ExternalCustomerDocument.application_id == ExternalEntrustApplication.id,
        )
        .filter(
            ExternalCustomerDocument.id == document_id,
            ExternalCustomerDocument.status == "published",
            ExternalEntrustApplication.external_account_id == g.external_account.id,
        )
        .first()
    )
    if not row or not row.stored_file or row.stored_file.status != "active":
        return _error("文件不存在或尚未开放下载", 404)
    raw = _read_customer_file(row.stored_file)
    if not raw:
        return _error("文件不存在或尚未开放下载", 404)
    if not current_app.config.get("APP_BUSINESS_READ_ONLY"):
        add_operation_audit(
            "external_portal.document.download",
            "external_customer_document",
            row.id,
            category="security",
            after={"applicationNo": row.application.application_no, "kind": row.kind},
            actor=g.external_account,
        )
        db.session.commit()
    response = make_response(raw)
    response.headers["Content-Type"] = row.stored_file.content_type
    response.headers["Content-Disposition"] = (
        "attachment; filename*=UTF-8''"
        f"{quote(row.stored_file.original_name, safe='')}"
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.set_etag(row.stored_file.sha256)
    return response


@public_bp.get("/notifications")
@require_external_auth
def list_customer_notifications():
    try:
        size = min(100, max(1, int(request.args.get("pageSize") or 20)))
    except (TypeError, ValueError):
        size = 20
    query = ExternalPortalNotification.query.filter_by(
        external_account_id=g.external_account.id
    )
    unread = query.filter(ExternalPortalNotification.read_at.is_(None)).count()
    rows = query.order_by(
        ExternalPortalNotification.published_at.desc(),
        ExternalPortalNotification.id.desc(),
    ).limit(size).all()
    response = _ok({
        "rows": [_portal_notification_payload(row) for row in rows],
        "unread": unread,
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response


@public_bp.post("/notifications/read-all")
@require_external_auth
def read_all_customer_notifications():
    now = datetime.utcnow()
    rows = ExternalPortalNotification.query.filter_by(
        external_account_id=g.external_account.id,
        read_at=None,
    ).all()
    for row in rows:
        row.read_at = now
    db.session.commit()
    return _ok({"updated": len(rows), "unread": 0})


@public_bp.post("/notifications/<int:notification_id>/read")
@require_external_auth
def read_customer_notification(notification_id):
    row = ExternalPortalNotification.query.filter_by(
        id=notification_id,
        external_account_id=g.external_account.id,
    ).first()
    if not row:
        return _error("消息不存在", 404)
    if not row.read_at:
        row.read_at = datetime.utcnow()
        db.session.commit()
    return _ok(_portal_notification_payload(row))


@public_bp.post("/entrusts")
@require_external_auth
def create_external_entrust():
    body = request.get_json(silent=True) or {}
    form_data, form_error = _validated_form_data(body)
    if form_error:
        return _error(form_error)
    scheme = _scheme_from_body(body)
    if not scheme:
        return _error("请选择有效的外部检测方案")
    form_data, selection_error = _canonical_selected_test_items(scheme, form_data)
    if selection_error:
        return _error(selection_error)
    idempotency_key = _text(
        request.headers.get("Idempotency-Key") or body.get("idempotencyKey")
    ) or None
    if idempotency_key:
        existing = ExternalEntrustApplication.query.filter_by(
            external_account_id=g.external_account.id,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            return _ok(existing.to_public_dict(), "已返回同一请求创建的委托草稿")
    quote = _quote_for(scheme, body)
    estimated = quote.get("estimatedAmount")
    application_no = allocate_external_application_number(business_today().year)
    row = ExternalEntrustApplication(
        application_no=application_no,
        external_account_id=g.external_account.id,
        scheme_id=scheme.id,
        project_id=scheme.project_id,
        scheme_snapshot=scheme.to_public_dict(detail=True),
        quote_snapshot=quote,
        estimated_amount=_decimal(estimated),
        form_version=_text(body.get("formVersion")) or "1.0",
        form_data=form_data,
        status="draft",
        idempotency_key=idempotency_key,
    )
    db.session.add(row)
    db.session.flush()
    _event(row, "create", None, "draft", g.external_account, kind="external")
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if idempotency_key:
            existing = ExternalEntrustApplication.query.filter_by(
                external_account_id=g.external_account.id,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                return _ok(existing.to_public_dict(), "已返回同一请求创建的委托草稿")
        raise
    return _ok(row.to_public_dict(), "委托草稿已保存")


@public_bp.get("/entrusts")
@require_external_auth
def list_external_entrusts():
    try:
        page = max(1, int(request.args.get("page") or 1))
        size = min(100, max(1, int(request.args.get("pageSize") or request.args.get("size") or 20)))
    except (TypeError, ValueError):
        page, size = 1, 20
    query = ExternalEntrustApplication.query.filter_by(
        external_account_id=g.external_account.id
    )
    status = _text(request.args.get("status"))
    if status:
        query = query.filter_by(status=status)
    total = query.count()
    rows = query.order_by(ExternalEntrustApplication.id.desc()).offset((page - 1) * size).limit(size).all()
    return _ok({
        "rows": _external_application_payloads(rows),
        "total": total,
        "page": page,
        "pageSize": size,
    })


@public_bp.get("/entrusts/<string:application_no>")
@require_external_auth
def get_external_entrust(application_no):
    row = _owned_application(application_no)
    if not row:
        return _error("委托申请不存在", 404)
    return _ok(_external_application_payloads([row])[0])


@public_bp.put("/entrusts/<string:application_no>")
@public_bp.patch("/entrusts/<string:application_no>")
@require_external_auth
def update_external_entrust(application_no):
    row = _owned_application(application_no)
    if not row:
        return _error("委托申请不存在", 404)
    if row.status not in PUBLIC_EDITABLE_STATUSES:
        return _error("只有草稿或已驳回状态可以修改", 409)
    body = request.get_json(silent=True) or {}
    form_data, form_error = _validated_form_data(body)
    if form_error:
        return _error(form_error)
    old_status = row.status
    if "formData" in body:
        row.form_data = form_data
    if body.get("formVersion") not in (None, ""):
        row.form_version = _text(body.get("formVersion"))
    scheme_changed = bool(body.get("schemeId") or body.get("slug"))
    scheme = row.scheme
    if scheme_changed:
        scheme = _scheme_from_body(body)
        if not scheme:
            return _error("请选择有效的外部检测方案")
        row.scheme = scheme
        row.project_id = scheme.project_id
        row.scheme_snapshot = scheme.to_public_dict(detail=True)
    if "formData" in body and scheme:
        canonical_form, selection_error = _canonical_selected_test_items(scheme, form_data)
        if selection_error:
            return _error(selection_error)
        row.form_data = canonical_form
    if scheme and (scheme_changed or isinstance(body.get("formData"), dict)):
        quote_input = dict(body)
        quote_input["formData"] = row.form_data if isinstance(row.form_data, dict) else {}
        quote = _quote_for(scheme, quote_input)
        row.quote_snapshot = quote
        row.estimated_amount = _decimal(quote.get("estimatedAmount"))
    _event(row, "update", old_status, old_status, g.external_account, kind="external")
    db.session.commit()
    return _ok(row.to_public_dict(), "委托草稿已保存")


@public_bp.post("/entrusts/<string:application_no>/submit")
@require_external_auth
def submit_external_entrust(application_no):
    row = _owned_application(application_no)
    if not row:
        return _error("委托申请不存在", 404)
    if row.status == "submitted":
        return _ok(row.to_public_dict(), "委托申请已提交")
    if row.status not in PUBLIC_EDITABLE_STATUSES:
        return _error("当前状态不能提交", 409)
    canonical_form, selection_error = _canonical_selected_test_items(
        row.scheme,
        dict(row.form_data or {}),
        require_current_hash=True,
    )
    if selection_error:
        return _error(selection_error, 409)
    row.form_data = canonical_form
    missing = _validate_submission(row)
    if missing:
        return _error(f"请补充：{'、'.join(missing)}")
    before = row.status
    row.status = "submitted"
    if not row.assigned_department_id and row.project:
        # Freeze the intake department at submission time.  Later project
        # reorganisations must not silently move historical customer records.
        row.assigned_department_id = row.project.department_id
    row.submitted_at = datetime.utcnow()
    # A resubmission starts a new review round while the immutable event stream
    # retains the previous rejection reason and reviewer.
    if before == "rejected":
        row.review_note = ""
        row.reviewer_id = None
        row.reviewer_name = ""
        row.reviewed_at = None
    _event(row, "resubmit" if before == "rejected" else "submit", before, "submitted", g.external_account, kind="external")
    db.session.commit()
    return _ok(row.to_public_dict(), "委托申请已提交，等待受理")


def _cancel_external_entrust(application_no):
    row = _owned_application(application_no)
    if not row:
        return _error("委托申请不存在", 404)
    if row.status == "cancelled":
        return _ok(row.to_public_dict(), "委托申请已取消")
    if row.status not in PUBLIC_CANCELLABLE_STATUSES:
        return _error("当前状态不能取消", 409)
    before = row.status
    row.status = "cancelled"
    _event(row, "cancel", before, "cancelled", g.external_account, kind="external")
    db.session.commit()
    return _ok(row.to_public_dict(), "委托申请已取消")


@public_bp.post("/entrusts/<string:application_no>/cancel")
@require_external_auth
def cancel_external_entrust(application_no):
    return _cancel_external_entrust(application_no)


@public_bp.delete("/entrusts/<string:application_no>")
@require_external_auth
def delete_external_entrust(application_no):
    return _cancel_external_entrust(application_no)


def _has_internal_queue_access(user):
    if user.role_key in {"admin", "super_admin"}:
        return True
    return bool({
        "online_entrust.view",
        "online_entrust.application.view",
        "online_entrust.query.view",
    }.intersection(user.permission_codes()))


def _has_internal_process_access(user, action):
    return has_internal_process_access(user, action)


def _internal_scope_allows(user, application):
    return internal_scope_allows(user, application)


def _internal_scope_query(query, user):
    if (
        user.role_key in {"admin", "super_admin"}
        or user.data_scope_type == "all"
        or user_has_org_wide_scope(user)
    ):
        return query
    department_ids = sorted(user.data_department_ids())
    if not department_ids:
        return query.filter(db.false())
    assigned_scope = (
        ExternalEntrustApplication.assigned_department_id.in_(department_ids)
        if department_ids
        else db.false()
    )
    legacy_project_scope = and_(
        ExternalEntrustApplication.assigned_department_id.is_(None),
        ExternalEntrustApplication.project.has(
            Project.department_id.in_(department_ids)
        ),
    )
    return query.filter(or_(assigned_scope, legacy_project_scope))


def _require_queue_access():
    if not _has_internal_queue_access(g.current_user):
        return _error("无网上委托受理权限", 403)
    return None


def _require_process_access(action):
    if not _has_internal_process_access(g.current_user, action):
        return _error("仅有查看权限不能办理网上委托，请联系管理员授权", 403)
    return None


def _has_customer_document_kind_access(user, kind):
    if user.role_key in {"admin", "super_admin"}:
        return True
    granted = set(user.action_codes())
    if kind == "invoice":
        return "finance.invoice.issue" in granted
    if kind == "certificate":
        return "report.print.pass" in granted
    return bool(granted.intersection(INTERNAL_PROCESS_ACTIONS["process"]))


def _has_customer_document_publish_access(
    user, kind, application, *, related_report=None
):
    if not _has_customer_document_kind_access(user, kind):
        return False
    if user.role_key in {"admin", "super_admin"} or kind != "certificate":
        return True
    report_project = project_for_report(related_report) if related_report else None
    return bool(
        report_project
        and user_has_project_step(user, report_project, "report_print")
    )


def _require_customer_document_kind_access(kind):
    if not _has_customer_document_kind_access(g.current_user, kind):
        return _error(
            "当前账号没有该类客户文件的专属发布权限", 403
        )
    return None


def _require_customer_document_publish_access(
    kind, application, *, related_report=None
):
    if not _has_customer_document_publish_access(
        g.current_user,
        kind,
        application,
        related_report=related_report,
    ):
        return _error(
            "当前账号没有该类客户文件的专属发布权限", 403
        )
    return None


@admin_external_bp.get("")
@require_auth
def list_admin_external_entrustments():
    denied = _require_queue_access()
    if denied:
        return denied
    keyword = _text(request.args.get("keyword")).lower()
    status = _text(request.args.get("status"))
    try:
        page = max(1, int(request.args.get("page") or 1))
        size = min(100, max(1, int(request.args.get("size") or 20)))
    except (TypeError, ValueError):
        page, size = 1, 20
    query = _internal_scope_query(ExternalEntrustApplication.query, g.current_user)
    if status:
        query = query.filter_by(status=status)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(or_(
            ExternalEntrustApplication.application_no.ilike(pattern),
            ExternalEntrustApplication.form_data.ilike(pattern),
            ExternalEntrustApplication.scheme_snapshot.ilike(pattern),
            ExternalEntrustApplication.internal_entrust_no.ilike(pattern),
            ExternalEntrustApplication.reviewer_name.ilike(pattern),
        ))
    total = query.count()
    rows = (
        query.order_by(ExternalEntrustApplication.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return _ok({"rows": [row.to_admin_dict() for row in rows], "total": total})


def _application_for_internal_action(application_id):
    row = ExternalEntrustApplication.query.filter_by(id=application_id).with_for_update().first()
    if not row or not _internal_scope_allows(g.current_user, row):
        return None
    return row


@admin_external_bp.post("/<int:application_id>/accept")
@require_auth
def accept_admin_external_entrustment(application_id):
    note = _text((request.get_json(silent=True) or {}).get("note"))
    result = accept_external_application(
        g.current_user,
        application_id,
        note=note,
    )
    if result.code == 0:
        return _ok(result.application.to_admin_dict(), result.message)
    return _error(result.message, result.http_status, result.code)


@admin_external_bp.post("/<int:application_id>/reject")
@require_auth
def reject_admin_external_entrustment(application_id):
    denied = _require_process_access("reject")
    if denied:
        return denied
    row = _application_for_internal_action(application_id)
    if not row:
        return _error("外部委托申请不存在或不在数据范围内", 404)
    if row.status == "rejected":
        return _ok(row.to_admin_dict(), "该申请已驳回")
    if row.status != "submitted":
        return _error("只有已提交的外部申请可以驳回", 409)
    note = _text((request.get_json(silent=True) or {}).get("note"))
    if not note:
        return _error("请填写驳回原因")
    row.status = "rejected"
    row.review_note = note
    row.reviewer_id = g.current_user.id
    row.reviewer_name = g.current_user.name
    row.reviewed_at = datetime.utcnow()
    _event(row, "reject", "submitted", "rejected", g.current_user, kind="internal", note=note)
    add_operation_audit(
        "online_entrust.reject",
        "external_entrust_application",
        row.application_no,
        category="workflow",
        before={"status": "submitted"},
        after={"status": "rejected"},
        message=note,
    )
    db.session.commit()
    return _ok(row.to_admin_dict(), "外部委托申请已驳回")


def _application_for_internal_view(application_id):
    row = db.session.get(ExternalEntrustApplication, application_id)
    return row if row and _internal_scope_allows(g.current_user, row) else None


@admin_external_bp.get("/<int:application_id>/customer-services")
@require_auth
def get_admin_customer_services(application_id):
    denied = _require_queue_access()
    if denied:
        return denied
    application = _application_for_internal_view(application_id)
    if not application:
        return _error("外部委托申请不存在或不在数据范围内", 404)
    customer_documents = [
        _customer_document_payload(row)
        for row in ExternalCustomerDocument.query.filter_by(application_id=application.id)
        .order_by(ExternalCustomerDocument.id.desc())
        .all()
    ]
    shipments = [
        _shipment_payload(row)
        for row in ExternalShipment.query.filter_by(application_id=application.id)
        .order_by(ExternalShipment.id.desc())
        .all()
    ]
    notifications = [
        _portal_notification_payload(row)
        for row in ExternalPortalNotification.query.filter_by(application_id=application.id)
        .order_by(ExternalPortalNotification.id.desc())
        .limit(100)
        .all()
    ]
    return _ok({
        "documents": customer_documents,
        "shipments": shipments,
        "notifications": notifications,
    })


@admin_external_bp.post("/<int:application_id>/customer-documents")
@require_auth
def publish_admin_customer_document(application_id):
    application = _application_for_internal_view(application_id)
    if not application:
        return _error("外部委托申请不存在或不在数据范围内", 404)
    kind = _text(request.form.get("kind")).lower()
    if kind not in PUBLIC_DOCUMENT_KINDS:
        return _error("文件类型仅支持证书、发票或其他交付文件")
    denied = _require_customer_document_kind_access(kind)
    if denied:
        return denied
    if (
        application.status not in CUSTOMER_DOCUMENT_ALLOWED_APPLICATION_STATUSES
        or not application.internal_entrust_no
    ):
        return _error("客户文件只能发布到已受理并进入院内流程的委托", 409)

    document_no = _text(request.form.get("documentNo"))[:100]
    report_no = _text(request.form.get("reportNo"))[:40]
    related_report = None
    if kind == "invoice":
        bill = (
            FinanceBill.query.filter_by(
                entrust_no=application.internal_entrust_no
            )
            .order_by(FinanceBill.updated_at.desc(), FinanceBill.id.desc())
            .first()
        )
        if not bill or not _text(bill.invoice_no):
            return _error("该委托尚无已登记的正式发票，不能发布发票文件", 409)
        if document_no and document_no != bill.invoice_no:
            return _error("发票文件编号必须与该委托的正式发票号码一致", 409)
        document_no = bill.invoice_no
        report_no = ""
    elif kind == "certificate":
        if not document_no or not report_no:
            return _error("发布证书必须填写证书编号和关联报告编号")
        related_report = Report.query.filter_by(
            report_no=report_no,
            entrust_no=application.internal_entrust_no,
        ).first()
        if not related_report or not _public_report_is_queryable(related_report):
            return _error("关联报告不存在、尚未批准或不属于该客户委托", 409)

    denied = _require_customer_document_publish_access(
        kind,
        application,
        related_report=related_report,
    )
    if denied:
        return denied

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return _error("请选择要发布的文件")
    content_type = _customer_upload_content_type(upload)
    if not content_type:
        return _error("文件内容与扩展名不一致，仅支持有效的 PDF、PNG 或 JPG")
    try:
        file_row = persist_stream(
            upload.stream,
            category="portal_document",
            original_name=upload.filename,
            content_type=content_type or "application/octet-stream",
            created_by=g.current_user.account,
            max_bytes=CUSTOMER_DOCUMENT_MAX_BYTES,
        )
    except ValueError as error:
        return _error(str(error))
    title = _text(request.form.get("title")) or PUBLIC_DOCUMENT_KINDS[kind]
    row = ExternalCustomerDocument(
        application=application,
        kind=kind,
        title=title[:200],
        document_no=document_no,
        report_no=report_no,
        stored_file=file_row,
        status="published",
        issued_at=_parse_datetime(request.form.get("issuedAt")),
        created_by=g.current_user.account,
    )
    db.session.add(row)
    db.session.flush()
    _create_portal_notification(
        application,
        category="document",
        title=f"{PUBLIC_DOCUMENT_KINDS[kind]}已发布",
        content=f"{title}已可在客户工作台查看和下载。",
        link="/account?tab=documents",
        source_key=f"document:{row.id}:published",
    )
    add_operation_audit(
        "online_entrust.customer_document.publish",
        "external_customer_document",
        row.id,
        category="business",
        after={
            "applicationNo": application.application_no,
            "kind": kind,
            "documentNo": row.document_no,
            "fileSha256": file_row.sha256,
        },
    )
    db.session.commit()
    return _ok(_customer_document_payload(row), "客户交付文件已发布")


@admin_external_bp.delete("/<int:application_id>/customer-documents/<int:document_id>")
@require_auth
def withdraw_admin_customer_document(application_id, document_id):
    application = _application_for_internal_view(application_id)
    row = ExternalCustomerDocument.query.filter_by(
        id=document_id,
        application_id=application_id,
    ).first()
    if not application or not row:
        return _error("客户交付文件不存在或不在数据范围内", 404)
    related_report = None
    if row.kind == "certificate" and row.report_no:
        related_report = Report.query.filter_by(
            report_no=row.report_no,
            entrust_no=application.internal_entrust_no,
        ).first()
    denied = _require_customer_document_publish_access(
        row.kind,
        application,
        related_report=related_report,
    )
    if denied:
        return denied
    if row.status != "withdrawn":
        row.status = "withdrawn"
        add_operation_audit(
            "online_entrust.customer_document.withdraw",
            "external_customer_document",
            row.id,
            category="business",
            before={"status": "published"},
            after={"status": "withdrawn", "applicationNo": application.application_no},
        )
        db.session.commit()
    return _ok(_customer_document_payload(row), "客户交付文件已撤回")


@admin_external_bp.post("/<int:application_id>/customer-shipments")
@require_auth
def save_admin_customer_shipment(application_id):
    denied = _require_process_access("process")
    if denied:
        return denied
    application = _application_for_internal_view(application_id)
    if not application:
        return _error("外部委托申请不存在或不在数据范围内", 404)
    if (
        application.status not in CUSTOMER_DOCUMENT_ALLOWED_APPLICATION_STATUSES
        or not application.internal_entrust_no
    ):
        return _error("物流只能建立在已受理并进入院内流程的委托上", 409)
    body = request.get_json(silent=True) or {}
    carrier = _text(body.get("carrier"))[:80]
    tracking_no = _text(body.get("trackingNo"))[:100]
    status = _text(body.get("status")).lower() or "shipped"
    if not carrier or not tracking_no:
        return _error("承运公司和快递单号为必填项")
    if status not in PUBLIC_SHIPMENT_STATUS_LABELS:
        return _error("物流状态不受支持")
    row = None
    if body.get("id") not in (None, ""):
        try:
            row = ExternalShipment.query.filter_by(
                id=int(body["id"]), application_id=application.id
            ).first()
        except (TypeError, ValueError):
            row = None
        if not row:
            return _error("物流记录不存在", 404)
    if row is None:
        row = ExternalShipment(
            application=application,
            carrier=carrier,
            tracking_no=tracking_no,
            created_by=g.current_user.account,
        )
        db.session.add(row)
    row.shipment_type = _text(body.get("shipmentType"))[:30] or "report_delivery"
    row.carrier = carrier
    row.tracking_no = tracking_no
    row.status = status
    row.latest_event = _text(body.get("latestEvent"))[:300]
    if isinstance(body.get("events"), list):
        row.events = [
            {
                "time": _text(item.get("time"))[:40],
                "status": _text(item.get("status"))[:40],
                "location": _text(item.get("location"))[:120],
                "description": _text(item.get("description"))[:300],
            }
            for item in body["events"][:100]
            if isinstance(item, dict)
        ]
    elif not isinstance(row.events, list):
        row.events = []
    events = list(row.events or [])
    latest_key = (status, row.latest_event)
    previous_key = (
        _text(events[-1].get("status")),
        _text(events[-1].get("description")),
    ) if events and isinstance(events[-1], dict) else ("", "")
    if row.latest_event and latest_key != previous_key:
        events.append({
            "time": _iso(datetime.utcnow()),
            "status": status,
            "location": "",
            "description": row.latest_event,
        })
    row.events = events[-100:]
    row.shipped_at = _parse_datetime(body.get("shippedAt")) or row.shipped_at
    if status == "delivered":
        row.delivered_at = (
            _parse_datetime(body.get("deliveredAt"))
            or row.delivered_at
            or datetime.utcnow()
        )
    row.updated_by = g.current_user.account
    db.session.flush()
    _create_portal_notification(
        application,
        category="shipment",
        title=f"物流状态：{PUBLIC_SHIPMENT_STATUS_LABELS[status]}",
        content=row.latest_event or f"{carrier} {tracking_no} 的物流状态已更新。",
        link="/account?tab=shipments",
    )
    add_operation_audit(
        "online_entrust.customer_shipment.update",
        "external_shipment",
        row.id,
        category="business",
        after={
            "applicationNo": application.application_no,
            "carrier": carrier,
            "trackingNo": tracking_no,
            "status": status,
        },
    )
    db.session.commit()
    return _ok(_shipment_payload(row), "客户物流状态已更新")


@admin_external_bp.post("/<int:application_id>/customer-notifications")
@require_auth
def publish_admin_customer_notification(application_id):
    denied = _require_process_access("process")
    if denied:
        return denied
    application = _application_for_internal_view(application_id)
    if not application:
        return _error("外部委托申请不存在或不在数据范围内", 404)
    body = request.get_json(silent=True) or {}
    title = _text(body.get("title"))
    content = _text(body.get("content"))
    if not title or not content:
        return _error("消息标题和内容为必填项")
    row = _create_portal_notification(
        application,
        category=_text(body.get("category"))[:30] or "business",
        title=title,
        content=content,
        link=_text(body.get("link")) or f"/account/entrusts/{application.application_no}",
    )
    db.session.flush()
    add_operation_audit(
        "online_entrust.customer_notification.publish",
        "external_portal_notification",
        row.id,
        category="business",
        after={"applicationNo": application.application_no, "category": row.category},
    )
    db.session.commit()
    return _ok(_portal_notification_payload(row), "客户消息已发布")
