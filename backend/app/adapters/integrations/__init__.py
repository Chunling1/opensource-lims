"""Public external-integration adapter contracts."""

from ...platform.architecture.public_contract import describe_module
from .dispatch import (
    InMemoryReplayLedger,
    IntegrationBusy,
    IntegrationDisabled,
    IntegrationEnvelope,
    IntegrationPermissionDenied,
    IntegrationProtocolError,
    IntegrationReplayConflict,
    IntegrationTimeout,
    dispatch_integration_command,
    integration_status,
)

MODULE_ID = "integration_adapters"
ERP_CONTRACTS: tuple[dict[str, object], ...] = ()
ERP_CUSTOMERS: tuple[dict[str, object], ...] = ()


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


def find_erp_contract(_contract_no: str):
    return None


def list_erp_contracts():
    return []


def list_erp_customers():
    return []


def customer_directory_authoritative() -> bool:
    return False


__all__ = [
    "ERP_CONTRACTS",
    "ERP_CUSTOMERS",
    "MODULE_ID",
    "InMemoryReplayLedger",
    "IntegrationBusy",
    "IntegrationDisabled",
    "IntegrationEnvelope",
    "IntegrationPermissionDenied",
    "IntegrationProtocolError",
    "IntegrationReplayConflict",
    "IntegrationTimeout",
    "contract",
    "customer_directory_authoritative",
    "dispatch_integration_command",
    "find_erp_contract",
    "integration_status",
    "list_erp_contracts",
    "list_erp_customers",
]
