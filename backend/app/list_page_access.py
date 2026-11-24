"""Preserve existing workflow/recall authorization before SQL page selection.

Only identity and authorization facts are read here; no business rows, scope
assessment, document content or list display projection is built off-page.
"""
from .models import Report
from .list_projection import read_list, leaves

IDENTITY = {**leaves('derivedFrom internalCorrectionRevision dataEntryStarted reportDelivery'),
            'rawSample': leaves('schemeCode schemeName baseReportNo'),
            'checkInput': leaves('entryStaff people')}
COLUMNS = set('id report_no project department owner status sample_status sample_reg_state archive_state voided '
              'entrust_no main_report_no report_kind current_document_version_id approved_document_version_id'.split())


def identity_rows(query):
    return read_list(query,Report,shape=IDENTITY,column_names=COLUMNS)


def report_access(query,user,view,*,row_projection=None):
    if view in {'query','change_request','release'}:
        # SQL predicates below enforce the exact lifecycle for the latter two.
        return query
    from .applications.report_lifecycle.queries import report_processing_step_error, report_allowed_actions
    from .platform.workflow import report_projection
    from .list_reads import prime_identifiers
    from .issuance_data_status import current_flows,flow_label
    from .report_delivery import delivery_released
    from .status_machine import report_data_status
    candidates=identity_rows(query)
    prime_identifiers('report',[r.report_no for r in candidates],candidates)
    flows=current_flows(candidates) if view in {'archive','approval'} else {}
    allowed=[]
    for r in candidates:
        # Only recall membership needs actions. Active query rows hydrate them
        # after LIMIT, never assess CMA/CNAS for the entire authorized scope.
        actions=[]
        if (view=='data_entry' and r.status=='待审核' or view in {'review','interim_report'} and r.status=='待批准'
                or view=='approval' and r.status=='待打印' or view=='archive'):
            actions=report_allowed_actions(user,r,issuance_label=flow_label(flows.get(r.id)))
        row={'status':r.status,'sampleStatus':r.sample_status,'sampleRegState':r.sample_reg_state or '登记完成',
             'archiveState':r.archive_state,'voided':r.voided,'allowedActions':actions,
             'distributionComplete':delivery_released(r),
             'dataStatus':report_data_status(r.status,r.sample_status,r.sample_reg_state,r.archive_state,r.voided,
                 issuance_label=flow_label(flows.get(r.id)))}
        projection=report_projection(row,view)
        if projection and (not row_projection or projection==row_projection) and (projection!='active' or not report_processing_step_error(user,r,view)):
            allowed.append(r.id)
    return query.filter(Report.id.in_(allowed))


def sample_access(query,user,view):
    if view not in {'inbound','outbound'}: return query
    from .authorization_scope import project_step_error
    ids=[r.id for r in identity_rows(query) if not project_step_error(user,r,
        'sample_inbound' if view=='inbound' else 'sample_outbound','样品流转')]
    return query.filter(Report.id.in_(ids))


def current_report_query(query):
    """Hide original rows replaced by a live correction in Report Query."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import aliased

    correction = aliased(Report)
    superseded = select(correction.id).where(
        correction.main_report_no == Report.report_no,
        correction.report_kind.in_(('correction', 'replacement')),
        func.coalesce(correction.voided, False).is_(False),
    ).correlate(Report).exists()
    return query.filter(~superseded)


def report_candidates(query,user,view,*,row_projection=None,presentation='report'):
    """Shared report lifecycle and permission scope for list pages and plan counts."""
    from sqlalchemy import func, or_
    from .list_paging import released, json_truthy
    r=Report
    if view == 'query' and presentation == 'report':
        query = current_report_query(query)
    requested_projection=row_projection
    if view not in {'query','archive'}: query=query.filter(func.coalesce(r.voided,False).is_(False))
    states={'data_entry':['检测录入中','待审核'],'data_change':['退回待重传','检测更改中'],
            'review':['待审核','待批准'],'interim_report':['待审核','待批准'],
            'approval':['待批准','待打印'],'print':['待打印','待发放','已发放','已归档']}
    if view in states: query=query.filter(r.status.in_(states[view]))
    if view=='release':
        query=query.filter(r.status.in_(['待发放','已发放']),r.archive_state=='归档完成')
        if requested_projection=='active':query=query.filter(~func.coalesce(released(),False))
        elif requested_projection=='recall':query=query.filter(released())
    if view=='change_request': query=query.filter(or_(r.status.in_(['待打印','待发放','已发放']),json_truthy(r.detail,'internalCorrectionRevision')))
    query=report_access(query,user,view,row_projection=requested_projection)
    return query
