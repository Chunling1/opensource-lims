from __future__ import annotations

import json
import csv
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func

from .applications.quality_resources import create_personnel_roster_entry
from .platform.audit import add_operation_audit
from .extensions import db
from .models import Department, Permission, Personnel, User, user_data_departments
from .security import hash_password, verify_password
from .platform.identity.login_security import initial_password

ACCOUNT_PATTERN = re.compile(r"^[a-z0-9._-]+$")
DEFAULT_SOURCE_NAME = "personnel_accounts_20260727.json"
DEPARTMENT_ALIASES = {
    "热工检测部": "热工系统检测部",
    "建筑声学检测部": "综合检测部",
    "建筑智能与电气检测部": "建筑智能电气检测部",
}


class PersonnelAccountImportError(ValueError):
    pass


@dataclass(frozen=True)
class RosterEntry:
    name: str
    code: str
    department: str
    source_rows: tuple[int, ...]


@dataclass
class PersonnelAccountImportSummary:
    source_rows: int = 0
    unique_personnel: int = 0
    duplicate_source_rows: int = 0
    personnel_matched_existing: int = 0
    personnel_to_create: int = 0
    personnel_created: int = 0
    personnel_updated: int = 0
    personnel_unchanged: int = 0
    personnel_duplicates_to_merge: int = 0
    personnel_duplicates_merged: int = 0
    accounts_matched_existing: int = 0
    accounts_to_create: int = 0
    accounts_created: int = 0
    existing_accounts_updated: int = 0
    existing_accounts_unchanged: int = 0
    dry_run: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PersonnelLoginRepairSummary:
    roster_accounts: int = 0
    protected_accounts: int = 0
    completed_password_changes: int = 0
    pending_first_login: int = 0
    explicitly_reset_accounts: int = 0
    passwords_to_repair: int = 0
    passwords_repaired: int = 0
    accounts_to_unlock: int = 0
    accounts_unlocked: int = 0
    accounts_to_enable: int = 0
    accounts_enabled: int = 0
    missing_accounts: int = 0
    dry_run: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_department(value: str) -> str:
    name = value.strip()
    if name.startswith("空调设备检测部-"):
        return "空调设备检测部"
    return DEPARTMENT_ALIASES.get(name, name)


