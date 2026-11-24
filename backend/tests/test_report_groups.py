"""Number groups narrow authorized lists before paging; never grant access."""
import json
from pathlib import Path
import pytest
from app.extensions import db
from app.models import Report
from app.report_groups import CONFIG, GROUPS, apply_report_group
from app.security import issue_token
pytest_plugins = ('testkit.fixtures',)


def test_configuration_matches_frontend_and_user_scope():
    frontend = Path(__file__).parents[2] / 'frontend/src/platformUi/reportGroups.json'
    assert json.loads(frontend.read_text(encoding='utf-8')) == CONFIG
    assert list(GROUPS) == ['净化组','通风组','校准组','工程组','热湿组','检验']
    assert len({c for codes in GROUPS.values() for c in codes}) == 76
    assert {'SYR', 'SYHP', 'SYC', 'SYHR'} <= set(GROUPS['热湿组'])
    assert sum(map(len, GROUPS.values())) == 76


def test_exact_codes_aliases_derived_and_other_departments(isolated_app):
    with isolated_app.app_context():
        expected = {}
        for group, codes in GROUPS.items():
            for code in codes:
                number = 'LAB-2026' + code + '-0001'
                db.session.add(Report(report_no=number,department=CONFIG['department']))
                expected[number] = group
        for number, department, group in [
            ('2026H-0105（E）', CONFIG['department'], '净化组'),
            ('LAB-2026ZX-0002-1', CONFIG['department'], '净化组'),
            ('LAB-2026G（Ⅱ）-0002', CONFIG['department'], '工程组'),
            ('LAB-2026JG(I)-0002', CONFIG['department'], '未归组'),
            ('LAB-2026ZX-JH-0002', '净化空调检测部', None),
            ('LAB-2026QCFS3-0002(E)', '围护结构检测部', None),
            ('LAB-2026H-0009', '净化空调检测部', None),
            ('LAB-2026H-0010', '空调设备检测部-净化组', '净化组'),
            ('LAB-2026H-0011', '空调设备检测部（净化）', '净化组'),
            ('LAB-2026DFJ-0002', CONFIG['department'], '未归组'),
            ('LAB-2026KQS-0002', '建筑声学检测部', None),
            ('LAB-2026YP-0002', CONFIG['department'], '未归组'),
            ('unknown', CONFIG['department'], '未归组'),
        ]:
            db.session.add(Report(report_no=number,department=department));expected[number]=group
        db.session.commit()
        assert apply_report_group(Report.query, '').count() == len(expected)
        assert {r.report_no for r in apply_report_group(Report.query, '__ac_department__')} == {n for n,g in expected.items() if g is not None}
        for group in [*GROUPS, '未归组']:
            assert {r.report_no for r in apply_report_group(Report.query, group)} == {n for n,g in expected.items() if g==group}
        for value in ['声学组','示例站点H','示例站点C','bad',[],{},True,1]:
            with pytest.raises(ValueError):apply_report_group(Report.query,value)


@pytest.mark.parametrize('endpoint,view,state,sample',[
    ('reports','query','待打印','已领取'),('reports','contract_review','待合同评审','待入库'),
    ('reports','data_entry','检测录入中','已领取'),('reports','review','待审核','已领取'),
    ('reports','approval','待批准','已领取'),('samples','register','待合同评审','待入库'),
    ('samples','inbound','待样品入库','待入库'),('samples','outbound','待样品领取','已入库'),
])
def test_group_paging_scope_keyword_and_export(isolated_app,isolated_client,scenario_factory,endpoint,view,state,sample):
    from app.platform.workflow.visibility import REPORT_LIST_VIEW_PERMISSIONS,SAMPLE_LIST_VIEW_PERMISSIONS
    f=scenario_factory; d=f.department(name=CONFIG['department']);p,steps=f.project(d)
    permission=(REPORT_LIST_VIEW_PERMISSIONS if endpoint=='reports' else SAMPLE_LIST_VIEW_PERMISSIONS)[view]
    user=f.user(d,account='group_operator',permissions=[permission],project_steps=steps)
    blocked,_=f.project(d,authorize_department=False)
    for code,project in [('H',p),('ZX',p),('HC',p),('HR',p),('IAQ',blocked)]:
        number='LAB-2026'+code+'-0001'
        db.session.add(Report(report_no=number,sample_no=number,department=d.name,project=project.name,status=state,sample_status=sample,sample_reg_state='登记完成',detail={'dataEntryStarted':True,'rawSample':{'schemeCode':project.code,'schemeName':project.name}}))
    db.session.add(Report(report_no='FOREIGN-2026H-0001',department='foreign',status=state,sample_status=sample))
    db.session.commit();headers={'Authorization':'Bearer '+issue_token(user)}
    def run(**extra):
        body=dict(view=view,serverPage=True,reportGroup='净化组',presentation='report' if endpoint=='reports' else 'registration-sample',page=1,pageSize=1,sort='code')
        body.update(extra)
        result=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json=body).get_json()
        assert result['code']==0,result
        return result['data']
    outputs=[]
    for path in ('legacy','ids','a','a2'):
        isolated_app.config.update(LIST_PAGE_IDS=path=='ids',LIST_QUERY_PROTOTYPE=path=='a',LIST_QUERY_A2=path=='a2')
        # Query/register intentionally use broader read scope than processing.
        # Compare the intersection with the existing ungrouped view, not a new permission rule.
        allowed=[r['reportNo'] for r in run(reportGroup='',pageSize=200)['rows']]
        ids=[n for n in allowed if n in ['LAB-2026H-0001','LAB-2026ZX-0001','LAB-2026IAQ-0001']]
        assert 'FOREIGN-2026H-0001' not in allowed
        pages=[run(page=i) for i in range(1,len(ids)+1)]
        assert all(p['total']==len(ids) for p in pages)
        assert [r['reportNo'] for p in pages for r in p['rows']]==ids
        assert run(page=len(ids)+1)['rows']==[]
        assert [r['reportNo'] for r in run(pageSize=200)['rows']]==ids
        assert run(searchField='reportCode',contains='ZX')['total']==1
        outputs.append(pages)
    assert all(v==outputs[0] for v in outputs)
    assert {r['reportNo'] for r in run(serverPage=False,pageSize=200)['rows']}==set(ids)
    invalid=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json=dict(view=view,serverPage=True,reportGroup='bad')).get_json()
    assert invalid['code']==1


def test_group_predicate_mysql(prototype_mysql_app, caplog):
    from testkit.factories import ScenarioFactory
    from app.list_paging import load_report_page
    with prototype_mysql_app.app_context():
        f=ScenarioFactory();d=f.department(name=CONFIG['department']);user=f.user(d,role_key='admin',account='admin')
        for i,code in enumerate(['H','HC','HR','ZX-JH','JG（Ⅱ）','G(II)','DFJ']):
            db.session.add(Report(report_no='LAB-2026'+code+'-0001(E)',sample_no=str(i),department=d.name))
        db.session.commit()
        for path in ['legacy','a2']:
            prototype_mysql_app.config.update(LIST_PAGE_IDS=True,LIST_QUERY_PROTOTYPE=False,LIST_QUERY_A2=path=='a2')
            for group,count in [('净化组',1),('校准组',1),('热湿组',1),('工程组',2),('未归组',2)]:
                rows,meta=load_report_page(Report.query,user,'query',dict(reportGroup=group,pageSize=1,page=1,sort='code'))
                assert meta['total']==count and len(rows)==1
        assert 'list query prototype fallback' not in caplog.text
        assert 'list page ids fallback' not in caplog.text


from test_list_query_prototype import prototype_mysql_app, mysql_server
