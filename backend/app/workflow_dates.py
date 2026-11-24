from datetime import UTC, date, datetime, timedelta, timezone

from .models import OperationAudit
from .organization_privileges import has_full_platform_authority

BUSINESS_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


def is_super_admin(user):
    """Compatibility predicate for administrator/company-root authority.

    ``system.user.view`` is a user-management page permission.  It must not
    silently grant business-data scope or workflow-date overrides.
    """

    return has_full_platform_authority(user)


def can_override_workflow_date(user):
    # Business decision 2026-11-07: nobody may waive chronological ordering.
    return False


def business_date(value):
    if not isinstance(value, datetime):
        return parse_date(value)
    moment = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return moment.astimezone(BUSINESS_TIMEZONE).date()


def business_today():
    return datetime.now(BUSINESS_TIMEZONE).date()


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def latest_workflow_date(object_type, object_id, action):
    event = (
        OperationAudit.query.filter_by(
            category="workflow",
            object_type=object_type,
            object_id=str(object_id),
            action=action,
            success=True,
        )
        .order_by(OperationAudit.created_at.desc(), OperationAudit.id.desc())
        .first()
    )
    return business_date(event.created_at) if event and event.created_at else None


def validate_after_previous(user, value, previous_date, field_label, previous_label):
    from .report_date_rules import ordered_pair
    return ordered_pair(value, previous_date, field_label, previous_label, required=True)
