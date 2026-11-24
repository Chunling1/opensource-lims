"""Lists, SQL filters and pickup recall agree on the first actual save."""
import pytest
from sqlalchemy import select, event
from app.extensions import db
from app.models import Report, OperationAudit
from app.data_entry_state import report_data_entry_started
from app.status_machine import sample_return_stock_blocker
from app.list_paging import data_status
from app.list_reads import reuse_list_reads, prime_identifiers
from app.blueprints.samples import _outbound_data_entry_started
from app.applications.sample_logistics.commands import execute_sample_return_stock

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('marker,pickup,save,expected', [
    ('absent', True, 'none', False), (None, True, 'none', False),
    ('absent', True, 'before', False), ('absent', True, 'failed', False),
    ('absent', True, 'after', True), (None, True, 'after', True),
    (False, True, 'after', False), (True, True, 'none', True),
    ('absent', False, 'none', True),
])
def test_state_and_recall(isolated_app, scenario_factory, marker, pickup, save, expected):
    dept = scenario_factory.department()
    project, steps = scenario_factory.project(dept)
    user = scenario_factory.user(dept, role_key='admin')
    detail = {'checkInput': {'copiedValue': 'legacy'}, 'rawSample': {'schemeCode':project.code,'schemeName':project.name}}
    if marker != 'absent': detail['dataEntryStarted'] = marker
    report = Report(report_no='STATE', status='检测录入中', sample_status='已领取',
                    department=dept.name, project=project.name, detail=detail)
    db.session.add(report)
    def audit(action, success=True):
        db.session.add(OperationAudit(object_type='report', object_id=report.report_no,
            action=action, success=success)); db.session.flush()
    if save == 'before': audit('report.data_entry.save')
    if pickup: audit('sample.out_warehouse.sign')
    if save in ('after', 'failed'): audit('report.data_entry.save', save == 'after')
    db.session.commit()
    before = dict(report.detail)
    label = '检测数据录入中' if expected else '样品出库领取完成'
    for _ in range(2):  # Repeated reads/opening do not mutate entry state.
        assert report_data_entry_started(report) is expected
        assert _outbound_data_entry_started(report) is expected
        assert report.to_row()['dataStatus'] == label
        assert (sample_return_stock_blocker(report) is None) is (not expected)
        for logistics in (False, True):
            assert db.session.execute(select(data_status(logistics=logistics)).where(Report.id == report.id)).scalar_one() == label
    assert report.detail == before
    result = execute_sample_return_stock(user, report.report_no)
    assert result.code == (1 if expected else 0), result
    if not expected: assert report.status == '待样品领取'


def test_returned_report_cannot_recall_pickup(isolated_app, scenario_factory):
    report = Report(report_no='RETURNED',status='退回待重传',sample_status='已领取',detail={'dataEntryStarted':False})
    assert report.to_row()['dataStatus'] == '检测数据录入中'
    assert sample_return_stock_blocker(report)


def test_list_audits_are_batched(isolated_app, scenario_factory):
    rows = [Report(report_no=f'BATCH-{i}',status='检测录入中',sample_status='已领取',detail={'checkInput':{'copied':True}}) for i in range(25)]
    db.session.add_all(rows);db.session.flush()
    for r in rows:
        db.session.add(OperationAudit(object_type='report',object_id=r.report_no,action='sample.out_warehouse.sign',success=True))
    db.session.commit()
    ids = [r.report_no for r in rows]
    sql=[]
    def capture(conn,cursor,statement,parameters,context,many):
        if 'operation_audits' in statement: sql.append(statement)
    @reuse_list_reads
    def read():
        prime_identifiers('report',ids,rows)
        return [report_data_entry_started(r) for r in rows]
    event.listen(db.engine,'before_cursor_execute',capture)
    try: assert set(read()) == {False}
    finally: event.remove(db.engine,'before_cursor_execute',capture)
    assert len(sql) == 2


def test_first_successful_save_changes_state(isolated_app,scenario_factory,monkeypatch):
    from app.edit_concurrency import test_form_version as token
    from app.security import issue_token
    monkeypatch.setattr('app.preview_cache.schedule_after_save',lambda *a:None)
    identity=scenario_factory.identity_scenario(permission_codes=('testing.data_entry.view',),granted_step_codes=('data_entry',))
    report=Report(report_no='FIRST-SAVE',department=identity.department.name,project=identity.project.name,
        owner=identity.user.name,status='检测录入中',sample_status='已领取',detail={'dataEntryStarted':False})
    db.session.add(report);db.session.commit()
    before=report.to_row()
    assert before['dataStatus']=='样品出库领取完成'
    response=isolated_app.test_client().put('/api/reports/FIRST-SAVE/testinfo',
        headers={'Authorization':'Bearer '+issue_token(identity.user)},json={'testEditVersion':token(report),'result':'首次录入'})
    assert response.get_json()['code']==0,response.get_json()
    db.session.refresh(report)
    assert report.detail['dataEntryStarted'] is True
    assert report.to_row()['dataStatus']=='检测数据录入中'
    assert sample_return_stock_blocker(report)
