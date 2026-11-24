import pytest
from app.extensions import db
from app.models import EquipmentCalibrationRecord, OperationAudit
from app.equipment_eligibility import evaluate_interval
from app.equipment_calibration import retained_periods
from test_equipment_department_authorization import case, headers
from test_equipment_calibration_periods import seed, renew, update
pytest_plugins=('testkit.fixtures',)


def backfill(case,e,actor=None,**extra):
    body=dict(start='2024-12-11',end='2025-12-10',certificateNo='OLDER',calUnit='原机构',reason='核对旧证书',confirmed=True)
    body.update(extra)
    return case[0].post(f'/api/quality/equipment/{e.id}/calibration-history',headers=headers(actor or case[2]),json=body).get_json()


def test_backfill_keeps_current_and_survives_correction_and_renewal(case):
    e=seed(case); before=e.to_row(full=True)
    assert backfill(case,e)['code']==0
    db.session.expire_all();assert e.to_row(full=True)==before
    assert evaluate_interval(e,'2025-01-01','2026-01-01')['selectable']
    record=EquipmentCalibrationRecord.query.one();assert record.changed_by_account==case[2].account
    assert record.after_data['backfillReason']=='核对旧证书'
    assert OperationAudit.query.filter_by(action='quality.equipment.calibration.backfill').count()==1
    assert update(case,e,calUnit='新机构')['code']==0
    assert renew(case,e)['code']==0
    assert len(retained_periods(e))==2
    assert evaluate_interval(e,'2025-01-01','2027-01-01')['selectable']


def test_backfilled_gap_and_manual_stop_remain_blocked(case):
    e=seed(case); assert backfill(case,e,end='2025-12-09')['code']==0
    r=evaluate_interval(e,'2025-12-09','2025-12-12')
    assert not r['selectable'] and r['evidence']['uncoveredFrom']=='2025-12-10'
    e.status='停用';assert not evaluate_interval(e,'2025-01-01','2025-01-02')['selectable']


@pytest.mark.parametrize('extra',[{'confirmed':False},{'reason':''},{'certificateNo':''},{'start':'2025-12-11'},{'start':'2025-02-30'},{'end':'2024-01-01'},{'start':'2024-12-11abc'},{'certificateNo':123}])
def test_invalid_backfill_no_mutation(case,extra):
    e=seed(case);before=e.to_row(full=True)
    assert backfill(case,e,**extra)['code']!=0
    db.session.expire_all();assert e.to_row(full=True)==before
    assert EquipmentCalibrationRecord.query.count()==0


def test_duplicate_and_unauthorized_cannot_add_period(case):
    e=seed(case)
    assert backfill(case,e,actor=case[1])['code']!=0
    assert EquipmentCalibrationRecord.query.count()==0
    assert backfill(case,e)['code']==0
    assert backfill(case,e)['code']!=0
    assert backfill(case,e,end='2026-01-01',certificateNo='OTHER')['code']!=0
    assert EquipmentCalibrationRecord.query.count()==1
