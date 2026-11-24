"""Public boundary for isolated BIM/CAD/OCR experiments.

The HTTP adapter imports experiment execution only through this package.  The
boundary intentionally exposes no persistence API: results remain
request-scoped until a human-approved owner module Command exists.
"""

from ...experimental.bim_cad import (
    BimCadExperimentError,
    experiment_status,
    recognize_document,
    simulate_energy,
)
from ...platform.architecture.public_contract import describe_module

MODULE_ID = "experiments"


def contract() -> dict[str, object]:
    return describe_module(MODULE_ID)


def run_experiment(kind: str, payload: dict[str, object]) -> dict[str, object]:
    """Run a supported deterministic experiment without persisting output."""

    if kind != "energy-simulation":
        raise BimCadExperimentError(
            "不支持的实验类型",
            code="unsupported_experiment",
            status_code=400,
        )
    return simulate_energy(payload)


def experiment_result(result: dict[str, object]) -> dict[str, object]:
    """Return the request-scoped result; never promote it to business data."""

    return dict(result)


__all__ = [
    "BimCadExperimentError",
    "MODULE_ID",
    "contract",
    "experiment_result",
    "experiment_status",
    "recognize_document",
    "run_experiment",
    "simulate_energy",
]
