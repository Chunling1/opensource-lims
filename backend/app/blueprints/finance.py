"""财务六节点接口：服务端状态机、RBAC、幂等和审计在同一事务中完成。"""
import time

from flask import Blueprint, g, jsonify, request
from sqlalchemy import update
from sqlalchemy.exc import OperationalError

from ..platform.audit import add_operation_audit
from ..platform.identity import has_org_wide_business_scope
from ..extensions import db
from ..finance_service import (
    FinanceRuleError,
    confirm_payment,
    is_duplicate,
    issue_invoice,
    price_bill,
    refund_bill,
    register_payment,
    settle_bill,
)
from ..models import FinanceBill, OperationAudit
from ..security import require_auth
from ..workflow_dates import business_date, latest_workflow_date, parse_date

bp = Blueprint("finance", __name__, url_prefix="/api/finance")

NODE_STATUSES = {
    "pricing": ["待计价"],
    "payment_registration": ["待收款"],
    "payment_confirmation": ["待收款确认"],
    "invoice": ["待开票"],
    "settlement": ["待结算"],
    "account_refund": ["已结算", "部分退款"],
}
COMMANDS = {
    "price": ("pricing", "finance.pricing.execute", price_bill),
    "payment-register": (
        "payment_registration", "finance.payment.register", register_payment,
    ),
    "payment-confirm": (
        "payment_confirmation", "finance.payment.confirm", confirm_payment,
    ),
    "invoice": ("invoice", "finance.invoice.issue", issue_invoice),
    "settle": ("settlement", "finance.settlement.execute", settle_bill),
    "refund": ("account_refund", "finance.refund.execute", refund_bill),
}

_SQLITE_BUSY_MAX_ATTEMPTS = 3
_SQLITE_BUSY_RETRY_SECONDS = 0.025


def _scope(query, user):
    if has_org_wide_business_scope(user):
        return query
    if str(user.data_scope_type or "").strip() == "self":
        identities = {
            str(getattr(user, "account", "") or "").strip(),
            str(getattr(user, "name", "") or "").strip(),
        }
        identities.discard("")
        return (
            query.filter(FinanceBill.created_by.in_(sorted(identities)))
            if identities
            else query.filter(db.false())
        )
    names = user.data_department_names()
    return query.filter(FinanceBill.department.in_(names)) if names else query.filter(db.false())


def _can_page(user, node):
    return f"finance.{node}.view" in user.permission_codes()


def _bill_row(bill, workflow_dates=None):
    def latest(object_type, object_id, action):
        if workflow_dates is not None:
            return workflow_dates.get((str(object_id), action))
        return latest_workflow_date(object_type, object_id, action)

    price_at = latest(
        "finance_bill", bill.id, "finance.pricing.execute",
    ) or business_date(bill.created_at)
    payment_confirmed_at = latest(
        "finance_bill", bill.id, "finance.payment.confirm",
    ) or parse_date(bill.payment_date)
    dates = {
        "priceAt": price_at,
        "paymentPreviousAt": max(
            (value for value in (price_at, payment_confirmed_at) if value),
            default=None,
        ),
        "paymentConfirmedAt": payment_confirmed_at,
        "invoiceAt": latest(
            "finance_bill", bill.id, "finance.invoice.issue",
        ) or parse_date(bill.invoice_date),
        "settlementAt": latest(
            "finance_bill", bill.id, "finance.settlement.execute",
        ) or parse_date(bill.settlement_date),
        "refundAt": latest(
            "finance_bill", bill.id, "finance.refund.execute",
        ) or parse_date(bill.refund_date),
    }
    workflow_dates = {
        key: value.isoformat() if value else "" for key, value in dates.items()
    }
    row = bill.to_row()
    row.update(workflow_dates)
    row["workflowDates"] = workflow_dates
    return row


