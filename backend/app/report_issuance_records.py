"""Read-only export of selected, page-authorized report issuance records."""
from .docparser_field_only import report_cover_names, section_field
from .entrust_render import _report_copy_count, _clean


def issuance_row(report):
    # Use the same field projection as the report cover, not the list's test items.
    context = report_cover_names(report)
    detail = report.detail or {}
    raw = detail.get('rawSample') or {}
    info = (detail.get('entrustSnapshot') or {}).get('info') or {}
    ci = detail.get('checkInput') or {}
    people = ci.get('people') or {}
    assigned = ci.get('assignedPeople') or detail.get('assignedPeople') or {}
    def name(value):
        return _clean(value.get('name')) if isinstance(value, dict) else _clean(value)
    first = name(people.get('primaryTester1')) or name(assigned.get('primaryTester1')) or _clean(report.owner)
    second = name(people['primaryTester2'] if 'primaryTester2' in people else assigned.get('primaryTester2'))
    authors = list(dict.fromkeys(x for x in (first, second) if x))
    quantity = next((_clean(v) for v in (raw.get('deliverStd'), info.get('reportCopies'),
                    section_field(report, '报告发送', '报告交付份数')) if _clean(v)), '')
    return dict(no=report.report_no, au='、'.join(authors), nam=context['SampleName'],
                cli=context['Client'], qty=_report_copy_count(quantity))
