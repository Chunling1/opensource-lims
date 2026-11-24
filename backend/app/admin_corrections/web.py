"""Privileged correction entry: explicit confirmation, concurrency and audit."""
import copy
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import FinanceBill, Project, Report
from ..platform.audit import add_operation_audit
from ..security import require_auth
from . import can_correct_business_data
from .catalog import CATALOG, LABELS, columns, field_type
from .source import SourceCorrection, effective
from .projection import validate_json, synchronize, snapshot_overrides
from .numbering import planned, apply as apply_number_changes

bp = Blueprint("admin_corrections", __name__, url_prefix="/api/admin-corrections")
WARNING = "本次使用管理员权限修订，可能包含普通账户不可修改的信息。保存后记录修改人和修改前后内容。"
CUSTOMER_FIELDS = {
    "code": "客户编码",
    "name": "客户名称", "type": "客户类型", "dept": "所属部门", "owner": "负责人",
    "industry": "行业", "addr": "地址", "legal": "法定代表人", "phone": "电话",
    "zip": "邮编", "taxNo": "税号", "bankName": "开户行", "bankAccount": "银行账户",
    "enabled": "启用状态（1启用，0禁用）",
}


def fail(message, status=400):
    return jsonify(code=status, message=message, data=None), status


def allowed(fn):
    @wraps(fn)
    @require_auth
    def run(*args, **kwargs):
        if not can_correct_business_data(g.current_user):
            return fail("仅管理员可进行管理员修订", 403)
        if request.method != "GET" and current_app.config.get("APP_BUSINESS_READ_ONLY"):
            return fail("平台处于只读维护状态", 423)
        return fn(*args, **kwargs)
    return run


@bp.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)


