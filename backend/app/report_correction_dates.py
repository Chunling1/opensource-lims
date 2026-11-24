"""Original issue dates belong to approved corrections, not editing rounds."""
import re
from datetime import date


def calendar_date(value):
    value = str(value or '').strip()
    match = re.fullmatch(r'(\d{4})(?:-|/|年)(\d{1,2})(?:-|/|月)(\d{1,2})日?', value)
    if not match:
        return ''
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return ''


def freeze_original_date(report, request_id):
    """Capture before clearing approval pointers or starting a new round."""
    from .report_business_date import report_date
    return {'requestId': request_id, 'sourceReportNo': report.report_no,
            'sourceVersionId': report.approved_document_version_id,
            'date': calendar_date(report_date(report))}


def original_issue_date(report):
    from .extensions import db
    from .models import ReportCorrectionRequest, ReportDocumentVersion
    detail = getattr(report, 'detail', None) or {}
    external = getattr(report, 'report_kind', None) == 'correction'
    internal = detail.get('internalCorrectionRevision')
    # A return, version number, or copied summary is not a correction.
    if not external and not internal:
        return ''
    request_id = detail.get('correctionRequestId')
    row = db.session.get(ReportCorrectionRequest, request_id) if request_id else None
    if row and (row.status != 'approved' or row.correction_report_no != report.report_no):
        return ''
    if internal and (not row or row.id != internal or row.correction_type != 'internal'):
        return ''
    if external and row and row.main_report_no != getattr(report, 'main_report_no', None):
        return ''
    frozen = detail.get('correctionOriginalIssueDate') or {}
    if (row and frozen.get('requestId') == row.id
            and frozen.get('sourceReportNo') == row.main_report_no):
        return calendar_date(frozen.get('date'))
    if internal:
        # Existing same-number corrections already retain the old pointer.
        from .internal_report_corrections import history_for
        audit = history_for(row.id)
        before = (audit.before_data or {}) if audit else {}
        version_id = (before.get('report') or {}).get('approvedDocumentVersionId')
        allowed = {v.get('id') for v in before.get('versions', [])}
        version = db.session.get(ReportDocumentVersion, version_id) if version_id in allowed else None
        if version and version.report_no == report.report_no:
            return calendar_date((version.snapshot or {}).get('approvalDate'))
    # Legacy explicit correction reports may carry the original date in their
    # historical summary. Empty markers such as '/' never activate the label.
    from .docparser_field_only import section_field
    return calendar_date(section_field(report, '实验信息', '原报告日期'))
