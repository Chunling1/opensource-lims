"""Compatibility boundary for authorization and data-scope rules.

The implementation deliberately delegates to ``app.authorization_scope`` in
phase one.  This makes the supported contract explicit while preserving the
existing, production-verified rules and immediate permission revocation.
"""

from ...authorization_scope import (
    PROJECT_STEP_FUNCTION_PERMISSIONS,
    all_standard_items,
    denied_standard_item_ids,
    department_has_org_wide_scope,
    department_projects,
    department_standard_items,
    project_for_report,
    project_step_error,
    project_step_matches_permissions,
    replace_standard_authorizations,
    scoped_standard_items,
    standard_authorization_payload,
    standard_is_authorized,
    standard_matches_department,
    user_has_org_wide_scope,
    user_has_project_step,
    validate_project_department,
    validate_project_selection,
)

__all__ = [name for name in globals() if not name.startswith("_")]
