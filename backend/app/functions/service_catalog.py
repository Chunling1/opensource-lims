"""Capability-driven public service object catalogue.

The authoritative sources remain Project, CapabilityEntry and
StdLibraryItem.  ExternalScheme only stores a reproducible public snapshot so
public pages never guess qualifications or query broad internal tables.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy.orm import joinedload

from ..platform.audit import add_operation_audit
from ..data_models.public_portal import ExternalScheme
from ..extensions import db
from ..models import CapabilityEntry, Project

BUSINESS_DEPARTMENTS = (
    "热工系统检测部",
    "建筑光学检测部",
    "净化技术检测部",
    "建筑热工检测部",
    "空调及净化系统工程检测部",
    "绿建检测一部",
    "围护结构检测部",
    "综合检测部",
    "建筑智能电气检测部",
    "空调设备检测部",
    "供暖设备检测部",
    "热工设备检测部",
)
MAX_OBJECTS_PER_DEPARTMENT = 6
MAX_PUBLIC_ITEMS = 6
ALLOWED_IMAGE_LICENSES = {
    "CC0",
    "Public domain",
    "CC BY 2.0",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 2.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
}


def _normal(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def _public_object_name(value: Any) -> str:
    """Remove source-PDF spacing noise without joining Latin-only names."""
    text = " ".join(str(value or "").strip().split())
    if re.search(r"[\u4e00-\u9fff]", text):
        return re.sub(r"\s+", "", text)
    return text


def _data_path(name: str) -> Path:
    return Path(current_app.root_path) / "data" / name


def _load_json(name: str, fallback: Any) -> Any:
    path = _data_path(name)
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _alias_maps() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    payload = _load_json("service_catalog_aliases.json", {})
    results: list[dict[str, list[str]]] = []
    for section_name in ("projectObjects", "projectCodes"):
        section: dict[str, list[str]] = {}
        for project_key, object_names in (payload.get(section_name) or {}).items():
            values = object_names if isinstance(object_names, list) else [object_names]
            section[_normal(project_key)] = [
                str(value).strip() for value in values if str(value).strip()
            ]
        results.append(section)
    return results[0], results[1]


def _valid_image_bytes(payload: bytes) -> bool:
    return (
        payload.startswith(b"\xff\xd8\xff")
        or payload.startswith(b"\x89PNG\r\n\x1a\n")
        or (len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP")
    )


def _image_map() -> dict[str, dict[str, Any]]:
    payload = _load_json("service_catalog_images.json", {})
    result: dict[str, dict[str, Any]] = {}
    for row in payload.get("images") or []:
        if not isinstance(row, dict):
            continue
        license_name = str(row.get("license") or "")
        asset = str(row.get("asset") or "")
        source_url = str(row.get("sourceUrl") or "")
        digest = str(row.get("sha256") or "").lower()
        if (
            license_name not in ALLOWED_IMAGE_LICENSES
            or not asset.startswith("/service/assets/service-objects/")
            or not source_url.startswith("https://commons.wikimedia.org/wiki/File:")
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            continue
        filename = asset.rsplit("/", 1)[-1]
        source_asset = Path(current_app.root_path).parents[1] / "portal" / "public" / "assets" / "service-objects" / filename
        deployed_asset = Path(current_app.root_path).parents[1] / "portal" / "dist" / "assets" / "service-objects" / filename
        local_asset = source_asset if source_asset.is_file() else deployed_asset
        if not local_asset.is_file():
            continue
        payload_bytes = local_asset.read_bytes()
        if not _valid_image_bytes(payload_bytes) or sha256(payload_bytes).hexdigest() != digest:
            continue
        aliases = row.get("objects") if isinstance(row.get("objects"), list) else []
        for alias in aliases:
            key = _normal(alias)
            if key:
                result[key] = dict(row)
    return result


def _current_standard(entry: CapabilityEntry, today: str) -> bool:
    standard = entry.standard_item
    if standard is None or standard.deleted_at is not None or bool(standard.out_of_scope):
        return False
    if entry.effective_date and entry.effective_date.isoformat() > today:
        return False
    if entry.expires_on and entry.expires_on.isoformat() < today:
        return False
    if standard.impl_date and str(standard.impl_date) > today:
        return False
    if standard.void_date and str(standard.void_date) <= today:
        return False
    return True


def _qualifications(entry: CapabilityEntry) -> list[str]:
    values = " ".join(
        str(value or "")
        for value in (
            entry.capability_type,
            getattr(entry.standard_item, "auth_kind", ""),
        )
    ).upper()
    return [name for name in ("CNAS", "CMA") if name in values]


def _item_snapshot(object_name: str, entries: list[CapabilityEntry]) -> dict[str, Any]:
    item_groups: dict[str, list[CapabilityEntry]] = defaultdict(list)
    for entry in entries:
        item_groups[_normal(entry.item_name)].append(entry)
    items = []
    all_standard_codes: set[str] = set()
    all_qualifications: set[str] = set()
    for item_entries in item_groups.values():
        standards: dict[str, dict[str, Any]] = {}
        sites: set[str] = set()
        restrictions: set[str] = set()
        qualifications: set[str] = set()
        for entry in item_entries:
            code = str(entry.standard_code or "").strip()
            if code:
                all_standard_codes.add(code)
                standard_qualifications = _qualifications(entry)
                qualifications.update(standard_qualifications)
                all_qualifications.update(standard_qualifications)
                standards.setdefault(code, {
                    "code": code,
                    "name": str(entry.standard_name or getattr(entry.standard_item, "name", "") or ""),
                    "qualificationTags": standard_qualifications,
                })
            if entry.site:
                sites.add(str(entry.site))
            if entry.restriction:
                restrictions.add(str(entry.restriction).strip())
        item_name = str(item_entries[0].item_name or "").strip()
        standard_rows = sorted(standards.values(), key=lambda row: row["code"])
        item_key = sha256(
            (object_name + "|" + item_name + "|" + "|".join(row["code"] for row in standard_rows)).encode("utf-8")
        ).hexdigest()[:16]
        items.append({
            "key": item_key,
            "name": item_name,
            "standards": standard_rows,
            "standardCount": len(standard_rows),
            "qualificationTags": sorted(qualifications),
            "sites": sorted(sites),
            "restrictionSummary": "；".join(sorted(restrictions))[:500],
        })
    items.sort(key=lambda row: (-row["standardCount"], row["name"]))
    return {
        "objectName": object_name,
        "items": items[:MAX_PUBLIC_ITEMS],
        "itemCount": len(items),
        "standardCount": len(all_standard_codes),
        "qualificationTags": sorted(all_qualifications),
    }


def _catalog_slug(project: Project) -> str:
    source = str(project.display_code or project.number_code or project.code or project.id).lower()
    value = "-".join(part for part in re.sub(r"[^a-z0-9]+", "-", source).split("-") if part)
    return value or f"project-{project.id}"


def _object_key(department_id: int, object_name: str) -> str:
    normalized = _normal(object_name)
    digest = sha256(f"{department_id}|{normalized}".encode()).hexdigest()[:20]
    return f"dept-{department_id}-{digest}"


def analyze_catalog() -> dict[str, Any]:
    name_aliases, code_aliases = _alias_maps()
    images = _image_map()
    today = date.today().isoformat()
    entries = (
        CapabilityEntry.query.options(
            joinedload(CapabilityEntry.standard_item),
            joinedload(CapabilityEntry.departments),
        )
        .filter(
            CapabilityEntry.active.is_(True),
            CapabilityEntry.mapping_status == "confirmed",
        )
        .order_by(CapabilityEntry.id)
        .all()
    )
    grouped: dict[tuple[int, str], list[CapabilityEntry]] = defaultdict(list)
    object_names: dict[tuple[int, str], str] = {}
    for entry in entries:
        if not _current_standard(entry, today):
            continue
        object_key = _normal(entry.object_name)
        if not object_key:
            continue
        for department in entry.departments:
            if department.name not in BUSINESS_DEPARTMENTS:
                continue
            key = (department.id, object_key)
            grouped[key].append(entry)
            object_names.setdefault(key, str(entry.object_name).strip())

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    projects = (
        Project.query.options(joinedload(Project.department))
        .filter(Project.active.is_(True))
        .order_by(Project.department_id, Project.id)
        .all()
    )
    for project in projects:
        department = project.department
        if department is None or department.name not in BUSINESS_DEPARTMENTS:
            continue
        project_key = _normal(project.name)
        matched_key = (department.id, project_key)
        match_type = "exact"
        display_name = _public_object_name(project.name)
        if matched_key not in grouped:
            match_type = "alias"
            reviewed_aliases = code_aliases.get(_normal(project.code)) or name_aliases.get(project_key, [])
            matched_alias = next(
                (
                    _public_object_name(object_name)
                    for object_name in reviewed_aliases
                    if (department.id, _normal(object_name)) in grouped
                ),
                None,
            )
            matched_key = (
                (department.id, _normal(matched_alias))
                if matched_alias is not None
                else None
            )
            display_name = matched_alias or ""
        if matched_key is None or matched_key not in grouped:
            rejected.append({
                "projectId": project.id,
                "project": project.name,
                "department": department.name,
                "reason": "no_exact_or_approved_alias",
            })
            continue
        object_name = display_name or _public_object_name(object_names[matched_key])
        snapshot = _item_snapshot(object_name, grouped[matched_key])
        image = images.get(_normal(object_name))
        score = (
            (100 if match_type == "exact" else 90)
            + min(snapshot["itemCount"], 10) * 2
            + min(snapshot["standardCount"], 10) * 3
            + (5 if snapshot["qualificationTags"] else 0)
        )
        eligible = snapshot["itemCount"] >= 2 and snapshot["standardCount"] >= 1 and image is not None
        reason = "" if eligible else (
            "missing_licensed_image" if image is None else "insufficient_current_capability"
        )
        hash_payload = dict(snapshot)
        hash_payload.update({
            "score": score,
            "matchType": match_type,
        })
        canonical = json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        snapshot.update(hash_payload)
        candidates.append({
            "project": project,
            "projectId": project.id,
            "projectName": project.name,
            "department": department.name,
            "objectName": object_name,
            "objectKey": _object_key(department.id, object_name),
            "matchType": match_type,
            "score": score,
            "eligible": eligible,
            "reason": reason,
            "snapshot": snapshot,
            "capabilityHash": sha256(canonical.encode("utf-8")).hexdigest(),
            "image": image,
        })

    selected_ids: set[int] = set()
    by_department: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if candidate["eligible"]:
            by_department[candidate["department"]].append(candidate)
    for rows in by_department.values():
        rows.sort(key=lambda row: (-row["score"], row["projectId"]))
        selected_object_keys: set[str] = set()
        for row in rows:
            object_key = _normal(row["objectName"])
            if object_key in selected_object_keys:
                continue
            selected_object_keys.add(object_key)
            selected_ids.add(row["projectId"])
            if len(selected_object_keys) >= MAX_OBJECTS_PER_DEPARTMENT:
                break
    for candidate in candidates:
        candidate["selected"] = candidate["projectId"] in selected_ids

    return {
        "candidates": candidates,
        "rejected": rejected,
        "departments": {
            name: sum(1 for row in candidates if row["selected"] and row["department"] == name)
            for name in BUSINESS_DEPARTMENTS
        },
    }


def sync_catalog(*, apply_changes: bool = False, actor=None) -> dict[str, Any]:
    analysis = analyze_catalog()
    name_aliases, code_aliases = _alias_maps()
    summary = {
        "dryRun": not apply_changes,
        "selected": sum(1 for row in analysis["candidates"] if row["selected"]),
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "rejected": len(analysis["rejected"]) + sum(
            1 for row in analysis["candidates"] if not row["eligible"]
        ),
        "departments": analysis["departments"],
        "changes": [],
    }
    now = datetime.utcnow()
    for candidate in analysis["candidates"]:
        project = candidate["project"]
        row = ExternalScheme.query.filter_by(project_id=project.id).first()
        # Existing manually published schemes remain in the catalogue even when
        # another project wins the per-department object de-duplication.  Enrich
        # those rows with the same verified capability/image snapshot, but never
        # auto-create an unselected duplicate.
        if not candidate["selected"] and row is None:
            continue
        if not candidate["eligible"]:
            continue
        is_new = row is None
        before_hash = row.capability_hash if row else ""
        if not is_new and before_hash == candidate["capabilityHash"] and row.cover_url == candidate["image"]["asset"]:
            summary["unchanged"] += 1
            continue
        action = "create" if is_new else "update"
        summary["changes"].append({
            "action": action,
            "projectId": project.id,
            "objectName": candidate["objectName"],
            "department": candidate["department"],
            "score": candidate["score"],
        })
        summary["created" if is_new else "updated"] += 1
        if not apply_changes:
            continue
        if is_new:
            slug = _catalog_slug(project)
            slug_conflict = ExternalScheme.query.filter_by(slug=slug).first()
            if slug_conflict is not None and slug_conflict.project_id != project.id:
                slug = f"{slug}-{project.id}"
            row = ExternalScheme(
                project=project,
                slug=slug,
                public_title=candidate["objectName"],
                subtitle=f"{candidate['department']}专业检测服务",
                summary=f"提供{candidate['objectName']}常见项目检测、标准核对与在线委托服务。",
                category=candidate["department"],
                price_mode="quote",
                feature_tags=[],
                deliverables=["检测报告"],
                pricing_rules={},
                display_order=candidate["score"],
                published=True,
                featured=False,
                auto_generated=True,
                published_at=now,
                updated_by=getattr(actor, "account", "catalog-sync") or "catalog-sync",
            )
            db.session.add(row)
        elif row.auto_generated:
            row.public_title = candidate["objectName"]
            row.subtitle = row.subtitle or f"{candidate['department']}专业检测服务"
            row.summary = row.summary or f"提供{candidate['objectName']}常见项目检测、标准核对与在线委托服务。"
            row.category = candidate["department"]
            row.display_order = candidate["score"]
        row.object_key = candidate["objectKey"]
        row.object_name = candidate["objectName"]
        row.object_aliases = (
            code_aliases.get(_normal(project.code))
            or name_aliases.get(_normal(project.name), [])
        )
        row.capability_snapshot = candidate["snapshot"]
        row.capability_hash = candidate["capabilityHash"]
        row.capability_synced_at = now
        row.cover_url = candidate["image"]["asset"]
        row.image_attribution = candidate["image"]
        row.capability_snapshot["generatedAt"] = now.isoformat(timespec="seconds")
        row.feature_tags = [item["name"] for item in candidate["snapshot"]["items"][:3]]
        row.version = int(row.version or 0) + 1
        add_operation_audit(
            "portal.service_catalog.sync",
            "external_scheme",
            project.id,
            category="configuration",
            before={"capabilityHash": before_hash},
            after={
                "capabilityHash": candidate["capabilityHash"],
                "objectName": candidate["objectName"],
                "score": candidate["score"],
                "published": bool(row.published),
            },
            actor=actor,
            message="能力库驱动的客户检测对象目录同步",
        )
    if apply_changes:
        db.session.commit()
    return summary


def public_catalog_diagnostics() -> dict[str, Any]:
    analysis = analyze_catalog()
    return {
        "departments": analysis["departments"],
        "candidates": [
            {
                key: row[key]
                for key in (
                    "projectId", "projectName", "department", "objectName",
                    "matchType", "score", "eligible", "selected", "reason",
                )
            }
            for row in analysis["candidates"]
        ],
        "rejected": analysis["rejected"],
    }


def public_image_credits() -> list[dict[str, Any]]:
    """Return each locally verified licensed image exactly once."""
    rows: dict[str, dict[str, Any]] = {}
    for image in _image_map().values():
        asset = str(image.get("asset") or "")
        if not asset or asset in rows:
            continue
        rows[asset] = {
            "asset": asset,
            "objects": [str(value) for value in image.get("objects") or []],
            "author": str(image.get("author") or ""),
            "sourceUrl": str(image.get("sourceUrl") or ""),
            "license": str(image.get("license") or ""),
            "licenseUrl": str(image.get("licenseUrl") or ""),
            "fetchedAt": str(image.get("fetchedAt") or ""),
            "sha256": str(image.get("sha256") or ""),
        }
    return sorted(rows.values(), key=lambda row: row["asset"])
