"""One read policy for entry state, shared by lists and pickup recall.

Opening a form does not start entry. Explicit saves set dataEntryStarted;
legacy copied checkInput values are disambiguated by successful pickup/save
audits. List callers reuse the request-local batch audit reader.
"""
from .status_machine import detection_data_started


def report_data_entry_started(report):
    detail = report.detail or {}
    if detail.get('dataEntryStarted') is not None:
        return bool(detail['dataEntryStarted'])
    # Unsaved form objects have no persisted audit history.
    if not getattr(report, 'id', None) or not getattr(report, 'report_no', None):
        return detection_data_started(detail)
    from .platform.audit import latest_operation_audit
    pickup = latest_operation_audit('report', report.report_no, 'sample.out_warehouse.sign')
    if pickup is None:
        return detection_data_started(detail)
    saved = latest_operation_audit('report', report.report_no, 'report.data_entry.save')
    return bool(saved and saved.id > pickup.id)
