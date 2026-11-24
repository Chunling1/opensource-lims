"""An explicit distribution grant includes its navigation prerequisite only."""
import pytest

from app.extensions import db
from app.models import user_action_permissions
from app.platform.identity.access import has_function_permission, has_action_permission
from app.report_delivery import RELEASE_ACTION, SEALED_DOWNLOAD
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)
PAGE = 'report.release.view'


def profile(client, user):
    response = client.get('/api/auth/profile', headers={
        'Authorization': 'Bearer ' + issue_token(user)})
    assert response.status_code == 200
    assert response.json['code'] == 0
    return response.json['data']


def test_existing_action_only_grant_exposes_menu_without_persisting_or_widening_scope(
        isolated_client, scenario_factory):
    f = scenario_factory
    user = f.user(f.department(), permissions=['report.query.view'])
    before_scope = user.data_scope()
    f.grant_action(user, RELEASE_ACTION)
    db.session.commit()
    payload = profile(isolated_client, user)
    assert PAGE in payload['permissions']
    assert RELEASE_ACTION in payload['actionPermissions']
    assert SEALED_DOWNLOAD not in payload['actionPermissions']
    assert 'report.archive.view' not in payload['permissions']
    assert payload['dataScope'] == before_scope
    assert has_function_permission(user, PAGE)
    assert {p.code for p in user.permissions} == {'report.query.view'}
    # Revocation takes effect on the next identity read without a permanent page grant.
    db.session.execute(user_action_permissions.delete().where(
        user_action_permissions.c.user_id == user.id,
        user_action_permissions.c.action_code == RELEASE_ACTION))
    db.session.commit()
    assert PAGE not in profile(isolated_client, user)['permissions']
    assert not has_function_permission(user, PAGE)


@pytest.mark.parametrize('page,action', [(False, None), (False, SEALED_DOWNLOAD),
                                      (True, None), (True, RELEASE_ACTION)])
def test_page_only_download_only_and_ordinary_grants_keep_their_boundaries(
        isolated_client, scenario_factory, page, action):
    f = scenario_factory
    user = f.user(f.department(), permissions=[PAGE] if page else [])
    if action:
        f.grant_action(user, action)
    db.session.commit()
    payload = profile(isolated_client, user)
    assert (PAGE in payload['permissions']) is (page or action == RELEASE_ACTION)
    assert has_action_permission(user, RELEASE_ACTION) is (action == RELEASE_ACTION)
    assert (SEALED_DOWNLOAD in payload['actionPermissions']) is (action == SEALED_DOWNLOAD)
    if page and action == RELEASE_ACTION:
        db.session.execute(user_action_permissions.delete().where(
            user_action_permissions.c.user_id == user.id))
        db.session.commit()
        assert PAGE in profile(isolated_client, user)['permissions']
        assert not has_action_permission(user, RELEASE_ACTION)


def test_org_checkbox_roundtrip_and_other_authorization_save_keep_menu_consistent(
        isolated_client, scenario_factory):
    f = scenario_factory
    department = f.department()
    admin = f.user(department, role_key='admin')
    target = f.user(department)
    db.session.commit()
    headers = {'Authorization': 'Bearer ' + issue_token(admin)}
    url = f'/api/admin/departments/{department.id}/members/{target.id}/authorizations'
    for body, expected in [({'reportDistribution': True}, True), ({}, True),
                           ({'reportDistribution': False}, False)]:
        response = isolated_client.put(url, json=body, headers=headers)
        assert response.json['code'] == 0, response.json
        payload = profile(isolated_client, target)
        assert (PAGE in payload['permissions']) is expected
        assert (RELEASE_ACTION in payload['actionPermissions']) is expected
        assert SEALED_DOWNLOAD not in payload['actionPermissions']


def test_batched_identity_reads_do_not_leak_grants_between_users_or_requests(scenario_factory):
    from app.list_reads import reuse_list_reads, prime_identifiers
    f = scenario_factory
    department = f.department()
    granted, ordinary = f.user(department), f.user(department)
    f.grant_action(granted, RELEASE_ACTION)
    db.session.commit()

    @reuse_list_reads
    def read():
        prime_identifiers('user', [granted.id, ordinary.id])
        return [(u.permission_codes(), u.action_codes()) for u in (granted, ordinary)]

    rows = read()
    assert PAGE in rows[0][0] and RELEASE_ACTION in rows[0][1]
    assert PAGE not in rows[1][0] and RELEASE_ACTION not in rows[1][1]
    db.session.execute(user_action_permissions.delete().where(
        user_action_permissions.c.user_id == granted.id))
    db.session.commit()
    assert all(PAGE not in pages and RELEASE_ACTION not in actions for pages, actions in read())
