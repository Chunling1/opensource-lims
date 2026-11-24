"""Public boundary for sample registration and logistics."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "sample_logistics"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
