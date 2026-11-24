"""Unified CNAS/CMA preflight and immutable per-stage acknowledgements."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from .platform.audit import add_operation_audit
from .platform.identity import project_for_report
from .checks import compute_report_checks
from .extensions import db
from .models import (
    CapabilityEntry,
    CapabilityImportBatch,
    ComplianceAcknowledgement,
    OperationAudit,
)
from .standard_control import find_controlled_standard, split_standard_codes, standard_scope_failures, standard_authorized_marks
from .preflight_reads import reuse_preflight_reads
from .seal_requirements import requested_seal as _requested_seal

STAGES = {"contract_review", "report_review", "report_approval"}

# Successful workflow re-entry is distinct from editing the compliance inputs.
# Use the existing immutable audit ID so already-returned reports also recover,
# without deleting acknowledgements or trusting a client-supplied round counter.
_CONTRACT_REENTRY = (
    "sample.register.complete", "report.entrust_change.complete",
    "report.contract_review.undo",
)
_REVIEW_REENTRY = _CONTRACT_REENTRY + (
    "report.data_entry.complete", "report.test_change.complete",
    "report.report_check.pass", "report.review.undo",
)
_STAGE_REENTRY = {
    "contract_review": _CONTRACT_REENTRY,
    "report_review": _REVIEW_REENTRY,
    "report_approval": _REVIEW_REENTRY + (
        "report.review.pass", "report.approval.undo",
    ),
}


def _review_round(report_no: str, stage: str) -> int | None:
    row = (OperationAudit.query.with_entities(OperationAudit.id)
           .filter_by(object_type="report", object_id=report_no, success=True)
           .filter(OperationAudit.action.in_(_STAGE_REENTRY[stage]))
           .order_by(OperationAudit.id.desc()).first())
    return row.id if row else None


def _field(detail: dict, section_name: str, field_name: str) -> str:
    for section in detail.get("summary") or []:
        if section.get("title") != section_name:
            continue
        for field in section.get("fields") or []:
            if isinstance(field, (list, tuple)) and len(field) >= 2 and field[0] == field_name:
                return str(field[1] or "").strip()
    return ""


def _standards(detail: dict) -> list[str]:
    from .report_standard_selection import standards_for_authorization
    return standards_for_authorization(detail)


def _standard(detail: dict) -> str:
    return "；".join(_standards(detail))


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _business_date(detail: dict) -> date:
    raw = detail.get("rawSample") or {}
    check = detail.get("checkInput") or {}
    return (
        _parse_date(check.get("testDate"))
        or _parse_date(raw.get("sendDate"))
        or _parse_date(raw.get("entrustDate"))
        or date.today()
    )


def _manual_projects(detail: dict) -> tuple[list[str], str]:
    raw = detail.get("rawSample") or {}
    value = raw.get("manualCapabilityItems") or []
    if isinstance(value, str):
        value = [part.strip() for part in re.split(r"[、；;\n]+", value) if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()], str(
        raw.get("manualCapabilityReason") or ""
    ).strip()


def _issue(category: str, title: str, message: str, *, evidence=None, effect="", hard=False, level=None) -> dict:
    basis = json.dumps(
        {"category": category, "title": title, "message": message, "evidence": evidence or {}},
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "id": hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20],
        "category": category,
        "title": title,
        "message": message,
        "evidence": evidence or {},
        "effect": effect,
        "level": level or ("block" if hard else "confirm"),
        "code": category,
        "hardBlocker": hard,
        "acknowledgeable": not hard and level != "notice",
    }


def _remove_mark(seal: str, mark: str) -> str:
    values = [
        value for value in re.split(r"[+、,\s]+", seal or "")
        if value and value.upper() != mark.upper()
    ]
    return " + ".join(values)


@reuse_preflight_reads
def build_compliance_preflight(report, stage: str) -> dict:
    if stage not in STAGES:
        raise ValueError("未知合规确认节点")
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    check_input = detail.get("checkInput") or {}
    requested_seal = _requested_seal(detail)
    final_seal = requested_seal
    standard_text = _standard(detail)
    standards = _standards(detail)
    when = _business_date(detail)
    active_batches = (
        CapabilityImportBatch.query
        .with_entities(CapabilityImportBatch.id, CapabilityImportBatch.source_sha256)
        .filter(
            CapabilityImportBatch.status.in_(("active", "review")),
            db.session.query(CapabilityEntry.id).filter(
                CapabilityEntry.batch_id == CapabilityImportBatch.id,
                CapabilityEntry.active.is_(True),
            ).exists(),
        )
        .order_by(CapabilityImportBatch.id)
        .all()
    )
    required = bool(active_batches)
    issues = []

    if project_for_report(report) is None:
        issues.append(_issue(
            "department_project_missing",
            "检测项目未关联部门项目库",
            f"检测项目「{report.project or '未填写'}」未匹配部门「{report.department or '未分配'}」的项目编号",
            evidence={"project": report.project or "", "department": report.department or ""},
            hard=True,
        ))

    manual_items, manual_reason = _manual_projects(detail)
    # Manual parameters are display/input data, not accreditation failures.

    standard_coverage = []
    selected_ids = []
    for value in raw.get("capabilityEntryIds") or []:
        try:
            selected_ids.append(int(value))
        except (TypeError, ValueError):
            issues.append(_issue(
                "invalid_capability_id",
                "能力记录编号无效",
                f"能力记录编号「{value}」不是有效编号",
                hard=True,
            ))
    entries = (
        CapabilityEntry.query.filter(CapabilityEntry.id.in_(selected_ids)).all()
        if selected_ids else []
    )
    entry_by_id = {row.id: row for row in entries}
    department = str(report.department or "").strip()
    # Parameters only establish library membership in this check. Do not infer
    # standard authorization from a parameter's location/type/date/mark/notes.
    for entry_id in dict.fromkeys(selected_ids):
        if entry_id not in entry_by_id:
            issues.append(_issue('capability_not_found', '检测参数不在库内',
                f'参数记录 {entry_id} 不存在。可填写依据确认继续；确认后移除 CMA/CNAS，并通知管理员核对数据',
                evidence={'entryId': entry_id}, effect='移除 CMA/CNAS 标识'))
            final_seal = _remove_mark(_remove_mark(final_seal, 'CMA'), 'CNAS')

    from .report_standard_selection import testing_selection_conflict
    conflict = testing_selection_conflict(detail) if stage != 'contract_review' else ''
    if conflict:
        issues.append(_issue('standard_selection_mismatch', '登记与检测依据不一致', conflict,
                             effect='保留盖章要求，复核标准关联', hard=True))

    if not conflict and stage != 'contract_review' and raw.get('standardItemIds'):
        from .functions.report_standard_text import load_report_standard_records
        expected = load_report_standard_records(standards, raw['standardItemIds'])
        if check_input.get('standardRecords') and expected != check_input.get('standardRecords'):
            issues.append(_issue('standard_identity_alignment', '标准记录自动对齐',
                '标准编号相同，提交时将按登记记录自动对齐检测标准ID；CMA/CNAS按登记记录判断',
                evidence={'registeredIds':raw['standardItemIds']}, level='notice'))

    if standards:
        from .standard_control import selected_controlled_standards
        for _std, result in selected_controlled_standards(standards, raw.get('standardItemIds'), department, when):
            standard_value = result['code']
            marks = [mark for mark in ('CMA', 'CNAS') if mark in requested_seal.upper()]
            if result.get('identityUnresolved'):
                issues.append(_issue('standard_identity_unresolved', '标准关联待核对',
                    standard_value + '：' + result['reason'],
                    evidence={'standard': standard_value, 'department': department},
                    effect='保留盖章要求，在当前校核窗口选择标准并填写依据，再重新校核', hard=True))
                standard_coverage.append({'standard': standard_value, 'marks': [],
                    'valid': False, 'result': result, 'failures': [], 'needsReview': True})
                continue
            failures = standard_scope_failures(result, marks)
            standard_coverage.append({'standard': standard_value,
                'marks': standard_authorized_marks(result),
                'valid': not failures, 'result': result, 'failures': failures})
            for failure in failures:
                issues.append(_issue(failure['category'], failure['message'],
                    standard_value + '：' + failure['message'],
                    evidence={'standard': standard_value, 'department': department, 'date': when.isoformat()},
                    effect='移除 ' + '/'.join(failure['marks']) + ' 标识' if failure['marks'] else '核实受控标准'))
                for mark in failure['marks']:
                    final_seal = _remove_mark(final_seal, mark)
    else:
        issues.append(_issue(
            "standard_missing",
            "未填写检测标准",
            "必须选择现行受控标准",
            hard=True,
        ))

    if stage in {"report_review", "report_approval"} and not check_input:
        issues.append(_issue(
            "test_data_missing",
            "检测数据尚未完整录入",
            "报告审核或批准前必须完成检测标准、仪器设备和检测日期录入",
            hard=True,
        ))
    # Instruments are selected during test-data entry, after contract review.
    # A partially prefilled checkInput already exists for some newly registered
    # reports, so using its mere presence here would incorrectly treat "not yet
    # selected" as "selected but invalid" and strip the requested marks.
    elif stage in {"report_review", "report_approval"} and check_input:
        checks, _danger, _note = compute_report_checks(report)
        equipment_check = next(
            (row for row in checks if row.get("group") == "仪器有效性校验"),
            None,
        )
        if equipment_check and equipment_check.get("status") != "通过":
            evidence = {
                "status": equipment_check.get("status"),
                "items": equipment_check.get("items") or [],
                "testDate": check_input.get("testDate") or "",
            }
            issues.append(_issue(
                "instrument_validity",
                "仪器设备有效性校验未通过",
                "；".join(str(item[1]) for item in evidence["items"]
                         if isinstance(item, (list, tuple)) and len(item) > 1 and item[0] == "阻断原因")
                or "所选仪器不在受控设备库内，请核对仪器关联",
                evidence=evidence,
                effect="请重新选择有效仪器或由设备管理员核对台账；保留原盖章要求",
                hard=True,
            ))

    if any(row['category'] in {'standard_selection_mismatch', 'standard_identity_unresolved'} for row in issues):
        final_seal = requested_seal
    required = required or any(row['hardBlocker'] or row['acknowledgeable'] for row in issues) or any(row['category'] in {'standard_selection_mismatch', 'standard_identity_unresolved'} for row in issues)
    from .standard_resolution import resolution_choices
    identity_choices = resolution_choices(report)
    for issue in issues:
        if issue['category'] == 'standard_identity_unresolved' and identity_choices and all(c['candidates'] for c in identity_choices):
            issue['level'] = 'confirm'
            issue['resolutionRequired'] = True
    issue_rows = sorted(issues, key=lambda row: (row["hardBlocker"], row["category"], row["id"]))
    fingerprint_raw = dict(raw)
    fingerprint_check_input = dict(check_input)
    if raw.get('standardItemIds') and not conflict:
        from .functions.report_standard_text import load_report_standard_records
        fingerprint_check_input['standardRecords'] = load_report_standard_records(standards, raw['standardItemIds'])
    # Compliance processing writes the stripped final seal back for display.
    # Normalize that system-managed field to the original request so recording
    # an acknowledgement does not invalidate itself.
    fingerprint_raw["seal"] = requested_seal
    fingerprint_check_input["seal"] = requested_seal
    version_source = {
        "stage": stage,
        "reportNo": report.report_no,
        "department": department,
        "standard": standard_text,
        "businessDate": when.isoformat(),
        "selectedIds": selected_ids,
        "manualItems": manual_items,
        "manualReason": manual_reason,
        "requestedSeal": requested_seal,
        "finalSeal": final_seal,
        "inputFingerprint": hashlib.sha256(
            json.dumps(
                {"rawSample": fingerprint_raw, "checkInput": fingerprint_check_input},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "activeBatches": [(row.id, row.source_sha256) for row in active_batches],
        "standardCoverage": standard_coverage,
        "coveragePolicy": "guard-three-level-strict-dates-v7",
        "issues": [row for row in issue_rows if row["category"] != "standard_identity_alignment"],
    }
    review_round = _review_round(report.report_no, stage)
    if review_round is not None:
        version_source["workflowRound"] = review_round
    version = hashlib.sha256(
        json.dumps(version_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    # Display reminders are excluded from the immutable acknowledgement fingerprint.
    if stage == 'contract_review':
        notice = OperationAudit.query.filter_by(action='quality.guard_notice', object_type='report', object_id=report.report_no).order_by(OperationAudit.id.desc()).first()
        if notice:
            issue_rows = issue_rows + [_issue('parameter_record_notice', '参数记录待核对', notice.message,
                evidence={'auditId':notice.id}, level='notice')]
    return {
        "required": required,
        "stage": stage,
        "preflightVersion": version,
        "requestedSeal": requested_seal,
        "finalSeal": final_seal,
        "issues": issue_rows,
        "standardCoverage": standard_coverage,
        "hardBlockers": [row for row in issue_rows if row["hardBlocker"]],
        "standardChoices": identity_choices,
        "requiresOpinion": any(row["acknowledgeable"] for row in issue_rows),
        "ready": not any(row["hardBlocker"] for row in issue_rows),
    }


def _apply_final_seal(report, requested_seal: str, final_seal: str, stage: str, version: str) -> None:
    detail = dict(report.detail or {})
    raw = dict(detail.get("rawSample") or {})
    raw["seal"] = final_seal
    detail["rawSample"] = raw
    check_input = dict(detail.get("checkInput") or {})
    check_input["seal"] = final_seal
    detail["checkInput"] = check_input
    summary = []
    for section in detail.get("summary") or []:
        section = dict(section)
        fields = []
        for field in section.get("fields") or []:
            field = list(field)
            if section.get("title") == "委托信息" and len(field) >= 2 and field[0] == "盖章要求":
                field[1] = final_seal
            fields.append(field)
        section["fields"] = fields
        summary.append(section)
    detail["summary"] = summary
    resolution = dict(detail.get("complianceResolution") or {})
    resolution.setdefault("requestedSealOriginal", requested_seal)
    resolution.update({
        "requestedSealCurrent": requested_seal,
        "finalSeal": final_seal,
        "lastStage": stage,
        "preflightVersion": version,
    })
    detail["complianceResolution"] = resolution
    report.detail = detail


def validate_and_record_acknowledgement(report, user, stage: str, payload: dict) -> dict:
    preflight = build_compliance_preflight(report, stage)
    if not preflight["required"]:
        from .standard_resolution import align_testing_identity
        align_testing_identity(report, user)
        return preflight
    submitted_version = str(payload.get("preflightVersion") or "")
    if submitted_version and ComplianceAcknowledgement.query.filter_by(
        report_no=report.report_no,
        stage=stage,
        preflight_version=submitted_version,
    ).first():
        raise ValueError("本节点的当前合规检查结果已经确认，不能重复提交")
    if payload.get("preflightVersion") != preflight["preflightVersion"]:
        raise ValueError("合规检查结果已变化，请刷新后重新确认")
    if preflight["hardBlockers"]:
        raise ValueError("存在不能确认绕过的问题：" + "；".join(
            row["message"] for row in preflight["hardBlockers"]
        ))
    needed = {row["id"] for row in preflight["issues"] if row["acknowledgeable"]}
    acknowledged = {str(value) for value in payload.get("acknowledgedIssueIds") or []}
    missing = needed - acknowledged
    if missing:
        raise ValueError("请逐项确认全部合规问题")
    opinion = str(payload.get("complianceOpinion") or "").strip()
    if needed and not opinion:
        raise ValueError("存在合规问题时必须填写确认意见")
    if str(payload.get("finalSeal") or "") != preflight["finalSeal"]:
        raise ValueError("最终标识与系统合规处理结果不一致")
    if ComplianceAcknowledgement.query.filter_by(
        report_no=report.report_no,
        stage=stage,
        preflight_version=preflight["preflightVersion"],
    ).first():
        raise ValueError("本节点的当前合规检查结果已经确认，不能重复提交")

    acknowledgement = ComplianceAcknowledgement(
        report_no=report.report_no,
        stage=stage,
        preflight_version=preflight["preflightVersion"],
        issues=preflight["issues"],
        acknowledged_issue_ids=sorted(acknowledged),
        requested_seal=preflight["requestedSeal"],
        final_seal=preflight["finalSeal"],
        opinion=opinion,
        actor_id=user.id,
        actor_account=user.account,
        actor_name=user.name or user.account,
        created_at=datetime.utcnow(),
    )
    db.session.add(acknowledgement)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("本节点已由其他人员完成确认，请刷新当前页面") from exc
    from .standard_resolution import align_testing_identity
    align_testing_identity(report, user)
    _apply_final_seal(
        report,
        preflight["requestedSeal"],
        preflight["finalSeal"],
        stage,
        preflight["preflightVersion"],
    )
    # A re-review may go straight back to report review without data entry.
    # Refresh the persisted scope flag here so old manual-only warnings do not
    # survive that path. Historical acknowledgements remain immutable.
    from .report_scope import assess_scope
    scope = assess_scope(report)
    report.out_of_scope = scope['outOfScope']
    report.out_of_scope_note = scope['note'] if scope['outOfScope'] else ''
    if any(row['category'] == 'capability_not_found' for row in preflight['issues']):
        add_operation_audit('quality.guard_notice', 'report', report.report_no, category='quality', actor=user,
            after={'department': report.department, 'recipientRoles': ['管理员', '合同评审人'],
                   'issues': preflight['issues'], 'reason': opinion},
            message='参数记录缺失已确认继续，CMA/CNAS标识已移除，请管理员核对，合同评审人复核')
    add_operation_audit(
        "compliance.acknowledge",
        "report",
        report.report_no,
        category="compliance",
        after={
            "stage": stage,
            "preflightVersion": preflight["preflightVersion"],
            "acknowledgedIssueIds": sorted(acknowledged),
            "requestedSeal": preflight["requestedSeal"],
            "finalSeal": preflight["finalSeal"],
            "opinion": opinion,
        },
        actor=user,
    )
    return preflight


__all__ = ["build_compliance_preflight", "validate_and_record_acknowledgement"]
