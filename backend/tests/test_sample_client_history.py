"""Regression coverage for explicit client clearing and historical sample persistence."""
from testkit.forms import loaded_form
from copy import deepcopy
from test_sample_pricing import business, saved, detail
from app.extensions import db
from app.models import Report
import pytest

pytest_plugins = ('testkit.fixtures',)


def payload(client_name):
    value = detail('30', ('30',))
    value['summary'].append({'title': '委托信息', 'fields': [['委托单位', client_name]]})
    value['entrustSnapshot'] = {'client': client_name, 'info': {'client': client_name}}
    value['rawSample'].update(
        locationWorkflowVersion=1, isOnsiteTesting=False,
        manualCapabilityItems=['库外温差'], manualCapabilityReason='委托约定',
        manualParameterLocations={'库外温差': {'mode': 'selected', 'addresses': ['验收地点乙']}},
        actualTestLocations=['验收地点乙'], testLocation='验收地点乙',
        commissionText={'basis': {'separator': '；'}, 'items': {'separator': '、'}})
    return value


@pytest.mark.parametrize('name', ['', '验收单位乙', '验收单位甲、验收单位乙'])
@pytest.mark.parametrize('route', ['edit', 'change-save'])
def test_draft_http_save_reopen_retains_locations_and_client(business, name, route):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-AUDIT', '30')
    row.client = '原单位'
    if route == 'change-save': row.status = '委托更改中'
    sibling = saved(parents[0], 'TEST-SIBLING', '20')
    sibling.client = '其他样品单位'
    parents[0].client = '原始委托单位'
    db.session.commit()
    value = payload(name)
    result = client.open(f'/api/reports/TEST-AUDIT/{route}', method='PUT' if route == 'edit' else 'POST', headers=headers,
                         json=loaded_form(client, f'/api/reports/TEST-AUDIT/{route}', {'fullDetail': value})).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    persisted = db.session.get(Report, row.id)
    assert persisted.client == name
    assert result['data']['client'] == name
    assert persisted.to_row()['client'] == name
    assert parents[0].client == '原始委托单位'
    assert db.session.get(Report, sibling.id).client == '其他样品单位'
    assert persisted.detail['rawSample']['manualParameterLocations'] == value['rawSample']['manualParameterLocations']
    view = 'sample_register' if route == 'edit' else 'entrust_change'
    response = client.get(f'/api/reports/TEST-AUDIT?view={view}&projection=sample_form_text',
                          headers=headers).get_json()
    assert response['code'] == 0, response
    assert response['data']['rawSample']['manualParameterLocations'] == value['rawSample']['manualParameterLocations']
    assert response['data']['entrustSnapshot']['client'] == name


def test_clearing_all_clients_updates_list_field_too(business):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-CLEAR', '30')
    row.client = '原单位'; db.session.commit()
    result = client.put('/api/reports/TEST-CLEAR/edit', headers=headers,
                        json=loaded_form(client, '/api/reports/TEST-CLEAR/edit', {'fullDetail': payload('')})).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    persisted = db.session.get(Report, row.id)
    assert persisted.detail['entrustSnapshot']['client'] == ''
    assert persisted.client == '', '列表主字段仍为原单位，而样品快照已清空'


def test_rejected_write_keeps_saved_locations_and_client(business):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-REJECT', '30')
    row.detail = payload('原单位'); db.session.commit()
    before = deepcopy(row.detail)
    rejected = payload('不应写入')
    rejected['rawSample']['stdPrice'] = '-1'
    result = client.put('/api/reports/TEST-REJECT/edit', headers=headers,
                        json=loaded_form(client, '/api/reports/TEST-REJECT/edit', {'fullDetail': rejected})).get_json()
    assert result['code'] != 0, result
    db.session.expire_all()
    assert db.session.get(Report, row.id).detail == before

    unauthorized = client.put('/api/reports/TEST-REJECT/edit', json=loaded_form(client, '/api/reports/TEST-REJECT/edit', {'fullDetail': rejected}))
    assert unauthorized.status_code == 401
    assert db.session.get(Report, row.id).detail == before


