from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
import pytest
from app.extensions import db
from app.models import EquipmentItem, OperationAudit
from app.blueprints.quality import _apply_equipment
from test_admin_corrections import workspace, headers
from test_equipment_import_identity import excel

pytest_plugins = ('testkit.fixtures',)


def seed():
    row = EquipmentItem(archive_no='QA-1', name='仪器', actual_cal_date='2026-01-01',
                        last_cal_date='2026-01-01', plan_cal_date='2026-12-31',
                        valid_until='2026-12-31', period='1年', certificate_no='CERT', keeper='保管人')
    db.session.add(row)
    db.session.commit()
    return row


@pytest.mark.parametrize('changes', [dict(actualCalDate='2026-02-01'), dict(lastCalDate='2026-02-01'), dict(period='2年')])
def test_start_and_end_aliases_stay_aligned(workspace, changes):
    row = seed()
    _apply_equipment(row, changes)
    assert row.actual_cal_date == row.last_cal_date
    assert row.plan_cal_date == row.valid_until
    assert row.plan_cal_date == ('2027-12-31' if 'period' in changes else '2027-01-31')


def test_single_update_rejects_old_window_and_preserves_untouched_fields(workspace):
    row = seed()
    client, actors, *_ = workspace
    first = client.put(f'/api/quality/equipment/{row.id}', headers=headers(actors[0]), json={'editVersion': 1, 'name': '新名称'})
    assert first.get_json()['data']['editVersion'] == 2
    stale = client.put(f'/api/quality/equipment/{row.id}', headers=headers(actors[0]), json={'editVersion': 1, 'keeper': '过时窗口'})
    assert stale.status_code == 409 and stale.get_json()['code'] == 409
    db.session.refresh(row)
    assert row.name == '新名称' and row.keeper == '保管人'


def test_two_orm_sessions_cannot_overwrite(workspace):
    row = seed()
    with Session(db.engine) as a, Session(db.engine) as b:
        first, second = a.get(EquipmentItem, row.id), b.get(EquipmentItem, row.id)
        first.name = 'A'
        a.commit()
        assert first.edit_version == 2
        second.name = 'B'
        with pytest.raises(StaleDataError):
            b.commit()
        b.rollback()
    db.session.refresh(row)
    assert row.name == 'A'


def upload(workspace, row, values, dry=False):
    client, actors, *_ = workspace
    return client.post('/api/quality/equipment/import', headers=headers(actors[0]), data={
        'dryRun': 'true' if dry else 'false',
        'file': (excel(['记录ID', '档案号', '仪器设备名称', '证书编号', '仪器设备管理员'], [[row.id, 'QA-1', *values]]), 'qa.xlsx'),
    }).get_json()


def test_preview_rolls_back_and_shows_explicit_clear(workspace):
    row = seed()
    result = upload(workspace, row, ['新名称', '[清空]', ''], dry=True)
    assert result['code'] == 0, result
    assert result['data']['updatedCount'] == 1
    assert 'certificateNo' in result['data']['changes'][0]['clearingFields']
    db.session.refresh(row)
    assert row.name == '仪器' and row.certificate_no == 'CERT' and row.edit_version == 1
    assert OperationAudit.query.filter_by(action='quality.equipment.import').count() == 0


def test_unchanged_and_empty_cells_do_not_write(workspace):
    row = seed()
    result = upload(workspace, row, ['仪器', '', ''])
    assert result['data']['unchangedCount'] == 1
    db.session.refresh(row)
    assert row.certificate_no == 'CERT' and row.keeper == '保管人' and row.edit_version == 1
    assert OperationAudit.query.filter_by(action='quality.equipment.import').count() == 0


@pytest.mark.parametrize('marker', ['/', '[清空]'])
def test_only_explicit_markers_clear(workspace, marker):
    row = seed()
    result = upload(workspace, row, ['仪器', marker, marker])
    assert result['code'] == 0, result
    db.session.refresh(row)
    assert row.certificate_no == row.keeper == ''


@pytest.mark.parametrize('label', ['本次校准日期', '实际校准日期', '计划校准日期'])
def test_current_and_legacy_date_headers(workspace, label):
    row = seed()
    client, actors, *_ = workspace
    result = client.post('/api/quality/equipment/import', headers=headers(actors[0]), data={'file': (
        excel(['记录ID','档案号','仪器设备名称',label,'下次校准日期'], [[row.id,'QA-1','仪器','2026/02/01','2027/01/31']]), 'qa.xlsx')}).get_json()
    assert result['code'] == 0, result
    db.session.refresh(row)
    assert row.actual_cal_date == row.last_cal_date == '2026-02-01'
    assert row.valid_until == row.plan_cal_date == '2027-01-31'


def test_period_edit_aligns_legacy_start_without_touching_unedited_ledger(workspace):
    row = seed()
    row.last_cal_date = '2025-01-01'
    _apply_equipment(row, {'keeper': '新保管人'})
    assert row.last_cal_date == '2025-01-01'
    _apply_equipment(row, {'period': '2年'})
    assert row.actual_cal_date == row.last_cal_date == '2026-01-01'


def test_preview_unchanged_legacy_aliases_does_not_realign_rows(workspace):
    row = seed()
    row.last_cal_date = '2025-01-01'
    db.session.commit()
    client, actors, *_ = workspace
    result = client.post('/api/quality/equipment/import', headers=headers(actors[0]), data={
        'file': (excel(['记录ID','档案号','仪器设备名称','本次校准日期','校准有效期至','校准周期'],
                       [[row.id,'QA-1','仪器','2026-01-01','2026-12-31','1年']]), 'qa.xlsx')}).get_json()
    assert result['data']['unchangedCount'] == 1
    db.session.refresh(row)
    assert row.last_cal_date == '2025-01-01'


def test_legacy_blank_actual_header_falls_back_to_populated_planned_date(workspace):
    row = seed()
    client, actors, *_ = workspace
    result = client.post('/api/quality/equipment/import', headers=headers(actors[0]), data={'file': (
        excel(['记录ID','档案号','仪器设备名称','实际校准日期','计划校准日期'],
              [[row.id,'QA-1','仪器','','2026-02-01']]), 'qa.xlsx')}).get_json()
    assert result['code'] == 0, result
    db.session.refresh(row)
    assert row.actual_cal_date == row.last_cal_date == '2026-02-01'
