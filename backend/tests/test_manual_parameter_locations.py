from datetime import date
from types import SimpleNamespace as NS
import pytest
from app.applications.quality_resources import testing_locations as locations


def entry(address='虚拟地点甲'):
    return NS(active=True, mapping_status='confirmed', batch=NS(status='active'),
              departments=[NS(name='虚拟检测部')], capability_type='检测',
              effective_date=None, expires_on=None, standard_item_id=1,
              standard_item=NS(deleted_at=None, is_onsite_standard=False, use_depts='虚拟检测部'),
              item_name='温度', standard_code='GB/TEST',
              raw_cells={'standardWorkbook': {'address': address}})


def resolve(raw, entries):
    return locations.resolve_testing_location(
        dict(isOnsiteTesting=False, manualCapabilityItems=['库外一'],
             manualCapabilityReason='虚拟测试', **raw),
        entries, '虚拟检测部', date(2026, 10, 20), '检测')


def test_manual_library_inheritance_and_legacy_address():
    result = resolve({'manualParameterLocations': {'库外一': {'mode': 'library', 'addresses': []}}},
                     [entry(), entry('虚拟地点乙')])
    assert result['actualTestLocations'] == ['虚拟地点甲', '虚拟地点乙']
    with pytest.raises(ValueError, match='需先选择'):
        resolve({'manualParameterLocations': {'库外一': {'mode': 'library', 'addresses': []}}}, [])
    assert resolve({'manualTestLocation': '历史地点'}, [entry()])['testLocation'] == '虚拟地点甲；历史地点'


def test_manual_selected_locations_are_validated_against_database(monkeypatch):
    monkeypatch.setattr(locations, 'available_testing_addresses', lambda: ['虚拟地点甲', '虚拟地点乙'])
    choice = {'mode': 'selected', 'addresses': ['虚拟地点乙', '虚拟地点甲']}
    assert resolve({'manualParameterLocations': {'库外一': choice}}, [])['actualTestLocations'] == ['虚拟地点乙', '虚拟地点甲']
    choice['addresses'] = ['伪造地点']
    with pytest.raises(ValueError, match='不在数据库'):
        resolve({'manualParameterLocations': {'库外一': choice}}, [entry()])
    with pytest.raises(ValueError, match='请选择'):
        resolve({'manualParameterLocations': {}}, [entry()])


def test_database_location_projection_and_authenticated_route(isolated_app, isolated_client, scenario_factory):
    from app.extensions import db
    from app.models import CapabilityEntry, CapabilityImportBatch
    from app.security import issue_token
    with isolated_app.app_context():
        dept = scenario_factory.department(name='虚拟地点部')
        user = scenario_factory.user(dept, account='location-reader', name='虚拟人员',
                                     permissions=('entrust.sample_register.view',))
        batch = CapabilityImportBatch(source_name='virtual.pdf', source_sha256='a'*64, status='active')
        db.session.add(batch); db.session.flush()
        for index, (address, active) in enumerate([('虚拟地点甲', True), ('虚拟地点甲', True), ('虚拟地点乙', True), ('已停用地点', False)]):
            db.session.add(CapabilityEntry(batch_id=batch.id, capability_type='检测',
                certificate_no='VIRTUAL', site='虚拟场所', item_name='温度', object_name='虚拟对象', standard_code='GB/TEST',
                mapping_status='confirmed', active=active, source_file='virtual.pdf',
                source_page=1, source_row=index, source_sha256=f'{index:064x}',
                raw_cells={'standardWorkbook': {'address': address}}))
        db.session.commit()
        headers = {'Authorization': 'Bearer '+issue_token(user)}
    response = isolated_client.get('/api/reports/lib/testing-locations', headers=headers)
    assert response.status_code == 200
    assert set(response.get_json()['data']['rows']) == {'虚拟地点甲', '虚拟地点乙', '已停用地点'}
    assert isolated_client.get('/api/reports/lib/testing-locations').status_code == 401


pytest_plugins = ('testkit.fixtures',)
