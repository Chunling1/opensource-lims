"""One instrument verdict for selection, completion and compliance review."""
from datetime import date, timedelta


def _date(value):
    try:
        return date.fromisoformat(str(value or '')[:10])
    except ValueError:
        return None


def _result(level, code, message, **evidence):
    return dict(level=level, code=code, message=message,
                selectable=level != 'block', evidence=evidence)


def evaluate_interval(equipment, start=None, end=None, *, selecting=False):
    if equipment.deleted_at is not None:
        return _result('block', 'equipment.deleted', '不存在或已删除')
    if equipment.manual_status() != '可用':
        return _result('block', 'equipment.unavailable', equipment.status or '停用/报废')
    start, end = _date(start), _date(end)
    # Current ledger and explicitly retained renewals; never infer legacy snapshots.
    ledger = equipment.to_row()
    long_term = any(word in str(ledger.get('period') or '') for word in ('长期', '永久', '不定期'))
    first = _date(ledger.get('actualCalDate') or ledger.get('lastCalDate'))
    last = _date(ledger.get('validUntil') or ledger.get('planCalDate'))
    evidence = dict(calibrationDate=first.isoformat() if first else '', validUntil=last.isoformat() if last else '')
    if not long_term and (not first or not last):
        return _result('block', 'equipment.missing_dates', '校准日期或有效期未登记完整，请设备管理员补齐台账', **evidence)
    if not long_term and first > last:
        return _result('block', 'equipment.invalid_dates', '校准有效期至早于校准日期，请设备管理员核对', **evidence)
    if not start or not end:
        return _result('notice' if selecting else 'block', 'equipment.interval_pending', '填写区间后判断', **evidence)
    if end < start:
        return _result('block', 'equipment.interval_invalid', '试验区间结束日期不得早于开始日期')
    if not long_term and (first > start or last < end):
        from .equipment_calibration import retained_periods, period
        periods = retained_periods(equipment)
        if periods:
            periods = sorted(periods + [period(ledger)], key=lambda p: p['start'])
            cursor, used = start, []
            for p in periods:
                begin, finish = _date(p['start']), _date(p['end'])
                if finish < cursor:
                    continue
                if begin > cursor:
                    break
                used.append(p)
                if finish >= end:
                    labels = '；'.join(f"{v['start']}至{v['end']}（证书{v['certificateNo'] or '未登记'}）" for v in used)
                    return _result('notice', 'equipment.covered', '历次校准覆盖试验区间：' + labels,
                                   **evidence, matchedPeriods=used)
                cursor = finish + timedelta(days=1)
            next_start = next((_date(p['start']) for p in periods if _date(p['start']) > cursor), None)
            gap_end = min(end, next_start - timedelta(days=1)) if next_start else end
            return _result('block', 'equipment.calibration_gap',
                           f'无有效校准覆盖：{cursor.isoformat()}至{gap_end.isoformat()}，请核对校准记录',
                           **evidence, uncoveredFrom=cursor.isoformat(), uncoveredTo=gap_end.isoformat())
    if not long_term and first > start:
        return _result('block', 'equipment.calibration_after_test', '校准开始日晚于试验开始', **evidence)
    if not long_term and last < end:
        return _result('block', 'equipment.expired', '校准有效期不足，未覆盖试验区间', **evidence)
    return _result('notice', 'equipment.covered', '长期有效' if long_term else '覆盖试验区间', **evidence)


def evaluate_intervals(equipment, intervals, *, selecting=False):
    results = [evaluate_interval(equipment, part.get('start'), part.get('end'), selecting=selecting)
               for part in (intervals or [{}])]
    return next((r for r in results if r['level'] == 'block'),
                next((r for r in results if r['code'] == 'equipment.interval_pending'), results[0]))
