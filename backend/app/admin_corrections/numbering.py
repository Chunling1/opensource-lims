"""Transactional correction of business numbers and their current references."""
import re
from copy import deepcopy

from sqlalchemy import String, Text, cast, inspect, update
from ..extensions import db
from ..models import Entrust, Report, BusinessNumberSequence, JSONText

NUMBER_FIELDS = {Entrust: ("entrust_no",),
                 Report: ("report_no", "sample_no")}
KEYS = {
    "entrust_no": {"entrustNo", "sourceEntrustNo", "entrust_no"},
    "report_no": {"reportNo", "mainReportNo", "derivedFrom", "report_no"},
    "sample_no": {"sampleNo", "sample_no", "样品编号", "样品/抽样单编号"},
}


def planned(row, before, patch):
    result = []
    for field in NUMBER_FIELDS.get(type(row), ()):
        if field not in patch or patch[field] == before.get(field):
            continue
        old, new = str(before.get(field) or ""), str(patch[field] or "").strip()
        if not old or not re.fullmatch(r"[A-Za-z0-9()\u4e00-\u9fff_-]{1,60}", new):
            raise ValueError("单号不能为空，且只能包含字母、数字、汉字、横线、下划线及括号")
        if patch[field] != new:
            raise ValueError("单号不能包含前后空格")
        max_length = row.__table__.c[field].type.length
        if len(new) > max_length:
            raise ValueError("单号超过允许长度")
        with db.session.no_autoflush:
            if type(row).query.filter(getattr(type(row), field) == new, type(row).id != row.id).first():
                raise ValueError("新单号已存在，请核对后修改")
        result.append((field, old, new))
    sample_change = next((item for item in result if item[0] == "sample_no"), None)
    if sample_change:
        _, old, new = sample_change
        # The centre prefix and derivative suffix remain intact.
        for report in Report.query.filter(Report.sample_no == old).all():
            previous_no = report.report_no
            if report.id == row.id and "report_no" in patch:
                continue
            marker = "-" + old
            if marker in previous_no:
                next_no = previous_no.replace(marker, "-" + new, 1)
                if len(next_no) > 40 or Report.query.filter(Report.report_no == next_no, Report.id != report.id).first():
                    raise ValueError("样品编号对应的报告编号已存在或过长")
                result.append(("report_no", previous_no, next_no))
    # A manual report-number correction also follows explicitly linked derivatives.
    pending = [item for item in result if item[0] == "report_no"]
    visited = {old for _, old, _ in pending}
    while pending:
        _, old, new = pending.pop(0)
        for child in Report.query.filter(Report.main_report_no == old).all():
            if child.report_no in visited or not child.report_no.startswith(old):
                continue
            replacement = new + child.report_no[len(old):]
            if len(replacement) > 40 or Report.query.filter(Report.report_no == replacement, Report.id != child.id).first():
                raise ValueError("关联报告编号已存在或过长")
            change = ("report_no", child.report_no, replacement)
            result.append(change); pending.append(change); visited.add(child.report_no)
    return result


def rewrite(value, keys, old, new):
    if isinstance(value, dict):
        return {k: new if k in keys and v == old else rewrite(v, keys, old, new) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], str) and value[0] in keys and value[1] == old:
            return [value[0], new]
        return [rewrite(v, keys, old, new) for v in value]
    return value


def apply(plan):
    """No commit: a collision, validation error or audit failure rolls back all."""
    if not plan:
        return
    outbound = None
    present = set(inspect(db.session.connection()).get_table_names())
    for field, old, new in plan:
        if field == 'report_no':
            # Use the same ORM hook as ordinary edits, also for derived reports.
            # A bulk UPDATE would bypass the confirmed-counter-review rule.
            row = db.session.query(Report).filter_by(report_no=old).with_for_update().first()
            if row is not None:
                row.report_no = new
                db.session.flush()
            db.session.execute(
                update(Report.__table__).where(Report.__table__.c.main_report_no == old).values(main_report_no=new)
            )
            for r in db.session.query(Report).filter(cast(Report.detail, Text).contains(old, autoescape=True)).all():
                original = r.detail
                revised = rewrite(deepcopy(original), KEYS["report_no"], old, new)
                if revised != original:
                    r.detail = revised
            # Primary row may already have been flushed by the edit endpoint.
            # Its hook handled indexes; do not rewrite historical JSON bodies.
            continue
        columns = {field}
        if field == "agreement_no":
            columns.add("contract_no")
        if field == "report_no":
            columns.add("main_report_no")
        # Mutable relational indexes include finance/outbound records; historical
        # payload bodies, signed files and audit before/after evidence stay intact.
        tables = {t.name: t for metadata in (db.metadata, outbound) if metadata is not None for t in metadata.tables.values()}
        for table in tables.values():
            if table.name not in present:
                continue
            for column in table.columns:
                if column.name in columns and isinstance(column.type, (String, Text)):
                    db.session.execute(update(table).where(column == old).values({column.name: new}))
        for mapper in db.Model.registry.mappers:
            model = mapper.class_
            if model.__tablename__ not in present:
                continue
            if model.__tablename__ in {"operation_audits", "report_document_versions", "compliance_acknowledgements"}:
                continue
            for column in model.__table__.columns:
                if isinstance(column.type, JSONText):
                    rows = db.session.query(model).filter(cast(column, Text).contains(old, autoescape=True)).all()
                    for row in rows:
                        original = getattr(row, column.name)
                        revised = rewrite(deepcopy(original), KEYS[field], old, new)
                        if revised != original:
                            setattr(row, column.name, revised)
        if field in ("entrust_no", "report_no"):
            from ..platform.audit import repoint_operation_audits
            repoint_operation_audits("entrust" if field == "entrust_no" else "report", old, new)
        # Keep future automatic allocation beyond a manually corrected serial.
        match = re.fullmatch(r"WT-(\d{4})-(\d+)", new) if field == "entrust_no" else (
            re.fullmatch(r"(\d{4}[A-Za-z0-9]+(?:\([IVX]+\))?(?:-[A-Za-z0-9]+)*)-(\d+)", new)
            if field == "sample_no" else None
        )
        if match:
            scope = ("entrust:" if field == "entrust_no" else "sample-report:") + match[1]
            counter = BusinessNumberSequence.query.filter_by(scope=scope).with_for_update().first()
            if counter is None:
                db.session.add(BusinessNumberSequence(scope=scope, last_value=int(match[2])))
            else:
                counter.last_value = max(counter.last_value, int(match[2]))
