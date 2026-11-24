"""Resolve standard identity explicitly; never infer lost marks from ambiguity."""
from copy import deepcopy
from .models import StdLibraryItem
from .standard_control import normalize_code, _department_matches, selected_controlled_standards
from .report_standard_selection import registration_standards, testing_standards
from .functions.report_standard_text import load_report_standard_records
from .platform.audit import add_operation_audit
from .preflight_reads import read_once, reuse_preflight_reads


def resolution_choices(report):
    raw = (report.detail or {}).get('rawSample') or {}
    codes = registration_standards(report.detail or {})
    selected = selected_controlled_standards(codes, raw.get('standardItemIds'), report.department)
    if not any(result.get('identityUnresolved') for _, result in selected):
        return []
    rows = read_once('controlled_standard_rows', lambda: StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all())
    resolved = {normalize_code(result['code']) for item,result in selected if item is not None and not result.get('identityUnresolved')}
    unresolved = {normalize_code(result['code']) for _,result in selected if result.get('identityUnresolved')}
    codes = [code for code in codes if normalize_code(code) not in resolved or normalize_code(code) in unresolved]
    return [dict(code=code, candidates=[dict(id=row.id, code=row.code, name=row.name,
                department=row.use_depts, implementationDate=row.impl_date, marks=row.auth_kind)
            for row in rows if normalize_code(row.code) == normalize_code(code)
            and _department_matches(row, report.department)]) for code in codes]


def align_testing_identity(report, actor):
    detail = deepcopy(report.detail or {})
    codes, tested = registration_standards(detail), testing_standards(detail)
    if not codes or not tested or {normalize_code(c) for c in codes} != {normalize_code(c) for c in tested}:
        return False
    ids = (detail.get('rawSample') or {}).get('standardItemIds')
    if not ids or any(result.get('identityUnresolved') for _, result in
                      selected_controlled_standards(codes, ids, report.department)):
        return False
    records = load_report_standard_records(codes, ids)
    check = detail.get('checkInput') or {}
    before = check.get('standardRecords')
    if before == records:
        return False
    check['standardRecords'] = records
    detail['checkInput'] = check
    report.detail = detail
    add_operation_audit('report.standard_identity.align', 'report', report.report_no,
        category='workflow', actor=actor, before={'standardRecords': before},
        after={'standardRecords': records}, message='同编号检测标准按登记记录ID自动对齐，资质按登记记录判断')
    return True


def resolve_identities(report, actor, selections, reason):
    choices = resolution_choices(report)
    if not choices:
        raise ValueError('标准关联已变化，请刷新校核结果')
    if not str(reason or '').strip():
        raise ValueError('请选择标准并填写确认依据')
    if not isinstance(selections, dict) or set(selections) != {c['code'] for c in choices}:
        raise ValueError('请逐项选择全部登记标准')
    ids = []
    for choice in choices:
        selected = selections[choice['code']]
        if type(selected) is not int or selected not in {c['id'] for c in choice['candidates']}:
            raise ValueError('候选标准已变化或不在本部门授权范围，请重新选择')
        ids.append(selected)
    detail = deepcopy(report.detail or {})
    raw = dict(detail.get('rawSample') or {})
    before = raw.get('standardItemIds')
    changing = {normalize_code(c['code']) for c in choices}
    previous_ids = raw.get('standardItemIds') if isinstance(raw.get('standardItemIds'), list) else []
    valid = StdLibraryItem.query.filter(StdLibraryItem.id.in_([i for i in previous_ids if type(i) is int]), StdLibraryItem.deleted_at.is_(None)).all()
    retained = [item.id for item in valid if normalize_code(item.code) not in changing]
    raw['standardItemIds'] = retained + ids
    detail['rawSample'] = raw
    report.detail = detail
    add_operation_audit('report.standard_identity.confirm', 'report', report.report_no,
        category='workflow', actor=actor, before={'standardItemIds': before},
        after={'standardItemIds': raw['standardItemIds'], 'reason': str(reason).strip()}, message='当场确认登记标准记录')
    align_testing_identity(report, actor)


@reuse_preflight_reads
def affected_reports(code, user=None):
    from .models import Report
    wanted = normalize_code(code)
    from .applications.report_lifecycle import scoped_report_query
    query = scoped_report_query(Report.query, user) if user is not None else Report.query
    rows = query.filter(Report.voided.isnot(True), Report.status.in_(
        ['待合同评审', '待样品入库', '待样品领取', '检测录入中', '检测更改中', '待校核', '待审核', '待批准'])).all()
    return [r for r in rows if wanted in {normalize_code(c) for c in registration_standards(r.detail or {})}
            and any(normalize_code(c['code']) == wanted for c in resolution_choices(r))]


def identity_revision(report):
    import hashlib, json
    return hashlib.sha256(json.dumps({'detail':report.detail,'status':report.status,'department':report.department},
        sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
