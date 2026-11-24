import pytest
from sqlalchemy import text, event
from app.extensions import db
from app.models import Report, Entrust
from app.list_paging import report_fields
from app.list_query_values import materialize_fields
from test_list_query_prototype import prototype_mysql_app, mysql_server


def test_a2_mysql_raw_values_and_full_field_semantics(prototype_mysql_app):
    with prototype_mysql_app.app_context():
        db.session.add(Entrust(entrust_no='WT',client='base',project_name='project',owner='owner',info={'client':'base','clientAddress':'address','handler':'handler'}))
        variants=[None,[],False,'plain',{}, {'entrustSnapshot':{'client':None,'info':{'client':None,'clientAddress':None}}},
            {'entrustSnapshot':{'client':'','info':{'client':'','clientAddress':''}}},
            {'rawSample':{'sendDate':'2026年1月2日','sampleTime':'2026/3/4','projectList':['one','two'], 'schemeCode':'CODE'}},
            {'summary':[{'fields':[['检测方案',' Name (CODE) '],['送样日期',' '],['送样日期','2026.1.2'],['抽样时间','2026/12/3']]}, {'fields':[['检测方案','ignored'],['送样日期','2025-01-01']]}]},
            {'rawSample':{'projectList':[],'projects':['one',None,2,False],'sendDate':'invalid'}},
            *[{'checkInput':v,'dataEntryStarted':v} for v in [None,False,True,0,1,'','text',{},[],{'arbitrary':'saved'}]],
            {'rawSample':{'projectList':'plain','schemeName':'name'},'summary':[]},
        ]
        for i,detail in enumerate(variants):
            db.session.add(Report(report_no='SEM-'+str(i),entrust_no='WT',status='检测录入中',sample_status='已领取',detail=detail))
        db.session.commit()
        db.session.execute(text('SET SESSION max_execution_time=120000'))
        db.session.execute(text('SET SESSION group_concat_max_len=@@max_allowed_packet'))
        for presentation in ('report','registration-sample','entry'):
            fields=report_fields(presentation)
            q=Report.query.outerjoin(Entrust,Entrust.entrust_no==Report.entrust_no)
            aq,af=materialize_fields(q,fields)
            # Compare every output expression, including JSON null vs absent,
            # dates, duplicate summary labels, array rendering and truthiness.
            old=q.with_entities(Report.id,*[v.label(k) for k,v in fields.items()]).order_by(Report.id).all()
            new=aq.with_entities(Report.id,*[v.label(k) for k,v in af.items()]).order_by(Report.id).all()
            assert len(old)==len(new)==len(variants)
            for before,after in zip(old,new):
                assert before[0]==after[0]
                for key,a,b in zip(fields,before[1:],after[1:]):
                    assert a==b,(presentation,before[0],key,a,b)
        db.session.rollback()


def test_read_committed_falls_back(prototype_mysql_app, monkeypatch, caplog):
    from testkit.factories import ScenarioFactory
    from app.list_paging import load_report_page
    with prototype_mysql_app.app_context():
        factory=ScenarioFactory();d=factory.department();u=factory.user(d,role_key='admin',account='admin')
        db.session.add(Report(report_no='RC'));db.session.commit()
        prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=False)
        old,om=load_report_page(Report.query,u,'query',{})
        prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=True)
        connection=db.session.connection()
        monkeypatch.setattr(connection,'get_isolation_level',lambda:'READ COMMITTED')
        new,nm=load_report_page(Report.query,u,'query',{})
        assert om==nm and [r.id for r in old]==[r.id for r in new]
        assert 'list query prototype fallback: RuntimeError' in caplog.text


def test_a2_commission_scope_and_adapter(prototype_mysql_app, caplog):
    from testkit.factories import ScenarioFactory
    from app.list_paging import load_report_page
    with prototype_mysql_app.app_context():
        factory=ScenarioFactory();d=factory.department();u=factory.user(d,role_key='admin',account='admin')
        e1=Entrust(entrust_no='E1');e2=Entrust(entrust_no='E2');db.session.add_all([e1,e2]);db.session.flush()
        wanted=e1.id
        db.session.add_all([Report(report_no='R1',entrust_no='E1',detail={'workflowDates':{'testStartDate':'2026-01-02'}}),Report(report_no='R2',entrust_no='E2')]);db.session.commit()
        for body in [{'commissionIds':[wanted]}, {'commissionIds':[]}, {'adapter':'platform','commissionIds':[wanted]},
                     {'workflowDates':{'testStartDate':{'enabled':True,'from':'2026-01-01','to':'2026-01-03'}}}]:
            results=[]
            for enabled in (False,True):
                prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=enabled,LIST_QUERY_A2=enabled)
                rows,meta=load_report_page(Report.query,u,'query',dict(body,contains='R',searchField='all'))
                results.append((meta,[(r.id,r.report_no,r.detail) for r in rows]))
            assert results[0]==results[1]
        assert 'list query prototype fallback:' not in caplog.text


@pytest.mark.parametrize('administrator',[True,False])
@pytest.mark.parametrize('endpoint,view,presentation',[
    ('reports','query','report'),('reports','data_entry','report'),
    ('reports','contract_review','registration-sample'),('reports','review','report'),
    ('reports','approval','report'),('samples','register','registration-sample'),
    ('samples','outbound','outbound'),
])
def test_a2_route_permissions(prototype_mysql_app,monkeypatch,caplog,endpoint,view,presentation,administrator):
    from testkit.factories import ScenarioFactory
    from test_list_query_prototype import test_prototype_route_permission_and_full_response
    with prototype_mysql_app.app_context():
        client=prototype_mysql_app.test_client()
        original=client.post
        def search_post(*args,**kwargs):
            if kwargs.get('json',{}).get('serverPage'):
                kwargs['json']=dict(kwargs['json'],searchField='all',contains='SCOPE')
                prototype_mysql_app.config['LIST_QUERY_A2']=prototype_mysql_app.config['LIST_QUERY_PROTOTYPE']
            return original(*args,**kwargs)
        monkeypatch.setattr(client,'post',search_post)
        test_prototype_route_permission_and_full_response(prototype_mysql_app,client,ScenarioFactory(),monkeypatch,endpoint,view,presentation,administrator)
        assert 'list query prototype fallback:' not in caplog.text
