"""User-approved first batch: legacy mirrors must not prevent normal saves."""
from copy import deepcopy
from datetime import date

import pytest

from app.extensions import db
from app.models import OperationAudit
from app.production_dates import normalize_rows
from app.report_date_policy import sample_date_values, synchronize_sample_date_summary
from app.edit_concurrency import test_form_version as form_version
from test_pickup_inbound_business_date import received
from test_equipment_department_authorization import case, headers

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('value,precision', [
    ('2026-10-21', 'day'), ('2026-10', 'month'), ('未标注', 'custom'), ('', 'custom'),
])
@pytest.mark.parametrize('explicit', [False, True])
def test_missing_production_precision_is_inferred(value, precision, explicit):
    row = {'name': '室内机', 'value': value}
    if explicit:
        row['precision'] = ''
    assert normalize_rows([row])[0]['precision'] == precision


@pytest.mark.parametrize('row', [
    {'value': '2026-02-30'}, {'value': '2026-13'},
    {'value': '2026-10', 'precision': 'day'}, {'value': '', 'precision': 'bad'},
])
def test_invalid_or_conflicting_precision_remains_blocked(row):
    with pytest.raises(ValueError):
        normalize_rows([row])


@pytest.mark.parametrize('value,expected', [('2026-10-22', date(2026, 10, 22)), ('', None)])
def test_form_date_wins_over_summary_including_explicit_clear(value, expected):
    source = {'rawSample': {'sendDate': value}, 'summary': [
        {'title': '送样信息', 'fields': [['送样日期', '2026-10-25'], ['备注', '保留']]}]}
    before = deepcopy(source)
    assert sample_date_values(source, None)['send'] == expected
    updated = synchronize_sample_date_summary(source)
    assert updated['summary'][0]['fields'] == [['送样日期', value or '—'], ['备注', '保留']]
    assert source == before


def test_summary_only_legacy_date_is_preserved():
    source = {'summary': [{'fields': [['送样日期', '2026-10-22']]}]}
    assert sample_date_values(source, None)['send'] == date(2026, 10, 22)
    assert synchronize_sample_date_summary(source) == source


def test_draft_record_change_audit_does_not_claim_automatic_alignment(case):
    from app.applications.testing_records.commands import save_test_draft
    _, user, _, _, _, _, report, *_ = case
    report.detail = {'checkInput': {'standardRecords': [{'id': 1}]}}
    db.session.commit()
    result = save_test_draft(user, report.report_no,
                            detail={'checkInput': {'standardRecords': [{'id': 2}]}})
    assert result.code == 0, result.message
    audit = OperationAudit.query.filter_by(object_id=report.report_no,
                                          action='report.standard_records.update').one()
    assert audit.before_data['standardRecords'] == [{'id': 1}]
    assert audit.after_data['standardRecords'] == [{'id': 2}]
    assert '按登记标准' not in audit.message


def test_retired_mobile_pickup_channel_is_rejected(received):
    # Batch-3 Q10 (2026-11-07): no mobile client; only the desktop channel remains.
    from app.applications.sample_logistics.commands import execute_sample_pickup
    _, _, report, _, user = received
    before = (report.status, report.sample_status, dict(report.detail or {}))
    result = execute_sample_pickup(user, report.report_no, channel='mobile')
    assert result.code == 1 and '来源无效' in result.message
    db.session.refresh(report)
    assert (report.status, report.sample_status, dict(report.detail or {})) == before


@pytest.mark.parametrize('out,pickup', [('', '2026-10-23'), ('2026-10-23', ''),
                                      ('2026-10-24', '2026-10-23')])
def test_single_pickup_date_and_conflicting_legacy_values_are_audited(received, out, pickup):
    client, auth, report, _, user = received
    result = client.post(f'/api/samples/{report.report_no}/pickup', headers=auth, json={
        'action': 'sign', 'managerName': user.name, 'receiverName': user.name,
        'outTime': out, 'pickupTime': pickup}).get_json()
    assert result['code'] == 0, result
    db.session.refresh(report)
    assert report.sample_pickup['outTime'] == report.sample_pickup['pickupTime'] == '2026-10-23'
    assert report.detail['workflowDates']['samplePickupAt'] == '2026-10-23'
    audit = OperationAudit.query.filter_by(object_id=report.report_no, action='sample.out_warehouse.sign').one()
    assert '自动对齐' in audit.message and '2026-10-23' in audit.message


@pytest.mark.parametrize('complete', [False, True])
def test_standard_mismatch_saves_draft_with_notice_but_blocks_completion(case, complete):
    client, user, _, _, _, _, report, *_ = case
    report.detail = {'rawSample': {'testBases': ['GB/T TEST-2026'], 'sendDate': '2026-09-20'},
                     'summary': [{'title': '送样信息', 'fields': [['送样日期', '2026-09-25']]}]}
    db.session.commit()
    response = client.put(f'/api/reports/{report.report_no}/testinfo', headers=headers(user), json={
        'testEditVersion': form_version(report), 'standards': ['OTHER-2026'],
        'validateForCompletion': complete}).get_json()
    if complete:
        assert response['code'] != 0 and '委托更改' in response['message'], response
        assert 'checkInput' not in report.detail
    else:
        assert response['code'] == 0, response
        assert response['data']['notice'] == '已按样品单标准更新'
        db.session.refresh(report)
        assert report.detail['checkInput']['standards'] == ['GB/T TEST-2026']
        assert report.detail['summary'][0]['fields'][0][1] == '2026-09-20'
        audit = OperationAudit.query.filter_by(object_id=report.report_no, action='report.data_entry.save').one()
        assert 'OTHER-2026' in audit.message and 'GB/T TEST-2026' in audit.message
        alignment = OperationAudit.query.filter_by(object_id=report.report_no, action='report.date_summary.align').one()
        assert alignment.account == user.account
        assert alignment.before_data['summary'][0]['fields'][0][1] == '2026-09-25'
        assert alignment.after_data['summary'][0]['fields'][0][1] == '2026-09-20'
