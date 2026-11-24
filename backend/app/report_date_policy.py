"""Read authoritative business dates and normalize their display mirrors."""
from copy import deepcopy
from .models import Entrust
from .report_date_rules import validate_date_order, date_value, predecessors, production_date
from .workflow_dates import latest_workflow_date

EVENTS = {
    'review': 'report.review.pass', 'approval': 'report.approval.pass',
    'issue': 'report.print.pass', 'release': 'report.distribution.complete',
    'archive': 'report.archive.pass',
}

SAMPLE_DATE_LABELS = {
    'produceDate': ('生产日期',), 'sampleTime': ('抽样日期', '抽样时间'),
    'sendDate': ('送样日期',), 'sampleArrivalDate': ('样品到达日期',),
    'sendOutTime': ('报告承诺时间(外部)', '报告寄送(对外)'),
    'sendInTime': ('报告承诺时间(内部)', '报告寄送(内部)'),
    'innerStdDate': ('约定检测日期', '内业标准日期'),
}


def synchronize_sample_date_summary(detail):
    """Return a copy; an explicit form value (including empty) owns its mirror.

    Legacy summary-only dates remain available. Callers persist this as part of
    their normal audited save, never as a side effect of a read/preflight.
    """
    result = deepcopy(detail or {})
    raw = result.get('rawSample') or {}
    labels = {label: key for key, names in SAMPLE_DATE_LABELS.items() for label in names}
    for section in result.get('summary') or []:
        for index, pair in enumerate(section.get('fields') or []):
            if len(pair) > 1 and pair[0] in labels and labels[pair[0]] in raw:
                section['fields'][index] = [pair[0], raw[labels[pair[0]]] or '—', *pair[2:]]
    return result


def audit_sample_date_alignment(report_no, source, actor):
    """Enqueue evidence in the caller's save transaction; never commit here."""
    normalized = synchronize_sample_date_summary(source)
    if normalized.get('summary') != (source or {}).get('summary'):
        from .platform.audit import add_operation_audit
        add_operation_audit(
            'report.date_summary.align', 'report', report_no, category='workflow', actor=actor,
            before={'summary': (source or {}).get('summary')},
            after={'summary': normalized.get('summary')},
            message='表单日期为准，自动同步摘要日期',
        )


def sample_date_values(detail, entrust_date):
    detail = detail or {}
    raw = detail.get('rawSample') or {}
    def field(key, *labels):
        candidates = []
        value = raw.get(key)
        empty = (None, '', '—', '待填写', '待录入')
        if key in raw:
            if value not in empty or (key == 'produceDate' and value == '—'):
                candidates.append(value)
        else:
            for section in detail.get('summary') or []:
                for pair in section.get('fields') or []:
                    if len(pair) > 1 and pair[0] in labels and pair[1] not in empty:
                        candidates.append(pair[1])
        parsed = []
        for item in candidates:
            try:
                value = production_date(item) if key == 'produceDate' else date_value(item)
            except ValueError:
                raise ValueError(f'{labels[0]}必须为有效日期') from None
            if value is not None:
                parsed.append(value)
        if len(set(parsed)) > 1:
            raise ValueError(f'{labels[0]}在表单与摘要中不一致，请核对后重新保存')
        return parsed[0] if parsed else None
    from .production_dates import normalize_rows
    rows = normalize_rows(raw['productionDates']) if 'productionDates' in raw else []
    return {
        'produce': None if rows else field('produceDate', '生产日期'),
        'productionDates': rows,
        'sample': field('sampleTime', '抽样日期', '抽样时间'),
        'send': field('sendDate', '送样日期'), 'entrust': entrust_date,
    }


def saved_business_dates(detail, pickup=None):
    """Use selected business dates only. Audit timestamps are not substitutes."""
    flow = (detail or {}).get('workflowDates') or {}
    check = (detail or {}).get('checkInput') or {}
    pickup = pickup or {}
    return {
        'inbound': flow.get('sampleInboundAt'),
        'pickup': flow.get('samplePickupAt') or pickup.get('pickupTime') or pickup.get('outTime'),
        'testStart': check.get('testStartDate'), 'testEnd': check.get('testDate'),
    }


def _report_date_error(report, through, value=None, *, overrides=None):
    """Only inspect this milestone and its ancestors, not stale later events
    from a previous review/rework cycle. Optional/skipped stages stay optional.
    """
    detail = report.detail or {}
    entrust = Entrust.query.filter_by(entrust_no=report.entrust_no).first() if report.entrust_no else None
    entrust_date = (entrust.info or {}).get('entrustDate') if entrust else None
    try:
        values = sample_date_values(detail, entrust_date)
    except ValueError as error:
        return str(error)
    values.update(saved_business_dates(detail, report.sample_pickup))
    before = predecessors(through)
    # Existing audit records supply actual operation dates; form/report display
    # dates must not be substituted for approval or issuance timestamps.
    for key, action in EVENTS.items():
        if key in before:
            values[key] = latest_workflow_date('report', report.report_no, action)
            if key == 'issue':
                values[key] = latest_workflow_date('report', report.report_no, 'report.seal.completed') or values[key]
    values.update(overrides or {})
    if value is not None:
        values[through] = value
    # A recorded physical stage with a lost date requires evidence recovery.
    # Configured skipped stages have no such event and remain optional.
    if any(values.get(k) for k in ('pickup', 'testStart', 'testEnd')) or value is not None:
        from .models import OperationAudit
        for key, label, actions in (
            ('inbound', '入库', ('sample.inbound.confirm', 'sample.mobile.inbound.confirm')),
            ('pickup', '领取', ('sample.out_warehouse.sign', 'sample.mobile.pickup.confirm')),
        ):
            if key in before and not values.get(key) and OperationAudit.query.filter_by(
                object_type='report', object_id=report.report_no, success=True,
            ).filter(OperationAudit.action.in_(actions)).first():
                return f'缺少原{label}业务日期，请核对历史记录恢复；不能用操作日期代替'
    return validate_date_order(values, through=through)


def check_date_order(report, stage, value=None, user=None, *, overrides=None, required=()):
    """Canonical date guard. No role can waive invalid or reversed dates."""
    detail = report.detail or {}
    values = saved_business_dates(detail, report.sample_pickup)
    values.update(overrides or {})
    if value is not None:
        values[stage] = value
    for key in required:
        if not values.get(key):
            from .report_date_rules import LABELS
            return {'level':'block','code':'date.predecessor_required',
                    'message': '缺少' + LABELS.get(key,key) + '，请核对原业务记录；不能用操作日期代替'}
    message = _report_date_error(report, stage, value, overrides=overrides)
    return {'level':'block' if message else 'notice',
            'code': 'date.invalid_order' if message else 'date.valid', 'message': message or ''}


def report_date_error(report, through, value=None, *, overrides=None):
    return check_date_order(report, through, value, overrides=overrides)['message'] or None
