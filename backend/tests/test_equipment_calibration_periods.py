"""Real maintenance endpoints preserve explicit renewals and reject coverage gaps."""
import json
import pytest
from app.extensions import db
from app.models import EquipmentCalibrationRecord
from app.equipment_eligibility import evaluate_interval, evaluate_intervals
from app.equipment_calibration import retained_periods
from test_equipment_department_authorization import case, headers
from test_equipment_import_identity import excel
pytest_plugins = ('testkit.fixtures',)


def seed(case, end='2026-12-10'):
    e=case[5][0]; e.period='1年'; e.actual_cal_date='2025-12-11'
    e.last_cal_date='2025-12-11'; e.valid_until=e.plan_cal_date=end
    e.certificate_no='OLD'; db.session.commit(); return e


def update(case, e, **values):
    return case[0].put(f'/api/quality/equipment/{e.id}',headers=headers(case[2]),json={'editVersion':e.edit_version,**values}).get_json()


def renew(case,e,start='2026-11-12',end='2027-11-11'):
    return update(case,e,calibrationMode='renewal',actualCalDate=start,planCalDate=end,certificateNo='NEW')


def test_early_renewal_retains_complete_previous_interval(case):
    e=seed(case); assert renew(case,e)['code']==0
    db.session.expire_all()
    r=evaluate_interval(e,'2026-11-11','2026-11-11')
    assert r['selectable'] and r['evidence']['matchedPeriods'][0]['certificateNo']=='OLD'
    assert retained_periods(e)[0]['end']=='2026-12-10'
    assert evaluate_interval(e,'2026-11-01','2027-01-01')['selectable']
    record=EquipmentCalibrationRecord.query.one()
    assert record.before_data['validUntil']=='2026-12-10'
    assert record.after_data['validUntil']=='2027-11-11'
    h=case[0].get(f'/api/quality/equipment/{e.id}/history',headers=headers(case[2])).get_json()
    assert len(h['data']['validPeriods'])==2


@pytest.mark.parametrize('old_end,allowed',[('2026-11-10',False),('2026-11-11',True),('2026-11-12',True)])
def test_gap_and_inclusive_adjacent_boundaries(case,old_end,allowed):
    e=seed(case,old_end); assert renew(case,e)['code']==0
    r=evaluate_interval(e,'2026-11-01','2026-11-13')
    assert r['selectable']==allowed
    if not allowed:
        assert r['code']=='equipment.calibration_gap'
        assert r['evidence']['uncoveredFrom']==r['evidence']['uncoveredTo']=='2026-11-11'
        assert evaluate_intervals(e,[{'start':'2026-11-10','end':'2026-11-10'}, {'start':'2026-11-12','end':'2026-11-12'}])['selectable']


def test_correction_does_not_keep_wrong_current_dates_and_repeated_renewals(case):
    e=seed(case); assert renew(case,e)['code']==0
    assert update(case,e,calibrationMode='correction',planCalDate='2027-10-31')['code']==0
    assert not evaluate_interval(e,'2027-11-01','2027-11-02')['selectable']
    assert len(retained_periods(e))==1
    assert renew(case,e,'2027-10-15','2028-10-14')['code']==0
    assert len(retained_periods(e))==2
    assert evaluate_interval(e,'2026-11-01','2028-01-01')['selectable']
    assert update(case,e,keeper='新保管人')['code']==0
    assert len(retained_periods(e))==2
    assert update(case,e,calibrationMode='correction',calUnit='校准机构')['code']==0
    assert len(retained_periods(e))==2


@pytest.mark.parametrize('values',[
    dict(actualCalDate='2025-01-01',certificateNo='NEW'),
    dict(actualCalDate='2026-11-12',certificateNo=''),
    dict(actualCalDate='not-a-date',certificateNo='NEW'),
    dict(actualCalDate='2026-11-12',planCalDate='2026-10-01',certificateNo='NEW'),
])
def test_invalid_renewal_rolls_back(case,values):
    e=seed(case); response=update(case,e,calibrationMode='renewal',**values)
    assert response['code']!=0
    db.session.expire_all(); assert e.actual_cal_date=='2025-12-11'
    assert EquipmentCalibrationRecord.query.count()==0


def test_no_invented_history_and_manual_stop_still_blocks(case):
    e=seed(case); e.actual_cal_date='2026-11-12'; db.session.commit()
    assert not evaluate_interval(e,'2026-11-11','2026-11-11')['selectable']
    assert renew(case,e,'2027-01-01','2027-12-31')['code']==0
    e.status='停用'; assert not evaluate_interval(e,'2026-11-12','2026-11-12')['selectable']


def test_invalid_current_dates_do_not_crash_or_fall_back_to_history(case):
    e=seed(case); assert renew(case,e)['code']==0
    e.valid_until='2026-01-01'
    assert evaluate_interval(e,'2026-11-11','2026-11-11')['code']=='equipment.invalid_dates'


def test_picker_and_completion_use_retained_period(case):
    e=seed(case); assert renew(case,e)['code']==0
    client,user=case[:2]; report=case[6]
    response=client.get(f'/api/reports/{report.report_no}/equipment-options',headers=headers(user),query_string={'intervals':json.dumps([{'start':'2026-10-01','end':'2026-10-02'}])}).get_json()
    assert response['data']['rows'][0]['eligibility']['selectable']
    assert case[-1]([e.id])['code']==0
    from app.checks import compute_report_checks
    assert compute_report_checks(report)[0][1]['status']=='通过'


def test_batch_renewal_atomic_and_retains_periods(case):
    e=seed(case); other=case[5][1]
    payload=dict(ids=[e.id,other.id],calibrationMode='renewal',changes=dict(actualCalDate='2026-11-12',planCalDate='2027-11-11',certificateNo='NEW'))
    r=case[0].post('/api/quality/equipment/batch-update',headers=headers(case[2]),json=payload).get_json()
    assert r['code']!=0; db.session.expire_all()
    assert e.actual_cal_date=='2025-12-11' and EquipmentCalibrationRecord.query.count()==0
    payload['ids']=[e.id]
    assert case[0].post('/api/quality/equipment/batch-update',headers=headers(case[2]),json=payload).get_json()['code']==0
    assert evaluate_interval(e,'2026-11-11','2026-11-11')['selectable']


def test_import_renewal_and_default_correction(case):
    e=seed(case)
    def upload(mode,end):
        book=excel(['记录ID','档案号','仪器设备名称','实际校准日期','下次校准日期','证书编号','校准维护方式'],[[e.id,e.archive_no,e.name,'2026-11-12',end,'NEW',mode]])
        return case[0].post('/api/quality/equipment/import',headers=headers(case[2]),data={'file':(book,'equipment.xlsx')}).get_json()
    assert upload('新增一次校准','2027-11-11')['code']==0
    assert evaluate_interval(e,'2026-11-11','2026-11-11')['selectable']
    assert upload('','2027-10-31')['code']==0
    assert len(retained_periods(e))==1
    assert not evaluate_interval(e,'2027-11-01','2027-11-02')['selectable']
