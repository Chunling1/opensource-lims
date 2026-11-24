"""OAuth2 资源所有者密码模式（Resource Owner Password Credentials）的令牌签发与校验。

简化实现：登录用账号密码换取 JWT 访问令牌，业务接口用 Bearer 令牌鉴权。
"""
import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .models import User

try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:  # 未装 bcrypt 时回退旧 sha256（仅开发环境，生产部署装 bcrypt）
    _HAS_BCRYPT = False


def _legacy_hash(password: str) -> str:
    """旧方案：sha256 + 静态盐（快速哈希，已弃用，仅用于兼容校验与迁移）。"""
    return hashlib.sha256(("lims$" + password).encode("utf-8")).hexdigest()


def _bcrypt_input(password: str) -> bytes:
    """先 sha256 再 base64 再喂 bcrypt：规避 bcrypt 72 字节静默截断（中文/超长口令安全）。"""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    """新口令一律 bcrypt（每用户独立盐 + 慢哈希）；无 bcrypt 时回退 sha256。"""
    if _HAS_BCRYPT:
        return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode("utf-8")
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def verify_password(password: str, password_hash: str) -> bool:
    """兼容校验：bcrypt（$2 开头）走 bcrypt，旧 sha256 走静态盐比对。"""
    if not password_hash:
        return False
    if password_hash.startswith(("pbkdf2:", "scrypt:")):
        from werkzeug.security import check_password_hash
        return check_password_hash(password_hash, password)
    if password_hash.startswith("$2"):
        if not _HAS_BCRYPT:
            return False
        try:
            return bcrypt.checkpw(_bcrypt_input(password), password_hash.encode("utf-8"))
        except ValueError:
            return False
    return hmac.compare_digest(_legacy_hash(password), password_hash)


def needs_rehash(password_hash: str) -> bool:
    """旧 sha256 哈希在登录成功后应平滑升级为 bcrypt。"""
    if not password_hash:
        return False
    return _HAS_BCRYPT and not password_hash.startswith("$2")


def credential_version(user: User) -> str:
    """Opaque password-state binding; never expose the stored password hash."""
    import json
    material = json.dumps([user.id, user.account, user.password_hash], ensure_ascii=False).encode("utf-8")
    return hmac.new(current_app.config["JWT_SECRET"].encode("utf-8"), b"internal-credential-v1\0" + material, hashlib.sha256).hexdigest()


def credential_matches(user: User, version) -> bool:
    return isinstance(version, str) and len(version) == 64 and hmac.compare_digest(version, credential_version(user))


def authenticated_version(user: User) -> str:
    # Authentication/exchange captures the verified state before releasing its transaction.
    return getattr(user, "_authenticated_credential_version", None) or credential_version(user)


def token_user(payload):
    uid = payload.get("uid")
    if type(uid) is not int or uid < 1:
        return None
    user = User.query.get(uid)
    return user if user and user.enabled and not user.must_change_password and payload.get("sub") == user.account and credential_matches(user, payload.get("cv")) else None


def issue_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.account,
        "uid": user.id,
        "role": user.role_key,
        "cv": authenticated_version(user),
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["JWT_EXPIRES_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token: str):
    return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"code": 401, "message": "缺少访问令牌", "data": None}), 401
        try:
            payload = decode_token(header[7:])
        except jwt.ExpiredSignatureError:
            return jsonify({"code": 401, "message": "令牌已过期", "data": None}), 401
        except jwt.InvalidTokenError:
            return jsonify({"code": 401, "message": "无效令牌", "data": None}), 401
        user = token_user(payload)
        if not user or not user.enabled:
            return jsonify({"code": 401, "message": "用户不存在或已禁用", "data": None}), 401
        g.current_user = user
        if request.endpoint in {"entrust.query", "reports.query", "samples.query"}:
            from .request_validation import json_fields
            return json_fields("keyword", "status", "view", "startDate", "endDate", pagination=True)(fn)(*args, **kwargs)
        return fn(*args, **kwargs)

    return wrapper
