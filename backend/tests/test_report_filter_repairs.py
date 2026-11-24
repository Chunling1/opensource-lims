import pytest
from sqlalchemy import select
from app.extensions import db
from app.models import Report, Entrust
from app.security import issue_token
from app.list_paging import report_fields
from app.applications.report_lifecycle.query_details import query_details
from test_sealed_archive_release import seal, prepared
from test_list_query_prototype import prototype_mysql_app, mysql_server

pytest_plugins=('testkit.fixtures',)

@pytest.mark.parametrize('view',['query','review','approval','print','archive','release'])
def test_report_only_account_can_load_new_plan_filter(isolated_client,scenario_factory,view):
    user=scenario_factory.identity_scenario(permission_codes=('report.'+view+'.view',)).user
    headers={'Authorization':'Bearer '+issue_token(user)}
    result=isolated_client.post('/api/reports/query',headers=headers,json={'view':view,'serverPage':True}).get_json()
    assert result['code']==0,result
    result=isolated_client.post('/api/reports/plan-counts',headers=headers,json={'view':view}).get_json()
    assert result['code']==0,result

def test_current_seal_completion_has_issuance_filter_date(prepared):
    report,version,user,raw=prepared
    seal(prepared)
    row=query_details([report])[report.report_no]
    assert row['issueStatus']=='已签发'
    fields=report_fields('report')
    sql_date=db.session.execute(select(fields['printDate']).select_from(Report).outerjoin(Entrust,Report.entrust_no==Entrust.entrust_no)).scalar()
    assert row['printDate'] and sql_date,(row['issueStatus'],row['printDate'],sql_date)

def test_mysql_combined_filters_preserve_a2_results(prototype_mysql_app):
    from datetime import datetime
    from app.models import OperationAudit
    from app.list_paging import _report_page
    from app.list_projection import list_reports
    from testkit.factories import ScenarioFactory
    with prototype_mysql_app.app_context():
        factory=ScenarioFactory();department=factory.department()
        user=factory.user(department,role_key='admin',account='admin')
        report=Report(report_no='QA-COMBINATION',sample_no='QA-SAMPLE',department=department.name,status='待批准',sample_status='已领取',detail={'checkInput':{'resultStatus':'判定合格'},'rawSample':{'sampleName':'QA SAMPLE','deliverWay':'邮寄','schemeCode':'P','schemeName':'PLAN'}})
        db.session.add(report)
        for action in ('report.review.pass','sample.dispose','sample.register.void'):
            db.session.add(OperationAudit(object_type='report',object_id=report.report_no,action=action,success=True,created_at=datetime(2026,11,1,17)))
        db.session.commit()
        for extra in ({'conclusion':'合格'},{'collectionMethod':'邮寄'},{'dateField':'auditDate','from':'2026-11-02','to':'2026-11-02'}, {'releaseStatus':'未发放'}, {'issueStatus':'未签发'}, {'dateField':'disposalDate','from':'2026-11-02'}, {'dateField':'voidedAt','to':'2026-11-02'}, {'plans':{'groupIds':[department.name],'planIds':[],'excludedPlanIds':[]}}):
            body={'view':'query','presentation':'report','searchField':'all','contains':'QA','sort':'code',**extra}
            actual=[]
            for enabled in (False,True):
                page,meta=_report_page(Report.query,user,'query',body,prototype=enabled,a2=enabled,allow_page_ids=False)
                actual.append((meta['total'],[r.report_no for r in list_reports(page,page_ids=getattr(meta,'page_ids',None))]))
            assert actual[0]==actual[1]==(1,['QA-COMBINATION']),(extra,actual)

