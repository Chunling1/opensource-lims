"""Maintain reusable parameters without rewriting imported qualification evidence."""
from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

from ...extensions import db
from ...models import CapabilityEntry, CapabilityImportBatch, Department
from .testing_locations import workbook_capability_owners


FIELDS = {'itemName': ('item_name', 400), 'objectName': ('object_name', 400),
          'site': ('site', 80), 'methodClause': ('method_clause', 600),
          'restriction': ('restriction', 4000)}


def owner_id(standard):
    return workbook_capability_owners().get(standard.id, standard.id)


def shared_source(standard):
    owners = workbook_capability_owners()
    return sum(owner == owners.get(standard.id, standard.id) for owner in owners.values()) > 1


def parameter_row(entry):
    row = entry.to_row()
    row['departments'] = sorted(row['departments'])
    cells = entry.raw_cells or {}
    row['internal'] = bool(cells.get('internalParameter'))
    row['superseded'] = bool(cells.get('parameterSupersededBy'))
    row['sourceSha256'] = entry.source_sha256
    row['version'] = sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return row


def validate_values(body, standard, *, entry=None):
    allowed = {*FIELDS, 'address', 'departments', 'reason', 'version', 'capabilityType', 'active', 'copyFromId'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError('包含不可维护字段；资质、证书、有效期及来源只能通过来源更新')
    reason = str(body.get('reason') or '').strip()
    if not reason or len(reason) > 1000:
        raise ValueError('请填写维护说明（不超过1000字）')
    if entry is not None and body.get('version') != parameter_row(entry)['version']:
        raise ValueError('参数已被其他人修改，请重新加载后核对')
    if entry is not None and (entry.raw_cells or {}).get('parameterSupersededBy'):
        raise ValueError('该参数已有新修订，请修改最新参数；旧记录仅供追溯或复制')
    values = {}
    for key, (attr, limit) in FIELDS.items():
        value = body.get(key, (getattr(entry, attr, '') or '') if entry else '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise ValueError(f'{key}格式或长度无效')
        values[attr] = value.strip()
    if not values['item_name'] or not values['object_name'] or not values['site']:
        raise ValueError('参数名称、检测对象和场所名称不能为空')
    from .testing_locations import capability_address
    address = body.get('address', capability_address(entry) if entry else '')
    if not isinstance(address, str) or not address.strip() or len(address.strip()) > 1000:
        raise ValueError('请填写完整检测地址（不超过1000字）')
    # Legacy department associations are provenance only. Do not expose a second
    # authorization editor or rewrite that provenance when revising a parameter.
    departments = list(entry.departments) if entry else []
    kind = body.get('capabilityType', entry.capability_type if entry else '检测')
    if kind not in ('检测', '检验', '校准'):
        raise ValueError('参数类型无效')
    if entry and kind != entry.capability_type:
        raise ValueError('已有参数类型属于来源信息，请通过来源更新')
    active = body.get('active', bool(entry.active) if entry else True)
    if type(active) is not bool:
        raise ValueError('启用状态无效')
    # Parameter status and source batch are retained as metadata, not business gates.
    return values, address.strip(), departments, kind, active, reason


def create_parameter(standard, validated, *, copied=None):
    values, address, departments, kind, active, reason = validated
    # A local parameter is not a new official capability, even when copied.
    batch = CapabilityImportBatch(source_name='内部参数维护', source_sha256=sha256(uuid4().bytes).hexdigest(),
                                  status='active', summary={'schema': 'lims.internal-parameter.v1'})
    db.session.add(batch); db.session.flush()
    evidence = {'internalParameter': True,
                'standardWorkbook': {'address': address, 'accreditation': '内部维护'},
                'parameterMaintenance': {'reason': reason}}
    if copied:
        evidence['copiedFrom'] = {'entryId': copied.id, 'standardItemId': copied.standard_item_id,
                                'sourceSha256': copied.source_sha256, 'snapshot': parameter_row(copied)}
    entry = CapabilityEntry(batch_id=batch.id, standard_item_id=owner_id(standard),
        standard_code=standard.code, standard_name=standard.name, capability_type=kind,
        certificate_no='', source_file='内部参数维护', source_page=0, source_row=0,
        source_sha256=batch.source_sha256, raw_cells=evidence, active=active, mapping_status='confirmed', **values)
    entry.departments = departments
    db.session.add(entry); db.session.flush()
    return entry


def update_parameter(entry, validated):
    values, address, departments, _, active, reason = validated
    from .testing_locations import capability_address
    if (all(value == (getattr(entry, attr) or '') for attr, value in values.items())
            and address == capability_address(entry)
            and {d.id for d in departments} == {d.id for d in entry.departments}
            and active == bool(entry.active)):
        return entry
    # Revision IDs keep historical sample snapshots from silently adopting new names/addresses.
    revised = CapabilityEntry(**{column.name: deepcopy(getattr(entry, column.name))
        for column in CapabilityEntry.__table__.columns if column.name != 'id'})
    for attr, value in values.items():
        setattr(revised, attr, value)
    revised.departments = departments
    revised.active = active
    # Keep official raw cells and attribution intact; project the maintained address separately.
    cells = deepcopy(entry.raw_cells or {})
    cells['parameterMaintenance'] = {'address': address, 'reason': reason, 'previousEntryId': entry.id}
    revised.raw_cells = cells
    db.session.add(revised); db.session.flush()
    entry.active = False
    previous_cells = deepcopy(entry.raw_cells or {})
    previous_cells['parameterSupersededBy'] = revised.id
    entry.raw_cells = previous_cells
    return revised
