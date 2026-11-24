"""Adding a catalog edition must preserve confirmed parameter record identity."""
from datetime import date, timedelta

import pytest
from app.extensions import db
from app.models import Report, StdLibraryItem
from test_capability_report_type import calibration_record, sample
from test_sample_pricing import business, create

pytest_plugins = ('testkit.fixtures',)


def yearless_record(controlled=False):
    entry = calibration_record('校准')
    entry.standard_code = 'JJG 161'
    entry.standard_item.code = 'JJG 161-2010'
    if controlled:
        entry.batch.summary = {
            'schema': 'lims.scope-workbook-import.v2',
            'createdItemIds': [entry.standard_item_id],
            'standardPolicies': {str(entry.standard_item_id): {
                'capabilityOwnerId': entry.standard_item_id}},
        }
    db.session.commit()
    return entry


def query(client, headers, entry, mode):
    item = entry.standard_item
    body = {'page': 1, 'size': 100, 'department': '虚拟部门', 'capabilityType': '校准'}
    if mode == 'id':
        body.update(standardItemId=item.id)
    elif mode == 'code':
        body.update(standardCode=item.code)
    elif mode == 'all':
        body.update(allStandards=True)
    else:
        body.update(allStandards=True, standardItemIds=[item.id], standardCodes=[item.code])
    return client.post('/api/reports/lib/capability-items', headers=headers, json=body).get_json()


@pytest.mark.parametrize('controlled', [False, True])
@pytest.mark.parametrize('mode', ['id', 'code', 'all', 'selected'])
def test_yearless_source_is_selectable_after_catalog_edition_added(business, controlled, mode):
    client, headers, _ = business
    entry = yearless_record(controlled)
    response = query(client, headers, entry, mode)
    assert response['code'] == 0, response
    assert response['data']['total'] == 1, response
    assert [r['id'] for r in response['data']['rows']] == [entry.id]
    if mode in ('id', 'selected'):
        assert response['data']['rows'][0]['standardCode'] == 'JJG 161-2010'
    assert response['data']['rows'][0]['address'] == '虚拟校准实验室完整地址'
    assert entry.standard_code == 'JJG 161'


@pytest.mark.parametrize('controlled', [False, True])
def test_yearless_source_draft_reopen_complete_preserves_ids_and_location(business, controlled):
    client, headers, parents = business
    entry = yearless_record(controlled)
    item = entry.standard_item
    value = sample(entry, '校准报告', '委托')
    value['rawSample'].update(testBases=[item.code], testBasis=item.code,
                             standardJudge=item.code, standardItemIds=[item.id])
    result = create(client, headers, parents[0], 'YEARLESS-QA', value, '登记中')
    assert result['code'] == 0, result
    reopened = client.get('/api/reports/YEARLESS-QA?view=sample_register&projection=sample_form_text',
                          headers=headers).get_json()['data']['rawSample']
    assert reopened['standardItemIds'] == [item.id]
    assert reopened['capabilityEntryIds'] == [entry.id]
    completed = client.post('/api/reports/YEARLESS-QA/sample-reg', headers=headers,
                            json={'action': 'complete'}).get_json()
    assert completed['code'] == 0, completed
    db.session.expire_all()
    raw = Report.query.filter_by(report_no='YEARLESS-QA').one().detail['rawSample']
    assert raw['testBases'] == [item.code]
    assert raw['actualTestLocations'] == ['虚拟校准实验室完整地址']
    assert entry.standard_code == 'JJG 161'


@pytest.mark.parametrize('change', ['edition', 'prefix', 'record', 'unlinked', 'inactive',
                                    'batch', 'department', 'expired', 'type'])
def test_yearless_compatibility_does_not_bypass_identity_or_authorization(business, change):
    client, headers, _ = business
    entry = yearless_record(True)
    selected_id = entry.standard_item_id
    if change == 'edition': entry.standard_code = 'JJG 161-2000'
    elif change == 'prefix': entry.standard_code = 'JJG 1610'
    elif change == 'record':
        other = StdLibraryItem(code=entry.standard_item.code, name='同编号另一记录', use_depts='虚拟部门')
        db.session.add(other); db.session.flush()
        entry.standard_item_id = other.id
    elif change == 'unlinked': entry.standard_item_id = None
    elif change == 'inactive': entry.active = False
    elif change == 'batch': entry.batch.status = 'inactive'
    elif change == 'department': entry.standard_item.use_depts = '其他部门'
    elif change == 'expired': entry.expires_on = date.today() - timedelta(days=1)
    elif change == 'type': entry.capability_type = '检测'
    db.session.commit()
    response = client.post('/api/reports/lib/capability-items', headers=headers, json={
        'allStandards': True, 'standardItemIds': [selected_id], 'standardCodes': ['JJG 161-2010'],
        'department': '虚拟部门', 'capabilityType': '校准', 'page': 1,
    }).get_json()
    assert response['code'] == 0, response
    if change in ('record', 'unlinked', 'department'):
        assert response['data']['rows'] == [], response
    else:
        # Parameter metadata does not override the selected standard identity.
        assert [r['id'] for r in response['data']['rows']] == [entry.id]


def test_confirmed_owner_group_rehydrates_only_selected_current_record(business):
    client, headers, _ = business
    entry = yearless_record(True)
    owner = entry.standard_item
    alias = StdLibraryItem(code=owner.code, name='同一来源的受控版本', use_depts='虚拟部门')
    owner.use_depts = '其他部门'
    db.session.add(alias); db.session.flush()
    entry.batch.summary = {
        'schema': 'lims.scope-workbook-import.v2',
        'createdItemIds': [owner.id, alias.id],
        'standardPolicies': {
            str(owner.id): {'capabilityOwnerId': owner.id, 'sourceRows': [1]},
            str(alias.id): {'capabilityOwnerId': owner.id, 'sourceRows': [1]},
        },
    }
    db.session.commit()
    body = {'allStandards': True, 'standardItemIds': [alias.id], 'standardCodes': [alias.code],
            'ids': [entry.id], 'department': '虚拟部门', 'capabilityType': '校准', 'page': 1}
    response = client.post('/api/reports/lib/capability-items', headers=headers, json=body).get_json()
    rows = response['data']['rows']
    assert len(rows) == 1, response
    assert (rows[0]['id'], rows[0]['standardCode'], rows[0]['standardName']) == (
        entry.id, alias.code, alias.name)
    assert entry.standard_item_id == owner.id and entry.standard_code == 'JJG 161'
    wrong_code = client.post('/api/reports/lib/capability-items', headers=headers,
                             json={**body, 'standardCodes': ['JJG 161-2000']}).get_json()
    assert [r['id'] for r in wrong_code['data']['rows']] == [entry.id]
