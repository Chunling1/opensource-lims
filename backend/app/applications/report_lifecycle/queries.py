"""Authorized read model for the report lifecycle.

HTTP, mobile, ELN and AI adapters must not import private helpers from the
reports Blueprint.  This module is the stable read boundary; it deliberately
preserves the production data-scope semantics while making the page and
project-step checks reusable.
"""

from __future__ import annotations
from app.organization_privileges import has_full_platform_authority

from ...extensions import db
from ...models import Report
from ...platform.audit import completion_owned_by, latest_operation_audit
from ...platform.identity import (
    has_function_permission,
    has_org_wide_business_scope,
    project_step_error,
)
from ...platform.workflow import (
    report_projection,
    sample_dispose_blocker,
    sample_matches_view,
    sample_return_stock_blocker,
)

REPORT_FEATURE_PERMISSIONS = frozenset(
    {
        "entrust.contract_review.view",
        "report.contract_review.view",
        "testing.data_entry.view",
        "testing.data_change.view",
        "report.review.view",
        "report.interim_report.view",
        "report.approval.view",
        "report.print.view",
        "report.archive.view",
        "report.release.view",
        "report.change_request.view",
        "report.query.view",
    }
)

REPORT_EDITABLE_STATUSES = frozenset(
    {"检测录入中", "待校核", "退回待重传", "检测更改中"}
)

REPORT_VIEW_STEP_RULES = {
    "contract_review": ("entrust_review", "合同评审"),
    "data_entry": ("data_entry", "检测数据录入"),
    "data_change": ("data_entry", "检测数据录入"),
    "review": ("report_review", "报告审核"),
    "interim_report": ("report_review", "报告审核"),
    "approval": ("report_approval", "报告批准"),
    "print": ("report_print", "报告签发"),
    "archive": ("report_archive", "报告归档"),
}

REPORT_ACTION_STEP_RULES = {
    "report.review": ("report_review", "报告审核"),
    "report.approval": ("report_approval", "报告批准"),
    "report.print": ("report_print", "报告签发"),
    "report.archive": ("report_archive", "报告归档"),
}

# Every full-detail read is bound to the page that opened it.  This allowlist
# prevents an adapter from widening a handling page to an arbitrary report
# query merely by supplying a made-up route name.
REPORT_DETAIL_VIEW_POLICIES = {
    "query": {"permissions": ("report.query.view",), "projection": "query"},
    "contract_review": {
        "permissions": ("entrust.contract_review.view",),
        "projection": "report",
        "step": ("entrust_review", "合同评审"),
    },
    "data_entry": {
        "permissions": ("testing.data_entry.view",),
        "projection": "report",
        "step": ("data_entry", "检测数据录入"),
    },
    "data_change": {
        "permissions": ("testing.data_change.view",),
        "projection": "report",
        "step": ("data_entry", "检测数据录入"),
    },
    "review": {
        "permissions": ("report.review.view",),
        "projection": "report",
        "step": ("report_review", "报告审核"),
    },
    "interim_report": {
        "permissions": ("report.interim_report.view",),
        "projection": "report",
        "step": ("report_review", "报告审核"),
    },
    "approval": {
        "permissions": ("report.approval.view",),
        "projection": "report",
        "step": ("report_approval", "报告批准"),
    },
    "print": {
        "permissions": ("report.print.view",),
        "projection": "report",
        "step": ("report_print", "报告签发"),
    },
    "archive": {
        "permissions": ("report.archive.view",),
        "projection": "report",
        "step": ("report_archive", "报告归档"),
    },
    "release": {"permissions": ("report.release.view",), "projection": "report"},
    "change_request": {
        "permissions": ("report.change_request.view",),
        "projection": "report",
    },
    # Read-only query pages keep full-lifecycle visibility, but each one still
    # requires its own exact feature permission and the normal data scope.
    "entrust_query": {
        "permissions": ("entrust.query.view",),
        "projection": "query",
    },
    "testing_task_query": {
        "permissions": ("testing.task_query.view",),
        "projection": "query",
    },
    "sample_flow_query": {
        "permissions": ("sample.flow_query.view",),
        "projection": "query",
    },
    "entrust_change": {
        "permissions": ("entrust.change.view",),
        "projection": "fixed",
        "statuses": frozenset({"委托更改中"}),
    },
    "sample_change": {
        "permissions": ("sample.change.view",),
        "projection": "fixed",
        "statuses": frozenset({"委托更改中"}),
    },
    "sample_register": {
        "permissions": ("entrust.sample_register.view",),
        "projection": "sample",
        "sample_view": "register",
    },
    "sample_inbound": {
        "permissions": ("sample.inbound.view",),
        "projection": "sample",
        "sample_view": "inbound",
        "step": ("sample_inbound", "样品入库"),
    },
    "sample_outbound": {
        "permissions": ("sample.outbound.view",),
        "projection": "sample",
        "sample_view": "outbound",
        "step": ("sample_outbound", "样品出库并领取"),
    },
    "sample_disposal": {
        "permissions": ("sample.disposal.view",),
        "projection": "sample_disposal",
    },
}

