"""Canonical sample-logistics Commands.

Batch-3 Q10 (2026-11-07): there is no mobile client, so the former mobile
channel (OCR-gated inbound, one-tap pickup) was removed.  Only ``desktop`` is
accepted; historical ``mobileSampleFlow`` / ``sample.mobile.*`` records stay
readable elsewhere but are never written again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...extensions import db
from ...models import Report
from ...platform.audit import add_operation_audit, latest_operation_audit
from ...platform.identity import is_platform_administrator, project_step_error
from ...platform.workflow import (
    sample_dispose_blocker,
    sample_return_stock_blocker,
    sample_inbound_undo_blocker,
)
from ...workflow_dates import (
    business_today,
    latest_workflow_date,
    parse_date,
    validate_after_previous,
)
from ..report_lifecycle import (
    apply_sample_inbound_transition,
    apply_sample_inbound_undo_transition,
    apply_sample_dispose_transition,
    apply_sample_outbound_return_transition,
    apply_sample_pickup_transition,
    apply_sample_return_stock_transition,
    apply_sample_void_transition,
    scoped_report_query,
)

InboundChannel = Literal["desktop"]
PickupChannel = Literal["desktop"]


@dataclass(frozen=True)
class SampleInboundResult:
    """Transport-neutral result of the sample inbound Command."""

    code: int
    message: str
    report: Report | None = None
    skipped_nodes: tuple[str, ...] = ()
    http_status: int = 200

    def response_payload(self, *, data=None) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "data": data}


@dataclass(frozen=True)
class SamplePickupResult:
    """Transport-neutral result of the shared pickup Command."""

    code: int
    message: str
    report: Report | None = None
    skipped_nodes: tuple[str, ...] = ()
    http_status: int = 200

    def response_payload(self, *, data=None) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "data": data}


@dataclass(frozen=True)
class SampleFlowResult:
    code: int
    message: str
    report: Report | None = None
    http_status: int = 200

    def response_payload(self, *, data=None) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "data": data}


def _data_entry_started(report: Report) -> bool:
    from ...data_entry_state import report_data_entry_started
    return report_data_entry_started(report)


def execute_sample_inbound(
    user,
    report_no: str,
    *,
    channel: InboundChannel,
    inbound_date: str | None = None,
) -> SampleInboundResult:
    """Rollback every partial mutation if a Command raises unexpectedly."""

    try:
        return _execute_sample_inbound(
            user,
            report_no,
            channel=channel,
            inbound_date=inbound_date,
        )
    except Exception:
        db.session.rollback()
        raise


def _execute_sample_inbound(
    user,
    report_no: str,
    *,
    channel: InboundChannel,
    inbound_date: str | None = None,
) -> SampleInboundResult:
    """Receive one sample into storage; the Command owns the transaction."""

    if channel != "desktop":
        return SampleInboundResult(1, "样品入库来源无效")
    if "sample.inbound.confirm" not in user.action_codes():
        return SampleInboundResult(403, "无样品入库权限")

    report = (
        scoped_report_query(Report.query, user)
        .filter(Report.report_no == str(report_no or ""))
        .with_for_update()
        .first()
    )
    if report is None:
        return SampleInboundResult(1, "样品不存在或不在数据范围内")
    if bool(report.voided) or (report.sample_reg_state or "") == "已作废":
        return SampleInboundResult(1, "样品单已作废，不能办理入库")

    grant_error = project_step_error(user, report, "sample_inbound", "样品入库")
    if grant_error:
        return SampleInboundResult(403, grant_error)

    sample_status = report.sample_status or "待入库"
    if report.status != "待样品入库":
        return SampleInboundResult(
            1,
            f"报告当前为「{report.status}」，仅合同评审通过后的待入库样品可办理入库",
        )
    if sample_status != "待入库":
        return SampleInboundResult(1, f"样品当前为「{sample_status}」，无需入库")

    before = report.to_row()
    if inbound_date is not None:
        parsed = parse_date(inbound_date)
        if parsed is None or inbound_date != parsed.isoformat():
            return SampleInboundResult(1, "入库日期必须为有效日期（YYYY-MM-DD）")
    operation_time = inbound_date if inbound_date is not None else business_today().isoformat()

    from ...report_date_policy import report_date_error
    date_error = report_date_error(report, "inbound", operation_time)
    if date_error:
        return SampleInboundResult(1, date_error)

    skipped_nodes = apply_sample_inbound_transition(report, operation_time=operation_time)
    add_operation_audit(
        "sample.inbound.confirm",
        "report",
        report.report_no,
        category="workflow",
        before=before,
        after=report.to_row(),
        message=None,
        actor=user,
    )
    db.session.commit()

    message = f"{report.report_no} 样品已入库，待出库领取"
    if skipped_nodes:
        message += f"；按项目流程已跳过：{'、'.join(skipped_nodes)}"

    return SampleInboundResult(0, message, report, skipped_nodes)


def execute_sample_pickup(
    user,
    report_no: str,
    *,
    channel: PickupChannel,
    manager_id: str = "",
    manager_name: str = "",
    out_time: str = "",
    receiver_name: str = "",
    pickup_time: str = "",
) -> SamplePickupResult:
    """Sign one sample out (desktop channel only)."""

    try:
        return _execute_sample_pickup(
            user,
            report_no,
            channel=channel,
            manager_id=manager_id,
            manager_name=manager_name,
            out_time=out_time,
            receiver_name=receiver_name,
            pickup_time=pickup_time,
        )
    except Exception:
        db.session.rollback()
        raise


def _execute_sample_pickup(
    user,
    report_no: str,
    *,
    channel: PickupChannel,
    manager_id: str,
    manager_name: str,
    out_time: str,
    receiver_name: str,
    pickup_time: str,
) -> SamplePickupResult:
    if channel != "desktop":
        return SamplePickupResult(1, "样品出库来源无效")
    if "sample.out_warehouse.sign" not in user.action_codes():
        return SamplePickupResult(403, "无样品出库领取权限")

    report = (
        scoped_report_query(Report.query, user)
        .filter(Report.report_no == str(report_no or ""))
        .with_for_update()
        .first()
    )
    if report is None:
        return SamplePickupResult(1, "样品不存在或不在数据范围内")
    if bool(report.voided) or (report.sample_reg_state or "") == "已作废":
        return SamplePickupResult(1, "样品单已作废，不能办理出库领取")

    grant_error = project_step_error(user, report, "sample_outbound", "样品出库并领取")
    if grant_error:
        return SamplePickupResult(403, grant_error)
    if report.status != "待样品领取" or (report.sample_status or "待入库") != "已入库":
        return SamplePickupResult(1, f"报告当前为「{report.status}」，不在样品出库领取节点")

    manager_id = str(manager_id or "").strip()
    manager_name = str(manager_name or "").strip()
    out_time = str(out_time or "").strip()
    receiver_name = str(receiver_name or "").strip()
    pickup_time = str(pickup_time or "").strip()
    original_dates = (out_time, pickup_time)
    pickup_time = pickup_time or out_time
    out_time = pickup_time
    missing = [
        label
        for label, value in (
            ("样品管理员", manager_name),
            ("出库领取日期", pickup_time),
            ("领样人姓名", receiver_name),
        )
        if not value
    ]
    if missing:
        return SamplePickupResult(1, f"出库领取单未填写：{'、'.join(missing)}")

    workflow_dates = dict((report.detail or {}).get("workflowDates") or {})
    inbound_date = parse_date(workflow_dates.get("sampleInboundAt"))
    if inbound_date is None:
        return SamplePickupResult(1, "缺少原入库业务日期，请先核对历史记录恢复日期；不能用操作日期代替或重复入库")
    date_error = validate_after_previous(
        user, pickup_time, inbound_date, "出库领取日期", "样品入库日期"
    )
    if date_error:
        return SamplePickupResult(1, date_error)
    workflow_pickup_at = parse_date(pickup_time).isoformat()
    audit_action = "sample.out_warehouse.sign"
    audit_message = (
        f"出库领取日期自动对齐：原出库日期={original_dates[0] or '空'}，"
        f"原领取日期={original_dates[1] or '空'}；统一为 {pickup_time}（领取日期优先）"
        if original_dates != (pickup_time, pickup_time) else None
    )

    # One business date, mirrored into both legacy fields.
    from ...report_date_policy import report_date_error
    date_error = report_date_error(report, "pickup", pickup_time)
    if date_error:
        return SamplePickupResult(1, date_error)
    before = report.to_row()
    skipped_nodes = apply_sample_pickup_transition(
        report,
        manager_id=manager_id,
        manager_name=manager_name,
        out_time=out_time,
        receiver_name=receiver_name,
        pickup_time=pickup_time,
        workflow_pickup_at=workflow_pickup_at,
    )
    add_operation_audit(
        audit_action,
        "report",
        report.report_no,
        category="workflow",
        before=before,
        after=report.to_row(),
        message=audit_message,
        actor=user,
    )
    db.session.commit()

    message = f"{report.report_no} 样品已由 {receiver_name} 签字领取，进入检测数据录入"
    if skipped_nodes:
        message += f"；按项目流程已跳过：{'、'.join(skipped_nodes)}"
    return SamplePickupResult(0, message, report, skipped_nodes)


def _locked_report(user, report_no: str) -> Report | None:
    return (
        scoped_report_query(Report.query, user)
        .filter(Report.report_no == str(report_no or ""))
        .with_for_update()
        .first()
    )


def _invalid_report(report: Report | None, action_label: str) -> SampleFlowResult | None:
    if report is None:
        return SampleFlowResult(1, "样品不存在或不在数据范围内")
    if bool(report.voided) or (report.sample_reg_state or "") == "已作废":
        return SampleFlowResult(1, f"样品单已作废，不能{action_label}")
    return None


def execute_sample_outbound_return(user, report_no: str, *, note: str) -> SampleFlowResult:
    """Return a pending/picked-not-started sample to entrust change."""
    try:
        if "sample.out_warehouse.return" not in user.action_codes():
            return SampleFlowResult(403, "无样品出库领取权限")
        report = _locked_report(user, report_no)
        invalid = _invalid_report(report, "从样品流转退回")
        if invalid:
            return invalid
        grant_error = project_step_error(user, report, "sample_outbound", "样品出库并领取")
        if grant_error:
            return SampleFlowResult(403, grant_error)
        pending = report.status == "待样品领取" and (report.sample_status or "待入库") == "已入库"
        picked = report.status == "检测录入中" and (report.sample_status or "") == "已领取"
        if not pending and not picked:
            return SampleFlowResult(1, f"报告当前为「{report.status}」，不允许从样品流转退回委托更改")
        if picked:
            blocker = sample_return_stock_blocker(report, _data_entry_started(report))
            if blocker:
                return SampleFlowResult(1, blocker)
        note = str(note or "").strip()
        if not note:
            return SampleFlowResult(1, "退回需填写原因（将转入委托更改）")
        before = report.to_row()
        apply_sample_outbound_return_transition(
            report,
            note=note,
            actor_account=user.account,
            actor_name=(user.name or user.account).strip(),
            occurred_on=business_today().isoformat(),
        )
        add_operation_audit(
            "sample.out_warehouse.return", "report", report.report_no,
            category="workflow", before=before, after=report.to_row(), message=note, actor=user,
        )
        db.session.commit()
        return SampleFlowResult(0, f"{report.report_no} 样品出库退回，转委托更改：{note}", report)
    except Exception:
        db.session.rollback()
        raise


def execute_sample_inbound_undo(user, report_no: str) -> SampleFlowResult:
    """Only the current pending-pickup receipt can be cancelled."""
    try:
        if "sample.inbound.confirm" not in user.action_codes():
            return SampleFlowResult(403, "无样品入库权限，不能撤销入库")
        report = _locked_report(user, report_no)
        invalid = _invalid_report(report, "撤销入库")
        if invalid:
            return invalid
        grant_error = project_step_error(user, report, "sample_inbound", "撤销入库")
        if grant_error:
            return SampleFlowResult(403, grant_error)
        blocker = sample_inbound_undo_blocker(report)
        if blocker:
            return SampleFlowResult(1, blocker)
        before = report.to_row()
        apply_sample_inbound_undo_transition(report)
        add_operation_audit(
            "sample.inbound.undo", "report", report.report_no,
            category="workflow", before=before, after=report.to_row(),
            message="撤销入库，恢复待入库", actor=user,
        )
        db.session.commit()
        return SampleFlowResult(0, "已撤销入库，样品恢复待入库", report)
    except Exception:
        db.session.rollback()
        raise


def execute_sample_return_stock(user, report_no: str) -> SampleFlowResult:
    """Undo a pickup before the first saved detection data."""
    try:
        if not is_platform_administrator(user) and "sample.return_stock" not in user.action_codes():
            return SampleFlowResult(403, "无样品回库权限")
        report = _locked_report(user, report_no)
        invalid = _invalid_report(report, "办理回库")
        if invalid:
            return invalid
        grant_error = project_step_error(user, report, "sample_outbound", "样品回库")
        if grant_error:
            return SampleFlowResult(403, grant_error)
        blocker = sample_return_stock_blocker(report, _data_entry_started(report))
        if blocker:
            return SampleFlowResult(1, blocker)
        before = report.to_row()
        apply_sample_return_stock_transition(report, occurred_at=business_today().isoformat())
        add_operation_audit(
            "sample.return_stock", "report", report.report_no,
            category="workflow", before=before, after=report.to_row(), actor=user,
        )
        db.session.commit()
        return SampleFlowResult(0, f"{report.report_no} 样品已回库，待重新出库领取", report)
    except Exception:
        db.session.rollback()
        raise


def execute_sample_dispose(user, report_no: str) -> SampleFlowResult:
    """Dispose a completed sample with the same owner/audit boundary."""
    try:
        if "sample.dispose" not in user.action_codes():
            return SampleFlowResult(403, "无样品处置权限")
        report = _locked_report(user, report_no)
        invalid = _invalid_report(report, "处置样品")
        if invalid:
            return invalid
        grant_error = project_step_error(user, report, "sample_outbound", "样品处置")
        if grant_error:
            return SampleFlowResult(403, grant_error)
        blocker = sample_dispose_blocker(report)
        if blocker:
            return SampleFlowResult(1, blocker)
        before = report.to_row()
        apply_sample_dispose_transition(report)
        add_operation_audit(
            "sample.dispose", "report", report.report_no, category="workflow",
            before=before, after=report.to_row(), actor=user,
        )
        db.session.commit()
        return SampleFlowResult(0, f"{report.report_no} 样品已处置", report)
    except Exception:
        db.session.rollback()
        raise


def execute_sample_void(user, report_no: str) -> SampleFlowResult:
    try:
        if "sample.register.void" not in user.action_codes():
            return SampleFlowResult(403, "无作废样品单权限")
        report = _locked_report(user, report_no)
        if report is None:
            return SampleFlowResult(1, "样品不存在或不在数据范围内")
        if report.voided:
            return SampleFlowResult(1, "样品单已作废")
        if report.status not in ("待合同评审", "委托更改中"):
            return SampleFlowResult(1, f"样品已流转至「{report.status}」，不能作废")
        before = report.to_row()
        apply_sample_void_transition(report)
        add_operation_audit(
            "sample.register.void", "report", report.report_no, category="workflow",
            before=before, after=report.to_row(), actor=user,
        )
        db.session.commit()
        return SampleFlowResult(0, f"样品单 {report.sample_no or report.report_no} 已作废", report)
    except Exception:
        db.session.rollback()
        raise


__all__ = [
    "InboundChannel",
    "PickupChannel",
    "SampleInboundResult",
    "SamplePickupResult",
    "SampleFlowResult",
    "execute_sample_dispose",
    "execute_sample_inbound",
    "execute_sample_inbound_undo",
    "execute_sample_outbound_return",
    "execute_sample_pickup",
    "execute_sample_return_stock",
    "execute_sample_void",
]
