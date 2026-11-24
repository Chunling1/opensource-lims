"""Portable, permission-safe search index for SQLite development and DM8 production."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import get_close_matches

from sqlalchemy import case, func

from ..platform.identity import (
    denied_standard_item_ids,
    has_org_wide_business_scope,
    project_for_report,
    standard_matches_department,
    user_has_project_step,
)
from ..extensions import db
from ..models import (
    AiIndexState,
    AiSearchDictionary,
    AiSearchDocument,
    AiSearchTerm,
    CapabilityEntry,
    Entrust,
    EquipmentItem,
    FinanceBill,
    OperationAudit,
    Project,
    Report,
    StdLibraryItem,
)

INDEX_KEY = "business"

DEFAULT_NAVIGATION = {
    "entrust": ("/inspection/entrust/query", "entrust.query.view", "委托查询"),
    "report": ("/inspection/report/query", "report.query.view", "报告查询"),
    "project": ("/inspection/system/custom_project", "system.custom_project.view", "检测项目自定义"),
    "sample": ("/inspection/sample/flow_query", "sample.flow_query.view", "样品流转查询"),
    "capability": ("/inspection/quality/standard_library", "quality.standard_library.view", "检测能力项目"),
}
ENTITY_LABELS = {
    "entrust": "委托", "sample": "样品", "report": "报告", "standard": "标准",
    "capability": "能力", "equipment": "设备",
    "project": "项目",
}
FINANCE_PERMISSIONS = {
    "finance.pricing.view", "finance.payment_registration.view",
    "finance.payment_confirmation.view", "finance.invoice.view",
    "finance.settlement.view", "finance.finance_reports.view",
    "finance.finance_statistics.view", "finance.account_refund.view",
}
PUBLIC_SEARCH_ENTITY_TYPES = {
    "entrust", "sample", "report", "standard", "capability", "equipment", "finance",
}
REPORT_NAVIGATION_INTENTS = (
    ("data_entry", ("检测数据录入", "数据录入", "录入数据"), "/inspection/testing/data_entry", "testing.data_entry.view", "data_entry", "检测数据录入"),
    ("contract_review", ("合同评审",), "/inspection/entrust/contract_review", "entrust.contract_review.view", "entrust_review", "合同评审"),
    ("review", ("报告审核", "审核报告", "审核模块"), "/inspection/report/review", "report.review.view", "report_review", "报告审核"),
    ("approval", ("报告批准", "批准报告", "批准模块"), "/inspection/report/approval", "report.approval.view", "report_approval", "报告批准"),
    ("print", ("报告签发", "电子签发", "签署报告"), "/inspection/report/print", "report.print.view", "report_print", "报告签发"),
    ("archive", ("报告归档", "归档报告", "归档模块"), "/inspection/report/archive", "report.archive.view", "report_archive", "报告归档"),
    ("query", ("报告查询", "查询模块"), "/inspection/report/query", "report.query.view", None, "报告查询"),
)
NAVIGATION_VERB = re.compile(r"(?:打开|进入|前往|去往|跳转(?:到|至)?|转到|办理|处理)")


def _ai_has_org_wide_scope(user) -> bool:
    """Reuse the authoritative explicit organization-wide business scope.

    `system.user.view` is an organization-management function permission, not
    authorization to search every department's business data.  Admin, the
    company root and an explicit ``data_scope_type=all`` grant remain valid.
    """
    return has_org_wide_business_scope(user)


def normalize(value) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).lower()).strip()


def terms(value) -> set[str]:
    text = normalize(value)
    result = set(re.findall(r"[a-z0-9][a-z0-9._/-]{1,159}", text))
    for block in re.findall(r"[\u3400-\u9fff]+", text):
        result.update(block if len(block) == 1 else (block[i:i + 2] for i in range(len(block) - 1)))
    return {token[:160] for token in result if token}


def _query_term_weights(value) -> dict[str, int]:
    """Expand a query with bounded, administrator-managed alias weights."""
    query = normalize(value)
    expanded = {token: 1 for token in terms(query)}
    if not query:
        return expanded
    for row in AiSearchDictionary.query.filter(AiSearchDictionary.active.is_(True)).all():
        aliases = [row.canonical, *(row.aliases or [])]
        if any(normalize(alias) and normalize(alias) in query for alias in aliases):
            for alias in aliases:
                for token in terms(alias):
                    expanded[token] = max(expanded.get(token, 1), max(1, min(int(row.weight or 1), 20)))
    return expanded


def _query_terms(value) -> set[str]:
    return set(_query_term_weights(value))


def _projection(entity_type, row):
    if entity_type == "entrust":
        return row.entrust_no or row.id, f"委托 {row.entrust_no or row.id}", [row.client, row.project_name, row.project_type], row.status, row.department, "/inspection/entrust/query"
    if entity_type == "report":
        return row.report_no, f"报告 {row.report_no}", [row.sample_no, row.client, row.project_name or row.project], row.status, row.department, "/inspection/report/query"
    if entity_type == "sample":
        sample_id = row.sample_no or row.report_no
        return sample_id, f"样品 {sample_id}", [row.report_no, row.entrust_no, row.client, row.project_name or row.project], row.sample_status or row.status, row.department, "/inspection/sample/flow_query"
    if entity_type == "project":
        department = row.department.name if row.department else ""
        return row.id, f"项目 {row.name}", [row.code, row.display_code, row.number_code, row.location], "启用" if row.active else "停用", department, "/inspection/system/custom_project"
    if entity_type == "standard":
        return row.id, f"标准 {row.code or ''}", [row.name, row.controlled_no, row.auth_kind, row.category, row.location], row.to_row()["status"], row.use_depts, "/inspection/quality/standard_library"
    if entity_type == "equipment":
        return row.id, f"设备 {row.archive_no or row.id}", [row.name, row.spec, row.factory_no, row.place], row.status, row.dept, "/inspection/quality/equipment_ledger"
    if entity_type == "capability":
        departments = ";".join(sorted({item.name for item in row.departments}))
        return row.id, f"能力 {row.item_name}", [row.standard_code, row.object_name, row.site, row.restriction], "已启用" if row.active else "未启用", departments, "/inspection/quality/standard_library"
    raise KeyError(entity_type)


SOURCES = {
    "entrust": Entrust, "report": Report, "sample": Report,
    "project": Project, "standard": StdLibraryItem,
    "capability": CapabilityEntry, "equipment": EquipmentItem,
}


def upsert(entity_type: str, row) -> bool:
    entity_id, title, summary_parts, status, department, route = _projection(entity_type, row)
    entity_id = str(entity_id)
    summary = " · ".join(str(value).strip() for value in summary_parts if value)
    # Resolve every lazy source relationship before a new required index row is
    # attached to the session. Otherwise loading CapabilityEntry.batch can
    # trigger an autoflush while content_hash is still unset.
    batch = getattr(row, "batch", None)
    source_updated_at = (
        getattr(row, "updated_at", None)
        or getattr(row, "created_at", None)
        or getattr(batch, "activated_at", None)
        or getattr(batch, "created_at", None)
    )
    digest = hashlib.sha256(json.dumps(
        [entity_type, entity_id, title, summary, status, department, route],
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    document = AiSearchDocument.query.filter_by(entity_type=entity_type, entity_id=entity_id).first()
    if document and document.content_hash == digest:
        return False
    if document is None:
        document = AiSearchDocument(entity_type=entity_type, entity_id=entity_id, created_at=datetime.utcnow())
        db.session.add(document)
    document.title, document.summary, document.status = title, summary, status or ""
    document.department, document.route = department or "", route
    document.source_updated_at = source_updated_at
    document.content_hash, document.updated_at = digest, datetime.utcnow()
    # Explicit ordering matters when historical source rows share a business
    # identifier: delete old terms before reinserting the last authoritative
    # projection, otherwise an autoflush can hit the per-document unique key.
    db.session.flush()
    AiSearchTerm.query.filter_by(document_id=document.id).delete(synchronize_session=False)
    db.session.flush()
    weighted = Counter()
    for token in terms(entity_id):
        weighted[token] += 12
    for token in terms(title):
        weighted[token] += 8
    for token in terms(summary):
        weighted[token] += 3
    for token in terms(status):
        weighted[token] += 2
    db.session.add_all(
        AiSearchTerm(document_id=document.id, term=token, weight=weight)
        for token, weight in weighted.items()
    )
    return True


def rebuild() -> dict:
    state = db.session.get(AiIndexState, INDEX_KEY) or AiIndexState(key=INDEX_KEY)
    db.session.add(state)
    state.last_started_at, state.last_error = datetime.utcnow(), None
    AiSearchTerm.query.delete(synchronize_session=False)
    AiSearchDocument.query.delete(synchronize_session=False)
    updated = 0
    for entity_type, model in SOURCES.items():
        query = model.query
        if hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at.is_(None))
        if entity_type == "capability":
            query = query.filter(CapabilityEntry.active.is_(True))
        for row in query.order_by(model.id).yield_per(250):
            updated += int(upsert(entity_type, row))
    state.last_audit_id = db.session.query(func.max(OperationAudit.id)).scalar() or 0
    state.rebuild_version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    state.backlog, state.last_finished_at = 0, datetime.utcnow()
    db.session.commit()
    return {
        "documents": AiSearchDocument.query.count(),
        "updatedProjections": updated,
        "lastAuditId": state.last_audit_id,
        "version": state.rebuild_version,
    }


def incremental(limit: int = 500) -> dict:
    state = db.session.get(AiIndexState, INDEX_KEY) or AiIndexState(key=INDEX_KEY)
    db.session.add(state)
    state.last_started_at, state.last_error = datetime.utcnow(), None
    rows = OperationAudit.query.filter(OperationAudit.id > (state.last_audit_id or 0)).order_by(OperationAudit.id).limit(limit).all()
    changed = 0
    aliases = {
        "entrust": ("entrust",),
        "report": ("report", "sample"),
        "project": ("project",), "standard": ("standard",),
        "capability_entry": ("capability",), "capability": ("capability",),
        "equipment": ("equipment",),
    }
    for audit in rows:
        entity_types = aliases.get(normalize(audit.object_type).replace(" ", "_"))
        if entity_types:
            primary_type = entity_types[0]
            model = SOURCES[primary_type]
            try:
                source_id = int(audit.object_id) if primary_type not in {"entrust", "report"} else None
            except ValueError:
                source_id = None
            if primary_type == "entrust":
                source = Entrust.query.filter_by(entrust_no=audit.object_id).first() or (
                    db.session.get(Entrust, int(audit.object_id))
                    if audit.object_id.isdigit()
                    else None
                )
            elif primary_type == "report":
                source = Report.query.filter_by(report_no=audit.object_id).first() or (
                    db.session.get(Report, int(audit.object_id))
                    if audit.object_id.isdigit()
                    else None
                )
            else:
                source = db.session.get(model, source_id) if source_id is not None else None
            if source is not None:
                for entity_type in entity_types:
                    changed += int(upsert(entity_type, source))
            else:
                # Delete only an exact projection key. When an audit stores a
                # database PK instead of the business identifier this is a
                # harmless no-op and the daily rebuild remains authoritative.
                for entity_type in entity_types:
                    stale = AiSearchDocument.query.filter_by(
                        entity_type=entity_type,
                        entity_id=str(audit.object_id or ""),
                    ).first()
                    if stale is not None:
                        db.session.delete(stale)
                        changed += 1
        state.last_audit_id = audit.id
    maximum = db.session.query(func.max(OperationAudit.id)).scalar() or 0
    state.backlog = max(0, maximum - (state.last_audit_id or 0))
    state.last_finished_at = datetime.utcnow()
    db.session.commit()
    return {"audits": len(rows), "changed": changed, "backlog": state.backlog, "lastAuditId": state.last_audit_id}


def _same_department(left: str, right: str) -> bool:
    """Fail closed on department boundaries while tolerating harmless spacing."""
    return bool(left and right) and normalize(left) == normalize(right)


def _source_for_document(document):
    """Reload the authoritative business row; an index row never grants access."""
    entity_id = str(document.entity_id or "")
    if document.entity_type == "entrust":
        source = Entrust.query.filter_by(entrust_no=entity_id).first()
        if source is None and entity_id.isdigit():
            source = db.session.get(Entrust, int(entity_id))
    elif document.entity_type == "report":
        source = Report.query.filter_by(report_no=entity_id).first()
    elif document.entity_type == "sample":
        source = Report.query.filter_by(sample_no=entity_id).first()
        if source is None:
            source = Report.query.filter_by(report_no=entity_id).first()
    elif document.entity_type == "finance":
        source = db.session.get(FinanceBill, int(entity_id)) if entity_id.isdigit() else None
    elif document.entity_type == "project":
        source = db.session.get(Project, int(entity_id)) if entity_id.isdigit() else None
    elif document.entity_type == "standard":
        source = db.session.get(StdLibraryItem, int(entity_id)) if entity_id.isdigit() else None
    elif document.entity_type == "capability":
        source = db.session.get(CapabilityEntry, int(entity_id)) if entity_id.isdigit() else None
    elif document.entity_type == "equipment":
        source = db.session.get(EquipmentItem, int(entity_id)) if entity_id.isdigit() else None
    else:
        return None
    if source is not None and getattr(source, "deleted_at", None) is not None:
        return None
    return source


def _source_department(document, source) -> str:
    if document.entity_type == "project":
        return source.department.name if source.department else ""
    if document.entity_type == "equipment":
        return source.dept or ""
    if document.entity_type == "capability":
        return ";".join(sorted({row.name for row in source.departments}))
    return getattr(source, "department", "") or ""


def _report_project(source):
    return project_for_report(source) if source else None


def _report_intent_access(user, source, query: str) -> tuple[bool, tuple | None, str]:
    """Authorize an explicit report-module request, with query fallback handled later."""
    intent = _report_navigation_intent(query)
    if intent is None:
        return False, None, ""
    _intent_name, _keywords, _route, permission, step_code, label = intent
    if permission not in set(user.permission_codes()):
        return False, intent, f"当前账号没有{label}权限"
    if step_code and not _ai_has_org_wide_scope(user):
        project = _report_project(source)
        if project is None or not user_has_project_step(user, project, step_code):
            return False, intent, f"当前账号没有该报告对应项目的{label}授权"
    return True, intent, ""


def _visible(user, document, query: str) -> bool:
    permissions = set(user.permission_codes())
    required = {
        "entrust": {"entrust.query.view"},
        "sample": {"sample.flow_query.view"},
        "project": {"system.custom_project.view"},
        "standard": {"quality.standard_library.view", "quality.standard_library_department.view"},
        "capability": {"quality.standard_library.view", "quality.standard_library_department.view"},
        "equipment": {"quality.equipment_ledger.view", "quality.equipment_ledger_department.view"},
    }.get(document.entity_type, set())
    if document.entity_type != "report" and not permissions.intersection(required):
        return False
    source = _source_for_document(document)
    if source is None:
        return False
    if document.entity_type == "capability" and not source.active:
        return False
    if document.entity_type == 'capability':
        from ..applications.quality_resources.testing_locations import workbook_retired_item_ids, workbook_current_variants, workbook_capability_matches_items
        if source.standard_item_id in workbook_retired_item_ids():
            return False
        groups = workbook_current_variants()
        workbook_source = source.standard_item_id in groups
        if workbook_source:
            wide = _ai_has_org_wide_scope(user)
            department = user.department.name if user.department else ''
            denied = set() if wide else denied_standard_item_ids(user)
            allowed_ids = {item.id for item in groups[source.standard_item_id]
                if item.id not in denied and (wide or standard_matches_department(item, department))}
            if not workbook_capability_matches_items(source, groups, allowed_ids, datetime.now().date()):
                return False
    from ..platform.identity.department_project_scope import uses_department_project_scope, report_is_visible
    if uses_department_project_scope(user) and document.entity_type in {'report', 'sample'}:
        department_allowed = report_is_visible(user, source)
    elif _ai_has_org_wide_scope(user):
        department_allowed = True
    else:
        # AI search deliberately uses the account's own department, not an
        # index projection or broader member/data grants. Source APIs still
        # perform their own authorization when the user opens a record.
        department = user.department.name if user.department else ""
        if not department:
            return False
        if document.entity_type == "standard":
            department_allowed = bool(
                source.id not in denied_standard_item_ids(user)
                and standard_matches_department(source, department)
            )
        elif document.entity_type == "capability":
            department_allowed = bool(
                source.active
                and any(_same_department(row.name, department) for row in source.departments)
                and (
                    workbook_source or source.standard_item_id is None
                    or source.standard_item_id not in denied_standard_item_ids(user)
                )
            )
        else:
            department_allowed = _same_department(_source_department(document, source), department)
    if not department_allowed:
        return False

    if document.entity_type != "report":
        return True

    # Ordinary report search is a report-query operation. Explicit workflow
    # navigation is separately authorized and may fall back to query access.
    intent_allowed, intent, _reason = _report_intent_access(user, source, query)
    if intent is not None and intent_allowed:
        return True
    return "report.query.view" in permissions


def _report_navigation_intent(query: str):
    normalized_query = normalize(query)
    if not NAVIGATION_VERB.search(normalized_query):
        return None
    for intent in REPORT_NAVIGATION_INTENTS:
        if any(normalize(keyword) in normalized_query for keyword in intent[1]):
            return intent
    return None


def _navigation_for(user, document, query: str) -> dict:
    """Return a server-authorized route; an index route is never trusted directly."""
    permissions = set(user.permission_codes())
    if document.entity_type == "report":
        source = _source_for_document(document)
        intent_allowed, intent, denied_reason = _report_intent_access(user, source, query)
        if intent is not None and intent_allowed:
            intent_name, _keywords, route, permission, step_code, label = intent
            return {
                "route": route, "routePermission": permission,
                "routeDeniedReason": "", "navigationIntent": intent_name,
            }
        if intent is not None and "report.query.view" in permissions:
            return {
                "route": "/inspection/report/query", "routePermission": "report.query.view",
                "routeDeniedReason": f"{denied_reason}，已按普通报告查询打开",
                "navigationIntent": "fallback_query",
            }

    if document.entity_type in {"standard", "capability"}:
        choices = (
            ("/inspection/quality/standard_library", "quality.standard_library.view", "检测标准基础信息库"),
            ("/inspection/quality/standard_library_department", "quality.standard_library_department.view", "检测标准基础信息库【科室】"),
        )
    elif document.entity_type == "equipment":
        choices = (
            ("/inspection/quality/equipment_ledger", "quality.equipment_ledger.view", "设备台账"),
            ("/inspection/quality/equipment_ledger_department", "quality.equipment_ledger_department.view", "设备台账【科室】"),
        )
    elif document.entity_type == "finance":
        choices = (
            ("/inspection/finance/pricing", "finance.pricing.view", "计价管理"),
            ("/inspection/finance/payment_registration", "finance.payment_registration.view", "收款登记"),
            ("/inspection/finance/payment_confirmation", "finance.payment_confirmation.view", "收款确认"),
            ("/inspection/finance/invoice", "finance.invoice.view", "发票管理"),
            ("/inspection/finance/settlement", "finance.settlement.view", "结算管理"),
            ("/inspection/finance/finance_reports", "finance.finance_reports.view", "财务报表"),
            ("/inspection/finance/finance_statistics", "finance.finance_statistics.view", "财务统计"),
            ("/inspection/finance/account_refund", "finance.account_refund.view", "账户退款处理"),
        )
    else:
        default = DEFAULT_NAVIGATION.get(document.entity_type)
        choices = (default,) if default else ()

    for route, permission, _label in choices:
        if permission in permissions:
            return {
                "route": route, "routePermission": permission,
                "routeDeniedReason": "", "navigationIntent": "default",
            }
    if choices:
        _route, permission, label = choices[0]
        return {
            "route": "", "routePermission": permission,
            "routeDeniedReason": f"当前账号没有{label}权限",
            "navigationIntent": "default",
        }
    return {
        "route": "", "routePermission": "",
        "routeDeniedReason": "当前记录没有可用的安全入口",
        "navigationIntent": "default",
    }


def _filter_values(filters: dict | None, key: str, allowed: set[str] | None = None) -> set[str]:
    raw = (filters or {}).get(key) or []
    if not isinstance(raw, list):
        return set()
    values = {normalize(value) for value in raw[:20] if str(value or "").strip()}
    return values.intersection(allowed) if allowed is not None else values


def _matches_filters(document, source, filters: dict | None) -> bool:
    if not filters:
        return True
    entity_types = _filter_values(filters, "entityTypes", PUBLIC_SEARCH_ENTITY_TYPES)
    if entity_types and document.entity_type not in entity_types:
        return False
    statuses = _filter_values(filters, "statuses")
    _entity_id, title, summary_parts, status_value, _department, _route = _projection(document.entity_type, source)
    if statuses and normalize(status_value) not in statuses:
        return False
    project = normalize((filters or {}).get("project") or "")
    searchable = normalize(" ".join([title, *(str(value or "") for value in summary_parts)]))
    if project and project not in searchable:
        return False
    updated = document.source_updated_at or document.updated_at
    for key, is_start in (("dateFrom", True), ("dateTo", False)):
        raw = str((filters or {}).get(key) or "").strip()[:10]
        if not raw:
            continue
        try:
            boundary = datetime.fromisoformat(raw)
            if not is_start:
                boundary = boundary.replace(hour=23, minute=59, second=59)
        except ValueError:
            continue
        if updated is None or (is_start and updated < boundary) or (not is_start and updated > boundary):
            return False
    return True


def _match_metadata(query: str, entity_id: str, title: str, summary: str, status_value: str, department: str) -> dict:
    query_value = normalize(query)
    query_tokens = terms(query_value)
    fields = {
        "businessNumber": entity_id,
        "title": title,
        "summary": summary,
        "status": status_value,
        "department": department,
    }
    matched_fields = []
    matched_terms = set()
    for key, value in fields.items():
        normalized_value = normalize(value)
        overlap = {token for token in query_tokens if token in normalized_value}
        if overlap or (query_value and query_value in normalized_value):
            matched_fields.append(key)
            matched_terms.update(overlap)
    exact = bool(entity_id and normalize(entity_id) == query_value)
    if exact:
        reason = "完整业务编号精确匹配"
    elif "businessNumber" in matched_fields:
        reason = "业务编号匹配"
    elif "title" in matched_fields:
        reason = "标题与业务术语匹配"
    elif "status" in matched_fields:
        reason = "状态匹配"
    else:
        reason = "业务摘要关键词匹配"
    return {
        "exactMatch": exact,
        "matchedFields": matched_fields,
        "matchedTerms": sorted(matched_terms, key=lambda item: (-len(item), item))[:12],
        "matchReason": reason,
    }


def _document_result(user, document, source, query: str, score: int) -> dict:
    entity_id, title, summary_parts, status_value, department, _route = _projection(document.entity_type, source)
    summary = " · ".join(str(value).strip() for value in summary_parts if value)
    navigation = _navigation_for(user, document, query)
    return {
        "id": f"{document.entity_type}:{entity_id}",
        "entityType": document.entity_type,
        "entityLabel": ENTITY_LABELS.get(document.entity_type, document.entity_type),
        "entityId": str(entity_id),
        "title": title,
        "summary": summary,
        "status": status_value or "",
        "department": department or "",
        **navigation,
        "score": int(score or 0),
        "updatedAt": (
            document.source_updated_at or document.updated_at
        ).isoformat(timespec="seconds") if (document.source_updated_at or document.updated_at) else "",
        **_match_metadata(query, str(entity_id), title, summary, status_value or "", department or ""),
    }


def reauthorize_results(user, rows: list[dict], *, read_only=True) -> list[dict]:
    """Reload every cited result immediately before it leaves the server.

    Search-index rows and an earlier permission decision are never treated as
    durable authorization.  Citations deliberately resolve to the ordinary
    read-only destination, even when the user's question contains a workflow
    action phrase.
    """
    authorized = []
    seen = set()
    for original_number, item in enumerate(rows[:50], start=1):
        entity_type = str(item.get("entityType") or "")
        entity_id = str(item.get("entityId") or "")
        key = (entity_type, entity_id)
        if not entity_type or not entity_id or key in seen:
            continue
        seen.add(key)
        document = AiSearchDocument.query.filter_by(
            entity_type=entity_type, entity_id=entity_id,
        ).first()
        authorization_query = "" if read_only else str(item.get("query") or "")
        if document is None or not _visible(user, document, authorization_query):
            continue
        source = _source_for_document(document)
        if source is None:
            continue
        refreshed = _document_result(
            user, document, source, authorization_query, int(item.get("score") or 0),
        )
        refreshed["_citationNumber"] = original_number
        if read_only and entity_type == "report":
            refreshed.update({
                "route": "/inspection/report/query",
                "routePermission": "report.query.view",
                "routeDeniedReason": "",
                "navigationIntent": "citation_read_only",
            })
        authorized.append(refreshed)
    return authorized


def _correction_suggestions(query: str) -> list[str]:
    normalized = normalize(query)
    if not normalized or len(normalized) > 80:
        return []
    vocabulary = []
    for row in AiSearchDictionary.query.filter(AiSearchDictionary.active.is_(True)).all():
        vocabulary.extend(str(value).strip() for value in [row.canonical, *(row.aliases or [])] if str(value).strip())
    by_normalized = {normalize(value): value for value in vocabulary if normalize(value)}
    return [by_normalized[value] for value in get_close_matches(normalized, list(by_normalized), n=3, cutoff=0.58)]


def search(user, query: str, limit: int = 20, filters: dict | None = None) -> list[dict]:
    try:
        result_limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        result_limit = 20
    token_weights = dict(list(_query_term_weights(query).items())[:40])
    tokens = list(token_weights)
    if not tokens:
        return []
    score_query = (db.session.query(
        AiSearchTerm.document_id.label("document_id"),
        func.sum(
            AiSearchTerm.weight * case(token_weights, value=AiSearchTerm.term, else_=1)
        ).label("score"),
    ).filter(AiSearchTerm.term.in_(tokens)).group_by(AiSearchTerm.document_id).subquery())
    scored_query = (db.session.query(AiSearchDocument, score_query.c.score)
        .join(score_query, score_query.c.document_id == AiSearchDocument.id)
        .order_by(score_query.c.score.desc(), AiSearchDocument.updated_at.desc()))
    query_value = normalize(query)
    from ..platform.identity.department_project_scope import uses_department_project_scope, appointed_project_ids, visible_department_names
    roster_departments = []
    if uses_department_project_scope(user):
        roster_departments = [p.department.name for p in Project.query.filter(Project.id.in_(appointed_project_ids(user))).all() if p.department]
        roster_departments = list(set(roster_departments) | visible_department_names(user))
    candidate_scope = db.or_(
        AiSearchDocument.department == (user.department.name if user.department else ''),
        db.and_(AiSearchDocument.entity_type.in_(('report', 'sample')), AiSearchDocument.department.in_(roster_departments)),
    )
    prefix_rows = []
    if re.fullmatch(r"[a-z0-9][a-z0-9._/-]{2,79}", query_value):
        escaped_prefix = query_value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        prefix_query = AiSearchDocument.query.filter(
            func.lower(AiSearchDocument.entity_id).like(f"{escaped_prefix}%", escape="\\")
        )
        if not _ai_has_org_wide_scope(user):
            prefix_query = prefix_query.filter(candidate_scope)
        prefix_rows = [(document, 10000) for document in prefix_query.order_by(AiSearchDocument.updated_at.desc()).limit(50).all()]
    if not _ai_has_org_wide_scope(user):
        department = user.department.name if user.department else ""
        if not department:
            return []
        # Keep local business rows and standards in separate bounded pools.
        # Otherwise a large standard library (which needs row-level checks)
        # can crowd every permitted report out of the candidate window.
        local_rows = scored_query.filter(
            candidate_scope,
            ~AiSearchDocument.entity_type.in_(("standard", "capability")),
        ).limit(250).all()
        standard_rows = scored_query.filter(
            AiSearchDocument.entity_type.in_(("standard", "capability"))
        ).limit(300).all()
        scored_by_id = {
            document.id: (document, score)
            for document, score in [*local_rows, *standard_rows, *prefix_rows]
        }
        scored = sorted(
            scored_by_id.values(),
            key=lambda pair: (
                int(pair[1] or 0),
                pair[0].updated_at or datetime.min,
            ),
            reverse=True,
        )
    else:
        scored_by_id = {
            document.id: (document, score)
            for document, score in [*scored_query.limit(200).all(), *prefix_rows]
        }
        scored = sorted(
            scored_by_id.values(),
            key=lambda pair: (int(pair[1] or 0), pair[0].updated_at or datetime.min),
            reverse=True,
        )
    result = []
    for document, score in scored:
        if not _visible(user, document, query):
            continue
        source = _source_for_document(document)
        if source is None or not _matches_filters(document, source, filters):
            continue
        result.append(_document_result(user, document, source, query, int(score or 0)))
        if len(result) >= 50:
            break
    result.sort(key=lambda row: (
        bool(row["exactMatch"]), int(row["score"]), row["updatedAt"], row["id"]
    ), reverse=True)
    return result[:result_limit]


def search_response(user, query: str, filters: dict | None = None, page_size: int = 20, cursor=None) -> dict:
    try:
        size = max(1, min(int(page_size), 30))
    except (TypeError, ValueError):
        size = 20
    try:
        offset = max(0, min(int(cursor or 0), 40))
    except (TypeError, ValueError):
        offset = 0
    candidates = search(user, query, 50, filters)
    page = candidates[offset:offset + size]
    next_cursor = str(offset + size) if offset + size < len(candidates) else ""
    entity_counts = Counter(row["entityType"] for row in candidates)
    status_counts = Counter(row["status"] for row in candidates if row["status"])
    return {
        "items": page,
        "nextCursor": next_cursor,
        "totalApprox": len(candidates),
        "facets": {
            "entityTypes": [
                {"value": key, "label": ENTITY_LABELS.get(key, key), "count": value}
                for key, value in sorted(entity_counts.items())
            ],
            "statuses": [
                {"value": key, "label": key, "count": value}
                for key, value in status_counts.most_common(20)
            ],
        },
        "queryInterpretation": {
            "normalized": normalize(query),
            "expandedTerms": sorted(_query_terms(query))[:30],
            "correctionSuggestions": _correction_suggestions(query),
            "scope": "当前账号权限和部门范围",
        },
    }


def status() -> dict:
    state = db.session.get(AiIndexState, INDEX_KEY)
    maximum = db.session.query(func.max(OperationAudit.id)).scalar() or 0
    count = AiSearchDocument.query.count()
    return {"documents": count, "lastAuditId": state.last_audit_id if state else 0,
        "backlog": max(0, maximum - (state.last_audit_id if state else 0)),
        "rebuildVersion": state.rebuild_version if state else "", "lastError": state.last_error if state else "",
        "lastFinishedAt": state.last_finished_at.isoformat(timespec="seconds") if state and state.last_finished_at else ""}
