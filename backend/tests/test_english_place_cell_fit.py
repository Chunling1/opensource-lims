"""R-TPL-EN-01: pass full English addresses to the vendor layout."""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from app import docparser_field_only as fields
from app.report_english_fields import SITES
from test_docparser_deep_integration import application, report


@pytest.fixture(autouse=True)
def synthetic_qr(monkeypatch):
    from app.blueprints import report_publication
    monkeypatch.setattr(report_publication, 'report_qr_url',
                        lambda _: 'https://example.invalid/english-cell-fit')


def body(blob):
    with ZipFile(BytesIO(blob)) as package:
        return etree.fromstring(package.read('word/document.xml'))


@pytest.mark.parametrize('kind,variant', [
    ('产品报告', 'Standard'), ('产品报告', 'Extended'),
    ('抽样报告', 'Standard'), ('抽样报告', 'Extended')])
@pytest.mark.parametrize('site', [1, 3])
@pytest.mark.parametrize('authoring', [False, True])
def test_existing_cell_keeps_full_foshan_and_anyi_address(application, kind, variant, site, authoring):
    item = report(kind)
    item.report_no = 'LAB-2026QA-0001'
    item.detail['rawSample'].update(reportLanguage='EN', reportTemplateVariant=variant,
                                   testLocation=SITES[site][0][-1])
    before = deepcopy(item.detail)
    blob, audit = fields.render_preview(item, authoring=authoring)
    root = body(blob)
    text = ''.join(root.xpath('//*[local-name()="t"]/text()'))
    assert not audit.get('locationAppendix'), 'address fits the supplier cell'
    assert SITES[site][1] in text
    assert 'See testing location appendix' not in text
    assert item.detail == before
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs = root.xpath('//w:p[.//w:t[contains(text(), $address)]]',
                            namespaces=ns, address=SITES[site][1])
    assert len(paragraphs) == 1
    sizes = paragraphs[0].xpath('./w:r/w:rPr/w:sz/@w:val', namespaces=ns)
    # Vendor paragraph style owns font selection; platform no longer refits it.
    assert paragraphs[0].xpath('./w:pPr/w:pStyle', namespaces=ns)


def test_genuinely_overlong_address_is_passed_full_to_vendor(application):
    item = report()
    address = 'Very long customer site address, building number 123; ' * 20
    item.detail['rawSample'].update(reportLanguage='EN', testLocation=address)
    before = deepcopy(item.detail)
    blob, audit = fields.render_preview(item)
    assert audit['noticeCodes'] == []
    text = ''.join(body(blob).itertext())
    expected = fields.report_context(item)["Place"]
    assert expected == address.rstrip("; ")  # existing site-list separator normalization
    assert expected in text
    assert 'See testing location appendix' not in text
    assert item.detail == before


@pytest.mark.parametrize('kind,variant', [
    ('产品报告', 'Standard'), ('产品报告', 'Extended'),
    ('抽样报告', 'Standard'), ('抽样报告', 'Extended')])
def test_explicit_address_line_breaks_are_preserved(application, kind, variant):
    item = report(kind)
    address = 'R&D Testing Center,\nNo.166, Dongyang Avenue,\nAnyi, Nanchang, China'
    item.detail['rawSample'].update(reportLanguage='EN', reportTemplateVariant=variant)
    context = fields.report_context(item)
    context['Place'] = address
    from app import document_module
    blob, audit = document_module.render_report(fields.profile_for(item), context)
    assert not audit.get('locationAppendix')
    root = body(blob)
    text = ''.join(root.xpath('//*[local-name()="t"]/text()'))
    assert address.replace('\n', '') in text
    assert len(root.xpath('//*[local-name()="br"]')) >= 2
