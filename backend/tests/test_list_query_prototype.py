from datetime import datetime
import pytest
from sqlalchemy import select, event
from app.extensions import db
from app.models import Report, Entrust, OperationAudit
from app.list_paging import report_fields, report_page
from app.list_projection import list_reports
from app.list_query_prototype import joined_sources
from app.admin_corrections.source import SourceCorrection

pytest_plugins = ('testkit.fixtures',)


def test_joined_fields_preserve_latest_success_id_nulls_and_corrections(isolated_app):
    with isolated_app.app_context():
        report = Report(report_no='AUDIT', entrust_no='WT', status='待批准', detail={
            'entrustSnapshot': {'info': {'clientAddress':'snapshot'}}})
        db.session.add_all([report, Entrust(entrust_no='WT', info={'clientAddress':'original'})]);db.session.flush()
        db.session.add(SourceCorrection(kind='sample-snapshot', source_key=str(report.id), fields={'clientAddress':'', 'projectType':None}))
        # Timestamps deliberately disagree with IDs. Failure and wrong object
        # must never win, and empty/whitespace names use the same row account.
        cases=[('report','AUDIT','sample.inbound.confirm',True,'earlier','a',datetime(2026,5,1)),
               ('report','AUDIT','sample.mobile.inbound.confirm',True,'','fallback',datetime(2026,1,1)),
               ('report','AUDIT','sample.inbound.confirm',False,'failed','bad',datetime(2026,6,1)),
               ('entrust','AUDIT','sample.inbound.confirm',True,'wrong-kind','bad',datetime(2026,7,1)),
               ('report','AUDIT','report.data_entry.complete',True,'one','a',datetime(2026,1,1)),
               ('report','AUDIT','report.data_change.complete',True,'  ','second',datetime(2026,1,1)),
               ('entrust','WT','entrust.register.create',True,None,'creator',datetime(2026,1,1))]
        for kind,identity,action,success,name,account,at in cases:
            db.session.add(OperationAudit(object_type=kind,object_id=identity,action=action,success=success,user_name=name,account=account,created_at=at));db.session.flush()
        db.session.commit()
        base=Report.query.outerjoin(Entrust,Report.entrust_no==Entrust.entrust_no)
        old=report_fields('report',logistics=True)
        q,audit,correction,edited=joined_sources(base)
        new=report_fields('report',logistics=True,audit=audit,correction=correction)
        keys=[k for k in old if k.endswith(('By','At'))]+['inboundPerson','clientAddress','erpProjectType','dataStatus']
        assert base.with_entities(*(old[k] for k in keys)).one()==q.with_entities(*(new[k] for k in keys)).one()
        assert q.with_entities(new['sampleInboundBy'],new['dataCompletedBy'],new['commissionCreatedBy']).one()==('fallback','second','creator')
        assert q.with_entities(new['sampleInboundAt']).scalar()=='2026-01-01 08:00:00'


@pytest.mark.parametrize('body',[
    {'page':2,'pageSize':2,'sort':'code'},
    {'page':9,'pageSize':2},
    {'contains':'term','searchField':'clientAddress','presentation':'report'},
    {'dataStatus':'报告批准中','sort':'reportNo','direction':'desc'},
])
def test_id_selection_matches_old_total_order_projection(isolated_app,scenario_factory,body):
    with isolated_app.app_context():
        d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
        db.session.add(Entrust(entrust_no='WT',info={'clientAddress':'term'}))
        for i in (2,10,1,30,5):
            db.session.add(Report(report_no='R'+str(i),sample_no='S'+str(i),entrust_no='WT',status='待批准',detail={'rawSample':{'sampleName':'x'}}))
        db.session.commit()
        def run(enabled):
            isolated_app.config['LIST_QUERY_PROTOTYPE']=enabled
            q,m=report_page(Report.query,u,'query',body)
            return m,[(r.id,r.report_no,r.detail) for r in list_reports(q,page_ids=getattr(m,"page_ids",None))]
        assert run(False)==run(True)


def test_feature_default_off_and_single_filter_select(isolated_app,scenario_factory):
    assert isolated_app.config['LIST_QUERY_PROTOTYPE'] is False
    with isolated_app.app_context():
        d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
        db.session.add(Report(report_no='SINGLE',sample_no='SINGLE'));db.session.commit()
        isolated_app.config['LIST_QUERY_PROTOTYPE']=True;sql=[]
        def capture(c,cur,statement,params,ctx,many):sql.append(statement)
        event.listen(db.engine,'before_cursor_execute',capture)
        try:
            q,meta=report_page(Report.query,u,'query',{'contains':'SINGLE','searchField':'sampleNo'})
            rows=list_reports(q,page_ids=getattr(meta,"page_ids",None))
        finally:event.remove(db.engine,'before_cursor_execute',capture)
        filters=[s for s in sql if 'LIKE' in s and 'reports' in s]
        assert len(filters)==1 and 'count(' not in filters[0].lower()
        assert filters[0].count('GROUP BY operation_audits.object_type, operation_audits.object_id')==1
        assert 'business_source_corrections' not in sql[-1]
        assert len(rows)==meta['total']==1


from test_mysql_local_concurrency import mysql_server


@pytest.fixture
def prototype_mysql_app(mysql_server,tmp_path):
    import pymysql
    from app import create_app
    from testkit.app import isolated_config
    conn=pymysql.connect(unix_socket=str(mysql_server),user='root',autocommit=True)
    name='prototype_'+str(tmp_path.name).replace('-','_')
    with conn.cursor() as cursor:cursor.execute('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4')
    conn.close()
    config=isolated_config(tmp_path)
    config.SQLALCHEMY_DATABASE_URI='mysql+pymysql://root@localhost/'+name+'?unix_socket='+str(mysql_server)
    app= create_app(config)
    with app.app_context():
        db.create_all()
        metadata.create_all(db.engine)
    yield app
    with app.app_context():db.session.remove();db.engine.dispose()


def test_mysql_audit_equivalence(prototype_mysql_app):
    test_joined_fields_preserve_latest_success_id_nulls_and_corrections(prototype_mysql_app)


def test_mysql_all_fields_no_match(prototype_mysql_app):
    # The original all-fields SQL exceeds SQLite's parser stack. Exercise the
    # unchanged assertion against the actual deployment dialect instead.
    from testkit.factories import ScenarioFactory
    test_id_selection_matches_old_total_order_projection(prototype_mysql_app,ScenarioFactory(),
        {'contains':'missing','searchField':'all','presentation':'report'})


@pytest.mark.parametrize('administrator',[True,False])
@pytest.mark.parametrize('endpoint,view,presentation',[
    ('reports','query','report'),('reports','data_entry','report'),
    ('reports','contract_review','registration-sample'),('reports','review','report'),
    ('reports','approval','report'),('samples','register','registration-sample'),
    ('samples','outbound','outbound'),
])
def test_prototype_route_permission_and_full_response(isolated_app,isolated_client,scenario_factory,monkeypatch,endpoint,view,presentation,administrator):
    original=isolated_client.post
    def shadow(*args,**kwargs):
        if not kwargs.get('json',{}).get('serverPage'):
            return original(*args,**kwargs)
        isolated_app.config['LIST_QUERY_PROTOTYPE']=False
        old=original(*args,**kwargs)
        isolated_app.config['LIST_QUERY_PROTOTYPE']=True
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
        response=shadow('/api/'+endpoint+'/query',headers=headers,json={'view':view,'serverPage':True,'presentation':presentation,'page':page,'pageSize':2})
        assert response.get_json()['code']==0
