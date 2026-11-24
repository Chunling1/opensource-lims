"""Business-write guard used while a migrated environment is under acceptance.

The guard is deliberately enforced on the server.  The UI also hides or blocks
write actions, but that is only a usability aid and must never be the security
boundary.
"""

from __future__ import annotations

from flask import Flask, jsonify, request

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Several existing list/search APIs use POST because their filters are complex.
# These routes are read-only from a business-data perspective and must remain
# available during acceptance.  Authentication and AI calls may still append
# security/AI audit rows; they cannot change the inspection workflow itself.
READ_ONLY_POST_PATHS = {
    "/api/auth/login",
    "/api/eln/session/login",
    "/api/eln/session/exchange",
    "/api/eln/session/logout",
    "/api/entrust/query",
    "/api/finance/bills/query",
    "/api/samples/query",
    "/api/samples/entrust-preview",
    "/api/reports/query",
    "/api/reports/derivable",
    "/api/reports/cover-preview",
    "/api/reports/lib/standards",
    "/api/reports/lib/schemes",
    "/api/reports/lib/validate-sample",
    "/api/reports/lib/items",
    "/api/reports/lib/capability-items",
    "/api/exports/xlsx",
    "/api/public/v1/auth/login",
    "/api/public/v1/quotes/estimate",
}

READ_ONLY_POST_PREFIXES = (
    "/api/ai/",
    "/api/experiments/bim-cad/",
    "/api/public/v1/assistant/",
)


def request_is_business_read_only_safe(method: str, path: str) -> bool:
    normalized_method = method.upper()
    if normalized_method in SAFE_METHODS:
        return True
    if normalized_method != "POST":
        return False
    return path in READ_ONLY_POST_PATHS or path.startswith(READ_ONLY_POST_PREFIXES)


def install_business_read_only_guard(app: Flask) -> None:
    @app.before_request
    def reject_business_writes():
        if not app.config.get("APP_BUSINESS_READ_ONLY"):
            return None
        if request_is_business_read_only_safe(request.method, request.path):
            return None
        return jsonify({
            "code": "business_read_only",
            "message": "当前为信创迁移只读验收环境，业务保存、完成、审核、批准及流转操作已关闭",
            "data": {"businessReadOnly": True},
        }), 423
