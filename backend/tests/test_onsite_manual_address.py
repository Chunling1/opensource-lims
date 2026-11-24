"""Onsite changes the actual address, never expands or narrows standard authority."""
from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest
from app.extensions import db
from app.models import StdLibraryItem, CapabilityEntry, CapabilityImportBatch, user_standard_denials
from app.security import issue_token
from app.applications.quality_resources.testing_locations import resolve_testing_location
from test_manual_parameter_locations import entry
from test_sample_pricing import business, detail, create

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture()
def catalog(isolated_client, scenario_factory):
    department = scenario_factory.department(name='现场规则测试部')
    other = scenario_factory.department(name='其他测试部')
    user = scenario_factory.user(department, permissions=['entrust.sample_register.view'])
    batch = CapabilityImportBatch(source_name='virtual.pdf', source_sha256='a'*64, status='active')
    db.session.add(batch); db.session.flush()
    rows = []
    for index, kind in enumerate(['normal', 'onsite', 'foreign', 'denied', 'void', 'expired', 'inactive']):
        dept = other if kind == 'foreign' else department
        standard = StdLibraryItem(code=f'TEST-{kind}', name=f'虚拟标准{kind}', use_depts=dept.name,
                                  is_onsite_standard=kind == 'onsite',
                                  void_date='2000-01-01' if kind == 'void' else None)
        db.session.add(standard); db.session.flush()
        capability = CapabilityEntry(batch_id=batch.id, standard_item_id=standard.id,
            capability_type='检测', certificate_no='TEST', site='实验室', item_name=kind,
            object_name='虚拟对象', standard_code=standard.code, standard_name=standard.name,
            mapping_status='confirmed', active=kind != 'inactive',
            expires_on=date.today()-timedelta(days=1) if kind == 'expired' else None,
            source_file='virtual.pdf', source_page=1, source_row=index, source_sha256=f'{index:064x}',
            raw_cells={'standardWorkbook': {'address': '库内实验室地址'}})
        capability.departments = [dept]
        db.session.add(capability)
        if kind == 'denied':
            db.session.execute(user_standard_denials.insert().values(user_id=user.id, standard_item_id=standard.id))
        rows.append(standard)
    db.session.commit()
    return isolated_client, {'Authorization': 'Bearer '+issue_token(user)}, rows


def test_standard_search_does_not_filter_by_onsite_flag_and_preserves_authority(catalog):
    client, headers, _ = catalog
    normal = client.get('/api/quality/std-library/search?size=100', headers=headers).get_json()
    onsite = client.get('/api/quality/std-library/search?size=100&onsiteOnly=1', headers=headers).get_json()
    assert normal['code'] == onsite['code'] == 0
    codes = {r['code'] for r in onsite['data']['rows']}
    assert codes == {r['code'] for r in normal['data']['rows']}
    assert {'TEST-normal', 'TEST-onsite'} <= codes
    assert not {'TEST-foreign', 'TEST-denied', 'TEST-void'} & codes


def test_parameter_search_keeps_non_onsite_parameters_and_existing_limits(catalog):
    client, headers, _ = catalog
    body = {'allStandards': True, 'capabilityType': '检测', 'size': 100}
    normal = client.post('/api/reports/lib/capability-items', headers=headers, json=body).get_json()
    onsite = client.post('/api/reports/lib/capability-items', headers=headers, json={**body, 'onsiteOnly': True}).get_json()
    assert normal['code'] == onsite['code'] == 0
    assert onsite['data']['rows'] == normal['data']['rows']
    codes = {r['standardCode'] for r in onsite['data']['rows']}
    assert {'TEST-normal', 'TEST-onsite'} <= codes
    assert {'TEST-expired', 'TEST-inactive'} <= codes
    assert not {'TEST-foreign', 'TEST-denied', 'TEST-void'} & codes


def raw(address='任意客户现场完整地址'):
    return {'isOnsiteTesting': True, 'onsiteTestLocation': address, 'manualCapabilityItems': []}


def resolve(value, items=None, standards=None):
    return resolve_testing_location(value, items if items is not None else [entry()],
        '虚拟检测部', date.today(), '检测', selected_standards=standards)


