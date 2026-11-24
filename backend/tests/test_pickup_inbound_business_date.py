"""Exercise ordinary-user HTTP pickup after a backdated business receipt."""
from copy import deepcopy
from datetime import datetime

import pytest
from app.extensions import db
from app.models import Entrust, OperationAudit, Report
from app.security import issue_token
from app.platform.audit import add_operation_audit

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture
def received(isolated_client, scenario_factory):
    s = scenario_factory.identity_scenario(
        permission_codes=('sample.inbound.view', 'sample.outbound.view'),
        granted_step_codes=('sample_inbound', 'sample_outbound'))
    for code in ('sample.inbound.confirm', 'sample.out_warehouse.sign'):
        scenario_factory.grant_action(s.user, code)
    entrust = Entrust(entrust_no='PICKUP-DATE-WT', department=s.department.name,
        owner=s.user.name, info={'entrustDate': '2026-10-20'})
    report = Report(report_no='PICKUP-DATE-QA', sample_no='PICKUP-QA', entrust_no=entrust.entrust_no,
        department=s.department.name, owner=s.user.name, project=s.project.name,
        status='待样品入库', sample_status='待入库',
        detail={'rawSample': {'sendDate': '2026-10-21'}})
    db.session.add_all([entrust, report]); db.session.commit()
    headers = {'Authorization': 'Bearer ' + issue_token(s.user)}
    result = isolated_client.post(f'/api/samples/{report.report_no}/inbound',
        headers=headers, json={'inboundDate': '2026-10-22'}).get_json()
    assert result['code'] == 0, result
    event = OperationAudit.query.filter_by(object_id=report.report_no, action='sample.inbound.confirm').one()
    event.created_at = datetime(2026, 10, 27, 2)
    db.session.commit()
    return isolated_client, headers, report, event, s.user


def pickup(case, day):
    client, headers, report, _, user = case
    return client.post(f'/api/samples/{report.report_no}/pickup', headers=headers, json={
        'action': 'sign', 'managerId': user.account, 'managerName': user.name,
        'receiverName': user.name, 'outTime': day, 'pickupTime': day}).get_json()


@pytest.mark.parametrize('day', ['2026-10-22', '2026-10-23'])
def test_past_business_receipt_allows_same_or_later_pickup_without_override(received, day):
    _, _, report, event, _ = received
    result = pickup(received, day)
    assert result['code'] == 0, result
    db.session.expire_all()
    assert report.sample_status == '已领取'
    assert report.detail['workflowDates']['sampleInboundAt'] == '2026-10-22'
    assert report.detail['workflowDates']['samplePickupAt'] == day
    assert event.created_at == datetime(2026, 10, 27, 2)


def test_before_business_receipt_rejected_without_state_or_audit_changes(received):
    _, _, report, _, _ = received
    before = deepcopy(report.detail)
    result = pickup(received, '2026-10-21')
    assert result['code'] != 0 and '2026-10-22' in result['message'], result
    db.session.expire_all()
    assert report.detail == before and report.sample_status == '已入库'
    assert OperationAudit.query.filter_by(object_id=report.report_no, action='sample.out_warehouse.sign').count() == 0


@pytest.mark.parametrize('mobile', [False, True])
def test_missing_business_snapshot_requires_evidence_recovery(received, mobile):
    _, _, report, event, _ = received
    report.detail = {**report.detail, 'workflowDates': {}}
    if mobile: event.action = 'sample.mobile.inbound.confirm'
    db.session.commit()
    result = pickup(received, '2026-10-26')
    assert result['code'] != 0 and '原入库业务日期' in result['message'], result
    assert pickup(received, '2026-10-27')['code'] != 0


@pytest.mark.parametrize('snapshot', [True, False])
def test_old_return_does_not_rewrite_original_business_boundary(received, snapshot):
    _, _, report, _, user = received
    flow = dict(report.detail['workflowDates'])
    if snapshot:
        flow.update(sampleReturnedAt='2026-10-25', sampleAvailableAt='2026-10-25')
    report.detail = {**report.detail, 'workflowDates': flow}
    add_operation_audit('sample.return_stock', 'report', report.report_no, category='workflow', actor=user)
    db.session.flush()
    event = OperationAudit.query.filter_by(object_id=report.report_no, action='sample.return_stock').one()
    event.created_at = datetime(2026, 10, 27, 2)
    db.session.commit()
    assert pickup(received, '2026-10-22')['code'] == 0


def test_pre_testing_undo_pickup_keeps_original_dates_and_allows_pickup_again(received, scenario_factory):
    client, headers, report, _, user = received
    scenario_factory.grant_action(user, 'sample.return_stock')
    db.session.commit()
    assert pickup(received, '2026-10-22')['code'] == 0
    before = deepcopy(report.detail['workflowDates'])
    result = client.post(f'/api/samples/{report.report_no}/return-stock', headers=headers, json={}).get_json()
    assert result['code'] == 0, result
    db.session.refresh(report)
    assert report.status == '待样品领取' and report.sample_status == '已入库'
    assert report.detail['workflowDates'] == before
    assert report.sample_pickup['pickupTime'] == '2026-10-22'
    assert report.sample_pickup['signed'] is False
    assert pickup(received, '2026-10-22')['code'] == 0
