"""Subproject catalog and explicit local eSign binding from the personnel roster.

No provider calls, SMS, signatures, identity verification or historical rewrites.
"""
from app.organization_privileges import has_full_platform_authority
from datetime import datetime
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import User, Personnel, EsignIdentityBinding, ReportEsignFlow
from ..security import require_auth
from ..audit import add_operation_audit
from ..functions.esign_service import normalize_psn_account, EsignServiceError

bp = Blueprint("business_supplement", __name__, url_prefix="/api/business-supplement")


class SubprojectCatalog(db.Model):
    __tablename__ = "sample_subproject_catalog"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(240), nullable=False)
    department = db.Column(db.String(240), nullable=False)
    business_category = db.Column(db.String(160), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    revision = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return dict(id=self.id, code=self.code, name=self.name, dept=self.department,
                    businessCategory=self.business_category, enabled=self.enabled,
                    revision=self.revision, updatedAt=self.updated_at.isoformat())


def ok(data=None, message="ok"):
    return jsonify(code=0, data=data, message=message)


def fail(message, status=400):
    return jsonify(code=status, data=None, message=message), status


def writable():
    return not current_app.config.get("APP_BUSINESS_READ_ONLY", False)


@bp.get("/subprojects")
@require_auth
def catalog_list():
    query = SubprojectCatalog.query
    if request.args.get("all") == "1":
        if not has_full_platform_authority(g.current_user):
            return fail("仅管理员可查看停用配置", 403)
    else:
        query = query.filter_by(enabled=True)
    return ok({"rows": [r.to_dict() for r in query.order_by(SubprojectCatalog.code).all()]})


@bp.post("/subprojects")
@bp.put("/subprojects/<int:item_id>")
@require_auth
def catalog_save(item_id=None):
    if not has_full_platform_authority(g.current_user) or not writable():
        return fail("需要管理员权限且平台可写", 403)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return fail("提交内容必须是对象")
    values = {}
    for key, column, maximum in (("code", "code", 60), ("name", "name", 240),
                                 ("dept", "department", 240),
                                 ("businessCategory", "business_category", 160)):
        value = body.get(key)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            return fail("请填写有效的子项目编号、名称、核算部门和业务三级分类")
        values[column] = value.strip()
    if type(body.get("enabled")) is not bool:
        return fail("启用状态必须是布尔值")
    values.update(enabled=body["enabled"], updated_at=datetime.utcnow())
    row = db.session.get(SubprojectCatalog, item_id) if item_id else None
    if item_id and not row:
        return fail("配置不存在", 404)
    before = row.to_dict() if row else None
    try:
        if row:
            if type(body.get("revision")) is not int:
                return fail("缺少版本，请刷新后重试", 409)
            changed = SubprojectCatalog.query.filter_by(id=item_id, revision=body["revision"]).update(
                dict(values, revision=SubprojectCatalog.revision + 1), synchronize_session=False)
            if changed != 1:
                db.session.rollback()
                return fail("配置已被其他人修改，请刷新后重试", 409)
            db.session.refresh(row)
        else:
            row = SubprojectCatalog(**values)
            db.session.add(row)
            db.session.flush()
        add_operation_audit("sample.subproject.configure", "subproject", row.id,
                            before=before, after=row.to_dict(), actor=g.current_user,
                            message="维护样品子项目配置", category="configuration")
        result = row.to_dict()
        db.session.commit()
        return ok(result)
    except IntegrityError:
        db.session.rollback()
        return fail("子项目编号已存在", 409)


def roster_identity(user):
    people = Personnel.query.filter(db.func.lower(Personnel.code) == user.account.lower(),
                                     Personnel.deleted_at.is_(None)).all()
    if len(people) != 1:
        raise ValueError("人员编号与账号没有唯一对应，请由人员管理员核对")
    person = people[0]
    if not person.name or person.name.strip() != (user.name or "").strip():
        raise ValueError("人员名册姓名与登录账号姓名不一致，请由管理员核对")
    try:
        mobile = normalize_psn_account(person.mobile, "mobile")
    except EsignServiceError:
        raise ValueError("名册手机号缺失或格式不正确，请先维护人员名册")
    # Normalize all roster mobiles before comparing; do not match by name alone.
    for other in Personnel.query.filter(Personnel.id != person.id, Personnel.deleted_at.is_(None)).all():
        try:
            same = normalize_psn_account(other.mobile, "mobile") == mobile
        except EsignServiceError:
            same = False
        if same:
            raise ValueError("名册手机号被其他人员使用，不能自动绑定")
    if EsignIdentityBinding.query.filter(EsignIdentityBinding.user_id != user.id,
                                         EsignIdentityBinding.psn_account == mobile).first():
        raise ValueError("手机号已有其他账号的签署绑定，请由管理员核对")
    return person, mobile


def binding_permission(user_id):
    actor = g.current_user
    return actor.id == user_id or actor.role_key == "admin" or "quality.personnel.update" in actor.action_codes()


@bp.route("/roster-binding/<int:user_id>", methods=["GET", "POST"])
@bp.route("/roster-binding/me", defaults={"user_id": None}, methods=["GET", "POST"])
@require_auth
def roster_binding(user_id):
    user_id = user_id or g.current_user.id
    if not binding_permission(user_id):
        return fail("无人员签署绑定权限", 403)
    user = User.query.filter_by(id=user_id).with_for_update().first() if request.method == "POST" else db.session.get(User, user_id)
    if not user or not user.enabled:
        return fail("账号不存在或已停用", 404)
    existing = EsignIdentityBinding.query.filter_by(user_id=user_id).first()
    if existing:
        return ok({"binding": existing.to_dict(), "canBind": False,
                   "reason": "已有绑定，保留现有身份；更换或恢复须由管理员核对"})
    try:
        person, mobile = roster_identity(user)
    except ValueError as exc:
        return fail(str(exc), 409)
    if request.method == "GET":
        return ok({"canBind": True, "userId": user.id, "legalName": user.name,
                   "mobileMasked": mobile[:3] + "****" + mobile[-4:]})
    body = request.get_json(silent=True) or {}
    if not writable():
        return fail("平台当前为只读状态", 403)
    if not isinstance(body, dict) or body.get("confirmed") is not True:
        return fail("请确认使用本人/该人员的名册手机号")
    row = EsignIdentityBinding(user_id=user.id, personnel_id=person.id, legal_name=user.name,
        psn_account=mobile, psn_account_kind="mobile", status="pending",
        created_by_id=g.current_user.id, updated_by_id=g.current_user.id)
    db.session.add(row)
    try:
        db.session.flush()
        # Only unsent new-platform flows; never edit provider/finished/legacy snapshots.
        flows = ReportEsignFlow.query.filter(
            ReportEsignFlow.id >= int(current_app.config.get("ESIGN_PROVIDER_FLOW_MIN_ID") or 0),
            ReportEsignFlow.status.in_(("binding_required", "ready")),
            db.or_(ReportEsignFlow.provider_flow_id.is_(None), ReportEsignFlow.provider_flow_id == ""),
            ReportEsignFlow.dispatched_at.is_(None)).with_for_update().all()
        count = 0
        for flow in flows:
            touched = False
            for signer in flow.signers:
                if signer.user_id == user.id and signer.status in ("binding_required", "pending") and not signer.signed_at:
                    signer.binding = row
                    signer.status = "pending"
                    count += 1
                    touched = True
            if not touched:
                continue
            missing = [s for s in flow.signers if not s.binding or s.binding.status not in ("pending", "verified")]
            roles_missing = {"chief", "reviewer", "approver"} - {s.role_code for s in flow.signers}
            if flow.signers and not missing and not roles_missing:
                flow.status = "ready"
                flow.error_code = None
                flow.error_message = None
            else:
                flow.status = "binding_required"
                problems = []
                if missing:
                    problems.append("未绑定：" + "、".join(s.role_name + "（" + (s.legal_name_snapshot or "") + "）" for s in missing))
                if roles_missing:
                    problems.append("流程人员分配不完整，请核对主检、审核、批准")
                flow.error_message = "；".join(problems)
        add_operation_audit("esign.identity.roster_bind", "user", user.id,
            after=row.to_dict(), actor=g.current_user, category="integration",
            message="确认使用名册手机号创建待实名绑定；未调用e签宝、未发短信")
        result = {"binding": row.to_dict(), "reconnectedSigners": count, "canBind": False}
        db.session.commit()
        return ok(result, "已绑定名册手机号，实名和签署仍须本人完成")
    except IntegrityError:
        db.session.rollback()
        return fail("绑定发生并发变化，请刷新", 409)
