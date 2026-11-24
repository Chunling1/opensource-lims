"""Identity, data-scope and project-step authorization facade."""

from .access import (
    can_manage_users,
    can_override_workflow_date,
    has_action_permission,
    has_function_permission,
    has_org_wide_business_scope,
    is_platform_administrator,
)
from .authentication import authenticate_internal_user

from .service import (
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
from .department_sync import synchronize_user_department
from .personnel_login import personnel_login, update_personnel_login

__all__ = [name for name in globals() if not name.startswith("_")]