def test_missing_client_preserves_previous_and_info_can_explicitly_clear(business):
    from app.sample_entrust import normalize_sample_entrust_snapshot, sample_client_from_detail
    client, headers, parents = business
    parents[0].client = '来源单位'
    row = saved(parents[0], 'TEST-MISSING-CLIENT', '30')
    row.detail = payload('样品单位'); row.client = '样品单位'
    db.session.commit()
    value = detail('30', ('30',))
    result = client.put('/api/reports/TEST-MISSING-CLIENT/edit', headers=headers,
                        json=loaded_form(client, '/api/reports/TEST-MISSING-CLIENT/edit', {'fullDetail': value})).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    assert db.session.get(Report, row.id).client == '样品单位'
    assert normalize_sample_entrust_snapshot({'info': {'client': ''}}, parents[0])['client'] == ''
    assert sample_client_from_detail({}, '样品单位') == '样品单位'
    assert sample_client_from_detail({'summary': [{'title': '委托信息', 'fields': [['委托单位', '']]}]}, '样品单位') == ''


@pytest.mark.parametrize('state', ['missing', 'unlinked'])
def test_historical_parameter_draft_survives_reopen_but_completion_rejects_without_writes(business, state):
    from app.models import CapabilityEntry, CapabilityImportBatch
    client, headers, parents = business
    entry_id = 900001
    if state == 'unlinked':
        batch = CapabilityImportBatch(source_name='virtual.pdf', source_sha256='f'*64, status='active')
        db.session.add(batch); db.session.flush()
        entry = CapabilityEntry(batch_id=batch.id, capability_type='检测', certificate_no='VIRTUAL',
            site='虚拟场所', item_name='历史参数', object_name='虚拟样品', standard_code='TEST-STD',
            mapping_status='confirmed', active=False, source_file='virtual.pdf', source_page=1,
            source_row=1, source_sha256='e'*64, raw_cells={'standardWorkbook': {'address': '历史地址'}})
        db.session.add(entry); db.session.flush(); entry_id = entry.id
    row = saved(parents[0], 'TEST-HISTORY', '30')
    value = payload('验收单位')
    value['rawSample'].update(capabilityEntryIds=[entry_id], manualCapabilityItems=[],
        capabilitySnapshots=[{'id': entry_id, 'itemName': '历史参数', 'standardCode': 'TEST-STD', 'address': '历史地址'}],
        testItemOrder=[{'kind': 'library', 'id': entry_id}], projectList=['历史参数'],
        project='历史参数', actualTestLocations=['历史地址'], testLocation='历史地址')
    db.session.commit()
    response = client.put('/api/reports/TEST-HISTORY/edit', headers=headers, json=loaded_form(client, '/api/reports/TEST-HISTORY/edit', {'fullDetail': value})).get_json()
    assert response['code'] == 0, response
    reopened = client.get('/api/reports/TEST-HISTORY?view=sample_register&projection=sample_form_text', headers=headers).get_json()
    for key in ('capabilityEntryIds', 'capabilitySnapshots', 'testItemOrder', 'actualTestLocations'):
        assert reopened['data']['rawSample'][key] == value['rawSample'][key]
    db.session.expire_all()
    before = deepcopy(db.session.get(Report, row.id).detail)
    result = client.post('/api/reports/TEST-HISTORY/sample-reg', headers=headers, json={'action': 'complete'}).get_json()
    assert result['code'] != 0, result
    assert ('已不存在' if state == 'missing' else '所选参数不属于选中的标准记录') in result['message']
    db.session.expire_all()
    assert db.session.get(Report, row.id).detail == before
    assert db.session.get(Report, row.id).sample_reg_state == '登记中'


@pytest.mark.parametrize('body,expected', [({'client': ''}, ''), ({}, '原单位')])
def test_legacy_change_submission_distinguishes_clear_and_omission(business, body, expected):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-LEGACY-CLIENT', '30', status='委托更改中')
    row.client = '原单位'
    value = detail('30', ('30',))
    value['entrustSnapshot'] = {'client': '原单位', 'info': {'client': '原单位'}}
    row.detail = value; db.session.commit()
    result = client.post('/api/reports/TEST-LEGACY-CLIENT/change-resubmit', headers=headers, json=loaded_form(client, '/api/reports/TEST-LEGACY-CLIENT/change-resubmit', body)).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    record = db.session.get(Report, row.id)
    assert record.client == expected
    assert record.detail['entrustSnapshot']['client'] == expected
