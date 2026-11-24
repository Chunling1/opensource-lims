from copy import deepcopy
from types import SimpleNamespace
import pytest

from app.extensions import db
from app.models import CapabilityEntry, CapabilityImportBatch, StdLibraryItem, OperationAudit, Report
from app.security import issue_token
from app.applications.quality_resources.testing_locations import available_testing_addresses

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture()
def setup(isolated_client, scenario_factory):
    dept = scenario_factory.department(name='参数维护测试部')
    other = scenario_factory.department(name='其他参数部')
    user = scenario_factory.user(dept, permissions=['quality.standard_library.view', 'entrust.sample_register.view'])
    for action in ['create', 'update', 'authorize']:
        scenario_factory.grant_action(user, 'quality.standard.' + action)
    old = StdLibraryItem(code='STD-OLD', name='旧标准', use_depts=dept.name)
    new = StdLibraryItem(code='STD-NEW', name='新标准', use_depts=dept.name)
    batch = CapabilityImportBatch(source_name='original.pdf', source_sha256='a'*64, status='active')
    db.session.add_all([old, new, batch]); db.session.flush()
    entry = CapabilityEntry(batch_id=batch.id, standard_item_id=old.id, standard_code=old.code,
        standard_name=old.name, capability_type='检测', certificate_no='CNAS-TEST',
        site='示例站点B', item_name='原参数', object_name='原检测对象', source_file='original.pdf',
        source_page=3, source_row=5, source_sha256='b'*64, active=True, mapping_status='confirmed',
        raw_cells={'standardWorkbook': {'address': '原完整检测地址', 'accreditation': 'CMA'}, 'original': ['原始行']})
    entry.departments = [dept]; db.session.add(entry); db.session.commit()
    return SimpleNamespace(client=isolated_client, headers={'Authorization':'Bearer '+issue_token(user)},
        factory=scenario_factory, user=user, dept=dept, other=other, old=old, new=new, entry=entry)


def data(s, standard=None, **changes):
    return dict(itemName='新增参数', objectName='新对象', site='示例站点B', address='新完整检测地址',
        departments=[s.dept.name], capabilityType='检测', active=True, reason='测试维护说明', **changes)


def create(s, value=None):
    return s.client.post(f'/api/quality/std-library/{s.new.id}/parameters', headers=s.headers,
                         json=value or data(s)).get_json()


def read(s, sid=None):
    return s.client.get(f'/api/quality/std-library/{sid or s.old.id}/parameters', headers=s.headers).get_json()['data']


def test_new_parameter_reusable_with_location_but_no_accreditation(setup):
    s=setup
    created=create(s)
    assert created['code']==0, created
    row=created['data']
    assert row['accreditation']=='内部维护' and row['internal'] and not row['certificateNo']
    picked=s.client.post('/api/reports/lib/capability-items', headers=s.headers,
        json={'standardItemId':s.new.id,'department':s.dept.name,'page':1}).get_json()
    assert [e['id'] for e in picked['data']['rows']]==[row['id']]
    assert picked['data']['rows'][0]['address']=='新完整检测地址'
    assert '新完整检测地址' in available_testing_addresses()
    assert OperationAudit.query.filter_by(action='quality.standard.parameter.create').count()==1


def test_old_revision_preserves_source_and_history_and_changes_lookup(setup):
    s=setup; source=deepcopy(s.entry.raw_cells)
    snapshot={'rawSample':{'capabilityEntryIds':[s.entry.id], 'capabilitySnapshots':[s.entry.to_row()],
                          'testLocation':'原完整检测地址', 'testItemOrder':[{'type':'library','id':s.entry.id}]}}
    report=Report(report_no='PARAM-HISTORY', detail=deepcopy(snapshot));db.session.add(report);db.session.commit()
    version=read(s)['rows'][0]['version']
    result=s.client.put(f'/api/quality/std-library/{s.old.id}/parameters/{s.entry.id}', headers=s.headers,
        json=data(s, version=version)).get_json()
    assert result['code']==0,result
    revised=db.session.get(CapabilityEntry,result['data']['id'])
    assert revised.id != s.entry.id and not s.entry.active
    assert revised.certificate_no==s.entry.certificate_no and revised.source_sha256==s.entry.source_sha256
    assert revised.raw_cells['standardWorkbook']==source['standardWorkbook']
    assert result['data']['address']=='新完整检测地址' and result['data']['accreditation']=='CMA'
    assert s.entry.item_name=='原参数' and s.entry.to_row()['address']=='原完整检测地址'
    db.session.refresh(report);assert report.detail==snapshot
    assert '新完整检测地址' in available_testing_addresses()
    assert '原完整检测地址' in available_testing_addresses()
    picked=s.client.post('/api/reports/lib/capability-items',headers=s.headers,
        json={'standardItemId':s.old.id,'page':1}).get_json()['data']['rows']
    assert {e['id'] for e in picked}=={s.entry.id,revised.id}
    assert next(e for e in picked if e['id']==s.entry.id)['superseded']
    old_edit=s.client.put(f'/api/quality/std-library/{s.old.id}/parameters/{s.entry.id}',headers=s.headers,
        json=data(s,version=version)).get_json()
    assert old_edit['code']!=0


