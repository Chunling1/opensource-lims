"""Public boundary for contracts and entrusts."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "entrust_contract"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
