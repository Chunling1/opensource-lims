from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

import openpyxl
from flask import Blueprint, current_app, g, jsonify, request, send_file

from ..audit import add_operation_audit
from ..extensions import db
from ..functions.stored_files import persist_bytes
from ..models import CustomTemplate, SystemConfigSetting
from ..security import require_auth

bp = Blueprint("system_config", __name__, url_prefix="/api/system")

ESIGN_SETTING_KEY = "esign_config"

SYSTEM_TEMPLATE_FIELDS = [
    {"key": "entrustNo", "label": "委托编号"},
    {"key": "reportNo", "label": "报告编号"},
    {"key": "sampleNo", "label": "样品编号"},
    {"key": "clientName", "label": "委托单位"},
    {"key": "clientAddress", "label": "委托单位地址"},
    {"key": "contactName", "label": "联系人"},
    {"key": "contactPhone", "label": "联系电话"},
    {"key": "sampleName", "label": "样品名称"},
    {"key": "sampleModel", "label": "规格型号"},
    {"key": "sampleQuantity", "label": "样品数量"},
    {"key": "testItems", "label": "检测项目/参数"},
    {"key": "testBasis", "label": "检测依据/标准"},
    {"key": "testConclusion", "label": "检测结论"},
    {"key": "testDate", "label": "检测日期"},
    {"key": "reportDate", "label": "报告日期"},
    {"key": "testerName", "label": "主检人员"},
    {"key": "reviewerName", "label": "审核人员"},
    {"key": "approverName", "label": "批准人员"},
    {"key": "remark", "label": "备注"},
]


def _require_system_admin():
    user = g.current_user
    if user.role_key == "admin" or any(p.code.startswith("system.") for p in user.permissions):
        return None
    return jsonify(code=403, message="需要系统管理权限", data=None), 403


def apply_esign_config_to_app(app) -> None:
    setting = db.session.get(SystemConfigSetting, ESIGN_SETTING_KEY)
    cfg = dict(setting.value_json or {}) if setting else {}
    if not cfg:
        app.config["ESIGN_REQUIRED_FOR_ISSUANCE"] = False
        return
    enabled = bool(cfg.get("enabled", False))
    app.config["ESIGN_REQUIRED_FOR_ISSUANCE"] = bool(cfg.get("requiredForIssuance", enabled))
    app.config["ESIGN_BASE_URL"] = str(cfg.get("baseUrl") or "").strip()
    app.config["ESIGN_APP_ID"] = str(cfg.get("appId") or "").strip()
    if cfg.get("appSecret"):
        app.config["ESIGN_APP_SECRET"] = str(cfg["appSecret"]).strip()
    app.config["ESIGN_ORG_ID"] = str(cfg.get("orgId") or "").strip()
    app.config["ESIGN_ORG_NAME"] = str(cfg.get("orgName") or "").strip()
    app.config["ESIGN_ORG_SEAL_ID"] = str(cfg.get("orgSealId") or "").strip()
    app.config["ESIGN_ORG_AUTOSIGN_ENABLED"] = bool(cfg.get("orgAutosignEnabled", False))
    app.config["ESIGN_POSITIONING_REDIRECT_URL"] = str(cfg.get("callbackUrl") or "").strip()


def _serialize_esign_config(cfg: dict | None = None) -> dict:
    data = dict(cfg or {})
    if not data:
        data = {
            "enabled": bool(current_app.config.get("ESIGN_REQUIRED_FOR_ISSUANCE", False)),
            "requiredForIssuance": bool(current_app.config.get("ESIGN_REQUIRED_FOR_ISSUANCE", False)),
            "baseUrl": str(current_app.config.get("ESIGN_BASE_URL") or "https://openapi.esign.cn"),
            "appId": str(current_app.config.get("ESIGN_APP_ID") or ""),
            "orgId": str(current_app.config.get("ESIGN_ORG_ID") or ""),
            "orgName": str(current_app.config.get("ESIGN_ORG_NAME") or ""),
            "orgSealId": str(current_app.config.get("ESIGN_ORG_SEAL_ID") or ""),
            "orgAutosignEnabled": bool(current_app.config.get("ESIGN_ORG_AUTOSIGN_ENABLED", False)),
            "callbackUrl": str(current_app.config.get("ESIGN_POSITIONING_REDIRECT_URL") or ""),
        }
    secret = str(data.get("appSecret") or current_app.config.get("ESIGN_APP_SECRET") or "")
    return {
        "enabled": bool(data.get("enabled", False)),
        "requiredForIssuance": bool(data.get("requiredForIssuance", False)),
        "baseUrl": str(data.get("baseUrl") or "https://openapi.esign.cn"),
        "appId": str(data.get("appId") or ""),
        "hasAppSecret": bool(secret),
        "appSecretMasked": ("*" * 8 + secret[-4:]) if len(secret) >= 4 else ("****" if secret else ""),
        "orgId": str(data.get("orgId") or ""),
        "orgName": str(data.get("orgName") or ""),
        "orgSealId": str(data.get("orgSealId") or ""),
        "orgAutosignEnabled": bool(data.get("orgAutosignEnabled", False)),
        "callbackUrl": str(data.get("callbackUrl") or ""),
    }


