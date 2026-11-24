"""2026-10-29 rule: standard authorization owns selection; parameter data is descriptive."""
from datetime import date, timedelta
import pytest
from app.extensions import db
from app.models import Report, StdLibraryItem
from app.report_scope import assess_scope
from app.standard_mark_coverage import standard_mark_coverage
from test_sample_pricing import business, create
from test_compliance_review_round import case
from test_capability_report_type import calibration_record, sample

pytest_plugins = ('testkit.fixtures',)


def metadata_only_entry():
    e = calibration_record('检验')
    e.active = False
    e.mapping_status = 'pending'
    e.departments = []
    e.batch.status = 'review'
    e.effective_date = date.today() + timedelta(days=10)
    e.expires_on = date.today() - timedelta(days=10)
    e.standard_code = 'SOURCE-1999'
    e.standard_item.code = 'CURRENT-2026'
    e.standard_item.auth_kind = 'CNAS+CMA+一单一库'
    e.raw_cells = {'internalParameter': True, 'parameterSupersededBy': 98765,
                   'standardWorkbook': {'address': '虚拟校准实验室完整地址', 'accreditation': '内部维护'}}
    db.session.commit()
    return e


@pytest.mark.parametrize('kind', ['检测', '校准', '检验', ''])
def test_all_parameter_metadata_is_visible_and_never_a_filter(business, kind):
    client, headers, _ = business
    e = metadata_only_entry(); item = e.standard_item
    response = client.post('/api/reports/lib/capability-items', headers=headers, json={
        'standardItemIds': [item.id], 'standardCodes': ['OUTDATED-TEXT'], 'page': 1,
        'capabilityType': kind, 'date': 'not-a-date', 'site': 'other-place'}).get_json()
    assert response['code'] == 0 and response['data']['total'] == 1, response
    row = response['data']['rows'][0]
    assert row['id'] == e.id and row['standardCode'] == item.code
    assert row['sourceStandardCode'] == 'SOURCE-1999'
    assert row['capabilityType'] == '检验' and row['accreditation'] == '内部维护'
    assert row['mappingStatus'] == 'pending' and not row['active'] and row['superseded']
    assert row['address'] == '虚拟校准实验室完整地址'
    data = client.get('/api/quality/std-library/search', headers=headers, query_string={
        'ids': str(item.id), 'capabilityOnly': '1', 'capabilityType': kind, 'date': 'invalid'}).get_json()
    assert data['data']['rows'][0]['capabilityTypes'] == ['检验']


@pytest.mark.parametrize('format', ['校准报告', '检验报告', '工程报告', '产品报告'])
def test_draft_reopen_complete_and_marks_depend_only_on_standard(business, format):
    client, headers, parents = business
    e = metadata_only_entry(); item = e.standard_item
    value = sample(e, format, '委托')
    value['rawSample'].update(testBases=[item.code], testBasis=item.code,
        standardJudge=item.code, standardItemIds=[item.id], seal='CNAS+CMA')
    created = create(client, headers, parents[0], 'DISPLAY-QA', value, '登记中')
    assert created['code'] == 0, created
    reopened = client.get('/api/reports/DISPLAY-QA?view=sample_register&projection=sample_form_text', headers=headers).get_json()
    assert reopened['data']['rawSample']['capabilityEntryIds'] == [e.id]
    completed = client.post('/api/reports/DISPLAY-QA/sample-reg', headers=headers, json={'action': 'complete'}).get_json()
    assert completed['code'] == 0, completed
    db.session.expire_all()
    report = Report.query.filter_by(report_no='DISPLAY-QA').one()
    raw = report.detail['rawSample']
    assert raw['actualTestLocations'] == ['虚拟校准实验室完整地址']
    scope = assess_scope(report)
    assert scope['computedState'] == 'in_scope', scope
    assert scope['rows'][0]['mark'] == '内部维护' and scope['rows'][0]['valid']
    coverage = standard_mark_coverage([item.code], '虚拟部门', date.today(), '检测', raw)
    assert coverage[0]['marks'] == ['CMA', 'CNAS'], coverage
    assert e.standard_code == 'SOURCE-1999' and e.batch.status == 'review' and not e.active
    item.auth_kind = 'CNAS'; db.session.commit()
    denied = assess_scope(report)
    assert denied['computedState'] == 'out_of_scope' and 'CMA' in denied['note']


