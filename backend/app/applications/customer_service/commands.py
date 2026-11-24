"""Customer-service Commands shared by HTTP and future portal adapters."""

from __future__ import annotations
from ...workflow_dates import business_today

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
import time
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError

from ..entrust import (
    EntrustCreationInput,
    create_external_portal_entrust_from_customer_acceptance,
)
from ...extensions import db
from ...models import (
    ExternalEntrustApplication,
    ExternalEntrustEvent,
    ExternalPortalNotification,
    ExternalScheme,
)
from ...platform.audit import add_operation_audit
from ...platform.identity import user_has_org_wide_scope
from ...platform.numbering.service import (
    CustomerAcceptanceNumberReservation,
    persist_customer_acceptance_number_gap,
    reserve_customer_acceptance_number_in_transaction,
)


PROCESS_ACTION_GRANTS = {
    "process": {
        "online_entrust.application.process",
        "online_entrust.process",  # compatibility with early pilot grants
    },
    "accept": {
        "online_entrust.application.accept",
        "online_entrust.accept",  # compatibility with early pilot grants
    },
    "reject": {
        "online_entrust.application.reject",
        "online_entrust.reject",  # compatibility with early pilot grants
    },
}


_ACCEPTANCE_CLAIM_PREFIX = "__customer_accepting__:"
_SQLITE_BUSY_MAX_ATTEMPTS = 3
_SQLITE_BUSY_RETRY_SECONDS = 0.025


EXTERNAL_SCHEME_FIELDS = {
    "externalPublished": "published",
    "externalSlug": "slug",
    "externalPublicTitle": "public_title",
    "externalTitle": "public_title",
    "title": "public_title",
    "externalSubtitle": "subtitle",
    "externalSummary": "summary",
    "summary": "summary",
    "externalDescription": "description",
    "externalCategory": "category",
    "category": "category",
    "externalCoverUrl": "cover_url",
    "externalPriceMode": "price_mode",
    "priceType": "price_mode",
    "externalPriceMin": "price_min",
    "priceMin": "price_min",
    "externalPriceMax": "price_max",
    "priceMax": "price_max",
    "externalPriceUnit": "price_unit",
    "priceUnit": "price_unit",
    "externalOriginalPrice": "original_price",
    "originalPrice": "original_price",
    "externalServiceCycleText": "service_cycle_text",
    "externalTurnaroundDays": "turnaround_days",
    "turnaroundDays": "turnaround_days",
    "externalFeatureTags": "feature_tags",
    "tags": "feature_tags",
    "externalDeliverables": "deliverables",
    "externalPricingRules": "pricing_rules",
    "externalDisplayOrder": "display_order",
    "sort": "display_order",
    "promotion": "promotion",
    "featured": "featured",
    "detail": "detail",
    "sampleRequirements": "sample_requirements",
    "contactPhone": "contact_phone",
}


def _external_values(body):
    nested = body.get("externalDisplay")
    values = dict(nested) if isinstance(nested, dict) else {}
    for flat, field in EXTERNAL_SCHEME_FIELDS.items():
        if flat in body:
            values[field] = body.get(flat)
    return values


def _external_money(value, label):
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label}格式不正确") from None
    if result < 0:
        raise ValueError(f"{label}不能小于 0")
    return result


def _default_external_slug(project):
    source = str(project.display_code or project.number_code or project.code or project.id).lower()
    slug = "-".join(part for part in re.sub(r"[^a-z0-9]+", "-", source).split("-") if part)
    return slug or f"project-{project.id}"


