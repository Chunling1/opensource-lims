"""Read-only, report-scoped projections of persisted workflow audit evidence."""
from ...models import OperationAudit

# Only business fields already present in historical audit snapshots are exposed.
# Never return IP metadata or arbitrary snapshot dictionaries.
FIELDS = {
    "client": "委托单位", "project": "检测项目", "sampleNo": "样品编号",
    "department": "检测部门", "owner": "登记人员", "status": "报告状态",
    "sampleStatus": "样品状态", "dataStatus": "数据状态", "version": "报告版本",
    "sampleRegState": "登记状态", "archiveState": "归档状态", "stamped": "签章状态",
    "contractNo": "样品外部ERP立项／关联合同",
}
COMMISSION = {"sample.register.update", "sample.contract.select", "report.entrust_change.save", "report.entrust_change.complete"}
TESTING = {"report.data_entry.save", "report.data_entry.complete", "report.data_change.complete", "report.test_change.complete"}
LABELS = {"sample.register.update": "样品登记修改", "sample.contract.select": "更换样品立项", "report.entrust_change.save": "保存委托更改",
          "report.entrust_change.complete": "完成委托更改", "report.data_entry.save": "保存检测数据",
          "report.data_entry.complete": "完成检测数据", "report.data_change.complete": "完成检测更改", "report.test_change.complete": "完成检测更改",
          "report.review.pass": "审核通过", "report.review.return": "审核退回",
          "report.approval.pass": "批准通过", "report.approval.return": "批准退回",
          "report.seal.completed": "报告盖章完成", "report.archive.pass": "报告归档", "report.archive.undo": "撤销归档",
          "report.distribution.complete": "报告发放完成", "report.print.pass": "报告签发", "report.print.undo": "撤销签发"}


def _text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def report_records(report_no, kind, page, page_size):
    query = OperationAudit.query.filter_by(object_type="report", object_id=report_no, success=True)
    if kind == "commission":
        query = query.filter(OperationAudit.action.in_(COMMISSION))
    elif kind == "testing":
        query = query.filter(OperationAudit.action.in_(TESTING))
    elif kind == "issues":
        query = query.filter(OperationAudit.action.endswith(".return"))
    else:
        query = query.filter(OperationAudit.category == "workflow")
    audits = query.order_by(OperationAudit.created_at, OperationAudit.id).all()
    items = []
    for sequence, audit in enumerate(audits, 1):
        before = audit.before_data if isinstance(audit.before_data, dict) else {}
        after = audit.after_data if isinstance(audit.after_data, dict) else {}
        at = audit.created_at.isoformat(timespec="seconds") if audit.created_at else ""
        label = LABELS.get(audit.action, audit.action)
        if kind == "issues":
            info = after.get("returnInfo") or {}
            items.append(dict(id=str(audit.id), submitterId=audit.account or "",
                submitter=audit.user_name or audit.account or "", description=info.get("note") or audit.message or "",
                type=info.get("source") or label, destination=info.get("modeLabel") or info.get("target") or "",
                submittedAt=at, handlerId="", handler="", opinion="", handledAt="", sequence=sequence))
            continue
        changes = [(key, label) for key, label in FIELDS.items()
                   if key in before and key in after and before[key] != after[key]]
        # Old saves did not record per-field content. Show the real operation,
        # explicitly leaving missing values empty instead of inventing a diff.
        for key, field in changes or [(None, "操作记录（未保存字段差异）")]:
            items.append(dict(id=f"{audit.id}:{key or 'operation'}", actor=audit.user_name or audit.account or "",
                at=at, field=field, before=_text(before.get(key)), after=_text(after.get(key)),
                type=label, sequence=sequence))
    items.reverse()
    total = len(items)
    page = min(page, max(1, (total + page_size - 1) // page_size))
    return dict(items=items[(page - 1) * page_size:page * page_size], total=total, page=page, pageSize=page_size)