COMPLIANCE_STAGE_ACCESS = {
    "contract_review": (
        ("entrust.contract_review.view", "report.contract_review.view"),
        "entrust_review",
        "合同评审",
    ),
    "report_review": (("report.review.view",), "report_review", "报告审核"),
    "report_approval": (
        ("report.approval.view",),
        "report_approval",
        "报告批准",
    ),
}


def has_report_feature_access(user) -> bool:
    """Require a report-lifecycle page in addition to data scope."""

    from ...admin_corrections import can_correct_business_data
    return can_correct_business_data(user) or has_function_permission(user, *REPORT_FEATURE_PERMISSIONS)


def scoped_report_query(query, user):
    """Apply data scope without granting module or project-step permissions.

    Legacy ``authorization`` retains its status filter but must intersect the
    same explicit department scope. Organization-wide and self scope retain
    their existing precedence; no stored authorization records are rewritten.
    """

    query = query.filter(db.or_(Report.report_kind.is_(None), Report.report_kind != "correction_history"))
    scope_type = str(getattr(user, "data_scope_type", "") or "department")
    if scope_type == 'department_project':
        from ...platform.identity.department_project_scope import scoped_report_query as roster_scope
        if not has_org_wide_business_scope(user):
            return roster_scope(query, user)
    if has_org_wide_business_scope(user):
        return query
    if scope_type == "self":
        return query.filter(Report.owner == getattr(user, "name", ""))
    if scope_type == "authorization":
        query = query.filter(Report.status.in_(("待批准", "待打印")))
    names = list(user.data_department_names())
    return query.filter(Report.department.in_(names)) if names else query.filter(db.false())


def get_visible_report(user, report_no: str, *, require_feature: bool = True):
    """Return a report only when the current user can see its business data."""

    if require_feature and not has_report_feature_access(user):
        return None
    return scoped_report_query(Report.query, user).filter(
        Report.report_no == str(report_no or "")
    ).first()


def report_content_editable(report) -> bool:
    from ...functions.esign_stages import content_blocker
    if report and content_blocker(report):
        return False
    return bool(report and report.status in REPORT_EDITABLE_STATUSES)


def report_data_entry_step_error(user, report) -> str:
    """Re-check the project step on every report-content write."""

    return project_step_error(user, report, "data_entry", "检测数据录入")


def report_processing_step_error(user, report, view: str) -> str:
    """Return the missing project-step message for an active processing row.

    Query views and recall projections deliberately do not use this helper:
    query access is read-only within the data scope, while recall ownership is
    governed by the existing completion/undo policy.
    """

    # Seal confirmation is an explicit appointment independent of project
    # handling. Keep its existing data, approved-version and state checks;
    # this read exception must not grant report_print mutation rights.
    if view == "print" and has_function_permission(user, "report.print.view"):
        from ...esign_seal_confirmation import access_error as seal_access_error
        if not seal_access_error(user, report):
            return ""
    rule = REPORT_VIEW_STEP_RULES.get(str(view or ""))
    if not rule:
        return ""
    step_code, label = rule
    return project_step_error(user, report, step_code, label)