def revision(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def values(row):
    result = {}
    for c in row.__table__.columns:
        value = getattr(row, c.name)
        result[c.name] = value.isoformat() if isinstance(value, (date, datetime)) else str(value) if isinstance(value, Decimal) else copy.deepcopy(value)
    return result


def description(row, names):
    return " · ".join(str(getattr(row, key, "") or "") for key in names if getattr(row, key, None))


def schema(model):
    return [dict(key=c.name, label=LABELS.get(c.name, c.name), type=field_type(c),
                 nullable=c.nullable, maxLength=getattr(c.type, "length", None))
            for c in columns(model)]


@bp.get("/catalog")
@allowed
def catalog():
    return jsonify(code=0, data=dict(warning=WARNING, modules=[
        dict(key=key, label=value[0]) for key, value in CATALOG.items()
    ]))


@bp.get("/registrar-options")
@allowed
def registrar_options():
    from .registrars import options
    try:
        page = int(request.args.get("page", 1))
        term = request.args.get("keyword", "").strip()
        if page < 1 or len(term) > 200:
            raise ValueError("查询参数无效")
        return jsonify(code=0, data=options(request.args.get("kind", "people"), term, page))
    except ValueError as exc:
        return fail(str(exc))


@bp.get("/<kind>")
@allowed
def search(kind):
    if kind == "customers":
        return fail("请使用外部ERP内容管理", 404)
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            raise ValueError()
    except ValueError:
        return fail("分页参数无效")
    term = request.args.get("keyword", "").strip()
    if len(term) > 200:
        return fail("关键词过长")
    if kind not in CATALOG:
        return fail("不存在的业务模块", 404)
    _, model, names = CATALOG[kind]
    query = model.query
    if term:
        query = query.filter(or_(*[getattr(model, name).contains(term, autoescape=True) for name in names]))
    total = query.count()
    rows = query.order_by(model.id.desc()).offset((page - 1) * 20).limit(20).all()
    return jsonify(code=0, data=dict(rows=[
        dict(id=str(row.id), label=description(row, names), status=getattr(row, "status", "") or "")
        for row in rows], total=total, page=page))


def customer_record(code):
    from ..workflow_hooks import empty_customer_search as search_erp_customers
    # Search by stable code; lookup remains bounded even for large directories.
    result = search_erp_customers(code, 1, 200, include_disabled=True)
    matches = [row for row in result["rows"] if row.get("_sourceKey", row["code"]) == code]
    if not matches:
        raise ValueError("客户不存在，请刷新客户库")
    return matches[0]


def convert(column, value):
    kind = field_type(column)
    if value is None:
        if not column.nullable:
            raise ValueError(f"{LABELS.get(column.name, column.name)}不能为空")
        return None
    if kind == "boolean" and type(value) is bool:
        return value
    if kind == "object" and isinstance(value, (dict, list)):
        encode(value)
        return copy.deepcopy(value)
    if kind == "number" and isinstance(value, (str, int, float, Decimal)) and not isinstance(value, bool):
        from sqlalchemy import Integer
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("数值无效")
        if isinstance(column.type, Integer):
            if number != number.to_integral_value():
                raise ValueError("请输入整数")
            return int(number)
        return number
    if kind in ("date", "datetime") and isinstance(value, (date, datetime)):
        return value
    if kind in ("date", "datetime") and isinstance(value, str):
        return date.fromisoformat(value) if kind == "date" else datetime.fromisoformat(value)
    if kind == "text" and isinstance(value, str):
        if getattr(column.type, "length", None) and len(value) > column.type.length:
            raise ValueError(f"{LABELS.get(column.name, column.name)}超过允许长度")
        return value
    raise ValueError(f"{LABELS.get(column.name, column.name)}格式不正确")


@bp.route("/<kind>/<key>", methods=["GET", "PUT"])
@allowed
def edit(kind, key):
    if kind == "customers":
        return fail("请使用外部ERP内容管理", 404)
    if kind not in CATALOG:
        return fail("不存在的业务模块", 404)
    _, model, names = CATALOG[kind]
    if key.isdigit():
        query = model.query.filter_by(id=int(key))
    elif kind in ("reports", "entrusts"):
        query = model.query.filter(getattr(model, names[0]) == key)
    else:
        return fail("记录不存在", 404)
    row = (query.with_for_update() if request.method == "PUT" else query).first()
    if row is None:
        return fail("记录不存在", 404)
    before, fields, label = values(row), schema(model), description(row, names)
    current_revision = revision(before)
    if request.method == "GET":
        return jsonify(code=0, data=dict(label=label, values={f["key"]: before.get(f["key"]) for f in fields},
                                        fields=fields, revision=current_revision, warning=WARNING))
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or (request.content_length or 0) > 2 * 1024 * 1024:
        return fail("修订内容格式或大小无效")
    if body.get("confirmed") is not True:
        return fail("请确认管理员修订提示后再保存", 409)
    if body.get("revision") != current_revision:
        return fail("数据已被修改，请重新打开后核对", 409)
    reason = body.get("reason")
    if not isinstance(reason, str) or not 2 <= len(reason.strip()) <= 300:
        return fail("请填写修改说明（2至300字）")
    patch = body.get("changes")
    known = {f["key"] for f in fields}
    if not isinstance(patch, dict) or not patch or set(patch) - known:
        return fail("修改字段无效")
    try:
        for name, value in patch.items():
            if name in ("info", "detail", "sample_pickup", "workflow_config"):
                validate_json(name, value, before.get(name))
        from .selection import validate as validate_selection
        validate_selection(row, before, patch)
        number_changes = planned(row, before, patch)
        editable = {c.name: c for c in columns(type(row))}
        after = dict(before)
        for name, value in patch.items():
            converted = convert(editable[name], value)
            if field_type(editable[name]) == "object":
                validate_json(name, converted, before.get(name))
            setattr(row, name, converted)
            after[name] = value
        synchronize(row, before, patch)
        for column in columns(type(row)):
            if field_type(column) != "object":
                convert(column, getattr(row, column.name))
        if isinstance(row, Report):
            overrides = snapshot_overrides(before, values(row))
            if overrides:
                save_source("sample-snapshot", str(row.id), overrides)
        if isinstance(row, Project) and before["code"] != row.code:
            row.code_aliases = list(dict.fromkeys([*(row.code_aliases or []), before["code"]]))
        if isinstance(row, FinanceBill):
            row.version += 1
        db.session.flush()
        apply_number_changes(number_changes)
        db.session.flush()
        db.session.refresh(row)
        after = values(row)
        add_operation_audit("admin.business.correct", kind, key, category="business",
                            before=before, after=after, message=WARNING + " 修改说明：" + reason.strip())
        db.session.commit()
        if isinstance(row, Report):
            from ..sample_preview_warmup import schedule_after_save
            schedule_after_save(row)
    except (ValueError, TypeError, InvalidOperation) as exc:
        db.session.rollback()
        return fail(str(exc))
    except RuntimeError as exc:
        db.session.rollback()
        return fail(str(exc), 503)
    except IntegrityError:
        db.session.rollback()
        return fail("编号重复或关联数据无效，请核对后保存", 409)
    response = row.to_row() if hasattr(row, "to_row") else dict(after)
    response["correctionValues"] = {f["key"]: after.get(f["key"]) for f in fields}
    response["correctionRevision"] = revision(after)
    response["message"] = "已保存管理员修订，修改人及修改前后内容已记录。"
    return jsonify(code=0, data=response)


def save_source(kind, key, patch):
    record = SourceCorrection.query.filter_by(kind=kind, source_key=key).with_for_update().first()
    if record is None:
        record = SourceCorrection(kind=kind, source_key=key, fields={}, revision=0)
        db.session.add(record)
    record.fields = dict(record.fields, **patch)
    identity = "contractNo" if kind == "contracts" else "code" if kind == "customers" else None
    if identity:
        record.effective_key = record.fields.get(identity, key)
    record.revision += 1
