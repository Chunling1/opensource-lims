"""Refresh stale registration labels in response data only, never stored snapshots."""
from copy import deepcopy
from .preflight_reads import reuse_preflight_reads
from .standard_control import find_controlled_standard
from .report_scope import standards_for, report_seal
from .compliance import _business_date


@reuse_preflight_reads
def project_standard_scope(report, data):
    codes = standards_for(data)
    if not codes:
        return data
    when = _business_date(data)
    from .standard_control import selected_controlled_standards
    results = [result for _, result in selected_controlled_standards(codes, (data.get('rawSample') or {}).get('standardItemIds'), report.department, when)]
    single = all(row.get('valid') and row.get('cma') and row.get('singleList') for row in results)
    output = dict(data)
    raw = dict(data.get('rawSample') or {})
    raw['testBasisSingle'] = single
    output['rawSample'] = raw
    summary = deepcopy(data.get('summary') or [])
    cma = all(row.get('valid') and row.get('cma') for row in results)
    value = ('一单一库内' if single else ('CMA授权范围内（非一单一库）' if cma else '超出一单一库（需复核）')) if 'CMA' in report_seal(data).upper() else '—（非CMA盖章）'
    if any(row.get('identityUnresolved') for row in results):
        value = '标准关联待核对（尚不能判断资质范围）'
    for section in summary:
        if section.get('title') == '实验信息':
            section['fields'] = [[field[0], value, *field[2:]] if len(field) >= 2 and field[0] == '检测依据范围' else field for field in section.get('fields') or []]
    output['summary'] = summary
    return output
