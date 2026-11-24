"""Explicit seal authority and version-bound confirmation; no provider I/O."""
from .extensions import db
from .models import user_action_permissions
from .esign_access import report_scope_error

PERMISSION = 'report.seal.confirm'


def has_permission(user):
    # Even an administrator must be appointed to use the organization's seal.
    from .preflight_reads import read_once
    return bool(user and user.enabled and read_once(('seal-explicit-permission', user.id), lambda: db.session.execute(
        db.select(user_action_permissions.c.user_id).where(
            user_action_permissions.c.user_id == user.id,
            user_action_permissions.c.action_code == PERMISSION,
    )).first()))


def assign(user, enabled):
    db.session.execute(user_action_permissions.delete().where(
        user_action_permissions.c.user_id == user.id,
        user_action_permissions.c.action_code == PERMISSION))
    if enabled:
        db.session.execute(user_action_permissions.insert().values(user_id=user.id, action_code=PERMISSION))


def access_error(user, report):
    error = report_scope_error(user, report)
    if error:
        return error
    if not has_permission(user):
        return '未获签章确认权限，请在组织机构人员授权中配置'
    if report.voided or report.status != '待打印' or not report.approved_document_version_id:
        return '报告不在当前批准后的签发阶段，不能签章确认'
    return ''
