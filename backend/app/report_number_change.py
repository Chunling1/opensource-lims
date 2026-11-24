"""Rename current report indexes without rewriting provider/audit evidence."""
from copy import deepcopy

from sqlalchemy import inspect, select, update

from .models import Report
ob = None
intakes = None


class ReportNumberChangeError(ValueError):
    pass


def check_number_change(session, old, new):
    if old == new:
        return
    # A task existing, approved, failed or in flight is not proof of reversal.
    reversed_step = session.execute(select(ob.steps.c.id).join(
        ob.events, ob.events.c.id == ob.steps.c.event_id).where(
        ob.events.c.business_key == old,
        ob.steps.c.operation == 'poContractCounterReview',
        ob.steps.c.state == 'SUCCEEDED').limit(1).with_for_update()).first()
    if reversed_step:
        raise ReportNumberChangeError('该报告已完成外部ERP反审核，不能修改报告编号；其他字段仍可修改。')
    if session.execute(select(Report.id).where(Report.report_no == new)).first():
        raise ReportNumberChangeError(f'报告编号 {new} 已存在，请选择其他报告标题')
    # Do not merge a new report into an orphaned historical outbound identity.
    for table, column in ((intakes, intakes.c.report_no),
                          (ob.owners, ob.owners.c.business_key),
                          (ob.events, ob.events.c.business_key),
                          (ob.reservations, ob.reservations.c.business_key)):
        if session.execute(select(column).where(column == new).limit(1)).first():
            raise ReportNumberChangeError('目标报告编号已有外部ERP关联记录，请核对后选择其他编号。')
    if session.execute(select(ob.reservations.c.business_key).where(
            ob.reservations.c.business_key.startswith(new + ':', autoescape=True)).limit(1)).first():
        raise ReportNumberChangeError('目标报告编号已有外部ERP关联记录，请核对后选择其他编号。')


def move_number_links(session, report, old, new):
    """Called before flush, in the report edit transaction; no commit or HTTP."""
    from .extensions import db
    from .admin_corrections.numbering import rewrite
    from .platform.audit import repoint_operation_audits

    # Keep report.id, sample_no, version IDs, files and all immutable JSON intact.
    present = set(inspect(session.connection()).get_table_names())
    for table in db.metadata.tables.values():
        if table is Report.__table__ or table.name not in present:
            continue
        for name in ('report_no', 'main_report_no', 'correction_report_no'):
            if name in table.c:
                session.execute(update(table).where(table.c[name] == old).values({name: new}))
    for table, column in ((intakes, intakes.c.report_no),
                          (ob.owners, ob.owners.c.business_key),
                          (ob.events, ob.events.c.business_key),
                          (ob.reservations, ob.reservations.c.business_key)):
        session.execute(update(table).where(column == old).values({column.name: new}))
    # Child reservation owners are reportNo:projectId, not just reportNo.
    children = session.execute(select(ob.reservations).where(
        ob.reservations.c.business_key.startswith(old + ':', autoescape=True))).mappings().all()
    for child in children:
        session.execute(update(ob.reservations).where(
            ob.reservations.c.namespace == child['namespace'],
            ob.reservations.c.external_id == child['external_id']).values(
            business_key=new + child['business_key'][len(old):]))

    # Other reports retain their own numbers, but their source lookup follows
    # this same report ID. Only current identity fields are rewritten.
    keys = {'reportNo', 'mainReportNo', 'baseReportNo', 'derivedFrom', 'report_no'}
    candidates = session.query(Report).filter(Report.main_report_no == old).all()
    for row in [report, *candidates]:
        if row.main_report_no == old:
            row.main_report_no = new
        value = rewrite(deepcopy(row.detail), keys, old, new)
        if value != row.detail:
            row.detail = value
    repoint_operation_audits('report', old, new)


def register_error_handler(app):
    @app.errorhandler(ReportNumberChangeError)
    def number_error(exc):
        from flask import jsonify
        from .extensions import db
        db.session.rollback()
        return jsonify(code=1, message=str(exc), data=None), 200
