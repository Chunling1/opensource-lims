"""Batch-3 Q13 (2026-11-07): report content accepts up to 100 extra pages."""
import pytest

from app.blueprints import report_documents
from app.extensions import db
from testkit.factories import login_headers
from test_preserved_approval_and_seal_confirmation import prepared

pytest_plugins = ('testkit.fixtures',)


def test_extra_page_limit_constant_is_one_hundred():
    assert report_documents.MAX_EXTRA_PAGES == 100


@pytest.mark.parametrize('count,accepted', [(100, True), (101, False)])
def test_extra_page_limit_is_one_hundred(prepared, isolated_client, count, accepted):
    report, _version, user, _raw = prepared
    user.role_key = 'admin'
    report.status = '检测录入中'
    report.detail = {}
    db.session.commit()
    body = {
        'resultGroups': [],
        'photos': [],
        'remarks': '',
        'extraPages': [{'title': f'附页{i}', 'content': 'x'} for i in range(count)],
    }
    response = isolated_client.put(
        f'/api/reports/{report.report_no}/document-content?view=query',
        headers=login_headers(isolated_client, user.account),
        json=body,
    ).get_json()
    if accepted:
        # Any refusal here must not be the page-count rule.
        assert '不能超过' not in (response.get('message') or ''), response
        assert response['code'] == 0, response
        from app.models import ReportDocumentContent
        db.session.expire_all()
        row = ReportDocumentContent.query.filter_by(report_no=report.report_no).one()
        assert len(row.extra_pages) == 100
    else:
        assert response['code'] != 0
        assert '不能超过 100 页' in response['message']
