"""Refresh editable library references by identity without changing saved reports.

Standard editions are method choices: changed codes require explicit reselection.
Parameter type/activation/date remain descriptive, per the existing library rule.
"""
from copy import deepcopy
import re

from .models import StdLibraryItem, CapabilityEntry
from .standard_control import normalize_code, capability_matches_standard


def current_entry_references(raw, user, department, *, completing=False, correcting=False):
    from .platform.identity import (user_has_org_wide_scope, denied_standard_item_ids,
                                   standard_matches_department)
    ids = raw.get('standardItemIds') or []
    if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError('标准记录ID无效，请重新选择')
    items = {row.id: row for row in StdLibraryItem.query.filter(
        StdLibraryItem.id.in_(ids), StdLibraryItem.deleted_at.is_(None)).all()} if ids else {}
    denied = set() if user_has_org_wide_scope(user) else denied_standard_item_ids(user)
    codes = raw.get('testBases') or str(raw.get('testBasis') or '').replace('；', ';').split(';')
    wanted = {normalize_code(code) for code in codes}
    for identity in ids:
        item = items.get(identity)
        if item is None or (not correcting and (item.id in denied or not standard_matches_department(item, department))):
            raise ValueError('所选标准已删除或不在当前授权范围，请办理委托更改后重新选择')
        if normalize_code(item.code) not in wanted:
            raise ValueError('标准库编号或版本已变更，请办理委托更改确认检测依据；不能继续沿用旧编号')
        if completing and item.to_row()['status'] != '现行':
            raise ValueError('所选标准当前不可用，请重新选择标准')
    result = {}
    if ids:
        records = [dict(id=i, code=items[i].code, name=items[i].name or '') for i in dict.fromkeys(ids)]
        result['standardRecords'] = records
        names = {f'id:{row["id"]}': row['name'] for row in records}
        for code in codes:
            values = {row['name'] for row in records if normalize_code(row['code']) == normalize_code(code)}
            names[code] = next(iter(values)) if len(values) == 1 else ''
        result['standardNames'] = names
        # Only library-bound judgment codes lose their obsolete embedded title;
        # manual judgment text and unrelated methods remain exactly as entered.
        if 'judgmentEntries' not in raw:
            from .functions.report_standard_text import judgment_rows
            _, embedded = judgment_rows(raw.get('standardJudge') or '')
            bound = {normalize_code(row['code']) for row in records}
            replace_titles = {code for code, title in embedded.items()
                              if normalize_code(code) in bound and re.fullmatch(r'《[^》]*》|<[^>]*>', title.strip())}
            if replace_titles:
                value = raw['standardJudge']
                for code in replace_titles:
                    value = value.replace(code + embedded[code], code).replace(code + ' ' + embedded[code], code)
                result['standardJudge'] = value
    capability_ids = raw.get('capabilityEntryIds') or []
    if not isinstance(capability_ids, list) or any(type(i) is not int or i <= 0 for i in capability_ids):
        raise ValueError('能力项目编号无效，请重新选择参数')
    if not capability_ids:
        return result
    entries = {row.id: row for row in CapabilityEntry.query.filter(CapabilityEntry.id.in_(capability_ids)).all()}
    if any(i not in entries for i in capability_ids):
        raise ValueError('所选参数已不存在，请办理委托更改后重新选择')
    if not items or any(not any(capability_matches_standard(e, s) for s in items.values()) for e in entries.values()):
        raise ValueError('所选参数不属于当前标准记录，请办理委托更改后重新选择')
    snapshots = [entries[i].to_row() for i in dict.fromkeys(capability_ids)]
    available = {('library', str(row['id'])): row['itemName'] for row in snapshots}
    manual = raw.get('manualCapabilityItems') or []
    available.update({('manual', str(name)): name for name in manual})
    projects = []
    for row in raw.get('testItemOrder') or []:
        key = (row.get('kind'), str(row.get('id') if row.get('kind') == 'library' else row.get('name')))
        value = available.pop(key, None)
        if value:
            projects.append(value)
    projects.extend(available.values())
    result.update(capabilitySnapshots=snapshots, projectList=projects)
    return deepcopy(result)
