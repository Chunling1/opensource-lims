"""One report date source for public output and financial integration."""


def report_date(report):
    from .extensions import db
    from .models import ReportDocumentVersion
    from .report_final_fields import approval_date

    version_id = getattr(report, 'approved_document_version_id', None)
    if version_id:
        version = db.session.get(ReportDocumentVersion, version_id)
        if version and version.report_no == report.report_no:
            value = (version.snapshot or {}).get('approvalDate')
            if value:
                return value
    return approval_date(report) or ''
