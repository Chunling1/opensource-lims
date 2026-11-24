"""Legacy generated covers must never masquerade as user attachments."""
from types import SimpleNamespace

import pytest

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture
def files(isolated_app):
    from app.extensions import db
    from app.models import Report, ReportAttachment
    with isolated_app.app_context():
        report = Report(report_no='COVER-TEST', sample_no='COVER-TEST-S', status='待审核', detail={})
        cover = ReportAttachment(report_no=report.report_no, name='系统生成封面.docx',
                                 source='模板生成', status='已生成', data=b'legacy-system')
        uploaded = ReportAttachment(report_no=report.report_no, name='系统生成封面.docx',
                                    source='其他附件', status='已上传', data=b'user-document')
        db.session.add_all([report, cover, uploaded]); db.session.flush()
        report.detail = {'reportComposition': {'includedOtherAttachmentIds': [cover.id, uploaded.id]}}
        db.session.commit()
        yield report, cover, uploaded


def test_list_hides_generated_cover_but_keeps_same_name_upload(files, isolated_app, monkeypatch):
    from flask import g
    from app.blueprints import attachments
    report, cover, uploaded = files
    monkeypatch.setattr(attachments, '_report_for_read', lambda *_: (report, None))
    with isolated_app.test_request_context():
        g.current_user = SimpleNamespace()
        response = attachments.list_attachments.__wrapped__(report.report_no)
        rows = response.get_json()['data']['rows']
    assert [row['id'] for row in rows] == [uploaded.id]
    assert not rows[0]['superseded']


def test_saved_cover_selection_is_ignored_without_reading_or_converting_it(files, monkeypatch):
    from app import report_documents as documents
    from app.blueprints.report_documents import _clean_composition_options
    report, cover, uploaded = files
    # Exercise previously persisted selections, including IDs sent by an older client.
    ids = [cover.id, uploaded.id]
    monkeypatch.setattr(documents, 'composition_options', lambda _: {'includedOtherAttachmentIds': ids})
    converted = []
    monkeypatch.setattr(documents, 'office_to_pdf_wps', lambda raw, suffix: converted.append(raw) or b'%PDF-user')
    assert documents._selected_other_attachment_pdfs(report) == [b'%PDF-user']
    assert converted == [b'user-document']
    assert _clean_composition_options(report.report_no, {'includedOtherAttachmentIds': ids}) == {
        'includedOtherAttachmentIds': [uploaded.id]}
    assert not documents.attachment_merge_eligible(cover)
    assert documents.attachment_merge_eligible(uploaded)
    fingerprints = documents._attachment_fingerprints(report.report_no,
        {'compositionOptions': {'includedOtherAttachmentIds': ids}}, 'official')
    assert [row['id'] for row in fingerprints] == [uploaded.id]


def test_template_cover_generation_remains_available_without_attachment_persistence(monkeypatch):
    from app import report_documents as documents, docparser_field_only
    monkeypatch.setattr(docparser_field_only, 'applies_to', lambda _: False)
    monkeypatch.setattr(documents, 'build_cover_from_template', lambda _: b'template-cover-and-home')
    assert documents.build_document(SimpleNamespace(), {}, None) == b'template-cover-and-home'
