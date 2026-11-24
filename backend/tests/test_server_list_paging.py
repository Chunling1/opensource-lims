"""Page selection must precede expensive row projection, with global filtering."""
import pytest
from sqlalchemy import event, select
from app.extensions import db
from app.models import Report, Entrust
from app.list_paging import report_page, report_fields, data_status
from app.list_projection import list_reports
from app.status_machine import report_data_status

pytest_plugins=('testkit.fixtures',)


@pytest.mark.parametrize('entity', ['report', 'entrust'])
def test_edit_time_order_uses_successful_entity_audits_and_stable_ties(isolated_app,scenario_factory,entity):
    from datetime import datetime
    from app.models import OperationAudit
    from app.list_paging import entrust_page
    # Legacy control: preserve the direct SQL ordering assertions below.
    isolated_app.config['LIST_PAGE_IDS']=False
    with isolated_app.app_context():
        dept=scenario_factory.department()
        user=scenario_factory.user(dept,role_key='admin',account='admin')
        model=Report if entity=='report' else Entrust
        identity='report_no' if entity=='report' else 'entrust_no'
        records=[model(**{identity:f'EDIT-{i}'},created_at=datetime(2026,1,1)) for i in range(4)]
        db.session.add_all(records)
        for index,day,success,kind in [(0,2,True,entity),(1,3,True,entity),(0,5,False,entity),
                                      (2,6,True,'entrust' if entity=='report' else 'report'),(3,3,True,entity)]:
            db.session.add(OperationAudit(action='save',object_type=kind,object_id=f'EDIT-{index}',
                success=success,created_at=datetime(2026,1,day)))
        db.session.commit()
        def page(body):
            return report_page(model.query,user,'query',body) if entity=='report' else entrust_page(model.query,body)
        ordered,meta=page({'page':1,'pageSize':2})
        assert meta['total']==4
        assert [getattr(r,identity) for r in ordered.all()]==['EDIT-3','EDIT-1']
        ordered,_=page({'page':2,'pageSize':2})
        assert [getattr(r,identity) for r in ordered.all()]==['EDIT-0','EDIT-2']
        ordered,_=page({'fields':{'editedAt':'2026-01-03'}})
        assert [getattr(r,identity) for r in ordered.all()]==['EDIT-3','EDIT-1']


def test_query_only_hydrates_requested_page_and_global_filter(isolated_app,scenario_factory):
    # LIMIT/OFFSET belongs to the legacy control, not the ID-first projection.
    isolated_app.config['LIST_PAGE_IDS']=False
    with isolated_app.app_context():
        dept=scenario_factory.department(name='分页部')
        user=scenario_factory.user(dept,permissions=['report.query.view'])
        for i in range(37):
            db.session.add(Report(report_no=f'PAGE-{i:03}',sample_no=f'S-{i:03}',department=dept.name,
                status='检测录入中' if i%2 else '待批准',sample_status='已领取',
                detail={'rawSample':{'sampleName':'匹配'+str(i),'trademarkImage':'DO-NOT-LOAD'*10000}}))
        db.session.commit()
        sql=[]
        def capture(conn,cursor,statement,parameters,context,many):sql.append(statement)
        event.listen(db.engine,'before_cursor_execute',capture)
        try:
            q,meta=report_page(Report.query,user,'query',{'page':2,'pageSize':10,'sort':'code'})
            rows=list_reports(q)
        finally:event.remove(db.engine,'before_cursor_execute',capture)
        assert meta['total']==37
        assert [r.report_no for r in rows]==[f'PAGE-{i:03}' for i in range(10,20)]
        assert all('trademarkImage' not in r.detail['rawSample'] for r in rows)
        assert 'LIMIT' in sql[-1] and 'OFFSET' in sql[-1]
        q,meta=report_page(Report.query,user,'query',{'page':1,'pageSize':10,'contains':'PAGE-036','searchField':'reportCode'})
        assert meta['total']==1 and list_reports(q)[0].report_no=='PAGE-036'
        q,meta=report_page(Report.query,user,'query',{'page':2,'pageSize':10,'status':'报告批准中','sort':'code'})
        assert meta['total']==19 and len(list_reports(q))==9


