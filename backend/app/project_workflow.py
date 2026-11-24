"""Per-project report workflow configuration and automatic skipped-node advancement."""
from __future__ import annotations

from datetime import date

from .platform.identity import project_for_report

PROJECT_WORKFLOW_STEPS = [
    {"code": "entrust_review", "name": "合同评审"},
    {"code": "sample_inbound", "name": "样品入库"},
    {"code": "sample_outbound", "name": "样品出库并领取"},
    {"code": "data_entry", "name": "检测数据录入"},
    {"code": "report_review", "name": "报告审核"},
    {"code": "report_approval", "name": "报告批准"},
    {"code": "report_print", "name": "报告签发"},
    {"code": "report_archive", "name": "报告归档"},
]
PROJECT_WORKFLOW_STEP_CODES = {item["code"] for item in PROJECT_WORKFLOW_STEPS}


def normalize_skipped_steps(values) -> list[str]:
    requested = {str(value or "").strip() for value in (values or [])}
    return [
        item["code"]
        for item in PROJECT_WORKFLOW_STEPS
        if item["code"] in requested
    ]


def skipped_steps_for_project(project) -> set[str]:
    config = project.workflow_config if isinstance(project.workflow_config, dict) else {}
    return set(normalize_skipped_steps(config.get("skippedSteps")))


def _append_skip_record(report, step_code: str, step_name: str) -> None:
    detail = dict(report.detail or {})
    records = list(detail.get("projectWorkflowSkips") or [])
    records.append({
        "stepCode": step_code,
        "stepName": step_name,
        "date": date.today().isoformat(),
    })
    detail["projectWorkflowSkips"] = records[-50:]
    report.detail = detail


def advance_skipped_project_steps(report) -> list[str]:
    """Advance through consecutive skipped nodes and apply their minimal state effects.

    The caller owns the transaction and audit event. The helper is deliberately
    idempotent: once a state has advanced, the same skipped node is not applied again.
    """
    project = project_for_report(report)
    if project is None:
        return []
    skipped = skipped_steps_for_project(project)
    if not skipped:
        return []

    advanced: list[str] = []
    for _ in range(len(PROJECT_WORKFLOW_STEPS) + 1):
        step_code = ""
        step_name = ""
        if (
            report.status == "待合同评审"
            and (report.sample_reg_state or "登记完成") == "登记完成"
            and not (report.detail or {}).get("requiresContractReReview")
            and "entrust_review" in skipped
        ):
            step_code, step_name = "entrust_review", "合同评审"
            report.sample_status = "待入库"
            report.status = "待样品入库"
        elif report.status == "待样品入库" and "sample_inbound" in skipped:
            step_code, step_name = "sample_inbound", "样品入库"
            report.sample_status = "已入库"
            report.status = "待样品领取"
        elif report.status == "待样品领取" and "sample_outbound" in skipped:
            step_code, step_name = "sample_outbound", "样品出库并领取"
            report.sample_status = "已领取"
            report.status = "检测录入中"
        elif report.status == "检测录入中" and "data_entry" in skipped:
            step_code, step_name = "data_entry", "检测数据录入"
            report.status = "待审核"
        elif report.status == "待审核" and "report_review" in skipped:
            # Skipping the human review must still freeze a verified document.
            from . import docparser_field_only
            if docparser_field_only.applies_to(report):
                from .report_version_consistency import lock_reviewed_document
                lock_reviewed_document(report)
            step_code, step_name = "report_review", "报告审核"
            report.status = "待批准"
        elif report.status == "待批准" and "report_approval" in skipped:
            step_code, step_name = "report_approval", "报告批准"
            report.status = "待打印"
        elif report.status == "待打印" and "report_print" in skipped:
            from .report_delivery import sealed_current_flow
            if not sealed_current_flow(report):
                break  # a project skip cannot substitute for actual signatures/seal
            step_code, step_name = "report_print", "报告签发"
            report.stamped = True
            report.status = "待发放"
        else:
            break

        _append_skip_record(report, step_code, step_name)
        advanced.append(step_name)
    if advanced:
        from .workflow_hooks import skipped as finance_skipped
        finance_skipped(report, advanced)
    return advanced


__all__ = [
    "PROJECT_WORKFLOW_STEPS",
    "PROJECT_WORKFLOW_STEP_CODES",
    "advance_skipped_project_steps",
    "normalize_skipped_steps",
    "skipped_steps_for_project",
]
