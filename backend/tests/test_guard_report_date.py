"""Approval date is authoritative; legacy input stays historical only."""
from datetime import datetime, timedelta
import pytest
from app.extensions import db
from app.models import OperationAudit, ReportDocumentVersion
from app.report_business_date import report_date
from app.edit_concurrency import test_form_version as form_version
from test_equipment_department_authorization import case, headers
pytest_plugins = ('testkit.fixtures',)


def event(report, action, day):
    row = OperationAudit(category='workflow', object_type='report', object_id=report.report_no,
                         action=action, success=True, created_at=datetime.fromisoformat(day))
    db.session.add(row); db.session.flush()
    return row


def test_unapproved_never_uses_legacy_or_clock(case):
    report = case[6]
    report.detail = {'reportDate':'2020-01-01', 'checkInput':{'reportDate':'2021-01-01'}}
    assert report_date(report) == ''
    from app.blueprints.public_portal import _public_report_payload
    assert _public_report_payload(report)['reportDate'] == '—'


def test_effective_event_without_version_and_undo(case):
    report = case[6]
    event(report, 'report.approval.pass', '2026-10-20T18:00:00')
    assert report_date(report) == '2026-10-21'
    event(report, 'report.approval.undo', '2026-10-22T00:00:00')
    assert report_date(report) == ''


def test_snapshot_precedes_event_and_rejects_other_report_version(case):
    report=case[6]
    event(report, 'report.approval.pass', '2026-10-20T00:00:00')
    v=ReportDocumentVersion(report_no=report.report_no, output_kind='official', version_no=1,
        status='approved',profile_code='QA',sha256='a'*64,source_hash='qa',snapshot={'approvalDate':'2026-10-19'})
    db.session.add(v);db.session.flush();report.approved_document_version_id=v.id
    assert report_date(report)=='2026-10-19'
    v.report_no='OTHER'
    assert report_date(report)=='2026-10-20'


@pytest.mark.parametrize('legacy', [False,True])
def test_save_ignores_new_legacy_writes_and_preserves_old_values(case, legacy):
    client,user,*_=case
    report=case[6]
    historical={'specialReportDate':True,'reportDate':'2020-01-01'} if legacy else {}
    report.detail={'checkInput':dict(historical)};db.session.commit()
    result=client.put(f'/api/reports/{report.report_no}/testinfo',headers=headers(user),json={
        'testEditVersion':form_version(report),'reportDate':'2099-12-31','specialReportDate':False,
        'testIntervals':[]}).get_json()
    assert result['code']==0,result
    ci=report.detail['checkInput']
    assert {k:ci[k] for k in historical}==historical
    if not legacy: assert 'reportDate' not in ci and 'specialReportDate' not in ci
