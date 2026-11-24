"""Roster data scope: own and explicitly granted departments plus appointed projects.

Opt-in via the existing scope field; no schema change or automatic grant repair.
Basic workflow rights are derived, never stored as professional appointments.
"""
from ...extensions import db
from ...models import ProjectStep, Report, user_project_permissions

SCOPE_TYPE = 'department_project'
APPOINTMENT_STEPS = frozenset({'data_entry', 'entrust_review', 'report_review', 'report_approval'})
BASIC_STEPS = frozenset({'entrust_register', 'sample_inbound', 'sample_outbound', 'report_print'})


def uses_department_project_scope(user):
    from ...organization_privileges import has_full_platform_authority
    return bool(user and not has_full_platform_authority(user)
                and getattr(user, 'data_scope_type', '') == SCOPE_TYPE)


def appointed_project_ids(user):
    if not user or not user.enabled:
        return set()
    return {row[0] for row in db.session.query(ProjectStep.project_id)
            .join(user_project_permissions, user_project_permissions.c.project_step_id == ProjectStep.id)
            .filter(user_project_permissions.c.user_id == user.id,
                    ProjectStep.step_code.in_(APPOINTMENT_STEPS)).distinct().all()}


def project_is_visible(user, project, appointed=None):
    if not user or not user.enabled or project is None:
        return False
    if user.department_id and project.department_id == user.department_id:
        return True
    return project.id in (appointed_project_ids(user) if appointed is None else appointed)


def visible_department_names(user):
    """Data grants augment the roster's home scope, never its workflow rights."""
    if not user or not user.enabled:
        return set()
    names = set(user.data_department_names())
    if user.department:
        names.add(user.department.name)
    return names


def report_is_visible(user, report, appointed=None):
    if not user or not user.enabled or report is None:
        return False
    if report.department in visible_department_names(user):
        return True
    return _report_in_appointed_projects(user, report, appointed)


def _report_in_appointed_projects(user, report, appointed=None):
    if not report.department:
        return False
    from ...authorization_scope import project_for_report
    project = project_for_report(report)
    return bool(project and project.id in (appointed_project_ids(user) if appointed is None else appointed))


def scoped_report_query(query, user):
    if not user or not user.enabled:
        return query.filter(db.false())
    names = visible_department_names(user)
    own = Report.department.in_(names) if names else db.false()
    appointed = appointed_project_ids(user)
    if not appointed:
        return query.filter(own)
    # Use the existing unique-project resolver rather than loose report-number
    # prefixes. Filter IDs before callers paginate/count; never expose raw rows.
    foreign = query.filter(db.or_(Report.department.is_(None), ~Report.department.in_(names))) if names else query
    from ...list_page_access import identity_rows
    allowed = [row.id for row in identity_rows(foreign) if _report_in_appointed_projects(user, row, appointed)]
    return query.filter(db.or_(own, Report.id.in_(allowed)))
