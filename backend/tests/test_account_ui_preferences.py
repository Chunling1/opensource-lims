import pytest
from app.extensions import db
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture()
def identity(isolated_client, scenario_factory):
    department = scenario_factory.department()
    users = [scenario_factory.user(department), scenario_factory.user(department)]
    db.session.commit()
    return isolated_client, users


def headers(user):
    return {'Authorization': 'Bearer ' + issue_token(user)}


def read(client, user):
    response = client.get('/api/auth/profile', headers=headers(user)).get_json()
    assert response['code'] == 0, response
    return response['data']['uiPreferences']


def test_account_preferences_survive_new_session_and_remain_isolated(identity):
    client, (user, other) = identity
    settings = {'columns': ['code', 'reportCode'], 'pageSize': 25, 'sort': 'code', 'direction': 'desc'}
    response = client.put('/api/auth/ui-preferences', headers=headers(user), json={'key':'review.samples', 'settings':settings})
    assert response.status_code == 200
    # Read with a newly issued token and a fresh DB session, as on another browser.
    user_id, other_id = user.id, other.id
    db.session.remove()
    from app.models import User
    assert read(client, db.session.get(User, user_id)) == {'review.samples':settings}
    assert read(client, db.session.get(User, other_id)) == {}


def test_introduced_column_marker_preserves_explicit_hiding(identity):
    client, (user, _) = identity
    settings = {'columns': ['code'], 'introducedColumns': ['reportCode']}
    assert client.put('/api/auth/ui-preferences', headers=headers(user), json={'key':'list:flow','settings':settings}).status_code == 200
    assert read(client,user)['list:flow'] == settings
    for invalid in (['reportCode','reportCode'],['../invalid'],'reportCode'):
        assert client.put('/api/auth/ui-preferences', headers=headers(user), json={'key':'list:flow','settings':{'introducedColumns':invalid}}).status_code == 400


def test_independent_tables_and_personal_profile_do_not_overwrite_each_other(identity):
    client, (user, _) = identity
    for key in ('review.samples', 'registration.samples'):
        assert client.put('/api/auth/ui-preferences', headers=headers(user), json={'key':key, 'settings':{'columns':['code']}}).status_code == 200
    response = client.put('/api/auth/personal-profile', headers=headers(user), json={'phone':'13800000000', 'email':'test@example.com', 'avatar':''}).get_json()
    assert response['code'] == 0, response
    assert set(read(client, user)) == {'review.samples', 'registration.samples'}
    client.put('/api/auth/ui-preferences', headers=headers(user), json={'key':'review.samples', 'settings':{'columns':['code','name']}})
    personal = client.get('/api/auth/personal-profile', headers=headers(user)).get_json()['data']
    assert personal['phone'] == '13800000000'
    assert read(client, user)['registration.samples'] == {'columns':['code']}


@pytest.mark.parametrize('body', [None, [], {}, {'key':'x','settings':{'columns':['code']},'userId':2},
    {'key':'../x','settings':{'columns':['code']}}, {'key':'x','settings':{'pageSize':0}},
    {'key':'x','settings':{'pageSize':True}}, {'key':'x','settings':{'columns':['code','code']}},
    {'key':'x','settings':{'permissions':['admin']}}, {'key':'x','settings':{'direction':'sideways'}}])
def test_invalid_preferences_cannot_change_accounts_or_business_settings(identity, body):
    client, (user, _) = identity
    response = client.put('/api/auth/ui-preferences', headers=headers(user), json=body)
    assert response.status_code == 400
    assert read(client, user) == {}


def test_anonymous_preferences_are_rejected(identity):
    client, _ = identity
    response = client.put('/api/auth/ui-preferences', json={'key':'x','settings':{'columns':['code']}}).get_json()
    assert response['code'] == 401
