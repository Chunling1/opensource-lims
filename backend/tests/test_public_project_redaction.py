"""Per-report display masking must not alter signed or editable report data."""
from copy import deepcopy

import pytest

from app.extensions import db
from test_report_publication import make_report, sign, lookup, new_token, ORIGIN

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('selected', [True, False])
def test_redaction_applies_to_both_public_routes_only(isolated_app, selected):
    with isolated_app.app_context():
        number = 'TEST-REDACTION-001'
        isolated_app.config['REPORT_QUERY_REDACT_PROJECT_NAMES'] = {number if selected else number + '-OTHER'}
        report, row, version = make_report(number)
        snap = deepcopy(version.snapshot)
        snap['report']['detail']['rawSample']['projectName'] = 'Frozen project name'
        version.snapshot = snap
        db.session.commit()
        flow = sign(report, version, sealed=True)
        before_snapshot, before_detail = deepcopy(version.snapshot), deepcopy(report.detail)
        before_hash = flow.signed_sha256
        client = isolated_app.test_client()
        qr = lookup(client, new_token(report))
        numbered = client.get('/api/public/v1/reports/query', query_string={'reportNo': number}, base_url=ORIGIN)
        assert qr.status_code == numbered.status_code == 200
        expected = '/' if selected else 'Frozen project name'
        assert qr.json['data']['facts']['projectName'] == expected
        assert numbered.json['data']['projectName'] == expected
        assert qr.json['data']['facts']['client'] == '冻结客户'
        assert qr.json['data']['downloadAllowed'] is False
        db.session.expire_all()
        assert version.snapshot == before_snapshot
        assert report.detail == before_detail
        assert flow.signed_sha256 == before_hash


def test_no_premature_facts_for_unissued_report(isolated_app):
    with isolated_app.app_context():
        report, _, _ = make_report('TEST-REDACTION-UNISSUED')
        isolated_app.config['REPORT_QUERY_REDACT_PROJECT_NAMES'] = {report.report_no}
        response = lookup(isolated_app.test_client(), new_token(report))
        assert response.json['data']['facts'] == {}