def apply_external_scheme(project, body, actor):
    """Create or update the customer-service-owned scheme projection.

    The caller owns the surrounding project transaction.  This Command never
    commits, so a project update and its external projection remain atomic.
    """

    values = _external_values(body)
    row = ExternalScheme.query.filter_by(project_id=project.id).first()
    if not values and row is None:
        return None
    if row is None:
        row = ExternalScheme(
            project=project,
            slug=_default_external_slug(project),
            public_title=project.name,
            price_mode="quote",
            published=False,
            feature_tags=[],
            deliverables=[],
            pricing_rules={},
        )
        db.session.add(row)
    if "published" in values:
        row.published = bool(values["published"])
    if "slug" in values:
        slug = str(values["slug"] or "").strip().lower() or _default_external_slug(project)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("外部展示地址只能使用小写字母、数字和中划线")
        conflict = ExternalScheme.query.filter(
            ExternalScheme.slug == slug,
            ExternalScheme.id != (row.id or 0),
        ).first()
        if conflict:
            raise ValueError("外部展示地址已被其他检测方案使用")
        row.slug = slug
    for field in (
        "public_title", "subtitle", "summary", "description", "category",
        "cover_url", "price_unit", "service_cycle_text",
    ):
        if field in values:
            setattr(row, field, str(values[field] or "").strip())
    if not str(row.public_title or "").strip():
        row.public_title = project.name
    if "price_mode" in values:
        mode = str(values["price_mode"] or "quote").strip().lower()
        if mode == "negotiable":
            mode = "quote"
        if mode not in {"quote", "fixed", "from", "range"}:
            raise ValueError("外部预定价方式无效")
        row.price_mode = mode
    for field, label in (
        ("price_min", "最低预估价"),
        ("price_max", "最高预估价"),
        ("original_price", "原价"),
    ):
        if field in values:
            setattr(row, field, _external_money(values[field], label))
    if row.price_min is not None and row.price_max is not None and row.price_min > row.price_max:
        raise ValueError("最低预估价不能高于最高预估价")
    if "turnaround_days" in values:
        value = values["turnaround_days"]
        if value in (None, ""):
            row.turnaround_days = None
        else:
            try:
                row.turnaround_days = max(1, int(value))
            except (TypeError, ValueError):
                raise ValueError("服务周期天数格式不正确") from None
    if "display_order" in values:
        try:
            row.display_order = int(values["display_order"] or 0)
        except (TypeError, ValueError):
            raise ValueError("外部展示排序格式不正确") from None
    for field in ("feature_tags", "deliverables"):
        if field in values:
            value = values[field]
            setattr(row, field, value if isinstance(value, list) else [])
    if "pricing_rules" in values:
        value = values["pricing_rules"]
        row.pricing_rules = value if isinstance(value, (dict, list)) else {}
    for field in ("promotion", "detail", "sample_requirements", "contact_phone"):
        if field in values:
            setattr(row, field, str(values[field] or "").strip())
    if "featured" in values:
        row.featured = bool(values["featured"])
    if "detail" in values and "description" not in values:
        row.description = row.detail
    if row.published and not row.published_at:
        row.published_at = datetime.utcnow()
    if not project.active:
        row.published = False
    row.version = int(row.version or 0) + 1
    row.updated_by = getattr(actor, "account", "") or ""
    return row


def unpublish_external_scheme_for_project(project_id: int, actor) -> None:
    """Disable a project's customer-facing scheme without committing."""

    row = ExternalScheme.query.filter_by(project_id=project_id).first()
    if row is None:
        return
    row.published = False
    row.updated_by = getattr(actor, "account", "") or ""
    row.version = int(row.version or 0) + 1


@dataclass(frozen=True)
class AcceptExternalApplicationResult:
    """Transport-neutral result of accepting one external application."""

    code: int
    message: str
    application: ExternalEntrustApplication | None = None
    http_status: int = 200

    def response_payload(self) -> dict[str, Any]:
        data = self.application.to_admin_dict() if self.application else None
        return {"code": self.code, "message": self.message, "data": data}


def _text(value: Any) -> str:
    return str(value or "").strip()


def has_internal_process_access(user, action: str) -> bool:
    """Return the existing action-grant decision without widening scope."""

    if user.role_key in {"admin", "super_admin"}:
        return True
    granted = set(user.action_codes())
    action_grants = PROCESS_ACTION_GRANTS.get(action, set())
    return bool(
        granted.intersection(PROCESS_ACTION_GRANTS["process"])
        or granted.intersection(action_grants)
    )


def internal_scope_allows(user, application: ExternalEntrustApplication) -> bool:
    """Apply the production department-scope rule to a source application."""

    if (
        user.role_key in {"admin", "super_admin"}
        or user.data_scope_type == "all"
        or user_has_org_wide_scope(user)
    ):
        return True
    department_ids = set(user.data_department_ids())
    if application.assigned_department_id:
        return application.assigned_department_id in department_ids
    project = application.project
    return bool(project and project.department_id in department_ids)


