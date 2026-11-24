"""ID-first pagination preserves complete responses and scoped permissions."""
import pytest
from sqlalchemy import event
from app.extensions import db
from app.models import Report
pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('administrator',[True,False])
@pytest.mark.parametrize('endpoint,view,presentation',[
    ('reports','query','report'),('reports','data_entry','report'),
    ('reports','contract_review','registration-sample'),('reports','review','report'),
    ('reports','approval','report'),('samples','register','registration-sample'),
    ('samples','outbound','outbound'),
])
def test_page_ids_route_permission_and_full_response(isolated_app,isolated_client,scenario_factory,monkeypatch,endpoint,view,presentation,administrator):
    original=isolated_client.post
    def shadow(*args,**kwargs):
        if not kwargs.get('json',{}).get('serverPage'):
            return original(*args,**kwargs)
        isolated_app.config.update(LIST_QUERY_PROTOTYPE=False, LIST_QUERY_A2=True, LIST_PAGE_IDS=False)
        old=original(*args,**kwargs)
        isolated_app.config['LIST_PAGE_IDS']=True
        new=original(*args,**kwargs)
        assert old.get_json()==new.get_json()
        return new
    d=scenario_factory.department(name='Scope');project,steps=scenario_factory.project(d)
    from app.platform.workflow.visibility import REPORT_LIST_VIEW_PERMISSIONS,SAMPLE_LIST_VIEW_PERMISSIONS
    permission=(REPORT_LIST_VIEW_PERMISSIONS if endpoint=='reports' else SAMPLE_LIST_VIEW_PERMISSIONS)[view]
    u=scenario_factory.user(d,role_key='admin' if administrator else 'member',account='admin' if administrator else 'operator',permissions=[permission],project_steps=steps)
    for action in ['report.review.undo','report.approval.undo','sample.return_stock']:scenario_factory.grant_action(u,action)
    for i,state in enumerate(['待合同评审','待样品领取','检测录入中','待审核','待批准','待打印']*2):
        db.session.add(Report(report_no='SCOPE-'+str(i),sample_no='S-'+str(i),department=d.name,project=project.name,status=state,sample_status='已入库' if state=='待样品领取' else '已领取',sample_reg_state='登记完成',detail={'rawSample':{'schemeCode':project.code,'schemeName':project.name},'dataEntryStarted':True}))
    db.session.add(Report(report_no='FOREIGN',department='foreign',project='foreign',status='待批准'))
    db.session.commit()
    from app.security import issue_token
    headers={'Authorization':'Bearer '+issue_token(u)}
    for page in (1,2,3):
        response=shadow('/api/'+endpoint+'/query',headers=headers,json={'view':view,'serverPage':True,'presentation':presentation,'page':page,'pageSize':2,'sort':'code'})
        assert response.get_json()['code']==0


def test_page_ids_default_off_and_projection_only_page(isolated_app,scenario_factory):
    from app.list_paging import load_report_page
    # The release regression intentionally enables LIST_PAGE_IDS. Verify the
    # unchanged default in an independent import without that environment key.
    import os, subprocess, sys
    env = dict(os.environ)
    env.pop('LIST_PAGE_IDS', None)
    default = subprocess.check_output(
        [sys.executable, '-c', 'from config import Config; print(Config.LIST_PAGE_IDS)'],
        env=env, text=True).strip()
    assert default == 'False'
    with isolated_app.app_context():
        dept=scenario_factory.department()
        user=scenario_factory.user(dept,role_key='admin',account='admin')
        for i in (10,2,1):
            db.session.add(Report(report_no='ID-'+str(i),sample_no='S'+str(i)))
        db.session.commit()
        sql=[]
        def capture(c,cur,statement,params,ctx,many):sql.append(statement)
        event.listen(db.engine,'before_cursor_execute',capture)
        isolated_app.config['LIST_PAGE_IDS']=True
        try:
            rows,meta=load_report_page(Report.query,user,'query',dict(sort='code',page=2,pageSize=1))
        finally:event.remove(db.engine,'before_cursor_execute',capture)
        assert meta['total']==3 and [r.sample_no for r in rows]==['S2']
        selections=[s for s in sql if s.lstrip().upper().startswith('SELECT') and 'FROM reports' in s]
        assert not any('count(' in s.lower() for s in selections)
        assert any('reports.id IN' in s and 'reports.detail' in s for s in selections)
        assert all('natural_number_key' not in s.lower() for s in selections if 'reports.detail' in s)
