from app.extensions import db
from app.models import Personnel
from testkit.factories import login_headers

pytest_plugins = ('testkit.fixtures',)


def test_maintain_roster_then_bind_without_mask_overwrite(isolated_client, scenario_factory):
    scenario = scenario_factory.identity_scenario()
    user = scenario.user
    admin = scenario_factory.user(scenario.department, role_key='admin')
    person = Personnel(name=user.name, code=user.account, dept=scenario.department.name)
    db.session.add(person)
    db.session.commit()
    endpoint = f'/api/quality/personnel/{person.id}'
    binding = f'/api/esign/admin/bindings/{user.id}'
    headers = login_headers(isolated_client, admin.account)
    values = {'legalName': user.name, 'psnAccount': '13800000009', 'status': 'pending'}
    assert '名册手机号' in isolated_client.put(binding, headers=headers, json=values).json['message']
    assert isolated_client.put(endpoint, headers=headers, json={'mobile': values['psnAccount']}).json['code'] == 0
    assert isolated_client.put(endpoint, headers=headers, json={'mobile': '13*******09', 'remark': 'test'}).json['code'] == 0
    assert isolated_client.put(binding, headers=headers, json={**values, 'psnAccount': '13800000008'}).json['code'] != 0
    result = isolated_client.put(binding, headers=headers, json=values).json
    assert result['code'] == 0 and result['data']['status'] == 'pending'
