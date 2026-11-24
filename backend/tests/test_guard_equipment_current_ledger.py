from datetime import date, datetime
import pytest
from app.extensions import db
from app.models import EquipmentCalibrationRecord
from app.equipment_eligibility import evaluate_interval
from test_equipment_department_authorization import case
pytest_plugins=('testkit.fixtures',)


def test_history_never_replaces_current_calibration(case):
    equipment=case[5][0]
    equipment.period='12个月';equipment.actual_cal_date='2026-10-01';equipment.valid_until='2027-10-01'
    db.session.add(EquipmentCalibrationRecord(equipment_id=equipment.id, changed_at=datetime(2026,10,1),
        changed_fields=['actualCalDate','validUntil'],before_data={'actualCalDate':'2025-10-01','validUntil':'2026-10-01'},
        after_data={'actualCalDate':'2026-10-01','validUntil':'2027-10-01'}))
    db.session.add(EquipmentCalibrationRecord(equipment_id=equipment.id, changed_at=datetime(2026,10,2),
        changed_fields=['keeper'],before_data={'keeper':'old'},after_data={'keeper':'new'}))
    db.session.flush()
    result=evaluate_interval(equipment,'2026-09-01','2026-09-30')
    assert not result['selectable'] and result['evidence']['calibrationDate']=='2026-10-01'
    assert not evaluate_interval(equipment,'2026-09-01','2026-10-02')['selectable']
    assert equipment.test_interval_error(date(2026,9,1),date(2026,9,30))=='校准开始日晚于试验开始'
    assert evaluate_interval(equipment,'2026-10-01','2026-10-02')['selectable']


def test_missing_dates_still_block_and_incomplete_interval_can_be_selected(case):
    equipment=case[5][0];equipment.period='12个月'
    assert evaluate_interval(equipment,selecting=True)['code']=='equipment.missing_dates'
    equipment.actual_cal_date='2026-01-01';equipment.valid_until='2026-12-31'
    assert evaluate_interval(equipment,selecting=True)['selectable']
    assert not evaluate_interval(equipment)['selectable']
    equipment.status='维修'
    assert not evaluate_interval(equipment,selecting=True)['selectable']


def test_picker_uses_same_current_verdict(case):
    client,user,admin,own,other,rows,report,url,grant,options,save=case
    from test_equipment_department_authorization import headers
    response=client.get(f'/api/reports/{report.report_no}/equipment-options',headers=headers(user),
        query_string={'intervals':'[{"start":"2026-10-01","end":"2026-10-02"}]'}).get_json()
    assert response['code']==0,response
    assert response['data']['rows'][0]['eligibility']['selectable']


def test_trial_before_first_calibration_uses_known_dates_not_empty_creation(case):
    equipment = case[5][0]
    equipment.period = '12个月'
    equipment.actual_cal_date = '2026-10-01'
    equipment.valid_until = '2027-10-01'
    db.session.add(EquipmentCalibrationRecord(
        equipment_id=equipment.id, changed_at=datetime(2026, 10, 1),
        changed_fields=['actualCalDate', 'validUntil'],
        before_data={'actualCalDate': '', 'lastCalDate': '', 'validUntil': ''},
        after_data={'actualCalDate': '2026-10-01', 'validUntil': '2027-10-01'}))
    db.session.flush()
    result = evaluate_interval(equipment, '2026-09-01', '2026-09-30')
    assert not result['selectable']
    assert result['code'] == 'equipment.calibration_after_test'
    assert result['message'] == '校准开始日晚于试验开始'
    assert result['evidence']['calibrationDate'] == '2026-10-01'


def test_history_without_any_calibration_still_reports_missing_dates(case):
    equipment = case[5][0]
    equipment.period = '12个月'
    equipment.actual_cal_date = equipment.last_cal_date = ''
    db.session.add(EquipmentCalibrationRecord(
        equipment_id=equipment.id, changed_at=datetime(2026, 10, 1),
        changed_fields=['keeper'], before_data={'keeper': 'old'}, after_data={'keeper': 'new'}))
    db.session.flush()
    result = evaluate_interval(equipment, '2026-09-01', '2026-09-30')
    assert not result['selectable']
    assert result['code'] == 'equipment.missing_dates'


@pytest.mark.parametrize('period', ['长期', '永久', '不定期'])
def test_long_term_current_ledger_ignores_expired_history(case, period):
    equipment = case[5][0]
    equipment.period = period
    equipment.actual_cal_date = equipment.last_cal_date = ''
    equipment.valid_until = equipment.plan_cal_date = ''
    history = EquipmentCalibrationRecord(equipment_id=equipment.id,
        changed_fields=['period', 'actualCalDate', 'validUntil'],
        before_data={'period': '1年', 'actualCalDate': '2024-01-01', 'validUntil': '2024-12-31'},
        after_data={'period': period, 'actualCalDate': '', 'validUntil': ''})
    db.session.add(history); db.session.flush()
    assert evaluate_interval(equipment, '2026-11-01', '2026-11-02')['code'] == 'equipment.covered'
    assert evaluate_interval(equipment, selecting=True)['selectable']
    from app.checks import compute_report_checks
    report = case[6]
    report.detail = {'checkInput': {'equipmentIds': [equipment.id],
        'testIntervals': [{'start': '2026-11-01', 'end': '2026-11-02'}]}}
    assert compute_report_checks(report)[0][1]['status'] == '通过'
    assert history.before_data['period'] == '1年'  # Audit remains intact.
    equipment.status = '停用'
    assert not evaluate_interval(equipment, '2026-11-01', '2026-11-02')['selectable']


def test_current_update_is_immediately_used_and_covered_current_needs_no_history(case):
    from sqlalchemy import event
    equipment = case[5][0]
    equipment.period = '1年'; equipment.actual_cal_date = '2026-01-01'
    equipment.valid_until = '2026-11-01'
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())
    event.listen(db.engine, 'before_cursor_execute', capture)
    try:
        assert evaluate_interval(equipment, '2026-11-02', '2026-11-03')['code'] == 'equipment.expired'
        statements.clear()  # Missing current coverage may consult confirmed renewals.
        equipment.valid_until = '2027-01-01'
        assert evaluate_interval(equipment, '2026-11-02', '2026-11-03')['selectable']
    finally:
        event.remove(db.engine, 'before_cursor_execute', capture)
    assert not any('equipment_calibration_records' in sql for sql in statements)


@pytest.mark.parametrize('stage', ['report_review', 'report_approval'])
def test_compliance_names_invalid_equipment_and_reason(case, stage):
    from app.compliance import build_compliance_preflight
    equipment, report = case[5][0], case[6]
    equipment.archive_no = 'QA-TR227'; equipment.name = '虚拟仪器'
    equipment.period = '1年'; equipment.actual_cal_date = '2026-01-01'
    equipment.valid_until = '2026-10-01'
    report.detail = {'checkInput': {'equipmentIds': [equipment.id],
        'testIntervals': [{'start': '2026-11-01', 'end': '2026-11-02'}]}}
    result = build_compliance_preflight(report, stage)
    issue = next(row for row in result['issues'] if row['category'] == 'instrument_validity')
    assert 'QA-TR227' in issue['message'] and '虚拟仪器' in issue['message']
    assert '校准有效期不足' in issue['message'] and issue['hardBlocker']
