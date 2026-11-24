"""Quality-resource owner Commands used by other business modules."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ...audit import add_operation_audit
from ...extensions import db
from ...models import (
    CapabilityEntry,
    EquipmentUsageRecord,
    Personnel,
    Report,
    Standard,
    StdLibraryItem,
    user_standard_denials,
)


PERSONNEL_PROFILE_FIELDS = {
    "gender": "gender",
    "education": "education",
    "title": "title",
    "major": "major",
    "gradTime": "grad_time",
    "position": "position",
    "testScope": "test_scope",
    "checkScope": "check_scope",
    "remark": "remark",
    "birthDate": "birth_date",
    "idNo": "id_no",
    "ethnicity": "ethnicity",
    "nativePlace": "native_place",
    "political": "political",
    "school": "school",
    "workStartTime": "work_start_time",
    "joinTime": "join_time",
}


STANDARD_REPLACEMENT_SCHEMA = "lims.standard-library-replacement.v1"
STANDARD_REPLACEMENT_ROW_FIELDS = {
    "controlledNo", "code", "name", "authKind", "outOfScope", "category",
    "useDepts", "remark", "isEnglish", "cma", "cnas", "oneLibrary",
    "sourceRows",
}


@dataclass
class StandardLibraryReplacementSummary:
    source_payload_sha256: str
    source_workbook_sha256: str
    source_rows: int
    canonical_rows: int
    master_created: int = 0
    master_updated: int = 0
    master_restored: int = 0
    master_retired: int = 0
    library_created: int = 0
    library_updated: int = 0
    library_restored: int = 0
    library_consolidated: int = 0
    library_retired: int = 0
    capability_links_remapped: int = 0
    denial_links_remapped: int = 0
    active_master_after: int = 0
    active_library_after: int = 0
    dry_run: bool = True

    def as_dict(self):
        return asdict(self)


def _load_standard_replacement_payload(source_path: Path) -> tuple[dict, str]:
    raw = source_path.read_bytes()
    payload_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("标准库替换文件不是有效 UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("schemaVersion") != STANDARD_REPLACEMENT_SCHEMA:
        raise ValueError("标准库替换文件契约不匹配")
    source = payload.get("sourceWorkbook")
    rows = payload.get("rows")
    if not isinstance(source, dict) or not isinstance(rows, list) or not rows:
        raise ValueError("标准库替换文件缺少来源或数据行")
    if len(rows) > 10000:
        raise ValueError("标准库替换文件数据行超出上限")
    source_hash = str(source.get("sha256") or "").lower()
    if len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
        raise ValueError("来源工作簿 SHA256 无效")
    seen_codes = set()
    limits = {
        "controlledNo": 40,
        "code": 160,
        "name": 400,
        "authKind": 60,
        "category": 120,
    }
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) != STANDARD_REPLACEMENT_ROW_FIELDS:
            raise ValueError(f"第 {index} 条标准字段不符合替换契约")
        code = row.get("code")
        name = row.get("name")
        if not isinstance(code, str) or not code.strip() or not isinstance(name, str) or not name.strip():
            raise ValueError(f"第 {index} 条标准缺少编号或名称")
        if code != code.strip() or name != name.strip() or code in seen_codes:
            raise ValueError(f"第 {index} 条标准编号重复或未规范化")
        seen_codes.add(code)
        for field, maximum in limits.items():
            value = row.get(field)
            if not isinstance(value, str) or len(value) > maximum:
                raise ValueError(f"第 {index} 条标准字段 {field} 无效或过长")
        if not isinstance(row.get("remark"), str):
            raise ValueError(f"第 {index} 条标准备注无效")
        if not isinstance(row.get("useDepts"), list) or any(
            not isinstance(value, str) or not value.strip() for value in row["useDepts"]
        ):
            raise ValueError(f"第 {index} 条标准授权部门无效")
        if len(row["useDepts"]) != len(set(row["useDepts"])):
            raise ValueError(f"第 {index} 条标准授权部门重复")
        if any(not isinstance(row.get(field), bool) for field in ("outOfScope", "isEnglish", "cma", "cnas", "oneLibrary")):
            raise ValueError(f"第 {index} 条标准布尔字段无效")
        if row["outOfScope"] != (not row["cma"] and not row["cnas"]):
            raise ValueError(f"第 {index} 条标准资质范围标记不一致")
        if not isinstance(row.get("sourceRows"), list) or not row["sourceRows"] or any(
            not isinstance(value, int) or value < 2 for value in row["sourceRows"]
        ):
            raise ValueError(f"第 {index} 条标准来源行无效")
    normalization = payload.get("normalization")
    if not isinstance(normalization, dict) or normalization.get("canonicalRows") != len(rows):
        raise ValueError("标准库规范化摘要与数据行数不一致")
    aliases = payload.get("codeAliases", [])
    if not isinstance(aliases, list) or len(aliases) > 10000:
        raise ValueError("标准库编号归并映射无效")
    seen_aliases = set()
    for index, alias in enumerate(aliases, start=1):
        if not isinstance(alias, dict) or set(alias) != {"fromCode", "toCode", "reason"}:
            raise ValueError(f"第 {index} 条标准编号归并映射字段无效")
        from_code = alias.get("fromCode")
        to_code = alias.get("toCode")
        reason = alias.get("reason")
        if (
            not isinstance(from_code, str) or not from_code.strip() or from_code != from_code.strip()
            or not isinstance(to_code, str) or not to_code.strip() or to_code != to_code.strip()
            or not isinstance(reason, str) or not reason.strip() or len(reason) > 60
            or len(from_code) > 200 or len(to_code) > 200
            or from_code == to_code or from_code in seen_codes or to_code not in seen_codes
            or from_code in seen_aliases
        ):
            raise ValueError(f"第 {index} 条标准编号归并映射无效")
        seen_aliases.add(from_code)
    return payload, payload_sha256


def replace_standard_library(source_path: Path, *, apply_changes: bool = False) -> StandardLibraryReplacementSummary:
    """Replace the quality-owned standard projections without breaking historical links."""

    # v1 merges records by code and rewrites their capability links, which is
    # incompatible with the approved v2 controlled-version source ownership.
    from .testing_locations import require_legacy_catalog_write_allowed
    require_legacy_catalog_write_allowed()
    payload, payload_sha256 = _load_standard_replacement_payload(source_path)
    rows = payload["rows"]
    source_codes = {row["code"] for row in rows}
    code_aliases = payload.get("codeAliases", [])
    source_workbook = payload["sourceWorkbook"]
    summary = StandardLibraryReplacementSummary(
        source_payload_sha256=payload_sha256,
        source_workbook_sha256=source_workbook["sha256"],
        source_rows=int(source_workbook.get("sourceRows") or 0),
        canonical_rows=len(rows),
        dry_run=not apply_changes,
    )
    before = {
        "activeMaster": Standard.query.filter(Standard.deleted_at.is_(None)).count(),
        "activeLibrary": StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).count(),
    }
    now = datetime.utcnow()
    all_masters = Standard.query.order_by(Standard.id).all()
    masters_by_code = {row.code: row for row in all_masters}
    all_library = StdLibraryItem.query.order_by(StdLibraryItem.id).all()
    library_by_code: dict[str, list[StdLibraryItem]] = {}
    for item in all_library:
        library_by_code.setdefault(item.code or "", []).append(item)
    capability_counts = dict(
        db.session.query(CapabilityEntry.standard_item_id, db.func.count(CapabilityEntry.id))
        .filter(CapabilityEntry.standard_item_id.is_not(None))
        .group_by(CapabilityEntry.standard_item_id)
        .all()
    )

    canonical_items: dict[str, StdLibraryItem] = {}

    def remap_denials(source_item_id: int, target_item_id: int) -> None:
        denial_user_ids = [
            value for (value,) in db.session.execute(
                db.select(user_standard_denials.c.user_id).where(
                    user_standard_denials.c.standard_item_id == source_item_id
                )
            )
        ]
        for user_id in denial_user_ids:
            exists = db.session.execute(
                db.select(user_standard_denials.c.user_id).where(
                    user_standard_denials.c.user_id == user_id,
                    user_standard_denials.c.standard_item_id == target_item_id,
                )
            ).first()
            if not exists:
                db.session.execute(user_standard_denials.insert().values(
                    user_id=user_id,
                    standard_item_id=target_item_id,
                ))
                summary.denial_links_remapped += 1
        db.session.execute(user_standard_denials.delete().where(
            user_standard_denials.c.standard_item_id == source_item_id
        ))

    for source in rows:
        code = source["code"]
        master = masters_by_code.get(code)
        if master is None:
            master = Standard(code=code)
            db.session.add(master)
            masters_by_code[code] = master
            summary.master_created += 1
        elif master.deleted_at is not None:
            master.deleted_at = None
            summary.master_restored += 1
        else:
            summary.master_updated += 1
        master.name = source["name"]
        master.auth_kind = source["authKind"]
        master.department = ";".join(source["useDepts"])
        master.category = source["category"]
        master.status = "现行"
        master.expired = False
        db.session.flush()

        candidates = library_by_code.get(code, [])
        controlled_no = source["controlledNo"]
        if candidates:
            item = max(
                candidates,
                key=lambda candidate: (
                    candidate.deleted_at is None,
                    capability_counts.get(candidate.id, 0),
                    (candidate.controlled_no or "") == controlled_no,
                    candidate.standard_id is not None,
                    -candidate.id,
                ),
            )
            if item.deleted_at is not None:
                item.deleted_at = None
                summary.library_restored += 1
            else:
                summary.library_updated += 1
        else:
            item = StdLibraryItem(code=code)
            db.session.add(item)
            library_by_code[code] = [item]
            summary.library_created += 1
        item.standard_id = master.id
        item.controlled_no = controlled_no
        item.code = code
        item.name = source["name"]
        item.auth_kind = source["authKind"]
        item.out_of_scope = source["outOfScope"]
        item.category = source["category"]
        item.use_depts = ";".join(source["useDepts"])
        item.remark = source["remark"]
        item.is_english = source["isEnglish"]
        db.session.flush()
        canonical_items[code] = item

        for duplicate in candidates:
            if duplicate.id == item.id:
                continue
            remapped = CapabilityEntry.query.filter_by(standard_item_id=duplicate.id).update(
                {CapabilityEntry.standard_item_id: item.id},
                synchronize_session=False,
            )
            summary.capability_links_remapped += remapped
            remap_denials(duplicate.id, item.id)
            if duplicate.deleted_at is None:
                duplicate.deleted_at = now
                summary.library_consolidated += 1

    for alias in code_aliases:
        target = canonical_items[alias["toCode"]]
        for old_item in library_by_code.get(alias["fromCode"], []):
            remapped = CapabilityEntry.query.filter_by(standard_item_id=old_item.id).update(
                {
                    CapabilityEntry.standard_item_id: target.id,
                    CapabilityEntry.standard_code: alias["toCode"],
                },
                synchronize_session=False,
            )
            summary.capability_links_remapped += remapped
            remap_denials(old_item.id, target.id)

    for master in all_masters:
        if master.code not in source_codes and master.deleted_at is None:
            master.deleted_at = now
            master.status = "已停用"
            summary.master_retired += 1
    for item in all_library:
        if item.code not in source_codes and item.deleted_at is None:
            item.deleted_at = now
            summary.library_retired += 1

    db.session.flush()
    summary.active_master_after = Standard.query.filter(Standard.deleted_at.is_(None)).count()
    summary.active_library_after = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).count()
    if summary.active_master_after != len(rows) or summary.active_library_after != len(rows):
        db.session.rollback()
        raise RuntimeError("替换后标准主表或受控表的活动记录数不等于候选记录数")

    if apply_changes:
        add_operation_audit(
            "quality.standard_library.replace",
            "standard_library",
            source_workbook["sha256"][:16],
            category="data-governance",
            before=before,
            after=summary.as_dict(),
            message=str(source_workbook.get("name") or "标准库替换"),
            trace_id=f"standard-library-{source_workbook['sha256'][:16]}",
        )
        db.session.commit()
    else:
        db.session.rollback()
    return summary


def synchronize_personnel_record(user, profile: dict | None = None) -> Personnel:
    """Keep the quality roster projection aligned with one login identity."""

    profile = profile if isinstance(profile, dict) else {}
    active = Personnel.query.filter(
        db.func.lower(Personnel.code) == user.account.lower(),
        Personnel.deleted_at.is_(None),
    ).order_by(Personnel.id).first()
    person = active or Personnel.query.filter(
        db.func.lower(Personnel.code) == user.account.lower(),
        Personnel.deleted_at.is_not(None),
    ).order_by(Personnel.id).first()
    if person is None:
        person = Personnel(code=user.account)
        db.session.add(person)
        roster_was_removed = False
    else:
        roster_was_removed = person.deleted_at is not None
    previous_department = (person.dept or "").strip()
    department_name = user.department.name if user.department else ""
    if not roster_was_removed or user.enabled:
        person.deleted_at = None
    person.code = user.account
    person.name = user.name
    person.dept = department_name
    if not (person.assigned_depts or "").strip() or previous_department != department_name:
        person.assigned_depts = department_name
    if not (person.position or "").strip() and user.role_name:
        person.position = user.role_name
    for payload_key, model_attr in PERSONNEL_PROFILE_FIELDS.items():
        if payload_key in profile:
            setattr(person, model_attr, profile.get(payload_key))
    return person


def move_linked_personnel_department(user, department) -> None:
    """Move all active roster projections linked to an internal account."""

    for person in Personnel.query.filter(
        db.func.lower(Personnel.code) == user.account.lower(),
        Personnel.deleted_at.is_(None),
    ).all():
        person.dept = department.name
        person.assigned_depts = department.name


def map_capability_entry_departments(
    entry: CapabilityEntry,
    departments: list,
) -> CapabilityEntry:
    """Set the quality-owned capability-to-department projection."""

    entry.departments = departments
    entry.mapping_status = "confirmed" if departments else "pending"
    return entry


def apply_personnel_authorization_projection(
    personnel: Personnel,
    *,
    permission_labels: set[str],
    department_names: set[str],
) -> tuple[bool, bool]:
    """Merge appointment-derived labels into the quality roster projection."""

    def merge(value: str | None, additions: set[str]) -> tuple[str, bool]:
        items = [part.strip() for part in (value or "").split(";") if part.strip()]
        before = list(items)
        for addition in sorted(additions):
            if addition not in items:
                items.append(addition)
        return ";".join(items), items != before

    personnel.permissions, permissions_changed = merge(
        personnel.permissions, permission_labels
    )
    personnel.assigned_depts, departments_changed = merge(
        personnel.assigned_depts, department_names
    )
    return permissions_changed, departments_changed


def create_personnel_roster_entry(*, name: str, code: str, department: str) -> Personnel:
    """Create a quality roster row without committing the caller transaction."""

    person = Personnel(
        name=name,
        code=code,
        dept=department,
        assigned_depts=department,
    )
    db.session.add(person)
    return person


def sync_equipment_usage_records(
    report: Report,
    equipment_rows: Iterable,
    *,
    used_from: str,
    used_to: str,
    actor_account: str,
    actor_name: str,
    interval_end,
) -> None:
    """Upsert the quality-owned equipment usage projection without committing."""

    for equipment in equipment_rows:
        usage = EquipmentUsageRecord.query.filter_by(
            equipment_id=equipment.id, report_no=report.report_no
        ).first()
        if usage is None:
            usage = EquipmentUsageRecord(
                equipment_id=equipment.id, report_no=report.report_no
            )
            db.session.add(usage)
        usage.sample_no = report.sample_no
        usage.project = report.project or report.project_name
        usage.used_from = used_from
        usage.used_to = used_to
        usage.used_by_account = actor_account
        usage.used_by_name = actor_name
        usage.status_at_use = equipment.effective_status(interval_end)