def test_copy_old_to_new_does_not_copy_official_grants(setup):
    s=setup
    result=create(s,data(s,copyFromId=s.entry.id))
    assert result['code']==0,result
    row=result['data'];copied=db.session.get(CapabilityEntry,row['id'])
    assert row['accreditation']=='内部维护' and row['certificateNo']==''
    assert copied.raw_cells['copiedFrom']['entryId']==s.entry.id
    assert copied.standard_item_id==s.new.id and s.entry.active


@pytest.mark.parametrize('extra', [{'accreditation':'CMA'}, {'certificateNo':'FAKE'},
    {'sourceSha256':'f'*64}, {'effectiveDate':'2000-01-01'}, {'sourceFile':'fake.pdf'}])
def test_source_fields_cannot_be_forged(setup,extra):
    assert create(setup,{**data(setup),**extra})['code']!=0


def test_parameter_departments_are_not_a_separate_grant_and_reason_required(setup):
    s=setup
    created = create(s,{**data(s),'departments':[s.other.name]})
    assert created['code']==0 and created['data']['departments']==[]
    assert s.new.use_depts==s.dept.name
    assert create(s,{**data(s),'reason':''})['code']!=0
    assert CapabilityEntry.query.count()==2


def test_permissions_module_actions_and_department_scope(setup):
    s=setup
    manager=s.factory.user(s.dept, permissions=['quality.standard_library.view'])
    limited=s.factory.user(s.dept, permissions=['quality.standard_library_department.view'])
    unrelated=s.factory.user(s.dept, permissions=['entrust.sample_register.view'])
    db.session.commit()
    for user in (unrelated,limited):
        response=s.client.post(f'/api/quality/std-library/{s.new.id}/parameters',
            headers={'Authorization':'Bearer '+issue_token(user)},json=data(s)).get_json()
        assert response['code']==403
    response=s.client.get(f'/api/quality/std-library/{s.old.id}/parameters',
        headers={'Authorization':'Bearer '+issue_token(manager)}).get_json()
    assert response['code']==0
    # Full library module implies standard maintenance actions in the existing permission model.
    response=s.client.post(f'/api/quality/std-library/{s.new.id}/parameters',
        headers={'Authorization':'Bearer '+issue_token(manager)},json=data(s)).get_json()
    assert response['code']==0


def test_cross_standard_write_and_stale_version_rejected(setup):
    s=setup
    for sid,version in [(s.new.id,read(s)['rows'][0]['version']),(s.old.id,'stale')]:
        result=s.client.put(f'/api/quality/std-library/{sid}/parameters/{s.entry.id}',headers=s.headers,
            json=data(s,version=version)).get_json()
        assert result['code']!=0
    assert s.entry.item_name=='原参数'


def test_catalog_uses_bounded_pagination_and_search(setup):
    s=setup
    for i in range(25):db.session.add(StdLibraryItem(code=f'PAGE-{i}',name='分页标准'))
    db.session.commit()
    result=s.client.get('/api/quality/std-library/parameter-catalog?keyword=分页&page=2&size=20',headers=s.headers).get_json()['data']
    assert result['total']==25 and len(result['rows'])==5
    result=s.client.get(f'/api/quality/std-library/{s.old.id}/parameters?keyword=不存在',headers=s.headers).get_json()['data']
    assert result['total']==0 and result['rows']==[]

def test_standard_accreditation_is_independent_of_parameter_display_mark(setup, monkeypatch):
    from app import report_scope
    s=setup
    row=create(s)['data']
    monkeypatch.setattr(report_scope, 'find_controlled_standard', lambda *args: (s.new, {'singleList':True}))
    monkeypatch.setattr(report_scope, 'standard_scope_failures', lambda *args: [])
    monkeypatch.setattr(report_scope, 'standard_authorized_marks', lambda *args: ['CMA','CNAS'])
    report=Report(report_no='PARAM-SCOPE',department=s.dept.name,detail={'rawSample':{
        'testBases':[s.new.code], 'capabilityEntryIds':[row['id']], 'seal':'CMA'}})
    db.session.add(report);db.session.commit()
    result=report_scope.assess_scope(report)
    assert result['computedState']=='in_scope'
    assert result['standardRows'][0]['valid']
    assert result['rows'][0]['mark']=='内部维护' and result['rows'][0]['valid']
    assert '尚无资质来源确认' not in result['note']


