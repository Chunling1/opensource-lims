"""财务费用单命令服务：状态校验、金额变更与幂等控制集中在此。"""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .extensions import db
from .models import Entrust, FinanceBill
from .workflow_dates import (
    business_date,
    latest_workflow_date,
    parse_date,
    validate_after_previous,
)

MONEY = Decimal("0.01")


class FinanceRuleError(ValueError):
    pass


class _OrdinaryActor:
    @staticmethod
    def permission_codes():
        return []


def money(value, field="金额"):
    try:
        result = Decimal(str(value or "0").replace(",", "").replace("¥", "").strip()).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )
        if not result.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise FinanceRuleError(f"{field}格式不正确") from None
    if result < 0:
        raise FinanceRuleError(f"{field}不能为负数")
    return result


def suggested_amount(value):
    cleaned = re.sub(r"[^0-9.\-]", "", value or "")
    try:
        return money(cleaned) if cleaned else Decimal("0.00")
    except FinanceRuleError:
        return Decimal("0.00")


def ensure_finance_bill(entrust, operator=""):
    bill = FinanceBill.query.filter_by(entrust_no=entrust.entrust_no).first()
    if bill:
        return bill
    bill = FinanceBill(
        bill_no=f"FY-{entrust.entrust_no}", entrust_no=entrust.entrust_no,
        contract_no=entrust.contract_no, client=entrust.client, project_name=entrust.project_name,
        department=entrust.department, amount_due=suggested_amount(entrust.amount),
        status="待计价", created_by=operator or entrust.owner, updated_by=operator or entrust.owner,
    )
    db.session.add(bill)
    return bill


def sync_finance_bills():
    existing = {row[0] for row in FinanceBill.query.with_entities(FinanceBill.entrust_no).all()}
    created = 0
    for entrust in Entrust.query.filter_by(status="委托完成").order_by(Entrust.id).all():
        if entrust.entrust_no not in existing:
            ensure_finance_bill(entrust, "系统迁移")
            created += 1
    if created:
        db.session.commit()
    return created


def _require_status(bill, *statuses):
    if bill.status not in statuses:
        raise FinanceRuleError(f"费用单当前为「{bill.status}」，不能执行此操作")


def _actor_name(actor):
    return (getattr(actor, "name", "") or str(actor or "")).strip()


def _touch(bill, actor, command_key):
    bill.updated_by = _actor_name(actor)
    bill.version = (bill.version or 0) + 1
    if command_key:
        bill.last_command_key = command_key


def is_duplicate(bill, command_key):
    return bool(command_key and bill.last_command_key == command_key)


def _validated_date(actor, value, previous_date, field_label, previous_label):
    effective = str(value or "").strip()
    if not effective:
        raise FinanceRuleError(f"{field_label}为必填")
    validation_actor = actor if callable(getattr(actor, "permission_codes", None)) else _OrdinaryActor()
    error = validate_after_previous(
        validation_actor, effective, previous_date, field_label, previous_label,
    )
    if error:
        raise FinanceRuleError(error)
    return parse_date(effective).isoformat()


def _latest_date(*values):
    dates = [value for value in values if value]
    return max(dates) if dates else None


def price_bill(bill, payload, actor, command_key=""):
    _require_status(bill, "待计价")
    amount_due = money(payload.get("amountDue"), "应收金额")
    if amount_due <= 0:
        raise FinanceRuleError("应收金额必须大于 0")
    bill.amount_due = amount_due
    bill.note = (payload.get("note") or "").strip()
    bill.status = "待收款"
    _touch(bill, actor, command_key)


def register_payment(bill, payload, actor, command_key=""):
    _require_status(bill, "待收款")
    amount = money(payload.get("amount"), "本次收款金额")
    outstanding = (bill.amount_due or 0) - (bill.amount_received or 0)
    if amount <= 0 or amount > outstanding:
        raise FinanceRuleError(f"本次收款金额应大于 0 且不超过未收金额 {outstanding:.2f}")
    method = (payload.get("paymentMethod") or "").strip()
    reference = (payload.get("paymentReference") or "").strip()
    if not method or not reference:
        raise FinanceRuleError("收款方式和银行流水号/凭证号为必填项")
    bill.pending_payment = amount
    bill.payment_method = method
    bill.payment_reference = reference
    priced_at = latest_workflow_date(
        "finance_bill", bill.id, "finance.pricing.execute",
    ) or business_date(bill.created_at)
    previous_confirmation = latest_workflow_date(
        "finance_bill", bill.id, "finance.payment.confirm",
    )
    payment_previous = _latest_date(priced_at, previous_confirmation)
    payment_previous_label = "上次收款确认" if previous_confirmation else "计价"
    bill.payment_date = _validated_date(
        actor,
        payload.get("paymentDate"),
        payment_previous,
        "收款日期",
        payment_previous_label,
    )
    bill.status = "待收款确认"
    _touch(bill, actor, command_key)


