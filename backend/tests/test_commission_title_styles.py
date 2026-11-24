"""The commission uses the entire saved formatted text, never a UI page slice."""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from app import docparser_field_only as fields
from app.entrust_render import _business_values
from test_entrust_output_release import objects

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('kind', ['product', 'product-extended', 'engineering', 'engineering-extended'])
def test_mixed_commission_titles_survive_actual_template(isolated_app, monkeypatch, kind):
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName':'虚拟机构'})
        entrust, report = objects(kind)
        report.report_no = 'LAB-TEST-R'
        expected = 'GB 1-2024 《甲标准》；\nGB 2-2024 <乙标准>；\nGB 3-2024 丙标准'
        report.detail['rawSample'].update(basisTitleStyles={'GB 1-2024':'CN','GB 2-2024':'EN','GB 3-2024':'none'},
                                         commissionText={'basis':expected, 'items':'温度'})
        before = deepcopy(report.detail)
        assert _business_values(entrust, report)['basis'] == expected
        assert fields.entrust_context(entrust, report, kind)['Basis'] == expected
        blob, _ = fields.render_entrust(entrust, report, kind)
        with ZipFile(BytesIO(blob)) as package:
            text = ''.join(etree.fromstring(package.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        for row in expected.split('\n'):
            assert row in text
        assert report.detail == before


def test_all_fifty_standards_reach_commission_context(isolated_app, monkeypatch):
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName':'虚拟机构'})
        entrust, report = objects()
        report.report_no = 'LAB-TEST-R'
        expected = '；\n'.join(f'GB {i}-2024 《标准{i}》' for i in range(1,51))
        report.detail['rawSample']['commissionText'] = {'basis':expected}
        assert fields.entrust_context(entrust, report, 'product')['Basis'] == expected
