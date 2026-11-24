"""Machine-readable target architecture and ownership contracts.

This package is deliberately static.  Importing it must not initialize Flask,
SQLAlchemy or any production integration.  It documents the modular-monolith
target and supplies dependency tests with one authoritative registry.
"""

from .boundaries import (
    BoundaryViolation,
    analyze_boundaries,
    analyze_source_text,
    boundary_evidence_payload,
    discover_model_shapes,
)
from .legacy_allowances import (
    LEGACY_BOUNDARY_ALLOWANCES,
    LegacyBoundaryAllowance,
    allowance_fingerprints,
    allowance_group_by_fingerprint,
)
from .registry import (
    CORE_STATE_FIELDS,
    EXTENSION_CORE_WRITE_RULES,
    FORBIDDEN_LEGACY_ADAPTER_IMPORTS,
    MODULE_REGISTRY,
    ModuleContract,
    module_contract,
    registry_payload,
    table_owner_map,
    table_reader_map,
)
from .source_map import (
    LEGACY_SHARED_FILES,
    MODULE_SOURCE_FILES,
    SourceOwnership,
    source_map_payload,
    source_ownership,
)

__all__ = [
    "BoundaryViolation",
    "CORE_STATE_FIELDS",
    "EXTENSION_CORE_WRITE_RULES",
    "FORBIDDEN_LEGACY_ADAPTER_IMPORTS",
    "LEGACY_BOUNDARY_ALLOWANCES",
    "LEGACY_SHARED_FILES",
    "MODULE_REGISTRY",
    "MODULE_SOURCE_FILES",
    "LegacyBoundaryAllowance",
    "ModuleContract",
    "SourceOwnership",
    "allowance_fingerprints",
    "allowance_group_by_fingerprint",
    "analyze_boundaries",
    "analyze_source_text",
    "boundary_evidence_payload",
    "discover_model_shapes",
    "module_contract",
    "registry_payload",
    "source_map_payload",
    "source_ownership",
    "table_owner_map",
    "table_reader_map",
]