def test_retired_source_marker_does_not_override_current_authorized_standard(business):
    client, headers, _ = business
    e = metadata_only_entry(); item = e.standard_item
    e.batch.summary = {'schema': 'lims.scope-workbook-import.v2', 'retiredItemIds': [item.id]}
    e.batch.status = 'active'; db.session.commit()
    result = client.post('/api/reports/lib/capability-items', headers=headers, json={'standardItemId': item.id}).get_json()
    assert result['data']['rows'][0]['id'] == e.id


def test_shared_identity_survives_inactive_source_batch(business):
    client, headers, _ = business
    e = metadata_only_entry(); owner = e.standard_item
    alias = StdLibraryItem(code='ALIAS-2026', name='受控关联记录', use_depts=owner.use_depts)
    db.session.add(alias); db.session.flush()
    e.batch.summary = {'schema': 'lims.scope-workbook-import.v2', 'createdItemIds': [owner.id, alias.id],
        'standardPolicies': {str(owner.id): {'capabilityOwnerId': owner.id, 'sourceRows': [1]},
                             str(alias.id): {'capabilityOwnerId': owner.id, 'sourceRows': [1]}}}
    db.session.commit()
    result = client.post('/api/reports/lib/capability-items', headers=headers, json={'standardItemId': alias.id}).get_json()
    assert result['data']['rows'][0]['id'] == e.id and result['data']['rows'][0]['standardCode'] == alias.code


def test_unrelated_same_code_record_never_inherits_parameters(business):
    client, headers, _ = business
    e = metadata_only_entry()
    other = StdLibraryItem(code=e.standard_item.code, name='独立英文记录', is_english=True, use_depts=e.standard_item.use_depts)
    db.session.add(other); db.session.commit()
    result = client.post('/api/reports/lib/capability-items', headers=headers, json={'standardItemId': other.id}).get_json()
    assert result['data']['rows'] == []


def test_empty_parameter_address_is_displayed_without_blocking_completion(business):
    client, headers, parents = business
    e = metadata_only_entry(); item = e.standard_item
    e.raw_cells = {}; db.session.commit()
    value = sample(e, '校准报告', '委托')
    value['rawSample'].update(testBases=[item.code], testBasis=item.code, standardJudge=item.code,
        standardItemIds=[item.id], testLocation='')
    result = create(client, headers, parents[0], 'EMPTY-ADDRESS-QA', value)
    assert result['code'] == 0, result
    raw = Report.query.filter_by(report_no='EMPTY-ADDRESS-QA').one().detail['rawSample']
    assert raw['actualTestLocations'] == [] and raw['testLocation'] == ''


@pytest.mark.parametrize('raw_cells', [['historical', 'source cells'], [], None])
def test_historical_source_cell_lists_remain_queryable_without_rewriting(business, raw_cells):
    client, headers, _ = business
    entry = calibration_record('校准')
    entry.raw_cells = raw_cells
    db.session.commit()
    result = client.post('/api/reports/lib/capability-items', headers=headers,
                         json={'standardItemId': entry.standard_item_id}).get_json()
    assert result['code'] == 0 and result['data']['total'] == 1, result
    assert result['data']['rows'][0]['id'] == entry.id
    assert result['data']['rows'][0]['superseded'] is False
    db.session.refresh(entry)
    assert entry.raw_cells == raw_cells


