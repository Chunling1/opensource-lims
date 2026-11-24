from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

import pytest
from lxml import etree

from app import docparser_field_only as fields, document_module
from app.models import Report
from app.report_date_display import report_date, format_report_dates
from app.report_date_rules import production_date, validate_date_order
from app.report_date_policy import sample_date_values
from test_sample_pricing import business, create, detail
from test_docparser_deep_integration import report

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('value,expected', [
    ('2026-10-24', '24 Oct 2026'), ('2026年10月24日', '24 Oct 2026'),
    ('2026-09', 'Sep 2026'), ('2024-02-29', '29 Feb 2024'),
    ('2026-10-01 ～ 2026-10-24', '1 Oct 2026 ～ 24 Oct 2026'),
    ('2026-10-29至2026-10-30', '29 Oct 2026 to 30 Oct 2026'),
    ('2026年10月29日 至 2026年10月30日', '29 Oct 2026 to 30 Oct 2026'),
    ('2026-10-29至2026-10-30；2026-11-01至2026-11-02',
     '29 Oct 2026 to 30 Oct 2026; 1 Nov 2026 to 2 Nov 2026'),
    ('2026-10-29；2026-10-30', '29 Oct 2026; 30 Oct 2026'),
    ('29 Oct 2026至30 Oct 2026', '29 Oct 2026 to 30 Oct 2026'),
    ('29 Oct 2026 to 30 Oct 2026', '29 Oct 2026 to 30 Oct 2026'),
    ('截至2026-10-30；未提供', '截至30 Oct 2026；未提供'),
    ('2026-02-29至2026-03-01', '2026-02-29至1 Mar 2026'),
    ('', ''), ('/', '/'), ('—', '—'), ('2026-02-29', '2026-02-29'),
])
def test_english_dates(value, expected):
    assert report_date(value, language='EN') == expected
    assert format_report_dates({'ReportDate': value, 'ReportNo': value}, language='EN') == {
        'ReportDate': expected, 'ReportNo': value}


def test_interval_translation_preserves_chinese_iso_and_non_date_fields():
    value = '2026-10-29至2026-10-30；2026-11-01'
    assert report_date(value) == '2026年10月29日至2026年10月30日；2026年11月1日'
    assert report_date(value, language='EN', iso=True) == value
    values = {'TestDate': value, 'Remark': value, 'Basis': value, 'ReportNo': value}
    assert format_report_dates(values, language='EN') == {
        **values, 'TestDate': '29 Oct 2026 to 30 Oct 2026; 1 Nov 2026'}
    assert values['TestDate'] == value


@pytest.mark.parametrize('marker', ['/', '—', 'N/A', '未提供'])
def test_marker_registration_roundtrip_and_output(business, monkeypatch, marker):
    client, headers, parents = business
    value = detail()
    value['rawSample']['produceDate'] = marker
    value['summary'].append({'title': '送样信息', 'fields': [['生产日期', marker]]})
    result = create(client, headers, parents[0], 'MARKER-QA', value)
    assert result['code'] == 0, result
    saved = Report.query.filter_by(report_no='MARKER-QA').one()
    assert saved.detail['rawSample']['produceDate'] == marker
    assert sample_date_values(saved.detail, None)['produce'] == marker
    assert production_date(marker) == marker
    assert validate_date_order({'produce': marker, 'send': '2026-10-01'}) is None
    assert '不得早于抽样日期' in validate_date_order({
        'produce': marker, 'sample': '2026-10-24', 'send': '2026-10-23'})
    from app.report_documents import report_values
    assert report_values(saved)['productionDate'] == marker
    from test_entrust_output_release import objects
    entrust, item = objects()
    item.report_no = 'LAB-TEST-R'
    item.detail['rawSample']['produceDate'] = marker
    monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName': '虚拟机构'})
    assert fields.entrust_context(entrust, item, 'product')['ManufacturingDate'] == marker
    blob, _ = fields.render_entrust(entrust, item, 'product')
    with ZipFile(BytesIO(blob)) as archive:
        xml = etree.fromstring(archive.read('word/document.xml'))
        assert marker in ''.join(xml.xpath('//*[local-name()="t"]/text()'))


PROFILES = [(kind, variant, language)
            for kind, variants in [('产品报告', ['Standard', 'Extended']),
                                   ('抽样报告', ['Standard', 'Extended']),
                                   ('工程报告', ['Standard']), ('检验报告', ['Standard'])]
            for variant in variants for language in ['CN', 'EN']]
PROFILES.append(('校准报告', 'Standard', 'CN'))


@pytest.mark.parametrize('kind,variant,language', PROFILES)
@pytest.mark.parametrize('corrected', [True, False])
def test_actual_report_templates_use_language_and_preserve_markers(isolated_app, monkeypatch, kind, variant, language, corrected):
    from app import report_final_fields
    from app.blueprints import report_publication
    original_run = document_module.subprocess.run
    def checked_run(*args, **kwargs):
        result = original_run(*args, **kwargs)
        assert result.returncode == 0, result.stderr or result.stdout
        return result
    monkeypatch.setattr(document_module.subprocess, 'run', checked_run)
    with isolated_app.app_context():
        item = report(kind)
        item.id = 0
        item.report_kind = 'correction' if corrected else 'main'
        # LAB is the vendor-supported center for all five report categories.
        item.report_no = 'LAB-TEST-001'
        item.department = ''
        item.detail['rawSample'].update(reportLanguage=language, reportTemplateVariant=variant,
                                       produceDate='—')
        item.detail['checkInput'] = {'testIntervals': [
            {'start': '2026-10-29', 'end': '2026-10-30'}]}
        item.detail['summary'].append({'title': '实验信息', 'fields': [['原报告日期', '2026-09-23']]})
        before = deepcopy(item.detail)
        monkeypatch.setattr(report_final_fields, 'approval_date', lambda _: '2026-10-24')
        monkeypatch.setattr(report_publication, 'report_qr_url', lambda _: 'https://example.invalid/report/date-test')
        context = fields.report_context(item)
        expected = '24 Oct 2026' if language == 'EN' else '2026年10月24日'
        original = '23 Sep 2026' if language == 'EN' else '2026年9月23日'
        assert context['ReportDate'] == ''  # Final issue date is bound on the approved PDF.
        assert context['OriginalReportDate'] == (original if corrected else '')
        assert context['ManufacturingDate'] == '—'
        interval = ('29 Oct 2026 to 30 Oct 2026' if language == 'EN'
                    else '2026年10月29日至30日')
        assert context['TestDate'] == interval
        selection = fields.profile_for(item)
        blob, _ = document_module.render_report(selection, context)
        with ZipFile(BytesIO(blob)) as archive:
            text = ''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        assert expected not in text
        if corrected:
            assert original in text
        else:
            assert original not in text
            assert '原签发日期' not in text and '更正签发日期' not in text
            assert 'Original Issue Date' not in text and 'Revised Issue Date' not in text
        if language == 'CN' and kind in ('产品报告', '抽样报告'):
            assert interval in text
        if language == 'EN':
            assert '2026年' not in text
            if kind in ('产品报告', '抽样报告'):
                assert interval in text
                assert '29 Oct 2026至30 Oct 2026' not in text
        assert item.detail == before