def confirm_payment(bill, payload, actor, command_key=""):
    _require_status(bill, "待收款确认")
    if payload.get("approved") is False:
        bill.pending_payment = Decimal("0.00")
        bill.note = (payload.get("reason") or "收款确认退回").strip()
        bill.status = "待收款"
        _touch(bill, actor, command_key)
        return
    pending = bill.pending_payment or 0
    if pending <= 0:
        raise FinanceRuleError("没有待确认的收款金额")
    bill.amount_received = (bill.amount_received or 0) + pending
    bill.pending_payment = Decimal("0.00")
    bill.status = "待开票" if bill.amount_received >= bill.amount_due else "待收款"
    _touch(bill, actor, command_key)


def issue_invoice(bill, payload, actor, command_key=""):
    _require_status(bill, "待开票")
    invoice_no = (payload.get("invoiceNo") or "").strip()
    invoice_type = (payload.get("invoiceType") or "").strip()
    amount = money(payload.get("amount") or bill.amount_received, "开票金额")
    if not invoice_no or not invoice_type:
        raise FinanceRuleError("发票号码和发票类型为必填项")
    if amount <= 0 or amount > (bill.amount_received or 0):
        raise FinanceRuleError("开票金额必须大于 0 且不能超过已确认收款")
    bill.invoice_no = invoice_no
    bill.invoice_type = invoice_type
    confirmed_at = latest_workflow_date(
        "finance_bill", bill.id, "finance.payment.confirm",
    ) or parse_date(bill.payment_date)
    bill.invoice_date = _validated_date(
        actor, payload.get("invoiceDate"), confirmed_at, "开票日期", "收款确认",
    )
    bill.amount_invoiced = amount
    bill.status = "待结算"
    _touch(bill, actor, command_key)


def settle_bill(bill, payload, actor, command_key=""):
    _require_status(bill, "待结算")
    if (bill.amount_received or 0) < (bill.amount_due or 0):
        raise FinanceRuleError("尚未全额收款，不能结算")
    if not bill.invoice_no:
        raise FinanceRuleError("尚未开票，不能结算")
    bill.settlement_no = (payload.get("settlementNo") or f"JS-{bill.bill_no}").strip()
    invoiced_at = latest_workflow_date(
        "finance_bill", bill.id, "finance.invoice.issue",
    ) or parse_date(bill.invoice_date)
    bill.settlement_date = _validated_date(
        actor, payload.get("settlementDate"), invoiced_at, "结算日期", "开票",
    )
    bill.note = (payload.get("note") or bill.note or "").strip()
    bill.status = "已结算"
    _touch(bill, actor, command_key)


def refund_bill(bill, payload, actor, command_key=""):
    _require_status(bill, "已结算", "部分退款")
    amount = money(payload.get("amount"), "退款金额")
    refundable = (bill.amount_received or 0) - (bill.amount_refunded or 0)
    reason = (payload.get("reason") or "").strip()
    if amount <= 0 or amount > refundable:
        raise FinanceRuleError(f"退款金额应大于 0 且不超过可退金额 {refundable:.2f}")
    if not reason:
        raise FinanceRuleError("退款原因不能为空")
    previous_refund = _latest_date(
        latest_workflow_date("finance_bill", bill.id, "finance.refund.execute"),
        parse_date(bill.refund_date),
    )
    settlement = _latest_date(
        latest_workflow_date("finance_bill", bill.id, "finance.settlement.execute"),
        parse_date(bill.settlement_date),
    )
    refund_previous = _latest_date(previous_refund, settlement)
    refund_previous_label = "上次退款" if previous_refund else "结算"
    bill.amount_refunded = (bill.amount_refunded or 0) + amount
    bill.refund_date = _validated_date(
        actor,
        payload.get("refundDate"),
        refund_previous,
        "退款日期",
        refund_previous_label,
    )
    bill.note = reason
    bill.status = "已退款" if bill.amount_refunded >= bill.amount_received else "部分退款"
    _touch(bill, actor, command_key)
