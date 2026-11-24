"""Canonical testing-record Commands.

The testing use case owns validation and transaction orchestration. Physical
testing fields still live on the legacy ``reports`` aggregate, so assignments
are delegated to the public ``report_lifecycle`` owner primitives. Desktop
HTTP and ELN adapters both call this module and cannot advance report workflow
by assigning ORM state themselves.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flask import current_app
from sqlalchemy.orm.exc import StaleDataError

from ...checks import compute_report_checks
from ...extensions import db
from ...models import Report, ReportAttachment
from ...platform.audit import add_operation_audit
from ...platform.file_vault import safe_file_name
from ...platform.identity import has_function_permission, project_step_error
from ...workflow_dates import latest_workflow_date, parse_date, validate_after_previous
from ..quality_resources import sync_equipment_usage_records
from ..report_lifecycle import (
    apply_eln_transfer_metadata,
    apply_testing_completion_transition,
    apply_testing_data_projection,
    persist_report_attachment,
    scoped_report_query,
)

EDITABLE_STATUSES = frozenset({"检测录入中", "退回待重传", "检测更改中"})


@dataclass(frozen=True)
class TestingCommandResult:
    code: int
    message: str
    data: Any = None
    http_status: int = 200
    report: Report | None = None
    attachment: ReportAttachment | None = None
    duplicate: bool = False

    def response_payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "data": self.data}


def _authorized_report(actor, report_no: str) -> tuple[Report | None, TestingCommandResult | None]:
    if actor is None or not bool(getattr(actor, "enabled", False)):
        return None, TestingCommandResult(403, "当前账号不存在或已停用")
    if not has_function_permission(actor, "testing.data_entry.view"):
        return None, TestingCommandResult(403, "无检测信息录入权限")
    report = scoped_report_query(Report.query, actor).filter(
        Report.report_no == str(report_no or "")
    ).first()
    if report is None:
        return None, TestingCommandResult(1, "报告不存在或不在数据范围内")
    if bool(report.voided):
        return None, TestingCommandResult(1, "作废报告不能录入或接收检测数据")
    grant_error = project_step_error(actor, report, "data_entry", "数据录入")
    if grant_error:
        return None, TestingCommandResult(403, grant_error)
    return report, None


def _sample_pickup_date(report: Report):
    pickup_date = parse_date(
        ((report.detail or {}).get("workflowDates") or {}).get("samplePickupAt")
    ) or parse_date((report.sample_pickup or {}).get("pickupTime"))
    return pickup_date


def _test_date_error(actor, report: Report, test_start: str, test_end: str) -> str:
    from ...report_date_policy import check_date_order
    return check_date_order(report, 'testEnd', test_end, actor,
        overrides={'testStart':test_start}, required=('pickup','testStart','testEnd'))['message']


def _editable_state_error(report: Report) -> str:
    from ...functions.esign_stages import content_blocker
    blocker = content_blocker(report)
    if blocker:
        return blocker
    if report.status not in EDITABLE_STATUSES:
        return f"报告当前为「{report.status}」，不在检测数据录入节点"
    if report.status != "检测更改中" and (report.sample_status or "待入库") != "已领取":
        return (
            f"样品当前为「{report.sample_status or '待入库'}」，"
            "请先完成样品入库与出库领取后再录入检测数据"
        )
    return ""


def save_test_draft(
    actor,
    report_no: str,
    *,
    detail: Mapping[str, Any],
    owner: str = "",
    validate_for_completion: bool = False,
    equipment_rows: Iterable[Any] = (),
    used_from: str = "",
    used_to: str = "",
    interval_end=None,
    alignment_note: str = "",
) -> TestingCommandResult:
    """Save one desktop testing draft through the canonical owner boundary."""

    from ...admin_corrections.existing import active as correcting
    if correcting("reports"):
        from flask import g
        report, error = g.business_correction["row"], None
    else:
        report, error = _authorized_report(actor, report_no)
    if error:
        return error
    state_error = "" if correcting("reports") else _editable_state_error(report)
    if state_error:
        return TestingCommandResult(1, state_error, report=report)
    if not isinstance(detail, Mapping):
        return TestingCommandResult(1, "检测数据格式无效", report=report)

    from ...report_date_policy import synchronize_sample_date_summary
    prepared = synchronize_sample_date_summary(dict(detail))
    check_input = prepared.get("checkInput") or {}
    if not isinstance(check_input, Mapping):
        return TestingCommandResult(1, "检测校验数据格式无效", report=report)
    # Drafts may be incomplete, but entered dates must obey the same ordering.
    from ...report_date_policy import report_date_error
    date_error = report_date_error(report, "testEnd", overrides={
        "testStart": check_input.get("testStartDate"),
        "testEnd": check_input.get("testDate"),
    })
    if date_error:
        return TestingCommandResult(1, date_error, report=report)
    for index, interval in enumerate(check_input.get("testIntervals") or []):
        if not isinstance(interval, Mapping):
            return TestingCommandResult(1, f"第 {index + 1} 个试验区间格式无效", report=report)
        start, end = str(interval.get("start") or ""), str(interval.get("end") or "")
        date_error = report_date_error(report, "testEnd", overrides={"testStart": start, "testEnd": end})
        if date_error:
            return TestingCommandResult(1, f"第 {index + 1} 个试验区间：{date_error}", report=report)
        if start and end and end < start:
            return TestingCommandResult(1, f"第 {index + 1} 个试验区间结束时间不能早于开始时间", report=report)
    required = (
        ("检测标准", "standard"),
        ("试验设备", "instrument"),
        ("试验开始日期", "testStartDate"),
        ("试验结束日期", "testDate"),
    )
    if validate_for_completion:
        missing = [label for label, key in required if not check_input.get(key)]
        if missing:
            return TestingCommandResult(
                1, "检测数据尚未完整：" + "、".join(missing), report=report
            )
        date_error = _test_date_error(
            actor,
            report,
            str(check_input.get("testStartDate") or ""),
            str(check_input.get("testDate") or ""),
        )
        if date_error:
            return TestingCommandResult(1, date_error, report=report)
        if not bool(check_input.get("validatedForCompletion")):
            return TestingCommandResult(1, "完成保存必须通过严格校验", report=report)

    if validate_for_completion:
        prepared.pop('testDataReviewRequired', None)
    before = report.to_row()
    try:
        previous_records = ((report.detail or {}).get('checkInput') or {}).get('standardRecords')
        next_records = (prepared.get('checkInput') or {}).get('standardRecords')
        if previous_records and next_records != previous_records:
            add_operation_audit('report.standard_records.update', 'report', report.report_no,
                category='workflow', actor=actor, before={'standardRecords':previous_records},
                after={'standardRecords':next_records}, message='检测保存更新标准记录；变更前后内容见审计快照')
        apply_testing_data_projection(report, detail=prepared, owner=owner)
        if validate_for_completion:
            sync_equipment_usage_records(
                report,
                tuple(equipment_rows),
                used_from=used_from,
                used_to=used_to,
                actor_account=actor.account,
                actor_name=actor.name or actor.account,
                interval_end=interval_end or parse_date(used_to),
            )
        db.session.flush()
        checks = compute_report_checks(report)[0] if validate_for_completion else []
        add_operation_audit(
            "report.data_entry.save",
            "report",
            report.report_no,
            category="workflow",
            before=before,
            after=report.to_row(),
            actor=actor,
            message=alignment_note or None,
        )
        from ...report_date_policy import audit_sample_date_alignment
        audit_sample_date_alignment(report.report_no, detail, actor)
        from ...edit_concurrency import test_form_version
        saved_form_version = test_form_version(report)
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        return TestingCommandResult(409, "保存期间检测数据已被更新，请保留输入并重新打开核对。", http_status=409)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("testing data save Command failed")
        return TestingCommandResult(
            1, "检测数据保存失败，事务已回滚", http_status=500
        )

    if validate_for_completion:
        return TestingCommandResult(
            0,
            "检测信息已保存，三库校验已完成",
            {"checks": checks, "draft": False, "testEditVersion": saved_form_version},
            report=report,
        )
    return TestingCommandResult(
        0,
        "检测数据草稿已保存" + ("；已按样品单标准更新" if alignment_note else ""),
        {"checks": [], "draft": True, "testEditVersion": saved_form_version,
         "notice": "已按样品单标准更新" if alignment_note else ""},
        report=report,
    )


def complete_test_data(
    actor,
    report_no: str,
    *,
    completion_blocker: str = "",
    signing_workflow: str | None = None,
) -> TestingCommandResult:
    """Complete testing and enter report review; ELN can only add a blocker."""

    report, error = _authorized_report(actor, report_no)
    if error:
        return error
    db.session.refresh(report, with_for_update=True)
    if report.status != "检测录入中" or (report.sample_status or "") != "已领取":
        return TestingCommandResult(
            1,
            f"报告当前为「{report.status}」、样品为「{report.sample_status or '待入库'}」，不能完成检测录入",
            report=report,
        )
    from ...functions import esign_stages
    existing = esign_stages.current_flow(report, lock=True)
    if existing:
        if signing_workflow is not None and signing_workflow != esign_stages.MODE:
            return TestingCommandResult(1, "该报告已确定签署流程，退回或撤回后仍沿用原选择", report=report)
        result = esign_stages.response(existing, actor)
        return TestingCommandResult(0, result['message'], result, report=report)
    check_input = (report.detail or {}).get("checkInput") or {}
    if not check_input.get("validatedForCompletion"):
        return TestingCommandResult(
            1,
            "请点击“保存并完成检测”，完成必填项及三库校验后再提交",
            report=report,
        )
    missing = [label for label, key in (
        ("检测标准", "standard"),
        ("试验设备", "instrument"),
        ("试验开始日期", "testStartDate"),
        ("试验结束日期", "testDate"),
    ) if not check_input.get(key)]
    if missing:
        return TestingCommandResult(
            1, "检测数据尚未完整：" + "、".join(missing), report=report
        )
    date_error = _test_date_error(
        actor,
        report,
        str(check_input.get("testStartDate") or ""),
        str(check_input.get("testDate") or ""),
    )
    if date_error:
        return TestingCommandResult(1, date_error, report=report)
    if str(completion_blocker or "").strip():
        return TestingCommandResult(1, str(completion_blocker).strip(), report=report)

    before = report.to_row()
    try:
        mode = esign_stages.choose_at_completion(report, actor, signing_workflow)
        if mode is None:
            return TestingCommandResult(0, "请选择签署流程", {"esignWorkflowRequired": True}, report=report)
        from ...review_version import freeze_ready_preview
        version = freeze_ready_preview(report, actor)
        _checks, danger, note = compute_report_checks(report)
        if mode == esign_stages.MODE:
            report.out_of_scope, report.out_of_scope_note = danger, note
            flow = esign_stages.begin(report, version, actor, mode=mode)
            db.session.commit()
            result = esign_stages.response(flow, actor)
            return TestingCommandResult(0, result['message'], result, report=report)
        skipped_nodes = apply_testing_completion_transition(
            report,
            out_of_scope=danger,
            out_of_scope_note=note,
        )
        add_operation_audit(
            "report.data_entry.complete",
            "report",
            report.report_no,
            category="workflow",
            before=before,
            after=report.to_row(),
            actor=actor,
        )
        db.session.commit()
    except (ValueError, esign_stages.service.EsignServiceError) as exc:
        db.session.rollback()
        return TestingCommandResult(1, str(exc), report=report)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("testing data completion Command failed")
        return TestingCommandResult(
            1, "检测数据完成失败，事务已回滚", http_status=500
        )

    message = f"{report.report_no} 检测数据录入完成，已进入报告审核"
    if skipped_nodes:
        message += f"；按项目流程已跳过：{'、'.join(skipped_nodes)}"
    if report.out_of_scope:
        message += "（超范围，已通知审核/批准人员）"
    return TestingCommandResult(0, message, report.to_row(), report=report)


def submit_original_record(
    actor,
    report_no: str,
    *,
    raw_pdf: bytes,
    original_name: str,
    record_id: str = "",
    task_revision: str = "",
    idempotency_key: str = "",
    max_bytes: int | None = None,
) -> TestingCommandResult:
    """Attach one ELN PDF idempotently without changing report workflow state."""

    report, error = _authorized_report(actor, report_no)
    if error:
        return error
    state_error = _editable_state_error(report)
    if state_error:
        return TestingCommandResult(1, state_error, report=report)
    payload = bytes(raw_pdf or b"")
    if not payload.startswith(b"%PDF-"):
        return TestingCommandResult(1, "回传文件不是有效的 PDF", http_status=400, report=report)
    if max_bytes is not None and len(payload) > int(max_bytes):
        return TestingCommandResult(1, "原始记录 PDF 超过允许大小", http_status=413, report=report)

    record_id = str(record_id or "").strip()[:100]
    task_revision = str(task_revision or "").strip()[:64]
    key = str(idempotency_key or record_id or "").strip()[:160]
    integration = dict((report.detail or {}).get("elnIntegration") or {})
    transfers = list(integration.get("transfers") or [])
    if key:
        previous = next(
            (item for item in transfers if item.get("idempotencyKey") == key),
            None,
        )
        if previous:
            attachment = db.session.get(ReportAttachment, previous.get("attachmentId"))
            if attachment and attachment.deleted_at is None:
                return TestingCommandResult(
                    0,
                    "ok",
                    {"attachment": attachment.meta(), "duplicate": True},
                    report=report,
                    attachment=attachment,
                    duplicate=True,
                )

    fallback = f"ELN-{report.report_no}-{record_id or datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
    try:
        name = safe_file_name(original_name or fallback, max_length=200)
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        attachment = persist_report_attachment(
            report,
            payload,
            category="report_attachment",
            name=name,
            content_type="application/pdf",
            kind="PDF",
            source="原始记录",
            status="已上传",
            uploaded_by=f"ELN · {actor.name or actor.account}",
            created_by=f"ELN/{actor.account}",
            max_bytes=max_bytes,
        )
        transfer = {
            "recordId": record_id,
            "attachmentId": attachment.id,
            "fileName": name,
            "sha256": attachment.stored_file.sha256,
            "taskRevision": task_revision,
            "idempotencyKey": key,
            "receivedAt": datetime.now(UTC).isoformat(),
            "userAccount": actor.account,
        }
        apply_eln_transfer_metadata(report, transfer)
        add_operation_audit(
            "eln.original_record.receive",
            "report",
            report.report_no,
            category="integration",
            after=transfer,
            message=f"ELN 回传原始记录 PDF：{name}",
            actor=actor,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("original record submission Command failed")
        return TestingCommandResult(
            1, "原始记录 PDF 保存失败", http_status=500, report=report
        )
    return TestingCommandResult(
        0,
        "原始记录 PDF 已导入检测数据录入模块",
        {"attachment": attachment.meta(), "duplicate": False},
        report=report,
        attachment=attachment,
    )


__all__ = [
    "EDITABLE_STATUSES",
    "TestingCommandResult",
    "complete_test_data",
    "save_test_draft",
    "submit_original_record",
]
