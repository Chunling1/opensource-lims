"""Admin login audit and prepare/download/apply workflow for credential rotation."""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, g, jsonify, request
from ...extensions import db
from ...models import User
from ...security import credential_version, hash_password, require_auth
from ..audit import add_operation_audit
from .access import is_platform_administrator
from .login_security import LoginEvent, LoginResetPlan, clear_failures, initial_password, prune_login_data


def _response(data=None, message="ok", code=0, status=200):
    response = jsonify(code=code, message=message, data=data)
    response.headers["Cache-Control"] = "no-store"
    return response, status


def admin_only(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not is_platform_administrator(g.current_user):
            return _response(message="仅系统管理员可管理登录安全", code=403, status=403)
        if request.method != "GET" and current_app.config.get("APP_BUSINESS_READ_ONLY"):
            return _response(message="当前环境只读", code=403, status=403)
        return fn(*args, **kwargs)
    return wrapped


def register_security_admin(bp):
    @bp.get("/security/login-records")
    @require_auth
    @admin_only
    def login_records():
        try:
            page = max(1, min(100000, int(request.args.get("page", "1"))))
        except ValueError:
            return _response(message="页码无效", code=1)
        prune_login_data()
        db.session.commit()
        query = LoginEvent.query.filter(LoginEvent.occurred_at >= datetime.utcnow() - timedelta(days=30))
        account = request.args.get("account", "").strip()[:40]
        if account:
            query = query.filter(LoginEvent.account == account)
        count = query.count()
        rows = query.order_by(LoginEvent.id.desc()).offset((page - 1) * 50).limit(50).all()
        return _response({"total": count, "rows": [{"time": r.occurred_at.isoformat() + "Z",
            "account": r.account, "result": r.result, "channel": r.channel, "peerAddress": r.peer_address} for r in rows]})

    @bp.post("/security/reset-plan")
    @require_auth
    @admin_only
    def create_reset_plan():
        prune_login_data()
        # Creating a new plan supersedes unfinished plans from the same administrator.
        LoginResetPlan.query.filter_by(actor_id=g.current_user.id, applied_at=None).delete(synchronize_session=False)
        ids = [r.id for r in User.query.order_by(User.id).all()]
        plan = LoginResetPlan(id=secrets.token_urlsafe(24), actor_id=g.current_user.id,
            expires_at=datetime.utcnow() + timedelta(minutes=30), target_ids=json.dumps(ids), prepared="[]")
        db.session.add(plan)
        db.session.commit()
        return _response({"planId": plan.id, "total": len(ids), "expiresAt": plan.expires_at.isoformat() + "Z"})

    def current_plan(plan_id):
        return LoginResetPlan.query.filter_by(id=plan_id, actor_id=g.current_user.id, applied_at=None).filter(
            LoginResetPlan.expires_at > datetime.utcnow()).populate_existing().with_for_update().first()

    @bp.post("/security/reset-plan/<plan_id>/next")
    @require_auth
    @admin_only
    def prepare_reset_chunk(plan_id):
        plan = current_plan(plan_id)
        if plan is None:
            return _response(message="重置准备已过期，请重新生成", code=1)
        entries = json.loads(plan.prepared)
        if any(entry.get("format") != "account-digits5-v2" for entry in entries):
            return _response(message="初始密码规则已更新，请重新生成密码表", code=1)
        ids = json.loads(plan.target_ids)
        rows = []
        fingerprints = {entry["fingerprint"] for entry in entries}
        # Small batches keep password hashing inside ordinary proxy/worker timeouts.
        for uid in ids[len(entries):len(entries) + 10]:
            user = db.session.get(User, uid)
            if user is None:
                db.session.rollback()
                return _response(message="人员已变化，请重新生成", code=1)
            password = initial_password(user.account)
            fingerprint = hmac.new(current_app.config["JWT_SECRET"].encode(), password.encode(), hashlib.sha256).hexdigest()
            while fingerprint in fingerprints:
                password = initial_password(user.account)
                fingerprint = hmac.new(current_app.config["JWT_SECRET"].encode(), password.encode(), hashlib.sha256).hexdigest()
            fingerprints.add(fingerprint)
            entries.append({"id": uid, "version": credential_version(user), "hash": hash_password(password), "fingerprint": fingerprint, "format": "account-digits5-v2"})
            rows.append({"account": user.account, "name": user.name,
                "department": user.department.name if user.department else "", "enabled": bool(user.enabled),
                "initialPassword": password})
        plan.prepared = json.dumps(entries)
        db.session.commit()
        return _response({"rows": rows, "prepared": len(entries), "total": len(ids), "complete": len(entries) == len(ids)})

    @bp.post("/security/reset-plan/<plan_id>/apply")
    @require_auth
    @admin_only
    def apply_reset_plan(plan_id):
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or body.get("confirmation") != "SAVED_PASSWORD_TABLE":
            return _response(message="请先保存账号密码表，再确认重置", code=1)
        plan = current_plan(plan_id)
        if plan is None:
            return _response(message="重置准备已过期或已使用", code=1)
        entries, ids = json.loads(plan.prepared), json.loads(plan.target_ids)
        if any(entry.get("format") != "account-digits5-v2" for entry in entries):
            return _response(message="初始密码规则已更新，请重新生成密码表；本次未修改任何密码", code=1)
        users = User.query.order_by(User.id).populate_existing().with_for_update().all()
        if not is_platform_administrator(g.current_user) or not g.current_user.enabled or g.current_user.must_change_password:
            db.session.rollback()
            return _response(message="管理员登录状态已变化，请重新登录", code=403, status=403)
        if len(entries) != len(ids) or [u.id for u in users] != ids or any(
                e["id"] != u.id or e["version"] != credential_version(u) for e, u in zip(entries, users)):
            db.session.rollback()
            return _response(message="账号或密码已变化，请重新生成密码表；本次未修改任何密码", code=1)
        for entry, user in zip(entries, users):
            user.password_hash = entry["hash"]
            user.must_change_password = True
            clear_failures(user)
        plan.applied_at = datetime.utcnow()
        # The applied hashes are already in users; no reason to retain duplicate credential material.
        plan.prepared = "[]"
        add_operation_audit("organization.users.reset_all_passwords", "users", "all", category="security",
            after={"count": len(users), "mustChangePassword": True}, message="管理员批量重置；未保存明文密码")
        db.session.commit()
        return _response({"count": len(users)}, "全部初始密码已生效，请按已保存的表格分发；当前账号也需重新登录并改密")
