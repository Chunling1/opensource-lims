"""Canonical Commands that create or mutate formal entrust records.

The customer portal is an adapter over the internal entrust domain.  It may
prepare an immutable input projection, but only this owner-module boundary may
construct and persist an :class:`Entrust` row.  The caller owns the surrounding
transaction so the source application, formal entrust, event and audit commit
atomically.
"""

from __future__ import annotations
from ...workflow_dates import business_today

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from ...extensions import db
from ...models import Entrust
from ...platform.numbering import allocate_entrust_number
from ...platform.numbering.service import (
    CustomerAcceptanceNumberReservation,
    customer_acceptance_number_value,
)


@dataclass(frozen=True)
class EntrustCreationInput:
    """Transport-neutral values required to create one formal entrust."""

    client: str
    project_name: str
    project_type: str
    amount: str
    department: str
    owner: str
    info: Mapping[str, Any]


def _create_external_portal_entrust(
    command: EntrustCreationInput,
    entrust_no: str,
) -> Entrust:
    """Construct the owner row after its number has been validly reserved."""

    info = dict(command.info)
    info["entrustNo"] = entrust_no
    entrust = Entrust(
        entrust_no=entrust_no,
        contract_no="",
        client=command.client,
        project_name=command.project_name,
        project_type=command.project_type,
        amount=command.amount,
        department=command.department,
        owner=command.owner,
        info=info,
        status="委托中",
    )
    db.session.add(entrust)
    db.session.flush()
    return entrust


def create_external_portal_entrust(command: EntrustCreationInput) -> Entrust:
    """Create, add and flush a formal entrust sourced from the public portal.

    Number reservation is durably committed before this Command constructs a
    business row, so a later failure leaves an intentional numbering gap.  The
    formal entrust and customer-service acceptance rows still share the caller's
    business transaction.  A flush supplies the primary key for that link.
    """

    entrust_no = allocate_entrust_number(business_today().year)
    return _create_external_portal_entrust(command, entrust_no)


def create_external_portal_entrust_from_customer_acceptance(
    command: EntrustCreationInput,
    reservation: CustomerAcceptanceNumberReservation,
) -> Entrust:
    """Consume the opaque in-transaction reservation from customer service.

    Keeping this as a dedicated owner Command prevents arbitrary callers from
    passing a raw WT string and bypassing the normal numbering contract.
    """

    return _create_external_portal_entrust(
        command,
        customer_acceptance_number_value(reservation),
    )


__all__ = [
    "EntrustCreationInput",
    "create_external_portal_entrust",
    "create_external_portal_entrust_from_customer_acceptance",
]
