"""Exercise preserved uploads through the actual background preview cache.

Temporary SQLite/files only. WPS is substituted; PDF validation and supplier
composition remain real, so changed cover text and attachment order are checked.
"""
import socket
from unittest.mock import Mock

import fitz
import pytest

pytest_plugins = ('testkit.fixtures',)


def pdf(*pages):
    with fitz.open() as document:
        for text in pages:
            document.new_page().insert_text((50, 100), text)
        from qr_pdf_fixture import add_cover_qr
        add_cover_qr(document)
        return document.tobytes()


@pytest.fixture
def preserved(isolated_app, monkeypatch):
    from app import preview_cache as cache, report_documents as documents, docparser_field_only as fields
    from app.extensions import db
    from app.models import Report, ReportAttachment

    def deny_network(*args, **kwargs):
        raise AssertionError('Preview test must not access external services')
    monkeypatch.setattr(socket, 'create_connection', deny_network)
    monkeypatch.setattr(socket.socket, 'connect', deny_network)
    monkeypatch.setattr(documents, 'select_profile', lambda _: None)
    monkeypatch.setattr(fields, 'applies_to', lambda _: True)
    monkeypatch.setattr(fields, 'profile_for', lambda _: dict(kind='engineering', language='CN', variant='Standard'))
    # Hash only the fixture data; package selection itself is outside this test.
    monkeypatch.setattr(cache, 'source_snapshot', lambda r: {'detail': r.detail})
    monkeypatch.setattr(cache, '_enqueue', lambda app, task, **kwargs: cache._execute(app, *task))
    from app import document_module
    render = Mock(side_effect=AssertionError('Preserve mode must not regenerate system cover'))
    monkeypatch.setattr(document_module, 'render_report', render)
    with isolated_app.app_context():
        report = Report(report_no='LAB-QA-PRESERVE', sample_no='QA-PRESERVE', detail={
            'reportComposition': {'preserveUploadedReport': True}})
        upload = ReportAttachment(report_no=report.report_no, name='changed-cover.pdf',
            content_type='application/pdf', kind='PDF', source='完整报告正文', status='已上传',
            data=pdf('LAB-QA-PRESERVE CUSTOM COVER', 'TEST RESULTS', 'CUSTOM LAST PAGE'))
        extra = ReportAttachment(report_no=report.report_no, name='extra.pdf',
            content_type='application/pdf', kind='PDF', source='其他附件', status='已上传', data=pdf('SELECTED EXTRA'))
        db.session.add_all([report, upload, extra]); db.session.flush()
        report.detail={'rawSample': {'sampleName': 'Long sample name ' * 100},
                       'reportComposition': {'preserveUploadedReport': True, 'includedOtherAttachmentIds': [extra.id]}}
        db.session.commit()
        yield cache, documents, report, upload, render


@pytest.mark.parametrize('word', [False, True])
def test_changed_cover_reaches_ready_cache_with_all_pages(preserved, monkeypatch, word):
    cache, documents, report, upload, render = preserved
    from app.extensions import db
    from app.models import Report
    converter = Mock(return_value=upload.data)
    monkeypatch.setattr(documents, 'office_to_pdf_wps', converter)
    if word:
        upload.name='changed-cover.docx'
        upload.content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        upload.data=b'isolated WPS conversion input'
        db.session.commit()
    no=report.report_no
    _, warnings=documents.build_complete_report_pdf(report)
    assert warnings == []  # Mode information must not become a fatal warning.
    cache.prepare(report)
    current=Report.query.filter_by(report_no=no).one()
    raw, state=cache.cached_pdf(current)
    assert state['status'] == 'ready', state
    with fitz.open(stream=raw, filetype='pdf') as output:
        texts=[page.get_text() for page in output]
    assert len(texts) == 4
    assert 'CUSTOM COVER' in texts[0]
    assert 'TEST RESULTS' in texts[1]
    # Supplier composition inserts appendices before the retained notice/back
    # page. Uploaded pages keep their relative order and are never replaced.
    assert 'SELECTED EXTRA' in texts[2]
    assert 'CUSTOM LAST PAGE' in texts[3]
    render.assert_not_called()
    assert converter.call_count == (2 if word else 0)


def test_preserve_still_rejects_report_identity_mismatch(preserved):
    cache, _, report, upload, _ = preserved
    from app.extensions import db
    from app.models import Report
    no=report.report_no
    upload.data=pdf('WRONG REPORT CUSTOM COVER', 'RESULTS', 'LAST PAGE'); db.session.commit()
    cache.prepare(report)
    raw, state=cache.cached_pdf(Report.query.filter_by(report_no=no).one())
    assert raw is None and state['status'] == 'failed'
    assert '报告编号' in state['message']


def test_real_conversion_warning_remains_blocking(preserved, monkeypatch):
    cache, _, report, _, _ = preserved
    from app.models import Report
    no=report.report_no
    monkeypatch.setattr(cache, 'build_complete_report_pdf', lambda _: (pdf('partial'), ['附件转 PDF 失败，未并入完整报告']))
    cache.prepare(report)
    raw, state=cache.cached_pdf(Report.query.filter_by(report_no=no).one())
    assert raw is None and state['status'] == 'failed'
    assert '附件转 PDF 失败' in state['message']


def test_failed_conversion_can_be_explicitly_retried(preserved, monkeypatch):
    cache, _, report, _, _ = preserved
    from app.models import Report
    no=report.report_no
    real=cache.build_complete_report_pdf
    monkeypatch.setattr(cache, 'build_complete_report_pdf', Mock(side_effect=ValueError('转换暂不可用')))
    cache.prepare(report)
    current=Report.query.filter_by(report_no=no).one()
    assert cache.status(current)['status'] == 'failed'
    monkeypatch.setattr(cache, 'build_complete_report_pdf', real)
    assert cache.prepare(current)['status'] == 'failed'  # No automatic retry.
    cache.prepare(current, retry=True)
    raw, state=cache.cached_pdf(Report.query.filter_by(report_no=no).one())
    assert state['status'] == 'ready' and raw.startswith(b'%PDF-')


@pytest.mark.parametrize('problem', ['short_pdf', 'broken_pdf', 'wps_failure'])
def test_preserve_does_not_bypass_file_conversion_checks(preserved, monkeypatch, problem):
    cache, documents, report, upload, _ = preserved
    from app.extensions import db
    from app.models import Report
    no=report.report_no
    if problem == 'short_pdf':
        upload.data=pdf(no + ' ONLY COVER')
    elif problem == 'broken_pdf':
        upload.data=b'%PDF-not-a-valid-document'
    else:
        upload.name='changed-cover.docx'; upload.content_type='application/msword'
        monkeypatch.setattr(documents, 'office_to_pdf_wps', lambda *_: None)
    db.session.commit()
    cache.prepare(report)
    raw, state=cache.cached_pdf(Report.query.filter_by(report_no=no).one())
    assert raw is None and state['status'] == 'failed'
    assert state['message']
