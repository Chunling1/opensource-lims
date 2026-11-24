"""Cheap revision gate for previews; uploads are immutable, replacements get new IDs.

Report.edit_version is incremented by SQLAlchemy in the business transaction.
Content timestamps and attachment metadata cover saves independent of Report.
No PDF/DOCX bytes or template directories are read on a revision-cache hit.
"""
from collections import OrderedDict
from datetime import datetime
import threading

from flask import current_app
from .models import ReportAttachment, ReportDocumentContent, StoredFile
from .report_documents import select_profile, snapshot_hash
from .report_final_fields import approval_date

_lock = threading.Lock()


def _attachment_changed(mapper, connection, row):
    # Also cover legacy in-place binary replacement; normal uploads use new IDs.
    from sqlalchemy import inspect
    if any(inspect(row).attrs[name].history.has_changes() for name in ('data', 'file_id')):
        row.uploaded_at = datetime.utcnow()


def install():
    from sqlalchemy import event
    if not event.contains(ReportAttachment, 'before_update', _attachment_changed):
        event.listen(ReportAttachment, 'before_update', _attachment_changed)


def frozen_original(report):
    # An old approval pointer survives returns. It is authoritative only in
    # the post-approval workflow, never in registration/review/data changes.
    return report.status in {'待打印', '待发放', '已发放', '已归档'}


def revision_key(report, engine):
    attachments = ReportAttachment.query.with_entities(
        ReportAttachment.id, ReportAttachment.name, ReportAttachment.source,
        ReportAttachment.content_type, ReportAttachment.status,
        ReportAttachment.file_id, ReportAttachment.uploaded_at,
        ReportAttachment.deleted_at, StoredFile.sha256,
    ).outerjoin(StoredFile, ReportAttachment.file_id == StoredFile.id).filter(
        ReportAttachment.report_no == report.report_no).order_by(ReportAttachment.id).all()
    content = ReportDocumentContent.query.with_entities(
        ReportDocumentContent.id, ReportDocumentContent.updated_at,
    ).filter_by(report_no=report.report_no).first()
    profile = select_profile(report)
    return snapshot_hash({'engine': engine, 'report': report.id,
        'revision': report.edit_version, 'content': [str(v) for v in content] if content else None,
        'attachments': [[str(v) for v in row] for row in attachments],
        'profile': profile.to_dict() if profile else None, 'approvalDate': approval_date(report)})


def source_hash(report, engine, snapshot):
    revision = revision_key(report, engine)
    app = current_app._get_current_object()
    with _lock:
        cache = app.extensions.setdefault('report_preview_revisions', OrderedDict())
        if revision in cache:
            cache.move_to_end(revision)
            return cache[revision]
    value = snapshot_hash({'schema': 2, 'engine': engine, 'source': snapshot(report)})
    with _lock:
        cache[revision] = value
        cache.move_to_end(revision)
        while len(cache) > 512:
            cache.popitem(last=False)
    return value
