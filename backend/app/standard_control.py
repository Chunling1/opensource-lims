"""受控标准库查询与授权判定，供质量台账、合同评审和检测校验共同使用。"""
import re
from datetime import date, datetime

from .models import StdLibraryItem
from .preflight_reads import read_once


def normalize_code(value):
    return re.sub(r"[\s`'\"]+", "", (value or "").upper())


def _parse_date(value):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _department_matches(item, department):
    # Empty assignment is explicitly unassigned, not an all-department grant.
    departments = [d.strip() for d in (item.use_depts or "").split(";") if d.strip()]
    if not (department or "").strip() or not departments:
        return False
    compact = re.sub(r"[（）()\s]", "", department)
    return any(compact in re.sub(r"[（）()\s]", "", d) or re.sub(r"[（）()\s]", "", d) in compact
               for d in departments)


def single_list_flag(auth_kind):
    return '一单一库' in re.split(r'[+、,\s]+', auth_kind or '')


def find_controlled_standard(code, department="", at=None, *, item_id=None):
    """返回最符合部门、有效期和资质范围的受控标准及判定信息。"""
    when = at or date.today()
    item, result = read_once(('controlled_standard', code, department, when, item_id),
                             lambda: _find_controlled_standard(code, department, when, item_id=item_id))
    # Do not expose a shared mutable verdict to different consumers.
    return item, dict(result)


def _find_controlled_standard(code, department="", at=None, *, item_id=None):
    when = at or date.today()
    wanted = normalize_code(code)
    current = read_once('controlled_standard_rows',
                       lambda: StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all())
    from .speed_reads import standard_candidates
    candidates = standard_candidates(current, wanted)
    if item_id is not None:
        candidates = [row for row in candidates if row.id == item_id]
    if not candidates:
        return None, {"valid": False, "reason": "标准不在受控标准库"}

    def rank(row):
        active = not row.void_date or (_parse_date(row.void_date) or date.min) > when
        implemented = not row.impl_date or (_parse_date(row.impl_date) or date.max) <= when
        return (
            _department_matches(row, department),
            active and implemented,
            not row.out_of_scope,
            single_list_flag(row.auth_kind),
            "CMA" in (row.auth_kind or ""),
        )

    item = max(candidates, key=rank)
    reasons = []
    void_date = _parse_date(item.void_date)
    impl_date = _parse_date(item.impl_date)
    if item.out_of_scope:
        reasons.append("标记为资质范围外")
    if void_date and void_date <= when:
        reasons.append(f"已于 {item.void_date} 作废")
    if impl_date and impl_date > when:
        reasons.append(f"实施日期为 {item.impl_date}")
    if not _department_matches(item, department):
        reasons.append(f"未授权给部门「{department}」")
    result = {
        "valid": not reasons,
        "reason": "；".join(reasons),
        "singleList": single_list_flag(item.auth_kind),
        "cma": "CMA" in (item.auth_kind or ""),
        "cnas": "CNAS" in (item.auth_kind or ""),
        "status": item.to_row()["status"],
    }
    # Standard authorization is maintained on the controlled standard itself.
    # Parameter source rows do not grant or revoke the standard's authorization.
    return item, result


def split_standard_codes(value):
    return [part.strip() for part in re.split(r"[\n；;、]+", value or "") if part.strip()]


def validate_stamp_standards(value, department, *, require_cma=False, require_cnas=False, at=None):
    errors = []
    codes = split_standard_codes(value)
    if not codes:
        return ["未填写检测依据，不能确认盖章授权"]
    for code in codes:
        _item, result = find_controlled_standard(code, department, at)
        marks = [mark for mark, enabled in (("CMA", require_cma), ("CNAS", require_cnas)) if enabled]
        errors.extend(f"{code}：{failure['message']}" for failure in standard_scope_failures(result, marks))
    return errors


def capability_matches_standard(entry, item, owners=None):
    """Parameter membership follows the selected record/explicit source owner only.

    Source code, type, dates, marks and activation are display provenance, not
    business selection gates. Never infer ownership from another same-code row.
    """
    if owners is None:
        from .applications.quality_resources.testing_locations import workbook_capability_owners
        owners = workbook_capability_owners()
    return entry.standard_item_id is not None and entry.standard_item_id == owners.get(item.id, item.id)


def standard_scope_failures(result, marks):
    """The shared standard-only verdict used by entry, review and scope display."""
    if not result.get('valid'):
        return [{'category': 'controlled_standard', 'message': result.get('reason') or '标准不在现行受控库',
                 'marks': list(marks)}]
    failures = []
    if 'CMA' in marks and not result.get('singleList'):
        failures.append({'category': 'single_list_scope', 'message': '标准未纳入当前部门一单一库',
                         'marks': ['CMA']})
    for mark in marks:
        if not result.get(mark.lower()):
            failures.append({'category': mark.lower() + '_standard_scope',
                             'message': f'标准未取得当前部门 {mark} 授权', 'marks': [mark]})
    return failures


def standard_authorized_marks(result):
    """Project the same independent CMA/CNAS rules in all review surfaces."""
    return [mark for mark in ('CMA', 'CNAS') if not standard_scope_failures(result, [mark])]


def selected_controlled_standards(codes, record_ids, department="", at=None):
    """Resolve explicit record identities; ambiguous legacy text requires reselection."""
    current = read_once('controlled_standard_rows',
                        lambda: StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all())
    explicit = bool(record_ids)
    if record_ids is not None and (not isinstance(record_ids, list) or any(type(i) is not int or i <= 0 for i in record_ids)):
        return [(None, {'code': code, 'valid': False, 'identityUnresolved': True, 'reason': '标准记录ID无效，请重新选择'}) for code in codes]
    # Explicit IDs are independent records, even when their printed codes match.
    # Codes remain descriptive/legacy input and must not collapse selected IDs.
    result = []
    by_id = {item.id: item for item in current}
    wanted = {normalize_code(code) for code in codes}
    def append(code, item=None):
        if item is None:
            result.append((None, {'code': code, 'valid': False, 'identityUnresolved': True, 'reason': '标准记录无法唯一确认，请重新选择对应标准'}))
        else:
            selected, verdict = find_controlled_standard(code, department, at, item_id=item.id)
            result.append((selected, {**verdict, 'code': code, 'standardId': item.id}))
    if explicit:
        covered = set()
        for identity in dict.fromkeys(record_ids):
            item = by_id.get(identity)
            code = item.code if item else str(identity)
            if item is None or normalize_code(code) not in wanted:
                append(code)
            else:
                covered.add(normalize_code(code))
                append(code, item)
        for code in codes:
            if normalize_code(code) not in covered:
                append(code)
    else:
        from .speed_reads import standard_index
        for code in codes:
            candidates = [item for item in standard_index(current).get(normalize_code(code), ())
                          if _department_matches(item, department)]
            append(code, candidates[0] if len(candidates) == 1 else None)
    return result
