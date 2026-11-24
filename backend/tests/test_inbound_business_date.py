"""Selectable inbound dates use the same strict chain and actual API as receipt."""
from copy import deepcopy
from datetime import date

import pytest

from app.extensions import db
from app.models import Entrust, Report, OperationAudit
from app.security import issue_token
from app.report_date_policy import report_date_error
from app.applications.sample_logistics.commands import execute_sample_inbound

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture
def case(isolated_client, scenario_factory):
    s = scenario_factory.identity_scenario(permission_codes=('sample.inbound.view',), granted_step_codes=('sample_inbound',))
    scenario_factory.grant_action(s.user, 'sample.inbound.confirm')
    e = Entrust(entrust_no='DATE-ENTRUST', department=s.department.name, owner=s.user.name, info={'entrustDate':'2026-10-10'})
    r = Report(report_no='DATE-REPORT', sample_no='DATE-SAMPLE', entrust_no=e.entrust_no,
               department=s.department.name, owner=s.user.name, project=s.project.name,
               status='待样品入库', sample_status='待入库',
               detail={'rawSample':{'produceDate':'2026-10-01','sampleTime':'2026-10-08','sendDate':'2026-10-12'}})
    db.session.add_all([e,r]); db.session.commit()
    return isolated_client, s.user, r, e


def receive(case, payload):
    client,user,r,_=case
    return client.post(f'/api/samples/{r.report_no}/inbound', json=payload,
                       headers={'Authorization':'Bearer '+issue_token(user)}).get_json()


@pytest.mark.parametrize('chosen', ['2026-10-12','2026-10-15'])
def test_selected_date_persists_and_controls_downstream(case, chosen):
    _,_,r,_=case
    result=receive(case, {'inboundDate':chosen})
    assert result['code']==0, result
    db.session.expire_all()
    assert r.detail['workflowDates']['sampleInboundAt']==chosen
    assert r.detail['workflowDates']['sampleAvailableAt']==chosen
    assert r.sample_status=='已入库'
    assert '不得早于' in report_date_error(r,'pickup','2026-10-11')
    if chosen == '2026-10-15':
        assert '不得早于入库日期' in report_date_error(r,'pickup','2026-10-14')
    assert report_date_error(r,'pickup',chosen) is None
    event=OperationAudit.query.filter_by(object_id=r.report_no,action='sample.inbound.confirm').one()
    assert event.created_at is not None
    # Completed receipt cannot be used as an edit endpoint.
    assert receive(case, {'inboundDate':'2026-10-16'})['code']!=0
    assert r.detail['workflowDates']['sampleInboundAt']==chosen


@pytest.mark.parametrize('value', ['2026-10-11','','2026-02-30','2026-10-12junk',None,123])
def test_rejection_does_not_mutate_report_or_audit(case, value):
    _,_,r,_=case
    before=deepcopy(r.detail)
    result=receive(case, {'inboundDate':value})
    assert result['code']!=0, result
    db.session.expire_all()
    assert r.sample_status=='待入库' and r.detail==before
    assert OperationAudit.query.filter_by(object_id=r.report_no,action='sample.inbound.confirm').count()==0


def test_contract_independent_chain_still_requires_entrust_before_inbound(case):
    _,_,r,e=case
    e.info={'entrustDate':'2026-10-14'};db.session.commit()
    result=receive(case, {'inboundDate':'2026-10-12'})
    assert '不得早于委托日期' in result['message']


def test_administrator_cannot_bypass_delivery_boundary(case):
    _,user,_,_=case
    user.role_key='admin';db.session.commit()
    result=receive(case, {'inboundDate':'2026-10-11'})
    assert '不得早于送样日期' in result['message']


def test_legacy_request_without_date_defaults_to_today(case, monkeypatch):
    from app.applications.sample_logistics import commands
    monkeypatch.setattr(commands,'business_today',lambda:date(2026,10,20))
    assert receive(case,{})['code']==0
    assert case[2].detail['workflowDates']['sampleInboundAt']=='2026-10-20'


def test_retired_mobile_inbound_channel_is_rejected(case):
    # Batch-3 Q10 (2026-11-07): mobile OCR inbound was removed with the mobile code.
    _,user,r,_=case
    result=execute_sample_inbound(user,r.report_no,channel='mobile')
    assert result.code==1 and '来源无效' in result.message
    assert r.sample_status=='待入库'
    assert 'mobileSampleFlow' not in (r.detail or {})


def test_permission_still_required(case, scenario_factory):
    client,_,r,_=case
    user=scenario_factory.user(scenario_factory.department())
    db.session.commit()
    result=client.post(f'/api/samples/{r.report_no}/inbound',json={'inboundDate':'2026-10-15'},headers={'Authorization':'Bearer '+issue_token(user)}).get_json()
    assert result['code']==403
    assert r.sample_status=='待入库'