def test_unchanged_save_does_not_invalidate_existing_parameter(setup):
    s=setup
    row=read(s)['rows'][0]
    result=s.client.put(f'/api/quality/std-library/{s.old.id}/parameters/{s.entry.id}',headers=s.headers,
        json={'version':row['version'],'reason':'核对后信息不变'}).get_json()
    assert result['code']==0,result
    assert result['data']['id']==s.entry.id and s.entry.active
    assert CapabilityEntry.query.count()==1


def test_shared_standard_variant_uses_owner_parameters(setup, monkeypatch):
    from app.applications.quality_resources import standard_parameters
    s=setup
    monkeypatch.setattr(standard_parameters, 'workbook_capability_owners', lambda: {s.old.id:s.old.id,s.new.id:s.old.id})
    result=read(s,s.new.id)
    assert result['sharedSource'] and result['rows'][0]['id']==s.entry.id
    updated=s.client.put(f'/api/quality/std-library/{s.new.id}/parameters/{s.entry.id}',headers=s.headers,
        json={'version':result['rows'][0]['version'],'itemName':'共享标准修订','reason':'同源版本维护'}).get_json()
    assert updated['code']==0,updated
    assert db.session.get(CapabilityEntry,updated['data']['id']).standard_item_id==s.old.id
    assert read(s)['rows'][0]['itemName']=='共享标准修订'

@pytest.mark.parametrize('selective',[False,True])
def test_internal_parameters_cannot_be_activated_as_cnas_source(setup,monkeypatch,selective):
    from app import cnas_capabilities
    from app.applications.quality_resources import testing_locations
    s=setup;row=create(s)['data'];entry=db.session.get(CapabilityEntry,row['id'])
    monkeypatch.setattr(testing_locations,'require_legacy_catalog_write_allowed',lambda:None)
    with pytest.raises(ValueError,match='不能作为资质来源激活'):
        if selective:
            cnas_capabilities.activate_confirmed_capability_entries(entry.batch_id,[entry.id],review_note='测试不能升级为资质')
        else:
            cnas_capabilities.activate_capability_batch(entry.batch_id)
    assert entry.to_row()['accreditation']=='内部维护'

def test_source_activation_keeps_superseded_parameter_retired(setup,monkeypatch):
    from app import cnas_capabilities
    from app.applications.quality_resources import testing_locations
    s=setup;version=read(s)['rows'][0]['version']
    result=s.client.put(f'/api/quality/std-library/{s.old.id}/parameters/{s.entry.id}',headers=s.headers,
        json=data(s,version=version)).get_json()
    assert result['code']==0,result
    monkeypatch.setattr(testing_locations,'require_legacy_catalog_write_allowed',lambda:None)
    with pytest.raises(ValueError,match='不能重新启用历史记录'):
        cnas_capabilities.activate_confirmed_capability_entries(s.entry.batch_id,[s.entry.id],review_note='不可恢复历史修订')
    s.entry.batch.attachment_count=42;s.entry.batch.chinese_page_count=791;db.session.flush()
    cnas_capabilities.activate_capability_batch(s.entry.batch_id)
    assert not s.entry.active
    assert db.session.get(CapabilityEntry,result['data']['id']).active


@pytest.mark.parametrize('plural', [True, False])
def test_same_code_parameters_respect_selected_record(setup, plural):
    s = setup
    s.new.code = s.old.code
    db.session.commit()
    english = create(s, data(s) | {'itemName': 'Thermal output'})['data']
    identity = {'standardItemIds': [s.new.id]} if plural else {'standardItemId': s.new.id}
    result = s.client.post('/api/reports/lib/capability-items', headers=s.headers,
        json={'allStandards': True, 'standardCodes': [s.old.code], 'department': s.dept.name, 'page': 1, **identity}).get_json()
    assert result['code'] == 0, result
    assert [row['id'] for row in result['data']['rows']] == [english['id']]
    assert result['data']['rows'][0]['itemName'] == 'Thermal output'
    assert db.session.get(CapabilityEntry, s.entry.id).item_name == '原参数'