def load_roster(source_path: str | Path) -> list[RosterEntry]:
    path = Path(source_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PersonnelAccountImportError("人员账号源文件无法读取") from exc
    if not isinstance(payload, list):
        raise PersonnelAccountImportError("人员账号源文件必须是数组")

    entries: dict[str, RosterEntry] = {}
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            raise PersonnelAccountImportError(f"源数据第 {index} 条不是对象")
        name = str(raw.get("name") or "").strip()
        code = str(raw.get("code") or raw.get("account") or "").strip().lower()
        department = _canonical_department(str(raw.get("department") or raw.get("dept") or ""))
        source_rows_raw = raw.get("sourceRows") or [index]
        if not isinstance(source_rows_raw, list) or not source_rows_raw:
            raise PersonnelAccountImportError(f"编号 {code or index} 缺少来源行号")
        try:
            source_rows = tuple(sorted({int(value) for value in source_rows_raw}))
        except (TypeError, ValueError) as exc:
            raise PersonnelAccountImportError(f"编号 {code or index} 的来源行号无效") from exc

        if not name or not code or not department:
            raise PersonnelAccountImportError(f"源数据第 {index} 条缺少姓名、编号或部门")
        if len(code) > 40 or not ACCOUNT_PATTERN.fullmatch(code):
            raise PersonnelAccountImportError(f"编号 {code} 不符合账号规则")
        if len(name) > 40:
            raise PersonnelAccountImportError(f"编号 {code} 的姓名超过系统长度限制")

        current = RosterEntry(name, code, department, source_rows)
        previous = entries.get(code)
        if previous is None:
            entries[code] = current
            continue
        if previous.name != current.name or previous.department != current.department:
            raise PersonnelAccountImportError(f"编号 {code} 存在姓名或部门冲突")
        entries[code] = RosterEntry(
            name,
            code,
            department,
            tuple(sorted(set(previous.source_rows + current.source_rows))),
        )
    return sorted(entries.values(), key=lambda entry: (entry.source_rows[0], entry.code))


def _existing_user_map() -> dict[str, User]:
    result: dict[str, User] = {}
    for user in User.query.order_by(User.id).all():
        key = user.account.strip().lower()
        if key in result:
            raise PersonnelAccountImportError(f"线上存在大小写重复账号：{key}")
        result[key] = user
    return result


def _personnel_rows(code: str) -> list[Personnel]:
    return (
        Personnel.query.filter(
            func.lower(Personnel.code) == code,
            Personnel.deleted_at.is_(None),
        )
        .order_by(Personnel.id)
        .all()
    )


def _merge_text_values(*values: str | None) -> str:
    items: list[str] = []
    for value in values:
        for item in (value or "").split(";"):
            item = item.strip()
            if item and item not in items:
                items.append(item)
    return ";".join(items)


def _merge_duplicate_personnel(primary: Personnel, duplicate: Personnel) -> None:
    preserve_fields = (
        "gender",
        "education",
        "title",
        "major",
        "grad_time",
        "position",
        "test_scope",
        "check_scope",
        "remark",
        "birth_date",
        "id_no",
        "ethnicity",
        "native_place",
        "political",
        "school",
        "work_start_time",
        "join_time",
    )
    for field in preserve_fields:
        if not getattr(primary, field) and getattr(duplicate, field):
            setattr(primary, field, getattr(duplicate, field))
    primary.permissions = _merge_text_values(primary.permissions, duplicate.permissions)
    duplicate.deleted_at = datetime.now(UTC).replace(tzinfo=None)


def _insert_department_grant(user: User, department: Department) -> None:
    db.session.execute(
        user_data_departments.insert().values(
            user_id=user.id,
            department_id=department.id,
            include_children=False,
            see_data=True,
            see_members=True,
            granted_by="personnel-import",
            granted_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
    )


def import_personnel_accounts(
    source_path: str | Path,
    *,
    apply_changes: bool = False,
    password_output: str | Path | None = None,
) -> PersonnelAccountImportSummary:
    roster = load_roster(source_path)
    summary = PersonnelAccountImportSummary(
        source_rows=sum(len(entry.source_rows) for entry in roster),
        unique_personnel=len(roster),
        duplicate_source_rows=sum(max(0, len(entry.source_rows) - 1) for entry in roster),
        dry_run=not apply_changes,
    )

    departments = {row.name: row for row in Department.query.all()}
    unknown = sorted({entry.department for entry in roster if entry.department not in departments})
    if unknown:
        raise PersonnelAccountImportError(f"存在未配置部门：{', '.join(unknown)}")

    dashboard_permission = Permission.query.filter_by(code="dashboard.view").one_or_none()
    if dashboard_permission is None:
        raise PersonnelAccountImportError("系统缺少 dashboard.view 基础权限")

    users = _existing_user_map()
    planned_personnel: dict[str, list[Personnel]] = {}
    for entry in roster:
        matches = _personnel_rows(entry.code)
        planned_personnel[entry.code] = matches
        if matches:
            summary.personnel_matched_existing += 1
            summary.personnel_duplicates_to_merge += max(0, len(matches) - 1)
        else:
            summary.personnel_to_create += 1

        existing_user = users.get(entry.code)
        if existing_user is None:
            summary.accounts_to_create += 1
        else:
            if existing_user.name.strip() != entry.name:
                raise PersonnelAccountImportError(
                    f"账号 {entry.code} 已属于其他姓名，停止导入"
                )
            summary.accounts_matched_existing += 1

    if not apply_changes:
        return summary

    if summary.accounts_to_create and not password_output:
        raise PersonnelAccountImportError("新建账号须指定 --password-output 保存随机初始密码表")
    password_file = None
    credentials = []
    if summary.accounts_to_create:
        password_file = os.fdopen(os.open(str(password_output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8-sig", newline="")
    try:
        for entry in roster:
            department = departments[entry.department]
            matches = planned_personnel[entry.code]
            if matches:
                person = matches[0]
                changed = (
                    person.name != entry.name
                    or person.code != entry.code
                    or person.dept != entry.department
                    or person.assigned_depts != entry.department
                    or len(matches) > 1
                )
                for duplicate in matches[1:]:
                    _merge_duplicate_personnel(person, duplicate)
                    summary.personnel_duplicates_merged += 1
                person.name = entry.name
                person.code = entry.code
                person.dept = entry.department
                person.assigned_depts = entry.department
                if changed:
                    summary.personnel_updated += 1
                else:
                    summary.personnel_unchanged += 1
            else:
                create_personnel_roster_entry(
                    name=entry.name,
                    code=entry.code,
                    department=entry.department,
                )
                summary.personnel_created += 1

            existing_user = users.get(entry.code)
            if existing_user is None:
                password = initial_password(entry.code)
                credentials.append((entry.code, entry.name, entry.department, password))
                user = User(
                    account=entry.code,
                    password_hash=hash_password(password),
                    name=entry.name,
                    role_key="basic",
                    role_name="基础用户",
                    home_path="/inspection/dashboard",
                    department_id=department.id,
                    data_scope_type="department",
                    data_scope_desc="仅查看本人所属部门数据",
                    enabled=True,
                    must_change_password=True,
                )
                user.permissions = [dashboard_permission]
                db.session.add(user)
                db.session.flush()
                _insert_department_grant(user, department)
                users[entry.code] = user
                summary.accounts_created += 1
            else:
                changed = (
                    existing_user.name != entry.name
                    or existing_user.department_id != department.id
                )
                existing_user.name = entry.name
                existing_user.department_id = department.id
                if changed:
                    summary.existing_accounts_updated += 1
                else:
                    summary.existing_accounts_unchanged += 1

        add_operation_audit(
            "system.personnel_accounts.import",
            "personnel_account_batch",
            Path(source_path).name,
            category="system",
            after=summary.as_dict(),
            message=(
                f"人员账号批量导入：人员 {summary.unique_personnel}，"
                f"新账号 {summary.accounts_created}"
            ),
        )
        if password_file:
            writer = csv.writer(password_file)
            writer.writerow(["账号", "姓名", "部门", "初始密码"])
            writer.writerows([["'" + str(cell) if str(cell).startswith(("=", "+", "-", "@", "\t", "\r")) else cell for cell in row] for row in credentials])
            password_file.flush()
            os.fsync(password_file.fileno())
        db.session.commit()
        return summary
    except Exception:
        db.session.rollback()
        raise
    finally:
        if password_file:
            password_file.close()


def repair_personnel_account_logins(
    source_path: str | Path,
    *,
    apply_changes: bool = False,
    protected_accounts: frozenset[str] = frozenset({"admin"}),
    reset_accounts: frozenset[str] = frozenset(),
) -> PersonnelLoginRepairSummary:
    """The old predictable-password repair has been retired."""
    raise PersonnelAccountImportError("旧登录修复入口已停用：请使用管理员登录安全页面生成随机初始密码并下载账号密码表")


__all__ = [
    "DEFAULT_SOURCE_NAME",
    "PersonnelLoginRepairSummary",
    "PersonnelAccountImportError",
    "PersonnelAccountImportSummary",
    "RosterEntry",
    "import_personnel_accounts",
    "load_roster",
    "repair_personnel_account_logins",
]
