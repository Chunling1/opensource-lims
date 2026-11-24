"""Supplier date paragraphs: preserve complete dates in all eight templates."""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile
from lxml import etree
import pytest
from app import document_module

PROFILES = [(kind, variant, language) for kind in ('product', 'sampling')
            for variant in ('Standard', 'Extended') for language in ('CN', 'EN')]
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

@pytest.mark.parametrize('kind,variant,language', PROFILES)
@pytest.mark.parametrize('case', ['short', 'intervals', 'components', 'empty'])
def test_complete_dates_render_in_their_original_cells(kind, variant, language, case):
    dates = {
        'short': ('2026年11月3日至2026年11月5日', '3 Nov 2026 to 5 Nov 2026'),
        'intervals': ('2026年9月1日至2026年9月3日；2026年10月11日至2026年10月15日',
                      '1 Sep 2026 to 3 Sep 2026; 11 Oct 2026 to 15 Oct 2026'),
        'components': ('2026年9月1日（室内机）\n2026年10月15日（室外机）',
                       '1 Sep 2026 (indoor unit)\n15 Oct 2026 (outdoor unit)'),
        'empty': ('', ''),
    }
    value = dates[case][language == 'EN']
    context = dict(ReportNo='LAB-DATE-QA-0001', SampleName='QA sample', Client='QA client',
                   TestDate=value, ManufacturingDate=value, SampleArrivalDate='2026-10-27')
    before = deepcopy(context)
    blob, audit = document_module.render_report(
        dict(kind=kind, center='LAB', language=language, variant=variant), context)
    with ZipFile(BytesIO(blob)) as z:
        root = etree.fromstring(z.read('word/document.xml'))
        styles = etree.fromstring(z.read('word/styles.xml'))
    paragraphs = root.xpath('//w:p', namespaces=NS)
    texts = [''.join(p.xpath('.//w:t/text()', namespaces=NS)) for p in paragraphs]
    all_text = ''.join(texts)
    assert '{{' not in all_text and '{%' not in all_text and '<w:' not in all_text
    if value:
        for line in value.splitlines():
            assert all_text.count(line) == 2
        hits = [p for p in paragraphs if ''.join(p.xpath('.//w:t/text()', namespaces=NS)) == value.replace('\n', '')]
        assert len(hits) == 2
        for p in hits:
            assert p.xpath('ancestor::w:tc', namespaces=NS)
            style = p.xpath('./w:pPr/w:pStyle/@w:val', namespaces=NS)[0]
            assert styles.xpath('//w:style[@w:styleId=$style]', namespaces=NS, style=style)
    if kind == 'sampling':
        assert '2026-10-27' in all_text
    assert context == before
    assert audit.get('capacityWarnings', []) == []

@pytest.mark.parametrize('field', ['TestDate', 'ManufacturingDate'])
@pytest.mark.parametrize('authoring', [False, True])
def test_long_dates_follow_published_doc_layout_policy(field, authoring):
    profile = dict(kind='product', center='LAB', language='EN', variant='Standard')
    value = '1 Sep 2026 to 3 Sep 2026\n' * 100
    context = {'ReportNo':'LAB-DATE-QA-0002', field:value}
    blob, audit = document_module.render_report(profile, context, authoring=authoring)
    assert field in audit['capacityWarnings']
    with ZipFile(BytesIO(blob)) as z:
        root = etree.fromstring(z.read('word/document.xml'))
    text = ''.join(root.xpath('//w:t/text()', namespaces=NS))
    assert text.count('1 Sep 2026 to 3 Sep 2026') == 100
