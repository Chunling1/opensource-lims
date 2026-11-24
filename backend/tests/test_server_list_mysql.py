"""Execute pagination expressions on an ephemeral, socket-only MySQL 8 server."""
import pytest
import pymysql
from sqlalchemy import select
from app import create_app
from app.extensions import db
from app.models import Report,Entrust
from app.list_paging import report_fields,report_page
from app.list_projection import list_reports
from testkit.app import isolated_config
from testkit.factories import ScenarioFactory
from test_mysql_local_concurrency import mysql_server


def test_mysql_executes_global_filters_and_page_projection(mysql_server,tmp_path):
    conn=pymysql.connect(unix_socket=str(mysql_server),user='root',autocommit=True)
    with conn.cursor() as cursor:cursor.execute('CREATE DATABASE pagination_qa CHARACTER SET utf8mb4')
    conn.close()
    config=isolated_config(tmp_path)
    config.SQLALCHEMY_DATABASE_URI=f'mysql+pymysql://root@localhost/pagination_qa?unix_socket={mysql_server}'
    app=create_app(config)
    with app.app_context():
        db.create_all()
        metadata.create_all(db.engine)
        factory=ScenarioFactory();dept=factory.department();user=factory.user(dept,role_key='admin',account='admin')
        db.session.add(Entrust(entrust_no='WT',project_name='项目',info={'handler':'经办人'}))
        for i in range(25):
            db.session.add(Report(report_no=f'MYSQL-{i:03}',sample_no=f'S-{i:03}',department=dept.name,entrust_no='WT',status='待批准',detail={
                'rawSample':{'sampleName':'测试样品','projectList':['参数甲','参数乙']},
                'summary':[{'fields':[['检测依据','GB2026']]}]}))
        db.session.commit()
        fields=report_fields('report')
        # Execute every exposed expression (not just SQL compilation).
        values=db.session.execute(select(*fields.values()).select_from(Report).outerjoin(Entrust,Report.entrust_no==Entrust.entrust_no).limit(1)).first()
        assert values is not None
        query,meta=report_page(Report.query,user,'query',{'page':2,'pageSize':10,'sort':'code'})
        assert meta['total']==25
        assert [r.sample_no for r in list_reports(query)]==[f'S-{i:03}' for i in range(10,20)]
        query,meta=report_page(Report.query,user,'query',{'contains':'参数甲、参数乙','searchField':'testItems','pageSize':3})
        assert meta['total']==25 and len(list_reports(query))==3
        query,meta=report_page(Report.query,user,'query',{'contains':'GB2026','searchField':'testBasis'})
        assert meta['total']==25
        from app.list_paging import scheme_fields,date_text
        db.session.add(Report(report_no='NAT-S2',sample_no='S2',detail={'summary':[{'fields':[['检测方案','项目（YP）']]}]}))
        db.session.add(Report(report_no='NAT-S10',sample_no='S10'))
        db.session.commit()
        query,meta=report_page(Report.query.filter(Report.report_no.like('NAT-%')),user,'query',{'sort':'code'})
        assert [r.sample_no for r in list_reports(query)]==['S2','S10']
        code,name=scheme_fields()
        assert db.session.execute(select(code,name).where(Report.report_no=='NAT-S2')).one()==('YP','项目')
        assert db.session.execute(select(date_text('2026年1月2日'))).scalar()=='2026-01-02'
        long_parameters=['参数'*20+str(i) for i in range(40)]
        db.session.add(Report(report_no='LONG',detail={'rawSample':{'projectList':long_parameters}}))
        db.session.commit()
        query,meta=report_page(Report.query,user,'query',{'contains':long_parameters[-1],'searchField':'testItems'})
        assert meta['total']==1 and list_reports(query)[0].report_no=='LONG'
        db.session.remove();db.engine.dispose()
