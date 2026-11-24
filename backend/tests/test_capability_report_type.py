"""Report format and parameter metadata never narrow standard-owned parameters."""
from datetime import date, timedelta

import pytest
from app.extensions import db
from app.models import CapabilityEntry, CapabilityImportBatch, Report, StdLibraryItem
from app.blueprints.reports import _sample_configuration as real_sample_configuration
from test_sample_pricing import business, create, detail
from test_onsite_manual_address import catalog

pytest_plugins = ('testkit.fixtures',)


def calibration_record(kind):
    standard = StdLibraryItem(code='JJG 229-2010', name='虚拟温度标准', use_depts='虚拟部门')
    batch = CapabilityImportBatch(source_name='virtual.pdf', source_sha256='a'*64, status='active')
    db.session.add_all([standard, batch]); db.session.flush()
    entry = CapabilityEntry(batch_id=batch.id, standard_item_id=standard.id, capability_type=kind,
        certificate_no='VIRTUAL', site='虚拟校准实验室', item_name='温度', object_name='虚拟对象',
        standard_code=standard.code, standard_name=standard.name, mapping_status='confirmed', active=True,
        source_file='virtual.pdf', source_page=1, source_row=1, source_sha256='b'*64,
        raw_cells={'standardWorkbook': {'address': '虚拟校准实验室完整地址'}})
    db.session.add(entry); db.session.commit()
    return entry


def sample(entry, report_type, category):
    value = detail()
    value['rawSample'].update(reportType=report_type, testCategory=category,
        locationWorkflowVersion=1, isOnsiteTesting=False, manualCapabilityItems=[],
        testBases=[entry.standard_code], testBasis=entry.standard_code,
        capabilityEntryIds=[entry.id], testLocation='虚拟校准实验室完整地址')
    return value


@pytest.mark.parametrize('report_type,category,kind', [
    ('校准报告', '委托', '校准'), ('校准报告', '型式检验', '校准'),
    ('检验报告', '委托', '检验'), ('检验（检查）报告', '校准', '检验'),
    ('产品报告', '校准', '检测'), ('工程报告', '委托', '检测'), ('抽样报告', '抽样检测', '检测'),
])
def test_draft_reopen_and_complete_by_report_format(business, report_type, category, kind):
    client, headers, parents = business
    entry = calibration_record(kind)
    result = create(client, headers, parents[0], 'TYPE-QA', sample(entry, report_type, category), '登记中')
    assert result['code'] == 0, result
    reopened = client.get('/api/reports/TYPE-QA?view=sample_register&projection=sample_form_text', headers=headers).get_json()
    assert reopened['code'] == 0, reopened
    assert reopened['data']['rawSample']['testCategory'] == category
    completed = client.post('/api/reports/TYPE-QA/sample-reg', headers=headers, json={'action': 'complete'}).get_json()
    assert completed['code'] == 0, completed
    db.session.expire_all()
    raw = Report.query.filter_by(report_no='TYPE-QA').one().detail['rawSample']
    assert raw['actualTestLocations'] == ['虚拟校准实验室完整地址']
    assert raw['testCategory'] == category


