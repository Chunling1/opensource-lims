"""Public boundary for read-only AI search and analysis."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "intelligence"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
