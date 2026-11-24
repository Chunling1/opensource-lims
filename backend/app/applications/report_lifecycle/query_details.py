"""Report-query-only fields and latest actual operators, batched within visible reports."""
from datetime import UTC

from sqlalchemy import func

from ...business_rows import clean, first, summary_field
from ...extensions import db
from ...models import OperationAudit
from ...workflow_dates import BUSINESS_TIMEZONE

# Assigned reviewers/approvers are deliberately not used as actual operators.
STAGES = {
    'commissionCreated': ('entrust', ('entrust.register.create',)),
    'commissionCompleted': ('entrust', ('entrust.register.complete',)),
    'sampleRegistered': ('report', ('sample.register.complete',)),
    'contractReviewed': ('report', ('report.contract_review.pass',)),
    'sampleInbound': ('report', ('sample.inbound.confirm', 'sample.mobile.inbound.confirm')),
    'sampleOutbound': ('report', ('sample.out_warehouse.sign', 'sample.mobile.pickup.confirm')),
    'sampleReturned': ('report', ('sample.return_stock', 'sample.mobile.return.confirm')),
    'dataSaved': ('report', ('report.data_entry.save',)),
    'dataCompleted': ('report', ('report.data_entry.complete', 'report.data_change.complete', 'report.test_change.complete')),
    'reportChecked': ('report', ('report.report_check.pass',)),
    'reportReviewed': ('report', ('report.review.pass',)),
    'reportApproved': ('report', ('report.approval.pass',)),
    'sealConfirmed': ('report', ('report.esign.unified.confirm', 'report.esign.organization_seal.confirm')),
    'reportIssued': ('report', ('report.print.pass', 'report.seal.completed')),
    'reportReleased': ('report', ('report.distribution.complete', 'report.release.pass')),
    'reportArchived': ('report', ('report.archive.pass',)),
}


def query_details(reports, stage_keys=None):
    """Caller passes only report rows that have already passed view/data authorization."""
    reports = list(reports)
    stages = STAGES if stage_keys is None else {key: STAGES[key] for key in stage_keys}
    evidence = {}
    for kind in ('entrust', 'report'):
        ids = list({str(r.entrust_no if kind == 'entrust' else r.report_no) for r in reports
                    if (r.entrust_no if kind == 'entrust' else r.report_no)})
        actions = {a for k, choices in stages.values() if k == kind for a in choices}
        for start in range(0, len(ids), 500):
            latest = db.session.query(func.max(OperationAudit.id)).filter(
                OperationAudit.object_type == kind, OperationAudit.object_id.in_(ids[start:start+500]),
                OperationAudit.action.in_(actions), OperationAudit.success.is_(True),
            ).group_by(OperationAudit.object_id, OperationAudit.action)
            # Do not load or expose audit snapshots/IP metadata in a list response.
            rows = db.session.query(OperationAudit.id, OperationAudit.object_id, OperationAudit.action,
                                    OperationAudit.user_name, OperationAudit.account, OperationAudit.created_at
                                    ).filter(OperationAudit.id.in_(latest)).all()
            for audit in rows:
                evidence[kind, audit.object_id, audit.action] = audit
    result = {}
    for report in reports:
        detail = report.detail or {}
        raw = detail.get('rawSample') or {}
        test = detail.get('checkInput') or {}
        dates = detail.get('workflowDates') or {}
        pickup = report.sample_pickup or {}
        row = {key: clean(raw.get(source)) for key, source in {
            'specification': 'spec', 'manufacturer': 'manufacturer', 'productionDate': 'produceDate',
            'sampleQuantity': 'sampleAmount', 'productCode': 'factoryNo', 'sampleAppearance': 'appearance',
            'testingLocation': 'testLocation', 'testBasis': 'testBasis', 'assessmentStandard': 'standardJudge',
            'paymentMethod': 'payWay', 'samplingLocation': 'samplingLocation',
        }.items()}
        row.update(sampleInboundDate=clean(dates.get('sampleInboundAt'))[:10],
                   sampleOutboundDate=clean(pickup.get('outTime'))[:10],
                   samplePickupDate=first(pickup.get('pickupTime'), dates.get('samplePickupAt'))[:10],
                   sampleReceiver=clean(pickup.get('receiverName')) if pickup.get('signed') else '',
                   testBasis=first(test.get('standard'), raw.get('testBasis'), summary_field(detail, '检测依据', '执行标准')),
                   testStartDate=clean(test.get('testStartDate')),
                   testEndDate=clean(test.get('testDate')),
                   testResult=first(test.get('result'), test.get('conclusion'), summary_field(detail, '检测结果', '结论')))
        result_status=clean(test.get('resultStatus'))
        row['resultStatus']={'判定合格':'合格','判定不合格':'不合格'}.get(result_status,result_status)
        method=clean(raw.get('deliverWay'))
        row['collectionMethod']='自取' if method in ('领取','自取') else '邮寄' if method=='邮寄' else '其他' if method else ''
        for key, (kind, actions) in stages.items():
            identity = report.entrust_no if kind == 'entrust' else report.report_no
            audits = [evidence[kind, identity, a] for a in actions if (kind, identity, a) in evidence]
            latest = max(audits, key=lambda a: a.id) if audits else None
            row[key + 'By'] = (latest.user_name or latest.account or '') if latest else ''
            at = latest.created_at if latest else None
            row[key + 'At'] = ((at.replace(tzinfo=UTC) if at.tzinfo is None else at)
                              .astimezone(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')) if at else ''
        for key,stage,workflow in [('checkDate','reportChecked','checkDate'),('auditDate','reportReviewed','auditDate'),
                                  ('approvalDate','reportApproved','approvalDate'),('printDate','reportIssued','reportDate'),
                                  ('archiveDate','reportArchived','archiveDate'),('distributionDate','reportReleased','distributionDate')]:
            row[key]=first(dates.get(workflow),row.get(stage+'At',''))
        row['archiveStatus']='已归档' if report.archive_state=='归档完成' else '待归档'
        from ...report_delivery import delivery_released
        row['releaseStatus']='已发放' if delivery_released(report) else '未发放'
        row['issueStatus']='已签发' if report.status in ('待发放','已发放','已归档') else '未签发'
        result[report.report_no] = row
    return result