@pytest.mark.parametrize('change,reason', [
    # Record-ID validation rejects ambiguous legacy department lookup and missing
    # standard links before the location-specific authorization check.
    ('type', '类型不符'), ('department', '无法唯一确认'), ('expired', '有效期'),
    ('future', '有效期'), ('inactive', '未启用'), ('unlinked', '不属于选中的标准记录'),
    ('batch', '未启用'), ('address', '缺少已确认'),
])
def test_completion_keeps_standard_identity_and_authority_only(business, change, reason):
    client, headers, parents = business
    entry = calibration_record('校准')
    if change == 'type': entry.capability_type = '检测'
    elif change == 'department': entry.standard_item.use_depts = '其他部门'
    elif change == 'expired': entry.expires_on = date.today() - timedelta(days=1)
    elif change == 'future': entry.effective_date = date.today() + timedelta(days=1)
    elif change == 'inactive': entry.active = False
    elif change == 'unlinked': entry.standard_item_id = None
    elif change == 'batch': entry.batch.status = 'inactive'
    elif change == 'address': entry.raw_cells = {'standardWorkbook': {'address': ''}}
    db.session.commit()
    result = create(client, headers, parents[0], 'TYPE-REJECT', sample(entry, '校准报告', '委托'))
    if change in ('department', 'unlinked'):
        assert result['code'] != 0 and reason in result['message'], result
        assert Report.query.filter_by(report_no='TYPE-REJECT').first() is None
    else:
        assert result['code'] == 0, result
        stored = Report.query.filter_by(report_no='TYPE-REJECT').one()
        assert stored.detail['rawSample']['capabilityEntryIds'] == [entry.id]


def test_queries_keep_standard_authority_without_parameter_metadata_filters(catalog):
    client, headers, _ = catalog
    for row in CapabilityEntry.query.all(): row.capability_type = '校准'
    db.session.commit()
    body = {'allStandards': True, 'capabilityType': '校准', 'size': 100, 'date': date.today().isoformat()}
    result = client.post('/api/reports/lib/capability-items', headers=headers, json=body).get_json()
    assert result['code'] == 0, result
    assert {r['standardCode'] for r in result['data']['rows']} == {'TEST-normal', 'TEST-onsite', 'TEST-expired', 'TEST-inactive'}
    wrong = client.post('/api/reports/lib/capability-items', headers=headers, json={**body, 'capabilityType': '检测'}).get_json()
    assert wrong['data']['rows'] == result['data']['rows']
    result = client.get('/api/quality/std-library/search?size=100&capabilityType=校准&capabilityOnly=1', headers=headers).get_json()
    assert result['code'] == 0, result
    assert {r['code'] for r in result['data']['rows']} == {'TEST-normal', 'TEST-onsite', 'TEST-expired', 'TEST-inactive'}


def test_cleaned_standard_code_draft_reopen_complete_and_review_configuration(business):
    # This fixture stubs unrelated scheme lookup; test the real standard review
    # configuration separately below without a project scheme.
    from app.standard_control import selected_controlled_standards
    client, headers, parents = business
    entry = calibration_record('检测')
    item = entry.standard_item
    item.code = 'EN 442-1:2014'
    item.name = 'English radiator specification'
    entry.standard_code = "'EN 442-1:2014"
    entry.standard_name = item.name
    db.session.commit()
    value = sample(entry, '产品报告', '委托')
    value['rawSample'].update(testBases=[item.code], testBasis=item.code,
                             standardJudge=item.code, standardItemIds=[item.id])
    result = create(client, headers, parents[0], 'CODE-CLEANUP-QA', value, '登记中')
    assert result['code'] == 0, result
    reopened = client.get('/api/reports/CODE-CLEANUP-QA?view=sample_register&projection=sample_form_text',
                          headers=headers).get_json()['data']['rawSample']
    assert reopened['standardItemIds'] == [item.id]
    assert reopened['capabilityEntryIds'] == [entry.id]
    assert reopened['testBases'] == [item.code]
    completed = client.post('/api/reports/CODE-CLEANUP-QA/sample-reg', headers=headers,
                            json={'action': 'complete'}).get_json()
    assert completed['code'] == 0, completed
    db.session.expire_all()
    raw = Report.query.filter_by(report_no='CODE-CLEANUP-QA').one().detail['rawSample']
    assert raw['actualTestLocations'] == ['虚拟校准实验室完整地址']
    assert raw['testBases'] == [item.code]
    assert selected_controlled_standards([item.code], [item.id], '虚拟部门')[0][1]['valid']
    configuration = real_sample_configuration([item.code], '虚拟部门', '',
                                             standard_item_ids=[item.id])
    assert configuration['ready'], configuration
    assert entry.standard_code == "'EN 442-1:2014"
