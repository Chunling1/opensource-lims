"""Date display at report output boundaries; stored dates remain unchanged."""
import re
from datetime import date, datetime

RELEASE = 'report-date-display-20261103-v3'
EN_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
DATE_FIELDS = frozenset({
    'ManufacturingDate', 'EntrustDate', 'SubmissionDate', 'TestDate',
    'ReportDate', 'OriginalReportDate', 'SampleArrivalDate', 'SamplingDate',
    'CalibrationDate', 'productionDate', 'sampleDate', 'testDate', 'issueDate',
    '委托日期', '检测日期', '检验日期', '校准日期', '送样日期', '接收日期',
    '样品到达日期', '生产日期', '生产日期/批号', '抽样日期', '报告日期',
    '签发日期', '批准日期',
})
_DATE = re.compile(
    r'(?<![A-Za-z0-9])(?P<year>[0-9]{4})'
    r'(?:(?P<sep>[-/.])(?P<month>[0-9]{1,2})(?P=sep)(?P<day>[0-9]{1,2})'
    r'|年\s*(?P<cn_month>[0-9]{1,2})月\s*(?P<cn_day>[0-9]{1,2})日)'
    r'(?![0-9])(?:[ T][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?'
    r'(?:Z|[+-][0-9]{2}:[0-9]{2})?)?'
)
_EN_DATE = (r'(?<![A-Za-z0-9])[0-9]{1,2} (?:' + '|'.join(EN_MONTHS)
            + r') [0-9]{4}(?![A-Za-z0-9])')
_EN_INTERVAL_SEPARATOR = re.compile(
    r'(' + _EN_DATE + r')\s*(至|；)\s*(?=' + _EN_DATE + r')'
)


def report_date(value, *, iso=False, language='CN'):
    """Format valid calendar dates and intervals without inventing missing dates."""
    if value is None:
        return ''
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        value = value.isoformat()
    if not isinstance(value, str):
        return value
    if re.fullmatch(r'\d{4}-\d{2}', value.strip()):
        try:
            month = date.fromisoformat(value.strip() + '-01')
        except ValueError:
            return value
        if iso:
            return value.strip()
        return (f'{EN_MONTHS[month.month - 1]} {month.year}' if language == 'EN'
                else f'{month.year}年{month.month}月')

    def replace(match):
        try:
            day = date(int(match['year']), int(match['month'] or match['cn_month']),
                       int(match['day'] or match['cn_day']))
        except ValueError:
            return match[0]
        if iso:
            return day.isoformat()
        return (f'{day.day} {EN_MONTHS[day.month - 1]} {day.year}' if language == 'EN'
                else f'{day.year}年{day.month}月{day.day}日')

    rendered = _DATE.sub(replace, value)
    if language == 'EN' and not iso:
        # Only separators between dates: preserve free text, markers and IDs.
        rendered = _EN_INTERVAL_SEPARATOR.sub(
            lambda match: match[1] + (' to ' if match[2] == '至' else '; '), rendered)
    return rendered


def compact_test_date(value, *, language='CN'):
    """Shorten only Chinese same-month testing ranges at the output boundary."""
    rendered = report_date(value, language=language)
    if language != 'CN' or not isinstance(rendered, str):
        return rendered
    pattern = re.compile(r'(?P<y1>[0-9]{4})年(?P<m1>[0-9]{1,2})月(?P<d1>[0-9]{1,2})日'
                         r'(?P<sep>\s*(?:至|～|~|—)\s*)'
                         r'(?P<y2>[0-9]{4})年(?P<m2>[0-9]{1,2})月(?P<d2>[0-9]{1,2})日')
    def shorten(match):
        try:
            start = date(int(match['y1']), int(match['m1']), int(match['d1']))
            end = date(int(match['y2']), int(match['m2']), int(match['d2']))
        except ValueError:
            return match[0]
        if (start.year, start.month) != (end.year, end.month) or end < start:
            return match[0]
        return f'{start.year}年{start.month}月{start.day}日{match["sep"]}{end.day}日'
    return pattern.sub(shorten, rendered)


def format_report_dates(values, *, language='CN'):
    # Explicit whitelist: certificates, report numbers, standards, remarks and
    # the tab-separated calibration instrument table are never rewritten.
    return {key: compact_test_date(value, language=language)
            if key in {'TestDate', '检测日期'} else
            report_date(value, language=language) if key in DATE_FIELDS else value
            for key, value in values.items()}


def production_date_text(detail, *, language='CN'):
    """An explicitly saved replacement (including an em dash) is real content."""
    detail = detail or {}
    raw = detail.get('rawSample') or {}
    if raw.get('productionDates'):
        from .production_dates import display_rows
        return display_rows(raw['productionDates'], language=language, formatted=True)
    if 'produceDate' in raw:
        return str(raw['produceDate'] or '').strip()
    for section in detail.get('summary') or []:
        if section.get('title') in ('送样信息', '样品信息'):
            for label, value in section.get('fields') or []:
                if label == '生产日期' and value not in (None, '—', '待填写', '待录入'):
                    return str(value).strip()
    info = (detail.get('entrustSnapshot') or {}).get('info') or {}
    return str(info.get('produceDate') or info.get('manufacturingDate') or '').strip()
