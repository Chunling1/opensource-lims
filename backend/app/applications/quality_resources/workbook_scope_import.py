"""Atomic replacement of CURRENT scope. Caller owns commit/rollback.

No schema changes, filesystem writes, report mutations or external requests.
Old capability rows/batches are retained unchanged for historical references.
"""
import hashlib
import json
import re
from datetime import date, datetime

from ...extensions import db
from ...models import CapabilityEntry, CapabilityImportBatch, Department, Standard, StdLibraryItem, user_standard_denials
from ...cnas_capabilities import normalize_standard_code
from .controlled_variants import PRESERVED_FIELDS, plan_controlled_groups


SCHEMA = 'lims.scope-workbook-import.v2'


def validate_bundle(bundle):
    if bundle.get('schemaVersion') != SCHEMA:
        raise ValueError('标准能力导入契约不匹配')
    if not re.fullmatch(r'[0-9a-f]{64}', bundle.get('sourceSha256', '')):
        raise ValueError('来源指纹无效')
    standards = bundle.get('standards')
    capabilities = bundle.get('capabilities')
    if not isinstance(standards, list) or not standards or not isinstance(capabilities, list) or not capabilities:
        raise ValueError('标准或能力明细为空，不执行替换')
    by_key = {}
    for row in standards:
        key = row['key']
        if key in by_key or not key or normalize_standard_code(row['code']) != key:
            raise ValueError('标准编号重复或规范键错误')
        if not row['name'] or type(row['isOnsiteStandard']) is not bool:
            raise ValueError('标准名称或现场属性无效')
        if not isinstance(row['departments'], list) or len(set(row['departments'])) != len(row['departments']):
            raise ValueError('标准部门授权无效')
        by_key[key] = row
    for row in capabilities:
        parent = by_key.get(row['standardKey'])
        if parent is None or not set(row['departments']).issubset(parent['departments']):
            raise ValueError('能力部门不属于标准授权范围')
        if row['accreditation'] not in ('CNAS', 'CMA') or row['capabilityType'] not in ('检测', '检验', '校准'):
            raise ValueError('资质体系或能力类型无效')
        if not all(str(row.get(k) or '').strip() for k in ('address', 'site', 'objectName', 'itemName', 'sourceFile')):
            raise ValueError('能力必填字段缺失')
        if row['itemName'] == '#REF!' or type(row['sourcePage']) is not int or row['sourcePage'] < 1:
            raise ValueError('能力名称或来源页异常')
        if row.get('effectiveDate'):
            date.fromisoformat(row['effectiveDate'])
    return by_key


