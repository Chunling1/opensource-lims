"""High-level identity policy used by business application services.

Page administration, business-data scope and workflow-date overrides are
independent capabilities.  Keeping them separate prevents a user-management
permission from silently widening access to inspection records.
"""

from __future__ import annotations

from collections.abc import Iterable

from .service import department_has_org_wide_scope
from ...organization_privileges import has_full_platform_authority


def is_platform_administrator(user) -> bool:
    """Admin authority includes enabled, direct company-root members."""
    return has_full_platform_authority(user)


def can_manage_users(user) -> bool:
    """User administration does not imply access to business records."""

    return is_platform_administrator(user) or _has_permission(
        user, "system.user.view"
    )


def has_org_wide_business_scope(user) -> bool:
    """Return the explicit organization-wide *business* data capability."""

    if not user:
        return False
    from ...admin_corrections import can_correct_business_data
    if can_correct_business_data(user):
        return True
    from .department_project_scope import uses_department_project_scope
    if uses_department_project_scope(user):
        return is_platform_administrator(user)
    return bool(
        is_platform_administrator(user)
        or str(getattr(user, "data_scope_type", "") or "").strip() == "all"
        or department_has_org_wide_scope(getattr(user, "department", None))
    )


def can_override_workflow_date(user) -> bool:
    """Retired permission: date ordering is mandatory for every account."""
    return False


def has_function_permission(user, *permission_codes: str) -> bool:
    """Check one of the requested page permissions without widening scope."""

    if is_platform_administrator(user):
        return True
    wanted = {str(code).strip() for code in permission_codes if str(code).strip()}
    return bool(wanted and wanted.intersection(_permission_codes(user)))


def has_action_permission(user, *action_codes: str) -> bool:
    """Check one of the requested action permissions."""

    if is_platform_administrator(user):
        return True
    wanted = {str(code).strip() for code in action_codes if str(code).strip()}
    return bool(wanted and wanted.intersection(_action_codes(user)))


def _permission_codes(user) -> set[str]:
    if not user:
        return set()
    values: Iterable[str] = user.permission_codes()
    return {str(value) for value in values}


def _action_codes(user) -> set[str]:
    if not user:
        return set()
    values: Iterable[str] = user.action_codes()
    return {str(value) for value in values}


def _has_permission(user, code: str) -> bool:
    return code in _permission_codes(user)


def _has_action(user, code: str) -> bool:
    return code in _action_codes(user)


__all__ = [
    "can_manage_users",
    "can_override_workflow_date",
    "has_action_permission",
    "has_function_permission",
    "has_org_wide_business_scope",
    "is_platform_administrator",
]
