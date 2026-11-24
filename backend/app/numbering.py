"""Durable business-number reservation.

Sample/report serials are shared by the ``year + report category`` stem
(for example ``2026M``), regardless of the testing-centre prefix.  Persisted
counters are committed before the surrounding business transaction begins.
Voiding, deleting, or rolling back a business record therefore cannot make an
issued number available again; a failed operation deliberately leaves a gap.
"""
import re
from datetime import datetime

from sqlalchemy import case
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import (
    BusinessNumberSequence,
    DataMigrationBatch,
    Entrust,
    ExternalEntrustApplication,
    OperationAudit,
    Report,
)

REPORT_PREFIX_RE = re.compile(r"^(?P<center>[A-Za-z0-9]+)-(?P<stem>\d{4}[A-Za-z0-9]+(?:\([IVX]+\))?(?:-[A-Za-z0-9]+)*)$")
ENTRUST_NO_RE = re.compile(r"^WT-(?P<year>\d{4})-(?P<serial>\d+)$")
EXTERNAL_APPLICATION_NO_RE = re.compile(r"^ON-(?P<year>\d{4})-(?P<serial>\d+)$")


def report_number_stem(prefix):
    match = REPORT_PREFIX_RE.fullmatch(str(prefix or "").strip())
    if not match:
        raise ValueError("报告编号前缀格式无效，应为“检测中心-年份检测类别”，例如 LAB-2026M")
    return match.group("center").upper(), match.group("stem").upper()


def _serial_from_report_value(value, stem):
    match = re.search(rf"(?:^|-){re.escape(stem)}-(\d+)$", str(value or ""), re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _numbering_migration(stem):
    """Explicit imported numbering boundary; previous audits remain intact."""
    row = db.session.query(DataMigrationBatch).filter(
        DataMigrationBatch.batch_id.like("sample-number-reset:%"),
        DataMigrationBatch.status == "completed",
    ).order_by(DataMigrationBatch.created_at.desc()).first()
    if row is None:
        return None
    policy = (row.manifest or {}).get("sample_numbering") or {}
    if str(policy.get("year")) != stem[:4]:
        return None
    return policy


def _report_serial_floor(stem):
    migration = _numbering_migration(stem)
    maximum = int((migration or {}).get("baselines", {}).get(stem, 0))
    for sample_no, report_no in db.session.query(Report.sample_no, Report.report_no).all():
        maximum = max(
            maximum,
            _serial_from_report_value(sample_no, stem),
            _serial_from_report_value(report_no, stem),
        )
    # Audit object ids preserve allocated report numbers even if a record is
    # ever physically removed by maintenance.
    audit_ids = db.session.query(OperationAudit.object_id).filter(
        OperationAudit.object_type == "report",
    )
    if migration:
        audit_ids = audit_ids.filter(OperationAudit.id > int(migration["audit_cutoff"]))
    for (object_id,) in audit_ids:
        maximum = max(maximum, _serial_from_report_value(object_id, stem))
    return maximum


def _entrust_serial_floor(year):
    maximum = 0
    for (entrust_no,) in db.session.query(Entrust.entrust_no).all():
        match = ENTRUST_NO_RE.fullmatch(str(entrust_no or ""))
        if match and int(match.group("year")) == year:
            maximum = max(maximum, int(match.group("serial")))
    audit_ids = db.session.query(OperationAudit.object_id).filter(
        OperationAudit.object_type == "entrust",
    ).all()
    for (object_id,) in audit_ids:
        match = ENTRUST_NO_RE.fullmatch(str(object_id or ""))
        if match and int(match.group("year")) == year:
            maximum = max(maximum, int(match.group("serial")))
    return maximum


def _external_application_serial_floor(year):
    maximum = 0
    for (application_no,) in db.session.query(
        ExternalEntrustApplication.application_no
    ).all():
        match = EXTERNAL_APPLICATION_NO_RE.fullmatch(str(application_no or ""))
        if match and int(match.group("year")) == year:
            maximum = max(maximum, int(match.group("serial")))
    return maximum


def _counter_value(scope):
    value = db.session.query(BusinessNumberSequence.last_value).filter(
        BusinessNumberSequence.scope == scope,
    ).scalar()
    return int(value or 0)


def _assert_clean_reservation_boundary():
    if db.session.new or db.session.dirty or db.session.deleted:
        raise RuntimeError("编号分配必须在业务写入前执行，当前事务存在未提交修改")


def _advance_counter(scope, floor):
    """Reserve and durably commit one serial before business rows are written.

    The caller must invoke numbering at a clean transaction boundary.  This
    prevents a sequence reservation from accidentally committing unrelated
    pending business changes.  Read-only identity-map contents are allowed and
    will simply be expired by the reservation commit.
    """

    _assert_clean_reservation_boundary()
    row = BusinessNumberSequence.query.filter_by(scope=scope).first()
    if row is None:
        try:
            db.session.add(BusinessNumberSequence(scope=scope, last_value=int(floor or 0)))
            db.session.flush()
        except IntegrityError:
            # A concurrent creator inserted the same scope first. No other
            # business changes exist at this allocation point, so retry safely.
            db.session.rollback()

    next_value = case(
        (BusinessNumberSequence.last_value < int(floor or 0), int(floor or 0) + 1),
        else_=BusinessNumberSequence.last_value + 1,
    )
    updated = BusinessNumberSequence.query.filter_by(scope=scope).update(
        {
            BusinessNumberSequence.last_value: next_value,
            BusinessNumberSequence.updated_at: datetime.utcnow(),
        },
        synchronize_session=False,
    )
    if updated != 1:
        raise RuntimeError(f"编号计数器初始化失败：{scope}")
    db.session.flush()
    reserved = _counter_value(scope)
    # This commit is intentional and limited to the sequence row: a later
    # business rollback must never release the reserved serial for reuse.
    db.session.commit()
    return reserved


def allocate_report_numbers(prefix):
    _assert_clean_reservation_boundary()
    center, stem = report_number_stem(prefix)
    serial = _advance_counter(f"sample-report:{stem}", _report_serial_floor(stem))
    sample_no = f"{stem}-{serial:04d}"
    return f"{center}-{sample_no}", sample_no


def peek_entrust_number(year):
    year = int(year)
    floor = max(_entrust_serial_floor(year), _counter_value(f"entrust:{year}"))
    return f"WT-{year}-{floor + 1:04d}"


def allocate_entrust_number(year):
    _assert_clean_reservation_boundary()
    year = int(year)
    serial = _advance_counter(f"entrust:{year}", _entrust_serial_floor(year))
    return f"WT-{year}-{serial:04d}"


def allocate_external_application_number(year):
    """Allocate a public application number without consuming a WT number."""
    _assert_clean_reservation_boundary()
    year = int(year)
    serial = _advance_counter(
        f"external-entrust:{year}", _external_application_serial_floor(year)
    )
    return f"ON-{year}-{serial:06d}"
