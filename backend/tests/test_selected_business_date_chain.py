"""Chosen business dates outrank later operation timestamps across the chain."""
from datetime import date, datetime
from types import SimpleNamespace as NS

import pytest
from app.blueprints import entrust, reports
from app.applications.testing_records import commands as testing
from app.extensions import db
from app.models import OperationAudit
from app.report_date_policy import report_date_error
from test_pickup_inbound_business_date import received, pickup

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('module', [entrust, reports], ids=['entrust-list', 'sample-validation'])
def test_selected_entrust_date_does_not_consult_operation_timestamps(monkeypatch, module):
    def unexpected(*args):
        pytest.fail('A chosen business date must not be replaced by the audit date')
    monkeypatch.setattr(module, 'latest_workflow_date', unexpected)
    row = NS(entrust_no='QA', info={'entrustDate': '2026-10-20'}, created_at=datetime(2026, 10, 27))
    assert module._entrust_completed_date(row) == date(2026, 10, 20)


@pytest.mark.parametrize('module', [entrust, reports], ids=['entrust-list', 'sample-validation'])
def test_missing_business_date_does_not_become_operation_date(monkeypatch, module):
    monkeypatch.setattr(module, 'latest_workflow_date', lambda *args: date(2026, 10, 26))
    row = NS(entrust_no='QA', info={}, created_at=datetime(2026, 10, 25))
    assert module._entrust_completed_date(row) is None


@pytest.mark.parametrize('validator', ['desktop', 'testing-command'])
def test_late_recording_does_not_shift_pickup_or_testing_dates(received, validator):
    _, _, report, inbound_event, user = received
    assert pickup(received, '2026-10-22')['code'] == 0
    event = OperationAudit.query.filter_by(object_id=report.report_no, action='sample.out_warehouse.sign').one()
    event.created_at = datetime(2026, 10, 28, 2)
    db.session.commit()
    if validator == 'desktop':
        check = lambda start, end: reports._validated_test_dates(user, report, start, end)[2]
    else:
        check = lambda start, end: testing._test_date_error(user, report, start, end)
    assert not check('2026-10-22', '2026-10-23')
    assert '不得早于' in check('2026-10-21', '2026-10-23')
    assert '不得早于' in check('2026-10-23', '2026-10-22')
    report.detail = {**report.detail, 'checkInput': {'testStartDate': '2026-10-22', 'testDate': '2026-10-23'}}
    db.session.commit()
    assert report_date_error(report, 'review', '2026-10-24') is None
    assert '不得早于' in report_date_error(report, 'review', '2026-10-22')
    assert inbound_event.created_at == datetime(2026, 10, 27, 2)
    assert event.created_at == datetime(2026, 10, 28, 2)
