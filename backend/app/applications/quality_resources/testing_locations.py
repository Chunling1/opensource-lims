"""Parameter-derived addresses and read-only workbook provenance lookups.

No writes or external requests. Address projection itself does not query ORM.
"""
import re
from ...preflight_reads import read_once


WORKFLOW_VERSION = 1
WORKBOOK_SCHEMA = 'lims.scope-workbook-import.v2'


def _active_workbook_batches():
    from ...models import CapabilityImportBatch
    return read_once('active_workbook_batches',
                     lambda: CapabilityImportBatch.query.filter_by(status='active').all())


def workbook_item_ids():
    """Identify the imported projection even if no eligible parameters remain."""
    return set(read_once('workbook_item_ids', _workbook_item_ids))


def _workbook_item_ids():
    ids = set()
    for batch in _active_workbook_batches():
        summary = batch.summary if isinstance(batch.summary, dict) else {}
        if summary.get('schema') == WORKBOOK_SCHEMA:
            ids.update(value for value in summary.get('createdItemIds', []) if type(value) is int)
    return ids


def workbook_capability_owners():
    """Share source parameters only within their declared controlled group."""
    return dict(read_once('workbook_capability_owners', _workbook_capability_owners))


def _workbook_capability_owners():
    """Share each source parameter only within its declared controlled group.

Language/date variants keep independent records without duplicating parameters.
Never infer ownership from code or department, which could widen authorization.
"""
    from ...models import CapabilityImportBatch
    owners = {}
    # Declared identity links remain valid provenance regardless of activation.
    batches = read_once('workbook_owner_batches', lambda: CapabilityImportBatch.query.order_by(CapabilityImportBatch.id).all())
    for batch in batches:
        summary = batch.summary if isinstance(batch.summary, dict) else {}
        if summary.get('schema') != WORKBOOK_SCHEMA:
            continue
        created = set(summary.get('createdItemIds', []))
        policies = summary.get('standardPolicies', {})
        for item_id in created:
            policy = policies.get(str(item_id), {})
            owner = policy.get('capabilityOwnerId', item_id)
            owner_policy = policies.get(str(owner), {})
            if type(owner) is not int or owner not in created or (
                owner != item_id and policy.get('sourceRows') != owner_policy.get('sourceRows')
            ):
                raise ValueError('受控记录的能力来源关联无效')
            owners[item_id] = owner
    return owners


def workbook_retired_item_ids():
    """Historical source rows remain stored, but are not current suggestions."""
    retired = set()
    for batch in _active_workbook_batches():
        summary = batch.summary if isinstance(batch.summary, dict) else {}
        if summary.get('schema') == WORKBOOK_SCHEMA:
            retired.update(value for value in summary.get('retiredItemIds', []) if type(value) is int)
    return retired


def require_legacy_catalog_write_allowed():
    """Legacy import/activation cannot rewrite v2 source ownership or accreditation."""
    if workbook_capability_owners():
        raise ValueError('当前标准库含受控版本来源关联，禁止使用旧标准导入或激活命令；请使用经核验的来源导入流程')


def workbook_current_variants(*, excluded_item_ids=()):
    """Resolve declared aliases without moving or rewriting capability rows.

    Include empty groups so a retired owner cannot fall back to its ORM link.
    """
    from ...models import StdLibraryItem
    owners = workbook_capability_owners()
    groups = {owner: [] for owner in owners.values()}
    if owners:
        for item in StdLibraryItem.query.filter(StdLibraryItem.id.in_(owners), StdLibraryItem.deleted_at.is_(None)).all():
            if item.id not in excluded_item_ids:
                groups[owners[item.id]].append(item)
    return groups


def workbook_capability_matches_items(entry, groups, allowed_item_ids, when):
    """Read-only gate for current workbook projections; legacy behavior stays owned by callers."""
    from ...cnas_capabilities import normalize_standard_code
    if entry.standard_item_id not in groups:
        return True
    if (not entry.active or entry.batch.status != 'active'
            or (entry.effective_date and when < entry.effective_date)
            or (entry.expires_on and when > entry.expires_on)):
        return False
    return any(item.id in allowed_item_ids
        and __import__('app.standard_control', fromlist=['capability_matches_standard']).capability_matches_standard(entry, item)
        and not item.out_of_scope
        and (not item.impl_date or str(item.impl_date) <= when.isoformat())
        and (not item.void_date or str(item.void_date) > when.isoformat())
        for item in groups[entry.standard_item_id])


def current_capability_variants(entry, groups, department, when, owners=None):
    """Only the same declared source group and unchanged standard code qualify."""
    from ...cnas_capabilities import normalize_standard_code
    result = []
    for item in groups.get(entry.standard_item_id, []):
        if not __import__('app.standard_control', fromlist=['capability_matches_standard']).capability_matches_standard(entry, item, owners=owners):
            continue
        from ...authorization_scope import standard_matches_department
        if department and not standard_matches_department(item, department):
            continue
        if item.out_of_scope or (item.impl_date and str(item.impl_date) > when.isoformat()) or (item.void_date and str(item.void_date) <= when.isoformat()):
            continue
        result.append(item)
    return result