@pytest.mark.parametrize('entity', ['report', 'entrust'])
def test_id_page_edit_time_order_uses_successful_entity_audits_and_stable_ties(isolated_app,scenario_factory,entity):
    from datetime import datetime
    from app.models import OperationAudit
    from app.list_paging import load_report_page,load_entrust_page
    isolated_app.config['LIST_PAGE_IDS']=True
    with isolated_app.app_context():
        dept=scenario_factory.department()
        user=scenario_factory.user(dept,role_key='admin',account='admin')
        model=Report if entity=='report' else Entrust
        identity='report_no' if entity=='report' else 'entrust_no'
        db.session.add_all([model(**{identity:f'EDIT-{i}'},created_at=datetime(2026,1,1)) for i in range(4)])
        for index,day,success,kind in [(0,2,True,entity),(1,3,True,entity),(0,5,False,entity),
                                      (2,6,True,'entrust' if entity=='report' else 'report'),(3,3,True,entity)]:
            db.session.add(OperationAudit(action='save',object_type=kind,object_id=f'EDIT-{index}',
                success=success,created_at=datetime(2026,1,day)))
        db.session.commit()
        def page(body):
            return load_report_page(model.query,user,'query',body) if entity=='report' else load_entrust_page(model.query,body)
        for body,expected,total in [
            ({'page':1,'pageSize':2},['EDIT-3','EDIT-1'],4),
            ({'page':2,'pageSize':2},['EDIT-0','EDIT-2'],4),
            ({'fields':{'editedAt':'2026-01-03'}},['EDIT-3','EDIT-1'],2),
        ]:
            rows,meta=page(body)
            assert meta['total']==total
            assert [getattr(r,identity) for r in rows]==expected
            assert list(meta.page_ids)==[r.id for r in rows]


def test_id_page_only_hydrates_requested_page_and_global_filter(isolated_app,scenario_factory):
    from app.list_paging import load_report_page
    isolated_app.config['LIST_PAGE_IDS']=True
    with isolated_app.app_context():
        dept=scenario_factory.department(name='分页部')
        user=scenario_factory.user(dept,permissions=['report.query.view'])
        for i in range(37):
            db.session.add(Report(report_no=f'PAGE-{i:03}',sample_no=f'S-{i:03}',department=dept.name,
                status='检测录入中' if i%2 else '待批准',sample_status='已领取',
                detail={'rawSample':{'sampleName':'匹配'+str(i),'trademarkImage':'DO-NOT-LOAD'*10000}}))
        db.session.commit()
        sql=[]
        def capture(conn,cursor,statement,parameters,context,many):sql.append(statement)
        event.listen(db.engine,'before_cursor_execute',capture)
        try:
            rows,meta=load_report_page(Report.query,user,'query',{'page':2,'pageSize':10,'sort':'code'})
        finally:event.remove(db.engine,'before_cursor_execute',capture)
        assert meta['total']==37
        assert [r.report_no for r in rows]==[f'PAGE-{i:03}' for i in range(10,20)]
        assert list(meta.page_ids)==[r.id for r in rows]
        assert all('trademarkImage' not in r.detail['rawSample'] for r in rows)
        selections=[s for s in sql if s.lstrip().upper().startswith('SELECT') and 'FROM reports' in s]
        assert not any('count(' in s.lower() for s in selections)
        # Filtering may inspect JSON too; only the SELECT clause hydrates rows.
        projections=[s for s in selections if 'reports.detail' in s.split('FROM reports',1)[0]]
        assert len(projections)==1 and 'reports.id IN' in projections[0]
        assert 'natural_number_key' not in projections[0].lower()
        rows,meta=load_report_page(Report.query,user,'query',{'page':1,'pageSize':10,'contains':'PAGE-036','searchField':'reportCode'})
        assert meta['total']==1 and rows[0].report_no=='PAGE-036'
        assert list(meta.page_ids)==[r.id for r in rows]
        rows,meta=load_report_page(Report.query,user,'query',{'page':2,'pageSize':10,'status':'报告批准中','sort':'code'})
        assert meta['total']==19 and len(rows)==9
        assert list(meta.page_ids)==[r.id for r in rows]


