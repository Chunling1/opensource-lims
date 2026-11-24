from io import BytesIO
from zipfile import ZipFile

import fitz
import pytest
from docx import Document
from lxml import etree
from PIL import Image

from app import conclusion_image, document_module

pytest_plugins = ('testkit.fixtures',)


def pdf(pages=1, blank=False, height=80):
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        if not blank:
            page.insert_text((72, 75), 'Conclusion table', fontsize=10)
            page.draw_rect(fitz.Rect(72, 80, 330, 80+height))
            page.insert_text((72, 95+height), 'Final conclusion: PASS', fontsize=10)
    return doc.tobytes()


def word():
    doc = Document()
    doc.add_table(rows=4, cols=3).cell(0, 0).text = 'test table'
    buf = BytesIO(); doc.save(buf)
    return buf.getvalue()


def test_render_keeps_full_ink_and_crops_white_margins():
    image, info = conclusion_image.render(word(), lambda _: pdf(height=30))
    assert 250 < info['widthPt'] < 265
    assert 50 < info['heightPt'] < 75
    assert info['minFontPt'] == 10
    assert Image.open(BytesIO(image)).height == round(info['heightPt']*3)


@pytest.mark.parametrize('data,message', [(b'', '转换失败'), (pdf(blank=True), '没有可见'), (pdf(pages=2), '多页')])
def test_invalid_conclusions_fail_explicitly(data, message):
    with pytest.raises(ValueError, match=message):
        conclusion_image.render(word(), lambda _: data)


PROFILE = dict(kind='product', center='LAB', language='CN', variant='Standard')


@pytest.mark.parametrize('language,variant', [('CN','Standard'), ('CN','Extended'), ('EN','Standard'), ('EN','Extended')])
def test_actual_worker_preserves_native_table_formula_and_long_content(language, variant, monkeypatch):
    from docx.oxml import parse_xml
    from docx.shared import Pt
    def unexpected(*args, **kwargs):
        raise AssertionError('Conclusion must not be converted to an image')
    monkeypatch.setattr(conclusion_image, 'render', unexpected)
    monkeypatch.setattr('app.docx_pdf.docx_to_pdf_wps', unexpected)
    doc = Document(BytesIO(word()))
    # Deliberately below the old platform font floor and longer than one cell.
    for index in range(70):
        doc.add_paragraph(f'Conclusion row {index}').runs[0].font.size = Pt(6)
    doc.add_paragraph()._p.append(parse_xml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:f><m:num><m:r><m:t>x</m:t></m:r></m:num>'
        '<m:den><m:r><m:t>y</m:t></m:r></m:den></m:f></m:oMath>'))
    doc.add_paragraph('CONCLUSION END MARKER')
    buf = BytesIO(); doc.save(buf)
    blob, audit = document_module.render_report(dict(PROFILE, language=language, variant=variant),
        {'Conclusion': 'original conclusion'}, buf.getvalue())
    with ZipFile(BytesIO(blob)) as package:
        xml = etree.fromstring(package.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
              'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
        texts = xml.xpath('//w:t/text()', namespaces=ns)
        assert 'original conclusion' not in texts
        assert 'test table' in texts
        assert 'CONCLUSION END MARKER' in texts
        assert all(f'Conclusion row {index}' in texts for index in range(70))
        assert xml.xpath('//m:f/m:num/m:r/m:t/text()', namespaces=ns) == ['x']
        assert xml.xpath('//m:f/m:den/m:r/m:t/text()', namespaces=ns) == ['y']
        assert audit['conclusionRendering']['policy'] == document_module.CONCLUSION_POLICY


def test_original_conclusion_bytes_reach_worker(monkeypatch):
    import json
    from pathlib import Path
    original_run = document_module.subprocess.run
    source = word()
    def inspected_run(*args, **kwargs):
        payload = json.loads(kwargs['input'])
        assert Path(payload['conclusion']).name == 'Conclusion.docx'
        assert Path(payload['conclusion']).read_bytes() == source
        assert 'conclusionImage' not in payload
        return original_run(*args, **kwargs)
    monkeypatch.setattr(document_module.subprocess, 'run', inspected_run)
    document_module.render_report(PROFILE, {}, source)


def test_invalid_docx_still_rejected():
    with pytest.raises(ValueError, match='Word'):
        document_module.render_report(PROFILE, {}, b'not a docx')


def test_ordinary_report_has_no_conclusion_audit():
    _, audit = document_module.render_report(PROFILE, {})
    assert 'conclusionRendering' not in audit


def test_attachment_selection_snapshot_and_preserve_boundary(isolated_app, monkeypatch):
    from app import report_documents as documents, docparser_field_only as fields
    from app.extensions import db
    from app.models import Report, ReportAttachment
    monkeypatch.setattr(documents, 'select_profile', lambda _: None)
    monkeypatch.setattr(fields, 'applies_to', lambda _: True)
    monkeypatch.setattr(fields, 'template_snapshot', lambda *a, **kw: {'version': 'fixture'})
    monkeypatch.setattr(fields, 'profile_for', lambda _: PROFILE)
    monkeypatch.setattr(documents, '_report_page_pdfs', lambda *a, **kw: ([pdf()], []))
    monkeypatch.setattr('app.report_final_fields.approval_date', lambda _: '')
    with isolated_app.app_context():
        report = Report(report_no='LAB-QA-CONCLUSION', sample_no='QA-CONCLUSION', detail={})
        item = ReportAttachment(report_no=report.report_no, name='Conclusion.docx',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            kind='Word', source='其他附件', status='已上传', data=word())
        ordinary = ReportAttachment(report_no=report.report_no, name='other.docx',
            content_type=item.content_type, kind='Word', source='其他附件', status='已上传', data=word())
        db.session.add_all([report, item, ordinary]); db.session.commit()
        snapshot = documents.source_snapshot(report, content={'photos': []})
        assert snapshot['attachments'][0]['renderingPolicy'] == document_module.CONCLUSION_POLICY
        assert [a['id'] for a in snapshot['attachments']] == [item.id]
        assert documents._selected_other_attachment_pdfs(report, strict_wps=True) == []
        report.detail = {'reportComposition': {'preserveUploadedReport': True}}
        with pytest.raises(ValueError, match='移除独立 Conclusion'):
            documents._compose_complete_report_pdf(report)
        duplicate = ReportAttachment(report_no=report.report_no, name='CONCLUSION.DOCX',
            content_type=item.content_type, kind='Word', source='其他附件', status='已上传', data=word())
        db.session.add(duplicate); db.session.commit()
        with pytest.raises(ValueError, match='多个有效 Conclusion'):
            documents._compose_complete_report_pdf(report)
