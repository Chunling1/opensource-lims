"""Keep registration identities paired with registration codes at every stage."""
from .standard_control import normalize_code, split_standard_codes


def _codes(value):
    values = value if isinstance(value, (list, tuple)) else [value]
    return list(dict.fromkeys(code for v in values for code in split_standard_codes(str(v or ''))))


def registration_standards(detail):
    raw = detail.get('rawSample') or {}
    # Explicit registration fields (even empty) must not revive inherited testing data.
    if 'testBases' in raw or 'testBasis' in raw:
        return _codes(raw.get('testBases') or raw.get('testBasis'))
    return []


def testing_standards(detail):
    ci = detail.get('checkInput') or {}
    return _codes(ci.get('standards') or ci.get('standard'))


def standards_for_authorization(detail):
    raw = detail.get('rawSample') or {}
    if 'testBases' in raw or 'testBasis' in raw:
        return registration_standards(detail)
    values = testing_standards(detail)
    if values:
        return values
    for section in detail.get('summary') or []:
        if section.get('title') == '实验信息':
            fields = {field[0]: field[1] for field in section.get('fields') or [] if isinstance(field, (list, tuple)) and len(field) >= 2}
            return _codes(fields.get('检测依据') or fields.get('执行标准'))
    return []


def testing_selection_conflict(detail):
    registered, tested = registration_standards(detail), testing_standards(detail)
    if registered and tested and {normalize_code(c) for c in registered} != {normalize_code(c) for c in tested}:
        return '登记标准：' + '；'.join(registered) + '；检测标准：' + '；'.join(tested) + '。如需变更检测方法，请走委托更改'
    return ''
