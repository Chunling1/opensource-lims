"""Bounded customer directory search for every caller, including legacy forms."""
from flask import Blueprint, jsonify, request
from ..security import require_auth

bp = Blueprint("customers", __name__, url_prefix="/api/customers")

@bp.get("/search")
@require_auth
def search():
    from ..workflow_hooks import empty_customer_search as search_erp_customers
    kw = (request.args.get("keyword") or "").strip()
    paginated = "page" in request.args
    try:
        page = int(request.args.get("page", "1"))
        size = int(request.args.get("size", "20")) if paginated else min(max(int(request.args.get("limit") or 50), 1), 200)
        if page < 1 or not 1 <= size <= 200 or len(kw) > 200:
            raise ValueError()
    except ValueError:
        return jsonify({"code": 400, "message": "分页参数或查询关键词无效", "data": None}), 400
    try:
        data = search_erp_customers(kw, page, size)
    except RuntimeError:
        return jsonify({"code": 503, "message": "客户库暂时不可用，请重试", "data": None}), 503
    return jsonify({"code": 0, "message": "ok", "data": data if paginated else {"rows": data["rows"]}})