def replace_scope_workbook(bundle):
    """Validate and stage replacement; never commit. Reapply same payload is a no-op."""
    by_key = validate_bundle(bundle)
    payload_hash = hashlib.sha256(json.dumps(bundle, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    previous = CapabilityImportBatch.query.filter_by(source_sha256=payload_hash).first()
    if previous:
        if previous.status != 'active':
            raise ValueError('此导入批次已存在但非启用状态，不重复应用')
        return {'reused': True, 'batchId': previous.id, 'payloadSha256': payload_hash}
    departments = {d.name: d for d in Department.query.all()}
    unknown = {d for row in bundle['standards'] for d in row['departments']} - departments.keys()
    if unknown:
        raise ValueError('未确认的部门：' + '、'.join(sorted(unknown)))
    old_items = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all()
    predecessors_by_key = {}
    for old in old_items:
        predecessors_by_key.setdefault(normalize_standard_code(old.code), []).append(old)
    # Fresh catalog IDs must not erase an administrator's explicit denial.
    # Keep the old association for historical references and copy only denials,
    # never grants. A denial on any same-code predecessor remains restrictive.
    old_denials = db.session.execute(db.select(user_standard_denials)).all()
    denied_users_by_item = {}
    for denial in old_denials:
        denied_users_by_item.setdefault(denial.standard_item_id, set()).add(denial.user_id)
    all_masters = Standard.query.order_by(Standard.id).all()
    master_before = {str(row.id): {column.name: (value.isoformat() if isinstance(value := getattr(row, column.name), datetime) else value)
        for column in Standard.__table__.columns} for row in all_masters}
    masters_by_exact_code = {row.code: row for row in all_masters}
    master_by_key = {}
    for master in all_masters:
        master_by_key.setdefault(normalize_standard_code(master.code), master)
    # Controlled historical IDs/fields remain readable. Current master metadata
    # follows the approved source; its original rows are journaled for rollback.
    from .testing_locations import workbook_item_ids
    maintained_ids = workbook_item_ids()
    items = []
    source_owners = {}
    batch = CapabilityImportBatch(source_name=bundle['sourceName'], source_sha256=payload_hash,
        status='active', activated_at=datetime.utcnow(), summary={
            'schema': SCHEMA, 'sourceWorkbookSha256': bundle['sourceSha256'],
            'sourceStandardRows': bundle['sourceStandardRows'],
            'retiredItemIds': [r.id for r in old_items], 'standardPolicies': {},
            'masterBefore': master_before,
        })
    db.session.add(batch); db.session.flush()
    policies = {}
    for key, source in by_key.items():
        master = masters_by_exact_code.get(source['code']) or master_by_key.get(key)
        if master is None:
            master = Standard(code=source['code'], name=source['name'], department=';'.join(source['departments']),
                category=source['category'], auth_kind=source['authKind'], status='现行', expired=False)
            db.session.add(master); db.session.flush()
            master_by_key[key] = master
        master.code = source['code']
        master.name = source['name']
        master.department = ';'.join(source['departments'])
        master.category = source['category']
        master.auth_kind = source['authKind']
        master.deleted_at = None
        predecessors = predecessors_by_key.get(key, [])
        denied_users = set().union(*(denied_users_by_item.get(r.id, set()) for r in predecessors))
        for group in plan_controlled_groups(source, predecessors, maintained_ids):
            owner = None
            for variant in group['variants']:
                item = StdLibraryItem(standard_id=master.id, code=source['code'], name=source['name'],
                    controlled_no=group['controlledNo'], category=source['category'],
                    auth_kind=source['authKind'], use_depts=';'.join(group['departments']),
                    out_of_scope=not bool(source['accreditations']), remark=source['remark'],
                    is_onsite_standard=group['isOnsiteStandard'],
                    **{field: (db.null() if field == 'is_english' and variant[field] is None else variant[field])
                       for field in PRESERVED_FIELDS})
                db.session.add(item); db.session.flush()
                if owner is None:
                    owner = item
                    for source_row in group['sourceRows']:
                        source_owners[(key, source_row)] = item
                if denied_users:
                    db.session.execute(user_standard_denials.insert(), [
                        {'user_id': user_id, 'standard_item_id': item.id} for user_id in sorted(denied_users)])
                items.append(item)
                policies[str(item.id)] = {
                    'sourceRows': group['sourceRows'], 'sourceVariants': source.get('sourceVariants', []),
                    'predecessorIds': variant['predecessorIds'], 'capabilityOwnerId': owner.id}
    for source in bundle['capabilities']:
        item = source_owners.get((source['standardKey'], source['sourceStandardRow']))
        if item is None:
            raise ValueError('能力来源行没有对应受控记录')
        if not set(source['departments']).issubset(set((item.use_depts or '').split(';'))):
            raise ValueError('能力部门不属于对应受控来源行，不能使用同编号其他记录的授权')
        row = CapabilityEntry(batch_id=batch.id, standard_item_id=item.id,
            capability_type=source['capabilityType'], certificate_no=source.get('certificateNo') or '',
            site=source['site'], object_name=source['objectName'], item_name=source['itemName'],
            standard_code=source.get('sourceStandardCode') or item.code,
            standard_name=source.get('sourceStandardName') or item.name,
            method_clause=source['methodOriginal'], restriction=source['restriction'],
            effective_date=date.fromisoformat(source['effectiveDate']) if source['effectiveDate'] else None,
            source_file=source['sourceFile'], source_page=source['sourcePage'], source_row=source['sourceRow'],
            source_sha256=bundle['sourceSha256'], mapping_status='confirmed' if source['departments'] else 'pending',
            active=True, raw_cells={'standardWorkbook': {
                'schema': SCHEMA, 'address': source['address'], 'accreditation': source['accreditation'],
                'oneLibraryState': source['oneLibraryState'], 'oneLibraryConditions': source['oneLibraryConditions'],
                'sourceStandardRow': source['sourceStandardRow'], 'note': source['note'],
                'sourceEvidence': source['sourceEvidence'],
            }})
        row.departments = [departments[name] for name in source['departments']]
        db.session.add(row)
    now = datetime.utcnow()
    for old in old_items:
        old.deleted_at = now
    selected_master_ids = {item.standard_id for item in items}
    for master in all_masters:
        if master.id not in selected_master_ids and master.deleted_at is None:
            master.deleted_at = now
    batch.summary = {**batch.summary, 'standardPolicies': policies, 'createdItemIds': [r.id for r in items]}
    db.session.flush()
    return {'reused': False, 'batchId': batch.id, 'payloadSha256': payload_hash,
            'standards': len(by_key), 'controlledItems': len(items),
            'capabilities': len(bundle['capabilities']), 'retiredItems': len(old_items)}
