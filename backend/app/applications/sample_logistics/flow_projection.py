"""Read-only display of existing logistics facts; never infer an operator."""
from ...business_rows import first, summary_field


def sample_event_dates(reports):
    from datetime import UTC
    from ...extensions import db
    from ...models import OperationAudit
    from ...workflow_dates import BUSINESS_TIMEZONE
    numbers=[report.report_no for report in reports]
    result={number:{} for number in numbers}
    if not numbers:return result
    actions={'sample.dispose':'disposalDate','sample.register.void':'voidedAt'}
    records=db.session.query(OperationAudit.object_id,OperationAudit.action,OperationAudit.created_at).filter(
        OperationAudit.object_type=='report',OperationAudit.object_id.in_(numbers),
        OperationAudit.success.is_(True),OperationAudit.action.in_(actions)).order_by(OperationAudit.id.desc()).all()
    for number,action,at in records:
        timestamp=((at.replace(tzinfo=UTC) if at.tzinfo is None else at).astimezone(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')) if at else ''
        result[number].setdefault(actions[action],timestamp)
    return result


def sample_flow_fields(report, inbound_actor=""):
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    dates = detail.get("workflowDates") or {}
    mobile = detail.get("mobileSampleFlow") or {}
    inbound = mobile.get("inbound") or {}
    returned = mobile.get("return") or {}
    pickup = report.sample_pickup or {}
    return {
        "inboundPerson": first(inbound_actor, inbound.get("operatorName"), inbound.get("operatorAccount")),
        "inboundTime": first(dates.get("sampleInboundAt"), inbound.get("operatedAt")),
        "pickupPerson": first(pickup.get("receiverName")),
        "pickupTime": first(pickup.get("pickupTime"), dates.get("samplePickupAt")),
        "outboundPerson": first(pickup.get("managerName"), pickup.get("managerId")),
        "outboundTime": first(pickup.get("outTime")),
        "sampleDisposition": first(returned.get("disposalMethod"), raw.get("sampleHandle"),
                                   summary_field(detail, "样品处理方式")),
    }
