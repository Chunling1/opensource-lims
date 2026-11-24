"""Appointed sealers can read in-scope issuance tasks without project handling rights."""
import pytest

from app.extensions import db
from app.models import user_data_departments
from app.security import issue_token
from app.esign_seal_confirmation import assign, access_error
from app.esign_access import manager_report_error
from app.authorization_scope import user_has_project_step, project_for_report
from app.applications.report_lifecycle.queries import get_authorized_report_for_view
from test_preserved_approval_and_seal_confirmation import prepared

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture
def office_case(prepared, scenario_factory, isolated_client):
    report, version, _, _ = prepared
    f = scenario_factory
    office = f.department(name='虚拟签章办公室')
    user = f.user(office, data_scope_type='department_project', permissions=[
        'report.print.view', 'report.query.view', 'report.review.view',
        'report.approval.view', 'report.pdf.preview',
    ])
    project = project_for_report(report)
    f.grant_data_department(user, project.department)
    assign(user, True)
    db.session.commit()
    return isolated_client, user, report, version, project


def listing(case):
    client, user, *_ = case
    return client.post('/api/reports/query', json={'view': 'print'},
        headers={'Authorization': 'Bearer ' + issue_token(user)}).get_json()


def test_sealer_sees_issuance_list_and_detail_without_project_appointment(office_case):
    client, user, report, _, project = office_case
    assert not user_has_project_step(user, project, 'report_print')
    assert not access_error(user, report)
    result = listing(office_case)
    assert result['code'] == 0, result
    assert [r['reportNo'] for r in result['data']['rows']] == [report.report_no]
    found, projection, error = get_authorized_report_for_view(user, report.report_no, 'print')
    assert found == report and projection == 'active' and not error
    headers = {'Authorization': 'Bearer ' + issue_token(user)}
    response = client.get(f'/api/reports/{report.report_no}?view=print', headers=headers).get_json()
    assert response['code'] == 0, response
    preview = client.get(f'/api/report-assurance/reports/{report.report_no}/artifact?view=print&file=1&original=1', headers=headers)
    assert preview.status_code == 200 and preview.data.startswith(b'%PDF')
    # Read access must not grant dispatch, cancellation, review or approval rights.
    assert manager_report_error(user, report)
    for step in ('report_print', 'report_review', 'report_approval', 'data_entry'):
        assert not user_has_project_step(user, project, step)


@pytest.mark.parametrize('missing', ['seal', 'data', 'page', 'enabled', 'approval', 'state'])
def test_sealer_read_access_requires_all_existing_boundaries(office_case, missing):
    _, user, report, _, _ = office_case
    if missing == 'seal':
        assign(user, False)
    elif missing == 'data':
        db.session.execute(user_data_departments.delete().where(user_data_departments.c.user_id == user.id))
    elif missing == 'page':
        user.permissions = [p for p in user.permissions if p.code != 'report.print.view']
    elif missing == 'enabled':
        user.enabled = False
    elif missing == 'approval':
        report.approved_document_version_id = None
    elif missing == 'state':
        report.status = '待批准'
    db.session.commit()
    assert get_authorized_report_for_view(user, report.report_no, 'print')[2]
    result = listing(office_case)
    assert result['code'] != 0 or not result['data']['rows']


@pytest.mark.parametrize('view,status', [('review', '待审核'), ('approval', '待批准')])
def test_sealer_read_exception_does_not_open_other_processing_pages(office_case, view, status):
    _, user, report, *_ = office_case
    report.status = status
    db.session.commit()
    assert get_authorized_report_for_view(user, report.report_no, view)[2]
