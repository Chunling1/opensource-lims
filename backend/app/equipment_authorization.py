"""Personal equipment-use grants; independent of business-data and ledger access."""
from .extensions import db
from .models import Department, user_equipment_departments
from .organization_privileges import has_full_platform_authority


def granted_department_ids(user):
    return sorted(db.session.execute(db.select(user_equipment_departments.c.department_id).where(
        user_equipment_departments.c.user_id == user.id)).scalars())


def authorization_payload(user):
    return {"equipmentDepartmentIds": granted_department_ids(user),
            "equipmentAuthorizationInherited": has_full_platform_authority(user)}


def validate_department_ids(value):
    if not isinstance(value, list) or any(type(item) is not int or item <= 0 for item in value):
        raise ValueError("仪器授权必须为部门 ID 列表")
    ids = set(value)
    existing = {row.id for row in Department.query.filter(Department.id.in_(ids)).all()} if ids else set()
    if ids != existing:
        raise ValueError("仪器授权包含不存在的部门，请刷新后重新选择")
    return sorted(ids)


def assign(user, ids):
    from .audit import add_operation_audit
    before = granted_department_ids(user)
    db.session.execute(user_equipment_departments.delete().where(user_equipment_departments.c.user_id == user.id))
    if ids:
        db.session.execute(user_equipment_departments.insert(),
                           [{"user_id": user.id, "department_id": value} for value in ids])
    add_operation_audit("organization.member.equipment_authorize", "user", user.id,
                        category="security", before={"departmentIds": before}, after={"departmentIds": ids})


def usable_department_names(user):
    # Existing global equipment-ledger authority is retained. Report/data visibility
    # alone never confers the ability to choose another department's instruments.
    if has_full_platform_authority(user) or "quality.equipment_ledger.view" in user.permission_codes():
        return None
    ids = set(granted_department_ids(user))
    if user.department_id:
        ids.add(user.department_id)
    return {row.name for row in Department.query.filter(Department.id.in_(ids)).all() if row.name}


def saved_equipment_ids(report):
    values = (report.detail or {}).get("checkInput", {}).get("equipmentIds") or []
    return {int(value) for value in values if str(value).isdigit()}


def unauthorized_new_equipment(user, report, rows):
    departments = usable_department_names(user)
    saved = saved_equipment_ids(report)
    return [] if departments is None else [row for row in rows if row.id not in saved and row.dept not in departments]
