"""Read-only report-number groups. Always intersect the existing access query."""
import json
import re
from pathlib import Path
from sqlalchemy import and_, or_, func
from .models import Report

CONFIG = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
GROUPS = {item['value']: item['codes'] for item in CONFIG['groups']}
DEPARTMENTS = [CONFIG['department'], *CONFIG['departmentAliases']]


def _pattern(codes):
    # Exact category boundary: H is not HC, ZX is not ZX-JH, G(II) is not G(I).
    # Only the serial and existing derived-report suffix follow the category.
    return r'^(?:[A-Z]+-)?[0-9]{4}(?:' + '|'.join(re.escape(c) for c in codes) + r')-[0-9]+(?:$|[-(（])'


def apply_report_group(query, value):
    if value is None or value == '':
        return query
    if not isinstance(value, str) or value not in (*GROUPS, '未归组', '__ac_department__'):
        raise ValueError('数据分组无效')
    department = func.trim(func.coalesce(Report.department, ''))
    department_scope = or_(department.in_(DEPARTMENTS), department.startswith(CONFIG['department'] + '-'))
    if value == '__ac_department__':
        return query.filter(department_scope)
    number = func.upper(func.trim(func.coalesce(Report.report_no, '')))
    for old, new in [('（','('),('）',')'),('Ⅱ','II'),('Ⅰ','I'),('Ⅲ','III')]:
        number = func.replace(number, old, new)
    codes = GROUPS[value] if value != '未归组' else [c for values in GROUPS.values() for c in values]
    match = number.op('REGEXP')(_pattern(codes))
    return query.filter(and_(department_scope, ~match if value == '未归组' else match))
