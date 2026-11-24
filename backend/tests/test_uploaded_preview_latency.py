"""Preserved uploads must not wait for unrelated Office/template generation."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import fitz
import pytest

pytest_plugins = ('testkit.fixtures',)


def pdf(*texts):
    with fitz.open() as doc:
        for text in texts:
            doc.new_page().insert_text((50, 100), text)
        from qr_pdf_fixture import add_cover_qr
        add_cover_qr(doc)
        return doc.tobytes()


@pytest.mark.parametrize('word', [False, True])
def test_preserved_pdf_or_cached_word_finishes_while_other_wps_job_is_busy(isolated_app, monkeypatch, word):
    from app import preview_cache as cache, report_documents as documents, docparser_field_only as fields
    from app import docx_pdf, preview_fingerprint
    from app.extensions import db
    from app.models import Report, ReportAttachment
    monkeypatch.setattr(documents, 'select_profile', lambda _: None)
    monkeypatch.setattr(fields, 'applies_to', lambda _: True)
    monkeypatch.setattr(fields, 'profile_for', lambda _: dict(kind='engineering', language='CN', variant='Standard'))
    monkeypatch.setattr(cache, 'source_snapshot', lambda r: {'detail': r.detail})
    monkeypatch.setattr(preview_fingerprint, 'office_conversion_hash', lambda: 'isolated-renderer')
    no = 'LAB-QA-FAST-UPLOAD'
    original = pdf(no + ' CUSTOM COVER', 'RESULTS', 'CUSTOM LAST PAGE')
    conversions = []
    monkeypatch.setattr(docx_pdf, '_office_to_pdf_with', lambda *args: conversions.append(1) or original)
    with isolated_app.app_context():
        report = Report(report_no=no, sample_no='QA-FAST-UPLOAD', detail={
            'reportComposition': {'preserveUploadedReport': True}})
        db.session.add(report)
        db.session.add(ReportAttachment(report_no=no, name='edited.' + ('docx' if word else 'pdf'),
            content_type='application/octet-stream', kind='Word' if word else 'PDF',
            source='完整报告正文', status='已上传', data=b'isolated Word source' if word else original))
        db.session.commit()
        if word:
            assert docx_pdf.office_to_pdf_wps(b'isolated Word source') == original
    entered, release = threading.Event(), threading.Event()

    def busy(app):
        with app.app_context():
            path = cache._root() / 'render'
            path.mkdir(exist_ok=True)
            claim = cache._claim(path, blocking=True)
            try:
                entered.set()
                assert release.wait(20)
            finally:
                cache._release(claim)

    cache._enqueue(isolated_app, (busy,))
    assert entered.wait(3)
    started = time.monotonic()
    try:
        with isolated_app.app_context():
            state = cache.prepare(Report.query.filter_by(report_no=no).one())
            while state['status'] in ('queued', 'running') and time.monotonic() - started < 8:
                time.sleep(.05)
                db.session.remove()
                state = cache.status(Report.query.filter_by(report_no=no).one())
            assert state['status'] == 'ready', state
            raw, _ = cache.cached_pdf(Report.query.filter_by(report_no=no).one())
            with fitz.open(stream=raw, filetype='pdf') as output:
                assert len(output) == 3
                assert 'CUSTOM COVER' in output[0].get_text()
                assert 'CUSTOM LAST PAGE' in output[2].get_text()
            print(f'preserved_{"cached_word" if word else "pdf"}_while_wps_busy_ms={(time.monotonic()-started)*1000:.1f}')
            assert len(conversions) == int(word)
    finally:
        release.set()
        for key in ('preview_tasks', 'uploaded_preview_tasks'):
            if key in isolated_app.extensions:
                isolated_app.extensions[key].join()


def test_uncached_word_conversions_stay_serial_and_failures_release_slot(isolated_app, monkeypatch):
    from app import wps_pdf_cache, preview_fingerprint
    monkeypatch.setattr(preview_fingerprint, 'office_conversion_hash', lambda: 'isolated-renderer')
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
    output = pdf('converted')

    def first():
        with isolated_app.app_context():
            def fail():
                entered.set()
                assert release.wait(5)
                raise ValueError('isolated conversion failure')
            return wps_pdf_cache.convert_once(b'first', '.doc', fail)

    def second():
        with isolated_app.app_context():
            return wps_pdf_cache.convert_once(b'second', '.doc', lambda: second_started.set() or output)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        assert entered.wait(3)
        b = pool.submit(second)
        try:
            assert not second_started.wait(.25), 'Different Word documents must not convert concurrently'
        finally:
            release.set()
        with pytest.raises(ValueError, match='isolated conversion failure'):
            a.result(timeout=5)
        assert b.result(timeout=5) == output
    with isolated_app.app_context():
        assert wps_pdf_cache.convert_once(b'first', '.doc', lambda: output) == output


def test_changed_source_during_composition_never_publishes_old_preview(isolated_app, monkeypatch):
    from sqlalchemy.orm import Session
    from app import preview_cache as cache
    from app.extensions import db
    from app.models import Report
    monkeypatch.setattr(cache, 'source_snapshot', lambda r: {'detail': r.detail})
    monkeypatch.setattr(cache, '_enqueue', lambda app, task, **kwargs: cache._execute(app, *task))
    with isolated_app.app_context():
        report = Report(report_no='QA-RACE', sample_no='QA-RACE-S', detail={
            'reportComposition': {'preserveUploadedReport': True}, 'revision': 1})
        db.session.add(report)
        db.session.commit()
        key = cache.source_key(report)
        path = cache._entry(report.report_no, key)

        def build(current):
            # Independent transaction models another request changing the source.
            with Session(db.engine) as other:
                row = other.get(Report, current.id)
                row.detail = {**row.detail, 'revision': 2}
                other.commit()
            return pdf('old output'), []

        monkeypatch.setattr(cache, 'build_complete_report_pdf', build)
        cache.prepare(report)
        assert cache._state(path)['status'] == 'stale'
        assert not (path / 'preview.pdf').exists()
        assert cache.cached_pdf(Report.query.filter_by(report_no='QA-RACE').one())[0] is None
