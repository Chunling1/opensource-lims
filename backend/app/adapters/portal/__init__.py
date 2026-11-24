"""Public boundary for the customer portal adapter."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "customer_service"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
