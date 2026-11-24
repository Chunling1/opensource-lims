from copy import deepcopy
from types import SimpleNamespace
import pytest
from app.extensions import db
from app.models import Report, ReportCorrectionRequest
from app.report_correction_dates import original_issue_date, calendar_date
from test_report_correction_approval import actors, submit, approve_both
from test_internal_report_corrections import previous_version

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('value', ['/', '—', 'None', '', '2026-02-30'])
def test_markers_are_not_original_dates(value):
    assert calendar_date(value) == ''


@pytest.mark.parametrize('value', ['/', '2026-10-24'])
def test_returned_ordinary_report_never_uses_copied_date(value):
    report = SimpleNamespace(report_kind='main', version='V3', detail={
        'changeRound': True, 'summary': [{'title':'实验信息','fields':[['原报告日期', value]]}]})
    assert original_issue_date(report) == ''


@pytest.mark.parametrize('kind', ['internal', 'external'])
def test_real_correction_freezes_previous_approval(actors, isolated_client, kind):
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'], kind)['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    row = db.session.get(ReportCorrectionRequest, rid)
    target = Report.query.filter_by(report_no=row.correction_report_no).one()
    before = deepcopy(target.detail)
    assert original_issue_date(target) == '2026-10-24'
    assert before['correctionOriginalIssueDate']['sourceVersionId'] == version.id
    assert target.detail == before
    # The source may later receive another approval; the original date is fixed.
    version.snapshot = {'approvalDate':'2026-11-08'}
    db.session.flush()
    assert original_issue_date(target) == '2026-10-24'


def test_existing_internal_history_restores_original_date(actors, isolated_client):
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    detail = deepcopy(report.detail); detail.pop('correctionOriginalIssueDate')
    report.detail = detail; db.session.flush()
    assert original_issue_date(report) == '2026-10-24'


def test_pending_or_wrong_correction_cannot_enable_label(actors, isolated_client):
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    report.detail = {'internalCorrectionRevision':rid, 'correctionRequestId':rid,
                     'summary':[{'title':'实验信息','fields':[['原报告日期','2026-10-24']]}]}
    assert original_issue_date(report) == ''
