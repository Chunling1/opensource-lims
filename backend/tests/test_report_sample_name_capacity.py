"""Real rendering checks for the revised three-line report cover name."""
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest
from app.document_module import render_report

PROFILES = [(k, l, v) for k in ('product', 'sampling') for l in ('CN', 'EN')
            for v in ('Standard', 'Extended')] + [
                (k, l, 'Standard') for k in ('engineering', 'inspection')
                for l in ('CN', 'EN')]


@pytest.mark.parametrize('kind,language,variant', PROFILES)
def test_cover_preserves_110_display_units_and_uses_taller_name_row(kind, language, variant):
    # Chinese characters count as two display units: 55 characters = 110.
    name = '测' * 54 + '终'
    blob, audit = render_report(
        dict(center='LAB', kind=kind, language=language, variant=variant),
        dict(ReportNo='LAB-2026QA-0001', SampleName=name))
    with ZipFile(BytesIO(blob)) as package:
        root = ET.fromstring(package.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    text = ''.join(t.text or '' for t in root.findall('.//w:t', ns))
    assert name in text
    rows = root.findall('.//w:tr', ns)
    name_rows = [r for r in rows if name in ''.join(t.text or '' for t in r.findall('.//w:t', ns))]
    assert name_rows
    # Only the cover uses the fixed all-caps field and the revised row height.
    assert name_rows[0].find('w:trPr/w:trHeight', ns).get('{'+ns['w']+'}val') == '1077'
    assert not audit.get('capacityWarnings')


def test_over_110_still_reports_capacity_problem():
    blob, audit = render_report(dict(center='LAB', kind='product', language='CN', variant='Standard'),
                      dict(ReportNo='LAB-2026QA-0001', SampleName='测' * 56))
    assert blob.startswith(b'PK') and 'SAMPLENAME' in audit['capacityWarnings']


def test_ascii_110_boundary_is_not_cut():
    name = 'A' * 109 + 'Z'
    blob, _ = render_report(dict(center='NCSA', kind='product', language='EN', variant='Standard'),
                            dict(ReportNo='LAB-2026QA-0001', SampleName=name))
    with ZipFile(BytesIO(blob)) as package:
        assert name in package.read('word/document.xml').decode()


@pytest.mark.parametrize('kind,language,variant', PROFILES[:8])
def test_first_page_long_name_does_not_use_cover_cell_geometry(kind, language, variant):
    # Product/sampling contain both fields. Engineering/inspection use
    # EngineeringName on their first page, so that pair is not present there.
    name = '测' * 54 + '终'
    blob, _ = render_report(
        dict(center='LAB', kind=kind, language=language, variant=variant),
        dict(ReportNo='LAB-2026QA-0001', SampleName=name))
    with ZipFile(BytesIO(blob)) as package:
        root = ET.fromstring(package.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    name_paragraphs = [p for p in root.findall('.//w:p', ns)
                       if ''.join(t.text or '' for t in p.findall('.//w:t', ns)) == name]
    assert len(name_paragraphs) >= 2
    # The 34pt first-page cell needs smaller type for 55 Chinese characters.
    # The cover is 53.85pt high and must not supply this cell's geometry.
    style = name_paragraphs[1].find('w:pPr/w:pStyle', ns)
    assert style is not None
    assert not style.get('{'+ns['w']+'}val').startswith('l-')
