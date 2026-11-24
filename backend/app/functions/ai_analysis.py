"""Permission-scoped, read-only business analysis for the AI workbench."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import or_

from ..platform.identity import denied_standard_item_ids, standard_matches_department
from ..extensions import db
from ..models import CapabilityEntry, Entrust, EquipmentItem, FinanceBill, Report, StdLibraryItem
from .ai_index import _ai_has_org_wide_scope, normalize, search

TEMPLATES = (
    {
        "id": "work_overview", "title": "我的待办与超期事项",
        "description": "汇总当前权限范围内的流程状态、到期和异常事项。",
        "prompt": "分析我当前可见的待办、超期和需要关注的业务",
        "permissions": {"report.query.view", "entrust.query.view"},
    },
    {
        "id": "entrust_progress", "title": "委托和样品整体进度",
        "description": "查看委托状态、样品状态和报告流程分布。",
        "prompt": "分析委托和样品整体进度",
        "permissions": {"entrust.query.view", "sample.flow_query.view", "report.query.view"},
    },
    {
        "id": "report_flow", "title": "报告流程分布",
        "description": "分析审核、批准、打印和发放等报告节点。",
        "prompt": "分析报告审核、批准、打印和发放情况",
        "permissions": {"report.query.view"},
    },
    {
        "id": "project_activity", "title": "项目近期业务情况",
        "description": "按项目汇总委托、样品和报告数量。",
        "prompt": "按项目分析最近业务情况",
        "permissions": {"entrust.query.view", "report.query.view"},
    },
    {
        "id": "standard_capability", "title": "标准与能力覆盖",
        "description": "汇总可见标准、授权类别和有效能力项目。",
        "prompt": "分析标准和能力项目覆盖情况",
        "permissions": {"quality.standard_library.view", "quality.standard_library_department.view"},
    },
    {
        "id": "equipment_calibration", "title": "设备校准与限制状态",
        "description": "查看设备可用、限制使用和近期校准到期情况。",
        "prompt": "分析设备校准到期和限制使用情况",
        "permissions": {"quality.equipment_ledger.view", "quality.equipment_ledger_department.view"},
    },
    {
        "id": "finance_overview", "title": "应收、开票和回款概况",
        "description": "汇总当前权限内的应收、实收、开票和未收金额。",
        "prompt": "分析应收、开票和回款概况",
        "permissions": {
            "finance.pricing.view", "finance.payment_registration.view",
            "finance.payment_confirmation.view", "finance.invoice.view",
            "finance.settlement.view", "finance.finance_reports.view",
            "finance.finance_statistics.view",
        },
    },
)


def available_templates(user) -> list[dict]:
    permissions = set(user.permission_codes())
    return [
        {key: value for key, value in item.items() if key != "permissions"}
        for item in TEMPLATES
        if permissions.intersection(item["permissions"])
    ]


def resolve_template(question: str) -> str:
    value = normalize(question)
    routes = (
        ("equipment_calibration", ("设备", "仪器", "校准", "检定")),
        ("standard_capability", ("标准", "能力", "cnas", "cma")),
        ("finance_overview", ("财务", "应收", "开票", "回款", "账单")),
        ("report_flow", ("报告", "审核", "批准", "打印", "发放")),
        ("entrust_progress", ("委托", "样品", "进度")),
        ("project_activity", ("项目", "方案")),
        ("work_overview", ("待办", "逾期", "超期", "异常")),
    )
    for template_id, keywords in routes:
        if any(normalize(keyword) in value for keyword in keywords):
            return template_id
    return ""


def _template(user, template_id: str) -> dict:
    allowed = {item["id"]: item for item in TEMPLATES if item["id"] in {row["id"] for row in available_templates(user)}}
    if template_id not in allowed:
        raise PermissionError("当前账号没有使用该分析模板所需的业务查看权限")
    return allowed[template_id]


def _scope(query, model, user):
    if _ai_has_org_wide_scope(user):
        return query
    department = user.department.name if user.department else ""
    if not department:
        return query.filter(db.false())
    column = getattr(model, "department", None)
    if column is None:
        column = getattr(model, "dept", None)
    return query.filter(column == department) if column is not None else query.filter(db.false())


def _apply_common_filters(query, model, filters: dict | None):
    filters = filters or {}
    statuses = [str(value)[:60] for value in (filters.get("statuses") or [])[:20] if str(value).strip()]
    if statuses and hasattr(model, "status"):
        query = query.filter(model.status.in_(statuses))
    project = str(filters.get("project") or "").strip()[:120]
    if project:
        columns = [
            column for column in (
                getattr(model, "project_name", None), getattr(model, "project", None)
            ) if column is not None
        ]
        if columns:
            query = query.filter(or_(*(column.contains(project) for column in columns)))
    return query


def _parse_day(value) -> date | None:
    try:
        return datetime.strptime(str(value or "")[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _counter_rows(counter: Counter, *, limit=20) -> list[dict]:
    return [
        {"label": str(label or "未标注"), "value": int(value)}
        for label, value in counter.most_common(limit)
    ]


def _metric(label: str, value, unit="", tone="default") -> dict:
    return {"label": label, "value": value, "unit": unit, "tone": tone}


def _indexed_sources(user, candidates: list[tuple[str, str]], maximum: int) -> list[dict]:
    rows = []
    seen = set()
    for entity_type, identifier in candidates:
        key = (entity_type, str(identifier or ""))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        found = search(user, key[1], 5, {"entityTypes": [entity_type]})
        exact = next((item for item in found if item["entityType"] == entity_type and item["entityId"] == key[1]), None)
        if exact:
            rows.append(exact)
        if len(rows) >= maximum:
            break
    return rows


def _report_rows(user, filters):
    if "report.query.view" not in set(user.permission_codes()):
        return []
    return _apply_common_filters(_scope(Report.query, Report, user), Report, filters).all()


def _entrust_rows(user, filters):
    if "entrust.query.view" not in set(user.permission_codes()):
        return []
    return _apply_common_filters(_scope(Entrust.query, Entrust, user), Entrust, filters).all()


def _report_analysis(user, filters, maximum):
    reports = _report_rows(user, filters)
    status_counts = Counter(row.status or "未标注" for row in reports)
    today = date.today()
    overdue = [row for row in reports if (_parse_day(row.deadline) or date.max) < today and row.status not in {"已发放", "已归档"}]
    pending = [row for row in reports if row.status not in {"已发放", "已归档", "已作废"} and not row.voided]
    sources = _indexed_sources(
        user,
        [("report", row.report_no) for row in [*overdue, *pending]][:maximum * 2],
        maximum,
    )
    return {
        "metrics": [
            _metric("报告总数", len(reports), "份"),
            _metric("办理中", len(pending), "份", "primary"),
            _metric("已超期", len(overdue), "份", "danger" if overdue else "default"),
            _metric("已发放", status_counts.get("已发放", 0), "份", "success"),
        ],
        "sections": [{"title": "报告节点分布", "kind": "bars", "rows": _counter_rows(status_counts)}],
        "sources": sources,
        "warnings": [f"发现 {len(overdue)} 份报告超过登记期限。"] if overdue else [],
        "followUps": ["查看超期报告明细", "按项目比较报告数量", "查看待审核和待批准报告"],
    }


def _entrust_analysis(user, filters, maximum):
    entrusts = _entrust_rows(user, filters)
    reports = _report_rows(user, filters)
    entrust_status = Counter(row.status or "未标注" for row in entrusts)
    sample_status = Counter(row.sample_status or "未标注" for row in reports)
    candidates = [("entrust", row.entrust_no or str(row.id)) for row in reversed(entrusts[-maximum:])]
    candidates.extend(("sample", row.sample_no or row.report_no) for row in reports[:maximum])
    return {
        "metrics": [
            _metric("委托总数", len(entrusts), "单"),
            _metric("样品总数", len(reports), "个"),
            _metric("委托办理中", sum(value for key, value in entrust_status.items() if "完成" not in key), "单", "primary"),
            _metric("待出入库", sum(value for key, value in sample_status.items() if "待" in key), "个", "warn"),
        ],
        "sections": [
            {"title": "委托状态", "kind": "bars", "rows": _counter_rows(entrust_status)},
            {"title": "样品流转状态", "kind": "bars", "rows": _counter_rows(sample_status)},
        ],
        "sources": _indexed_sources(user, candidates, maximum),
        "warnings": [],
        "followUps": ["查看办理中的委托", "查看待出库样品", "分析对应报告进度"],
    }


def _project_analysis(user, filters, maximum):
    reports = _report_rows(user, filters)
    entrusts = _entrust_rows(user, filters)
    counts = Counter((row.project_name or row.project or "未关联项目") for row in reports)
    counts.update((row.project_name or "未关联项目") for row in entrusts)
    top_names = {name for name, _value in counts.most_common(10)}
    sources = _indexed_sources(user, [
        ("report", row.report_no) for row in reports
        if (row.project_name or row.project or "未关联项目") in top_names
    ], maximum)
    return {
        "metrics": [
            _metric("涉及项目", len(counts), "个"),
            _metric("委托", len(entrusts), "单"),
            _metric("样品/报告", len(reports), "份"),
        ],
        "sections": [{"title": "项目业务量", "kind": "bars", "rows": _counter_rows(counts, limit=15)}],
        "sources": sources,
        "warnings": [],
        "followUps": ["筛选某个项目", "查看项目报告状态", "比较项目业务量"],
    }


def _standard_analysis(user, _filters, maximum):
    permissions = set(user.permission_codes())
    if not permissions.intersection({"quality.standard_library.view", "quality.standard_library_department.view"}):
        raise PermissionError("当前账号没有标准与能力查看权限")
    from ..applications.quality_resources.testing_locations import workbook_current_variants, workbook_capability_matches_items
    groups = workbook_current_variants()
    if _ai_has_org_wide_scope(user):
        standards = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all()
        capabilities = CapabilityEntry.query.filter(CapabilityEntry.active.is_(True)).all()
    else:
        department = user.department.name if user.department else ""
        denied = denied_standard_item_ids(user)
        standards = [
            row for row in StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all()
            if row.id not in denied and standard_matches_department(row, department)
        ]
        capabilities = [
            row for row in CapabilityEntry.query.filter(CapabilityEntry.active.is_(True)).all()
            if any(normalize(item.name) == normalize(department) for item in row.departments)
            and (row.standard_item_id in groups or row.standard_item_id is None or row.standard_item_id not in denied)
        ]
    from ..applications.quality_resources.testing_locations import workbook_retired_item_ids, workbook_capability_owners
    retired = workbook_retired_item_ids()
    capabilities = [row for row in capabilities if row.standard_item_id not in retired]
    allowed_ids = {row.id for row in standards}
    capabilities = [row for row in capabilities if workbook_capability_matches_items(row, groups, allowed_ids, date.today())]
    auth_counts = Counter(token for row in standards for token in (row.auth_kind or "未标注").replace("+", "、").split("、") if token)
    standard_ids = {row.standard_item_id for row in capabilities if row.standard_item_id}
    owners = workbook_capability_owners()
    linked_standard_ids = {row.id for row in standards if owners.get(row.id, row.id) in standard_ids}
    uncovered = [row for row in standards if row.id not in linked_standard_ids]
    candidates = [("standard", str(row.id)) for row in uncovered[:maximum]]
    candidates.extend(("capability", str(row.id)) for row in capabilities[:maximum])
    return {
        "metrics": [
            _metric("授权标准", len(standards), "项"),
            _metric("有效能力", len(capabilities), "项", "success"),
            _metric("有关联能力标准", len(linked_standard_ids), "项"),
            _metric("暂无能力关联", len(uncovered), "项", "warn" if uncovered else "default"),
        ],
        "sections": [{"title": "标准授权类别", "kind": "bars", "rows": _counter_rows(auth_counts)}],
        "sources": _indexed_sources(user, candidates, maximum),
        "warnings": [f"有 {len(uncovered)} 项可见标准暂未关联启用能力项目。"] if uncovered else [],
        "followUps": ["查看暂无能力关联的标准", "按场所查看能力项目", "查询某个标准编号"],
    }


def _equipment_analysis(user, _filters, maximum):
    permissions = set(user.permission_codes())
    if not permissions.intersection({"quality.equipment_ledger.view", "quality.equipment_ledger_department.view"}):
        raise PermissionError("当前账号没有设备台账查看权限")
    query = EquipmentItem.query.filter(EquipmentItem.deleted_at.is_(None))
    equipment = _scope(query, EquipmentItem, user).all()
    status_counts = Counter(row.effective_status() for row in equipment)
    today = date.today()
    upcoming = []
    for row in equipment:
        valid = _parse_day(row.valid_until or row.plan_cal_date)
        if valid and today <= valid <= today + timedelta(days=90) and row.period != "长期":
            upcoming.append((valid, row))
    upcoming.sort(key=lambda item: item[0])
    sources = _indexed_sources(user, [("equipment", str(row.id)) for _day, row in upcoming], maximum)
    return {
        "metrics": [
            _metric("设备总数", len(equipment), "台"),
            _metric("可用", status_counts.get("可用", 0), "台", "success"),
            _metric("限制使用", status_counts.get("限制使用", 0), "台", "danger" if status_counts.get("限制使用") else "default"),
            _metric("90天内到期", len(upcoming), "台", "warn" if upcoming else "default"),
        ],
        "sections": [{"title": "设备有效状态", "kind": "bars", "rows": _counter_rows(status_counts)}],
        "sources": sources,
        "warnings": [f"有 {len(upcoming)} 台设备将在 90 天内到期。"] if upcoming else [],
        "followUps": ["查看即将到期设备", "查看限制使用设备", "按科室查询设备"],
    }


def _money(value) -> Decimal:
    try:
        return Decimal(value or 0)
    except Exception:
        return Decimal(0)


def _finance_analysis(user, filters, maximum):
    finance_permissions = {code for code in user.permission_codes() if code.startswith("finance.") and code.endswith(".view")}
    broad = bool(finance_permissions.intersection({
        "finance.settlement.view", "finance.finance_reports.view",
        "finance.finance_statistics.view",
    }))
    can_due = broad or "finance.pricing.view" in finance_permissions
    can_received = broad or bool(finance_permissions.intersection({
        "finance.payment_registration.view", "finance.payment_confirmation.view",
    }))
    can_invoiced = broad or "finance.invoice.view" in finance_permissions
    if not any((can_due, can_received, can_invoiced)):
        raise PermissionError("当前账号没有财务查看权限")
    bills = _apply_common_filters(_scope(FinanceBill.query, FinanceBill, user), FinanceBill, filters).all()
    due = sum((_money(row.amount_due) for row in bills), Decimal(0))
    received = sum((_money(row.amount_received) for row in bills), Decimal(0))
    invoiced = sum((_money(row.amount_invoiced) for row in bills), Decimal(0))
    outstanding = sum((max(_money(row.amount_due) - _money(row.amount_received), Decimal(0)) for row in bills), Decimal(0))
    status_counts = Counter(row.status or "未标注" for row in bills)
    pending = sorted(bills, key=lambda row: max(_money(row.amount_due) - _money(row.amount_received), Decimal(0)), reverse=True)
    metrics = []
    if can_due:
        metrics.append(_metric("应收", f"{due:.2f}", "元"))
    if can_received:
        metrics.append(_metric("实收", f"{received:.2f}", "元", "success"))
    if can_invoiced:
        metrics.append(_metric("已开票", f"{invoiced:.2f}", "元"))
    if can_due and can_received:
        metrics.append(_metric("未收", f"{outstanding:.2f}", "元", "danger" if outstanding else "default"))
    warnings = []
    if can_due and can_received and outstanding:
        warnings.append(f"当前权限范围内未收金额为 {outstanding:.2f} 元。")
    return {
        "metrics": metrics,
        "sections": [{"title": "财务状态", "kind": "bars", "rows": _counter_rows(status_counts)}],
        "sources": _indexed_sources(user, [("finance", str(row.id)) for row in pending], maximum),
        "warnings": warnings,
        "followUps": ["查看未收金额较高的费用单", "查看待开票记录", "按项目汇总财务状态"],
    }


def run_analysis(user, template_id: str, filters: dict | None = None, maximum_sources=20) -> dict:
    template = _template(user, template_id)
    maximum = max(1, min(int(maximum_sources or 20), 20))
    if template_id in {"work_overview", "report_flow"}:
        result = _report_analysis(user, filters, maximum)
        if template_id == "work_overview":
            entrusts = _entrust_rows(user, filters)
            result["metrics"].insert(0, _metric("可见委托", len(entrusts), "单"))
    elif template_id == "entrust_progress":
        result = _entrust_analysis(user, filters, maximum)
    elif template_id == "project_activity":
        result = _project_analysis(user, filters, maximum)
    elif template_id == "standard_capability":
        result = _standard_analysis(user, filters, maximum)
    elif template_id == "equipment_calibration":
        result = _equipment_analysis(user, filters, maximum)
    elif template_id == "finance_overview":
        result = _finance_analysis(user, filters, maximum)
    else:
        raise ValueError("不支持的分析模板")
    result.update({
        "templateId": template_id,
        "title": template["title"],
        "summary": template["description"],
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "scopeLabel": "当前账号权限和部门范围",
        "readOnly": True,
    })
    return result


__all__ = ["available_templates", "resolve_template", "run_analysis"]
