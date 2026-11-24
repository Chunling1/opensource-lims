"""Prepare the saved sample's default entrust PDF after a successful commit.

Uses the existing bounded worker and content-addressed store; no business writes.
Conversion failures remain visible through the normal preview/retry endpoint.
"""
import hashlib
from flask import current_app


def _execute(app, report_no, claim):
    from .extensions import db
    from . import preview_cache as cache
    try:
        with app.app_context():
            db.session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
            from .models import Report, Entrust
            from .sample_entrust import sample_entrust_object
            from .entrust_render import _document_kind, build_entrust_doc
            from .entrust_preview_cache import ensure
            report = Report.query.filter_by(report_no=report_no).first()
            if not report or report.voided:
                return
            entrust = Entrust.query.filter_by(entrust_no=report.entrust_no).first()
            if not entrust:
                return
            entrust = sample_entrust_object(report, entrust)
            kind = _document_kind(entrust, report)
            raw = build_entrust_doc(entrust, report, kind, '')
            if raw:
                ensure(raw, kind)
    except Exception:
        app.logger.exception('sample preview preparation failed')
    finally:
        with app.app_context():
            db.session.remove()
        cache._release(claim)


def schedule_after_save(report):
    from . import preview_cache as cache
    claim = None
    try:
        key = hashlib.sha256(report.report_no.encode()).hexdigest()
        path = cache._entry('sample-warmup-v1', key)
        claim = cache._claim(path)
        if claim is not None:
            cache._enqueue(current_app._get_current_object(), (_execute, report.report_no, claim))
    except Exception:
        if claim is not None:
            cache._release(claim)
        current_app.logger.exception('sample preview enqueue failed after successful save')