def _claim_command(bill, command_key):
    """Atomically claim the bill version held by this request.

    ``version`` prevents any two commands from mutating one snapshot.  The
    idempotency key is written by the same conditional UPDATE, so a same-key
    loser can reload and return the established idempotent response.  Both
    values roll back together if validation, audit or commit fails.
    """

    expected_version = int(bill.version or 0)
    conditions = (
        FinanceBill.id == bill.id,
        FinanceBill.version == expected_version,
        FinanceBill.status == bill.status,
    )
    values = {FinanceBill.version: expected_version + 1}
    if command_key:
        conditions += db.or_(
            FinanceBill.last_command_key.is_(None),
            FinanceBill.last_command_key != command_key,
        ),
        values[FinanceBill.last_command_key] = command_key
    result = db.session.execute(
        update(FinanceBill)
        .where(*conditions)
        .values(values)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def _is_retryable_sqlite_busy(error):
    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return False
    message = str(getattr(error, "orig", error)).lower()
    return "database is locked" in message or "database table is locked" in message


def _idempotent_response(bill):
    return jsonify({
        "code": 0,
        "message": "操作已处理，请勿重复提交",
        "data": _bill_row(bill),
    })


@bp.post("/bills/query")
@require_auth
def query_bills():
    body = request.get_json(silent=True) or {}
    node = (body.get("node") or "pricing").strip()
    if node not in NODE_STATUSES or not _can_page(g.current_user, node):
        return jsonify({"code": 403, "message": "无该财务节点查看权限", "data": None}), 200
    # A processing endpoint only returns the states owned by that node.  A
    # future all-lifecycle finance query must be a separate read-only module.
    query = _scope(FinanceBill.query, g.current_user).filter(
        FinanceBill.status.in_(NODE_STATUSES[node])
    )
    keyword = (body.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(db.or_(
            FinanceBill.bill_no.like(like), FinanceBill.entrust_no.like(like),
            FinanceBill.contract_no.like(like), FinanceBill.client.like(like),
            FinanceBill.project_name.like(like),
        ))
    status = (body.get("status") or "").strip()
    if status:
        query = query.filter(FinanceBill.status == status)
    try:
        page = max(1, int(body.get("page") or 1))
        size = min(100, max(1, int(body.get("size") or 20)))
    except (TypeError, ValueError):
        page, size = 1, 20
    total = query.count()
    rows = query.order_by(
        FinanceBill.updated_at.desc(),
        FinanceBill.id.desc(),
    ).offset((page - 1) * size).limit(size).all()
    # Preserve the latest successful workflow timestamp, without reading five
    # full audit snapshots for every row in the page.
    from sqlalchemy import func
    dates = {
        (object_id, action): business_date(moment)
        for object_id, action, moment in db.session.query(
            OperationAudit.object_id, OperationAudit.action,
            func.max(OperationAudit.created_at),
        ).filter(
            OperationAudit.category == 'workflow',
            OperationAudit.object_type == 'finance_bill',
            OperationAudit.object_id.in_([str(row.id) for row in rows]),
            OperationAudit.success.is_(True),
        ).group_by(OperationAudit.object_id, OperationAudit.action).all()
    } if rows else {}
    return jsonify({"code": 0, "message": "ok", "data": {
        "rows": [_bill_row(row, dates) for row in rows], "total": total, "page": page, "size": size,
        "nodeStatuses": NODE_STATUSES[node],
    }})


@bp.get("/bills/<int:bill_id>")
@require_auth
def bill_detail(bill_id):
    node = str(request.args.get("node") or "").strip()
    if node not in NODE_STATUSES or not _can_page(g.current_user, node):
        return jsonify({"code": 403, "message": "无当前财务节点查看权限", "data": None}), 200
    bill = _scope(FinanceBill.query, g.current_user).filter(FinanceBill.id == bill_id).first()
    if not bill:
        return jsonify({"code": 1, "message": "费用单不存在或不在数据范围内", "data": None}), 200
    if bill.status not in NODE_STATUSES[node]:
        return jsonify({"code": 403, "message": "该费用单当前不属于本财务节点", "data": None}), 200
    events = OperationAudit.query.filter_by(object_type="finance_bill", object_id=str(bill.id)) \
        .order_by(OperationAudit.id.desc()).limit(100).all()
    return jsonify({"code": 0, "message": "ok", "data": {
        "bill": _bill_row(bill), "events": [event.to_dict() for event in events],
    }})


@bp.post("/bills/<int:bill_id>/<command>")
@require_auth
def run_command(bill_id, command):
    config = COMMANDS.get(command)
    if not config:
        return jsonify({"code": 1, "message": "未知财务操作", "data": None}), 200
    node, action_code, handler = config
    if not _can_page(g.current_user, node):
        return jsonify({
            "code": 403,
            "message": "无当前财务节点功能权限",
            "data": None,
        }), 200
    if action_code not in g.current_user.action_codes():
        return jsonify({"code": 403, "message": "无该财务操作权限", "data": None}), 200
    body = request.get_json(silent=True) or {}
    command_key = (body.get("idempotencyKey") or "").strip()
    for attempt in range(_SQLITE_BUSY_MAX_ATTEMPTS):
        try:
            bill = _scope(FinanceBill.query, g.current_user).filter(
                FinanceBill.id == bill_id
            ).first()
            if not bill:
                return jsonify({
                    "code": 1,
                    "message": "费用单不存在或不在数据范围内",
                    "data": None,
                }), 200
            if is_duplicate(bill, command_key):
                return _idempotent_response(bill)
            if bill.status not in NODE_STATUSES[node]:
                return jsonify({
                    "code": 1,
                    "message": f"费用单当前为「{bill.status}」，不能执行此操作",
                    "data": {"status": bill.status},
                }), 200

            before = bill.to_row()
            if not _claim_command(bill, command_key):
                db.session.rollback()
                db.session.expire_all()
                current = _scope(FinanceBill.query, g.current_user).filter(
                    FinanceBill.id == bill_id
                ).first()
                if not current:
                    return jsonify({
                        "code": 1,
                        "message": "费用单不存在或不在数据范围内",
                        "data": None,
                    }), 200
                if is_duplicate(current, command_key):
                    return _idempotent_response(current)
                if current.status not in NODE_STATUSES[node]:
                    return jsonify({
                        "code": 1,
                        "message": f"费用单当前为「{current.status}」，不能执行此操作",
                        "data": {"status": current.status},
                    }), 200
                return jsonify({
                    "code": 1,
                    "message": "财务操作并发冲突，请刷新后重试",
                    "data": {"status": current.status},
                }), 200

            try:
                handler(bill, body, g.current_user, command_key)
            except FinanceRuleError as error:
                db.session.rollback()
                return jsonify({
                    "code": 1,
                    "message": str(error),
                    "data": {"status": before["status"]},
                }), 200
            add_operation_audit(
                action_code, "finance_bill", bill.id, category="workflow", before=before,
                after=bill.to_row(), message=(body.get("reason") or body.get("note") or "").strip(),
            )
            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "财务操作已完成",
                "data": _bill_row(bill),
            })
        except OperationalError as error:
            retryable = _is_retryable_sqlite_busy(error)
            db.session.rollback()
            if retryable and attempt + 1 < _SQLITE_BUSY_MAX_ATTEMPTS:
                time.sleep(_SQLITE_BUSY_RETRY_SECONDS * (attempt + 1))
                continue
            raise
        except Exception:
            db.session.rollback()
            raise

    # The bounded loop always returns or raises; retain an explicit fail-closed
    # guard so a future edit cannot silently fall through.
    raise RuntimeError("财务操作重试状态异常")
