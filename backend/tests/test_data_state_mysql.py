"""Execute the unified status on temporary socket-only MySQL, including A2."""
from app.extensions import db
from app.models import Report, OperationAudit
from app.list_paging import load_report_page
from app.data_entry_state import report_data_entry_started
from testkit.factories import ScenarioFactory
from test_mysql_local_concurrency import mysql_server
from test_list_query_prototype import prototype_mysql_app


def test_mysql_entry_status_filters_and_paging(prototype_mysql_app):
    with prototype_mysql_app.app_context():
        f=ScenarioFactory();dept=f.department();user=f.user(dept,role_key='admin')
        for i in range(3):
            db.session.add(Report(report_no=f'STATE-{i}',sample_no=f'STATE-{i}',department=dept.name,status='检测录入中',sample_status='已领取',detail={'dataEntryStarted':None,'checkInput':{'copied':True}}))
            db.session.add(OperationAudit(object_type='report',object_id=f'STATE-{i}',action='sample.out_warehouse.sign',success=True))
        db.session.flush()
        db.session.add(OperationAudit(object_type='report',object_id='STATE-2',action='report.data_entry.save',success=True))
        db.session.commit()
        for ids,a2 in [(False,False),(True,False),(True,True)]:
            prototype_mysql_app.config.update(LIST_PAGE_IDS=ids,LIST_QUERY_A2=a2,LIST_QUERY_PROTOTYPE=False)
            for label,expected in [('样品出库领取完成',['STATE-0','STATE-1']),('检测数据录入中',['STATE-2'])]:
                rows,meta=load_report_page(Report.query,user,'query',{'status':label,'sort':'code','direction':'asc','pageSize':10})
                assert meta['total']==len(expected)
                assert [r.report_no for r in rows]==expected
                assert all(r.to_row()['dataStatus']==label for r in rows)
                assert all(report_data_entry_started(r)==(label=='检测数据录入中') for r in rows)
