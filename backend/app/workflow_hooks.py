"""Local workflow hooks (eSign withdrawal guard, zero external ERP dependency)."""
from __future__ import annotations

import json
from datetime import datetime

LOCAL_UNDOS = {'testing.data_entry.undo', 'report.review.undo', 'report.approval.undo', 'report.print.undo'}
PRE_ISSUANCE = {'待合同评审', '待样品入库', '待样品领取', '检测录入中', '待校核', '待审核', '待批准', '委托更改中', '检测更改中', '检测更改完成'}
ISSUED = {'待打印', '已打印', '待归档', '待发放', '已发放'}


def capture(report, phase, actor=None, skipped=False):
    return None


def skipped(report, steps):
    return None


def _local_blocker(report):
    from .functions.esign_service import ReportEsignFlow
    from .functions.esign_dispatch_state import definitely_uncreated
    flows = ReportEsignFlow.query.filter_by(report_no=report.report_no).with_for_update().populate_existing().all()
    for flow in flows:
        if flow.status in {'cancelled', 'revoked', 'expired'}:
            continue
        if flow.provider_flow_id or flow.status in {'dispatching', 'signing', 'completed', 'signed', 'verified', 'cancelling'}:
            return '报告已有电子签署流程，请先完成签署撤回或状态核对。'
        if not definitely_uncreated(flow):
            return '电子签署发起结果待核实，请先核对原流程。'
    return None


def blocker(report, action):
    if action in LOCAL_UNDOS:
        return _local_blocker(report)
    return None


def complete_local_undo(report, action, actor):
    if action not in LOCAL_UNDOS:
        return
    error = _local_blocker(report)
    if error:
        raise ValueError(error)
    from .models import ReportEsignFlow
    from .functions.esign_dispatch_state import definitely_uncreated, snapshot
    from .audit import add_operation_audit
    for flow in ReportEsignFlow.query.filter_by(report_no=report.report_no).with_for_update().all():
        if flow.status in {'cancelled', 'revoked', 'expired'}:
            continue
        if definitely_uncreated(flow):
            value = snapshot(flow)
            value['localWithdrawal'] = dict(
                action=action,
                previousStatus=flow.status,
                actorId=getattr(actor, 'id', None),
                withdrawnAt=datetime.utcnow().isoformat(),
            )
            flow.positioning_json = json.dumps(value, ensure_ascii=False)
            flow.status = 'cancelled'
            add_operation_audit(
                'report.esign.local.withdraw',
                'report',
                report.report_no,
                category='integration',
                actor=actor,
                after={'flowId': flow.id, **value['localWithdrawal']},
                message='撤回业务节点，停用尚未创建远端流程的本地签署任务；保留文件和失败记录',
            )


def empty_authorization_payload(*_args, **_kwargs):
    return {'roles': [], 'grants': []}


def empty_effective_roles(*_args, **_kwargs):
    return []


def empty_customer_search(*_args, **_kwargs):
    return {'rows': [], 'total': 0}


def empty_confirmed_contracts(*_args, **_kwargs):
    return {}