@pytest.mark.parametrize('view,status,step',[('query','待审核',None),('review','待审核','report_review'),('approval','待批准','report_approval'),('print','待打印','report_print'),('archive','待发放','report_archive'),('release','待发放',None)])
def test_plan_counts_equal_module_visibility_and_deny_wrong_page(isolated_client,scenario_factory,view,status,step):
    scenario=scenario_factory.identity_scenario(permission_codes=('report.'+view+'.view',),granted_step_codes=(step,) if step else ())
    other=scenario_factory.department()
    for number,department in [('IN',scenario.department.name),('OUT',other.name)]:
        db.session.add(Report(report_no=number,sample_no=number,department=department,project=scenario.project.name,status=status,archive_state='归档完成' if view=='release' else '',detail={'rawSample':{'schemeCode':scenario.project.code,'schemeName':scenario.project.name}}))
    db.session.commit()
    headers={'Authorization':'Bearer '+issue_token(scenario.user)}
    def post(path,body):return isolated_client.post('/api/reports/'+path,headers=headers,json=body).get_json()
    listing=post('query',{'view':view,'serverPage':True,'presentation':'report'})
    counts=post('plan-counts',{'view':view})
    assert listing['code']==counts['code']==0,(listing,counts)
    assert listing['data']['total']==1,listing
    assert sum(r['sampleCount'] for r in counts['data']['rows'])==1,counts
    assert all(r['department']==scenario.department.name for r in counts['data']['rows'])
    denied=post('plan-counts',{'view':'release' if view!='release' else 'query'})
    assert denied['code']==403,denied
    if step and view!='archive':
        scenario.user.project_steps.clear();db.session.commit()
        assert not post('plan-counts',{'view':view})['data']['rows']


def test_plan_counts_on_mysql_strict_group_by(prototype_mysql_app):
    from sqlalchemy import text
    from flask import g
    from app.blueprints.reports import report_plan_counts
    from testkit.factories import ScenarioFactory
    with prototype_mysql_app.app_context(),prototype_mysql_app.test_request_context('/api/reports/plan-counts',method='POST',json={'view':'query'}):
        factory=ScenarioFactory();department=factory.department();user=factory.user(department,role_key='admin',account='admin')
        db.session.add(Report(report_no='QA-STRICT-PLAN',department=department.name,status='待审核',detail={'rawSample':{'schemeCode':'P','testDept':department.name}}));db.session.commit()
        db.session.execute(text("SET SESSION sql_mode = CONCAT_WS(',',@@sql_mode,'ONLY_FULL_GROUP_BY')"))
        g.current_user=user
        result=report_plan_counts.__wrapped__().get_json()
        assert result['code']==0
        assert sum(row['sampleCount'] for row in result['data']['rows'])==1


def test_sample_counts_on_mysql_strict_group_by(prototype_mysql_app):
    from sqlalchemy import text
    from flask import g
    from app.blueprints.samples import plan_counts
    from testkit.factories import ScenarioFactory
    with prototype_mysql_app.app_context(), prototype_mysql_app.test_request_context():
        factory = ScenarioFactory()
        department = factory.department()
        g.current_user = factory.user(department, role_key='admin', account='admin')
        for i, (status, sample_status, detail) in enumerate([
            ('待样品入库', '', {'rawSample': {'schemeCode': 'P', 'testDept': '现场'}}),
            ('待样品领取', '已入库', {'rawSample': {'schemeCode': 'P', 'testDept': '现场'}}),
            ('检测录入中', '已领取', {'rawSample': {'schemeCode': 'Q'}}),
            ('检测更改中', '已领取', {'rawSample': {'schemeCode': 'Q'}}),
            ('待打印', '已领取', {'rawSample': {'schemeCode': 'Q'}}),
        ]):
            db.session.add(Report(report_no=f'QA-SAMPLE-STRICT-{i}', department=department.name,
                status=status, sample_status=sample_status, detail=detail))
        db.session.add(Report(report_no='QA-VOID', department=department.name, voided=True))
        db.session.commit()
        db.session.execute(text("SET SESSION sql_mode = CONCAT_WS(',',@@sql_mode,'ONLY_FULL_GROUP_BY')"))
        result = plan_counts.__wrapped__().get_json()
        assert result['code'] == 0
        rows = {row['schemeCode']: row for row in result['data']['rows']}
        assert len(rows) == 2
        assert rows['P']['testDepartment'] == '现场'
        assert rows['Q']['testDepartment'] == department.name
        for key, expected in {'flowSampleCount': 5, 'disposalSampleCount': 1,
            'taskQuerySampleCount': 3, 'dataEntrySampleCount': 1, 'dataChangeSampleCount': 1,
            'inboundSampleCount': 1, 'outboundSampleCount': 1}.items():
            assert sum(row[key] for row in rows.values()) == expected
