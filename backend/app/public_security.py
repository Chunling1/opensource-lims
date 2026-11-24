"""Authentication boundary for external customer accounts."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .models import ExternalAccount


def issue_external_token(account: ExternalAccount) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": account.account,
        "external_uid": account.id,
        "actor": "external",
        "iss": current_app.config["PUBLIC_JWT_ISSUER"],
        "aud": current_app.config["PUBLIC_JWT_AUDIENCE"],
        "iat": now,
        "exp": now + timedelta(
            seconds=current_app.config["PUBLIC_JWT_EXPIRES_SECONDS"]
        ),
    }
    return jwt.encode(
        payload, current_app.config["PUBLIC_JWT_SECRET"], algorithm="HS256"
    )


def decode_external_token(token: str):
    payload = jwt.decode(
        token,
        current_app.config["PUBLIC_JWT_SECRET"],
        algorithms=["HS256"],
        issuer=current_app.config["PUBLIC_JWT_ISSUER"],
        audience=current_app.config["PUBLIC_JWT_AUDIENCE"],
        options={"require": ["sub", "external_uid", "actor", "iss", "aud", "iat", "exp"]},
    )
    if payload.get("actor") != "external":
        raise jwt.InvalidTokenError("invalid external actor")
    return payload


def require_external_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"code": 401, "message": "缺少外部客户访问令牌", "data": None}), 401
        try:
            payload = decode_external_token(header[7:])
        except jwt.ExpiredSignatureError:
            return jsonify({"code": 401, "message": "登录已过期", "data": None}), 401
        except jwt.InvalidTokenError:
            return jsonify({"code": 401, "message": "无效的外部客户令牌", "data": None}), 401
        account = db_get_external_account(payload.get("external_uid"))
        if not account or not account.enabled or account.account != payload.get("sub"):
            return jsonify({"code": 401, "message": "外部客户账号不存在或已停用", "data": None}), 401
        g.external_account = account
        return fn(*args, **kwargs)

    return wrapper


def db_get_external_account(identifier):
    try:
        return ExternalAccount.query.get(int(identifier))
    except (TypeError, ValueError):
        return None