def _record_acceptance_event(
    application: ExternalEntrustApplication,
    actor,
    *,
    note: str,
) -> ExternalEntrustEvent:
    """Record the accepted fact and its customer notification in-transaction."""

    form_data = application.form_data if isinstance(application.form_data, dict) else {}
    form_hash = hashlib.sha256(
        json.dumps(
            form_data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    event = ExternalEntrustEvent(
        application=application,
        action="accept",
        from_status="submitted",
        to_status="accepted",
        actor_kind="internal",
        actor_id=getattr(actor, "id", None),
        actor_account=getattr(actor, "account", "") or "",
        actor_name=getattr(actor, "name", "") or "",
        note=note,
        snapshot={
            "applicationNo": application.application_no,
            "status": application.status,
            "formVersion": application.form_version,
            "formDataHash": form_hash,
            "internalEntrustNo": application.internal_entrust_no or "",
            "reviewNote": application.review_note or "",
        },
    )
    db.session.add(event)
    db.session.add(ExternalPortalNotification(
        external_account_id=application.external_account_id,
        application_id=application.id,
        category="entrust",
        title="委托已受理",
        content=(
            note or "您的在线委托已受理，并已进入院内检测流程。"
        )[:500],
        link=f"/account/entrusts/{application.application_no}",
        source_key=None,
    ))
    return event


def _entrust_creation_input(
    application: ExternalEntrustApplication,
    actor,
) -> EntrustCreationInput:
    """Project the immutable customer source into formal entrust input."""

    form = application.form_data if isinstance(application.form_data, dict) else {}
    snapshot = (
        application.scheme_snapshot
        if isinstance(application.scheme_snapshot, dict)
        else {}
    )
    project = application.project
    department = project.department.name if project and project.department else ""
    client = _text(
        form.get("companyName")
        or form.get("client")
        or application.account.company_name
    )
    project_name = _text(
        form.get("projectName")
        or snapshot.get("publicTitle")
        or snapshot.get("name")
    )
    amount = (
        ""
        if application.estimated_amount is None
        else f"{application.estimated_amount:.2f}"
    )
    info = dict(form)
    info.update({
        "sourceChannel": "external_portal",
        "sourceExternalApplicationNo": application.application_no,
        "sourceExternalApplicationId": application.id,
        "sourceExternalAccountId": application.external_account_id,
        "sourceExternalSubmittedAt": (
            application.submitted_at.isoformat(timespec="seconds")
            if application.submitted_at
            else ""
        ),
        "handleDept": department,
        "handleDepartment": department,
        "handler": actor.name,
        "onlineEntrustState": "网上委托待补全",
        "needsInternalCompletion": True,
        "completionNotice": "请在委托登记中补充合同及内部必填字段后再完成登记",
        "contractPartyA": client,
        "consignor": _text(
            form.get("contactName")
            or form.get("consignor")
            or application.account.name
        ),
        "consignorPhone": _text(
            form.get("contactMobile")
            or form.get("contactPhone")
            or form.get("consignorPhone")
            or application.account.mobile
        ),
        "projectName": project_name,
        "projectAddress": _text(form.get("projectAddress")),
        "sampleName": _text(form.get("sampleName")),
        "specification": _text(
            form.get("specification") or form.get("sampleModel")
        ),
        "manufacturer": _text(form.get("manufacturer")),
        "sampleAmount": _text(form.get("quantity") or form.get("sampleQuantity")),
        "quantityUnit": _text(form.get("quantityUnit")),
        "externalSchemeSnapshot": snapshot,
        "externalQuoteSnapshot": application.quote_snapshot or {},
        "externalApplicationSnapshot": application.to_public_dict(),
    })
    project_type = _text(
        (
            form.get("projectType")
            or snapshot.get("category")
            or (project.workflow_config or {}).get("testCategory")
        )
        if project
        else ""
    )
    return EntrustCreationInput(
        client=client,
        project_name=project_name,
        project_type=project_type,
        amount=amount,
        department=department,
        owner=actor.name,
        info=info,
    )


def _claim_submitted_application(application_id: int) -> bool:
    """Atomically claim one unaccepted submitted application in this transaction."""

    sentinel = f"{_ACCEPTANCE_CLAIM_PREFIX}{application_id}"
    result = db.session.execute(
        update(ExternalEntrustApplication)
        .where(
            ExternalEntrustApplication.id == application_id,
            ExternalEntrustApplication.status == "submitted",
            ExternalEntrustApplication.internal_entrust_no.is_(None),
            ExternalEntrustApplication.internal_entrust_id.is_(None),
        )
        .values(internal_entrust_no=sentinel)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def _result_after_failed_acceptance_claim(
    user,
    application_id: int,
) -> AcceptExternalApplicationResult:
    """Reload after a losing CAS and preserve existing idempotent semantics."""

    db.session.rollback()
    db.session.expire_all()
    existing = db.session.get(ExternalEntrustApplication, application_id)
    if not existing or not internal_scope_allows(user, existing):
        return AcceptExternalApplicationResult(
            1,
            "外部委托申请不存在或不在数据范围内",
            http_status=404,
        )
    if existing.status == "accepted" and existing.internal_entrust_id:
        return AcceptExternalApplicationResult(0, "该申请已受理", existing)
    if existing.status != "submitted":
        return AcceptExternalApplicationResult(
            1,
            "只有已提交的外部申请可以受理",
            http_status=409,
        )
    return AcceptExternalApplicationResult(
        1,
        "受理并发冲突，请刷新后重试",
        http_status=409,
    )


def _is_retryable_sqlite_busy(exc: OperationalError) -> bool:
    """Recognize only SQLite lock contention; never hide other DB failures."""

    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return False
    message = str(getattr(exc, "orig", exc)).lower()
    return "database is locked" in message or "database table is locked" in message


def _rollback_acceptance_and_preserve_gap(
    reservation: CustomerAcceptanceNumberReservation | None,
) -> None:
    """Roll back all business facts, then durably preserve an issued serial."""

    db.session.rollback()
    if reservation is not None:
        # This runs only after the full business rollback.  Failure is surfaced
        # explicitly by the numbering owner and is never silently swallowed.
        persist_customer_acceptance_number_gap(reservation)


def accept_external_application(
    user,
    application_id: int,
    *,
    note: str = "",
) -> AcceptExternalApplicationResult:
    """Accept a submitted application and create its formal entrust atomically.

    A conditional UPDATE is the cross-process concurrency guard.  Its temporary
    sentinel, the number waterline and every business fact remain in one
    transaction, so the sentinel can never become externally visible.  SQLite
    lock contention is retried with a small strict limit; exhaustion is raised.
    """

    if not has_internal_process_access(user, "accept"):
        return AcceptExternalApplicationResult(
            1,
            "仅有查看权限不能办理网上委托，请联系管理员授权",
            http_status=403,
        )

    note = _text(note)
    for attempt in range(_SQLITE_BUSY_MAX_ATTEMPTS):
        reservation: CustomerAcceptanceNumberReservation | None = None
        try:
            application = ExternalEntrustApplication.query.filter_by(
                id=application_id
            ).first()
            if not application or not internal_scope_allows(user, application):
                return AcceptExternalApplicationResult(
                    1,
                    "外部委托申请不存在或不在数据范围内",
                    http_status=404,
                )
            if application.status == "accepted" and application.internal_entrust_id:
                return AcceptExternalApplicationResult(0, "该申请已受理", application)
            if application.status != "submitted":
                return AcceptExternalApplicationResult(
                    1,
                    "只有已提交的外部申请可以受理",
                    http_status=409,
                )
            if not _claim_submitted_application(application_id):
                return _result_after_failed_acceptance_claim(user, application_id)

            reservation = reserve_customer_acceptance_number_in_transaction(
                business_today().year
            )
            entrust = create_external_portal_entrust_from_customer_acceptance(
                _entrust_creation_input(application, user),
                reservation,
            )
            entrust_no = entrust.entrust_no
            project = application.project
            now = datetime.utcnow()
            application.status = "accepted"
            application.internal_entrust = entrust
            application.internal_entrust_no = entrust_no
            application.assigned_department_id = (
                project.department_id if project else None
            )
            application.assigned_user_id = user.id
            application.reviewer_id = user.id
            application.reviewer_name = user.name
            application.review_note = note
            application.reviewed_at = now
            application.converted_at = now
            _record_acceptance_event(application, user, note=note)
            add_operation_audit(
                "online_entrust.accept",
                "external_entrust_application",
                application.application_no,
                category="workflow",
                before={"status": "submitted"},
                after={"status": "accepted", "internalEntrustNo": entrust_no},
                message=note,
                actor=user,
            )
            db.session.commit()
            return AcceptExternalApplicationResult(
                0,
                f"已受理并生成委托单 {entrust_no}",
                application,
            )
        except OperationalError as exc:
            retryable = _is_retryable_sqlite_busy(exc)
            _rollback_acceptance_and_preserve_gap(reservation)
            if retryable and attempt + 1 < _SQLITE_BUSY_MAX_ATTEMPTS:
                time.sleep(_SQLITE_BUSY_RETRY_SECONDS * (attempt + 1))
                continue
            raise
        except IntegrityError:
            _rollback_acceptance_and_preserve_gap(reservation)
            return _result_after_failed_acceptance_claim(user, application_id)
        except Exception:
            _rollback_acceptance_and_preserve_gap(reservation)
            raise

    raise RuntimeError("受理重试状态异常")


__all__ = [
    "AcceptExternalApplicationResult",
    "PROCESS_ACTION_GRANTS",
    "accept_external_application",
    "has_internal_process_access",
    "internal_scope_allows",
]
