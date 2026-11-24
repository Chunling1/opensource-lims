"""Static boundary analysis for the incremental modular-monolith migration.

This analyzer deliberately uses only the Python standard library.  It can run
before Flask, a database driver or a production configuration is available and
therefore forms part of the fail-closed merge/release gate.

It is a conservative structural check, not a replacement for runtime tests.
The analyzer catches recognizable direct writes and adapter coupling; database
integration and permission tests remain responsible for behavioural proof.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from .registry import MODULE_REGISTRY, table_owner_map
from .source_map import normalize_source_path, source_ownership

CORE_DOMAIN_MODULES = frozenset({
    "entrust_contract",
    "sample_logistics",
    "testing_records",
    "report_lifecycle",
    "quality_resources",
    "finance_billing",
})

WRITE_COLLECTION_METHODS = frozenset({"append", "clear", "extend", "remove"})


@dataclass(frozen=True)
class ModelShape:
    class_name: str
    table_name: str
    fields: frozenset[str]


@dataclass(frozen=True)
class BoundaryViolation:
    """Stable, serializable evidence for one static boundary violation."""

    rule_id: str
    fingerprint: str
    source_path: str
    source_scope: str
    target: str
    operation: str
    detail: str
    line: int

    def evidence(self) -> dict[str, object]:
        return asdict(self)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _is_model_field_value(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func).split(".")[-1] in {
        "Column",
        "relationship",
    }


def discover_model_shapes(app_root: Path) -> dict[str, ModelShape]:
    """Discover class/table/field names without importing SQLAlchemy models."""

    files = [app_root / "models.py", *sorted((app_root / "data_models").glob("*.py"))]
    shapes: dict[str, ModelShape] = {}
    for path in files:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            table_name = ""
            fields: set[str] = set()
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "__tablename__"
                            and isinstance(statement.value, ast.Constant)
                            and isinstance(statement.value.value, str)
                        ):
                            table_name = statement.value.value
                        elif isinstance(target, ast.Name) and _is_model_field_value(statement.value):
                            fields.add(target.id)
            if table_name:
                if node.name in shapes:
                    raise ValueError(f"duplicate ORM model class: {node.name}")
                shapes[node.name] = ModelShape(node.name, table_name, frozenset(fields))
    return shapes


def _module_name(app_root: Path, path: Path) -> str:
    relative = path.relative_to(app_root.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_import(current_module: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    current_parts = current_module.split(".")
    package_parts = current_parts if current_module.endswith(".__init__") else current_parts[:-1]
    ascend = max(node.level - 1, 0)
    if ascend:
        package_parts = package_parts[:-ascend]
    module_parts = (node.module or "").split(".") if node.module else []
    return ".".join([*package_parts, *module_parts])


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _node_signature(node: ast.AST) -> str:
    payload = ast.dump(node, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _violation_fingerprint(
    *,
    rule_id: str,
    source_path: str,
    source_scope: str,
    target: str,
    operation: str,
    node_signature: str,
    occurrence: int,
) -> str:
    payload = {
        "ruleId": rule_id,
        "sourcePath": source_path,
        "sourceScope": source_scope,
        "target": target,
        "operation": operation,
        "nodeSignature": node_signature,
        "occurrence": occurrence,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _BoundaryVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        source_path: str,
        current_module: str,
        source_module_id: str | None,
        source_layer: str | None,
        model_shapes: dict[str, ModelShape],
    ) -> None:
        self.source_path = source_path
        self.current_module = current_module
        self.source_module_id = source_module_id
        self.source_layer = source_layer
        self.model_shapes = model_shapes
        self.table_owners = table_owner_map()
        self.model_aliases: dict[str, str] = {}
        self.scope_stack: list[str] = ["<module>"]
        self.bindings_stack: list[dict[str, str]] = [{}]
        self.violations: list[BoundaryViolation] = []
        self._occurrences: dict[tuple[str, ...], int] = {}

    @property
    def scope(self) -> str:
        return ".".join(self.scope_stack)

    @property
    def bindings(self) -> dict[str, str]:
        return self.bindings_stack[-1]

    def _record(
        self,
        *,
        rule_id: str,
        node: ast.AST,
        target: str,
        operation: str,
        detail: str,
    ) -> None:
        signature = _node_signature(node)
        occurrence_key = (
            rule_id,
            self.source_path,
            self.scope,
            target,
            operation,
            signature,
        )
        occurrence = self._occurrences.get(occurrence_key, 0) + 1
        self._occurrences[occurrence_key] = occurrence
        fingerprint = _violation_fingerprint(
            rule_id=rule_id,
            source_path=self.source_path,
            source_scope=self.scope,
            target=target,
            operation=operation,
            node_signature=signature,
            occurrence=occurrence,
        )
        self.violations.append(BoundaryViolation(
            rule_id=rule_id,
            fingerprint=fingerprint,
            source_path=self.source_path,
            source_scope=self.scope,
            target=target,
            operation=operation,
            detail=detail,
            line=getattr(node, "lineno", 0),
        ))

    def _model_for_name(self, name: str) -> str | None:
        for bindings in reversed(self.bindings_stack):
            if name in bindings:
                return bindings[name]
        if name in self.model_aliases:
            return self.model_aliases[name]
        candidates = {
            class_name: class_name
            for class_name in self.model_shapes
            if name in {class_name.lower(), _snake_case(class_name)}
        }
        if len(candidates) == 1:
            return next(iter(candidates.values()))
        return None

    def _model_from_expr(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return self._model_for_name(node.id)
        if isinstance(node, ast.Attribute):
            return self._model_from_expr(node.value)
        if isinstance(node, ast.Subscript):
            return self._model_from_expr(node.value)
        if isinstance(node, ast.Call):
            call = _call_name(node.func)
            if call.endswith("session.get") and node.args:
                return self._model_from_expr(node.args[0])
            return self._model_from_expr(node.func)
        return None

    def _model_target(self, model_name: str) -> tuple[ModelShape, str | None]:
        shape = self.model_shapes[model_name]
        return shape, self.table_owners.get(shape.table_name)

    def _record_write(
        self,
        *,
        node: ast.AST,
        model_name: str,
        operation: str,
    ) -> None:
        if not self.source_module_id:
            return
        shape, owner = self._model_target(model_name)
        if not owner or owner == self.source_module_id:
            return
        target = f"{model_name}({shape.table_name})"
        detail = (
            f"{self.source_module_id} performs {operation} on {target}, "
            f"owned by {owner}"
        )
        self._record(
            rule_id="non_owner_orm_write",
            node=node,
            target=target,
            operation=operation,
            detail=detail,
        )
        if self.source_layer == "extension" and owner in CORE_DOMAIN_MODULES:
            self._record(
                rule_id="extension_core_orm_write",
                node=node,
                target=target,
                operation=operation,
                detail=detail,
            )

    def _bind_target(self, target: ast.AST, model_name: str | None) -> None:
        if not model_name:
            return
        if isinstance(target, ast.Name):
            self.bindings[target.id] = model_name
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._bind_target(item, model_name)

    def _check_assignment_target(self, node: ast.AST, target: ast.AST) -> None:
        if isinstance(target, (ast.Tuple, ast.List)):
            for child in target.elts:
                self._check_assignment_target(node, child)
            return
        if not isinstance(target, ast.Attribute):
            return
        model_name = self._model_from_expr(target.value)
        if not model_name:
            return
        shape = self.model_shapes[model_name]
        # Known columns/relationships are definitive.  A dynamically attached
        # helper attribute is not treated as a database write.
        if target.attr in shape.fields:
            self._record_write(
                node=node,
                model_name=model_name,
                operation=f"assign.{target.attr}",
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        resolved = _resolve_import(self.current_module, node)
        if resolved in {"app.models"} or resolved.startswith("app.data_models."):
            for alias in node.names:
                if alias.name in self.model_shapes:
                    self.model_aliases[alias.asname or alias.name] = alias.name
        if resolved.startswith("app.blueprints.") and resolved != self.current_module:
            imported = ",".join(sorted(alias.name for alias in node.names))
            self._record(
                rule_id="blueprint_private_import",
                node=node,
                target=resolved,
                operation=f"import.{imported}",
                detail="Blueprint modules are HTTP adapters and may not import each other",
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope_stack.append(node.name)
        inferred: dict[str, str] = {}
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            model = self._model_for_name(arg.arg)
            if model:
                inferred[arg.arg] = model
        self.bindings_stack.append(inferred)
        for statement in node.body:
            self.visit(statement)
        self.bindings_stack.pop()
        self.scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_stack.append(node.name)
        self.bindings_stack.append({})
        for statement in node.body:
            self.visit(statement)
        self.bindings_stack.pop()
        self.scope_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_assignment_target(node, target)
        model = self._model_from_expr(node.value)
        for target in node.targets:
            self._bind_target(target, model)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._check_assignment_target(node, node.target)
        self._bind_target(node.target, self._model_from_expr(node.value))
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_assignment_target(node, node.target)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._bind_target(node.target, self._model_from_expr(node.iter))
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_Call(self, node: ast.Call) -> None:
        call = _call_name(node.func)
        if isinstance(node.func, ast.Name) and node.func.id in self.model_aliases:
            self._record_write(
                node=node,
                model_name=self.model_aliases[node.func.id],
                operation="construct",
            )
        elif call.endswith("session.add") and node.args:
            added = self._model_from_expr(node.args[0])
            if added:
                self._record_write(node=node, model_name=added, operation="session.add")
        elif call.endswith("session.add_all") and node.args:
            collection = node.args[0]
            if isinstance(collection, (ast.List, ast.Tuple, ast.Set)):
                for item in collection.elts:
                    added = self._model_from_expr(item)
                    if added:
                        self._record_write(node=item, model_name=added, operation="session.add_all")
        elif call.endswith("session.delete") and node.args:
            deleted = self._model_from_expr(node.args[0])
            if deleted:
                self._record_write(node=node, model_name=deleted, operation="session.delete")
        elif isinstance(node.func, ast.Attribute) and node.func.attr in {"update", "delete"}:
            target_model = self._model_from_expr(node.func.value)
            if target_model:
                self._record_write(
                    node=node,
                    model_name=target_model,
                    operation=f"query.{node.func.attr}",
                )
        elif (
            isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and node.args
        ):
            target_model = self._model_from_expr(node.args[0])
            if target_model:
                field = "dynamic"
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    field = str(node.args[1].value)
                self._record_write(
                    node=node,
                    model_name=target_model,
                    operation=f"setattr.{field}",
                )
        elif isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_COLLECTION_METHODS:
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute):
                target_model = self._model_from_expr(receiver.value)
                if target_model and receiver.attr in self.model_shapes[target_model].fields:
                    self._record_write(
                        node=node,
                        model_name=target_model,
                        operation=f"relationship.{receiver.attr}.{node.func.attr}",
                    )
        self.generic_visit(node)


def iter_python_sources(app_root: Path) -> Iterator[Path]:
    for path in sorted(app_root.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


def analyze_boundaries(app_root: Path) -> list[BoundaryViolation]:
    """Analyze every mapped module source and return stable violations."""

    model_shapes = discover_model_shapes(app_root)
    violations: list[BoundaryViolation] = []
    for path in iter_python_sources(app_root):
        relative = f"app/{path.relative_to(app_root).as_posix()}"
        ownership = source_ownership(relative)
        if ownership is None or ownership.kind != "module":
            continue
        current_module = _module_name(app_root, path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        contract = MODULE_REGISTRY[ownership.owner_module]
        visitor = _BoundaryVisitor(
            source_path=relative,
            current_module=current_module,
            source_module_id=ownership.owner_module,
            source_layer=contract.layer,
            model_shapes=model_shapes,
        )
        visitor.visit(tree)
        violations.extend(visitor.violations)
    return sorted(
        violations,
        key=lambda row: (
            row.rule_id,
            row.source_path,
            row.source_scope,
            row.target,
            row.operation,
            row.fingerprint,
        ),
    )


def analyze_source_text(
    app_root: Path,
    *,
    source_path: str,
    source_text: str,
) -> list[BoundaryViolation]:
    """Analyze synthetic source using the production mapping and model schema.

    This small public seam exists so the gate can test its own detectors.  It
    never imports or executes the supplied source text.
    """

    normalized = normalize_source_path(source_path)
    ownership = source_ownership(normalized)
    if ownership is None:
        raise ValueError(f"cannot analyze unmapped source path: {normalized}")
    if ownership.kind != "module" or not ownership.owner_module:
        raise ValueError(f"synthetic analysis requires a single-owner module: {normalized}")
    relative = normalized.removeprefix("app/")
    module_parts = list(Path(relative).with_suffix("").parts)
    if module_parts[-1] == "__init__":
        module_parts.pop()
    current_module = ".".join(("app", *module_parts))
    visitor = _BoundaryVisitor(
        source_path=normalized,
        current_module=current_module,
        source_module_id=ownership.owner_module,
        source_layer=MODULE_REGISTRY[ownership.owner_module].layer,
        model_shapes=discover_model_shapes(app_root),
    )
    visitor.visit(ast.parse(source_text, filename=normalized))
    return sorted(
        visitor.violations,
        key=lambda row: (
            row.rule_id,
            row.source_path,
            row.source_scope,
            row.target,
            row.operation,
            row.fingerprint,
        ),
    )


def boundary_evidence_payload(violations: Iterable[BoundaryViolation]) -> dict[str, object]:
    rows = list(violations)
    return {
        "schemaVersion": "architecture-boundary-evidence.v1",
        "violations": [row.evidence() for row in rows],
        "fingerprints": sorted(row.fingerprint for row in rows),
    }


__all__ = [
    "BoundaryViolation",
    "CORE_DOMAIN_MODULES",
    "ModelShape",
    "analyze_boundaries",
    "analyze_source_text",
    "boundary_evidence_payload",
    "discover_model_shapes",
    "iter_python_sources",
]