@pytest.mark.parametrize('status,sample,reg,archive,voided,started',[
    ('待合同评审','待入库','登记中','',False,False),
    ('检测录入中','已领取','登记完成','',False,False),
    ('检测录入中','已领取','登记完成','',False,True),
    ('待审核','已领取','登记完成','',False,True),
    ('待发放','已领取','登记完成','归档完成',False,True),
    ('待打印','已领取','登记完成','',False,True),
    ('待校核','已入库','登记完成','',False,True),
    ('待批准','已领取','登记完成','',True,True),
])
def test_sql_status_matches_canonical(isolated_app,status,sample,reg,archive,voided,started):
    with isolated_app.app_context():
        db.session.add(Report(report_no='STATUS',status=status,sample_status=sample,sample_reg_state=reg,
            archive_state=archive,voided=voided,detail={'dataEntryStarted':started}))
        db.session.commit()
        actual=db.session.execute(select(data_status()).select_from(Report)).scalar()
        assert actual==report_data_status(status,sample,reg,archive,voided,started)


def test_mysql_page_expression_compiles_without_client_sql(isolated_app):
    from sqlalchemy.dialects import mysql
    with isolated_app.app_context():
        fields=report_fields('entry')
        sql=str(select(fields['name'],fields['dataStatus']).compile(dialect=mysql.dialect()))
        assert 'json_unquote' in sql.lower()


