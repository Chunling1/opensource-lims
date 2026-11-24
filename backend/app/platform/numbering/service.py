"""Application boundary for monotonic, non-reusable business numbers.

The normal public allocators below deliberately commit a reservation before a
business transaction starts.  Customer-portal acceptance is the one narrower
case where the source-row compare-and-set, number waterline and formal entrust
must commit atomically.  Its reservation helpers therefore live in this owner
module, are intentionally omitted from :mod:`app.platform.numbering`, and
require an opaque capability before the entrust owner can consume the value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...models import BusinessNumberSequence
from ...numbering import _assert_clean_reservation_boundary, _entrust_serial_floor

from ...numbering import (
    allocate_entrust_number,
    allocate_external_application_number,
    allocate_report_numbers,
    peek_entrust_number,
    report_number_stem,
)


_CUSTOMER_ACCEPTANCE_CAPABILITY = object()


@dataclass(frozen=True)
class CustomerAcceptanceNumberReservation:
    """Opaque transaction-local WT reservation for customer acceptance only."""

    year: int
    serial: int
    value: str
    _capability: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._capability is not _CUSTOMER_ACCEPTANCE_CAPABILITY:
            raise TypeError("客户受理编号预留只能由业务编号模块创建")


def _customer_acceptance_scope(year: int) -> str:
    return f"entrust:{int(year)}"


def _locked_counter(scope: str, floor: int) -> BusinessNumberSequence:
    """Return a sequence row locked in the caller's existing transaction."""

    row = (
        BusinessNumberSequence.query.filter_by(scope=scope)
        .with_for_update()
        .first()
    )
    if row is not None:
        return row

    # The acceptance CAS owns SQLite's single writer lock before reaching this
    # path.  The savepoint also keeps the initialization portable when two
    # different applications create the same scope concurrently elsewhere.
    try:
        with db.session.begin_nested():
            row = BusinessNumberSequence(scope=scope, last_value=int(floor or 0))
            db.session.add(row)
            db.session.flush()
    except IntegrityError:
        row = (
            BusinessNumberSequence.query.filter_by(scope=scope)
            .with_for_update()
            .first()
        )
        if row is None:
            raise RuntimeError(f"编号计数器初始化失败：{scope}") from None
    return row


def reserve_customer_acceptance_number_in_transaction(
    year: int,
) -> CustomerAcceptanceNumberReservation:
    """Reserve one WT number without committing the caller's business transaction.

    This is an internal customer-service integration seam, not a replacement
    for :func:`allocate_entrust_number`.  The caller must already own the source
    application by atomic CAS and must either commit all acceptance facts or
    roll back and persist the returned serial as an intentional gap.
    """

    year = int(year)
    scope = _customer_acceptance_scope(year)
    floor = _entrust_serial_floor(year)
    row = _locked_counter(scope, floor)
    serial = max(int(row.last_value or 0), int(floor or 0)) + 1
    row.last_value = serial
    row.updated_at = datetime.utcnow()
    db.session.flush()
    return CustomerAcceptanceNumberReservation(
        year=year,
        serial=serial,
        value=f"WT-{year}-{serial:04d}",
        _capability=_CUSTOMER_ACCEPTANCE_CAPABILITY,
    )


def customer_acceptance_number_value(
    reservation: CustomerAcceptanceNumberReservation,
) -> str:
    """Validate and expose an opaque customer-acceptance reservation."""

    if (
        not isinstance(reservation, CustomerAcceptanceNumberReservation)
        or reservation._capability is not _CUSTOMER_ACCEPTANCE_CAPABILITY
    ):
        raise TypeError("无效的客户受理编号预留")
    return reservation.value


def persist_customer_acceptance_number_gap(
    reservation: CustomerAcceptanceNumberReservation,
) -> None:
    """Persist a rolled-back issued serial as a deliberate, non-reusable gap."""

    customer_acceptance_number_value(reservation)
    _assert_clean_reservation_boundary()
    scope = _customer_acceptance_scope(reservation.year)
    try:
        floor = _entrust_serial_floor(reservation.year)
        row = _locked_counter(scope, max(floor, reservation.serial))
        row.last_value = max(
            int(row.last_value or 0),
            int(floor or 0),
            reservation.serial,
        )
        row.updated_at = datetime.utcnow()
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        raise RuntimeError(
            f"客户受理编号空洞持久化失败：{reservation.value}"
        ) from exc


# Only ordinary allocators form the platform-wide public facade.  The customer
# acceptance helpers above are imported explicitly by their two owner Commands.
__all__ = [
    "allocate_entrust_number",
    "allocate_external_application_number",
    "allocate_report_numbers",
    "peek_entrust_number",
    "report_number_stem",
]
