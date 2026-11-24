"""Explicit calibration renewals, separate from unverified legacy edit snapshots."""
from datetime import date
from .models import EquipmentCalibrationRecord

FIELDS = {'actualCalDate', 'lastCalDate', 'planCalDate', 'validUntil', 'period', 'calUnit', 'certificateNo'}
MARKER = '_retainedCalibrationPeriodsV1'


def period(row):
    start = str(row.get('actualCalDate') or row.get('lastCalDate') or '')[:10]
    end = str(row.get('validUntil') or row.get('planCalDate') or '')[:10]
    try:
        if date.fromisoformat(start) > date.fromisoformat(end):
            return None
    except ValueError:
        return None
    return dict(start=start, end=end, certificateNo=row.get('certificateNo') or '',
                calUnit=row.get('calUnit') or '')


def retained_periods(equipment):
    if not equipment.id:
        return []
    record = EquipmentCalibrationRecord.query.filter_by(equipment_id=equipment.id).order_by(
        EquipmentCalibrationRecord.id.desc()).first()
    # Legacy partial snapshots are audit evidence, not confirmed calibration periods.
    return list((record.after_data or {}).get(MARKER) or []) if record else []


def maintenance_snapshot(equipment, before, after, mode):
    saved = retained_periods(equipment)
    if mode == 'renewal':
        previous, current = period(before), period(after)
        if not previous or not current:
            raise ValueError('新增校准前，请补齐并核对上一期和本期的校准日期、有效期至')
        if current['start'] <= previous['start']:
            raise ValueError('新增校准日期必须晚于上一期；录错日期请选择纠正本期信息')
        if not current['certificateNo']:
            raise ValueError('新增校准请填写证书编号，并确认本期校准符合使用要求')
        saved.append(previous)
    elif mode != 'correction':
        raise ValueError('请选择校准维护方式：新增一次校准或纠正本期信息')
    return saved


def backfill_period(equipment, payload):
    """Explicitly attested historical evidence; never rewrite the current ledger."""
    if not isinstance(payload, dict) or payload.get('confirmed') is not True:
        raise ValueError('请核对历史校准凭证并确认该期间符合使用要求')
    values = {}
    for key, limit in [('start', 10), ('end', 10), ('certificateNo', 160), ('calUnit', 200), ('reason', 300)]:
        value = payload.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise ValueError('历史校准日期或凭证信息格式无效')
        values[key] = value.strip()
    try:
        start, end = date.fromisoformat(values['start']), date.fromisoformat(values['end'])
        if start.isoformat() != values['start'] or end.isoformat() != values['end'] or start > end:
            raise ValueError()
    except ValueError:
        raise ValueError('请填写有效的历史校准起止日期，结束日期不得早于开始日期') from None
    current = period(equipment.to_row(full=True))
    if not current or values['start'] >= current['start']:
        raise ValueError('请先核对当前校准日期；历史校准开始日期必须早于当前期')
    if not values['certificateNo'] or len(values['reason']) < 2:
        raise ValueError('请填写历史证书编号和补录依据（2至300字）')
    saved = retained_periods(equipment)
    if any(p['start'] == values['start'] for p in saved):
        raise ValueError('该开始日期的校准记录已存在，请核对维护记录，勿重复补录')
    return saved + [values]
