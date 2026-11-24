"""Explicit one-time rollout of the two user-approved grants, never startup repair."""
from .extensions import db
from .models import User, Permission, user_action_permissions, user_permissions
from .report_delivery import SEALED_DOWNLOAD, RELEASE_ACTION


def grant_existing_users():
    from .models import OperationAudit
    from .audit import add_operation_audit
    marker = 'report.delivery.initial_grants'
    if OperationAudit.query.filter_by(action=marker, object_type='system', object_id='delivery-v1').first():
        return []
    changes = []
    # The release page is only a navigation prerequisite; action remains separately revocable.
    if not db.session.get(Permission, 'report.release.view'):
        db.session.add(Permission(code='report.release.view', name='报告发放', ptype='page'))
        db.session.flush()
    for user in User.query.order_by(User.id):
        for code in (SEALED_DOWNLOAD, RELEASE_ACTION):
            if not db.session.execute(db.select(user_action_permissions.c.user_id).where(
                user_action_permissions.c.user_id == user.id,
                user_action_permissions.c.action_code == code)).first():
                db.session.execute(user_action_permissions.insert().values(user_id=user.id, action_code=code))
                changes.append({'userId':user.id, 'action':code})
        if not db.session.execute(db.select(user_permissions.c.user_id).where(
            user_permissions.c.user_id == user.id,
            user_permissions.c.permission_code == 'report.release.view')).first():
            db.session.execute(user_permissions.insert().values(user_id=user.id, permission_code='report.release.view'))
            changes.append({'userId':user.id, 'page':'report.release.view'})
    add_operation_audit(marker, 'system', 'delivery-v1', category='permission',
                        after={'inserted': changes}, message='User authorized one-time grants to all existing accounts')
    return changes



FIELDS = {'sealedReportDownload': SEALED_DOWNLOAD, 'reportDistribution': RELEASE_ACTION}


def authorization_payload(user):
    codes = {row[0] for row in db.session.execute(db.select(user_action_permissions.c.action_code).where(
        user_action_permissions.c.user_id == user.id))}
    from .organization_privileges import has_full_platform_authority
    return {**{field: code in codes for field, code in FIELDS.items()},
            'reportDeliveryInherited': has_full_platform_authority(user)}


def assign_authorizations(user, body):
    from .audit import add_operation_audit
    before = authorization_payload(user)
    for field, code in FIELDS.items():
        if field not in body:
            continue
        assert type(body[field]) is bool
        db.session.execute(user_action_permissions.delete().where(
            user_action_permissions.c.user_id == user.id,
            user_action_permissions.c.action_code == code))
        if body[field]:
            db.session.execute(user_action_permissions.insert().values(user_id=user.id, action_code=code))
        add_operation_audit('organization.member.' + code, 'user', user.id,
            category='security', before={field: before[field]}, after={field: body[field]})
