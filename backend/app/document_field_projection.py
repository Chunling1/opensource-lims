"""Read-only projections shared by commission and report template adapters.

Never infer actual test dates from commission, sampling or submission dates.
Saved structured values take precedence over historical display summaries.
"""
import re


def _text(value):
    value = str(value or '').strip()
    return '' if value in ('—', '-', '待录入', '待检测人员录入', '待检测人员录入并上传') else value


def judgment_basis(detail, legacy='', *, report=False, language=None):
    raw = (detail or {}).get('rawSample') or {}
    value = _text(raw['standardJudge']) if 'standardJudge' in raw else _text(legacy)
    entries = raw.get('judgmentEntries')
    if not value and entries is None:
        return value
    from .functions.report_standard_text import (judgment_entry, judgment_rows, judgment_display_settings,
        load_report_standard_names, load_report_standard_records, format_report_standards, standard_title)
    settings = ((detail or {}).get('checkInput') or {}).get('judgmentDisplay') if report else None
    if settings is None:
        settings = raw.get('judgmentDisplay')
    if entries is not None:
        from .standard_control import normalize_code
        settings = judgment_display_settings(settings or {})
        selected_language = language or (((detail or {}).get('reportComposition') or {}).get('reportLanguage') if report else None) or raw.get('reportLanguage') or 'CN'
        parsed = [(entry, *judgment_entry(entry)) for entry in entries]
        selected = [code for _, code, name in parsed if not name and re.match(r'^[A-Za-z].*\d', code)]
        names = load_report_standard_names(selected)
        library_records = load_report_standard_records(selected, raw.get('standardItemIds'))
        records = []
        for entry, code, name in parsed:
            if name:
                records.append({'key': entry, 'code': code, 'name': name})
                continue
            matches = [row for row in library_records if normalize_code(row['code']) == normalize_code(code)]
            records.extend(matches or [{'code': code, 'name': names.get(code) or ''}])
        return format_report_standards([], {}, settings['standardShowName'], language=selected_language,
            styles=settings['standardTitleStyles'], separator_text=settings['standardSeparatorText'], records=records)
    codes, embedded = judgment_rows(value)
    selected = [code for code in codes if re.match(r'^[A-Za-z].*\d', code)]
    names = {**load_report_standard_names(selected), **embedded}
    records = load_report_standard_records([code for code in selected if code not in embedded], raw.get('standardItemIds'))
    if settings is not None:
        from .standard_control import normalize_code
        records = [row for code in codes for row in (
            [row for row in records if normalize_code(row['code']) == normalize_code(code)]
            or [{'code': code, 'name': names.get(code) or ''}])]
        settings = judgment_display_settings(settings)
        selected_language = language or (((detail or {}).get('reportComposition') or {}).get('reportLanguage') if report else None) or raw.get('reportLanguage') or 'CN'
        return format_report_standards(codes, names, settings['standardShowName'],
            language=selected_language, styles=settings['standardTitleStyles'],
            separator_text=settings['standardSeparatorText'], records=records)
    # Historical free text retains its spacing and separators. Name resolution
    # uses the same exact/normalized-code rules as the detection basis.
    for code in sorted(selected, key=len, reverse=True):
        if names.get(code) and code not in embedded:
            value = re.sub(r'(?<![A-Za-z0-9])' + re.escape(code) + r'(?![A-Za-z0-9])',
                           lambda _: code + standard_title(names[code]), value)
    return value


def test_items(detail, legacy='', *, separator=None):
    raw = (detail or {}).get('rawSample') or {}
    joiner = '、' if separator is None else separator
    manual = raw.get('manualCapabilityItems')
    order = raw.get('testItemOrder')
    if isinstance(order, list) and order:
        ids = list(dict.fromkeys(str(value) for value in raw.get('capabilityEntryIds') or []))
        snapshots = {str(row.get('id')): _text(row.get('itemName'))
                     for row in raw.get('capabilitySnapshots') or [] if isinstance(row, dict)}
        manual_names = [_text(value) for value in manual or []] if isinstance(manual, list) else []
        available = {('library', key): snapshots[key] for key in ids if snapshots.get(key)}
        available.update({('manual', name): name for name in manual_names if name})
        # References only control order; names still come from the saved selection.
        # Incomplete old snapshots retain the legacy projection instead of losing items.
        if all(snapshots.get(key) for key in ids):
            names = []
            for item in order:
                if not isinstance(item, dict):
                    continue
                kind = item.get('kind')
                key = (kind, str(item.get('id')) if kind == 'library' else _text(item.get('name')))
                name = available.pop(key, None)
                if name:
                    names.append(name)
            names.extend(available.values())
            return joiner.join(names)
    if separator is not None:
        projects = raw.get('projectList')
        if isinstance(projects, list) and projects:
            return joiner.join(filter(None, map(_text, projects)))
        commission_text = raw.get('commissionText')
        saved_text = commission_text.get('items') if isinstance(commission_text, dict) else None
        if isinstance(saved_text, str) and saved_text:
            return saved_text
    if not isinstance(manual, list) or not manual:
        return _text(legacy)
    base = _text(legacy)
    # Do not split punctuation inside a manually entered parameter name.
    existing = set(base.split('、'))
    additions = []
    for value in manual:
        name = _text(value)
        if name and name not in existing:
            additions.append(name)
            existing.add(name)
    return joiner.join(filter(None, [base, *additions]))


def test_dates(detail, legacy_start='', legacy_end='', legacy_intervals=''):
    check = (detail or {}).get('checkInput') or {}
    if 'testIntervals' in check and isinstance(check['testIntervals'], list):
        pairs = [(_text(row.get('start')), _text(row.get('end')))
                 for row in check['testIntervals'] if isinstance(row, dict)]
    elif 'testStartDate' in check or 'testDate' in check:
        pairs = [(_text(check.get('testStartDate')), _text(check.get('testDate')))]
    else:
        start, end = _text(legacy_start), _text(legacy_end)
        if not start and not end and _text(legacy_intervals):
            return '', '', _text(legacy_intervals)
        pairs = [(start, end)]
    starts = [start for start, _ in pairs if start]
    ends = [end for _, end in pairs if end]
    # The template slot is "Date of Test", not the full timestamp audit trail.
    # Keep stored timestamps intact; only project their calendar dates.
    def date(value):
        return value[:10] if re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[ T])', value) else value
    dates = [(date(start), date(end)) for start, end in pairs]
    rendered = [start if start == end else '至'.join(filter(None, (start, end)))
                for start, end in dates if start or end]
    return min(starts, default=''), max(ends, default=''), '；'.join(rendered)
