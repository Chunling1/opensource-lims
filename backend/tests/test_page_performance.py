"""Synthetic all-module read-only benchmark; no production data or endpoints."""
import cProfile
import io
import json
import pstats
import time
import hashlib
from collections import Counter
from datetime import datetime

import pytest
from sqlalchemy import event
from app.extensions import db
from app.models import Agreement, Entrust, Report, StdLibraryItem, OperationAudit, EquipmentItem, Personnel, FinanceBill, User, Standard
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture()
def benchmark(isolated_app, scenario_factory, monkeypatch):
    f = scenario_factory
    department = f.department(name='性能验证部门')
    from app.catalog import MODULES
    user = f.user(department, role_key='admin', permissions=['dashboard.view'])
    project, _ = f.project(department, name='性能验证项目')
    standards = [StdLibraryItem(code=f'BENCH-{i}', name=f'虚拟标准{i}', use_depts=department.name, auth_kind='CNAS') for i in range(2000)]
    db.session.add_all(standards)
    db.session.flush()
    today = datetime.utcnow().replace(hour=0,minute=0,second=0,microsecond=0)
    statuses = ['待合同评审','待样品入库','待样品领取','检测录入中','待审核','待批准','待打印','已发放']
    for i in range(200):
        a = Agreement(agreement_no=f'BENCH-HT-{i}', client='虚拟客户', status='已登记', created_at=today, info={'note':'备注'})
        e = Entrust(entrust_no=f'BENCH-WT-{i}', contract_no=a.agreement_no, department=department.name, owner=user.name, status='委托完成', created_at=today, info={'entrustDate':'2026-10-01'})
        detail = {'rawSample': {'standardItemIds':[standards[i].id], 'testBases':[standards[i].code], 'sendDate':'2026-10-01', 'sampleName':'测试样品', 'testDept':department.name}, 'checkInput':{'standards':[standards[i].code], 'testDate':'2026-10-02'}, 'entrustSnapshot':{'info':{}}, 'largeUnused': 'x'*30000}
        r=Report(report_no=f'BENCH-R-{i:04}',sample_no=f'BENCH-S-{i:04}',entrust_no=e.entrust_no,department=department.name,owner=user.name,project=project.name,status=statuses[i%8],sample_status='已入库',sample_reg_state='登记完成',detail=detail)
        db.session.add_all([a,e,r])
        db.session.add_all([
            Standard(code=f'MASTER-{i}',name='虚拟主标准'),
            EquipmentItem(archive_no=f'EQ-{i}',name='虚拟设备',dept=department.name,period='长期',remark='x'*30000),
            Personnel(code=f'bench-person-{i}',name=f'虚拟人员{i}',dept=department.name,remark='x'*30000),
            User(account=f'bench-person-{i}',name=f'虚拟人员{i}',password_hash=user.password_hash,role_key='operator',role_name='测试人员',home_path='/dashboard',department_id=department.id),
            FinanceBill(bill_no=f'BILL-{i}',entrust_no=e.entrust_no,department=department.name,status=['待计价','待收款','待收款确认','待开票','待结算','已结算'][i%6],created_at=today,updated_at=today),
        ])
        for action in ['sample.register.complete','report.data_entry.complete','report.review.pass']:
            db.session.add(OperationAudit(object_type='report',object_id=r.report_no,action=action,success=True,account=user.account,user_name=user.name,user_id=user.id,created_at=today,before_data={'large':'x'*30000},after_data={'large':'x'*30000}))
    db.session.commit()
    token = issue_token(user)
    db.session.remove()
    return isolated_app.test_client(), {'Authorization':'Bearer '+token}


def test_serve_local_pages(benchmark):
    import os
    if os.getenv('SERVE_SYNTHETIC_PERFORMANCE') != '1':
        pytest.skip('Opt-in isolated browser fixture server only')
    client, headers = benchmark
    print('SYNTHETIC_AUTH '+headers['Authorization'], flush=True)
    from werkzeug.serving import make_server
    make_server('0.0.0.0', 5498, client.application, threaded=True).serve_forever()


def test_all_page_read_benchmark(benchmark):
    client, headers = benchmark
    endpoints = [('委托','POST','/api/entrust/query',{'projection':'list'})]
    endpoints += [('样品/'+view,'POST','/api/samples/query',{'view':view}) for view in ['register','inbound','outbound','flow_query']]
    endpoints += [('报告/'+view,'POST','/api/reports/query',{'view':view}) for view in ['query','contract_review','data_entry','data_change','review','approval','print','archive']]
    endpoints += [('标准维护','GET','/api/quality/std-library',None),('标准主数据','GET','/api/quality/standards',None),('标准选择','GET','/api/quality/std-library/search',None),('仪器维护','GET','/api/quality/equipment',None),('人员维护','GET','/api/quality/personnel',None),('组织机构','GET','/api/admin/departments/tree',None),('用户管理','GET','/api/admin/users',None),('项目管理','GET','/api/admin/project-masters',None),('工作台','POST','/api/auth/workbench',{})]
    for name, method, url, body in endpoints:
        queries=[]
        def query(_c,_cu,statement,*_a): queries.append(statement)
        event.listen(db.engine,'before_cursor_execute',query)
        profile=cProfile.Profile()
        started=time.perf_counter()
        try:
            profile.enable()
            with client.application.app_context():
                response=client.open(url,method=method,headers=headers,json=body)
            profile.disable()
        finally:
            event.remove(db.engine,'before_cursor_execute',query)
        elapsed=time.perf_counter()-started
        data=response.get_json() or {}
        stable=dict(data.get('data') or {})
        stable.pop('updatedAt',None)
        digest=hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        print('PERF '+json.dumps({'page':name,'seconds':round(elapsed,4),'queries':len(queries),'bytes':len(response.data),'http':response.status_code,'code':data.get('code'),'message':data.get('message'),'sha256':digest},ensure_ascii=False))
        if elapsed>0.3:
            output=io.StringIO()
            pstats.Stats(profile,stream=output).strip_dirs().sort_stats('cumtime').print_stats(18)
            print(output.getvalue())
            print('QUERIES',Counter(q.split('FROM ')[-1].split('\n')[0][:100] for q in queries).most_common(8))
        assert response.status_code==200, (name, data)
        assert data.get('code')==0, (name, data)
