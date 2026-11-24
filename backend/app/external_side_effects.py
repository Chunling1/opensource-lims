"""Fail-closed guard for integrations that affect systems outside this deployment.

The writable verification platform owns an isolated business database, so normal
business writes remain available there. Only real cross-system integration
boundaries are disabled. AI inference and the local WPS conversion service are
deliberately not included because they do not push business state to the primary
platform or a third-party business system.
"""

from __future__ import annotations

import re

from flask import Flask, jsonify, request

from config_profiles.base import (
    ALLOWED_DEPLOYMENT_ROLES,
    DEPLOYMENT_ROLE_ERROR,
    default_environment_label,
)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_ELN_PREFIX = "/api/integrations/eln/v1"
_ESIGN_EXTERNAL_PATH = re.compile(
    r"^/api/esign/(?:tasks/(?:\d+/sign-url|batch-sign-url)|flows/\d+/(?:dispatch|positioning-url|cancel)|reports/[^/]+/organization-seal|callback)$"
)


def request_has_external_side_effect(method: str, path: str) -> bool:
    """Return whether a request crosses a guarded business integration boundary."""

    normalized_method = method.upper()
    if normalized_method in SAFE_METHODS:
        return False
    # ELN task reads remain available for diagnostics. Its mutating callbacks
    # are blocked, including any future non-GET endpoint under the same prefix.
    if path == _ELN_PREFIX or path.startswith(f"{_ELN_PREFIX}/"):
        return True
    return bool(normalized_method == "POST" and _ESIGN_EXTERNAL_PATH.fullmatch(path))


def validate_deployment_isolation(app: Flask) -> None:
    """Validate and normalize non-secret deployment identity settings."""

    role = str(
        app.config.get("DEPLOYMENT_ROLE") or "standard"
    ).strip().lower()
    if role not in ALLOWED_DEPLOYMENT_ROLES:
        raise RuntimeError(DEPLOYMENT_ROLE_ERROR)
    label = str(app.config.get("ENVIRONMENT_LABEL") or "").strip()
    if not label:
        label = default_environment_label(role)
    if len(label) > 80:
        raise RuntimeError("ENVIRONMENT_LABEL must not exceed 80 characters")
    app.config["DEPLOYMENT_ROLE"] = role
    app.config["ENVIRONMENT_LABEL"] = label
    if (
        role == "validation"
        and app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED")
    ):
        raise RuntimeError(
            "validation deployment forbids EXTERNAL_SIDE_EFFECTS_ENABLED"
        )


def install_external_side_effect_guard(app: Flask) -> None:
    @app.before_request
    def reject_external_side_effects():
        if request.method == "POST":
            match = re.fullmatch(r"/api/esign/(?:tasks|flows)/(\d+)/(?:sign-url|dispatch|positioning-url|cancel)", request.path)
            if match and int(match.group(1)) < int(app.config.get("ESIGN_PROVIDER_FLOW_MIN_ID") or 0):
                return jsonify({"code": "historical_esign_flow", "message": "该签署记录属于重新绑定之前，仅供历史查阅；请为新平台准备新的签署任务"}), 409
        if (app.config.get("ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED")
                and app.config.get("DEPLOYMENT_ROLE") != "validation"
                and _ESIGN_EXTERNAL_PATH.fullmatch(request.path)):
            return None
        if app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED"):
            return None
        if not request_has_external_side_effect(request.method, request.path):
            return None
        return jsonify({
            "code": "external_side_effects_disabled",
            "message": "当前部署已关闭真实外部推送和回调，请完成正式切流门禁后再执行该操作",
            "data": {
                "deploymentRole": app.config.get(
                    "DEPLOYMENT_ROLE", "standard"
                ),
                "externalSideEffectsEnabled": False,
            },
        }), 423
