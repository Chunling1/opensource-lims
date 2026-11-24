"""关键业务写操作审计。

调用方负责与业务变更使用同一个 db.session 提交，保证业务结果和审计记录一致。
后台任务可显式传入 actor，避免依赖请求上下文。
"""
from datetime import datetime
import re
from uuid import uuid4

from flask import g, has_request_context, request
from sqlalchemy import func

from .extensions import db
from .models import OperationAudit


TRACE_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._:-]{0,63}$")


def _operation_trace_id(explicit=""):
    """Return one safe trace id for every audit row in the current request.

    A trusted gateway may supply ``X-Trace-Id``.  Invalid values are ignored
    instead of being persisted, and all audit calls in the same request reuse
    the generated identifier so a multi-row Command can be reconstructed.
    Background tasks may pass ``trace_id`` explicitly; otherwise each call
    receives a new identifier.
    """

    candidate = str(explicit or "").strip()
    if not candidate and has_request_context():
        candidate = str(request.headers.get("X-Trace-Id") or "").strip()
        if not candidate:
            candidate = str(getattr(g, "operation_trace_id", "") or "").strip()
    if not TRACE_ID_RE.fullmatch(candidate):
        candidate = uuid4().hex
    if has_request_context():
        g.operation_trace_id = candidate
    return candidate


def add_operation_audit(
    action,
    object_type,
    object_id,
    *,
    category="business",
    before=None,
    after=None,
    success=True,
    message="",
    actor=None,
    ip_address="",
    trace_id="",
):
    user = actor
    if user is None and has_request_context():
        user = getattr(g, "current_user", None)
    if not ip_address and has_request_context():
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    row = OperationAudit(
        category=category,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        trace_id=_operation_trace_id(trace_id),
        user_id=getattr(user, "id", None),
        account=getattr(user, "account", "") or "",
        user_name=getattr(user, "name", "") or "",
        ip_address=ip_address or "",
        before_data=before,
        after_data=after,
        success=bool(success),
        message=message or "",
    )
    db.session.add(row)
    return row


def latest_operation_audit(object_type, object_id, action):
    from .list_reads import latest_audit
    return latest_audit(str(object_type), str(object_id), str(action),
                        lambda: _latest_operation_audit_uncached(object_type, object_id, action))


def _latest_operation_audit_uncached(object_type, object_id, action):
    return (
        OperationAudit.query.filter_by(
            object_type=str(object_type),
            object_id=str(object_id),
            action=str(action),
            success=True,
        )
        .order_by(OperationAudit.id.desc())
        .first()
    )


def completion_owned_by(user, object_type, object_id, action):
    """Only the user who completed a workflow node may undo that completion."""
    row = latest_operation_audit(object_type, object_id, action)
    if row is None:
        return False, None
    if row.user_id is not None and user.id is not None:
        return row.user_id == user.id, row
    return bool(row.account and row.account == user.account), row


def records_by_edit_time(records, object_type, object_id, fallback_time=None):
    """Return ``(record, edited_at)`` pairs ordered by the latest successful edit."""
    records = list(records)
    if not records:
        return []
    identifiers = list(dict.fromkeys(str(object_id(record)) for record in records))
    from .list_reads import prime_identifiers
    prime_identifiers(object_type, identifiers, records)
    latest = {}
    for start in range(0, len(identifiers), 500):
        batch = identifiers[start:start + 500]
        audit_rows = (
            db.session.query(OperationAudit.object_id, func.max(OperationAudit.created_at))
            .filter(
                OperationAudit.object_type == object_type,
                OperationAudit.object_id.in_(batch),
                OperationAudit.success.is_(True),
            )
            .group_by(OperationAudit.object_id)
            .all()
        )
        latest.update({str(identifier): edited_at for identifier, edited_at in audit_rows})

    def edit_time(record):
        identifier = str(object_id(record))
        fallback = fallback_time(record) if fallback_time else None
        return latest.get(identifier) or fallback

    def sort_key(record):
        stable_id = getattr(record, "id", 0) or 0
        return edit_time(record) or datetime.min, stable_id

    ordered = sorted(records, key=sort_key, reverse=True)
    return [(record, edit_time(record)) for record in ordered]


def edit_time_text(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""