def test_normal_standard_uses_actual_address_without_modifying_library():
    item = entry()
    result = resolve(raw(), [item], [item.standard_item])
    assert result['actualTestLocations'] == ['任意客户现场完整地址']
    assert result['capabilityLocations'] == ['虚拟地点甲']
    assert item.standard_item.is_onsite_standard is False
    assert item.raw_cells['standardWorkbook']['address'] == '虚拟地点甲'


@pytest.mark.parametrize('address,reason', [('', '完整地址'), (' '*4, '完整地址'), ('长'*1001, '过长')], ids=['empty', 'whitespace', 'too-long'])
def test_actual_address_still_required_and_bounded(address, reason):
    with pytest.raises(ValueError, match=reason):
        resolve(raw(address))


@pytest.mark.parametrize('change,reason', [
    ({'active': False}, '未启用'), ({'standard_item': NS(deleted_at=None, is_onsite_standard=False, use_depts='其他部')}, '未授权'),
    ({'capability_type': '校准'}, '类型不符'),
    ({'expires_on': date.today()-timedelta(days=1)}, '有效期'),
])
def test_manual_address_does_not_bypass_capability_requirements(change, reason):
    item = entry(); item.__dict__.update(change)
    if 'standard_item' in change:
        with pytest.raises(ValueError, match=reason):
            resolve(raw(), [item])
    else:
        assert resolve(raw(), [item])['testLocation'] == raw()['onsiteTestLocation']


def test_report_mark_evidence_no_longer_requires_onsite_attribute(monkeypatch):
    from app import standard_mark_coverage as marks
    monkeypatch.setattr(marks, 'capability_matches_standard', lambda *args: True)
    item = entry()
    assert marks.candidate_reasons(item, item.standard_item, '虚拟检测部', date.today(), '检测', raw(), {}) == []
    assert marks.candidate_reasons(item, item.standard_item, '虚拟检测部', date.today(), '检测', raw(''), {}) == []


def test_manual_only_reason_optional_but_actual_address_required():
    value = {**raw(), 'manualCapabilityItems': ['库外温度'], 'manualCapabilityReason': '委托约定'}
    assert resolve(value, [], [entry().standard_item])['testLocation'] == value['onsiteTestLocation']
    value['manualCapabilityReason'] = ''
    assert resolve(value, [], [entry().standard_item])['testLocation'] == value['onsiteTestLocation']
    value['onsiteTestLocation'] = ''
    with pytest.raises(ValueError, match='完整地址'):
        resolve(value, [], [entry().standard_item])


def test_library_address_is_optional_metadata_in_both_modes():
    item = entry('')
    assert resolve(raw(), [item], [item.standard_item])['testLocation'] == raw()['onsiteTestLocation']
    assert resolve({**raw(), 'isOnsiteTesting': False}, [item])['testLocation'] == ''


def test_http_save_reopen_and_completion_keep_actual_address_and_basis(business):
    from app.models import Report
    client, headers, parents = business
    standard = StdLibraryItem(code='TEST-STD', name='普通实验室标准', use_depts='虚拟部门', is_onsite_standard=False)
    db.session.add(standard); db.session.commit()
    value = detail('30', ('30',))
    value['rawSample'].update(raw())
    value['rawSample'].update(locationWorkflowVersion=1, testLocation=raw()['onsiteTestLocation'],
        actualTestLocations=[raw()['onsiteTestLocation']], manualCapabilityItems=['库外温差'],
        manualCapabilityReason='', testBases=['TEST-STD'], standardItemIds=[standard.id])
    result = create(client, headers, parents[0], 'TEST-ONSITE', value, '登记中')
    assert result['code'] == 0, result
    reopened = client.get('/api/reports/TEST-ONSITE?view=sample_register&projection=sample_form_text', headers=headers).get_json()
    assert reopened['code'] == 0, reopened
    assert reopened['data']['rawSample']['testBases'] == ['TEST-STD']
    assert reopened['data']['rawSample']['onsiteTestLocation'] == raw()['onsiteTestLocation']
    completed = client.post('/api/reports/TEST-ONSITE/sample-reg', headers=headers, json={'action': 'complete'}).get_json()
    assert completed['code'] == 0, completed
    db.session.expire_all()
    stored = Report.query.filter_by(report_no='TEST-ONSITE').one()
    assert stored.sample_reg_state == '登记完成'
    assert stored.detail['rawSample']['actualTestLocations'] == [raw()['onsiteTestLocation']]