@pytest.mark.parametrize('stage', ['contract_review', 'report_review', 'report_approval'])
def test_review_stages_never_use_parameter_metadata_as_qualification(case, stage):
    from app import compliance
    from app.models import CapabilityEntry
    _, _, report = case
    e = CapabilityEntry.query.one()
    e.active = False; e.batch.status = 'review'; e.mapping_status = 'pending'
    e.departments = []; e.capability_type = '校准'
    e.effective_date = date.today() + timedelta(days=10)
    e.expires_on = date.today() - timedelta(days=10)
    e.standard_code = 'HISTORICAL-SOURCE'
    e.raw_cells = {'internalParameter': True}
    detail = dict(report.detail)
    detail['rawSample'] = {**detail['rawSample'], 'standardItemIds': [e.standard_item_id],
                           'capabilityEntryIds': [e.id], 'reportType': '工程报告'}
    report.detail = detail; db.session.commit()
    result = compliance.build_compliance_preflight(report, stage)
    assert result['ready'] and result['issues'] == [], result
    assert 'CNAS' in result['finalSeal'] and 'CMA' in result['finalSeal']
    assert assess_scope(report)['computedState'] == 'in_scope'

def test_same_code_records_complete_with_separate_parameters_and_authorizations(business):
    from app.blueprints.reports import _sample_configuration
    from app.standard_control import selected_controlled_standards
    client, headers, parents = business
    cn=calibration_record('检测')
    cn.batch.source_sha256='c'*64;db.session.commit()
    en=calibration_record('校准')
    cn.standard_item.name='中文名称';en.standard_item.name='English title'
    for entry in (cn,en):entry.standard_item.auth_kind='CNAS+CMA+一单一库'
    db.session.commit();code=cn.standard_item.code;ids=[cn.standard_item_id,en.standard_item_id]
    response=client.post('/api/reports/lib/capability-items',headers=headers,json={'standardItemIds':ids,'standardCodes':[code]}).get_json()
    assert {r['id'] for r in response['data']['rows']}=={cn.id,en.id},response
    value=sample(cn,'产品报告','委托');value['rawSample'].update(standardItemIds=ids,capabilityEntryIds=[cn.id,en.id],seal='CNAS+CMA')
    created=create(client,headers,parents[0],'BOTH-LANGUAGE-QA',value,'登记中');assert created['code']==0,created
    reopened=client.get('/api/reports/BOTH-LANGUAGE-QA?view=sample_register&projection=sample_form_text',headers=headers).get_json()
    assert reopened['data']['rawSample']['standardItemIds']==ids
    completed=client.post('/api/reports/BOTH-LANGUAGE-QA/sample-reg',headers=headers,json={'action':'complete'}).get_json()
    assert completed['code']==0,completed
    db.session.expire_all();report=Report.query.filter_by(report_no='BOTH-LANGUAGE-QA').one();raw=report.detail['rawSample']
    assert raw['standardItemIds']==ids and raw['capabilityEntryIds']==[cn.id,en.id]
    coverage=standard_mark_coverage([code],'虚拟部门',date.today(),'检测',raw)
    assert [r['standardId'] for r in coverage]==ids
    assert [r['evidence'][0]['id'] for r in coverage]==[cn.id,en.id]
    scope=assess_scope(report);assert scope['computedState']=='in_scope',scope
    en.standard_item.auth_kind='CNAS';db.session.commit()
    scope=assess_scope(report);assert scope['computedState']=='out_of_scope' and 'CMA' in scope['note']
    en.standard_item.use_depts='其他部门';db.session.commit()
    resolved=selected_controlled_standards([code],ids,'虚拟部门')
    assert resolved[0][1]['valid'] and not resolved[1][1]['valid']


@pytest.mark.parametrize('stage', ['contract_review', 'report_review', 'report_approval'])
def test_review_checks_both_same_code_record_authorizations(case, stage):
    from copy import deepcopy
    from app import compliance
    from app.models import CapabilityEntry
    _, _, report = case
    cn = CapabilityEntry.query.one().standard_item
    en = StdLibraryItem(code=cn.code, name='English standard', auth_kind=cn.auth_kind, use_depts=cn.use_depts)
    db.session.add(en); db.session.flush()
    detail = deepcopy(report.detail)
    detail['rawSample']['standardItemIds'] = [cn.id, en.id]
    report.detail = detail; db.session.commit()
    result = compliance.build_compliance_preflight(report, stage)
    assert result['ready'] and not result['issues'], result
    en.use_depts = '另一个部门'; db.session.commit()
    denied = compliance.build_compliance_preflight(report, stage)
    assert denied['issues'], denied
    assert assess_scope(report)['computedState'] != 'in_scope'
