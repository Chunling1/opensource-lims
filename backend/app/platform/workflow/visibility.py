"""Pure workflow visibility rules shared by every delivery adapter.

The functions in this module do not query or mutate the database.  They make
the processing-list contract explicit: query views see the full authorized
lifecycle, while handling views see their active state plus an explicitly
labelled recall projection where the existing undo rules permit it.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any


REPORT_LIST_VIEW_PERMISSIONS = {
    "dashboard": "dashboard.view",
    "query": "report.query.view",
    "contract_review": "entrust.contract_review.view",
    "data_entry": "testing.data_entry.view",
    "data_change": "testing.data_change.view",
    "review": "report.review.view",
    "interim_report": "report.interim_report.view",
    "approval": "report.approval.view",
    "print": "report.print.view",
    "archive": "report.archive.view",
    "release": "report.release.view",
    "change_request": "report.change_request.view",
}

SAMPLE_LIST_VIEW_PERMISSIONS = {
    "register": "entrust.sample_register.view",
    "inbound": "sample.inbound.view",
    "outbound": "sample.outbound.view",
    "flow_query": "sample.flow_query.view",
}

UNDO_FLOW = {
    "report.contract_review.undo": ("待样品入库", "待合同评审"),
    "report.report_check.undo": ("待审核", "检测录入中"),
    "report.review.undo": ("待批准", "待审核"),
    "report.approval.undo": ("待打印", "待批准"),
    "report.print.undo": ("已发放", "待打印"),
}

REPORT_NODE_FLOW = {
    "report.report_check.pass": "待审核",
    "report.review.pass": "待批准",
    "report.approval.pass": "待打印",
    "report.print.pass": "待发放",
}

REPORT_NODE_EXPECTED = {
    "testing.data_entry": frozenset({"检测录入中"}),
    "report.report_check": frozenset({"待校核", "退回待重传"}),
    "report.review": frozenset({"待审核"}),
    "report.approval": frozenset({"待批准"}),
    "report.print": frozenset({"待打印"}),
}


def report_projection(row: Mapping[str, Any], view: str) -> str | None:
    """Return ``active``, ``recall`` or ``None`` for a report list row."""

    status = str(row.get("status") or "")
    actions = _actions(row.get("allowedActions"))
    if view == "query":
        return "active"
    if view == "archive":
        if "report.archive.pass" in actions and not bool(row.get("voided")) and (
            (status == "待打印" and row.get("dataStatus") == "报告已盖章，归档中，未发放")
            or status in {"待发放", "已发放"}
        ) and str(row.get("archiveState") or "") != "归档完成":
            return "active"
        # Archive search spans the authorized lifecycle. Other stages are read-only;
        # archive commands still enforce state, project grants and allowedActions.
        return "recall"
    if bool(row.get("voided")):
        return None
    if view == "contract_review":
        if (
            status == "待合同评审"
            and str(row.get("sampleRegState") or "登记完成") == "登记完成"
        ):
            return "active"
        from ...workflow_hooks import PRE_ISSUANCE, ISSUED
        if status in PRE_ISSUANCE or status in ISSUED or status in {"待合同评审", "委托更改中"}:
            return "recall"
    elif view == "data_entry":
        if status == "检测录入中" and str(row.get("sampleStatus") or "") == "已领取":
            return "active"
        if status == "待审核" and "report.report_check.undo" in actions:
            return "recall"
    elif view == "data_change":
        return "active" if status in {"退回待重传", "检测更改中"} else None
    elif view in {"review", "interim_report"}:
        if status == "待审核":
            return "active"
        if status == "待批准" and "report.review.undo" in actions:
            return "recall"
    elif view == "approval":
        if status == "待批准":
            return "active"
        if status == "待打印" and "report.approval.undo" in actions:
            return "recall"
    elif view == "print":
        if status == "待打印":
            return "active"
        if status in {"待发放", "已发放", "已归档"}:
            return "recall"
    elif view == "release":
        if status in {"待发放", "已发放"} and row.get("archiveState") == "归档完成":
            return "recall" if row.get("distributionComplete") else "active"
        return None
    elif view == "change_request":
        if row.get("hasInternalCorrectionHistory"):
            return "active"
        return "active" if status in {"待打印", "待发放", "已发放"} else None
    return None


def report_matches_view(row: Mapping[str, Any], view: str) -> bool:
    return report_projection(row, view) is not None


def sample_matches_view(report, row: Mapping[str, Any], view: str) -> bool:
    """Apply the canonical sample list-state policy to an ORM-like object."""

    status = str(getattr(report, "status", "") or "")
    sample_status = str(getattr(report, "sample_status", "") or "")
    if view == "flow_query":
        return True
    if bool(getattr(report, "voided", False)):
        return False
    if view == "register":
        return status == "待合同评审" and str(
            getattr(report, "sample_reg_state", "") or "登记完成"
        ) in {"登记中", "登记完成"}
    if view == "inbound":
        return bool(
            (status == "待样品入库" and sample_status == "待入库")
            or (status == "待样品领取" and sample_status == "已入库")
        )
    if view == "outbound":
        return bool(
            (status == "待样品领取" and sample_status == "已入库")
            or (
                status == "检测录入中"
                and sample_status == "已领取"
                and bool(row.get("canRecallSampleOutbound"))
            )
        )
    return False


def _actions(value: Any) -> set[str]:
    if not isinstance(value, Collection) or isinstance(value, (str, bytes)):
        return set()
    return {str(item) for item in value}


__all__ = [
    "REPORT_LIST_VIEW_PERMISSIONS",
    "REPORT_NODE_EXPECTED",
    "REPORT_NODE_FLOW",
    "SAMPLE_LIST_VIEW_PERMISSIONS",
    "UNDO_FLOW",
    "report_matches_view",
    "report_projection",
    "sample_matches_view",
]
