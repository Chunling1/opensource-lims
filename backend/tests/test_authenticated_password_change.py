"""Password changes use real authentication against an isolated database."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.security import issue_token, verify_password
from app.platform.identity.login_security import LoginChallenge, _answer_hash

pytest_plugins = ('testkit.fixtures',)
OLD = 'OldSecret123!'
NEW = 'NewSecret456!'


@pytest.fixture()
def identity(isolated_client, scenario_factory):
    department = scenario_factory.department()
    user = scenario_factory.user(department, login_value=OLD)
    other = scenario_factory.user(department, login_value=OLD)
    db.session.commit()
    headers = {'Authorization': 'Bearer ' + issue_token(user)}
    return isolated_client, user, other, headers


def change(client, user, headers=None, **values):
    return client.post('/api/auth/change-password', headers=headers or {}, json={
        'account': user.account, 'oldPassword': OLD, 'newPassword': NEW, **values,
    }).get_json()


def test_authenticated_change_needs_no_captcha_and_uses_token_identity(identity):
    client, user, other, headers = identity
    assert change(client, user, headers, account=other.account)['code'] == 0
    db.session.refresh(user)
    db.session.refresh(other)
    assert verify_password(NEW, user.password_hash)
    assert verify_password(OLD, other.password_hash)
    # The old token cannot be reused after the password changes.
    assert client.get('/api/auth/profile', headers=headers).get_json()['code'] == 401


@pytest.mark.parametrize('state', ['anonymous', 'invalid-token', 'disabled', 'first-login'])
def test_only_a_valid_enabled_login_can_skip_captcha(identity, state):
    client, user, _, headers = identity
    if state == 'anonymous':
        headers = {}
    elif state == 'invalid-token':
        headers = {'Authorization': 'Bearer invalid-token'}
    elif state == 'disabled':
        user.enabled = False
    else:
        user.must_change_password = True
        headers = {}
    db.session.commit()
    expected = 401 if state in ('invalid-token', 'disabled') else 4
    assert change(client, user, headers)['code'] == expected
    db.session.refresh(user)
    assert verify_password(OLD, user.password_hash)


def test_wrong_old_password_still_locks_account(identity):
    client, user, _, headers = identity
    for attempt in range(5):
        result = change(client, user, headers, oldPassword='wrong')
        assert result['code'] == (2 if attempt == 4 else 1)
    assert change(client, user, headers)['code'] == 2
    db.session.refresh(user)
    assert verify_password(OLD, user.password_hash)


def test_password_rules_remain_enforced(identity):
    client, user, _, headers = identity
    for value in ['weak', OLD]:
        assert change(client, user, headers, newPassword=value)['code'] == 1
    db.session.refresh(user)
    assert verify_password(OLD, user.password_hash)


def test_first_login_still_accepts_valid_captcha(identity):
    client, user, _, _ = identity
    user.must_change_password = True
    identifier, answer = 'test-first-login-challenge', '1234'
    db.session.add(LoginChallenge(id=identifier, answer_hash=_answer_hash(identifier, answer),
        expires_at=datetime.utcnow() + timedelta(minutes=2), peer_address='127.0.0.1'))
    db.session.commit()
    assert change(client, user, captchaId=identifier, captcha=answer)['code'] == 0
    db.session.refresh(user)
    assert not user.must_change_password
    assert verify_password(NEW, user.password_hash)
