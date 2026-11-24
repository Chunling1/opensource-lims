"""Opt-in report list query plan. No persisted state or authorization changes."""
from sqlalchemy import select, func, case, and_, cast, String, literal, union
from sqlalchemy.orm import aliased
from .models import Report, OperationAudit
from .extensions import db


def joined_sources(query, *, required_actions=None):
    """One successful-audit aggregation; latest means greatest ID, not time.

    Each action set selects its winning ID inside that aggregation. PK joins
    then read all columns from that same winning row (including blank names).
    """
    from .applications.report_lifecycle.query_details import STAGES
    from .admin_corrections.source import SourceCorrection
    groups = list(dict.fromkeys((kind, tuple(actions)) for kind, actions in STAGES.values()))
    for entry in [('report', ('sample.out_warehouse.sign',)),
                  ('report', ('report.data_entry.save',)),
                  ('report', ('sample.inbound.confirm', 'sample.mobile.inbound.confirm'))]:
        if entry not in groups:
            groups.append(entry)
    if required_actions is not None:
        groups=[g for g in groups if any(action in required_actions for action in g[1])]
    # Materialize only authorized candidate identities. UNION removes duplicate
    # entrust numbers before joining, so each audit row is aggregated once.
    candidates = query.with_entities(Report.report_no.label('report_no'),
        Report.entrust_no.label('entrust_no')).order_by(None).distinct().cte('list_candidates')
    keys = union(
        select(literal('report').label('kind'), candidates.c.report_no.label('identity')),
        select(literal('entrust').label('kind'), candidates.c.entrust_no.label('identity')),
    ).cte('list_candidate_audit_keys')
    a = OperationAudit
    aggregate = select(a.object_type.label('kind'), a.object_id.label('identity'),
        func.max(a.created_at).label('edited_at'),
        *[func.max(case((and_(a.object_type == kind, a.action.in_(actions)), a.id))).label('latest_'+str(i))
          for i, (kind, actions) in enumerate(groups)]
    ).join(keys, and_(a.object_type == keys.c.kind, a.object_id == keys.c.identity)).where(a.success.is_(True)).group_by(a.object_type, a.object_id).cte('list_audit_summary')
    relations = {}
    for kind, identity in [('report', Report.report_no), ('entrust', Report.entrust_no)]:
        relation = aggregate.alias('list_'+kind+'_audits')
        query = query.outerjoin(relation, and_(relation.c.kind == kind, relation.c.identity == identity))
        relations[kind] = relation
    winners = {}
    for i, (kind, actions) in enumerate(groups):
        winner = aliased(OperationAudit, name='list_audit_'+str(i))
        query = query.outerjoin(winner, winner.id == relations[kind].c['latest_'+str(i)])
        winners[kind, frozenset(actions)] = winner

    def audit(kind, identity, actions, column='created_at'):
        winner=winners.get((kind,frozenset(actions)))
        if winner is None:
            from .list_paging import audit_value
            return audit_value(kind,identity,actions,column)
        return getattr(winner,column)

    correction = aliased(SourceCorrection, name='list_source_correction')
    query = query.outerjoin(correction, and_(correction.kind == 'sample-snapshot',
                                            correction.source_key == cast(Report.id, String)))
    return query, audit, correction.fields, relations['report'].c.edited_at


def select_ids(query, model, body, fields):
    from .list_paging import NaturalNumberKey
    from sqlalchemy import text
    if db.engine.dialect.name in {'mysql', 'mariadb'}:
        # All statements in the request must share the current snapshot.
        isolation = db.session.connection().get_isolation_level()
        if isolation.replace('_', ' ').upper() != 'REPEATABLE READ':
            raise RuntimeError('ID-first list pagination requires REPEATABLE READ')
        db.session.execute(text('SET SESSION group_concat_max_len = @@max_allowed_packet'))
    page = max(1, int(body.get('page') or 1))
    size = max(1, min(200, int(body.get('pageSize') or 10)))
    sort = body.get('sort') or 'editedAt'
    if sort not in fields:
        raise ValueError('列表排序字段无效：'+str(sort))
    expr = fields[sort]
    if sort in {'code','sampleNo','reportNo','reportCode','entrustNo','commissionCode','contractNo','erpProjectNo'}:
        expr = NaturalNumberKey(expr)
    descending = not body.get('sort') or body.get('direction', 'asc') == 'desc'
    ordered = query.order_by(None).order_by(expr.desc() if descending else expr.asc(),
                                           fields['editedAt'].desc(), model.id.desc())
    ids = [row[0] for row in ordered.with_entities(model.id).all()]
    selected = ids[(page-1)*size:page*size]
    # No global predicate/joins remain in the projection query. These IDs have
    # already passed the unchanged scope and candidate permission functions.
    page_query = model.query.filter(model.id.in_(selected)).order_by(model.id)
    from .list_paging import PageMeta
    return page_query, PageMeta(total=len(ids), page=page, pageSize=size, page_ids=selected)
