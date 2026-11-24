from copy import deepcopy
import pytest
from app.extensions import db
from app.models import Report
from app.authorization_scope import project_for_report, project_step_error
from app.list_projection import list_reports
from app.security import issue_token
from app.preflight_reads import reuse_preflight_reads
pytest_plugins = ('testkit.fixtures',)

@pytest.fixture
def case(scenario_factory, isolated_client):
    f=scenario_factory;dept=f.department()
    first,_=f.project(dept,name='示例站点B方案');second,steps=f.project(dept,name='示例站点F方案')
    first.number_code=second.number_code='QC1'
    user=f.user(dept,permissions=['entrust.contract_review.view'],project_steps=[s for s in steps if s.step_code=='entrust_review'])
    source=Report(report_no='TEST-2026QC1-0558',sample_no='2026QC1-0558',entrust_no='WT-TEST',department=dept.name,report_kind='main',status='检测录入中',detail={'rawSample':{'schemeCode':'QC1','schemeName':second.name}})
    derived=Report(report_no=source.report_no+'(E)',sample_no=source.sample_no,entrust_no=source.entrust_no,department=dept.name,report_kind='english',main_report_no=source.report_no,status='待合同评审',sample_reg_state='登记完成',detail={'derivedFrom':source.report_no,'rawSample':{'schemeCode':'QC1','schemeName':'','baseReportNo':source.report_no}})
    db.session.add_all([source,derived]);db.session.commit()
    return isolated_client,user,source,derived,first,second

def test_legacy_derivative_visible_and_read_only(case):
    client,user,source,r,_,project=case;before=deepcopy(r.detail);version=r.edit_version
    assert project_for_report(r).id==project.id
    projected=list_reports(Report.query.filter_by(id=r.id))[0]
    assert project_for_report(projected).id==project.id
    assert not project_step_error(user,projected,'entrust_review','合同评审')
    result=client.post('/api/reports/query',json={'view':'contract_review'},headers={'Authorization':'Bearer '+issue_token(user)}).get_json()
    assert result['code']==0,result
    assert r.report_no in [row['reportNo'] for row in result['data']['rows']]
    response=client.get('/api/reports/'+r.report_no,query_string={'view':'contract_review'},headers={'Authorization':'Bearer '+issue_token(user)}).get_json()
    assert response['code']==0,response
    db.session.expire_all();assert r.detail==before and r.edit_version==version

@pytest.mark.parametrize('fault',['name','code','reference','raw_reference','department','entrust','source_voided','source_missing','self','source_derived','source_ambiguous','main'])
def test_conflicting_identity_never_falls_back(case,fault):
    _,_,source,r,_,_=case;d=deepcopy(r.detail)
    if fault=='name':d['rawSample']['schemeName']='无效方案'
    if fault=='code':d['rawSample']['schemeCode']='UNKNOWN'
    if fault=='reference':d['derivedFrom']='OTHER'
    if fault=='raw_reference':d['rawSample']['baseReportNo']='OTHER'
    if fault=='department':r.department='其他部门'
    if fault=='entrust':r.entrust_no='OTHER'
    if fault=='source_voided':source.voided=True
    if fault=='source_missing':r.main_report_no='MISSING';d['derivedFrom']='MISSING';d['rawSample']['baseReportNo']='MISSING'
    if fault=='self':r.main_report_no=r.report_no
    if fault=='source_derived':source.report_kind='english'
    if fault=='source_ambiguous':source.detail={'rawSample':{'schemeCode':'QC1'}}
    if fault=='main':r.report_kind='main'
    r.detail=d;db.session.commit()
    assert project_for_report(r) is None
    assert project_for_report(list_reports(Report.query.filter_by(id=r.id))[0]) is None

def test_does_not_grant_other_project_permission(case):
    client,user,source,r,first,_=case
    source.detail={'rawSample':{'schemeCode':'QC1','schemeName':first.name}};db.session.commit()
    assert project_for_report(r).id==first.id
    assert '未取得' in project_step_error(user,r,'entrust_review','合同评审')
    result=client.post('/api/reports/query',json={'view':'contract_review'},headers={'Authorization':'Bearer '+issue_token(user)}).get_json()
    assert r.report_no not in [row['reportNo'] for row in result['data']['rows']]

def test_same_missing_scheme_different_parent_cache_is_separate(case):
    _,_,source,r,first,second=case
    other=Report(report_no='TEST-2026QC1-0559',entrust_no=source.entrust_no,department=source.department,report_kind='main',detail={'rawSample':{'schemeCode':'QC1','schemeName':first.name}})
    clone=Report(report_no=other.report_no+'(E)',entrust_no=source.entrust_no,department=r.department,report_kind='english',main_report_no=other.report_no,detail={'rawSample':{'schemeCode':'QC1'}})
    db.session.add_all([other,clone]);db.session.commit()
    @reuse_preflight_reads
    def resolve():return [project_for_report(x).id for x in (r,clone,r)]
    assert resolve()==[second.id,first.id,second.id]
