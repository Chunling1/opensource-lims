"""Public boundary for billing and settlement."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "finance_billing"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
