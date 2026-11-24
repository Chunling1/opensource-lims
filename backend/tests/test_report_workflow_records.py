from datetime import datetime
from types import SimpleNamespace
import pytest
pytest_plugins = ('testkit.fixtures',)

@pytest.fixture
def records(isolated_app):
    from app.extensions import db
    from app.models import OperationAudit
    with isolated_app.app_context():
        for index, (number, action, before, after, success) in enumerate([
            ('R1','report.entrust_change.save',{'client':'旧单位'},{'client':'新单位','secret':'hidden'},True),
            ('R1','report.data_entry.save',{}, {},True),
            ('R1','report.review.return',{}, {'returnInfo':{'note':'补充原始记录','source':'审核退回','target':'检测更改'}},True),
            ('R2','report.review.return',{}, {'returnInfo':{'note':'另一报告保密内容'}},True),
            ('R1','report.review.return',{}, {'returnInfo':{'note':'失败请求'}},False),
        ]):
            db.session.add(OperationAudit(object_type='report',object_id=number,action=action,category='workflow',before_data=before,after_data=after,success=success,user_name='审核员',account='reviewer',ip_address='private',created_at=datetime(2026,10,19,10,index)))
        db.session.commit()
        yield

def test_only_current_report_successful_evidence_is_projected(records):
    from app.applications.report_lifecycle.records import report_records
    issue=report_records('R1','issues',1,10)
    assert issue['total']==1
    assert issue['items'][0]['description']=='补充原始记录'
    assert issue['items'][0]['handler']==''  # no invented resolution
    change=report_records('R1','commission',1,10)['items'][0]
    assert (change['field'],change['before'],change['after'])==('委托单位','旧单位','新单位')
    assert 'secret' not in str(change) and 'private' not in str(change)
    legacy=report_records('R1','testing',1,10)['items'][0]
    assert legacy['field']=='操作记录（未保存字段差异）'
    assert legacy['before']==legacy['after']==''
    assert report_records('R1','workflow',99,10)['page']==1

def test_endpoint_reuses_authoritative_view_scope_before_reading(records,isolated_app,monkeypatch):
    from flask import g
    from app.blueprints import reports
    calls=[]
    def scope(user,no,view):
        calls.append((no,view))
        return None,None,'无权查看'
    monkeypatch.setattr(reports,'get_authorized_report_for_view',scope)
    with isolated_app.test_request_context('/?view=approval&kind=issues'):
        g.current_user=SimpleNamespace()
        response,status=reports.report_workflow_records.__wrapped__('R1')
        assert response.get_json()['code']==403
    assert calls==[('R1','approval')]

@pytest.mark.parametrize('query',['kind=bogus','page=0','pageSize=100000','page=x'])
def test_endpoint_rejects_invalid_pagination(records,isolated_app,monkeypatch,query):
    from flask import g
    from app.blueprints import reports
    monkeypatch.setattr(reports,'get_authorized_report_for_view',lambda *_:(SimpleNamespace(report_no='R1'),None,None))
    with isolated_app.test_request_context('/?view=review&'+query):
        g.current_user=SimpleNamespace()
        response,status=reports.report_workflow_records.__wrapped__('R1')
        assert response.get_json()['code']==1

def test_endpoint_is_readonly_and_uncacheable(records,isolated_app,monkeypatch):
    from flask import g
    from app.blueprints import reports
    from app.extensions import db
    monkeypatch.setattr(reports,'get_authorized_report_for_view',lambda *_:(SimpleNamespace(report_no='R1'),None,None))
    monkeypatch.setattr(db.session,'commit',lambda:pytest.fail('read must not commit'))
    with isolated_app.test_request_context('/?view=print&kind=issues'):
        g.current_user=SimpleNamespace()
        response=reports.report_workflow_records.__wrapped__('R1')
        assert response.get_json()['data']['items'][0]['description']=='补充原始记录'
        assert response.headers['Cache-Control']=='no-store'
