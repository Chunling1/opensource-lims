"""Shared login policy. Passwords and CAPTCHA answers are never audit data."""
import base64
import hashlib
import hmac
import io
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, has_request_context, jsonify, request
from ...extensions import db

MAX_ATTEMPTS = 5
LOCK_MINUTES = 30
WINDOW_MINUTES = 15
POLICY_MESSAGE = "密码至少 8 位，必须包含大写英文、小写英文、数字和特殊字符"


class LoginFailureState(db.Model):
    __tablename__ = "login_failure_states"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    failures = db.Column(db.Text, nullable=False, default="[]")


class LoginEvent(db.Model):
    __tablename__ = "login_security_events"
    id = db.Column(db.Integer, primary_key=True)
    occurred_at = db.Column(db.DateTime, nullable=False, index=True, default=datetime.utcnow)
    account = db.Column(db.String(40), nullable=False)
    result = db.Column(db.String(40), nullable=False)
    channel = db.Column(db.String(40), nullable=False)
    peer_address = db.Column(db.String(64), nullable=False)


class LoginChallenge(db.Model):
    __tablename__ = "login_challenges"
    id = db.Column(db.String(48), primary_key=True)
    answer_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    peer_address = db.Column(db.String(64), nullable=False, index=True)
    consumed = db.Column(db.Boolean, nullable=False, default=False)