def report_detail_projection(
    report,
    view: str,
    *,
    allowed_actions=(),
    can_recall_sample_outbound: bool = False,
    can_dispose_sample: bool = False,
) -> str | None:
    """Return ``active``/``recall`` only when the record belongs to *view*.

    Recall ownership and audit ordering are resolved by the HTTP adapter and
    passed in as facts; the canonical state rules remain centralized here.
    """

    from ...admin_corrections import can_correct_business_data
    from ...report_delivery import delivery_released
    policy = REPORT_DETAIL_VIEW_POLICIES.get(str(view or ""))
    if not policy:
        return None
    kind = policy["projection"]
    if kind == "query":
        return "active"
    if kind == "report":
        # Visibility depends on workflow fields only. Building a full display row
        # would re-evaluate standards, seals and signatures for every candidate.
        row = {
            "status": report.status, "sampleStatus": report.sample_status,
            "sampleRegState": report.sample_reg_state or "登记完成",
            "archiveState": report.archive_state, "voided": report.voided,
            "distributionComplete": delivery_released(report),
            "dataStatus": report.to_row()['dataStatus'] if view == 'archive' and report.status == '待打印' else '',
            "hasInternalCorrectionHistory": bool((report.detail or {}).get("internalCorrectionRevision")),
        }
        row["allowedActions"] = list(allowed_actions or ())
        return report_projection(row, view)
    if kind == "sample":
        row = {}
        row["canRecallSampleOutbound"] = bool(can_recall_sample_outbound)
        sample_view = str(policy["sample_view"])
        if not sample_matches_view(report, row, sample_view):
            return None
        return (
            "recall"
            if sample_view == "outbound"
            and str(getattr(report, "status", "") or "") == "检测录入中"
            else "active"
        )
    if kind == "sample_disposal":
        return "active" if can_dispose_sample else None
    if kind == "fixed":
        statuses = policy.get("statuses")
        sample_statuses = policy.get("sample_statuses")
        if statuses is not None and str(
            getattr(report, "status", "") or ""
        ) not in statuses:
            return None
        if sample_statuses is not None and str(
            getattr(report, "sample_status", "") or ""
        ) not in sample_statuses:
            return None
        return "active"
    return None


def report_detail_access_error(user, report, view: str, projection: str | None) -> str:
    """Validate the exact feature, state projection and project step."""

    from ...admin_corrections import can_correct_business_data
    policy = REPORT_DETAIL_VIEW_POLICIES.get(str(view or ""))
    if not policy:
        return "报告详情入口无效"
    from ...admin_corrections import can_correct_business_data
    if view == "query" and can_correct_business_data(user):
        return ""
    permissions = tuple(policy.get("permissions") or ())
    if not has_function_permission(user, *permissions):
        return "无当前业务模块查看权限"
    if projection not in {"active", "recall"}:
        return "该记录当前不属于本业务模块"
    # Active handling belongs to the user's current project-step grant.  A
    # recall projection is different: it is owned by the completed action and
    # its audit trail.  Requiring the old project-step grant again would make a
    # legitimate undo disappear after a later authorization adjustment.
    step = policy.get("step")
    if step and projection == "active":
        if view in REPORT_VIEW_STEP_RULES:
            return report_processing_step_error(user, report, view)
        step_code, label = step
        return project_step_error(user, report, step_code, label)
    return ""


def report_allowed_actions(user, report, *, issuance_label=None) -> list[str]:
    """Return the existing active/recall action projection for one report.

    This lives at the application boundary so every adapter (detail, files,
    mobile) applies the same completion-owner rule instead of importing a
    private Blueprint helper.
    """

    granted = set(user.action_codes())
    is_admin = bool(
        has_full_platform_authority(user)
    )

    def allowed(code: str) -> bool:
        return bool(
            has_full_platform_authority(user)
            or code in granted
        )

    candidates: list[str] = []
    if report.status == "检测录入中" and data_entry_return_allowed(user, report):
        candidates.append("testing.data_entry.return")
    if report.status == "待审核":
        candidates.extend(("report.review.pass", "report.review.return"))
    if report.status == "待批准":
        candidates.extend(("report.approval.pass", "report.approval.return"))
    from ...report_delivery import delivery_released, RELEASE_ACTION, SEALED
    released = delivery_released(report)
    if report.status == '待打印' and issuance_label is None:
        from ...issuance_data_status import issuance_status
        issuance_label = issuance_status(report)
    sealed_pending = report.status == '待打印' and issuance_label == SEALED
    if report.status in {"待发放", "已发放"} or sealed_pending:
        if (report.archive_state or "") == "归档完成":
            if not released and has_function_permission(user, 'report.release.view'):
                candidates.append(RELEASE_ACTION)
            owned, _completion = completion_owned_by(
                user, "report", report.report_no, "report.archive.pass"
            )
            if not released and (owned or is_admin) and not project_step_error(
                user, report, "report_archive", "报告归档"
            ):
                candidates.append("report.archive.undo")
        else:
            candidates.append("report.archive.pass")

    undo = {
        "待样品入库": (
            "report.contract_review.undo",
            "report.contract_review.pass",
            True,
            "entrust_review",
            "合同评审",
        ),
        "待审核": (
            "report.report_check.undo",
            "report.data_entry.complete",
            True,
            "data_entry",
            "检测数据录入",
        ),
        "待批准": (
            "report.review.undo",
            "report.review.pass",
            True,
            "report_review",
            "报告审核",
        ),
        "待打印": (
            "report.approval.undo",
            "report.approval.pass",
            True,
            "report_approval",
            "报告批准",
        ),
        "待发放": (
            "report.print.undo",
            "report.print.pass",
            True,
            "report_print",
            "报告签发",
        ),
    }.get("待发放" if report.status == "已发放" else report.status)
    if (report.archive_state or "") == "归档完成":
        undo = None
    if undo and allowed(undo[0]):
        undo_code, completion_code, owner_only, step_code, label = undo
        owned, _completion = completion_owned_by(
            user, "report", report.report_no, completion_code
        )
        if (not owner_only or owned or is_admin) and not project_step_error(
            user, report, step_code, label
        ):
            candidates.append(undo_code)
    return [code for code in candidates if allowed(code) and not (
        code == "report.archive.pass"
        and project_step_error(user, report, "report_archive", "报告归档")
    )]


