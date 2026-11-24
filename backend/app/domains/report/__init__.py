"""Public boundary for the report lifecycle."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "report_lifecycle"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
