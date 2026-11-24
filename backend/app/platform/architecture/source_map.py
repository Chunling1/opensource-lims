"""Machine-readable source ownership for the modular monolith.

The table registry answers who owns *data*.  This module answers who owns a
Python source file.  Existing multi-purpose files are deliberately marked as
``legacyShared`` together with the exact modules whose tests they affect.

The mapping is intentionally fail-closed:

* a source file must resolve to exactly one module or one ``legacyShared``
  entry;
* exact entries must point at a file that still exists (stale entries fail);
* target package roots are the only prefix mappings, so a new loose file under
  ``app/`` is not silently assigned to an arbitrary module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Literal

from .registry import MODULE_REGISTRY

SourceKind = Literal["module", "legacyShared"]


@dataclass(frozen=True)
class SourceOwnership:
    """Resolved ownership and test impact for one backend source file."""

    source_path: str
    kind: SourceKind
    owner_module: str | None
    impact_modules: tuple[str, ...]
    rationale: str


ALL_MODULES = tuple(MODULE_REGISTRY)


# Exact legacy locations that already have one clear logical owner.  Moving a
# file into its target package later does not change the logical owner; it only
# removes the corresponding exact entry below.
MODULE_SOURCE_FILES: dict[str, str] = {
    "app/applications/customer_service/__init__.py": "customer_service",
    "app/applications/customer_service/commands.py": "customer_service",
    "app/applications/entrust/__init__.py": "entrust_contract",
    "app/applications/entrust/commands.py": "entrust_contract",
    "app/applications/sample_logistics/__init__.py": "sample_logistics",
    "app/applications/sample_logistics/commands.py": "sample_logistics",
    "app/applications/testing_records/__init__.py": "testing_records",
    "app/applications/testing_records/commands.py": "testing_records",
    "app/applications/report_lifecycle/__init__.py": "report_lifecycle",
    "app/applications/report_lifecycle/commands.py": "report_lifecycle",
    "app/applications/report_lifecycle/projections.py": "report_lifecycle",
    "app/applications/report_lifecycle/queries.py": "report_lifecycle",
    "app/applications/quality_resources/__init__.py": "quality_resources",
    "app/applications/quality_resources/commands.py": "quality_resources",
    # Appointment authorization owns project/step/user grants; its small
    # quality roster projection is delegated through a public Command.
    "app/appointment_authorizations.py": "platform_identity",
    "app/audit.py": "audit_trace",
    "app/authorization_scope.py": "platform_identity",
    "app/blueprints/admin.py": "platform_identity",
    "app/blueprints/ai.py": "intelligence",
    "app/blueprints/attachments.py": "report_lifecycle",
    "app/blueprints/auth.py": "platform_identity",
    "app/blueprints/bim_cad.py": "experiments",
    "app/blueprints/customers.py": "customer_service",
    "app/blueprints/eln.py": "eln_adapter",
    "app/blueprints/eln_integration.py": "eln_adapter",
    "app/blueprints/entrust.py": "entrust_contract",
    "app/blueprints/finance.py": "finance_billing",
    "app/blueprints/erp.py": "integration_adapters",
    "app/blueprints/public_portal.py": "customer_service",
    "app/blueprints/quality.py": "quality_resources",
    "app/blueprints/report_documents.py": "report_lifecycle",
    "app/blueprints/reports.py": "report_lifecycle",
    "app/blueprints/samples.py": "sample_logistics",
    "app/business_read_only.py": "workflow_core",
    "app/cnas_capabilities.py": "quality_resources",
    "app/cover_render.py": "report_lifecycle",
    "app/covers.py": "report_lifecycle",
    "app/data_models/eln.py": "eln_adapter",
    "app/data_models/files.py": "file_vault",
    "app/data_models/public_portal.py": "customer_service",
    "app/data_models/reference_imports.py": "integration_adapters",
    "app/docx_pdf.py": "report_lifecycle",
    "app/entrust_render.py": "entrust_contract",
    "app/experimental/bim_cad/__init__.py": "experiments",
    "app/experimental/bim_cad/energy_calc.py": "experiments",
    "app/experimental/bim_cad/engine.py": "experiments",
    "app/experimental/bim_cad/floorplan_onnx.py": "experiments",
    "app/external_side_effects.py": "integration_adapters",
    "app/finance_service.py": "finance_billing",
    "app/forms/ai_forms.py": "intelligence",
    "app/forms/reference_data.py": "quality_resources",
    "app/functions/ai_analysis.py": "intelligence",
    "app/functions/ai_index.py": "intelligence",
    "app/functions/ai_provider.py": "intelligence",
    "app/functions/file_migration.py": "file_vault",
    "app/functions/portal_assistant.py": "customer_service",
    "app/functions/reference_data_import.py": "integration_adapters",
    "app/functions/service_catalog.py": "customer_service",
    "app/functions/stored_files.py": "file_vault",
    "app/library.py": "quality_resources",
    "app/numbering.py": "business_numbering",
    # Account provisioning is the platform identity owner boundary.  The
    # companion quality roster is updated through quality public Commands.
    "app/personnel_accounts.py": "platform_identity",
    # This legacy-location service mutates the Report aggregate while applying
    # workflow policy; data ownership therefore belongs to report_lifecycle.
    "app/project_workflow.py": "report_lifecycle",
    "app/public_security.py": "customer_service",
    "app/report_documents.py": "report_lifecycle",
    "app/security.py": "platform_identity",
    "app/standard_control.py": "quality_resources",
    "app/status_machine.py": "workflow_core",
    "app/storage/__init__.py": "file_vault",
    "app/storage/local.py": "file_vault",
    "app/workflow_dates.py": "workflow_core",
}


# Files that still combine responsibilities.  Each entry names the complete
# reverse-dependency test impact.  New files must not be added here casually;
# this is a migration debt ledger, not a general ignore list.
LEGACY_SHARED_FILES: dict[str, tuple[str, ...]] = {
    "app/__init__.py": ALL_MODULES,
    "app/adapters/__init__.py": (
        "customer_service", "eln_adapter", "intelligence",
        "integration_adapters", "experiments",
    ),
    "app/applications/__init__.py": ALL_MODULES,
    "app/blueprints/__init__.py": ALL_MODULES,
    "app/blueprints/exports.py": (
        "platform_identity", "entrust_contract", "sample_logistics",
        "report_lifecycle", "quality_resources", "finance_billing",
    ),
    "app/business_rows.py": (
        "entrust_contract", "sample_logistics", "testing_records",
        "report_lifecycle", "finance_billing", "intelligence",
    ),
    "app/catalog.py": (
        "platform_identity", "workflow_core", "quality_resources",
    ),
    "app/checks.py": (
        "testing_records", "report_lifecycle", "quality_resources",
    ),
    "app/commands.py": ALL_MODULES,
    "app/compliance.py": (
        "testing_records", "report_lifecycle", "quality_resources",
        "audit_trace",
    ),
    "app/data_models/__init__.py": ALL_MODULES,
    "app/domains/__init__.py": (
        "entrust_contract", "sample_logistics", "testing_records",
        "report_lifecycle", "quality_resources", "finance_billing",
    ),
    "app/extensions.py": ALL_MODULES,
    "app/forms/__init__.py": (
        "quality_resources", "intelligence", "integration_adapters",
    ),
    "app/functions/__init__.py": (
        "file_vault", "quality_resources", "customer_service",
        "intelligence", "integration_adapters",
    ),
    "app/functions/database_compat.py": ALL_MODULES,
    "app/models.py": ALL_MODULES,
    "app/platform/__init__.py": (
        "platform_identity", "workflow_core", "audit_trace", "file_vault",
        "business_numbering",
    ),
    "app/sample_entrust.py": (
        "entrust_contract", "sample_logistics", "testing_records",
        "report_lifecycle",
    ),
    "app/seed.py": ALL_MODULES,
    "app/seed_data.py": ALL_MODULES,
}


def _target_package_roots() -> tuple[tuple[str, str], ...]:
    roots = []
    for module_id, contract in MODULE_REGISTRY.items():
        root = contract.target_package.replace(".", "/")
        roots.append((f"{root}/", module_id))
    # Longest path first prevents a future nested package from being claimed by
    # a shorter package root.
    return tuple(sorted(roots, key=lambda item: len(item[0]), reverse=True))


TARGET_PACKAGE_ROOTS = _target_package_roots()
GOVERNANCE_ROOT = "app/platform/architecture/"


def normalize_source_path(source_path: str) -> str:
    """Return a repository-independent POSIX path rooted at ``app/``."""

    normalized = PurePosixPath(source_path.replace("\\", "/")).as_posix()
    if normalized.startswith("backend/"):
        normalized = normalized[len("backend/"):]
    return normalized


def source_ownership(source_path: str) -> SourceOwnership | None:
    """Resolve a Python source path, or return ``None`` when it is unmapped."""

    path = normalize_source_path(source_path)
    exact_module = MODULE_SOURCE_FILES.get(path)
    exact_shared = LEGACY_SHARED_FILES.get(path)
    if exact_module and exact_shared:
        raise ValueError(f"source path has two ownership entries: {path}")
    if exact_module:
        return SourceOwnership(
            source_path=path,
            kind="module",
            owner_module=exact_module,
            impact_modules=(exact_module,),
            rationale="legacy location with one logical owner",
        )
    if exact_shared:
        return SourceOwnership(
            source_path=path,
            kind="legacyShared",
            owner_module=None,
            impact_modules=exact_shared,
            rationale="existing multi-module source; change requires full impact tests",
        )
    if path.startswith(GOVERNANCE_ROOT):
        return SourceOwnership(
            source_path=path,
            kind="legacyShared",
            owner_module=None,
            impact_modules=ALL_MODULES,
            rationale="architecture governance affects every module",
        )
    for root, module_id in TARGET_PACKAGE_ROOTS:
        if path.startswith(root):
            return SourceOwnership(
                source_path=path,
                kind="module",
                owner_module=module_id,
                impact_modules=(module_id,),
                rationale="file is inside the registered target package",
            )
    return None


def source_map_payload() -> dict[str, object]:
    """Return the static source mapping for release/test evidence."""

    return {
        "schemaVersion": "architecture-source-map.v1",
        "moduleFiles": dict(sorted(MODULE_SOURCE_FILES.items())),
        "legacyShared": {
            path: list(modules)
            for path, modules in sorted(LEGACY_SHARED_FILES.items())
        },
        "targetPackageRoots": [
            {"path": root, "moduleId": module_id}
            for root, module_id in TARGET_PACKAGE_ROOTS
        ],
        "example": asdict(source_ownership("app/models.py")),
    }


__all__ = [
    "ALL_MODULES",
    "GOVERNANCE_ROOT",
    "LEGACY_SHARED_FILES",
    "MODULE_SOURCE_FILES",
    "SourceOwnership",
    "TARGET_PACKAGE_ROOTS",
    "normalize_source_path",
    "source_map_payload",
    "source_ownership",
]
