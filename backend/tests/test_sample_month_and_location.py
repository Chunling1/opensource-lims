from datetime import date
import pytest
from app.extensions import db
from app.models import Report, StdLibraryItem
from app.report_date_rules import production_date, validate_date_order
from app.report_date_policy import sample_date_values
from app.report_date_display import report_date
from app.entrust_render import _business_category
from test_sample_pricing import business, create, detail
from test_onsite_manual_address import catalog

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('value', ['2026-10', '2026-10-22', '2024-02-29'])
def test_production_precision_retained(value):
    assert production_date(value) == value


@pytest.mark.parametrize('value', ['2026-00', '2026-13', '2026-02-29', '2026-2', '0000-10'])
def test_invalid_production_rejected(value):
    with pytest.raises(ValueError): production_date(value)


def test_month_order_without_inventing_a_stored_day():
    source = {'rawSample': {'produceDate': '2026-10', 'sendDate': '2026-10-01'},
              'summary': [{'fields': [['生产日期', '2026-10']]}]}
    values = sample_date_values(source, '2026-10-01')
    assert values['produce'] == '2026-10'
    assert validate_date_order(values) is None
    assert '不得早于生产日期' in validate_date_order({**values, 'send': '2026-09-30'})
    assert validate_date_order({'produce': '2026-10-22', 'send': '2026-10-21'})
    assert validate_date_order({'produce': '2026-10', 'send': '2026-10'}) == '送样日期必须为有效日期'
    assert report_date('2026-10') == '2026年10月'
    assert report_date('2026-10-22') == '2026年10月22日'
    assert _business_category('委托（有见证送检）') == '委托（有见证送检）'


def test_month_and_witness_category_save_roundtrip(business):
    client, headers, parents = business
    value = detail()
    month = date.today().isoformat()[:7]
    value['rawSample'].update(produceDate=month, testCategory='委托（有见证送检）')
    result = create(client, headers, parents[0], 'MONTH-QA', value)
    assert result['code'] == 0, result
    stored = Report.query.filter_by(report_no='MONTH-QA').one().detail['rawSample']
    assert stored['produceDate'] == month
    assert stored['testCategory'] == '委托（有见证送检）'


def test_manual_and_copied_locations_visible_without_granting_capabilities(catalog):
    client, headers, rows = catalog
    rows[0].location = '示例站点B'
    copied = StdLibraryItem(code='TEST-COPY', name='复制地点标准', location=rows[0].location,
                            use_depts=rows[0].use_depts)
    db.session.add(copied); db.session.commit()
    result = client.get('/api/quality/std-library/search?keyword=示例站点B', headers=headers).get_json()
    assert result['code'] == 0
    found = {r['code']: r for r in result['data']['rows']}
    assert found['TEST-normal']['location'] == found['TEST-COPY']['location'] == '示例站点B'
    assert found['TEST-normal']['sites'] == ['实验室']
    assert found['TEST-COPY']['sites'] == []
    assert found['TEST-COPY']['cnas'] is False


@pytest.mark.parametrize('kind', ['product', 'product-extended'])
def test_month_precision_in_actual_word(isolated_app, monkeypatch, kind):
    from test_entrust_output_release import objects
    from app import docparser_field_only as fields
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName': '虚拟机构'})
        entrust, report = objects(kind)
        report.report_no = 'LAB-TEST-R'
        report.detail['rawSample'].update(produceDate='2026-09', testCategory='委托（有见证送检）')
        blob, _ = fields.render_entrust(entrust, report, kind)
        with ZipFile(BytesIO(blob)) as package:
            rendered = ''.join(etree.fromstring(package.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        assert '2026年9月' in rendered
        assert '2026年9月1日' not in rendered
        assert '委托（有见证送检）' in rendered
