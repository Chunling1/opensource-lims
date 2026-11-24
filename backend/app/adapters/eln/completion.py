"""ELN completion gate consumed by the report lifecycle."""

from __future__ import annotations

import hashlib
import json

from flask import current_app

from ...data_models.eln import (
    ElnOriginalRecord,
    ElnProjectConfig,
    ElnRecordTemplate,
    ElnTaskPolicy,
)
from ...extensions import db
from ...platform.audit import latest_operation_audit
from ...platform.identity import project_for_report


def _person_code(value):
    if isinstance(value, dict):
        return str(value.get("code") or value.get("account") or "").strip().lower()
    return str(value or "").strip().lower()


def _primary_accounts(report) -> set[str]:
    detail = report.detail or {}
    people = (detail.get("checkInput") or {}).get("people") or {}
    assigned = detail.get("assigned") or {}
    values = {
        _person_code(people.get("primaryTester1")),
        _person_code(people.get("primaryTester2")),
        _person_code(assigned.get("primaryTester1")),
        _person_code(assigned.get("primaryTester2")),
    }
    values.discard("")
    return values


def _task_revision(report) -> str:
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    project = project_for_report(report)
    payload = {
        "reportNo": report.report_no,
        "sampleNo": report.sample_no or "",
        "entrustNo": report.entrust_no or "",
        "status": report.status or "",
        "sampleStatus": report.sample_status or "",
        "client": report.client or "",
        "department": report.department or "",
        "project": {
            "id": project.id if project else None,
            "code": (
                project.display_code or project.number_code or project.code
                if project else ""
            ),
            "name": project.name if project else (report.project or report.project_name or ""),
        },
        "sample": {
            "name": str(raw.get("sampleName") or raw.get("name") or ""),
            "spec": str(raw.get("spec") or raw.get("model") or ""),
            "batchNo": str(raw.get("batchNo") or raw.get("factoryNo") or ""),
        },
        "standards": raw.get("testBases") or raw.get("testBasis") or [],
        "capabilityEntryIds": raw.get("capabilityEntryIds") or [],
        "manualCapabilityItems": raw.get("manualCapabilityItems") or [],
        "primaryAccounts": sorted(_primary_accounts(report)),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ensure_policy(report):
    policy = ElnTaskPolicy.query.filter_by(report_no=report.report_no).first()
    if policy:
        return policy
    project = project_for_report(report)
    if project is None:
        return None
    config = ElnProjectConfig.query.filter_by(project_id=project.id).first()
    if config is None or not config.enabled:
        return None
    audit_rows = [
        latest_operation_audit("report", report.report_no, "sample.out_warehouse.sign"),
        latest_operation_audit("report", report.report_no, "report.data_entry.save"),
    ]
    dates = [row.created_at for row in audit_rows if row and row.created_at]
    started = min(dates) if dates else None
    policy = ElnTaskPolicy(
        report_no=report.report_no,
        project_id=project.id,
        required=bool(config.apply_to_existing or (started and started >= config.effective_at)),
        config_version=config.config_version,
        required_templates=config.required_templates or [],
        min_finalized_records=max(1, int(config.min_finalized_records or 1)),
    )
    db.session.add(policy)
    db.session.flush()
    return policy


def eln_completion_error(report) -> str:
    """Return a blocker without advancing the formal report workflow."""

    if not current_app.config.get("ELN_ENABLED"):
        return ""
    policy = _ensure_policy(report)
    if policy is None or not policy.required:
        return ""
    records = ElnOriginalRecord.query.filter_by(
        report_no=report.report_no,
        status="FINALIZED",
        task_revision=_task_revision(report),
    ).all()
    required_codes = {
        str(value).strip() for value in (policy.required_templates or [])
        if str(value).strip()
    }
    found_codes = {
        template.code
        for template in (
            db.session.get(ElnRecordTemplate, row.template_id) for row in records
        )
        if template
    }
    missing = sorted(required_codes - found_codes)
    if missing:
        return "电子原始记录尚未完成必需模板审核：" + "、".join(missing)
    if len(records) < int(policy.min_finalized_records or 1):
        return f"电子原始记录需至少 {policy.min_finalized_records} 份审核通过，当前为 {len(records)} 份"
    return ""
