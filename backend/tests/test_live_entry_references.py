"""Editable drafts follow current IDs; reads never rewrite completed snapshots."""
from copy import deepcopy
from datetime import datetime, date
from io import BytesIO
from docx import Document
import pytest
from app.extensions import db
from app.models import StdLibraryItem, Report
from app.entry_references import current_entry_references
from app.equipment_eligibility import evaluate_interval
from app.functions.report_standard_text import load_report_standard_names, load_report_standard_records
from test_equipment_department_authorization import case, headers
from test_capability_report_type import calibration_record
pytest_plugins = ('testkit.fixtures',)


def library(case):
    entry = calibration_record('检测')
    item = entry.standard_item
    item.use_depts = case[3].name
    raw = dict(testBases=[item.code],standardItemIds=[item.id],capabilityEntryIds=[entry.id],
        projectList=['旧参数','手填'],manualCapabilityItems=['手填'],
        capabilitySnapshots=[{'id':entry.id,'itemName':'旧参数'}],
        testItemOrder=[{'kind':'manual','name':'手填'},{'kind':'library','id':entry.id}])
    case[6].detail={'rawSample':deepcopy(raw)}
    db.session.commit()
    return entry,item,raw


def test_fresh_projection_keeps_ids_order_manual_and_saved_snapshot(case):
    entry,item,raw=library(case)
    item.name='当前标准名';entry.item_name='当前参数名';db.session.commit()
    client,user,*_=case
    response=client.get(f'/api/reports/{case[6].report_no}/entry-references',headers=headers(user))
    result=response.get_json()
    assert result['code']==0,result
    assert response.headers['Cache-Control']=='no-store'
    assert result['data']['projectList']==['手填','当前参数名']
    assert result['data']['standardRecords']==[{'id':item.id,'code':item.code,'name':'当前标准名'}]
    assert case[6].detail['rawSample']==raw
    # Metadata never adds new activation/type/date restrictions.
    entry.active=False;entry.mapping_status='pending';entry.batch.status='review';db.session.commit()
    assert current_entry_references(raw,user,case[3].name)['projectList']==['手填','当前参数名']


def test_bound_judgment_title_updates_without_replacing_free_text(case):
    entry,item,raw=library(case)
    raw['standardJudge']=item.code+'《旧名称》；手工约定'
    item.name='新名称';db.session.commit()
    values=current_entry_references(raw,case[1],case[3].name)
    assert values['standardJudge']==item.code+'；手工约定'
    assert values['standardRecords'][0]['name']=='新名称'
    assert raw['standardJudge'].endswith('《旧名称》；手工约定')
    raw['standardJudge']=item.code+' 第5条特殊约定；手工约定'
    assert 'standardJudge' not in current_entry_references(raw,case[1],case[3].name)


def test_save_rehydrates_current_names_dates_and_people(case,monkeypatch):
    monkeypatch.setattr('app.preview_cache.schedule_after_save',lambda *a:None)
    entry,item,raw=library(case)
    item.name='新标准';entry.item_name='新参数'
    row=case[5][0];row.name='新仪器';row.last_cal_date='2025-12-17';row.plan_cal_date='2026-12-16'
    row.actual_cal_date='2025-12-17';row.valid_until='2026-12-16';row.period='12个月'
    case[1].name='新姓名';db.session.commit()
    from app.edit_concurrency import test_form_version
    response=case[0].put(f'/api/reports/{case[6].report_no}/testinfo',headers=headers(case[1]),json={
        'testEditVersion':test_form_version(case[6]),'equipmentIds':[row.id],
        'testIntervals':[{'start':'2026-10-01','end':'2026-10-02'}],
        'standardShowName':True,'primaryTester1Code':case[1].account,
        'remark':'未保存手填内容','standards':[item.code]}).get_json()
    assert response['code']==0,response
    saved=case[6].detail
    assert saved['rawSample']['projectList']==['手填','新参数']
    assert saved['checkInput']['standardRecords'][0]['name']=='新标准'
    assert saved['checkInput']['equipmentSnapshots'][0]['lastCalDate']=='2025-12-17'
    assert saved['checkInput']['equipmentSnapshots'][0]['validUntil']=='2026-12-16'
    assert saved['checkInput']['people']['primaryTester1']['name']=='新姓名'
    assert saved['checkInput']['remark']=='未保存手填内容'


