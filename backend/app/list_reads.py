"""Batch read reuse restricted to one explicitly read-only list invocation."""
from contextvars import ContextVar
from functools import wraps

_state = ContextVar('business_list_reads', default=None)

def reuse_list_reads(fn):
    from .preflight_reads import reuse_preflight_reads
    @wraps(fn)
    def wrapped(*args, **kwargs):
        token = _state.set({'ids': {}, 'audits': {}, 'counts': None})
        try:
            return reuse_preflight_reads(fn)(*args, **kwargs)
        finally:
            _state.reset(token)
    return wrapped

def prime_identifiers(object_type, identifiers, records=None):
    state = _state.get()
    if state is not None:
        if object_type == 'report' and records is not None:
            state['scope_reports'] = tuple(records)
            state.pop('erp_contract_numbers', None)
            state.pop('scope_report_ids', None)
            state.pop('snapshot_overrides', None)
            for key in tuple(state):
                if isinstance(key, tuple) and key[0] == 'esign_visible_ids':
                    state.pop(key)
        state['ids'][object_type] = tuple(dict.fromkeys(map(str, identifiers)))
        state['audits'] = {k:v for k,v in state['audits'].items() if k[0] != object_type}


def snapshot_override(report_id, fallback):
    state = _state.get()
    reports = state.get('scope_reports', ()) if state else ()
    ids = tuple(str(r.id) for r in reports)
    if str(report_id) not in ids:
        return fallback()
    if 'snapshot_overrides' not in state:
        from .admin_corrections.source import SourceCorrection
        state['snapshot_overrides'] = {
            row.source_key: row for row in SourceCorrection.query.filter(
                SourceCorrection.kind == 'sample-snapshot',
                SourceCorrection.source_key.in_(ids)).all()}
    return state['snapshot_overrides'].get(str(report_id))

def latest_audit(object_type, object_id, action, fallback):
    state = _state.get()
    ids = state['ids'].get(object_type, ()) if state else ()
    if str(object_id) not in ids:
        return fallback()
    key = (object_type, str(action))
    if key not in state['audits']:
        from sqlalchemy import func
        from .extensions import db
        from .models import OperationAudit
        found = {}
        for start in range(0, len(ids), 500):
            newest = db.session.query(func.max(OperationAudit.id)).filter(
                OperationAudit.object_type == object_type,
                OperationAudit.object_id.in_(ids[start:start+500]),
                OperationAudit.action == str(action),
                OperationAudit.success.is_(True),
            ).group_by(OperationAudit.object_id)
            from sqlalchemy.orm import load_only
            fields = [OperationAudit.id, OperationAudit.object_type, OperationAudit.object_id,
                      OperationAudit.action, OperationAudit.account, OperationAudit.user_id,
                      OperationAudit.user_name, OperationAudit.created_at, OperationAudit.success]
            # Only scope review consumes its small decision evidence; completion
            # and pickup checks must not hydrate full before/after form snapshots.
            if action == 'report.scope.review':
                fields.append(OperationAudit.after_data)
            for row in OperationAudit.query.options(load_only(*fields, raiseload=True)).filter(OperationAudit.id.in_(newest)).all():
                found[row.object_id] = row
        state['audits'][key] = found
    return state['audits'][key].get(str(object_id))

def sample_count(entrust_no, fallback):
    state = _state.get()
    if state is None or str(entrust_no) not in state['ids'].get('entrust', ()):
        return fallback()
    if state['counts'] is None:
        from sqlalchemy import func
        from .extensions import db
        from .models import Report
        state['counts'] = dict(db.session.query(Report.entrust_no, func.count(Report.id)).filter(Report.entrust_no.in_(state['ids'].get('entrust', ()))).group_by(Report.entrust_no).all())
    return state['counts'].get(entrust_no, 0)


def agreement_for_snapshot(contract_no, fallback):
    """Reuse contract reads only within one read-only list invocation."""
    state = _state.get()
    if state is None:
        return fallback()
    if 'snapshot_agreements' not in state:
        from .models import Agreement
        from .extensions import db
        # Snapshot normalization only needs contract identity, type and party A.
        columns = (Agreement.id, Agreement.agreement_no, Agreement.erp_type,
                   Agreement.contract_type, Agreement.client)
        state['snapshot_agreements'] = {
            row.agreement_no: Agreement(**row._asdict())
            for row in db.session.query(*columns).filter(Agreement.agreement_no == contract_no).all()}
    cache = state['snapshot_agreements']
    if contract_no not in cache:
        cache[contract_no] = fallback()
    return cache[contract_no]


def capability_entries(ids, fallback):
    state = _state.get()
    if state is None or 'scope_reports' not in state:
        return fallback()
    if 'scope_capabilities' not in state:
        from .models import CapabilityEntry
        all_ids = set(ids)
        for report in state['scope_reports']:
            for value in ((report.detail or {}).get('rawSample') or {}).get('capabilityEntryIds') or []:
                try:
                    all_ids.add(int(value))
                except (ValueError, TypeError):
                    pass  # The existing scope calculation reports invalid identifiers.
        rows = []
        identifiers = list(all_ids)
        for start in range(0, len(identifiers), 500):
            rows.extend(CapabilityEntry.query.filter(CapabilityEntry.id.in_(identifiers[start:start+500])).all())
        state['scope_capabilities'] = {row.id: row for row in rows}
    return [state['scope_capabilities'][i] for i in ids if i in state['scope_capabilities']]


def erp_contract_number(report_no):
    """One batched receipt read per list invocation; never a provider request."""
    from .extensions import db
    from .workflow_hooks import empty_confirmed_contracts as confirmed_contract_numbers
    state = _state.get()
    scoped = tuple(r.report_no for r in state.get('scope_reports', ())) if state else ()
    if report_no not in scoped:
        return confirmed_contract_numbers(db.session, [report_no]).get(report_no, '')
    if 'erp_contract_numbers' not in state:
        state['erp_contract_numbers'] = confirmed_contract_numbers(db.session, scoped)
    return state['erp_contract_numbers'].get(report_no, '')


def report_visible_to(user, report_id, fallback):
    """Batch the existing eSign scope predicate in read-only lists only."""
    state = _state.get()
    reports = state.get('scope_reports', ()) if state else ()
    if state is None or not reports:
        return fallback()
    if 'scope_report_ids' not in state:
        state['scope_report_ids'] = frozenset(r.id for r in reports)
    ids = state['scope_report_ids']
    if report_id not in ids:
        return fallback()
    key = ('esign_visible_ids', user.id)
    if key not in state:
        from .models import Report
        from .applications.report_lifecycle.queries import scoped_report_query
        visible = set()
        values = list(ids)
        for start in range(0, len(values), 500):
            visible.update(row[0] for row in scoped_report_query(Report.query, user)
                           .with_entities(Report.id).filter(Report.id.in_(values[start:start+500])).all())
        state[key] = visible
    return report_id in state[key]


def user_grant_rows(table, user_id, fallback):
    """Reuse grant rows only while rendering an explicitly primed user list."""
    state = _state.get()
    ids = state['ids'].get('user', ()) if state else ()
    if str(user_id) not in ids:
        return fallback()
    key = ('user_grants', table.name)
    if key not in state:
        from .extensions import db
        grouped = {}
        for start in range(0, len(ids), 500):
            rows = db.session.execute(table.select().where(
                table.c.user_id.in_([int(value) for value in ids[start:start+500]])
            )).fetchall()
            for row in rows:
                grouped.setdefault(row.user_id, []).append(row)
        state[key] = grouped
    return state[key].get(user_id, [])
