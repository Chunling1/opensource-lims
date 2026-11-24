"""Component production dates. Business dates and explanatory text stay separate."""
from copy import deepcopy
from datetime import date
import re


def normalize_rows(rows):
    if not isinstance(rows, list):
        raise ValueError('生产日期明细必须为列表')
    result = []
    for i, source in enumerate(rows):
        if not isinstance(source, dict):
            raise ValueError(f'生产日期第{i + 1}项格式无效')
        row = {}
        for key in ('name', 'precision', 'value', 'note'):
            value = source.get(key, '')
            if not isinstance(value, str):
                raise ValueError(f'生产日期第{i + 1}项的{key}必须为文字')
            row[key] = value.strip()
        label = row['name'] or f'第{i + 1}项'
        precision, value = row['precision'], row['value']
        if not precision:
            precision = ('day' if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) else
                         'month' if re.fullmatch(r'\d{4}-\d{2}', value) else 'custom')
            row['precision'] = precision
        if precision not in ('day', 'month', 'custom'):
            raise ValueError(f'{label}：请选择生产日期精度')
        if value:
            try:
                if precision == 'day':
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                        raise ValueError()
                    date.fromisoformat(value)
                elif precision == 'month':
                    if not re.fullmatch(r'\d{4}-\d{2}', value):
                        raise ValueError()
                    date.fromisoformat(value + '-01')
                elif re.search(r'\d{4}[-/.年]\d', value):
                    raise ValueError()
            except ValueError:
                raise ValueError(f'{label}：生产日期格式无效；日期请用精确到日或月填写') from None
        result.append(row)
    return result


def display_rows(rows, *, language='CN', formatted=False):
    from .report_date_display import report_date
    labels = {'室内机': 'Indoor unit', '室外机': 'Outdoor unit', '整机': 'Unit'}
    lines = []
    for row in normalize_rows(rows):
        name, value, note = row['name'], row['value'], row['note']
        if language == 'EN':
            match = re.fullmatch(r'(室内机|室外机|整机)(\d*)', name)
            if match:
                name = labels[match[1]] + (' ' + match[2] if match[2] else '')
        if formatted and row['precision'] != 'custom':
            value = report_date(value, language=language)
        line = (name + (': ' if language == 'EN' else '：') if name else '') + value
        if note:
            line += f' ({note})' if language == 'EN' else f'（{note}）'
        lines.append(line)
    return '\n'.join(lines)


def canonical_detail(detail):
    """Structured rows are authoritative; regenerate the legacy display mirror."""
    result = deepcopy(detail)
    raw = result.get('rawSample') or {}
    if 'productionDates' not in raw:
        return result
    rows = normalize_rows(raw['productionDates'])
    raw['productionDates'] = rows
    # An empty list means a legacy single value, not an instruction to erase it.
    if rows:
        raw['produceDate'] = display_rows(rows)
        for section in result.get('summary') or []:
            if section.get('title') in ('送样信息', '样品信息'):
                section['fields'] = [[k, raw['produceDate']] if k == '生产日期' else [k, v]
                                     for k, v in section.get('fields') or []]
    result['rawSample'] = raw
    return result
