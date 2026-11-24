"""Public boundary for standards, capabilities, equipment and personnel."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "quality_resources"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


__all__ = ["MODULE_ID", "contract"]
