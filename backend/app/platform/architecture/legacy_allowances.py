"""Temporary semantic boundary allowances.

All catalogued cross-Blueprint imports and non-owner ORM writes now use
public module contracts.  The empty tuple is intentional: future violations
must fail the gate instead of silently becoming new debt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyBoundaryAllowance:
    rule_id: str
    source_path: str
    reason: str
    impact_modules: tuple[str, ...]
    fingerprints: tuple[str, ...]


LEGACY_BOUNDARY_ALLOWANCES: tuple[LegacyBoundaryAllowance, ...] = ()


def allowance_fingerprints() -> frozenset[str]:
    return frozenset()


def allowance_group_by_fingerprint() -> dict[str, LegacyBoundaryAllowance]:
    return {}


__all__ = [
    "LEGACY_BOUNDARY_ALLOWANCES",
    "LegacyBoundaryAllowance",
    "allowance_fingerprints",
    "allowance_group_by_fingerprint",
]
