"""Public ELN adapter contract."""

from ...platform.architecture.public_contract import describe_module

MODULE_ID = "eln_adapter"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


def eln_completion_error(report) -> str:
    """Resolve the ORM-backed completion query after model initialization."""

    from .completion import eln_completion_error as implementation

    return implementation(report)


__all__ = ["MODULE_ID", "contract", "eln_completion_error"]
