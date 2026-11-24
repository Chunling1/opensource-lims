"""Full platform authority follows enabled admin identity or direct company membership.

No grants are persisted: moving an ordinary account out of the company root
removes inherited authority on the next request.
"""

ROOT_DEPARTMENT_CODE = "ROOT"
ROOT_DEPARTMENT_NAME = "示例检测机构"


def department_has_org_wide_scope(department):
    return bool(department and (
        department.code == ROOT_DEPARTMENT_CODE
        or department.name == ROOT_DEPARTMENT_NAME
    ))


def has_full_platform_authority(user):
    return bool(user and getattr(user, "enabled", False) and (
        str(getattr(user, "role_key", "") or "").strip() == "admin"
        or str(getattr(user, "account", "") or "").strip() == "admin"
        or department_has_org_wide_scope(getattr(user, "department", None))
    ))