@pytest.mark.parametrize('old_code', ["'EN 442-1:2014", '"EN 442-1:2014"', '`EN 442-1:2014`'])
@pytest.mark.parametrize('plural', [True, False])
def test_code_cleanup_keeps_selected_parameters_and_current_display(setup, old_code, plural):
    s = setup
    s.new.code = old_code
    s.new.name = 'Specification for radiators'
    s.old.code = 'EN 442-1:2014'
    s.old.controlled_no = 'CN-RECORD'
    s.entry.standard_code = s.old.code
    db.session.commit()
    english = create(s, data(s) | {'itemName': 'Dimensional deviations'})['data']
    changed = s.client.put(f'/api/quality/std-library/{s.new.id}', headers=s.headers,
                          json={'code': s.old.code}).get_json()
    assert changed['code'] == 0, changed
    identity = {'standardItemIds': [s.new.id]} if plural else {'standardItemId': s.new.id}
    body = {'allStandards': True, 'standardCodes': [s.old.code], 'page': 1,
            'department': s.dept.name, 'capabilityType': '检测', **identity}
    for hydration in ({}, {'ids': [english['id']]}):
        result = s.client.post('/api/reports/lib/capability-items', headers=s.headers,
                               json=body | hydration).get_json()
        assert result['code'] == 0, result
        assert [row['id'] for row in result['data']['rows']] == [english['id']]
        row = result['data']['rows'][0]
        assert row['standardCode'] == 'EN 442-1:2014'
        assert row['standardName'] == s.new.name
        assert row['address'] == '新完整检测地址'
        assert row['accreditation'] == '内部维护'
    # Picker display changes must not rewrite original parameter/history evidence.
    assert read(s, s.new.id)['rows'][0]['standardCode'] == old_code
    assert db.session.get(CapabilityEntry, english['id']).standard_code == old_code


def test_code_cleanup_preserves_id_binding_independent_of_source_edition(setup):
    from app.standard_control import capability_matches_standard
    s = setup
    s.new.code = "'EN 442-1:2014"
    english = create(s)['data']
    entry = db.session.get(CapabilityEntry, english['id'])
    s.new.code = 'EN 442-1:2014'
    s.old.code = s.new.code
    assert capability_matches_standard(entry, s.new)
    assert not capability_matches_standard(entry, s.old)
    s.new.code = 'EN 442-1:2026'
    db.session.commit()
    assert capability_matches_standard(entry, s.new)
    result = s.client.post('/api/reports/lib/capability-items', headers=s.headers,
        json={'allStandards': True, 'standardItemIds': [s.new.id],
              'standardCodes': [s.new.code], 'page': 1}).get_json()
    assert [row['id'] for row in result['data']['rows']] == [entry.id]


def test_standard_scope_uses_id_and_rejects_ambiguous_legacy(setup):
    from app.standard_control import selected_controlled_standards
    s = setup
    s.new.code = s.old.code
    s.old.auth_kind = 'CMA'
    s.new.out_of_scope = True
    db.session.commit()
    assert selected_controlled_standards([s.new.code], [s.new.id], s.dept.name)[0][0].id == s.new.id
    assert not selected_controlled_standards([s.new.code], [s.new.id], s.dept.name)[0][1]['valid']
    assert selected_controlled_standards([s.new.code], [], s.dept.name)[0][0] is None
    assert selected_controlled_standards([s.new.code], [999999], s.dept.name)[0][0] is None


def test_equipment_check_does_not_ignore_missing_ids_or_match_names(setup, monkeypatch):
    from app.models import EquipmentItem, Instrument
    from app.checks import compute_report_checks
    from types import SimpleNamespace
    from app import report_scope
    monkeypatch.setattr(report_scope, 'scope_projection', lambda _: dict(seal='',state='in_scope',standardRows=[],rows=[],note='',reviewApplied=False,outOfScope=False))
    equipment = EquipmentItem(archive_no='SAME', name='Meter', period='长期', status='在用')
    other = EquipmentItem(archive_no='SAME', name='Meter', period='长期', status='停用')
    db.session.add_all([equipment, other]); db.session.commit()
    def check(ids):
        return compute_report_checks(SimpleNamespace(detail={'checkInput': {'equipmentIds': ids,'instrument':'Meter'}}, project=''))[0][1]
    assert check([equipment.id])['status'] == '通过'
    assert check([other.id])['status'] == '不通过'
    assert check([equipment.id, 999999])['status'] == '不通过'
    db.session.add_all([Instrument(code='A',name='Legacy meter'),Instrument(code='B',name='Legacy meter')]);db.session.commit()
    report = SimpleNamespace(detail={'checkInput': {'instrument':'Legacy meter'}}, project='')
    assert compute_report_checks(report)[0][1]['status'] == '不在库内'
