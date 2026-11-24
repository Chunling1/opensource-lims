"""Business selection inherits department authorization from the selected standard."""
from datetime import date
import pytest
from app.extensions import db
from app.models import Department, Report, StdLibraryItem, User
from app.security import issue_token
from test_sample_pricing import business, create
from test_capability_report_type import calibration_record, sample

pytest_plugins = ('testkit.fixtures',)


def pending_parameter():
    entry = calibration_record('校准')
    entry.mapping_status = 'pending'
    entry.departments = []
    entry.standard_code = 'JJG 130'
    entry.standard_item.code = 'JJG 130-2011'
    entry.standard_item.auth_kind = 'CNAS'
    entry.batch.summary = {'schema': 'lims.scope-workbook-import.v2',
        'createdItemIds': [entry.standard_item_id],
        'standardPolicies': {str(entry.standard_item_id): {'capabilityOwnerId': entry.standard_item_id}}}
    db.session.commit()
    return entry


def pick(client, headers, item, **kwargs):
    return client.post('/api/reports/lib/capability-items', headers=headers, json={
        'standardItemId': item.id, 'page': 1, 'capabilityType': '校准', **kwargs}).get_json()['data']['rows']


@pytest.mark.parametrize('assigned', [None, '', '  ;；  '])
@pytest.mark.parametrize('endpoint', ['search', 'legacy', 'parameters'])
def test_unassigned_standard_is_hidden_even_for_company_admin(business, assigned, endpoint):
    client, headers, _ = business
    entry = calibration_record('校准')
    entry.standard_item.use_depts = assigned
    db.session.commit()
    if endpoint == 'search':
        response = client.get('/api/quality/std-library/search', headers=headers,
            query_string={'ids': str(entry.standard_item_id)}).get_json()
    elif endpoint == 'legacy':
        response = client.post('/api/reports/lib/standards', headers=headers, json={}).get_json()
    else:
        assert pick(client, headers, entry.standard_item) == []
        return
    assert response['code'] == 0, response
    assert entry.standard_item_id not in {row['id'] for row in response['data']['rows']}, response
    if endpoint == 'search': assert response['data']['total'] == 0


@pytest.mark.parametrize('controlled', [False, True])
def test_pending_department_provenance_does_not_block_authorized_parameters(business, controlled):
    client, headers, _ = business
    entry = pending_parameter()
    if not controlled: entry.batch.summary = {}
    db.session.commit()
    item = entry.standard_item
    for params in ({}, {'capabilityOnly': '1'}, {'ids': str(item.id)}):
        data = client.get('/api/quality/std-library/search', headers=headers, query_string=params).get_json()['data']
        row = next(r for r in data['rows'] if r['id'] == item.id)
        assert row['capabilityTypes'] == ['校准']
    assert [r['id'] for r in pick(client, headers, item)] == [entry.id]
    legacy = client.post('/api/reports/lib/standards', headers=headers, json={}).get_json()['data']['rows']
    assert next(r for r in legacy if r['id'] == item.id)['hasActiveCapability']
    from app.standard_mark_coverage import standard_mark_coverage
    raw = {'standardItemIds': [item.id], 'isOnsiteTesting': False,
           'actualTestLocations': ['虚拟校准实验室完整地址']}
    coverage = standard_mark_coverage([item.code], '虚拟部门', date.today(), '校准', raw)
    assert coverage[0]['marks'] == ['CNAS']
    assert entry.mapping_status == 'pending' and entry.departments == []


def test_standard_grant_and_revoke_apply_without_reconfirming_parameter(business, scenario_factory):
    client, _, _ = business
    dept = Department.query.filter_by(name='虚拟部门').one()
    user = scenario_factory.user(dept, permissions=['entrust.sample_register.view'])
    headers = {'Authorization': 'Bearer ' + issue_token(user)}
    entry = pending_parameter(); item = entry.standard_item
    item.use_depts = ''
    db.session.commit()
    assert pick(client, headers, item) == []
    item.use_depts = dept.name
    db.session.commit()
    assert [r['id'] for r in pick(client, headers, item)] == [entry.id]
    item.use_depts = '其他部门'
    db.session.commit()
    assert pick(client, headers, item, department=dept.name) == []
    assert entry.mapping_status == 'pending' and entry.departments == []


def test_pending_parameter_draft_reopen_complete(business, monkeypatch):
    client, headers, parents = business
    # Restore real standard authorization; only unrelated scheme rendering remains stubbed.
    from app import authorization_scope
    from app.blueprints import reports
    monkeypatch.setattr(reports, 'standard_is_authorized', authorization_scope.standard_is_authorized)
    entry = pending_parameter(); item = entry.standard_item
    value = sample(entry, '校准报告', '委托')
    value['rawSample'].update(testBases=[item.code], testBasis=item.code, standardJudge=item.code,
                             standardItemIds=[item.id])
    result = create(client, headers, parents[0], 'PARAM-DEPT-QA', value, '登记中')
    assert result['code'] == 0, result
    raw = client.get('/api/reports/PARAM-DEPT-QA?view=sample_register&projection=sample_form_text',
        headers=headers).get_json()['data']['rawSample']
    assert raw['capabilityEntryIds'] == [entry.id] and raw['standardItemIds'] == [item.id]
    result = client.post('/api/reports/PARAM-DEPT-QA/sample-reg', headers=headers,
        json={'action': 'complete'}).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    raw = Report.query.filter_by(report_no='PARAM-DEPT-QA').one().detail['rawSample']
    assert raw['actualTestLocations'] == ['虚拟校准实验室完整地址']
    assert entry.mapping_status == 'pending'


@pytest.mark.parametrize('assigned', ['', '其他部门'])
def test_direct_completion_cannot_bypass_standard_department(business, monkeypatch, assigned):
    client, headers, parents = business
    from app import authorization_scope
    from app.blueprints import reports
    monkeypatch.setattr(reports, 'standard_is_authorized', authorization_scope.standard_is_authorized)
    entry = calibration_record('校准'); item = entry.standard_item
    item.use_depts = assigned
    db.session.commit()
    value = sample(entry, '校准报告', '委托')
    value['rawSample']['standardItemIds'] = [item.id]
    result = create(client, headers, parents[0], 'UNASSIGNED-QA', value)
    assert result['code'] != 0, result
    assert Report.query.filter_by(report_no='UNASSIGNED-QA').first() is None


def test_parameter_revision_keeps_legacy_mapping_without_requiring_department_confirmation(business):
    from app.applications.quality_resources.standard_parameters import validate_values, parameter_row, update_parameter
    client, headers, _ = business
    entry = pending_parameter(); item = entry.standard_item
    values = validate_values({'version': parameter_row(entry)['version'], 'reason': '修正参数说明',
        'itemName': '温度修订'}, item, entry=entry)
    revised = update_parameter(entry, values)
    db.session.commit()
    assert revised.active and revised.mapping_status == 'pending' and revised.departments == []
    assert [r['id'] for r in pick(client, headers, item)] == [entry.id, revised.id]
    entry.batch.status = 'review'
    db.session.commit()
    assert [r['id'] for r in pick(client, headers, item)] == [entry.id, revised.id]
    validate_values({'version': parameter_row(revised)['version'], 'reason': '测试', 'active': True},
                    item, entry=revised)
