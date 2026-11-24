"""Report-only standard display. Never changes codes used for authorization."""

import re

SEPARATORS = {"newline": "\n", "semicolon": "；", "space": " "}


def load_report_standard_names(codes, standard_item_ids=None):
    """One narrow projection for the entire report; no capability/batch reads.

    Exact codes win. Whitespace/punctuation aliases use the existing canonical
    code rule, but conflicting names are never guessed. Preserve printed codes.
    """
    from ..models import Standard
    from ..cnas_capabilities import normalize_standard_code
    if not codes:
        return {}
    wanted = {normalize_standard_code(code) for code in codes}
    exact, aliases = {}, {}
    for code, name in Standard.query.with_entities(Standard.code, Standard.name).all():
        key = normalize_standard_code(code)
        if key not in wanted:
            continue
        exact[code] = name or ""
        clean = " ".join(str(name or "").split())
        if clean:
            aliases.setdefault(key, set()).add(clean)
    result = {}
    for code in codes:
        names = aliases.get(normalize_standard_code(code), set())
        result[code] = exact.get(code) or (next(iter(names)) if len(names) == 1 else "")
    # A selected library record determines the name, never capability ownership.
    if isinstance(standard_item_ids, list) and standard_item_ids:
        result = {code: '' for code in codes}
        from ..models import StdLibraryItem
        ids = [value for value in standard_item_ids if type(value) is int and value > 0]
        selected = {}
        for item in StdLibraryItem.query.filter(StdLibraryItem.id.in_(ids), StdLibraryItem.deleted_at.is_(None)).all():
            if item.code in result:
                selected.setdefault(item.code, set()).add(item.name or '')
        for code, names in selected.items():
            result[code] = next(iter(names)) if len(names) == 1 else ''
    return result


def load_report_standard_records(codes, standard_item_ids):
    """Render only explicit records, preserving ID order and same-code names."""
    from ..models import StdLibraryItem
    from ..standard_control import normalize_code
    if not isinstance(standard_item_ids, list) or not standard_item_ids:
        return []
    ids = list(dict.fromkeys(i for i in standard_item_ids if type(i) is int and i > 0))
    rows = {item.id: item for item in StdLibraryItem.query.filter(StdLibraryItem.id.in_(ids), StdLibraryItem.deleted_at.is_(None)).all()}
    wanted = {normalize_code(code) for code in codes}
    return [dict(id=i, code=rows[i].code, name=rows[i].name or '') for i in ids
            if i in rows and normalize_code(rows[i].code) in wanted]


def standard_separator(value):
    return value if isinstance(value, str) and value in SEPARATORS else "semicolon"


def standard_title(name, language="CN"):
    name = str(name or "").strip()
    while len(name) >= 2 and (name[0], name[-1]) in (("《", "》"), ("<", ">")):
        name = name[1:-1].strip()
    if language == "none":
        return name
    left, right = ("<", ">") if language == "EN" else ("《", "》")
    return f"{left}{name}{right}" if name else ""


# Match a standard identifier, not arbitrary numbers in its title. Preserve the
# printed code (including spaces, punctuation and edition) and list separators.
_STANDARD_CODE = re.compile(
    r"(?<![A-Za-z0-9])[A-Z]{1,8}(?:/[A-Z]{1,8})?(?:[ \t]+(?:EN|ISO|IEC))*\s*"
    r"\d+(?:[.\-]\d+)*\s*[-－—:]\s*\d{4}(?!\d)"
)


def format_standard_titles(value, *, language="CN", styles=None):
    """Bracket titles already present in report text; never add a library name.

    Covers historical summaries and saved display projections without changing
    authorization codes or the user's choice to display codes only.
    """
    value = str(value or "")
    # A standard referenced inside an existing title is part of that title.
    searchable = re.sub(r"《[^》]*》|<[^>]*>", lambda m: " " * len(m[0]), value)
    codes = list(_STANDARD_CODE.finditer(searchable))
    if not codes:
        return value
    parts = [value[:codes[0].start()]]
    for index, code in enumerate(codes):
        end = codes[index + 1].start() if index + 1 < len(codes) else len(value)
        tail = value[code.end():end]
        title = tail.strip(" \t\r\n;；、,")
        if title:
            start = tail.index(title)
            style = (styles or {}).get(value[code.start():code.end()], language)
            tail = tail[:start] + standard_title(title, style) + tail[start + len(title):]
        parts.extend((value[code.start():code.end()], tail))
    return "".join(parts)


def display_separator(value, default="；"):
    if value is None:
        return default
    if not isinstance(value, str) or len(value) > 16 or any(c not in "；;、，, \n" for c in value):
        raise ValueError("分隔符只能组合分号、顿号、逗号、空格和换行，最多16个字符")
    return value


def format_report_standards(codes, names, show_name=False, separator="semicolon", *, language="CN", styles=None, separator_text=None, records=None):
    parts = []
    rows = records or [{'code': code, 'name': names.get(code) or ''} for code in codes]
    if records:
        from ..standard_control import normalize_code
        covered = {normalize_code(row['code']) for row in records}
        rows = [*records, *[{'code': code, 'name': names.get(code) or ''} for code in codes if normalize_code(code) not in covered]]
    for row in rows:
        code = row['code']
        name = " ".join(str(row.get('name') or "").split())
        key = row.get('key') or 'id:' + str(row.get('id'))
        style = (styles or {}).get(key, (styles or {}).get(code, language))
        title = standard_title(name, style)
        parts.append(f"{code} {title}" if show_name and title else code)
    return display_separator(separator_text, SEPARATORS[standard_separator(separator)]).join(parts)


def judgment_entry(entry):
    titled = re.fullmatch(r'([A-Za-z][^《<>]*\d[^《<>]*?)\s+《(.+)》', entry)
    if titled:
        return titled[1].strip(), titled[2]
    match = _STANDARD_CODE.match(entry)
    return (match[0].strip(), entry[match.end():].strip()) if match else (entry, '')


def judgment_rows(value):
    """Keep handwritten criteria; resolve library names only for selected codes."""
    rows, names = [], {}
    for part in re.split(r'[；;、\n]+', str(value or '')):
        part = part.strip()
        if not part:
            continue
        match = _STANDARD_CODE.match(part)
        code = match[0].strip() if match else part
        if code not in rows:
            rows.append(code)
        if match and part[match.end():].strip():
            names[code] = part[match.end():].strip()
    return rows, names


def judgment_display_settings(value):
    if not isinstance(value, dict):
        raise ValueError('判定依据显示设置格式不正确')
    styles = value.get('standardTitleStyles', {})
    if not isinstance(styles, dict) or any(style not in ('CN', 'EN', 'none') for style in styles.values()):
        raise ValueError('请选择中文书名号、英文书名号或不加书名号')
    show = value.get('standardShowName', True)
    if not isinstance(show, bool):
        raise ValueError('显示标准名称必须为是或否')
    return dict(standardShowName=show, standardTitleStyles=styles,
                standardSeparatorText=display_separator(value.get('standardSeparatorText')))
