"""Canonical internal-account authentication shared by all user interfaces."""

from __future__ import annotations

from datetime import datetime, timedelta

from ...extensions import db
from ...models import User
from ...security import hash_password, needs_rehash, verify_password, credential_version
from .login_security import clear_failures, is_locked, password_failure, log_login

MAX_ATTEMPTS = 5
LOCK_MINUTES = 30


def authenticate_internal_user(account: str, password: str):
    """Authenticate one enabled internal account and update lock counters."""

    if not isinstance(account, str) or not isinstance(password, str):
        return None, 1, "账号和密码格式无效"
    account = account.strip()
    provided = str(password or "")
    user = User.query.filter_by(account=account).populate_existing().with_for_update().first()
    invalid_message = "账号或密码错误"
    if not user or not user.enabled:
        log_login(account, "invalid_credentials")
        db.session.commit()
        return None, 1, invalid_message
    if is_locked(user):
        mins = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
        log_login(account, "locked")
        db.session.commit()
        return None, 2, f"密码错误次数过多，账号已锁定，请 {mins} 分钟后重试或联系管理员重置"
    if not verify_password(provided, user.password_hash):
        if password_failure(user):
            log_login(account, "password_locked")
            db.session.commit()
            return None, 2, "15 分钟内密码错误 5 次，账号已锁定 30 分钟，请联系管理员重置"
        log_login(account, "invalid_credentials")
        db.session.commit()
        return None, 1, invalid_message
    clear_failures(user)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(provided)
    user._authenticated_credential_version = credential_version(user)
    log_login(account, "first_login_required" if user.must_change_password else "success")
    db.session.commit()
    if user.must_change_password:
        return user, 3, "首次登录，请先在检测系统重置密码"
    return user, 0, "ok"
