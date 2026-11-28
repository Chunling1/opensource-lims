"""Canonical report-lifecycle Commands.

HTTP, mobile and future adapters translate transport data into these Commands;
they do not assign report state themselves.  The first extraction deliberately
preserves the existing public API, status names and transaction boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from flask import current_app

from ...checks import compute_report_checks
from ...compliance import validate_and_record_acknowledgement
from ...extensions import db
from ...models import Report, ReportAttachment
from ...platform.file_vault import persist_bytes
from ...platform.audit import (
    add_operation_audit,
    completion_owned_by,
)
from ...platform.identity import (
    has_function_permission,
    is_platform_administrator,
    project_step_error,
)
from ...platform.workflow import (
    REPORT_NODE_EXPECTED,
    REPORT_NODE_FLOW,
    UNDO_FLOW,
    review_undo_blocker,
)
from ...project_workflow import advance_skipped_project_steps
from ...multi_stage_approval import advance_stage_or_complete, reset_multi_stage_on_return
from ...report_documents import document_preflight, select_profile
from ...workflow_dates import business_today
from .queries import scoped_report_query

RETURN_SOURCE = {
    "report.contract_review": "合同评审退回",
    "report.report_check": "校核退回",
    "report.review": "审核退回",
    "report.approval": "批准退回",
    "report.print": "打印退回",
}
RETURN_MODE_LABELS = {
    "entrust_only": "退回委托更改",
    "data_only": "退回检测数据录入更改",
    "entrust_and_data": "委托和检测数据都退回",
}


# A workflow action needs all three independent boundaries: its action grant,
# the page/function that owns the node, and the current project-step grant.
# Legacy action rows alone must never make an old same-department account a
# valid handler for a report it can merely see.
ACTION_ACCESS_POLICIES = {
    "testing.data_entry": (
        ("testing.data_entry.view",),
        "data_entry",
        "检测数据录入",
    ),
    "report.contract_review": (
        ("entrust.contract_review.view", "report.contract_review.view"),
        "entrust_review",
        "合同评审",
    ),
    "report.report_check": (
        ("testing.data_entry.view",),
        "data_entry",
        "检测数据录入",
    ),
    "report.review": (("report.review.view",), "report_review", "报告审核"),
    "report.approval": (
        ("report.approval.view",),
        "report_approval",
        "报告批准",
    ),
    "report.print": (("report.print.view",), "report_print", "报告签发"),
    "report.archive": (("report.archive.view",), "report_archive", "报告归档"),
}

UNDO_COMPLETION_POLICIES = {
    "report.contract_review.undo": ("report.contract_review.pass", "合同评审"),
    "report.report_check.undo": ("report.data_entry.complete", "检测数据录入"),
    "report.review.undo": ("report.review.pass", "报告审核"),
    "report.approval.undo": ("report.approval.pass", "报告批准"),
    "report.print.undo": ("report.print.pass", "报告签发"),
    "report.archive.undo": ("report.archive.pass", "报告归档"),
}


@dataclass(frozen=True)
class ReportCommandResult:
    code: int
    message: str
    data: Any = None
    http_status: int = 200

    def response_payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "data": self.data}


def apply_sample_inbound_transition(
    report: Report,
    *,
    operation_time: str,
) -> tuple[str, ...]:
    """Apply the legacy Report-backed sample-inbound state transition.

    ``reports`` is owned by ``report_lifecycle`` while sample state is still
    stored on that legacy aggregate.  Sample application Commands call this
    public owner boundary instead of assigning Report fields directly.  The
    caller keeps the surrounding audit and transaction boundary.
    """

    detail = dict(report.detail or {})
    workflow_dates = dict(detail.get("workflowDates") or {})
    workflow_dates["sampleInboundAt"] = operation_time
    workflow_dates["sampleAvailableAt"] = operation_time
    detail["workflowDates"] = workflow_dates

    report.detail = detail
    report.sample_status = "已入库"
    report.status = "待样品领取"
    return tuple(advance_skipped_project_steps(report))


def apply_sample_inbound_undo_transition(report: Report) -> None:
    """Cancel the current receipt; its former dates remain in operation audits."""
    detail = dict(report.detail or {})
    dates = dict(detail.get("workflowDates") or {})
    dates.pop("sampleInboundAt", None)
    dates.pop("sampleAvailableAt", None)
    detail["workflowDates"] = dates
    # A completed outbound-return plan must not bypass receipt on later review.
    if resumes_sample_outbound(detail):
        detail["returnPlan"] = {**detail["returnPlan"],
            "sourceAction": "sample.inbound.undo", "afterContractReview": "sample_inbound",
            "preservedSampleStatus": "待入库", "targetLabel": "委托更改 → 合同评审 → 样品入库"}
    report.detail = detail
    report.status = "待样品入库"
    report.sample_status = "待入库"


def apply_sample_pickup_transition(
    report: Report,
    *,
    manager_id: str,
    manager_name: str,
    out_time: str,
    receiver_name: str,
    pickup_time: str,
    workflow_pickup_at: str,
) -> tuple[str, ...]:
    """Apply the Report-owned part of a sample pickup transition.

    Sample logistics validates the business request, while this owner boundary
    is the only place that mutates the legacy Report aggregate.
    """

    detail = dict(report.detail or {})
    workflow_dates = dict(detail.get("workflowDates") or {})
    workflow_dates["samplePickupAt"] = workflow_pickup_at
    detail["workflowDates"] = workflow_dates
    detail["dataEntryStarted"] = False

    report.detail = detail
    pickup = {
        "managerId": manager_id,
        "managerName": manager_name,
        "outTime": out_time,
        "receiverName": receiver_name,
        "pickupTime": pickup_time,
        "signed": True,
    }
    report.sample_pickup = pickup
    report.sample_status = "已领取"
    report.status = "检测录入中"
    return tuple(advance_skipped_project_steps(report))


def resumes_sample_outbound(detail: dict[str, Any]) -> bool:
    """Recognize the saved destination, including pre-fix outbound returns."""
    plan = detail.get("returnPlan") or {}
    destination = plan.get("afterContractReview")
    return destination == "sample_outbound" or (
        plan.get("sourceAction") == "sample.out_warehouse.return"
        and destination == "sample_inbound"
    )


def apply_sample_outbound_return_transition(
    report: Report, *, note: str, actor_account: str, actor_name: str, occurred_on: str
) -> None:
    """Return an outbound sample to entrust change through the Report owner."""

    detail = dict(report.detail or {})
    detail["changeNote"] = note
    detail["changeSource"] = {
        "status": report.status,
        "sampleStatus": report.sample_status or "",
    }
    detail["returnPlan"] = {
        "mode": "entrust_only",
        "sourceAction": "sample.out_warehouse.return",
        "sourceStatus": report.status,
        "afterContractReview": "sample_outbound",
        "preservedSampleStatus": "已入库",
        "targetLabel": "委托更改 → 合同评审 → 样品出库领取中",
        "createdAt": occurred_on,
        "createdBy": actor_account,
    }
    detail["returnInfo"] = {
        "source": "样品流转退回",
        "by": actor_name or actor_account,
        "date": occurred_on,
        "note": note,
        "mode": "entrust_only",
        "modeLabel": "仅修改委托/样品信息",
        "target": "委托更改 → 合同评审 → 样品出库领取中",
    }
    report.detail = detail
    report.sample_pickup = {**(report.sample_pickup or {}), "signed": False, "returnNote": note}
    report.sample_status = "出库退回"
    report.status = "委托更改中"


def apply_sample_return_stock_transition(report: Report, *, occurred_at: str) -> None:
    """Undo a pickup before data entry and make the sample available again."""

    detail = dict(report.detail or {})
    workflow_dates = dict(detail.get("workflowDates") or {})
    # Undo is an audit event, not a new physical inbound/return business date.
    detail["workflowDates"] = workflow_dates
    detail["dataEntryStarted"] = False
    report.detail = detail
    report.sample_status = "已入库"
    report.sample_pickup = {**(report.sample_pickup or {}), "signed": False}
    report.status = "待样品领取"


def apply_sample_dispose_transition(report: Report) -> None:
    """Mark a completed sample as disposed through its owning aggregate."""

    report.sample_status = "已处置"


def apply_sample_void_transition(report: Report) -> None:
    report.voided = True
    report.sample_reg_state = "已作废"


def persist_report_attachment(
    report: Report,
    raw: bytes,
    *,
    category: str,
    name: str,
    content_type: str,
    kind: str,
    source: str,
    status: str,
    uploaded_by: str,
    created_by: str,
    max_bytes: int | None = None,
) -> ReportAttachment:
    """Create a Report-owned stored attachment without committing the caller transaction."""

    stored_file = persist_bytes(
        raw,
        category=category,
        original_name=name,
        content_type=content_type,
        created_by=created_by,
        max_bytes=max_bytes,
    )
    attachment = ReportAttachment(
        report_no=report.report_no,
        name=name,
        content_type=content_type,
        kind=kind,
        source=source,
        status=status,
        stored_file=stored_file,
        data=None,
        uploaded_by=uploaded_by,
    )
    db.session.add(attachment)
    db.session.flush()
    return attachment


def apply_eln_transfer_metadata(report: Report, transfer: Mapping[str, Any]) -> None:
    """Append one idempotent ELN transfer projection to the Report aggregate."""

    detail = dict(report.detail or {})
    integration = dict(detail.get("elnIntegration") or {})
    transfers = list(integration.get("transfers") or [])
    transfers.append(dict(transfer))
    integration["latest"] = dict(transfer)
    integration["transfers"] = transfers[-100:]
    detail["elnIntegration"] = integration
    report.detail = detail


def apply_testing_data_projection(
    report: Report,
    *,
    detail: Mapping[str, Any],
    owner: str = "",
) -> None:
    """Persist the Report-backed testing projection through its table owner.

    ``testing_records`` owns the detection-data use case, while the legacy
    physical columns still live on ``reports``.  Keeping this deliberately
    small owner primitive prevents a testing adapter from assigning Report
    fields directly without changing the current database shape.
    """

    report.detail = dict(detail)
    if str(owner or "").strip():
        report.owner = str(owner).strip()


def apply_testing_completion_transition(
    report: Report,
    *,
    out_of_scope: bool,
    out_of_scope_note: str,
) -> tuple[str, ...]:
    """Apply the existing data-entry completion transition as Report owner."""

    report.out_of_scope = bool(out_of_scope)
    report.out_of_scope_note = str(out_of_scope_note or "")
    report.status = "待审核"
    return tuple(advance_skipped_project_steps(report))


def return_plan(action_code: str, return_mode: str = "") -> dict[str, Any]:
    node = str(action_code or "").rsplit(".", 1)[0]
    mode = str(return_mode or "").strip()
    if node == "report.contract_review":
        return {"mode": "entrust_only", "targetLabel": "委托更改 → 合同评审 → 样品入库"}
    if node == "testing.data_entry":
        return {
            "mode": "entrust_only",
            "afterContractReview": "data_entry",
            "targetLabel": "委托更改 → 合同评审 → 检测数据录入",
        }
    if node == "testing.data_check":
        return {
            "mode": "data_only",
            "afterDataChange": "data_check",
            "targetLabel": "检测数据更改 → 检测数据校核",
        }
    if node in {"report.review", "report.approval"}:
        mode = mode if mode in RETURN_MODE_LABELS else "data_only"
        if mode == "entrust_only":
            return {
                "mode": mode,
                "afterContractReview": "review",
                "skipSampleFlow": True,
                "targetLabel": "委托更改 → 合同评审 → 跳过样品出入库 → 报告审核",
            }
        if mode == "entrust_and_data":
            return {
                "mode": mode,
                "afterContractReview": "data_change",
                "afterDataChange": "review",
                "skipSampleFlow": True,
                "targetLabel": "委托更改 → 合同评审 → 跳过样品出入库 → 检测数据更改 → 报告审核",
            }
        return {
            "mode": mode,
            "afterDataChange": "review",
            "targetLabel": "检测数据更改 → 报告审核",
        }
    if node == "report.report_check":
        return {
            "mode": "data_only",
            "afterDataChange": "report_check",
            "targetLabel": "检测数据更改 → 报告校核",
        }
    return {
        "mode": "data_only",
        "afterDataChange": "review",
        "targetLabel": "检测数据更改 → 报告审核",
    }


def apply_return_plan(report, user, action_code: str, note: str, return_mode: str = "") -> dict[str, Any]:
    """Apply the existing return workflow as an owner-module mutation."""

    plan = return_plan(action_code, return_mode)
    plan.update(
        {
            "sourceAction": action_code,
            "sourceStatus": report.status,
            "preservedSampleStatus": report.sample_status or "已领取",
            "createdAt": business_today().isoformat(),
            "createdBy": user.account,
        }
    )
    detail = dict(report.detail or {})
    if action_code == "report.contract_review.return" and resumes_sample_outbound(detail):
        # Rejection during re-review must not erase the original pickup destination.
        plan.update(
            afterContractReview="sample_outbound",
            preservedSampleStatus="已入库",
            targetLabel="委托更改 → 合同评审 → 样品出库领取中",
        )
    elif action_code == "report.contract_review.return":
        previous_plan = detail.get("returnPlan") or {}
        if previous_plan.get("afterContractReview") in {"data_entry", "data_change", "review"}:
            # A rejection during re-review changes the latest reason/actor, not
            # the destination chosen when the report first left its work node.
            # Keep the original sample state too: the current state can be the
            # temporary review label from reports created before this fix.
            for key in (
                "mode", "afterContractReview", "afterDataChange", "skipSampleFlow",
                "preservedSampleStatus", "targetLabel",
            ):
                if key in previous_plan:
                    plan[key] = previous_plan[key]
    previous_plan = detail.get("returnPlan") or {}
    if action_code == "report.contract_review.return" and previous_plan:
        plan["originalSourceAction"] = previous_plan.get("originalSourceAction") or previous_plan.get("sourceAction")
        plan["originalSourceStatus"] = previous_plan.get("originalSourceStatus") or previous_plan.get("sourceStatus")
    else:
        plan["originalSourceAction"] = action_code
        plan["originalSourceStatus"] = report.status
    detail["returnPlan"] = plan
    detail["returnInfo"] = {
        "source": RETURN_SOURCE.get(
            str(action_code or "").rsplit(".", 1)[0],
            "检测录入退回" if str(action_code or "").startswith("testing.data_entry") else "数据校核退回",
        ),
        "by": (user.name or user.account).strip(),
        "date": business_today().isoformat(),
        "note": str(note or "").strip(),
        "mode": plan["mode"],
        "modeLabel": RETURN_MODE_LABELS.get(plan["mode"], plan["mode"]),
        "target": plan["targetLabel"],
    }
    signatures = dict(detail.get("signatures") or {})
    signatures.pop("审核", None)
    signatures.pop("批准", None)
    detail["signatures"] = signatures
    report.detail = detail
    report.status = "委托更改中" if plan["mode"] in {"entrust_only", "entrust_and_data"} else "检测更改中"
    # Clear stale controlled/approved pointers on return so pre-return PDFs are never served as current.
    report.current_document_version_id = None
    report.approved_document_version_id = None
    return plan


def document_version_blocker(report, *, reviewed=False) -> str:
    from ... import docparser_field_only
    if docparser_field_only.applies_to(report):
        from ...report_version_consistency import require_current_document, require_reviewed_document
        try:
            (require_reviewed_document if reviewed else require_current_document)(report)
        except ValueError as exc:
            return str(exc)
        return ""
    profile = select_profile(report)
    if not profile or not profile.requires_version:
        return ""
    check = document_preflight(report, "official")
    if check["missing"]:
        return "报告缺少必填内容：" + "、".join(check["missing"])
    if not report.current_document_version_id:
        return "请先生成正式报告版本，再提交审核"
    if check["currentVersionStale"]:
        return "业务数据或报告正文已变化，请重新生成正式报告版本"
    return ""


def _action_access_error(user, report, action_code: str) -> str:
    node = str(action_code or "").rsplit(".", 1)[0]
    policy = ACTION_ACCESS_POLICIES.get(node)
    if policy is None:
        return ""
    permissions, step_code, label = policy
    if not has_function_permission(user, *permissions):
        return f"无{label}功能权限"
    return project_step_error(user, report, step_code, label)


def _undo_owner_error(user, report, action_code: str) -> str:
    policy = UNDO_COMPLETION_POLICIES.get(str(action_code or ""))
    if policy is None or is_platform_administrator(user):
        return ""
    completion_action, label = policy
    owned, completion = completion_owned_by(
        user, "report", report.report_no, completion_action
    )
    if owned:
        return ""
    completer = (
        (completion.user_name or completion.account).strip()
        if completion is not None
        else ""
    )
    message = f"仅完成该{label}的用户或管理员可以撤回"
    return message + (f"（完成人：{completer}）" if completer else "")


def _data_entry_return_owner_error(user, report) -> str:
    """Bind an active data-entry return to recorded task handlers.

    A task may be bound by its saved entry staff/primary testers, a saved-data
    audit, or (before the first save) the person who signed the sample pickup.
    Historical rows with none of those facts fail closed for non-admin users.
    """

    if is_platform_administrator(user):
        return ""
    account = str(getattr(user, "account", "") or "").strip().lower()
    detail = dict(report.detail or {})
    check_input = dict(detail.get("checkInput") or {})
    people = dict(check_input.get("people") or {})
    recorded_accounts = {
        str(item.get("account") or item.get("code") or "").strip().lower()
        for item in (
            check_input.get("entryStaff") or {},
            people.get("primaryTester1") or {},
            people.get("primaryTester2") or {},
        )
        if isinstance(item, Mapping)
    }
    recorded_accounts.discard("")
    if account and account in recorded_accounts:
        return ""

    latest_handler = None
    for completion_action in (
        "report.data_entry.save",
        "sample.out_warehouse.sign",
        "sample.mobile.pickup.confirm",
    ):
        owned, completion = completion_owned_by(
            user, "report", report.report_no, completion_action
        )
        if owned:
            return ""
        if completion is not None and (
            latest_handler is None or completion.id > latest_handler.id
        ):
            latest_handler = completion

    handler = (
        (latest_handler.user_name or latest_handler.account).strip()
        if latest_handler is not None
        else ""
    )
    message = "仅当前检测任务已记录的主检、录入人或样品领取人可以退回"
    return message + (f"（当前处理人：{handler}）" if handler else "")


def execute_report_action(
    user,
    report_no: str,
    action_code: str | None,
    body: Mapping[str, Any] | None = None,
) -> ReportCommandResult:
    """Rollback every partial mutation if a Command raises unexpectedly."""

    from ...functions.esign_service import EsignServiceError
    try:
        return _execute_report_action(user, report_no, action_code, body)
    except EsignServiceError as exc:
        db.session.rollback()
        return ReportCommandResult(1, str(exc))
    except Exception:
        db.session.rollback()
        raise


def _execute_report_action(
    user,
    report_no: str,
    action_code: str | None,
    body: Mapping[str, Any] | None = None,
) -> ReportCommandResult:
    """Execute one report lifecycle action in a single DB transaction."""

    body = body or {}
    if str(action_code or "").startswith("report.release."):
        return ReportCommandResult(1, "旧版发放接口已停用，请在报告归档后使用新的报告发放入口")
    if action_code not in user.action_codes():
        return ReportCommandResult(403, "无此操作权限")
    report = (
        scoped_report_query(Report.query, user)
        .filter(Report.report_no == report_no)
        .with_for_update()
        .first()
    )
    if report is None:
        return ReportCommandResult(1, "报告不存在或不在数据范围内")
    if bool(report.voided) or (report.sample_reg_state or "") == "已作废":
        return ReportCommandResult(1, "样品单已作废，不能执行报告流程操作")

    node = str(action_code or "").rsplit(".", 1)[0]
    access_error = _action_access_error(user, report, str(action_code or ""))
    if access_error:
        return ReportCommandResult(403, access_error)
    if action_code == "testing.data_entry.return":
        owner_error = _data_entry_return_owner_error(user, report)
        if owner_error:
            return ReportCommandResult(403, owner_error)
    before_row = report.to_row()
    finance_before_status = report.status
    from ...workflow_hooks import capture as finance_capture, blocker as finance_blocker
    from ...functions import esign_stages
    staged_flow = esign_stages.current_flow(report)
    finance_error = finance_blocker(report, action_code) if not staged_flow else None
    if finance_error:
        return ReportCommandResult(1, finance_error)

    from ...report_delivery import delivery_released, RELEASE_ACTION, SEALED
    if action_code == RELEASE_ACTION:
        if not has_function_permission(user, 'report.release.view'):
            return ReportCommandResult(403, '无报告发放功能权限')
        if report.archive_state != '归档完成' or report.status not in {'待发放', '已发放'}:
            return ReportCommandResult(1, '请先完成盖章和归档，再发放报告')
        if delivery_released(report):
            return ReportCommandResult(1, '该报告已经发放完成，请勿重复操作')
        from ...report_delivery import sealed_current_flow, sealed_file_integrity_error
        version_id = report.approved_document_version_id or report.current_document_version_id
        flow = sealed_current_flow(report)
        esign_on = bool(current_app.config.get("ESIGN_ENABLED"))
        if flow:
            integrity_error = sealed_file_integrity_error(flow)
            if integrity_error:
                return ReportCommandResult(1, integrity_error)
        elif esign_on:
            return ReportCommandResult(1, '当前批准版本没有已完成盖章的正式文件，不能发放')
        elif not version_id:
            return ReportCommandResult(1, '当前报告没有已批准的正式文档版本，不能发放')
        from ...report_date_policy import report_date_error
        error = report_date_error(report, 'release', business_today())
        if error:
            return ReportCommandResult(1, error)
        detail = dict(report.detail or {})
        detail['reportDelivery'] = {
            'released': True,
            'versionId': version_id,
            'sealedFlowId': flow.id if flow else None,
            'offlineRelease': not bool(flow),
            'releasedBy': user.account,
            'releasedAt': str(business_today()),
        }
        report.detail = detail
        report.status = '已发放'
        add_operation_audit(action_code, 'report', report.report_no, category='workflow',
                            before=before_row, after=report.to_row(), actor=user)
        db.session.commit()
        msg = '报告发放完成，所属部门人员可下载正式盖章报告' if flow else '报告发放完成（线下签章模式），所属部门人员可查询下载正式报告'
        return ReportCommandResult(0, msg, report.to_row())
    if action_code == "report.archive.pass":
        sealed_pending = report.status == '待打印' and report.to_row()['dataStatus'] == SEALED
        if report.status not in {"待发放", "已发放"} and not sealed_pending:
            return ReportCommandResult(1, f"报告当前「{report.status}」，需先完成报告签发才能归档")
        if (report.archive_state or "") == "归档完成":
            return ReportCommandResult(1, "该报告已归档")
        if current_app.config.get("ESIGN_REQUIRED_FOR_ISSUANCE") or not report.stamped:
            from ...report_delivery import sealed_current_flow, sealed_file_integrity_error
            flow = sealed_current_flow(report)
            if not flow:
                return ReportCommandResult(1, '当前批准版本尚未完成盖章，不能归档')
            integrity_error = sealed_file_integrity_error(flow)
            if integrity_error:
                return ReportCommandResult(1, integrity_error)
        from ...report_date_policy import report_date_error
        date_error = report_date_error(report, "archive", business_today())
        if date_error:
            return ReportCommandResult(1, date_error)
        if sealed_pending:
            report.status = '待发放'
            report.stamped = True
        report.archive_state = "归档完成"
        add_operation_audit(action_code, "report", report.report_no, category="workflow", before=before_row, after=report.to_row(), actor=user)
        db.session.commit()
        return ReportCommandResult(0, f"{report.report_no} 已归档，等待授权人员发放", report.to_row())
    if action_code == "report.archive.undo":
        if delivery_released(report):
            return ReportCommandResult(1, '报告已发放，不能直接撤销归档，请走报告更改流程')
        if (report.archive_state or "") != "归档完成":
            return ReportCommandResult(1, "该报告未归档，无需撤销")
        owner_error = _undo_owner_error(user, report, str(action_code))
        if owner_error:
            return ReportCommandResult(403, owner_error)
        report.archive_state = ""
        add_operation_audit(action_code, "report", report.report_no, category="workflow", before=before_row, after=report.to_row(), actor=user)
        db.session.commit()
        return ReportCommandResult(0, f"{report.report_no} 已撤销归档", report.to_row())

    if str(action_code).endswith(".undo"):
        rule = UNDO_FLOW.get(str(action_code))
        if not rule:
            return ReportCommandResult(1, "该节点不支持撤销")
        need_status, back_status = rule
        legacy_issue = action_code == "report.print.undo" and report.status == "待发放"
        if report.status != need_status and not legacy_issue:
            return ReportCommandResult(1, f"报告当前「{report.status}」，无法撤销（需处于「{need_status}」）")
        owner_error = _undo_owner_error(user, report, str(action_code))
        if owner_error:
            return ReportCommandResult(403, owner_error)
        if action_code == "report.contract_review.undo":
            blocker = review_undo_blocker(report)
            if blocker:
                return ReportCommandResult(1, blocker)
        if action_code == "report.print.undo" and (report.archive_state or "") == "归档完成":
            return ReportCommandResult(1, "报告已归档，请先撤销归档")
        if staged_flow:
            esign_stages.cancel_round(staged_flow.id, user, str(body.get('note') or '撤销业务节点'),
                return_action=action_code)
            return ReportCommandResult(0, '整轮签署已撤销，请重新完成检测并逐节点签署', report.to_row())
        if action_code == "report.contract_review.undo":
            report.sample_status = "待合同评审"
        from ...workflow_hooks import complete_local_undo
        complete_local_undo(report, action_code, user)
        report.status = back_status
        if action_code in ("report.review.undo", "report.approval.undo"):
            detail = dict(report.detail or {})
            signatures = dict(detail.get("signatures") or {})
            roles = ("审核", "批准") if action_code == "report.review.undo" else ("批准",)
            for role in roles:
                signatures.pop(role, None)
            detail["signatures"] = signatures
            report.detail = detail
        if action_code in ("report.approval.undo", "report.print.undo"):
            report.stamped = False
            report.approved_document_version_id = None
        undo_row = report.to_row()
        add_operation_audit(action_code, "report", report.report_no, category="workflow", before=before_row, after=undo_row, actor=user)
        db.session.commit()
        return ReportCommandResult(
            0,
            f"{report.report_no} 已撤销，回退至「{back_status}」",
            {
                "reportNo": report.report_no,
                "status": report.status,
                "sampleStatus": report.sample_status or "待入库",
                "dataStatus": undo_row.get("dataStatus", ""),
                "outOfScope": bool(report.out_of_scope),
                "outOfScopeNote": report.out_of_scope_note or "",
                "stamped": bool(report.stamped),
            },
        )

    expected = REPORT_NODE_EXPECTED.get(node)
    if expected and report.status not in expected:
        return ReportCommandResult(1, f"报告当前处于「{report.status}」，不在该节点处理范围")

    if staged_flow and action_code in {'report.review.pass', 'report.approval.pass'}:
        role = 'reviewer' if action_code == 'report.review.pass' else 'approver'
        if role in esign_stages.state(staged_flow)['decisions']:
            flow = esign_stages.confirm_stage(report, user, role)
            db.session.commit()
            result = esign_stages.response(flow, user)
            return ReportCommandResult(0, result['message'], result)
    plan = None
    if str(action_code).endswith(".pass"):
        date_stage = {
            "report.report_check.pass": "review", "report.review.pass": "review",
            "report.approval.pass": "approval", "report.print.pass": "issue",
        }.get(action_code)
        if date_stage:
            from ...report_date_policy import report_date_error
            date_error = report_date_error(report, date_stage, business_today())
            if date_error:
                return ReportCommandResult(1, date_error)
        if action_code == "report.report_check.pass":
            blocker = document_version_blocker(report)
            if blocker:
                return ReportCommandResult(1, blocker)
        if action_code in ("report.review.pass", "report.approval.pass"):
            stage = "report_review" if action_code == "report.review.pass" else "report_approval"
            try:
                validate_and_record_acknowledgement(report, user, stage, body)
            except ValueError as exc:
                return ReportCommandResult(1, str(exc))
            # Compliance can align standards or change a rendered seal. Do not
            # approve bytes which predate those changes; roll back this attempt.
            if action_code == "report.review.pass":
                from ... import docparser_field_only
                if staged_flow or docparser_field_only.applies_to(report):
                    from ...report_version_consistency import lock_reviewed_document
                    try:
                        lock_reviewed_document(report, user)
                        blocker = ""
                    except ValueError as exc:
                        blocker = str(exc)
                else:
                    blocker = document_version_blocker(report)
            elif staged_flow:
                from ...report_version_consistency import require_reviewed_document
                try:
                    require_reviewed_document(report, record_legacy=False, actor=user)
                    blocker = ''
                except ValueError as exc:
                    blocker = str(exc)
            else:
                blocker = document_version_blocker(report, reviewed=True)
            if blocker:
                db.session.rollback()
                return ReportCommandResult(1, blocker)
        if staged_flow and action_code in {'report.review.pass', 'report.approval.pass'}:
            flow = esign_stages.confirm_stage(report, user, 'reviewer' if action_code == 'report.review.pass' else 'approver')
            db.session.commit()
            result = esign_stages.response(flow, user)
            return ReportCommandResult(0, result['message'], result)
        if action_code == "report.report_check.pass":
            check_input = (report.detail or {}).get("checkInput") or {}
            if not check_input.get("standard") or not check_input.get("instrument"):
                return ReportCommandResult(1, "请先录入检测信息（标准/仪器/检测日期）后再提交校核")
            _checks, danger, note = compute_report_checks(report)
            report.out_of_scope = danger
            report.out_of_scope_note = note
        if action_code == "report.print.pass":
            from ...functions.esign_service import issuance_blocker

            blocker = issuance_blocker(report)
            if blocker:
                return ReportCommandResult(1, blocker)
            report.stamped = True
        if action_code in ("report.review.pass", "report.approval.pass"):
            role = "审核" if action_code == "report.review.pass" else "批准"
            detail = dict(report.detail or {})
            signatures = dict(detail.get("signatures") or {})
            signatures[role] = (user.e_signature or user.name or "").strip()
            detail["signatures"] = signatures
            report.detail = detail
        if action_code == "report.approval.pass" and report.current_document_version_id:
            report.approved_document_version_id = report.current_document_version_id
        multi_done = True
        multi_msg = ""
        if action_code in ("report.review.pass", "report.approval.pass"):
            from ...platform.identity import project_for_report
            kind = "review" if action_code == "report.review.pass" else "approval"
            multi_done, multi_msg, multi_err = advance_stage_or_complete(
                report, user, kind, project_for_report(report), str(body.get("note") or "").strip()
            )
            if multi_err:
                db.session.rollback()
                return ReportCommandResult(1, multi_err)
        if multi_done:
            report.status = REPORT_NODE_FLOW.get(str(action_code), report.status)
            skipped_nodes = advance_skipped_project_steps(report)
            message = f"{report.report_no} 已流转至「{report.to_row().get('dataStatus', report.status)}」"
            if skipped_nodes:
                message += f"；按项目流程已跳过：{'、'.join(skipped_nodes)}"
            if report.out_of_scope:
                message += "（超范围，已通知批准人）"
        else:
            skipped_nodes = []
            message = multi_msg
    elif str(action_code).endswith(".return"):
        note = str(body.get("note") or "").strip()
        if not note:
            return ReportCommandResult(1, "退回必须填写原因")
        if staged_flow:
            esign_stages.cancel_round(staged_flow.id, user, note,
                return_action=action_code, return_mode=str(body.get('returnMode') or ''))
            return ReportCommandResult(0, '整轮签署已撤销，按退回路径修改后重新完成全部签字', report.to_row())
        plan = apply_return_plan(report, user, str(action_code), note, str(body.get("returnMode") or ""))
        reset_multi_stage_on_return(report)
        message = f"{report.report_no} 已退回：{plan['targetLabel']}"
    else:
        return ReportCommandResult(1, "未知动作")

    add_operation_audit(
        str(action_code),
        "report",
        report.report_no,
        category="workflow",
        before=before_row,
        after=report.to_row(),
        message=str(body.get("note") or "").strip(),
        actor=user,
    )
    if str(action_code).endswith(".pass") and finance_before_status != "待打印" and report.status == "待打印" and "报告批准" not in skipped_nodes:
        finance_capture(report, "REPORT_ISSUANCE_STARTED", user)
    db.session.commit()
    esign_flow = None
    issue_date_error = None
    esign_prepare_error = None
    if action_code == 'report.approval.pass':
        from ... import docparser_field_only
        if docparser_field_only.applies_to(report):
            try:
                from ...report_final_fields import ensure_approved_date_version
                from ...models import ReportDocumentVersion
                version = (db.session.get(ReportDocumentVersion, report.approved_document_version_id)
                           if report.approved_document_version_id else None)
                ensure_approved_date_version(report, version, user)
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                issue_date_error = str(exc)[:300]
                add_operation_audit('report.issue_date.failed', 'report', report.report_no,
                    category='report', success=False, actor=user, message=issue_date_error)
                db.session.commit()
                message += '；批准已保留，但报告日期核查未通过，暂不能发起新签署：' + issue_date_error
    if (
        action_code == "report.approval.pass"
        and not issue_date_error
        and current_app.config.get("ESIGN_WORKFLOW_ENABLED")
    ):
        try:
            from ...functions.esign_service import ensure_report_esign_flow

            esign_flow = ensure_report_esign_flow(report.report_no, user).to_dict()
        except Exception as exc:  # 批准已提交；明确呈现后续准备失败，不自动重新签署。
            db.session.rollback()
            esign_prepare_error = str(exc)[:300]
            message += '；批准已保留，但电子签署任务准备失败，请在报告签发页核查后重新准备：' + esign_prepare_error
            add_operation_audit(
                "report.esign.prepare.failed",
                "report",
                report.report_no,
                category="integration",
                success=False,
                message=str(exc),
                actor=user,
            )
            db.session.commit()
    return ReportCommandResult(
        0,
        message,
        {
            "reportNo": report.report_no,
            "status": report.status,
            "outOfScope": bool(report.out_of_scope),
            "outOfScopeNote": report.out_of_scope_note or "",
            "sampleStatus": report.sample_status or "待入库",
            "stamped": bool(report.stamped),
            "dataStatus": report.to_row().get("dataStatus", ""),
            "esignFlow": esign_flow,
            "issueDateError": issue_date_error,
            "esignPrepareError": esign_prepare_error,
            "returnPlan": plan,
        },
    )


__all__ = [
    "ReportCommandResult",
    "apply_sample_inbound_transition",
    "apply_sample_inbound_undo_transition",
    "apply_return_plan",
    "document_version_blocker",
    "execute_report_action",
    "return_plan",
]
