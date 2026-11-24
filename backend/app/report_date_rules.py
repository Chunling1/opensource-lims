"""Inclusive business-date ordering. No persistence, defaults or permissions.

Sampling and entrust dates deliberately have no edge between them. Missing
optional milestones are skipped without losing transitive ordering. Existing
workflow entrypoints remain responsible for required fields and state grants.
"""
from datetime import date, datetime
import re


def production_date_marker(value):
    text = str(value or '').strip()
    return bool(text) and not re.match(r'^\d{4}(?:[-/.年]|$)', text)


def production_date(value):
    """Preserve month precision; only a comparison boundary may use day one."""
    text = str(value or '').strip()
    if production_date_marker(text):
        return text
    if re.fullmatch(r'\d{4}-\d{2}', text):
        date.fromisoformat(text + '-01')
        return text
    parsed = date_value(value)
    return parsed.isoformat() if parsed else ''


def production_date_boundary(value):
    text = production_date(value)
    if production_date_marker(text):
        return None
    return date_value(text + '-01' if len(text) == 7 else text)

LABELS = {
    'produce': '生产日期', 'sample': '抽样日期', 'send': '送样日期',
    'entrust': '委托日期', 'inbound': '入库日期', 'pickup': '出库领取日期',
    'testStart': '检测开始日期', 'testEnd': '检测截止日期',
    'review': '审核日期', 'approval': '批准日期', 'issue': '签发日期',
    'release': '发放日期', 'archive': '归档日期',
}
EDGES = (
    ('produce', 'sample'), ('produce', 'send'), ('produce', 'entrust'),
    ('sample', 'send'), ('send', 'inbound'), ('entrust', 'inbound'),
    ('inbound', 'pickup'), ('pickup', 'testStart'), ('testStart', 'testEnd'),
    ('testEnd', 'review'), ('review', 'approval'), ('approval', 'issue'),
    ('issue', 'archive'), ('archive', 'release'),
)


def date_value(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or '').strip()
    if not text or text in ('—', '待填写', '待录入'):
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        raise ValueError('无效日期') from None


def predecessors(node):
    result = set()
    pending = [node]
    while pending:
        target = pending.pop()
        for before, after in EDGES:
            if after == target and before not in result:
                result.add(before)
                pending.append(before)
    return result


def ordered_pair(value, previous, label, previous_label, *, required=False):
    try:
        current, prior = date_value(value), date_value(previous)
    except ValueError:
        return f'{label}必须为有效日期'
    if current is None:
        return f'{label}必须为有效日期' if required else None
    if prior is None:
        return f'{previous_label}尚未完成，暂不能填写{label}' if required else None
    if current < prior:
        return f'{label}不得早于{previous_label} {prior.isoformat()}'
    return None


def validate_date_order(values, *, through=None):
    if values.get('productionDates'):
        from .production_dates import normalize_rows
        try:
            rows = normalize_rows(values['productionDates'])
        except ValueError as error:
            return str(error)
        base = {k: v for k, v in values.items() if k not in ('productionDates', 'produce')}
        # Check each component against the whole chain, including skipped nodes.
        for index, row in enumerate(rows):
            error = validate_date_order({**base, 'produce': row['value'] if row['precision'] != 'custom' else ''}, through=through)
            if error:
                return f"{row['name'] or f'第{index + 1}项'}：{error}"
        return None
    allowed = set(LABELS) if through is None else predecessors(through) | {through}
    parsed = {}
    for key, label in LABELS.items():
        if key not in allowed:
            continue
        try:
            parsed[key] = production_date_boundary(values.get(key)) if key == 'produce' else date_value(values.get(key))
        except ValueError:
            return f'{label}必须为有效日期'
    for after, label in LABELS.items():
        if not parsed.get(after):
            continue
        for before in LABELS:
            if before in predecessors(after) and parsed.get(before):
                error = ordered_pair(parsed[after], parsed[before], label, LABELS[before])
                if error:
                    return error
    return None