def data_entry_return_allowed(user, report) -> bool:
    """Project an active return only for a recorded handler of the task."""

    if (
        has_full_platform_authority(user)
    ):
        return True
    account = str(getattr(user, "account", "") or "").strip().lower()
    check_input = dict((report.detail or {}).get("checkInput") or {})
    people = dict(check_input.get("people") or {})
    recorded_accounts = {
        str(item.get("account") or item.get("code") or "").strip().lower()
        for item in (
            check_input.get("entryStaff") or {},
            people.get("primaryTester1") or {},
            people.get("primaryTester2") or {},
        )
        if isinstance(item, dict)
    }
    if account and account in recorded_accounts:
        return True
    return any(
        completion_owned_by(user, "report", report.report_no, action)[0]
        for action in (
            "report.data_entry.save",
            "sample.out_warehouse.sign",
            "sample.mobile.pickup.confirm",
        )
    )


def sample_outbound_recall_allowed(user, report) -> bool:
    """Mirror the desktop/mobile outbound recall projection."""

    from ...data_entry_state import report_data_entry_started
    started = report_data_entry_started(report)
    return bool(
        sample_return_stock_blocker(report, started) is None
        and (
            has_full_platform_authority(user)
            or "sample.return_stock" in user.action_codes()
        )
    )


def get_authorized_report_for_view(user, report_no: str, view: str):
    """Resolve one report through the exact page-context access policy.

    Returns ``(report, projection, error)``.  Feature permission is checked
    before the scoped lookup so callers do not reveal record existence.
    """

    from ...admin_corrections import can_correct_business_data
    policy = REPORT_DETAIL_VIEW_POLICIES.get(str(view or ""))
    if not policy:
        return None, None, "报告详情入口无效"
    if not (view == "query" and can_correct_business_data(user)) and not has_function_permission(user, *tuple(policy.get("permissions") or ())):
        return None, None, "无当前业务模块查看权限"
    report = scoped_report_query(Report.query, user).filter(
        Report.report_no == str(report_no or "")
    ).first()
    if report is None:
        return None, None, "报告不存在或不在数据范围内"
    projection = report_detail_projection(
        report,
        view,
        allowed_actions=report_allowed_actions(user, report),
        can_recall_sample_outbound=sample_outbound_recall_allowed(user, report),
        can_dispose_sample=sample_dispose_blocker(report) is None,
    )
    error = report_detail_access_error(user, report, view, projection)
    return report, projection, error


def compliance_stage_access_error(user, report, stage: str) -> str:
    policy = COMPLIANCE_STAGE_ACCESS.get(str(stage or ""))
    if not policy:
        return "合规核查阶段无效"
    permissions, step_code, label = policy
    if not has_function_permission(user, *permissions):
        return f"无{label}查看权限"
    return project_step_error(user, report, step_code, label)


__all__ = [
    "REPORT_EDITABLE_STATUSES",
    "REPORT_ACTION_STEP_RULES",
    "REPORT_DETAIL_VIEW_POLICIES",
    "COMPLIANCE_STAGE_ACCESS",
    "REPORT_FEATURE_PERMISSIONS",
    "REPORT_VIEW_STEP_RULES",
    "get_visible_report",
    "data_entry_return_allowed",
    "compliance_stage_access_error",
    "has_report_feature_access",
    "report_content_editable",
    "report_data_entry_step_error",
    "report_detail_access_error",
    "report_detail_projection",
    "get_authorized_report_for_view",
    "report_allowed_actions",
    "report_processing_step_error",
    "sample_outbound_recall_allowed",
    "scoped_report_query",
]
