"""五类旧 JSON 参考数据的结构校验、日期规范化和隐私脱敏。"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

DATASET_FILES = {
    "std_library": "std_library.json",
    "standards": "standards.json",
    "equipment_ledger": "equipment_ledger.json",
    "personnel": "personnel.json",
    "quality_departments": "quality_departments.json",
}

DATASET_FIELDS = {
    "std_library": frozenset(
        {
            "controlledNo",
            "code",
            "name",
            "authKind",
            "outOfScope",
            "category",
            "location",
            "issueCount",
            "issuer",
            "useDepts",
            "implDate",
            "voidDate",
            "delayDays",
            "replaceNo",
            "isEnglish",
            "remark",
        }
    ),
    "standards": frozenset({"code", "name", "category", "dept", "qualKind"}),
    "equipment_ledger": frozenset(
        {
            "archiveNo",
            "name",
            "spec",
            "factoryNo",
            "maker",
            "calUnit",
            "dept",
            "place",
            "lastCalDate",
            "period",
            "planCalDate",
            "actualCalDate",
            "range",
            "accuracy",
            "keeper",
            "buyDate",
            "buyPrice",
            "useRecord",
            "manual",
            "cert",
            "acceptDoc",
            "status",
            "remark",
        }
    ),
    "personnel": frozenset(
        {
            "name",
            "code",
            "gender",
            "education",
            "title",
            "major",
            "gradTime",
            "position",
            "testScope",
            "checkScope",
            "remark",
            "dept",
            "birthDate",
            "mobile",
            "ethnicity",
            "nativePlace",
            "political",
            "school",
            "workStartTime",
            "joinTime",
            "assignedDepts",
            "permissions",
        }
    ),
    "quality_departments": frozenset({"name"}),
}

REQUIRED_FIELDS = {
    "std_library": frozenset({"code", "name"}),
    "standards": frozenset({"code", "name"}),
    "equipment_ledger": frozenset({"archiveNo", "name"}),
    "personnel": frozenset({"code", "name"}),
    "quality_departments": frozenset({"name"}),
}

DATE_FIELDS = {
    "std_library": frozenset({"implDate", "voidDate"}),
    "equipment_ledger": frozenset({"lastCalDate", "planCalDate", "actualCalDate", "buyDate"}),
    "personnel": frozenset({"birthDate", "gradTime", "workStartTime", "joinTime"}),
}

ARRAY_FIELDS = {
    "std_library": frozenset({"useDepts"}),
    "personnel": frozenset({"assignedDepts", "permissions"}),
}

BOOLEAN_FIELDS = {
    "std_library": frozenset({"outOfScope", "isEnglish"}),
}

SENSITIVE_FIELD_NAMES = frozenset(
    {
        "idno",
        "id_no",
        "identitynumber",
        "identity_number",
        "phone",
        "mobile",
        "email",
    }
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str


class ReferenceDataValidationError(ValueError):
    def __init__(self, dataset: str, issues: list[ValidationIssue]):
        self.dataset = dataset
        self.issues = tuple(issues)
        super().__init__(f"reference data validation failed: dataset={dataset}, issues={len(issues)}")


def normalize_iso_date(value: Any, field: str) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise ReferenceDataValidationError("date", [ValidationIssue("invalid_type", field)])
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ReferenceDataValidationError("date", [ValidationIssue("invalid_date", field)]) from exc


def validate_reference_row(dataset: str, payload: Any) -> dict[str, Any]:
    if dataset not in DATASET_FIELDS:
        raise ReferenceDataValidationError(dataset, [ValidationIssue("unknown_dataset", "dataset")])

    if dataset == "quality_departments":
        payload = {"name": payload} if isinstance(payload, str) else payload
    if not isinstance(payload, dict):
        raise ReferenceDataValidationError(dataset, [ValidationIssue("invalid_row_type", "row")])

    issues: list[ValidationIssue] = []
    allowed = DATASET_FIELDS[dataset]
    for field in payload:
        if field not in allowed:
            issues.append(ValidationIssue("unknown_field", field))

    normalized: dict[str, Any] = {}
    array_fields = ARRAY_FIELDS.get(dataset, frozenset())
    boolean_fields = BOOLEAN_FIELDS.get(dataset, frozenset())
    date_fields = DATE_FIELDS.get(dataset, frozenset())

    for field in allowed:
        value = payload.get(field)
        if field in array_fields:
            if value is None:
                normalized[field] = []
            elif not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                issues.append(ValidationIssue("invalid_string_array", field))
            else:
                normalized[field] = [item.strip() for item in value if item.strip()]
        elif field in boolean_fields:
            if value is None:
                normalized[field] = False
            elif not isinstance(value, bool):
                issues.append(ValidationIssue("invalid_boolean", field))
            else:
                normalized[field] = value
        elif field in date_fields:
            try:
                normalized[field] = normalize_iso_date(value, field)
            except ReferenceDataValidationError as exc:
                issues.extend(exc.issues)
        elif value is None:
            normalized[field] = ""
        elif not isinstance(value, str):
            issues.append(ValidationIssue("invalid_string", field))
        else:
            normalized[field] = value.strip()

    for field in REQUIRED_FIELDS[dataset]:
        if not normalized.get(field):
            issues.append(ValidationIssue("required", field))

    if issues:
        raise ReferenceDataValidationError(dataset, issues)
    return normalized


def mask_sensitive_text(value: Any, prefix: int = 2, suffix: int = 2) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    if len(text) <= prefix + suffix:
        return "*" * len(text)
    return f"{text[:prefix]}{'*' * (len(text) - prefix - suffix)}{text[-suffix:]}"


def mask_private_fields(payload: Any, reveal: bool = False) -> Any:
    """递归复制并脱敏常见隐私字段；仅显式授权时返回原值副本。"""
    if reveal:
        return deepcopy(payload)
    if isinstance(payload, list):
        return [mask_private_fields(item) for item in payload]
    if not isinstance(payload, dict):
        return deepcopy(payload)
    result = {}
    for key, value in payload.items():
        normalized_key = str(key).replace("-", "_").lower()
        if normalized_key in SENSITIVE_FIELD_NAMES:
            result[key] = mask_sensitive_text(value)
        else:
            result[key] = mask_private_fields(value)
    return result
