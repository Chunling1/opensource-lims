"""Per-sample entrust snapshots.

An Entrust is the project's initial registration.  Every Report (sample) owns a
deep-copied snapshot in ``Report.detail["entrustSnapshot"]`` so later edits are
isolated from the source Entrust and sibling samples.
"""
from copy import deepcopy
from types import SimpleNamespace

EDITABLE_TOP_LEVEL = (
    "client",
    "projectName",
    "amount",
    "department",
    "owner",
)


def entrust_snapshot(entrust):
    """Build a detached, JSON-safe snapshot from an Entrust model."""
    return {
        "sourceEntrustId": entrust.id,
        "sourceEntrustNo": entrust.entrust_no or "",
        "entrustNo": entrust.entrust_no or "",
        "contractNo": entrust.contract_no or "",
        "client": entrust.client or "",
        "projectName": entrust.project_name or "",
        "projectType": entrust.project_type or "",
        "amount": entrust.amount or "",
        "department": entrust.department or "",
        "owner": entrust.owner or "",
        "info": deepcopy(entrust.info or {}),
    }


def normalize_sample_entrust_snapshot(raw, source_entrust, report_id=None, *, select_contract=False):
    """Merge sample edits over the source while keeping the source identity locked."""
    result = entrust_snapshot(source_entrust)
    if not isinstance(raw, dict):
        return result

    for key in EDITABLE_TOP_LEVEL:
        value = raw.get(key)
        if value is not None and not isinstance(value, (dict, list)):
            result[key] = str(value).strip()

    incoming_info = raw.get("info")
    if isinstance(incoming_info, dict):
        merged_info = deepcopy(result["info"])
        for key, value in incoming_info.items():
            if isinstance(key, str) and not isinstance(value, (dict, list)):
                merged_info[key] = "" if value is None else str(value)
        result["info"] = merged_info

    # Reads use the persisted selection. Only validated sample-write routes may
    # opt into a new selection; the source entrust identity/date remain locked.
    from .admin_corrections.projection import apply_snapshot_overrides
    # 委托日期继承原委托；管理员已保存的样品修订另行应用。
    source_info = deepcopy(source_entrust.info or {})
    result["projectType"] = source_entrust.project_type or ""
    result["info"]["projectType"] = source_info.get("projectType") or result["projectType"]
    result["info"]["erpType"] = source_info.get("erpType") or result["projectType"]
    result["info"]["entrustDate"] = source_info.get("entrustDate") or ""
    result = apply_snapshot_overrides(result, report_id)

    # Keep renderer-facing top-level values and the editable form mutually aligned.
    info = result["info"]
    aliases = {
        "client": "client",
        "projectName": "projectName",
        "projectType": "projectType",
        "department": "handleDept",
        "owner": "handler",
    }
    for top_key, info_key in aliases.items():
        if top_key in raw:
            info[info_key] = result[top_key]
        elif top_key == "client" and isinstance(incoming_info, dict) and info_key in incoming_info:
            result[top_key] = str(info.get(info_key) or "").strip()
        elif info.get(info_key):
            result[top_key] = str(info[info_key]).strip()

    info["entrustNo"] = result["entrustNo"]
    info["contractNo"] = ""
    info["erpContractNo"] = ""
    if isinstance(incoming_info, dict) and "contractPartyA" in incoming_info:
        result["info"]["contractPartyA"] = str(incoming_info.get("contractPartyA") or "").strip()
    return result


def sample_client_from_detail(detail, previous):
    """Missing fields preserve the old client; an explicit empty string clears it."""
    snapshot = detail.get("entrustSnapshot") or {}
    if isinstance(snapshot.get("client"), str):
        return snapshot["client"].strip()
    for section in detail.get("summary") or []:
        if section.get("title") == "委托信息":
            for key, value in section.get("fields") or []:
                if key == "委托单位" and isinstance(value, str):
                    return value.strip()
    return previous


def registrar_identity(detail):
    """Read saved sample identity, including legacy snapshots; never infer the editor."""
    detail = detail or {}
    raw = detail.get("rawSample") or {}
    snapshot = detail.get("entrustSnapshot") or {}
    info = snapshot.get("info") or {}
    fields = {k: v for section in detail.get("summary") or []
              if section.get("title") == "委托信息" for k, v in section.get("fields") or []}
    def first(*values):
        return next((str(v).strip() for v in values if v is not None), "")
    return (
        first(detail.get("sampleRegistrar"), raw.get("registrar"), info.get("sampleRegistrar"),
              snapshot.get("owner"), info.get("handler"), fields.get("样品登记人"), fields.get("经办人")),
        first(detail.get("sampleRegistrarAccount"), raw.get("registrarAccount"), info.get("sampleRegistrarAccount")),
        first(detail.get("sampleRegistrarDepartment"), raw.get("registrarDepartment"), info.get("sampleRegistrarDepartment"),
              snapshot.get("department"), info.get("handleDept"), fields.get("样品登记部门"), fields.get("经办部门")),
    )