@bp.get("/esign-config")
@require_auth
def get_esign_config():
    denied = _require_system_admin()
    if denied:
        return denied
    setting = db.session.get(SystemConfigSetting, ESIGN_SETTING_KEY)
    return jsonify(code=0, message="ok", data=_serialize_esign_config(setting.value_json if setting else None))


@bp.put("/esign-config")
@require_auth
def save_esign_config():
    denied = _require_system_admin()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    setting = db.session.get(SystemConfigSetting, ESIGN_SETTING_KEY)
    existing = dict(setting.value_json or {}) if setting else {}
    enabled = bool(body.get("enabled", False))
    new_secret = str(body.get("appSecret") or "").strip()
    next_cfg = {
        "enabled": enabled,
        "requiredForIssuance": bool(body.get("requiredForIssuance", enabled)),
        "baseUrl": str(body.get("baseUrl") or "https://openapi.esign.cn").strip(),
        "appId": str(body.get("appId") or "").strip(),
        "appSecret": new_secret or str(existing.get("appSecret") or ""),
        "orgId": str(body.get("orgId") or "").strip(),
        "orgName": str(body.get("orgName") or "").strip(),
        "orgSealId": str(body.get("orgSealId") or "").strip(),
        "orgAutosignEnabled": bool(body.get("orgAutosignEnabled", False)),
        "callbackUrl": str(body.get("callbackUrl") or "").strip(),
    }
    if enabled and (not next_cfg["appId"] or not next_cfg["appSecret"]):
        return jsonify(code=400, message="启用线上电子签章时，请填写 AppID 与 AppSecret", data=None), 400

    if setting is None:
        setting = SystemConfigSetting(key=ESIGN_SETTING_KEY, value_json=next_cfg, updated_by=g.current_user.account)
        db.session.add(setting)
    else:
        setting.value_json = next_cfg
        setting.updated_by = g.current_user.account

    add_operation_audit(
        "system.esign_config.update",
        "system_config",
        ESIGN_SETTING_KEY,
        before={"enabled": existing.get("enabled", False), "appId": existing.get("appId", "")},
        after={"enabled": next_cfg["enabled"], "appId": next_cfg["appId"]},
        actor=g.current_user,
    )
    db.session.commit()
    apply_esign_config_to_app(current_app)
    return jsonify(code=0, message="电子签章配置已保存", data=_serialize_esign_config(next_cfg))


def _extract_docx_placeholders(raw_bytes: bytes) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_.\u4e00-\u9fa5-]+)\s*\}\}|\$\{\s*([a-zA-Z0-9_.\u4e00-\u9fa5-]+)\s*\}")
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zf:
            for name in zf.namelist():
                if name.startswith("word/") and name.endswith(".xml"):
                    xml_bytes = zf.read(name)
                    try:
                        root = ET.fromstring(xml_bytes)
                        text = "".join(root.itertext())
                    except ET.ParseError:
                        text = re.sub(r"<[^>]+>", "", xml_bytes.decode("utf-8", errors="ignore"))
                    for m in pattern.finditer(text):
                        token = (m.group(1) or m.group(2) or "").strip()
                        if token and token not in seen:
                            seen.add(token)
                            found.append(token)
    except Exception:
        pass
    return found


@bp.get("/templates")
@require_auth
def list_templates():
    denied = _require_system_admin()
    if denied:
        return denied
    rows = CustomTemplate.query.order_by(CustomTemplate.kind.asc(), CustomTemplate.id.desc()).all()
    return jsonify(
        code=0,
        message="ok",
        data={
            "items": [r.to_dict() for r in rows],
            "systemFields": SYSTEM_TEMPLATE_FIELDS,
        },
    )