def capability_metadata(entry):
    cells = entry.raw_cells if isinstance(entry.raw_cells, dict) else {}
    return cells.get('standardWorkbook', {}) if isinstance(cells.get('standardWorkbook'), dict) else {}


def capability_address(entry):
    cells = entry.raw_cells if isinstance(entry.raw_cells, dict) else {}
    maintained = cells.get('parameterMaintenance') or {}
    return parameter_address_key(str(maintained.get('address') or capability_metadata(entry).get('address') or ''))


def capability_accreditation(entry):
    # Legacy records were imported exclusively through the CNAS importer.
    return str(capability_metadata(entry).get('accreditation') or 'CNAS')


def parameter_address_key(address):
    key = re.sub(r'\s+', '', address)
    return ('示例市华北产业园兴业大街6号'
            if key == '示例市华北产业园兴业大街6号' else key)


def normalized_addresses(entries):
    result = []
    seen = set()
    for entry in entries:
        address = capability_address(entry)
        if not address:
            continue
        key = parameter_address_key(address)
        if key not in seen:
            seen.add(key)
            result.append(address)
    return result


def available_testing_addresses():
    """Project only distinct addresses from the active confirmed database library."""
    from sqlalchemy import JSON, type_coerce
    from ...extensions import db
    from ...models import CapabilityEntry, CapabilityImportBatch
    # raw_cells uses JSONText (TEXT/LONGTEXT); supply the JSON expression type
    # without casting or loading the full source payload into Python.
    source_address = type_coerce(CapabilityEntry.raw_cells, JSON)['standardWorkbook']['address'].as_string()
    maintained_address = type_coerce(CapabilityEntry.raw_cells, JSON)['parameterMaintenance']['address'].as_string()
    address = db.func.coalesce(maintained_address, source_address)
    rows = db.session.query(address).join(
        CapabilityImportBatch, CapabilityImportBatch.id == CapabilityEntry.batch_id
    ).filter(address.isnot(None)).distinct().all()
    return sorted({parameter_address_key(value) for (value,) in rows
                   if isinstance(value, str) and value.strip()})


def resolve_testing_location(raw, entries, department, when, capability_type, selected_standards=None, controlled_groups=None):
    if type(raw.get('isOnsiteTesting')) is not bool:
        raise ValueError('是否现场检测必须为是或否')
    manual_items = raw.get('manualCapabilityItems') or []
    if not isinstance(manual_items, list) or any(not isinstance(item, str) or not item.strip() for item in manual_items):
        raise ValueError('库外项目必须为非空名称列表')
    if not entries and not manual_items:
        raise ValueError('请先选择带完整地址的能力项目/参数')
    if raw['isOnsiteTesting'] and selected_standards is not None:
        if not selected_standards or any(item is None for item in selected_standards):
            raise ValueError('检测依据对应标准不可用')
    # Parameter attributes only project display values. Authorization and
    # membership are checked on the selected standard, never on parameter data.
    from ...authorization_scope import standard_matches_department
    standards = selected_standards if selected_standards is not None else [entry.standard_item for entry in entries]
    if any(standard is None or standard.deleted_at is not None
           or not standard_matches_department(standard, department) for standard in standards):
        raise ValueError('所选参数对应标准已停用或未授权给检测部门')
    source_addresses = normalized_addresses(
        [entry for entry in entries if capability_address(entry)] if raw['isOnsiteTesting'] else entries)
    if raw['isOnsiteTesting']:
        address = str(raw.get('onsiteTestLocation') or '').strip()
        if not address:
            raise ValueError('请填写现场检测完整地址')
        if len(address) > 1000:
            raise ValueError('现场检测地址过长')
        actual = [address]
    else:
        actual = list(source_addresses)
        choices = raw.get('manualParameterLocations')
        if manual_items and choices is not None:
            if not isinstance(choices, dict):
                raise ValueError('库外检测地点格式无效')
            allowed = None
            for name in manual_items:
                choice = choices.get(name)
                if not isinstance(choice, dict) or choice.get('mode') not in ('library', 'selected'):
                    raise ValueError(f'「{name}」请选择库外检测地点')
                if choice['mode'] == 'library':
                    if not source_addresses:
                        raise ValueError(f'「{name}」需先选择有地点的库内参数，或单独选择地点')
                    continue
                values = choice.get('addresses')
                if (not isinstance(values, list) or not values or len(values) > 100
                        or any(not isinstance(value, str) or not value.strip() for value in values)):
                    raise ValueError(f'「{name}」请选择数据库中的检测地点')
                if allowed is None:
                    allowed = set(available_testing_addresses())
                for value in values:
                    address = parameter_address_key(value)
                    if address not in allowed:
                        raise ValueError(f'「{name}」的检测地点已不在数据库中，请重新选择')
                    if address not in actual:
                        actual.append(address)
        elif manual_items:
            manual_address = str(raw.get('manualTestLocation') or '').strip()
            if not manual_address or len(manual_address) > 1000:
                raise ValueError('请填写库外项目完整检测地址（不超过1000字）')
            if parameter_address_key(manual_address) not in {parameter_address_key(value) for value in actual}:
                actual.append(parameter_address_key(manual_address))
    return {'actualTestLocations': actual, 'capabilityLocations': source_addresses,
            'testLocation': '；'.join(actual), 'locationWorkflowVersion': WORKFLOW_VERSION}
