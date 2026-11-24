"""Preserve visibility, dates, paging and fresh permissions while batching reads."""
from datetime import date, datetime, timedelta
import pytest
from sqlalchemy import event
from app.extensions import db
from app.models import Report, StdLibraryItem, OperationAudit, FinanceBill, user_action_permissions
from app.list_reads import reuse_list_reads, prime_identifiers

pytest_plugins = ('testkit.fixtures',)


def test_standard_scope_is_bounded_for_saved_forms_and_fresh_next_read(isolated_app, scenario_factory):
    from app.standard_control import selected_controlled_standards
    from app.preflight_reads import reuse_preflight_reads
    dept = scenario_factory.department()
    standard = StdLibraryItem(code='SHARED', name='标准一', use_depts=dept.name)
    db.session.add(standard); db.session.flush()
    report = Report(report_no='R', department=dept.name, detail={
        'rawSample': {'testBases':['SHARED'], 'standardItemIds':[standard.id]},
        'checkInput': {'standards':['SHARED']},
    })
    db.session.add(report); db.session.commit()
    queries=[]
    def capture(_c,_cu,sql,*args):
        if 'FROM std_library_items' in sql: queries.append(sql)
    @reuse_preflight_reads
    def read():
        return [selected_controlled_standards(['SHARED'], [standard.id], dept.name) for _ in range(60)]
    event.listen(db.engine,'before_cursor_execute',capture)
    try:
        rows=read()
    finally: event.remove(db.engine,'before_cursor_execute',capture)
    assert len(queries) <= 2
    assert rows[0] == rows[-1]
    # Changing the catalogue must be visible on the next independent read.
    standard.deleted_at=datetime.now(); db.session.commit()
    assert read()[0] != rows[0]


@pytest.mark.parametrize('status', ['待合同评审','待样品入库','待样品领取','检测录入中','检测更改中','退回待重传','待审核','待批准','待打印','待发放','已发放','已归档'])
def test_workflow_membership_equals_full_display_projection(isolated_app, status):
    from app.applications.report_lifecycle.queries import report_detail_projection, REPORT_DETAIL_VIEW_POLICIES
    from app.platform.workflow.visibility import report_projection
    actions=['report.review.undo','report.report_check.undo','report.approval.undo','report.archive.undo']
    for voided in (False, True):
        for archive in ('','归档完成'):
            report=Report(report_no='R',status=status,sample_status='已领取',sample_reg_state='登记完成',archive_state=archive,voided=voided,detail={'internalCorrectionRevision':1})
            row=report.to_row(issuance_label='报告签发中'); row['allowedActions']=actions
            for view, policy in REPORT_DETAIL_VIEW_POLICIES.items():
                if policy['projection']=='report':
                    assert report_detail_projection(report,view,allowed_actions=actions)==report_projection(row,view), (status,view)


def test_standard_sql_pages_preserve_edit_sort_and_scope(isolated_app, scenario_factory):
    from app.blueprints.quality import _edited_page
    from app.audit import records_by_edit_time
    rows=[StdLibraryItem(code=f'S-{i}',name='标准',use_depts='可见' if i<8 else '其他') for i in range(10)]
    db.session.add_all(rows); db.session.flush()
    for index in (1,3,5,8):
        db.session.add(OperationAudit(object_type='controlled_standard',object_id=str(rows[index].id),action='edit',success=True,created_at=datetime(2026,10,1)+timedelta(days=index//2)))
    db.session.add(OperationAudit(object_type='controlled_standard',object_id=str(rows[0].id),action='edit',success=False,created_at=datetime(2026,11,1)))
    db.session.commit()
    query=StdLibraryItem.query.filter_by(use_depts='可见')
    expected=records_by_edit_time(query.all(),'controlled_standard',lambda r:r.id)
    actual=[pair for page in range(1,4) for pair in _edited_page(query,'controlled_standard',page,3)]
    assert [(r.id,t) for r,t in actual]==[(r.id,t) for r,t in expected]


def test_user_grants_do_not_survive_the_list_invocation(isolated_app, scenario_factory):
    f=scenario_factory; user=f.user(f.department())
    code='report.seal.confirm'
    db.session.execute(user_action_permissions.insert().values(user_id=user.id,action_code=code)); db.session.commit()
    from app.esign_seal_confirmation import has_permission, assign
    @reuse_list_reads
    def read():
        prime_identifiers('user',[user.id])
        return user.action_codes(), has_permission(user)
    before=read()
    assert code in before[0] and before[1]
    assign(user,False); db.session.commit()
    after=read()
    assert code not in after[0] and not after[1]
    assert not has_permission(user)


def test_workbench_keeps_business_due_dates(isolated_app, scenario_factory):
    from app.app_workspace import dashboard_data
    f=scenario_factory; dept=f.department(); user=f.user(dept,role_key='admin'); project,_=f.project(dept)
    db.session.add(Report(report_no='DUE',department=dept.name,project=project.name,status='待审核',detail={'rawSample':{'requiredTestDate':'2020-01-01','sampleName':'待办样品'},'checkInput':{'ignored':'large'}}))
    db.session.commit()
    data=dashboard_data(user,{})
    row=next(r for r in data['items'] if r['id']=='DUE')
    assert row['due']=='2020-01-01' and row['overdue'] and row['name']=='待办样品'