class LoginResetPlan(db.Model):
    __tablename__ = "login_reset_plans"
    id = db.Column(db.String(48), primary_key=True)
    actor_id = db.Column(db.Integer, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    target_ids = db.Column(db.Text, nullable=False)
    prepared = db.Column(db.Text, nullable=False, default="[]")
    applied_at = db.Column(db.DateTime)


def password_is_strong(value):
    return (isinstance(value, str) and 8 <= len(value) <= 128
            and any(c in string.ascii_uppercase for c in value)
            and any(c in string.ascii_lowercase for c in value)
            and any(c in string.digits for c in value)
            and any(c in string.punctuation for c in value))


def initial_password(account):
    # Temporary credentials only; all callers must require first-login change.
    if not isinstance(account, str) or not account:
        raise ValueError("生成初始密码需要账号")
    return account + str(10000 + secrets.randbelow(90000))


def clear_failures(user):
    state = db.session.get(LoginFailureState, user.id) if user.id else None
    if state:
        state.failures = "[]"
    user.failed_attempts = 0
    user.locked_until = None


def reset_initial_password(user, password=None):
    from ...security import hash_password
    password = password or initial_password(user.account)
    user.password_hash = hash_password(password)
    user.must_change_password = True
    clear_failures(user)
    return password


def is_locked(user):
    now = datetime.utcnow()
    if user.locked_until and user.locked_until > now:
        return True
    if user.locked_until:
        clear_failures(user)
    return False


def password_failure(user):
    """Caller must hold the User row lock until commit (all credential paths do)."""
    import json
    now = datetime.utcnow()
    state = db.session.get(LoginFailureState, user.id)
    if state is None:
        state = LoginFailureState(user_id=user.id, failures="[]")
        db.session.add(state)
    recent = [stamp for stamp in json.loads(state.failures)
              if datetime.fromisoformat(stamp) > now - timedelta(minutes=WINDOW_MINUTES)]
    recent.append(now.isoformat())
    state.failures = json.dumps(recent[-MAX_ATTEMPTS:])
    user.failed_attempts = len(recent)
    if len(recent) >= MAX_ATTEMPTS:
        user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
        return True
    return False


def prune_login_data():
    now = datetime.utcnow()
    LoginEvent.query.filter(LoginEvent.occurred_at < now - timedelta(days=30)).delete(synchronize_session=False)
    LoginChallenge.query.filter(LoginChallenge.expires_at < now).delete(synchronize_session=False)
    LoginResetPlan.query.filter(LoginResetPlan.expires_at < now).delete(synchronize_session=False)


def log_login(account, result):
    # Use the actual network peer. Untrusted forwarded headers are not evidence of a client IP.
    channel = request.path if has_request_context() else "internal"
    peer = request.remote_addr or "" if has_request_context() else ""
    db.session.add(LoginEvent(account=str(account or "")[:40], result=result,
                              channel=channel[:40], peer_address=peer[:64]))
    LoginEvent.query.filter(LoginEvent.occurred_at < datetime.utcnow() - timedelta(days=30)).delete(synchronize_session=False)


def _answer_hash(identifier, answer):
    return hmac.new(current_app.config["JWT_SECRET"].encode(),
                    ("captcha-v1:" + identifier + ":" + answer).encode(), hashlib.sha256).hexdigest()


def create_challenge():
    from PIL import Image, ImageDraw, ImageFont
    prune_login_data()
    peer = (request.remote_addr or "")[:64]
    # Retain consumed challenges until expiry too, so refresh/consume cannot bypass the issuance limit.
    if LoginChallenge.query.filter_by(peer_address=peer).count() >= 600:
        db.session.commit()
        return jsonify(code=429, message="验证码请求过多，请稍后再试", data=None), 429
    identifier = secrets.token_urlsafe(24)
    answer = "".join(secrets.choice(string.digits) for _ in range(6))
    canvas = Image.new("RGB", (180, 56), "#f2f6ff")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    for i, digit in enumerate(answer):
        glyph = Image.new("RGBA", (28, 44), (255, 255, 255, 0))
        # Scale the fallback bitmap font as well, so minimal servers remain readable.
        box = font.getbbox(digit)
        ink = Image.new("RGBA", (max(1, box[2]-box[0]), max(1, box[3]-box[1])), (255,255,255,0))
        ImageDraw.Draw(ink).text((-box[0], -box[1]), digit, font=font, fill="#18365e")
        glyph.paste(ink.resize((20, 32), Image.Resampling.LANCZOS), (4, 4))
        glyph = glyph.rotate(secrets.randbelow(25) - 12, resample=Image.Resampling.BICUBIC)
        canvas.paste(glyph, (5 + 28 * i, 5 + secrets.randbelow(5)), glyph)
    for _ in range(3):
        draw.line([(secrets.randbelow(180), secrets.randbelow(56)),
                   (secrets.randbelow(180), secrets.randbelow(56))], fill="#91a8c6", width=1)
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    db.session.add(LoginChallenge(id=identifier, answer_hash=_answer_hash(identifier, answer),
        expires_at=datetime.utcnow() + timedelta(minutes=2), peer_address=peer))
    db.session.commit()
    response = jsonify(code=0, message="ok", data={"captchaId": identifier,
        "image": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(), "expiresInSeconds": 120})
    response.headers["Cache-Control"] = "no-store"
    return response


def captcha_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(code=4, message="请输入图片中的数字验证码", data=None), 200
        if request.endpoint == 'auth.login' and not body.get('captchaVerification') and not body.get('captchaId'):
            from ...app_workspace import login_needs_captcha
            from ...models import User
            account = body.get('account')
            if isinstance(account, str):
                account = account.strip()
                # Hold the existing account lock through the password check on databases with row locking.
                User.query.filter_by(account=account).populate_existing().with_for_update().first()
                if not login_needs_captcha(account):
                    return fn(*args, **kwargs)
            return jsonify(code=4, message='上次登录未成功，请先完成安全验证', data={'captchaRequired': True}), 200
        if "captchaVerification" in body:
            from ...app_workspace import verify_aj_captcha
            failure = verify_aj_captcha(body)
            if failure is not None:
                return failure
            return fn(*args, **kwargs)
        identifier, answer = body.get("captchaId"), body.get("captcha")
        valid = False
        consumed = 0
        if isinstance(identifier, str) and len(identifier) <= 48 and isinstance(answer, str) and len(answer) <= 16:
            challenge = db.session.get(LoginChallenge, identifier)
            if challenge:
                expected, expires = challenge.answer_hash, challenge.expires_at
                # Conditional UPDATE is the cross-worker one-use boundary, even under races.
                consumed = LoginChallenge.query.filter_by(id=identifier, consumed=False).update({"consumed": True}, synchronize_session=False)
                db.session.commit()
                valid = (consumed == 1 and expires > datetime.utcnow()
                    and hmac.compare_digest(expected, _answer_hash(identifier, answer)))
        if not valid:
            if consumed:
                log_login(body.get("account") if isinstance(body.get("account"), str) else "", "captcha_rejected")
                db.session.commit()
            return jsonify(code=4, message="验证码错误或已过期，请刷新后重试", data=None), 200
        return fn(*args, **kwargs)
    return wrapped