def stamp_sample_registrar(detail, user, *, previous=None):
    """Stamp new samples once; subsequent ordinary saves retain their saved identity."""
    if previous is not None:
        name, account, department = registrar_identity(previous)
    else:
        account = str(getattr(user, "account", "") or "").strip()
        name = str(getattr(user, "name", "") or account).strip()
        department = str(getattr(getattr(user, "department", None), "name", "") or "").strip()
    result = write_sample_registrar(detail, name, account, department)
    if previous is not None:
        info = ((previous or {}).get("entrustSnapshot") or {}).get("info") or {}
        return write_registrar_ids(result, info.get("sampleRegistrarUserId"), info.get("sampleRegistrarDepartmentId"))
    return write_registrar_ids(result, getattr(user, "id", None), getattr(user, "department_id", None))


def write_registrar_ids(detail, user_id, department_id):
    for target, user_key, dept_key in (
        (detail, "sampleRegistrarUserId", "sampleRegistrarDepartmentId"),
        (detail.get("rawSample"), "registrarUserId", "registrarDepartmentId"),
        ((detail.get("entrustSnapshot") or {}).get("info"), "sampleRegistrarUserId", "sampleRegistrarDepartmentId"),
    ):
        if isinstance(target, dict):
            target[user_key] = str(user_id) if user_id is not None else ""
            target[dept_key] = str(department_id) if department_id is not None else ""
    return detail


def write_sample_registrar(detail, name, account, department):
    result = deepcopy(detail) if isinstance(detail, dict) else {}
    result["sampleRegistrar"] = name
    result["sampleRegistrarAccount"] = account
    result["sampleRegistrarDepartment"] = department

    raw_sample = result.get("rawSample")
    if isinstance(raw_sample, dict):
        raw_sample = deepcopy(raw_sample)
        raw_sample["registrar"] = name
        raw_sample["registrarAccount"] = account
        raw_sample["registrarDepartment"] = department
        result["rawSample"] = raw_sample

    snapshot = result.get("entrustSnapshot")
    if isinstance(snapshot, dict):
        snapshot = deepcopy(snapshot)
        snapshot["department"] = department
        snapshot["owner"] = name
        info = deepcopy(snapshot.get("info") or {})
        info["handleDept"] = department
        info["handler"] = name
        info["sampleRegistrar"] = name
        info["sampleRegistrarAccount"] = account
        info["sampleRegistrarDepartment"] = department
        snapshot["info"] = info
        result["entrustSnapshot"] = snapshot

    for section in result.get("summary") or []:
        if not isinstance(section, dict) or section.get("title") != "委托信息":
            continue
        fields = []
        department_seen = False
        registrar_seen = False
        for field in section.get("fields") or []:
            if not isinstance(field, (list, tuple)) or len(field) < 2:
                continue
            label, value = field[0], field[1]
            if label in ("经办部门", "样品登记部门"):
                fields.append(["样品登记部门", department])
                department_seen = True
            elif label in ("经办人", "样品登记人"):
                fields.append(["样品登记人", name])
                registrar_seen = True
            else:
                fields.append([label, value])
        if not department_seen:
            fields.append(["样品登记部门", department])
        if not registrar_seen:
            fields.append(["样品登记人", name])
        section["fields"] = fields
    return result


def report_entrust_snapshot(report, source_entrust):
    detail = report.detail or {}
    return normalize_sample_entrust_snapshot(detail.get("entrustSnapshot"), source_entrust, report.id)


def sample_entrust_object(report, source_entrust):
    """Return an Entrust-shaped object backed by the report's private snapshot."""
    snapshot = report_entrust_snapshot(report, source_entrust)
    effective = SimpleNamespace(
        id=source_entrust.id,
        entrust_no=snapshot["entrustNo"],
        contract_no=snapshot["contractNo"],
        client=snapshot["client"],
        project_name=snapshot["projectName"],
        project_type=snapshot["projectType"],
        amount=snapshot["amount"],
        department=snapshot["department"],
        owner=snapshot["owner"],
        info=deepcopy(snapshot["info"]),
        status=source_entrust.status,
        created_at=source_entrust.created_at,
    )
    if hasattr(source_entrust, "to_row"):
        def _to_row():
            row = dict(source_entrust.to_row())
            row.update({
                "entrustNo": snapshot["entrustNo"],
                "contractNo": snapshot["contractNo"],
                "client": snapshot["client"],
                "projectName": snapshot["projectName"],
                "projectType": snapshot["projectType"],
                "amount": snapshot["amount"],
                "department": snapshot["department"],
                "owner": snapshot["owner"],
                "info": deepcopy(snapshot["info"]),
            })
            return row
        effective.to_row = _to_row
    return effective


def sample_party_error(detail, source, previous=None, report_id=None):
    return None


def sample_contract_frozen_error(report_id):
    return None


def persist_sample_contract_selection(report):
    return None