@pytest.mark.parametrize('language,separator', [('CN', '；\n'), ('EN', ', '), ('EN', '')])
def test_authoring_download_preserves_parameter_separator_and_selected_equipment_order(
    case, scenario_factory, isolated_app, language, separator,
):
    from app.blueprints.report_publication import ensure_prepared_query
    from app.docparser_field_only import ENGINE, report_context

    client, user, _, own, _, equipment, report, _, _, _, save = case
    entry, _, raw = library(case)
    entry.item_name = 'Updated Test'
    report.report_no = 'LAB-2026QA-0001'
    report.sample_no = '2026QA-0001'
    report.entrust_no = 'WT-2026-0001'
    report.detail = {'rawSample': {
        **raw, 'reportType': '产品报告', 'reportLanguage': language,
        'itemsSeparator': separator, 'commissionText': {'items': '手填' + separator + '旧参数'},
    }}
    for row, archive_no, name in zip(equipment[:2], ('QA-01', 'QA-02'), ('Gauge, type A', 'Meter')):
        row.dept, row.archive_no, row.name = own.name, archive_no, name
    scenario_factory.grant_action(user, 'report.attachment.upload')
    isolated_app.config.update(DOCUMENT_TEMPLATE_ENGINE=ENGINE, REPORT_QUERY_ORIGIN='https://example.invalid')
    ensure_prepared_query(report)
    db.session.commit()
    ids = [equipment[1].id, equipment[0].id]
    assert save(ids)['code'] == 0
    check = report.detail['checkInput']
    expected_items = '手填' + separator + 'Updated Test'
    assert [row['id'] for row in check['equipmentSnapshots']] == ids
    assert report_context(report)['Items'] == expected_items
    response = client.get(f'/api/reports/{report.report_no}/authoring-template', headers=headers(user))
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', response.json
    doc = Document(BytesIO(response.data))
    cells = [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    assert any(expected_items in cell for cell in cells)
    instruments = next(cell for cell in cells if 'Gauge, type A' in cell)
    assert instruments.index('Meter') < instruments.index('Gauge, type A')


def test_new_parameter_formatting_preserves_names_and_old_confirmed_values():
    from app.document_field_projection import test_items as project_items
    from app.report_documents import report_values
    from test_docparser_deep_integration import report

    item = report()
    raw = item.detail['rawSample']
    raw.update(itemsSeparator='；', commissionText={'items': 'Wind, type A；Pressure'},
               projectList=['Wind, type A', 'Pressure'])
    assert report_values(item)['testItems'] == '参数A'
    assert project_items(item.detail, '参数A', separator='；') == 'Wind, type A；Pressure'
    raw.pop('projectList')
    assert project_items(item.detail, '参数A', separator='；') == raw['commissionText']['items']


@pytest.mark.parametrize('change',['deleted','code','department','parameter_deleted','parameter_owner'])
def test_no_silent_fallback_or_method_switch(case,change):
    entry,item,raw=library(case)
    duplicate=StdLibraryItem(code=item.code,name='不能替换为同编号记录',use_depts=case[3].name)
    db.session.add(duplicate);db.session.flush()
    if change=='deleted':item.deleted_at=datetime.utcnow()
    elif change=='code':item.code='DIFFERENT-2026'
    elif change=='department':item.use_depts='其他部门'
    elif change=='parameter_deleted':db.session.delete(entry)
    else:entry.standard_item_id=duplicate.id
    db.session.commit()
    with pytest.raises(ValueError):current_entry_references(raw,case[1],case[3].name)
    assert case[6].detail['rawSample']==raw


def test_deleted_standard_never_supplies_a_name(case):
    entry,item,raw=library(case);item.deleted_at=datetime.utcnow();db.session.commit()
    assert load_report_standard_names([item.code],[item.id])=={item.code:''}
    assert load_report_standard_records([item.code],[item.id])==[]


@pytest.mark.parametrize('status', ['待打印', '待发放', '已发放', '已归档'])
def test_completed_read_and_cross_scope_do_not_change_history(case, status):
    entry,item,raw=library(case);case[6].status=status;entry.item_name='新参数';db.session.commit()
    result=case[0].get(f'/api/reports/{case[6].report_no}/entry-references',headers=headers(case[1])).get_json()
    assert result['code']==0
    assert result['data']=={}
    assert case[6].detail['rawSample']==raw
    result=case[0].get('/api/reports/QA-HIDDEN/entry-references',headers=headers(case[1])).get_json()
    assert result['code']==403



def test_authorized_people_reads_current_name_and_excludes_disabled_accounts(case):
    client,user,admin,*_=case
    user.name='人员库当前姓名';db.session.commit()
    url=f'/api/reports/{case[6].report_no}/authorized-people'
    values=client.get(url,headers=headers(admin)).get_json()
    assert values['code']==0,values
    assert next(p for p in values['data']['testers'] if p['code']==user.account)['name']=='人员库当前姓名'
    user.enabled=False;db.session.commit()
    values=client.get(url,headers=headers(admin)).get_json()
    assert all(p['code']!=user.account for p in values['data']['testers'])


from test_admin_corrections import workspace, loaded_form


def test_completed_correction_preserves_unchanged_reference_snapshots(workspace):
    from app.models import EquipmentItem
    client, actors, rows, _ = workspace
    user, report = actors[1], rows[2]
    equipment = EquipmentItem(archive_no='QA-COMPLETE', name='当前仪器', period='长期')
    db.session.add(equipment);db.session.flush()
    saved_equipment = dict(id=equipment.id,archiveNo='QA-COMPLETE',name='历史仪器',spec='',maker='',factoryNo='')
    saved_person = dict(id=user.id,code=user.account,name='历史姓名')
    saved_standard = dict(id=9988,code='QA 1',name='历史标准')
    report.detail = {'rawSample':{'testBases':['QA 1']},'checkInput':{
        'equipmentIds':[equipment.id],'equipmentSnapshots':[saved_equipment],
        'people':{'primaryTester1':saved_person},'standards':['QA 1'],
        'standardNames':{'QA 1':'历史标准'},'standardRecords':[saved_standard]}}
    db.session.commit()
    record=client.get(f'/api/admin-corrections/reports/{report.id}',headers=headers(user)).get_json()['data']
    result=client.put(f'/api/reports/{report.report_no}/testinfo',headers=headers(user),json=loaded_form(client,f'/api/reports/{report.report_no}/testinfo',{
        'equipmentIds':[equipment.id],'primaryTester1Code':user.account,'standardShowName':True,
        'remark':'仅改备注','adminCorrection':{'revision':record['revision'],'confirmed':True,'reason':'核对备注'}})).get_json()
    assert result['code']==0,result
    saved=report.detail['checkInput']
    assert saved['equipmentSnapshots']==[saved_equipment]
    assert saved['people']['primaryTester1']==saved_person
    assert saved['standardRecords']==[saved_standard]
    assert saved['standardNames']=={'QA 1':'历史标准'}
    assert saved['remark']=='仅改备注'
