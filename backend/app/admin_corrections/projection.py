"""Keep editable record columns and their existing form snapshots consistent."""
from copy import deepcopy

from ..models import Entrust, Report


def validate_json(name, value, previous):
    if value is None:
        return
    if name in ("info", "detail", "sample_pickup", "workflow_config") and not isinstance(value, dict):
        raise ValueError("登记、检测及流程信息必须是对象")
    if isinstance(previous, dict) and not isinstance(value, dict):
        raise ValueError("不能将信息分组改为文字或列表")
    if isinstance(previous, list) and not isinstance(value, list):
        raise ValueError("不能将明细列表改为其他格式")
    if isinstance(value, dict):
        for key, child in value.items():
            validate_json(key, child, (previous or {}).get(key) if isinstance(previous, dict) else None)
    if name == "detail":
        for key in ("rawSample", "entrustSnapshot", "checkInput", "contractReview", "workflowDates"):
            if key in value and not isinstance(value[key], dict):
                raise ValueError(f"{key} 必须保留信息分组格式")
        if "summary" in value:
            if not isinstance(value["summary"], list) or any(
                not isinstance(s, dict) or not isinstance(s.get("fields", []), list)
                or any(not isinstance(f, list) or len(f) != 2 for f in s.get("fields", []))
                for s in value["summary"]
            ):
                raise ValueError("信息摘要格式不正确")


def synchronize(row, before, patch):
    """Only changed aliases win. Conflicting edits require an explicit choice."""
    if isinstance(row, Entrust):
        info = deepcopy(row.info or {})
        old = before.get("info") or {}
        aliases = (
            {"client": ("client",), "project_name": ("projectName",),
             "department": ("handleDept", "handleDepartment"), "owner": ("handler",),
             "project_type": ("projectType", "erpType"), "amount": ("amount",)}
            if isinstance(row, Entrust) else
            {"client": ("client",), "project_name": ("projectName",),
             "department": ("department",), "owner": ("projectOwner",),
             "erp_type": ("erpType",)}
        )
        for attr, keys in aliases.items():
            candidates = [getattr(row, attr)] if attr in patch else []
            candidates += [info[k] for k in keys if k in info and info[k] != old.get(k)]
            if candidates:
                if any(str(v or "") != str(candidates[0] or "") for v in candidates):
                    raise ValueError("同一信息的不同位置填写不一致，请核对后保存")
                value = candidates[0]
                setattr(row, attr, value)
                for key in keys:
                    info[key] = value
        row.info = info
    if not isinstance(row, Report):
        return
    detail = deepcopy(row.detail or {})
    old = before.get("detail") or {}
    mappings = {
        "client": [("entrustSnapshot", "client"), ("entrustSnapshot", "info", "client")],
        "project_name": [("projectName",), ("entrustSnapshot", "projectName"), ("entrustSnapshot", "info", "projectName")],
        "department": [("rawSample", "testDept")],
        "project": [("rawSample", "project")],
    }
    summary_labels = {"client": ("委托单位",), "project_name": ("工程名称", "项目名称"),
                      "department": ("检测部门",), "project": ("检测项目",)}

    def at(obj, path):
        for key in path:
            if not isinstance(obj, dict) or key not in obj:
                return None
            obj = obj[key]
        return obj

    for attr, paths in mappings.items():
        candidates = [getattr(row, attr)] if attr in patch else []
        candidates += [at(detail, p) for p in paths if at(detail, p) is not None and at(detail, p) != at(old, p)]
        if not candidates:
            continue
        if any(str(v or "") != str(candidates[0] or "") for v in candidates):
            raise ValueError("同一信息的列表值与表单值不一致，请核对后保存")
        value = candidates[0]
        if not isinstance(value, str):
            raise ValueError("名称和部门信息应为文字")
        setattr(row, attr, value)
        for path in paths:
            target = detail
            # Existing snapshots are independent; do not create incomplete ones.
            if len(path) > 1 and path[0] not in detail:
                continue
            for key in path[:-1]:
                target = target.setdefault(key, {})
            target[path[-1]] = value
        for section in detail.get("summary", []):
            section["fields"] = [[k, value if k in summary_labels[attr] else v] for k, v in section.get("fields", [])]
    row.detail = synchronize_registrar(detail, old)


def snapshot_overrides(before, after):
    """Track only source-locked business values, never caller-controlled privilege."""
    old = (before.get("detail") or {}).get("entrustSnapshot") or {}
    new = (after.get("detail") or {}).get("entrustSnapshot") or {}
    result = {}
    if new.get("contractNo") and new.get("contractNo") != old.get("contractNo"):
        result["contractNo"] = new["contractNo"]
        result["projectType"] = new.get("projectType", "")
        for key in ("erpType", "erpProjectNo", "contractPartyA"):
            result[key] = (new.get("info") or {}).get(key, "")
    if "projectType" in new and new["projectType"] != old.get("projectType"):
        result["projectType"] = new["projectType"]
    for key in ("projectType", "erpType", "erpProjectNo", "entrustDate", "contractPartyA"):
        info = new.get("info") or {}
        if key in info and info[key] != (old.get("info") or {}).get(key):
            result[key] = info[key]
    return result


def apply_snapshot_overrides(snapshot, report_id):
    from flask import has_app_context
    if not report_id or not has_app_context():
        return snapshot
    from .source import SourceCorrection
    from ..list_reads import snapshot_override
    override = snapshot_override(report_id, lambda:
        SourceCorrection.query.filter_by(kind="sample-snapshot", source_key=str(report_id)).first())
    if override:
        for key, value in override.fields.items():
            if key in ("projectType", "contractNo"):
                snapshot[key] = value
            snapshot["info"][key] = value
            if key == "contractNo":
                snapshot["info"]["erpContractNo"] = value
    return snapshot


def synchronize_registrar(detail, previous):
    """Called only by validated administrator corrections, retaining actor audit separately."""
    from ..sample_entrust import registrar_identity, write_sample_registrar
    paths = {
        "name": [("sampleRegistrar",), ("rawSample", "registrar"),
                 ("entrustSnapshot", "owner"), ("entrustSnapshot", "info", "handler"),
                 ("entrustSnapshot", "info", "sampleRegistrar")],
        "department": [("sampleRegistrarDepartment",), ("rawSample", "registrarDepartment"),
                       ("entrustSnapshot", "department"), ("entrustSnapshot", "info", "handleDept"),
                       ("entrustSnapshot", "info", "sampleRegistrarDepartment")],
    }
    missing = object()
    def at(obj, path):
        for key in path:
            if not isinstance(obj, dict) or key not in obj:
                return missing
            obj = obj[key]
        return obj
    name, account, department = registrar_identity(previous)
    values = {"name": name, "department": department}
    changed = False
    for field, aliases in paths.items():
        candidates = [at(detail, p) for p in aliases if at(detail, p) is not missing and at(detail, p) != at(previous, p)]
        if not candidates:
            continue
        if any(not isinstance(v, str) for v in candidates):
            raise ValueError("样品登记人和登记部门应为文字")
        candidates = [v.strip() for v in candidates]
        if len(set(candidates)) != 1:
            raise ValueError("样品登记信息的不同位置填写不一致，请核对后保存")
        values[field] = candidates[0]
        changed = True
    from .registrars import apply_selection
    selected = apply_selection(detail, previous, values["name"] != name, values["department"] != department)
    return selected if selected is not None else detail
