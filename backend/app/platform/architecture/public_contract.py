"""Public module descriptors for the incremental modular monolith.

The physical packages introduced by the local governance copy expose only
metadata at first.  They do not move ORM tables or change runtime behavior.
Existing code can migrate behind these public boundaries one command/query at
a time while the public API stays compatible.
"""

from __future__ import annotations

from dataclasses import asdict

from .registry import MODULE_REGISTRY


def describe_module(module_id: str) -> dict[str, object]:
    """Return the authoritative public contract for one registered module."""

    try:
        contract = MODULE_REGISTRY[module_id]
    except KeyError as exc:
        raise ValueError(f"unknown module: {module_id}") from exc
    return asdict(contract)


def public_commands(module_id: str) -> tuple[str, ...]:
    return MODULE_REGISTRY[module_id].command_surface


def public_queries(module_id: str) -> tuple[str, ...]:
    return MODULE_REGISTRY[module_id].query_surface


def public_events(module_id: str) -> tuple[str, ...]:
    return MODULE_REGISTRY[module_id].event_surface


__all__ = [
    "describe_module",
    "public_commands",
    "public_events",
    "public_queries",
]