@pytest.mark.parametrize('administrator',[True,False])
@pytest.mark.parametrize('endpoint,view,presentation',[
    ('reports','query','entry'),('reports','data_entry','entry'),('reports','data_change','entry'),('reports','print','report'),('reports','release','report'),('reports','change_request','report'),('reports','review','report'),('reports','approval','report'),
    ('reports','contract_review','registration-sample'),('reports','archive','report'),
    ('samples','register','registration-sample'),('samples','flow_query','flow'),('samples','inbound','inbound'),('samples','outbound','outbound'),
])
def test_route_page_matches_legacy_scope_without_off_page_rows(isolated_client,scenario_factory,monkeypatch,endpoint,view,presentation,administrator):
    from app.security import issue_token
    from app import business_rows
    d=scenario_factory.department(name='分页授权部')
    project,steps=scenario_factory.project(d)
    from app.platform.workflow.visibility import REPORT_LIST_VIEW_PERMISSIONS,SAMPLE_LIST_VIEW_PERMISSIONS
    permission=(REPORT_LIST_VIEW_PERMISSIONS if endpoint=='reports' else SAMPLE_LIST_VIEW_PERMISSIONS)[view]
    u=scenario_factory.user(d,role_key='admin' if administrator else 'member',account='admin' if administrator else 'operator',permissions=[permission],project_steps=steps)
    for action in ['report.report_check.undo','report.review.undo','report.approval.undo','sample.return_stock','report.archive.pass']:scenario_factory.grant_action(u,action)
    for i in range(49):
        state,sample=[('待合同评审','待入库'),('待样品入库','待入库'),('待样品领取','已入库'),
                      ('检测录入中','已领取'),('待审核','已领取'),('待批准','已领取'),
                      ('待打印','已领取'),('待发放','已领取'),('已发放','已领取'),
                      ('已归档','已处置'),('退回待重传','已领取'),('检测更改中','已领取')][i%12]
        db.session.add(Report(report_no=f'ROUTE-{i:03}',sample_no=f'S-{i:03}',department=d.name,
            project=project.name,status=state,sample_status=sample,sample_reg_state='登记完成',
            archive_state='归档完成' if state in {'待发放','已发放','已归档'} else '未归档',
            detail={'rawSample':{'schemeCode':project.code,'schemeName':project.name},'dataEntryStarted':False}))
    db.session.commit()
    headers={'Authorization':'Bearer '+issue_token(u)}
    legacy=isolated_client.post(f'/api/{endpoint}/query',headers=headers,json={'view':view}).get_json()
    assert legacy['code']==0,legacy
    calls=[];original=business_rows.report_business_row
    def track(*args,**kwargs):calls.append(args[0].report_no);return original(*args,**kwargs)
    monkeypatch.setattr(business_rows,'report_business_row',track)
    if endpoint=='samples':monkeypatch.setattr('app.blueprints.samples.report_business_row',track)
    all_rows=[]
    total=legacy['data']['total']
    for page in range(1,(total+4)//5+1):
        calls.clear()
        result=isolated_client.post(f'/api/{endpoint}/query',headers=headers,json={
            'view':view,'serverPage':True,'page':page,'pageSize':5,'presentation':presentation}).get_json()
        assert result['code']==0,result
        assert result['data']['total']==total
        assert len(calls)<=5
        all_rows.extend(result['data']['rows'])
    assert [r['reportNo'] for r in all_rows]==[r['reportNo'] for r in legacy['data']['rows']]


def test_plan_counts_do_not_build_rows(isolated_client, scenario_factory, monkeypatch):
    from app.security import issue_token
    from app import business_rows
    d=scenario_factory.department()
    u=scenario_factory.user(d,permissions=['sample.flow_query.view'])
    other=scenario_factory.department()
    for i in range(41):
        db.session.add(Report(report_no=f'COUNT-{i}',department=d.name if i<40 else other.name,
            status='检测录入中',sample_status='已领取',detail={'rawSample':{'schemeCode':'YP','testDept':d.name}}))
    db.session.commit()
    def fail(*args,**kwargs):raise AssertionError('counts must not hydrate business rows')
    monkeypatch.setattr(business_rows,'report_business_row',fail)
    result=isolated_client.post('/api/samples/plan-counts',headers={'Authorization':'Bearer '+issue_token(u)}).get_json()
    assert result['code']==0,result
    assert sum(r['flowSampleCount'] for r in result['data']['rows'])==40
    assert sum(r['dataEntrySampleCount'] for r in result['data']['rows'])==40


def test_invalid_fields_and_empty_commission_scope(isolated_client,scenario_factory):
    from app.security import issue_token
    d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
    db.session.add(Report(report_no='NONE',department=d.name));db.session.commit()
    headers={'Authorization':'Bearer '+issue_token(u)}
    for query in [{'sort':'injected SQL'}, {'workflowDates':{'arbitrary':{'enabled':True,'from':'2026-01-01'}}}]:
        result=isolated_client.post('/api/reports/query',headers=headers,json={'serverPage':True,**query}).get_json()
        assert result['code']==1
    result=isolated_client.post('/api/reports/query',headers=headers,json={'serverPage':True,'commissionIds':[]}).get_json()
    assert result['data']['total']==0 and result['data']['rows']==[]


@pytest.mark.parametrize('id_paging',[False,True])
@pytest.mark.parametrize('historical',[False,True])
def test_entry_name_and_scheme_filters_follow_displayed_fields(isolated_app,scenario_factory,id_paging,historical):
    from app.list_paging import load_report_page
    with isolated_app.app_context():
        isolated_app.config.update(LIST_PAGE_IDS=id_paging,LIST_QUERY_A2=True,LIST_QUERY_PROTOTYPE=False)
        d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
        detail={'summary':[{'fields':[['样品名称','空气处理机组'],['检测方案','设备检测方案（QA）']]}]} if historical else {'rawSample':{'sampleName':'空气处理机组','schemeName':'设备检测方案','projectList':['风量','噪声']}}
        db.session.add(Report(report_no='QA-ENTRY',sample_no='S1',department=d.name,project='旧检测参数',project_name='工程甲',detail=detail))
        db.session.commit()
        fields=report_fields('entry')
        actual=db.session.execute(select(*(fields[k] for k in ['name','engineeringName','projectName'])).select_from(Report).outerjoin(Entrust,Report.entrust_no==Entrust.entrust_no)).one()
        assert actual==('空气处理机组','工程甲','设备检测方案')
        for key,word,total in [('name','空气处理机组',1),('name','旧检测参数',0),('engineeringName','工程甲',1),('projectName','设备检测方案',1),('projectName','工程甲',0)]:
            rows,meta=load_report_page(Report.query,u,'query',{'presentation':'entry','searchField':key,'contains':word,'sort':key})
            assert meta['total']==total,(key,word)
            assert len(rows)==total
        report_values=report_fields('report')
        expected_items='旧检测参数' if historical else '风量、噪声'
        assert db.session.execute(select(report_values['name'],report_values['projectName']).select_from(Report).outerjoin(Entrust,Report.entrust_no==Entrust.entrust_no)).one()==(expected_items,'工程甲')


@pytest.mark.parametrize('id_paging',[False,True])
def test_sample_logistics_columns_match_sources_and_sql_filters(isolated_app,isolated_client,scenario_factory,id_paging):
    from app.security import issue_token
    isolated_app.config.update(LIST_PAGE_IDS=id_paging,LIST_QUERY_A2=True,LIST_QUERY_PROTOTYPE=False)
    d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
    report=Report(report_no='LAB-LOGISTICS',sample_no='LOGISTICS',department=d.name,status='待审核',sample_status='已领取',owner='录入人',sample_pickup={'managerName':'出库人','outTime':'2026-11-02','receiverName':'领样人','pickupTime':'2026-11-03','signed':True},detail={'workflowDates':{'sampleInboundAt':'2026-11-01'},'rawSample':{'sampleName':'样品','registrar':'登记人','sampleHandle':'客户取回'}})
    db.session.add(report);db.session.commit()
    headers={'Authorization':'Bearer '+issue_token(u)}
    def query(presentation,**filters):
        response=isolated_client.post('/api/samples/query',headers=headers,json={'view':'flow_query','presentation':presentation,'serverPage':True,**filters}).get_json()
        assert response['code']==0,response
        return response['data']
    row=query('flow')['rows'][0]
    assert row['reportNo']=='LAB-LOGISTICS'
    assert (row['inboundTime'],row['outboundTime'],row['pickupTime'])==('2026-11-01','2026-11-02','2026-11-03')
    assert (row['outboundPerson'],row['pickupPerson'],row['registrar'],row['owner'])==('出库人','领样人','登记人','录入人')
    assert row['sampleDisposition']=='客户取回'
    for key,value in [('outboundPerson','出库人'),('collectionPerson','领样人'),('owner','登记人'),('dataEntryPerson','录入人')]:
        assert query('flow',searchField=key,contains=value)['total']==1
    assert query('flow',**{'dateField':'outboundDate','from':'2026-11-02','to':'2026-11-02'})['total']==1
    assert query('flow',**{'dateField':'collectionDate','from':'2026-11-03','to':'2026-11-03'})['total']==1
    assert query('flow',**{'dateField':'outboundDate','from':'2026-11-03','to':'2026-11-03'})['total']==0
    assert query('disposal',requirement='客户取回')['total']==1


@pytest.mark.parametrize('id_paging',[False,True])
def test_expanded_report_and_sample_filters_match_actual_facts(isolated_app,isolated_client,scenario_factory,id_paging):
    from datetime import datetime
    from app.models import OperationAudit
    from app.security import issue_token
    isolated_app.config.update(LIST_PAGE_IDS=id_paging,LIST_QUERY_A2=True,LIST_QUERY_PROTOTYPE=False)
    d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
    project,steps=scenario_factory.project(d)
    for number,status,result,date in [('ONE','待批准','判定合格','2026-11-01'),('TWO','待审核','判定不合格','2026-11-02')]:
        db.session.add(Report(report_no=number,sample_no=number,department=d.name,project=project.name,status=status,sample_status='已领取',detail={'workflowDates':{'sampleInboundAt':date},'checkInput':{'resultStatus':result,'testDate':date},'rawSample':{'deliverWay':'邮寄','schemeCode':project.code,'schemeName':project.name}}))
    for action in ['report.review.pass','sample.dispose','sample.register.void']:
        db.session.add(OperationAudit(object_type='report',object_id='ONE',action=action,success=True,created_at=datetime(2026,11,1,17)))
    scenario_factory.grant_action(u,'report.review.undo')
    db.session.commit();headers={'Authorization':'Bearer '+issue_token(u)}
    def post(endpoint,body):
        result=isolated_client.post('/api/'+endpoint+'/query',headers=headers,json={'serverPage':True,'page':1,'pageSize':1,**body}).get_json()
        assert result['code']==0,result
        return result['data']
    report_body={'view':'query','presentation':'report','conclusion':'合格','dateField':'testEndDate','from':'2026-11-01','to':'2026-11-01'}
    rows=post('reports',report_body);assert rows['total']==1 and rows['rows'][0]['reportNo']=='ONE'
    assert rows['rows'][0]['resultStatus']=='合格'
    assert post('reports',{**report_body,'dateField':'auditDate','from':'2026-11-02','to':'2026-11-02'})['total']==1
    assert post('reports',{'view':'review','presentation':'report','checkStatus':'已审核'})['total']==1
    assert post('reports',{'view':'query','presentation':'report','collectionMethod':'邮寄'})['total']==2
    for presentation,field in [('cancel','voidedAt'),('disposal','disposalDate')]:
        sample=post('samples',{'view':'flow_query','includeVoided':True,'presentation':presentation,'dateField':field,'from':'2026-11-02','to':'2026-11-02'})
        assert sample['total']==1
        assert sample['rows'][0][field].startswith('2026-11-02')
    assert post('samples',{'view':'flow_query','presentation':'flow','status':'','dates':{'inbound':{'from':'2026-11-02','to':'2026-11-02'}}})['total']==1


@pytest.mark.parametrize('view,status',[('query','待审核'),('review','待审核'),('approval','待批准'),('print','待打印'),('archive','待发放'),('release','待发放')])
def test_report_advanced_filters_work_in_each_module(isolated_app,isolated_client,scenario_factory,view,status):
    from app.security import issue_token
    isolated_app.config.update(LIST_PAGE_IDS=True,LIST_QUERY_A2=True,LIST_QUERY_PROTOTYPE=False)
    d=scenario_factory.department();project,_=scenario_factory.project(d)
    u=scenario_factory.user(d,role_key='admin',account='admin')
    for number,result in [('MATCH','判定合格'),('OTHER','判定不合格')]:
        db.session.add(Report(report_no=number,sample_no=number,department=d.name,project=project.name,status=status,sample_status='已领取',archive_state='归档完成' if view=='release' else '',detail={'workflowDates':{'approvalDate':'2026-11-01'},'checkInput':{'resultStatus':result},'rawSample':{'schemeCode':project.code,'schemeName':project.name}}))
    db.session.commit()
    response=isolated_client.post('/api/reports/query',headers={'Authorization':'Bearer '+issue_token(u)},json={'view':view,'presentation':'report','serverPage':True,'conclusion':'合格','dateField':'approvalDate','from':'2026-11-01','to':'2026-11-01'}).get_json()
    assert response['code']==0,response
    assert response['data']['total']==1
    assert response['data']['rows'][0]['reportNo']=='MATCH'


def test_sql_search_values_match_sample_snapshot(isolated_app,scenario_factory):
    from app.business_rows import report_business_row
    from app.admin_corrections.source import SourceCorrection
    with isolated_app.app_context():
        d=scenario_factory.department();user=scenario_factory.user(d,role_key='admin',account='admin')
        e=Entrust(entrust_no='WT',client='原客户',project_name='原工程',project_type='委托',contract_no='OLD',
                  owner='原经办',department=d.name,amount='100',info={'entrustDate':'2026-10-01','handler':'原经办','handleDept':d.name,'erpType':'虚拟框架'})
        db.session.add(e);db.session.flush()
        r=Report(report_no='LAB-2026YP-0026',sample_no='2026YP-0026',entrust_no='WT',department=d.name,status='待审核',client='',project_name='',owner='原人员',detail={
            'rawSample':{'sampleName':'样品甲','projectList':['计数效率','计径效率'],'schemeCode':'YP','schemeName':'演示方案'},
            'entrustSnapshot':{'client':'新客户','projectName':'新工程','owner':'新经办','department':'新部门','amount':'200',
                               'info':{'handler':'旧缓存','handleDept':'旧部门','consignor':'委托人','clientAddr':'新地址'}}})
        db.session.add(r);db.session.flush()
        db.session.add(SourceCorrection(kind='sample-snapshot',source_key=str(r.id),fields={'contractNo':'NEW','projectType':'型式检验','erpType':'标准合同','entrustDate':'2026-10-02'}))
        db.session.commit()
        expected=report_business_row(r,e)
        fields=report_fields('report')
        keys=['sampleOrProjectName','projectName','client','handler','handlerDepartment','amount','testCategory','erpProjectNo','erpProjectType','entrustDate','testItems','reportTitle']
        actual=db.session.execute(select(*(fields[k] for k in keys)).select_from(Report).outerjoin(Entrust,Report.entrust_no==Entrust.entrust_no)).one()
        for key,value in zip(keys,actual):assert value==expected[key],(key,value,expected[key])


@pytest.mark.parametrize('value',[True,False,'true','false',0,1,None,'',{},[]])
def test_sql_json_truth_preserves_python_marker_semantics(isolated_app,value):
    from app.list_paging import started
    with isolated_app.app_context():
        db.session.add(Report(report_no='BOOL',detail={'dataEntryStarted':value,'checkInput':{}}));db.session.commit()
        assert bool(db.session.execute(select(started()).select_from(Report)).scalar())==bool(value)


def test_legacy_dates_plans_and_identifier_order(isolated_app,scenario_factory):
    from app.list_paging import scheme_fields,date_text
    with isolated_app.app_context():
        d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
        for number in ('S10','S2','S01'):
            db.session.add(Report(report_no=number,sample_no=number,detail={'sampleRegisteredAt':'2026年1月2日',
                'summary':[{'fields':[['检测方案','检测项目（YP）']]}]}))
        db.session.commit()
        code,name=scheme_fields()
        assert db.session.execute(select(code,name).select_from(Report).limit(1)).one()==('YP','检测项目')
        actual=db.session.execute(select(date_text('2026年1月2日'))).scalar()
        assert actual=='2026-01-02',actual
        q,meta=report_page(Report.query,u,'query',{'presentation':'entry','sort':'code','pageSize':2,'from':'2026-01-01','to':'2026-01-03','dateField':'sampleRegisteredAt'})
        assert meta['total']==3, db.session.execute(select(report_fields()['sampleRegisteredAt']).select_from(Report)).all()
        assert [r.report_no for r in list_reports(q)]==['S01','S2']


def test_page_cost_is_bounded_with_large_report_bodies(isolated_client,scenario_factory,monkeypatch):
    import time,json
    from app.security import issue_token
    from app import business_rows
    d=scenario_factory.department();project,steps=scenario_factory.project(d);u=scenario_factory.user(d,role_key='admin',account='admin',project_steps=steps)
    for i in range(347):
        db.session.add(Report(report_no=f'PERF-{i:04}',sample_no=f'S-{i:04}',department=d.name,project=project.name,
            status='检测录入中',sample_status='已领取',detail={'rawSample':{'sampleName':'性能测试','schemeCode':project.code,'schemeName':project.name,'trademarkImage':'x'*50000},'dataEntryStarted':True}))
    db.session.commit()
    headers={'Authorization':'Bearer '+issue_token(u)}
    original=business_rows.report_business_row
    metrics={}
    for mode,body in [('legacy',{'view':'data_entry'}),('page',{'view':'data_entry','presentation':'entry','serverPage':True,'page':1,'pageSize':10,'sort':'code'})]:
        calls=[];sql=[]
        def row(*a,**k):calls.append(a[0].report_no);return original(*a,**k)
        def capture(_c,_cu,statement,*args):sql.append(statement)
        monkeypatch.setattr(business_rows,'report_business_row',row)
        event.listen(db.engine,'before_cursor_execute',capture)
        started_at=time.perf_counter()
        try:response=isolated_client.post('/api/reports/query',headers=headers,json=body)
        finally:event.remove(db.engine,'before_cursor_execute',capture)
        data=response.get_json()
        assert data['code']==0,data
        metrics[mode]={'seconds':round(time.perf_counter()-started_at,3),'sql':len(sql),'hydrated':len(calls),'bytes':len(response.data)}
        assert data['data']['total']==347
    print('PAGINATION_BENCHMARK='+json.dumps(metrics))
    assert metrics['page']['hydrated']==10
    assert metrics['legacy']['hydrated']==347
    assert metrics['page']['bytes']<metrics['legacy']['bytes']/10


@pytest.mark.parametrize('version',[1,'1',True,False,None])
def test_delivery_filter_uses_the_same_version_type_as_canonical(isolated_app,version):
    from app.list_paging import released
    from app.report_delivery import delivery_released
    with isolated_app.app_context():
        r=Report(report_no='DELIVERY',status='已发放',archive_state='归档完成',detail={
            'reportDelivery':{'released':True,'sealedFlowId':1,'versionId':version}})
        db.session.add(r);db.session.commit()
        # Only SQL expression parity is under test; no document/signature is created.
        expected=delivery_released(r)
        assert bool(db.session.execute(select(released()).select_from(Report)).scalar())==expected


def test_summary_aliases_follow_document_order(isolated_app):
    from app.list_paging import summary
    with isolated_app.app_context():
        db.session.add(Report(report_no='ALIASES',detail={'summary':[{'fields':[['执行标准','FIRST'],['检测依据','SECOND']]}]}));db.session.commit()
        assert db.session.execute(select(summary('检测依据','执行标准')).select_from(Report)).scalar()=='FIRST'


def test_report_query_operator_timestamp_matches_display(isolated_app):
    from datetime import datetime
    from app.models import OperationAudit
    with isolated_app.app_context():
        db.session.add(Report(report_no='ACTUAL',detail={'sampleRegisteredAt':'2026-01-02'}))
        db.session.add(OperationAudit(object_type='report',object_id='ACTUAL',action='sample.register.complete',success=True,created_at=datetime(2026,1,3,1,20)))
        db.session.commit()
        assert db.session.execute(select(report_fields('report')['sampleRegisteredAt']).select_from(Report)).scalar()=='2026-01-03 09:20:00'
        assert db.session.execute(select(report_fields('entry')['sampleRegisteredAt']).select_from(Report)).scalar()=='2026-01-02'


@pytest.mark.parametrize('snapshot',[
    {'info':{'consignor':None,'handler':'','client':''}},
    {'owner':None,'department':None,'client':None,'projectName':None},
    {'owner':'','department':'','client':'','projectName':''},
])
def test_snapshot_clear_and_missing_values_match_display(isolated_app,snapshot):
    from app.business_rows import report_business_row
    with isolated_app.app_context():
        e=Entrust(entrust_no='SNAP',owner='原人',department='原部',client='原客户',project_name='原工程',info={'consignor':'原委托','handler':'原人','handleDept':'原部'})
        db.session.add(e);db.session.flush()
        r=Report(report_no='SNAP-R',entrust_no=e.entrust_no,client='',project_name='',owner='报告人',department='报告部',detail={'entrustSnapshot':snapshot})
        db.session.add(r);db.session.commit()
        expected=report_business_row(r,e);fields=report_fields('registration-sample')
        keys=['client','handler','handlerDepartment','consignor','projectName']
        actual=db.session.execute(select(*(fields[k] for k in keys)).select_from(Report).outerjoin(Entrust,Report.entrust_no==Entrust.entrust_no)).one()
        for key,value in zip(keys,actual):assert (value or '')==expected[key],(key,value,expected[key])


def test_alternate_adapter_filters_use_its_display_vocabulary(isolated_app,scenario_factory):
    from app.list_paging import report_page,entrust_page
    with isolated_app.app_context():
        d=scenario_factory.department();u=scenario_factory.user(d,role_key='admin',account='admin')
        db.session.add(Entrust(entrust_no='AD-WT',contract_no='HT-1',owner='委托人',info={'entrustDate':'2026-01-02'}))
        db.session.add(Report(report_no='AD-R',sample_no='AD-S',entrust_no='AD-WT',owner='主检',status='待合同评审',sample_reg_state='登记完成',detail={'rawSample':{'registrar':'登记人','schemeCode':'YP','schemeName':'测试方案','testCategory':'委托','reportCategory':'英文'}}))
        db.session.commit()
        q,meta=report_page(Report.query,u,'query',{'adapter':'platform','presentation':'entry','dataStatus':'完成登记','sampleType':'英文报告样品','fields':{'owner':'登记人','testPlan':'YP','category':'委托'},'from':'2026-01-02','to':'2026-01-02'})
        assert meta['total']==1 and q.one().report_no=='AD-R'
        q,meta=report_page(Report.query,u,'query',{'adapter':'platform','presentation':'entry','status':'completed'})
        assert meta['total']==1
        q,meta=entrust_page(Entrust.query,{'adapter':'platform','fields':{'contract':'HT-1','owner':'委托人'}})
        assert meta['total']==1