@bp.post("/templates")
@require_auth
def upload_template():
    denied = _require_system_admin()
    if denied:
        return denied
    file = request.files.get("file")
    kind = str(request.form.get("kind") or "report").strip()
    name = str(request.form.get("name") or (file.filename if file else "")).strip()
    if kind not in {"commission", "report"}:
        return jsonify(code=400, message="模板类型仅支持 commission 或 report", data=None), 400
    if not file or not file.filename or not file.filename.lower().endswith(".docx"):
        return jsonify(code=400, message="请上传 .docx 格式模板文件", data=None), 400
    if not name:
        return jsonify(code=400, message="请填写模板名称", data=None), 400

    raw = file.read()
    if not raw:
        return jsonify(code=400, message="上传模板文件为空", data=None), 400
    placeholders = _extract_docx_placeholders(raw)
    stored = persist_bytes(
        raw,
        category="custom_template",
        original_name=file.filename,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        created_by=g.current_user.account,
    )
    default_mapping = {
        p: next((f["key"] for f in SYSTEM_TEMPLATE_FIELDS if f["key"].lower() == p.lower() or f["label"] == p), "")
        for p in placeholders
    }
    tpl = CustomTemplate(
        kind=kind,
        name=name,
        file_name=file.filename,
        stored_file_id=stored.id,
        placeholders_json=placeholders,
        field_mapping_json=default_mapping,
        is_active=False,
        created_by=g.current_user.account,
    )
    db.session.add(tpl)
    db.session.commit()
    return jsonify(code=0, message="模板上传成功", data=tpl.to_dict()), 201


@bp.put("/templates/<int:tid>")
@require_auth
def update_template(tid: int):
    denied = _require_system_admin()
    if denied:
        return denied
    tpl = db.session.get(CustomTemplate, tid)
    if tpl is None:
        return jsonify(code=404, message="模板不存在", data=None), 404
    body = request.get_json(silent=True) or {}
    if "name" in body and str(body["name"]).strip():
        tpl.name = str(body["name"]).strip()
    if "fieldMapping" in body and isinstance(body["fieldMapping"], dict):
        tpl.field_mapping_json = {str(k): str(v) for k, v in body["fieldMapping"].items()}
    if "isActive" in body:
        active = bool(body["isActive"])
        if active:
            CustomTemplate.query.filter(CustomTemplate.kind == tpl.kind, CustomTemplate.id != tpl.id).update(
                {"is_active": False}
            )
        tpl.is_active = active
    db.session.commit()
    return jsonify(code=0, message="模板配置已更新", data=tpl.to_dict())


@bp.delete("/templates/<int:tid>")
@require_auth
def delete_template(tid: int):
    denied = _require_system_admin()
    if denied:
        return denied
    tpl = db.session.get(CustomTemplate, tid)
    if tpl is None:
        return jsonify(code=404, message="模板不存在", data=None), 404
    db.session.delete(tpl)
    db.session.commit()
    return jsonify(code=0, message="模板已删除", data=None)


@bp.get("/sample-imports/<kind>")
@require_auth
def download_sample_import(kind: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    if kind == "personnel":
        ws.title = "人员导入模板"
        ws.append(["姓名", "工号/账号", "所在部门", "职称", "岗位/职务", "手机号", "可工作部门", "流程权限"])
        ws.append(["张工", "tester_zhang", "理化检测室", "工程师", "主检员", "13800000001", "理化检测室", "数据录入;样品领取"])
        ws.append(["李工", "reviewer_li", "综合业务部", "高级工程师", "技术审核人", "13800000002", "理化检测室;综合业务部", "报告审核;报告批准"])
        filename = "personnel-import-template.xlsx"
    elif kind == "equipment":
        ws.title = "设备台账导入模板"
        ws.append(["设备编号", "设备名称", "规格型号", "出厂编号", "所属部门", "校准周期(月)", "本次校准日期", "有效截止日期", "设备状态"])
        ws.append(["EQ-2026-001", "恒温恒湿箱", "LHS-150HC", "SN-1001", "理化检测室", 12, "2026-01-15", "2027-01-14", "正常"])
        ws.append(["EQ-2026-002", "电子天平", "ME204E", "SN-1002", "理化检测室", 12, "2026-03-01", "2027-02-28", "正常"])
        filename = "equipment-import-template.xlsx"
    elif kind == "standards":
        ws.title = "标准与CNAS资质模板"
        ws.append(["标准编号", "标准名称", "检测参数", "类别", "适用部门", "实施日期", "资质标识(CMA/CNAS)", "状态"])
        ws.append(["GB/T 18883-2022", "室内空气质量标准", "甲醛、苯、TVOC", "化学检测", "理化检测室", "2023-02-01", "CMA;CNAS", "现行有效"])
        ws.append(["GB/T 50081-2019", "混凝土物理力学性能试验方法标准", "抗压强度", "力学检测", "力学检测室", "2019-12-01", "CMA;CNAS", "现行有效"])
        filename = "standards-cnas-import-template.xlsx"
    else:
        return jsonify(code=400, message="不支持的模板类型", data=None), 400

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
