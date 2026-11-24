"""Small, paged organization directory for explicit administrator selections."""
from sqlalchemy import or_
from ..models import User, Department


def options(kind, keyword, page):
    if kind == "people":
        query = User.query.outerjoin(Department, User.department_id == Department.id)
        if keyword:
            query = query.filter(or_(User.name.contains(keyword, autoescape=True),
                                     User.account.contains(keyword, autoescape=True),
                                     Department.name.contains(keyword, autoescape=True)))
        total = query.count()
        rows = query.with_entities(User.id, User.name, User.account, User.enabled,
                                   Department.id.label("dept_id"), Department.name.label("dept_name"))
        rows = rows.order_by(User.id).offset((page - 1) * 20).limit(20).all()
        return dict(rows=[dict(id=r.id, name=r.name, account=r.account, enabled=r.enabled,
                               departmentId=r.dept_id, department=r.dept_name or "") for r in rows], total=total, page=page)
    if kind != "departments":
        raise ValueError("选择类型无效")
    query = Department.query
    if keyword:
        query = query.filter(or_(Department.name.contains(keyword, autoescape=True), Department.code.contains(keyword, autoescape=True)))
    total = query.count()
    rows = query.order_by(Department.id).offset((page - 1) * 20).limit(20).all()
    return dict(rows=[dict(id=r.id, name=r.name, code=r.code) for r in rows], total=total, page=page)


def selected_id(value, model, label):
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError(f"请从组织机构选择{label}")
    row = model.query.filter_by(id=int(value)).first()
    if row is None:
        raise ValueError(f"所选{label}不存在，请重新选择")
    return row


def apply_selection(detail, previous, names_changed, department_changed):
    from ..sample_entrust import registrar_identity, write_sample_registrar, write_registrar_ids
    info = (detail.get("entrustSnapshot") or {}).get("info") or {}
    old_info = (previous.get("entrustSnapshot") or {}).get("info") or {}
    user_id = info.get("sampleRegistrarUserId")
    department_id = info.get("sampleRegistrarDepartmentId")
    user_changed = str(user_id or "") != str(old_info.get("sampleRegistrarUserId") or "")
    dept_changed = str(department_id or "") != str(old_info.get("sampleRegistrarDepartmentId") or "")
    if not (user_changed or dept_changed or names_changed or department_changed):
        return None
    name, account, department = registrar_identity(previous)
    if user_changed or names_changed:
        user = selected_id(user_id, User, "登记人")
        name, account = user.name, user.account
        if not dept_changed and not department_changed:
            department_id = user.department_id
            department = user.department.name if user.department else ""
    if (dept_changed or department_changed) and not (user_changed and not department_id):
        dept = selected_id(department_id, Department, "登记部门")
        department = dept.name
    result = write_sample_registrar(detail, name, account, department)
    return write_registrar_ids(result, user_id, department_id)
