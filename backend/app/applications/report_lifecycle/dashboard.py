"""Dashboard tasks are handling access, not report-query visibility.

The caller must apply scoped_report_query before calling this projection.
Reuse the exact handling-page state and project grant checks; never grant a
permission or treat completion/recall of a previous node as a pending task.
"""
from .queries import report_detail_projection, report_detail_access_error


TODO_RULES = {
    '待合同评审': ('contract_review', 'report.contract_review.pass'),
    '待样品入库': ('sample_inbound', 'sample.inbound.confirm'),
    '待样品领取': ('sample_outbound', 'sample.out_warehouse.sign'),
    '检测录入中': ('data_entry', None),
    '退回待重传': ('data_change', None),
    '检测更改中': ('data_change', None),
    '待审核': ('review', 'report.review.pass'),
    '待批准': ('approval', 'report.approval.pass'),
    '待打印': ('print', 'report.print.pass'),
    '待发放': ('archive', 'report.archive.pass'),
    '已发放': ('archive', 'report.archive.pass'),
    '委托更改中': ('entrust_change', 'entrust.change.resubmit'),
}


def report_todo_view(user, report, *, actions=None):
    if not user.enabled or getattr(report, 'voided', False):
        return None
    from ...report_delivery import delivery_released, SEALED, RELEASE_ACTION
    if delivery_released(report):
        return None
    rule = TODO_RULES.get(report.status)
    if report.status in {'待发放', '已发放'} and report.archive_state == '归档完成':
        rule = ('release', RELEASE_ACTION)
    elif report.status == '待打印' and report.to_row()['dataStatus'] == SEALED:
        rule = ('archive', 'report.archive.pass')
    if rule is None:
        return None
    view, action = rule
    if action and action not in (set(user.action_codes()) if actions is None else actions):
        return None
    # The action above has already been verified against this user's grants.
    # Supply that evidence to archive projection, without changing read scope.
    projection = report_detail_projection(report, view, allowed_actions=[action] if action else [])
    if projection != 'active' or report_detail_access_error(user, report, view, projection):
        return None
    # These processing pages save data through the data-entry write endpoint.
    if view == 'data_change' and 'testing.data_entry.view' not in user.permission_codes():
        return None
    return view
