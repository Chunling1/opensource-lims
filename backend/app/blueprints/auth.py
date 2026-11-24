"""认证接口 — OAuth2 资源所有者密码模式：账号密码换 JWT，登录返回前端 AuthResponse 契约。"""
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request

from ..extensions import db
from ..models import User
from ..app_workspace import personal_details, register_workspace
from ..ui_preferences import ui_preferences, register_ui_preferences
from ..platform.identity import authenticate_internal_user
from ..security import (
    decode_token,
    token_user,
    hash_password,
    issue_token,
    needs_rehash,
    require_auth,
    verify_password,
)

from ..request_validation import json_fields
from ..platform.identity.login_security import (
    captcha_required, create_challenge, password_is_strong, POLICY_MESSAGE,
    clear_failures, is_locked, password_failure, log_login,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MAX_ATTEMPTS = 5
LOCK_MINUTES = 30


def _user_from_bearer():
    """有有效 Bearer 令牌则返回对应用户，否则 None（用于改密的登录态判定）。"""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = decode_token(header[7:])
    except Exception:
        return None
    return token_user(payload)


def _auth_payload(user: User):
    """对齐前端 src/services/auth.ts 的 AuthResponse 结构。"""
    from ..admin_corrections import can_correct_business_data
    from ..organization_privileges import has_full_platform_authority
    from ..workflow_hooks import empty_effective_roles as effective_roles
    from ..functions.esign_stages import prompt_available
    return {
        "account": user.account,
        "personal": personal_details(user),
        "uiPreferences": ui_preferences(user),
        "userName": user.name,
        "roleKey": user.role_key,
        "roleName": user.role_name,
        "homePath": user.home_path,
        "dataScope": user.data_scope(),
        "permissions": user.permission_codes(),
        "actionPermissions": user.action_codes(),
        "erpPermissions": effective_roles(user),
        # 功能开关由后端统一下发。关闭时前端不渲染入口，接口仍会二次拒绝，
        # 因此部署 AI 代码不会改变现有平台菜单和业务流程。
        "features": {
            "stageSigning": prompt_available(),
            "fullPlatformAuthority": has_full_platform_authority(user),
            "businessDataCorrection": can_correct_business_data(user),
            "aiAssistant": bool(
                current_app.config.get("AI_ENABLED")
                and current_app.config.get("AI_BASE_URL")
                and current_app.config.get("AI_API_KEY")
            ),
            "aiVoice": bool(
                current_app.config.get("AI_ENABLED")
                and current_app.config.get("AI_VOICE_ENABLED")
                and current_app.config.get("AI_BASE_URL")
                and current_app.config.get("AI_API_KEY")
            ),
            "bimCadExperiment": bool(
                current_app.config.get("BIM_CAD_EXPERIMENT_ENABLED")
            ),
            "businessReadOnly": bool(
                current_app.config.get("APP_BUSINESS_READ_ONLY")
            ),
            "deploymentRole": current_app.config.get(
                "DEPLOYMENT_ROLE", "standard"
            ),
            "environmentLabel": current_app.config.get(
                "ENVIRONMENT_LABEL", "开源标准版"
            ),
            "externalSideEffectsEnabled": bool(
                current_app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED")
            ),
        },
        # 扩展：项目授权（规格 2.1），前端忽略未知字段不影响兼容
        "projectPermissions": [
            {"project": ps.project.name, "step": ps.step_name} for ps in user.effective_project_steps()
        ],
    }


@bp.post("/login")
@json_fields("account", "password", "captchaId", "captcha")
@captcha_required
def login():
    data = request.get_json(silent=True) or {}
    account = (data.get("account") or "").strip()
    password = data.get("password") or ""
    user, code, message = authenticate_internal_user(account, password)
    if code:
        error_data = (
            {"mustChangePassword": True, "account": user.account}
            if code == 3 and user is not None
            else None
        )
        if code == 2:
            locked = User.query.filter_by(account=account).first()
            seconds = max(1, int((locked.locked_until-datetime.utcnow()).total_seconds())+1) if locked and locked.locked_until else LOCK_MINUTES*60
            error_data = {"retryAfterSeconds": seconds, "maxAttempts": MAX_ATTEMPTS}
        elif code == 1:
            checked = User.query.filter_by(account=account).first()
            if checked and checked.enabled:
                error_data = {"remainingAttempts": max(0,MAX_ATTEMPTS-(checked.failed_attempts or 0))}
        return jsonify({"code": code, "message": message, "data": error_data}), 200
    if user is None:
        current_app.logger.error("authentication succeeded without a user")
        return jsonify({"code": 1, "message": "登录状态异常，请稍后重试", "data": None}), 500
    token = issue_token(user)
    payload = _auth_payload(user)
    payload["token"] = token
    payload["tokenType"] = "Bearer"
    return jsonify({"code": 0, "message": "ok", "data": payload})


@bp.post("/change-password")
@json_fields("account", "oldPassword", "newPassword", "captchaId", "captcha")
def change_password():
    """首次登录/主动改密：校验旧密码后设置新密码，清除强制改密标记。

    鉴权：已登录用户改密以令牌内账号为准（忽略请求体 account，防止改他人口令）；
    有效登录态无需验证码；无令牌的首次登录改密仍需验证码，且仅限 must_change_password 账号。
    """
    auth_header = (request.headers.get("Authorization") or "").strip()
    user = _user_from_bearer()
    if user is None:
        if auth_header:
            return jsonify({"code": 401, "message": "未登录或登录态已失效", "data": None}), 200
        return captcha_required(_change_password)(None)
    return _change_password(user)


def _change_password(token_user):
    data = request.get_json(silent=True) or {}
    old = data.get("oldPassword") or ""
    new = data.get("newPassword") or ""
    if token_user is not None:
        user = User.query.filter_by(id=token_user.id).populate_existing().with_for_update().first()
    else:
        account = (data.get("account") or "").strip()
        user = User.query.filter_by(account=account).populate_existing().with_for_update().first()
        if not user or not user.enabled:
            return jsonify({"code": 1, "message": "账号不存在", "data": None}), 200
        if not user.must_change_password:
            return jsonify({"code": 401, "message": "请先登录后再修改密码", "data": None}), 200
    if is_locked(user):
        log_login(user.account, "change_locked")
        db.session.commit()
        return jsonify({"code": 2, "message": "账号锁定中，请稍后或联系管理员", "data": None}), 200
    # 原密码错误同样计入锁定，防止绕过登录锁定从改密接口无限爆破（与 /login 共用失败计数）
    if not verify_password(old, user.password_hash):
        if password_failure(user):
            log_login(user.account, "password_locked")
            db.session.commit()
            return jsonify({"code": 2, "message": f"原密码连续 {MAX_ATTEMPTS} 次错误，账号已锁定 {LOCK_MINUTES} 分钟", "data": None}), 200
        log_login(user.account, "change_wrong_password")
        db.session.commit()
        return jsonify({"code": 1, "message": "原密码错误", "data": None}), 200
    if not password_is_strong(new):
        return jsonify({"code": 1, "message": POLICY_MESSAGE, "data": None}), 200
    if new == old:
        return jsonify({"code": 1, "message": "新密码不能与原密码相同", "data": None}), 200
    user.password_hash = hash_password(new)
    user.must_change_password = False
    clear_failures(user)
    log_login(user.account, "password_changed")
    db.session.commit()
    return jsonify({"code": 0, "message": "密码已重置，请用新密码登录", "data": None})


@bp.get("/profile")
@require_auth
def profile():
    return jsonify({"code": 0, "message": "ok", "data": _auth_payload(g.current_user)})


@bp.get("/captcha")
def captcha():
    return create_challenge()


from ..platform.identity.security_admin import register_security_admin
register_security_admin(bp)


register_workspace(bp)
register_ui_preferences(bp)
