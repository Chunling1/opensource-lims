from datetime import datetime
import pytest
from sqlalchemy import event
from app.extensions import db
from app.models import Report, OperationAudit
from app.applications.report_lifecycle.query_details import query_details

pytest_plugins = ('testkit.fixtures',)


def test_actual_latest_successful_operators_and_selected_business_dates(isolated_app):
    with isolated_app.app_context():
        report = Report(report_no='QA-QUERY', entrust_no='QA-WT', owner='指定负责人', detail={
            'workflowDates': {'sampleInboundAt': '2026-10-22'},
            'checkInput': {'reviewer': '尚未审核的指定人员', 'testStartDate': '2026-10-23', 'testDate': '2026-10-25', 'standard':'STD-CURRENT','result':'实测结果'},
            'rawSample': {'spec': '规格A', 'sampleAmount': '2台'}},
            sample_pickup={'signed': True, 'receiverName': '领样人', 'outTime': '2026-10-23'})
        db.session.add(report)
        for action, person, success, kind, identity in [
            ('entrust.register.complete', '委托完成人', True, 'entrust', 'QA-WT'),
            ('sample.inbound.confirm', '入库人', True, 'report', 'QA-QUERY'),
            ('report.review.pass', '第一轮审核人', True, 'report', 'QA-QUERY'),
            ('report.review.return', '退回人', True, 'report', 'QA-QUERY'),
            ('report.review.pass', '第二轮审核人', True, 'report', 'QA-QUERY'),
            ('report.review.pass', '失败操作', False, 'report', 'QA-QUERY'),
            ('report.approval.pass', '其他报告批准人', True, 'report', 'OTHER'),
        ]:
            db.session.add(OperationAudit(action=action, user_name=person, success=success,
                object_type=kind, object_id=identity, created_at=datetime(2026,10,28,1,30)))
        db.session.commit()
        row=query_details([report])['QA-QUERY']
        assert row['commissionCompletedBy']=='委托完成人'
        assert row['reportReviewedBy']=='第二轮审核人'
        assert row['reportReviewedAt']=='2026-10-28 09:30:00'
        assert row['reportApprovedBy']==row['reportApprovedAt']==''
        assert row['sampleInboundDate']=='2026-10-22'
        assert row['sampleInboundAt']=='2026-10-28 09:30:00'
        assert row['sampleReceiver']=='领样人'
        assert row['specification']=='规格A' and row['testEndDate']=='2026-10-25'
        assert row['testBasis']=='STD-CURRENT' and row['testResult']=='实测结果'


def test_query_audits_batched_without_loading_snapshots(isolated_app):
    with isolated_app.app_context():
        reports=[Report(report_no=f'QA-{i}',entrust_no='QA-WT',detail={}) for i in range(40)]
        db.session.add_all(reports);db.session.commit()
        for report in reports: _=report.detail
        statements=[]
        def capture(conn,cursor,statement,*args): statements.append(statement)
        event.listen(db.engine,'before_cursor_execute',capture)
        try: result=query_details(reports)
        finally: event.remove(db.engine,'before_cursor_execute',capture)
        assert len(result)==40
        assert len(statements)==2
        assert all('before_data' not in s and 'after_data' not in s for s in statements)


def test_query_endpoint_includes_operators_and_denies_unauthorized_reader(isolated_app,scenario_factory):
    from app.security import issue_token
    f=scenario_factory;dept=f.department();project,steps=f.project(dept)
    user=f.user(dept,role_key='admin',permissions=['report.query.view'],project_steps=steps)
    outsider=f.user(dept,permissions=[])
    report=Report(report_no='QA-ENDPOINT',sample_no='QA-ENDPOINT',department=dept.name,owner=user.name,
                  project=project.name,status='检测录入中',sample_status='已领取',detail={'rawSample':{'schemeCode':project.code,'spec':'SPEC'}})
    db.session.add_all([report,OperationAudit(object_type='report',object_id=report.report_no,
        action='sample.inbound.confirm',user_name='实际入库人',success=True)])
    db.session.commit()
    client=isolated_app.test_client()
    response=client.post('/api/reports/query',headers={'Authorization':'Bearer '+issue_token(user)},json={'view':'query'})
    assert response.json['code']==0,response.json
    row=response.json['data']['rows'][0]
    assert row['sampleInboundBy']=='实际入库人' and row['specification']=='SPEC'
    denied=client.post('/api/reports/query',headers={'Authorization':'Bearer '+issue_token(outsider)},json={'view':'query'})
    assert denied.json['code']==403 and denied.json['data'] is None
