"""UTC December 31 is already the next business year in Beijing."""
from datetime import datetime, UTC
from types import SimpleNamespace
import pytest
from flask import g
from app import workflow_dates
from app.applications.entrust import commands as entrust
from app.applications.customer_service import commands as customer
from app.blueprints import public_portal as portal

pytest_plugins = ('testkit.fixtures',)

class Allocated(Exception):
    pass

@pytest.mark.parametrize('entry', ['formal', 'accept', 'portal'])
def test_business_year_at_utc_boundary(isolated_app, monkeypatch, entry):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 12, 31, 18, tzinfo=UTC).astimezone(tz)
        @classmethod
        def utcnow(cls):
            return datetime(2026, 12, 31, 18)
    monkeypatch.setattr(workflow_dates, 'datetime', Clock)
    for module in (entrust, customer, portal):
        monkeypatch.setattr(module, 'datetime', Clock)
    seen = []
    def allocate(year):
        seen.append(year)
        raise Allocated()
    with isolated_app.test_request_context('/api/public/entrusts', method='POST', json={}):
        if entry == 'formal':
            monkeypatch.setattr(entrust, 'allocate_entrust_number', allocate)
            call = lambda: entrust.create_external_portal_entrust(None)
        elif entry == 'accept':
            app = SimpleNamespace(status='submitted', internal_entrust_id=None)
            query = SimpleNamespace(filter_by=lambda **kw: SimpleNamespace(first=lambda: app))
            monkeypatch.setattr(customer, 'ExternalEntrustApplication', SimpleNamespace(query=query))
            monkeypatch.setattr(customer, 'has_internal_process_access', lambda *a: True)
            monkeypatch.setattr(customer, 'internal_scope_allows', lambda *a: True)
            monkeypatch.setattr(customer, '_claim_submitted_application', lambda *a: True)
            monkeypatch.setattr(customer, 'reserve_customer_acceptance_number_in_transaction', allocate)
            call = lambda: customer.accept_external_application(None, 1)
        else:
            g.external_account = SimpleNamespace(id=1)
            monkeypatch.setattr(portal, '_validated_form_data', lambda body: ({}, None))
            monkeypatch.setattr(portal, '_scheme_from_body', lambda body: SimpleNamespace(id=1))
            monkeypatch.setattr(portal, '_canonical_selected_test_items', lambda *a: ({}, None))
            monkeypatch.setattr(portal, '_quote_for', lambda *a: {})
            monkeypatch.setattr(portal, 'allocate_external_application_number', allocate)
            call = portal.create_external_entrust.__wrapped__
        with pytest.raises(Allocated): call()
    assert seen == [2027]
