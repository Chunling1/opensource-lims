"""Original-sample picker: workflow breadth, pagination and data boundaries."""
import pytest
from app.extensions import db
from app.models import Report
from testkit.factories import login_headers

pytest_plugins = ('testkit.fixtures',)

@pytest.fixture
def sources(isolated_app, isolated_client, scenario_factory):
    with isolated_app.app_context():
        own = scenario_factory.department(name='虚拟来源部门')
        actor = scenario_factory.user(own, account='source_picker', permissions=('entrust.sample_register.view',))
        for index, state in enumerate(['待合同评审', '待入库', '待领取', '检测录入中', '待审核', '待批准', '已发放']):
            db.session.add(Report(report_no=f'LAB-2026TEST-{index:04}', sample_no=f'2026TEST-{index:04}',
                project='TEST', project_name=f'虚拟项目{index}', client='虚拟客户', template='TEST', version='1',
                status=state, sign='', department=own.name, owner=actor.name,
                detail={'checkInput': {'standard': 'GB TEST'}} if index == 3 else {},
                voided=False, sample_reg_state='登记中' if index == 0 else '登记完成'))
        db.session.add(Report(report_no='LAB-VOID', sample_no='VOID', project='TEST', project_name='作废',
            client='虚拟客户', template='TEST', version='1', status='待合同评审', sign='', department=own.name,
            owner=actor.name, detail={}, voided=True))
        db.session.add(Report(report_no='LAB-FOREIGN', sample_no='FOREIGN', project='TEST', project_name='跨部门',
            client='虚拟客户', template='TEST', version='1', status='待合同评审', sign='', department='其他部门',
            owner='其他人员', detail={}, voided=False))
        db.session.commit()
    return login_headers(isolated_client, 'source_picker')

def page(client, headers, **body):
    return client.post('/api/reports/derivable', headers=headers, json={'category':'分项', **body}).get_json()

@pytest.mark.parametrize('category', ['分项', '英文'])
def test_all_stages_without_check_input_are_selectable(isolated_client, sources, category):
    data = page(isolated_client, sources, category=category)['data']
    assert data['total'] == 7
    assert {r['status'] for r in data['rows']} == {'待合同评审','待入库','待领取','检测录入中','待审核','待批准','已发放'}
    assert all('detail' not in r for r in data['rows'])

def test_paging_and_search_never_limit_to_first_page(isolated_client, sources):
    first = page(isolated_client, sources, size=2)['data']
    second = page(isolated_client, sources, size=2, page=2)['data']
    assert first['total'] == second['total'] == 7
    assert len(first['rows']) == len(second['rows']) == 2
    assert not {r['reportNo'] for r in first['rows']} & {r['reportNo'] for r in second['rows']}
    found = page(isolated_client, sources, keyword='2026TEST-0000')['data']
    assert found['total'] == 1
    assert found['rows'][0]['sampleNo'] == '2026TEST-0000'
    assert page(isolated_client, sources, size=1000)['data']['size'] == 50
    assert page(isolated_client, sources, page=100)['data']['rows'] == []

@pytest.mark.parametrize('keyword', ['FOREIGN','VOID','%','_'])
def test_scope_void_and_literal_search(isolated_client, sources, keyword):
    assert page(isolated_client, sources, keyword=keyword)['data']['total'] == 0

@pytest.mark.parametrize('category', ['补充','普通'])
def test_other_categories_retain_existing_standard_requirement(isolated_client, sources, category):
    data = page(isolated_client, sources, category=category)['data']
    assert data['total'] == 1
    assert data['rows'][0]['sampleNo'] == '2026TEST-0003'

def test_invalid_paging_is_reported(isolated_client, sources):
    assert page(isolated_client, sources, page='bad')['code'] == 1

def test_existing_derivative_exposes_root_number(isolated_app, isolated_client, sources):
    with isolated_app.app_context():
        row = Report.query.filter_by(sample_no='2026TEST-0006').one()
        row.main_report_no = 'LAB-2026TEST-0000'
        db.session.commit()
    data = page(isolated_client, sources, keyword='2026TEST-0006')['data']
    assert data['rows'][0]['mainReportNo'] == 'LAB-2026TEST-0000'

@pytest.mark.parametrize('source', ['LAB-FOREIGN','LAB-VOID','LAB-MISSING'])
def test_save_rechecks_original_source_scope(isolated_app, isolated_client, sources, source):
    from app.models import Entrust
    with isolated_app.app_context():
        db.session.add(Entrust(entrust_no='WT-TEST', status='委托完成', info={}, department='虚拟来源部门'))
        db.session.commit()
    response = isolated_client.post('/api/reports/create', headers=sources, json={
        'entrustNo':'WT-TEST','reportCategory':'分项','baseReportNo':source,
        'reportNo':source+'-1','regState':'登记中',
    }).get_json()
    assert response['code'] == 1
    assert '原报告不存在、已作废或不在数据范围内' in response['message']

def test_registration_stage_source_can_save_derived_draft(isolated_app, isolated_client, sources, monkeypatch):
    from app.models import Entrust
    from app.blueprints import reports as routes
    from app import sample_preview_warmup
    monkeypatch.setattr(sample_preview_warmup, 'schedule_after_save', lambda *a: None)
    # Unrelated date/price/catalog gates are covered by registration suites;
    # exercise the real source resolution, numbering, inheritance and insert.
    monkeypatch.setattr(routes, 'sample_party_error', lambda *a, **k: None)
    monkeypatch.setattr(routes, 'sample_price_error', lambda *a, **k: None)
    monkeypatch.setattr(routes, '_validate_sample_detail_dates', lambda user, detail, ent, **kw: (detail,None))
    monkeypatch.setattr(routes, '_validate_sample_registration_completion', lambda user, detail, ent, **kw: (detail,'incomplete draft'))
    with isolated_app.app_context():
        db.session.add(Entrust(entrust_no='WT-TEST', status='委托完成', info={}, client='虚拟客户', project_name='虚拟项目', department='虚拟来源部门'))
        base=Report.query.filter_by(report_no='LAB-2026TEST-0000').one()
        base.detail={'sourceMarker':'retained','rawSample':{'sampleName':'原样品'}}
        db.session.commit()
    response = isolated_client.post('/api/reports/create', headers=sources, json={
        'entrustNo':'WT-TEST','reportCategory':'分项','baseReportNo':'LAB-2026TEST-0000',
        'reportNo':'LAB-2026TEST-0000-1','regState':'登记中','detail':{},'project':'TEST',
    }).get_json()
    assert response['code'] == 0, response
    with isolated_app.app_context():
        result=Report.query.filter_by(report_no='LAB-2026TEST-0000-1').one()
        assert result.main_report_no == 'LAB-2026TEST-0000'
        assert result.detail['sourceMarker'] == 'retained'
        assert result.detail['rawSample']['sampleName'] == '原样品'


def test_english_source_needs_only_sample_number_and_preserves_scope(isolated_app, isolated_client, sources):
    with isolated_app.app_context():
        row = Report.query.filter_by(sample_no='2026TEST-0006').one()
        row.sample_no = ' '
        db.session.commit()
    assert page(isolated_client, sources, category='英文')['data']['total'] == 6
    found = page(isolated_client, sources, category='英文', keyword='2026TEST-0000')['data']
    assert found['total'] == 1
    for keyword in ('FOREIGN', 'VOID'):
        assert page(isolated_client, sources, category='英文', keyword=keyword)['data']['total'] == 0
