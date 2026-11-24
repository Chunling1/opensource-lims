"""Account-scoped search projection for the customer portal assistant.

The assistant is deliberately deterministic. It never connects a model to
the database and never returns an internal route. Callers must supply rows
that have already been filtered to the authenticated external account.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

_SPACE_RE = re.compile(r"\s+")
_FILLER_RE = re.compile(
    r"(?:请|麻烦|帮我|帮忙|我想|我要|需要|查一下|查询|搜索|找一下|找到|看看|查看|打开|进入|有关|相关)"
)
_INTENT_TERMS = {
    "scheme": ("检测", "服务", "方案", "项目", "标准", "报价", "样品", "对象"),
    "entrust": ("委托", "订单", "申请", "进度", "办理"),
    "document": ("报告", "证书", "文件", "下载", "交付"),
    "invoice": ("发票", "账单", "费用", "开票", "付款"),
    "shipment": ("物流", "快递", "运单", "寄送", "包裹"),
    "notification": ("通知", "消息", "动态", "提醒"),
}


def _text(value) -> str:
    return str(value or "").strip()


def _compact(value) -> str:
    return _SPACE_RE.sub("", _text(value).lower())


def _terms(query: str) -> list[str]:
    compact = _FILLER_RE.sub("", _compact(query))
    terms = [compact] if compact else []
    for kind, aliases in _INTENT_TERMS.items():
        if any(alias in compact for alias in aliases):
            terms.extend(aliases)
            terms.append(kind)
    terms.extend(compact[index:index + 2] for index in range(max(0, len(compact) - 1)))
    return list(dict.fromkeys(term for term in terms if term))


def _score(query: str, kind: str, identifier: str, fields: Iterable[object]) -> int:
    compact_query = _FILLER_RE.sub("", _compact(query))
    identifier_text = _compact(identifier)
    field_texts = [_compact(value) for value in fields if _text(value)]
    haystack = " ".join(field_texts)
    score = 0
    if compact_query and compact_query == identifier_text:
        score += 180
    elif compact_query and compact_query in identifier_text:
        score += 110
    if compact_query and compact_query in haystack:
        score += 80
    for term in _terms(query):
        if term == kind:
            score += 24
        elif term in identifier_text:
            score += 16
        elif term in haystack:
            score += 6
    return score


def _safe_notification_route(value: object, application_no: str) -> str:
    route = _text(value)
    if route.startswith("/account") or route.startswith("/reports/"):
        return route
    if application_no:
        return f"/account/entrusts/{application_no}"
    return "/account?view=notifications"


def search_customer_resources(
    query: str,
    *,
    schemes: Iterable[Mapping] = (),
    applications: Iterable[Mapping] = (),
    documents: Iterable[Mapping] = (),
    invoices: Iterable[Mapping] = (),
    shipments: Iterable[Mapping] = (),
    notifications: Iterable[Mapping] = (),
    limit: int = 20,
) -> list[dict]:
    """Return weighted, route-whitelisted results for one external account."""
    results: list[dict] = []

    def append(kind, identifier, title, subtitle, status, route, fields):
        score = _score(query, kind, identifier, [title, subtitle, status, *fields])
        if score <= 0:
            return
        results.append({
            "id": f"{kind}:{identifier}",
            "kind": kind,
            "title": _text(title),
            "subtitle": _text(subtitle),
            "status": _text(status),
            "route": route,
            "score": score,
        })

    for item in schemes:
        slug = _text(item.get("slug"))
        common_items = item.get("commonTestItems") if isinstance(item.get("commonTestItems"), list) else []
        item_names = [entry.get("name") for entry in common_items if isinstance(entry, Mapping)]
        standards = [
            f"{standard.get('code', '')} {standard.get('name', '')}"
            for entry in common_items if isinstance(entry, Mapping)
            for standard in (entry.get("standards") or []) if isinstance(standard, Mapping)
        ]
        append(
            "scheme", slug, item.get("objectName") or item.get("publicTitle"),
            " · ".join(filter(None, (_text(item.get("department")), _text(item.get("summary"))))),
            "可在线委托", f"/schemes/{slug}",
            [item.get("code"), item.get("category"), *item_names, *standards, *(item.get("qualificationTags") or [])],
        )

    for item in applications:
        number = _text(item.get("applicationNo"))
        form = item.get("formData") if isinstance(item.get("formData"), Mapping) else {}
        scheme = item.get("schemeSnapshot") if isinstance(item.get("schemeSnapshot"), Mapping) else {}
        append(
            "entrust", number,
            form.get("projectName") or scheme.get("objectName") or scheme.get("publicTitle") or "检测委托",
            f"{number} · {_text(form.get('sampleName'))}", item.get("status"),
            f"/account/entrusts/{number}",
            [item.get("internalEntrustNo"), form.get("companyName"), form.get("sampleName"), form.get("notes")],
        )

    for item in documents:
        identifier = _text(item.get("id") or item.get("documentNo") or item.get("reportNo"))
        append(
            "document", identifier, item.get("title") or "客户文件",
            " · ".join(filter(None, (_text(item.get("applicationNo")), _text(item.get("documentNo") or item.get("reportNo"))))),
            item.get("status"), "/account?view=documents",
            [item.get("kindLabel"), item.get("kind"), item.get("fileName"), item.get("reportNo")],
        )

    for item in invoices:
        identifier = _text(item.get("id") or item.get("invoiceNo") or item.get("billNo"))
        append(
            "invoice", identifier, item.get("invoiceNo") or item.get("billNo") or "发票办理",
            " · ".join(filter(None, (_text(item.get("applicationNo")), _text(item.get("invoiceType"))))),
            item.get("status"), "/account?view=billing",
            [item.get("entrustNo"), item.get("amountDue"), item.get("invoiceDate")],
        )

    for item in shipments:
        identifier = _text(item.get("id") or item.get("trackingNo"))
        append(
            "shipment", identifier, item.get("trackingNo") or "物流记录",
            " · ".join(filter(None, (_text(item.get("carrier")), _text(item.get("latestEvent"))))),
            item.get("statusLabel") or item.get("status"), "/account?view=shipping",
            [item.get("applicationNo"), item.get("shipmentType")],
        )

    for item in notifications:
        identifier = _text(item.get("id"))
        application_no = _text(item.get("applicationNo"))
        append(
            "notification", identifier, item.get("title") or "业务动态", item.get("content"),
            "未读" if not item.get("read") else "已读",
            _safe_notification_route(item.get("link"), application_no),
            [item.get("category"), application_no],
        )

    results.sort(key=lambda item: (-item["score"], item["kind"], item["id"]))
    return results[:max(1, min(int(limit or 20), 30))]
