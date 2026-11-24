"""Whitelisted AI form-draft schemas and deterministic server-side validation."""

from __future__ import annotations

from copy import deepcopy

SCHEMAS = {
    "entrust.v1": {
        "client": "string",
        "projectName": "string",
        "consignor": "string",
        "clientAddr": "string",
        "consignorPhone": "string",
    },
    "sample.v1": {
        "sampleName": "string",
        "spec": "string",
        "sampleAmount": "string",
        "appearance": "string",
        "manufacturer": "string",
        "produceDate": "string",
        "testBases": "string_list",
        "remark": "string",
        "homepageRemark": "string",
        "samplingLocation": "string",
    },
    "report-data.v1": {
        "recordNo": "string",
        "result": "string",
        "conclusion": "string",
        "remark": "string",
    },
}

# These business-controlled paths are documented here as an additional deny
# layer. They are intentionally absent from SCHEMAS and can never be emitted.
LOCKED_PATHS = {
    "entrustNo", "sampleNo", "reportNo", "registrar", "department",
    "originalEntrustNo", "erpContractNo", "schemeCode", "schemeName",
}


class FormDraftError(ValueError):
    pass


def schema_fields(schema_id: str) -> dict[str, str]:
    schema = SCHEMAS.get(schema_id)
    if schema is None:
        raise FormDraftError("不支持的表单架构")
    return deepcopy(schema)


def validate_form_draft(schema_id: str, raw_patches) -> list[dict]:
    schema = schema_fields(schema_id)
    if not isinstance(raw_patches, list):
        raise FormDraftError("AI 草稿格式不正确")
    if len(raw_patches) > 30:
        raise FormDraftError("AI 草稿字段过多")
    result = []
    seen = set()
    for item in raw_patches:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if path in seen or path in LOCKED_PATHS or path not in schema:
            continue
        value = item.get("value")
        expected = schema[path]
        if expected == "string_list":
            if isinstance(value, str):
                value = [part.strip() for part in value.replace("；", ";").split(";") if part.strip()]
            if not isinstance(value, list):
                continue
            value = [str(part).strip()[:300] for part in value if str(part).strip()][:30]
        else:
            if isinstance(value, (dict, list)) or value is None:
                continue
            value = str(value).strip()[:2000]
        confidence = item.get("confidence", 0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0
        result.append({
            "path": path,
            "value": value,
            "confidence": confidence,
            "evidence": str(item.get("evidence") or "")[:300],
            "warning": str(item.get("warning") or "")[:300],
        })
        seen.add(path)
    return result
