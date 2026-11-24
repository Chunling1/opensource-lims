from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from app import docparser_field_only as fields
from app.report_english_fields import (
    CATEGORIES, SITES, english_category, english_place, localize_report_fields,
)
from test_docparser_deep_integration import application, report


@pytest.fixture(autouse=True)
def synthetic_publication(monkeypatch):
    from app.blueprints import report_publication
    # Rendering tests do not create or query real QR publication records.
    monkeypatch.setattr(report_publication, 'report_qr_url',
                        lambda _: 'https://example.invalid/report/english-fields')


def docx_text(blob):
    with ZipFile(BytesIO(blob)) as package:
        return ''.join(etree.fromstring(package.read('word/document.xml')).xpath(
            '//*[local-name()="t"]/text()'))


@pytest.mark.parametrize('chinese,english', CATEGORIES.items())
def test_category_translations(chinese, english):
    assert english_category(chinese) == english
    assert english_category(chinese.replace('(', '（').replace(')', '）')) == english


@pytest.mark.parametrize('aliases,english', SITES)
def test_complete_site_aliases(aliases, english):
    for alias in aliases:
        assert english_place(alias) == english
        assert english_place('(校准实验室)' + alias) == english
        assert english_place('（校准实验室）' + alias) == english
    assert english_place(english) == english


def test_custom_locations_are_not_guessed_and_source_is_not_mutated():
    context = dict(Category='特殊委托', Place='北京市示例站点B区客户现场；示例市南区科研西路30号院',
                   SampleName='中文自定义样品')
    before = deepcopy(context)
    result = localize_report_fields(context, language='EN')
    assert result['Category'] == context['Category']
    assert result['Place'] == '北京市示例站点B区客户现场; 示例市南区科研西路30号院'
    assert result['SampleName'] == context['SampleName']
    assert context == before
    assert localize_report_fields(context, language='CN') == before
    assert english_place('/') == '/'
    assert english_place('') == ''


def test_multiple_sites_translate_individually_and_are_idempotent():
    source = '；'.join(aliases[-1] for aliases, _ in SITES)
    expected = '; '.join(english for _, english in SITES)
    assert english_place(source) == expected
    assert english_place(expected) == expected
    assert english_place('示例站点B\r\n示例站点A') == SITES[0][1] + '; ' + SITES[4][1]


PROFILES = [('产品报告', 'Standard'), ('产品报告', 'Extended'),
            ('抽样报告', 'Standard'), ('抽样报告', 'Extended'),
            ('工程报告', 'Standard'), ('检验报告', 'Standard')]


@pytest.mark.parametrize('kind,variant', PROFILES)
@pytest.mark.parametrize('language', ['CN', 'EN'])
def test_actual_report_pipeline_preserves_data_and_renders_language(application, kind, variant, language):
    item = report(kind)
    item.report_no = 'LAB-2026QA-0001'
    category = '委托（有见证送检）'
    place = '（校准实验室）示例市东区实验大道2号'
    item.detail['rawSample'].update(reportLanguage=language, reportTemplateVariant=variant,
                                   testCategory=category, testLocation=place, appearance='正常')
    before = deepcopy(item.detail)
    context = fields.report_context(item)
    assert context['Category'] == ('Commission (with Witnessed Sampling)' if language == 'EN' else category)
    assert context['Place'] == (SITES[0][1] if language == 'EN' else place)
    assert context['SampleCondition'] == ('Normal' if language == 'EN' else '正常')
    blob, audit = fields.render_preview(item)
    rendered = docx_text(blob)
    assert context['Category'] in rendered
    if kind == '产品报告':
        assert context['SampleCondition'] in rendered
    if kind in ('产品报告', '抽样报告'):
        assert context['Place'] in rendered
    else:
        # The supplied engineering/inspection template has only a cover and
        # uploaded body, with no system Place slot. Do not invent a new field.
        from app.document_module import VENDOR
        template = VENDOR / 'assets/templates' / fields.profile_for(item)['filename']
        assert '{{ Place }}' not in docx_text(template.read_bytes())
    assert not audit.get('capacityWarnings')
    if language == 'EN':
        assert category not in rendered and place not in rendered
    assert item.detail == before


@pytest.mark.parametrize('value,expected', [('异常', 'Abnormal'), (' 正常 ', 'Normal'),
    ('正常，包装有划痕', '正常，包装有划痕'), ('Normal', 'Normal'), ('/', '/'), ('', ''), (None, None)])
def test_sample_condition_exact_choices_only(value, expected):
    context = dict(SampleCondition=value, SealingCondition='正常', TaskSource='委托')
    result = localize_report_fields(context, language='EN')
    assert result == dict(SampleCondition=expected, SealingCondition='正常', TaskSource='委托')
    assert localize_report_fields(context, language='CN') == context
    assert context['SampleCondition'] == value


@pytest.mark.parametrize('aliases,english', SITES)
def test_each_address_survives_actual_english_template(application, aliases, english):
    item = report()
    item.detail['rawSample'].update(reportLanguage='EN', testLocation=aliases[-1])
    blob, audit = fields.render_preview(item)
    assert english in docx_text(blob)
    assert not audit.get('capacityWarnings')


def test_actual_location_uses_english_prefix_when_truncated(application):
    item = report()
    item.detail['rawSample'].update(reportLanguage='EN',
                                   testLocation='；'.join(aliases[-1] for aliases, _ in SITES))
    blob, audit = fields.render_preview(item)
    rendered = docx_text(blob)
    if audit.get('noticeCodes'):
        assert audit['noticeCodes'] == ['LOCATION_TRUNCATED']
        assert SITES[0][1][:20] in rendered
    else:
        for _, english in SITES:
            assert english in rendered
    assert 'HN-LOCATION-V1' not in rendered


@pytest.mark.parametrize('authoring', [False, True])
def test_single_long_english_address_fits_existing_cell(application, authoring):
    item = report()
    item.detail['rawSample'].update(reportLanguage='EN', testLocation=SITES[3][0][-1])
    blob, audit = fields.render_preview(item, authoring=authoring)
    assert not audit.get('locationAppendix')
    rendered = docx_text(blob)
    assert 'See testing location appendix' not in rendered
    assert SITES[3][1] in rendered
    assert not audit.get('capacityWarnings')


def test_short_english_address_stays_on_home_page(application):
    item = report()
    item.detail['rawSample'].update(reportLanguage='EN', testLocation='示例站点B')
    blob, audit = fields.render_preview(item)
    assert not audit.get('locationAppendix')
    assert SITES[0][1] in docx_text(blob)
    with ZipFile(BytesIO(blob)) as package:
        root = etree.fromstring(package.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraph = root.xpath('//w:p[.//w:t[contains(text(), "Lab Avenue")]]', namespaces=ns)
    assert len(paragraph) == 1
    assert paragraph[0].find('w:pPr/w:pStyle', ns) is not None  # vendor paragraph style


@pytest.mark.parametrize('source', ['summary', 'checkInput', 'entrustSnapshot'])
def test_alternative_stored_place_sources(application, source):
    item = report()
    item.detail['rawSample'].update(reportLanguage='EN', testLocation='')
    address = SITES[1][0][-1]
    if source == 'summary':
        item.detail['summary'].append({'title': '实验信息', 'fields': [['检测地点', address]]})
    elif source == 'checkInput':
        item.detail['checkInput'] = {'calibrationPlace': address}
    else:
        item.detail['entrustSnapshot']['info']['testLocation'] = address
    before = deepcopy(item.detail)
    assert fields.report_context(item)['Place'] == SITES[1][1]
    assert item.detail == before
