"""Explicit correction grants maintained in organization membership."""
from .extensions import db
from .models import user_action_permissions
FIELDS = {
    "correctionApprovalLevel1": "report.correction.approve.level1",
    "correctionApprovalLevel2": "report.correction.approve.level2",
}
STORAGE_CODES = ("report.correction.approve", *FIELDS.values())


def authorization_payload(user):
    codes = {row.action_code for row in user._action_grant_rows()}
    return {field: code in codes for field, code in FIELDS.items()}


def assign(user, field, enabled):
    code = FIELDS[field]
    db.session.execute(user_action_permissions.delete().where(
        user_action_permissions.c.user_id == user.id,
        user_action_permissions.c.action_code == code))
    if enabled:
        db.session.execute(user_action_permissions.insert().values(user_id=user.id, action_code=code))
