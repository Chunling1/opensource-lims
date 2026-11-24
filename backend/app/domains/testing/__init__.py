"""Public boundary for test tasks and original records."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "testing_records"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
