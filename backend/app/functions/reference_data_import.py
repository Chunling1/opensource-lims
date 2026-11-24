"""旧参考 JSON 的只增不改、可重入数据库导入。

导入遵循三条约束：现有业务记录优先、每个源行独立认领、冲突只记摘要元数据。
调用者应在独立 Flask 应用上下文中执行；函数会自行提交批次事务。
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..data_models.reference_imports import LegacyImportBatch, LegacyImportConflict, LegacyImportRow
from ..extensions import db
from ..forms.reference_data import (
    DATASET_FIELDS,
    DATASET_FILES,
    ReferenceDataValidationError,
    ValidationIssue,
    validate_reference_row,
)
from ..models import Department, EquipmentItem, Personnel, Standard, StdLibraryItem


class ReferenceDataFileError(ValueError):
    pass


class ReferenceDataImportError(RuntimeError):
    def __init__(self, dataset: str, failure_code: str):
        self.dataset = dataset
        self.failure_code = failure_code
        super().__init__(f"reference import failed: dataset={dataset}, code={failure_code}")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class ImportSummary:
    dataset: str
    source_sha256: str
    source_rows: int
    validated_rows: int = 0
    inserted: int = 0
    adopted: int = 0
    conflicts: int = 0
    skipped: int = 0
    dry_run: bool = True
    already_completed: bool = False
    batch_id: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _Adapter:
    model: Any
    target_table: str
    to_match_attrs: Callable[[dict[str, Any]], dict[str, Any]]
    to_insert_attrs: Callable[[dict[str, Any]], dict[str, Any]]
    natural_candidates: Callable[[dict[str, Any]], list[Any]]
    preserve_duplicate_rows: bool = True


def _std_library_attrs(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "controlled_no": row.get("controlledNo", ""),
        "code": row.get("code", ""),
        "name": row.get("name", ""),
        "auth_kind": row.get("authKind", ""),
        "out_of_scope": bool(row.get("outOfScope")),
        "category": row.get("category", ""),
        "location": row.get("location", ""),
        "issue_count": row.get("issueCount", ""),
        "issuer": row.get("issuer", ""),
        "use_depts": ";".join(row.get("useDepts") or []),
        "impl_date": row.get("implDate", ""),
        "void_date": row.get("voidDate", ""),
        "delay_days": row.get("delayDays", ""),
        "replace_no": row.get("replaceNo", ""),
        "is_english": bool(row.get("isEnglish")),
        "remark": row.get("remark", ""),
    }


def _std_library_candidates(row: dict[str, Any]) -> list[StdLibraryItem]:
    return (
        StdLibraryItem.query.filter_by(
            code=row.get("code", ""),
            controlled_no=row.get("controlledNo", ""),
        )
        .order_by(StdLibraryItem.id)
        .all()
    )


def _equipment_attrs(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "archive_no": row.get("archiveNo", ""),
        "name": row.get("name", ""),
        "spec": row.get("spec", ""),
        "factory_no": row.get("factoryNo", ""),
        "maker": row.get("maker", ""),
        "cal_unit": row.get("calUnit", ""),
        "dept": row.get("dept", ""),
        "place": row.get("place", ""),
        "last_cal_date": row.get("lastCalDate", ""),
        "period": row.get("period", ""),
        "plan_cal_date": row.get("planCalDate", ""),
        "actual_cal_date": row.get("actualCalDate", ""),
        "meas_range": row.get("range", ""),
        "accuracy": row.get("accuracy", ""),
        "keeper": row.get("keeper", ""),
        "buy_date": row.get("buyDate", ""),
        "buy_price": row.get("buyPrice", ""),
        "use_record": row.get("useRecord", ""),
        "manual": row.get("manual", ""),
        "cert": row.get("cert", ""),
        "accept_doc": row.get("acceptDoc", ""),
        "status": row.get("status", ""),
        "remark": row.get("remark", ""),
    }


def _equipment_candidates(row: dict[str, Any]) -> list[EquipmentItem]:
    return EquipmentItem.query.filter_by(archive_no=row.get("archiveNo", "")).order_by(EquipmentItem.id).all()


def _personnel_attrs(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": row.get("name", ""),
        "code": row.get("code", ""),
        "gender": row.get("gender", ""),
        "education": row.get("education", ""),
        "title": row.get("title", ""),
        "major": row.get("major", ""),
        "grad_time": row.get("gradTime", ""),
        "position": row.get("position", ""),
        "test_scope": row.get("testScope", ""),
        "check_scope": row.get("checkScope", ""),
        "remark": row.get("remark", ""),
        "dept": row.get("dept", ""),
        "birth_date": row.get("birthDate", ""),
        "id_no": row.get("idNo", ""),
        "ethnicity": row.get("ethnicity", ""),
        "native_place": row.get("nativePlace", ""),
        "political": row.get("political", ""),
        "school": row.get("school", ""),
        "work_start_time": row.get("workStartTime", ""),
        "join_time": row.get("joinTime", ""),
        "assigned_depts": ";".join(row.get("assignedDepts") or []),
        "permissions": ";".join(row.get("permissions") or []),
    }


def _personnel_candidates(row: dict[str, Any]) -> list[Personnel]:
    return Personnel.query.filter_by(code=row.get("code", "")).order_by(Personnel.id).all()


def _standard_attrs(row: dict[str, Any]) -> dict[str, Any]:
    attrs = {
        "code": row.get("code", ""),
        "name": row.get("name", ""),
        "auth_kind": row.get("qualKind", ""),
        "department": row.get("dept", ""),
        "status": "现行",
        "expired": False,
    }
    if "category" in Standard.__table__.columns:
        attrs["category"] = row.get("category", "")
    return attrs


def _standard_candidates(row: dict[str, Any]) -> list[Standard]:
    return Standard.query.filter_by(code=row.get("code", "")).order_by(Standard.id).all()


def _department_code(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:20].upper()
    return f"LQD_{digest}"


def _department_match_attrs(row: dict[str, Any]) -> dict[str, Any]:
    return {"name": row["name"]}


def _department_insert_attrs(row: dict[str, Any]) -> dict[str, Any]:
    return {"code": _department_code(row["name"]), "name": row["name"]}


def _department_candidates(row: dict[str, Any]) -> list[Department]:
    code = _department_code(row["name"])
    return (
        Department.query.filter(db.or_(Department.name == row["name"], Department.code == code))
        .order_by(Department.id)
        .all()
    )


ADAPTERS = {
    "std_library": _Adapter(
        StdLibraryItem,
        StdLibraryItem.__tablename__,
        _std_library_attrs,
        _std_library_attrs,
        _std_library_candidates,
    ),
    "standards": _Adapter(
        Standard,
        Standard.__tablename__,
        _standard_attrs,
        _standard_attrs,
        _standard_candidates,
        preserve_duplicate_rows=False,
    ),
    "equipment_ledger": _Adapter(
        EquipmentItem,
        EquipmentItem.__tablename__,
        _equipment_attrs,
        _equipment_attrs,
        _equipment_candidates,
    ),
    "personnel": _Adapter(
        Personnel,
        Personnel.__tablename__,
        _personnel_attrs,
        _personnel_attrs,
        _personnel_candidates,
    ),
    "quality_departments": _Adapter(
        Department,
        Department.__tablename__,
        _department_match_attrs,
        _department_insert_attrs,
        _department_candidates,
        preserve_duplicate_rows=False,
    ),
}


def _canonical_sha256(dataset: str, payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{dataset}\n{canonical}".encode()).hexdigest()


def _load_source(dataset: str, source_path: str | Path) -> tuple[str, list[Any]]:
    if dataset not in ADAPTERS:
        raise ReferenceDataFileError(f"unknown reference dataset: {dataset}")
    path = Path(source_path)
    raw = path.read_bytes()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceDataFileError(f"invalid reference JSON: dataset={dataset}") from exc
    if not isinstance(payload, list):
        raise ReferenceDataFileError(f"reference JSON root must be an array: dataset={dataset}")
    return source_sha256, payload


def _matches(candidate: Any, attrs: dict[str, Any]) -> bool:
    return all(getattr(candidate, field) == value for field, value in attrs.items())


def _different_fields(candidate: Any, attrs: dict[str, Any]) -> set[str]:
    return {field for field, value in attrs.items() if getattr(candidate, field) != value}


def _target_length_issues(adapter: _Adapter, attrs: dict[str, Any]) -> list[ValidationIssue]:
    issues = []
    for field, value in attrs.items():
        column = adapter.model.__table__.columns.get(field)
        max_length = getattr(column.type, "length", None) if column is not None else None
        if max_length and isinstance(value, str) and len(value) > max_length:
            issues.append(ValidationIssue("target_length_exceeded", field))
    return issues


def _safe_field_names(dataset: str, fields: set[str] | list[str] | tuple[str, ...]) -> str:
    known = set(DATASET_FIELDS[dataset])
    known.update(ADAPTERS[dataset].model.__table__.columns.keys())
    safe = {field if field in known else "unknown" for field in fields}
    return ",".join(sorted(safe))


def _record_resolution(
    batch: LegacyImportBatch,
    row_no: int,
    row_sha256: str,
    adapter: _Adapter,
    resolution: str,
    target_id: str | None = None,
) -> LegacyImportRow:
    import_row = LegacyImportRow(
        batch_id=batch.id,
        source_row_no=row_no,
        row_sha256=row_sha256,
        target_table=adapter.target_table,
        target_id=target_id,
        resolution=resolution,
    )
    db.session.add(import_row)
    db.session.flush()
    return import_row


def _record_conflict(
    batch: LegacyImportBatch,
    dataset: str,
    row_no: int,
    row_sha256: str,
    adapter: _Adapter,
    code: str,
    fields: set[str] | list[str] | tuple[str, ...],
    target_id: str | None = None,
) -> None:
    import_row = _record_resolution(batch, row_no, row_sha256, adapter, "conflict", target_id)
    db.session.add(
        LegacyImportConflict(
            batch_id=batch.id,
            import_row_id=import_row.id,
            source_row_no=row_no,
            row_sha256=row_sha256,
            target_table=adapter.target_table,
            target_id=target_id,
            conflict_code=code,
            field_names=_safe_field_names(dataset, fields),
        )
    )


def _preexisting_ids(adapter: _Adapter, inserted_target_ids: set[str] | None = None) -> set[str]:
    inserted_target_ids = inserted_target_ids or set()
    ids = {str(value) for (value,) in db.session.query(adapter.model.id).all()}
    return ids - inserted_target_ids


def _classify_existing(
    adapter: _Adapter,
    normalized: dict[str, Any],
    match_attrs: dict[str, Any],
    preexisting_ids: set[str],
    claimed_ids: set[str],
) -> tuple[str, Any | None, list[Any]]:
    candidates = adapter.natural_candidates(normalized)
    existing = [candidate for candidate in candidates if str(candidate.id) in preexisting_ids]
    exact = [candidate for candidate in existing if _matches(candidate, match_attrs)]
    unclaimed_exact = [candidate for candidate in exact if str(candidate.id) not in claimed_ids]
    if unclaimed_exact:
        return "adopt", unclaimed_exact[0], existing
    if exact:
        if adapter.preserve_duplicate_rows:
            return "insert", None, existing
        return "adopt", exact[0], existing
    if existing:
        return "conflict", existing[0], existing
    return "insert", None, existing


def _dry_run(dataset: str, source_sha256: str, rows: list[Any]) -> ImportSummary:
    adapter = ADAPTERS[dataset]
    summary = ImportSummary(dataset, source_sha256, len(rows), dry_run=True)
    preexisting_ids = _preexisting_ids(adapter)
    claimed_ids: set[str] = set()

    for raw_row in rows:
        try:
            normalized = validate_reference_row(dataset, raw_row)
        except ReferenceDataValidationError:
            summary.conflicts += 1
            continue
        summary.validated_rows += 1
        match_attrs = adapter.to_match_attrs(normalized)
        action, target, existing = _classify_existing(
            adapter,
            normalized,
            match_attrs,
            preexisting_ids,
            claimed_ids,
        )
        if action == "adopt":
            claimed_ids.add(str(target.id))
            summary.adopted += 1
        elif action == "conflict":
            summary.conflicts += 1
        else:
            length_issues = _target_length_issues(adapter, adapter.to_insert_attrs(normalized))
            if length_issues:
                summary.conflicts += 1
            else:
                summary.inserted += 1
        del existing
    return summary


def _process_batch(
    batch: LegacyImportBatch,
    dataset: str,
    source_sha256: str,
    rows: list[Any],
) -> ImportSummary:
    adapter = ADAPTERS[dataset]
    summary = ImportSummary(dataset, source_sha256, len(rows), dry_run=False, batch_id=batch.id)
    processed = {row.source_row_no: row for row in LegacyImportRow.query.filter_by(batch_id=batch.id).all()}
    inserted_target_ids = {
        row.target_id for row in processed.values() if row.resolution == "inserted" and row.target_id is not None
    }
    claimed_ids = {
        row.target_id
        for row in processed.values()
        if row.resolution in {"inserted", "adopted"} and row.target_id is not None
    }
    preexisting_ids = _preexisting_ids(adapter, inserted_target_ids)

    for row_no, raw_row in enumerate(rows, start=1):
        row_sha256 = _canonical_sha256(dataset, raw_row)
        previous = processed.get(row_no)
        if previous:
            if previous.row_sha256 != row_sha256:
                raise ReferenceDataFileError(f"source row hash changed inside batch: dataset={dataset}, row={row_no}")
            summary.skipped += 1
            continue

        try:
            normalized = validate_reference_row(dataset, raw_row)
        except ReferenceDataValidationError as exc:
            fields = {issue.field for issue in exc.issues}
            _record_conflict(
                batch,
                dataset,
                row_no,
                row_sha256,
                adapter,
                "validation_failed",
                fields,
            )
            summary.conflicts += 1
            continue

        summary.validated_rows += 1
        match_attrs = adapter.to_match_attrs(normalized)
        action, target, existing = _classify_existing(
            adapter,
            normalized,
            match_attrs,
            preexisting_ids,
            claimed_ids,
        )

        if action == "adopt":
            target_id = str(target.id)
            claimed_ids.add(target_id)
            _record_resolution(batch, row_no, row_sha256, adapter, "adopted", target_id)
            summary.adopted += 1
            continue

        if action == "conflict":
            different = set().union(*(_different_fields(candidate, match_attrs) for candidate in existing))
            target_id = str(target.id) if target is not None else None
            _record_conflict(
                batch,
                dataset,
                row_no,
                row_sha256,
                adapter,
                "existing_record_changed",
                different,
                target_id,
            )
            summary.conflicts += 1
            continue

        insert_attrs = adapter.to_insert_attrs(normalized)
        length_issues = _target_length_issues(adapter, insert_attrs)
        if length_issues:
            _record_conflict(
                batch,
                dataset,
                row_no,
                row_sha256,
                adapter,
                "target_length_exceeded",
                {issue.field for issue in length_issues},
            )
            summary.conflicts += 1
            continue

        target = adapter.model(**insert_attrs)
        db.session.add(target)
        db.session.flush()
        target_id = str(target.id)
        claimed_ids.add(target_id)
        _record_resolution(batch, row_no, row_sha256, adapter, "inserted", target_id)
        summary.inserted += 1

    db.session.flush()
    all_rows = LegacyImportRow.query.filter_by(batch_id=batch.id).all()
    batch.source_row_count = len(rows)
    batch.inserted_count = sum(row.resolution == "inserted" for row in all_rows)
    batch.adopted_count = sum(row.resolution == "adopted" for row in all_rows)
    batch.conflict_count = sum(row.resolution == "conflict" for row in all_rows)
    batch.skipped_count = summary.skipped
    batch.status = "completed"
    batch.failure_code = None
    batch.completed_at = _utcnow()
    db.session.commit()
    return summary


def import_reference_dataset(
    dataset: str,
    source_path: str | Path,
    *,
    dry_run: bool = True,
) -> ImportSummary:
    source_sha256, rows = _load_source(dataset, source_path)
    if dry_run:
        return _dry_run(dataset, source_sha256, rows)

    batch = LegacyImportBatch.query.filter_by(dataset=dataset, source_sha256=source_sha256).first()
    if batch and batch.status == "completed":
        return ImportSummary(
            dataset,
            source_sha256,
            len(rows),
            skipped=len(rows),
            dry_run=False,
            already_completed=True,
            batch_id=batch.id,
        )

    if batch is None:
        batch = LegacyImportBatch(
            dataset=dataset,
            source_sha256=source_sha256,
            source_row_count=len(rows),
            status="running",
        )
        db.session.add(batch)
    else:
        batch.status = "running"
        batch.failure_code = None
        batch.completed_at = None
    db.session.commit()

    batch_id = batch.id
    try:
        return _process_batch(batch, dataset, source_sha256, rows)
    except Exception as exc:
        db.session.rollback()
        failure_code = type(exc).__name__[:120]
        failed_batch = db.session.get(LegacyImportBatch, batch_id)
        if failed_batch is not None:
            failed_batch.status = "failed"
            failed_batch.failure_code = failure_code
            db.session.commit()
        raise ReferenceDataImportError(dataset, failure_code) from None


def dry_run_reference_dataset(dataset: str, source_path: str | Path) -> ImportSummary:
    return import_reference_dataset(dataset, source_path, dry_run=True)


def import_all_reference_data(data_dir: str | Path, *, dry_run: bool = True) -> dict[str, ImportSummary]:
    base = Path(data_dir)
    return {
        dataset: import_reference_dataset(dataset, base / filename, dry_run=dry_run)
        for dataset, filename in DATASET_FILES.items()
    }
